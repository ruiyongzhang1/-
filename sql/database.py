import pymysql
import math

class DatabaseManager:
    def __init__(self, host, user, password, database):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self._connect()

    def _connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                cursorclass=pymysql.cursors.DictCursor
            )
        except Exception as e:
            raise

    def _execute_query(self, query, params=None):
        """执行SQL查询并返回结果"""
        if not self.connection:
            self._connect()
            
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return results
        except Exception:
            return []

    def _get_common_query(self):
        """返回通用的景点查询SQL语句"""
        return """
            SELECT
                s.name AS name,
                s.type AS type,
                s.rating AS rating,
                s.address AS address,
                s.cost AS cost,
                s.open_time_start AS open_time_start,
                s.open_time_end AS open_time_end,
                s.opentime_today AS opentime_today,
                s.opentime_week AS opentime_week,
                s.tel AS tel,
                c.name AS city_name,
                p.name AS province_name
            FROM scenic_spots s
            JOIN cities c ON s.city_id = c.id
            JOIN provinces p ON c.province_id = p.id
        """

    def query(self, processed_questions):
        """执行查询并返回结果"""
        results = []
        
        for question in processed_questions:
            query_type = question.get("type")
            
            if query_type == "city_spots":
                city_name = question.get("city_name")
                if city_name:
                    query = self._get_common_query() + " WHERE c.name = %s"
                    city_results = self._execute_query(query, (city_name,))
                    results.extend(city_results)
                    
            elif query_type == "compound_filter":
                keywords = question.get("keywords", [])
                compound_results = self._execute_compound_filter(keywords)
                results.extend(compound_results)
                
            elif query_type == "spot_info":
                spot_name = question.get("spot_name")
                attributes = question.get("attributes", [])
                # 构建景点信息查询
                columns = []
                if "评分" in attributes:
                    columns.append("s.rating")
                if "位置" in attributes:
                    columns.append("s.address")
                if "电话" in attributes:
                    columns.append("s.tel")
                if "营业时间" in attributes:
                    columns.extend(["s.open_time_start", "s.open_time_end", "s.opentime_today", "s.opentime_week"])
                if "所在城市" in attributes:
                    columns.append("c.name")
                if not columns:
                    columns = ["s.name", "s.rating", "s.address", "s.tel", "s.open_time_start", "s.open_time_end", "s.opentime_today", "s.opentime_week", "c.name"]
                column_str = ", ".join(columns)
                query = f"SELECT {column_str} FROM scenic_spots s JOIN cities c ON s.city_id = c.id WHERE s.name = %s"
                spot_results = self._execute_query(query, (spot_name,))
                results.extend(spot_results)
            
            elif query_type == "nearby_spots":
                spot_name = question.get("spot_name")
                nearby_results = self._execute_nearby_spots_query(spot_name)
                results.extend(nearby_results)
        
        return results

    def _execute_nearby_spots_query(self, spot_name):
        """执行附近景点查询，基于经纬度计算距离"""
        # 首先查询目标景点的经纬度
        query = "SELECT longitude, latitude FROM scenic_spots WHERE name = %s"
        result = self._execute_query(query, (spot_name,))
        
        if not result:
            return []
            
        target_longitude = result[0]['longitude']
        target_latitude = result[0]['latitude']
        
        # 使用Haversine公式计算距离
        # 注意：不同数据库系统对三角函数的支持可能不同，这里使用MySQL的函数
        distance_query = f"""
            SELECT
                s.name AS name,
                s.type AS type,
                s.rating AS rating,
                s.address AS address,
                s.cost AS cost,
                s.open_time_start AS open_time_start,
                s.open_time_end AS open_time_end,
                s.opentime_today AS opentime_today,
                s.opentime_week AS opentime_week,
                s.tel AS tel,
                c.name AS city_name,
                p.name AS province_name,
                -- Haversine公式计算距离（单位：公里）
                6371 * 2 * ASIN(SQRT(
                    POWER(SIN((s.latitude - {target_latitude}) * PI()/180 / 2), 2) +
                    COS(s.latitude * PI()/180) * COS({target_latitude} * PI()/180) *
                    POWER(SIN((s.longitude - {target_longitude}) * PI()/180 / 2), 2)
                )) AS distance
            FROM scenic_spots s
            JOIN cities c ON s.city_id = c.id
            JOIN provinces p ON c.province_id = p.id
            WHERE s.name != %s
            ORDER BY distance ASC, s.rating DESC
            LIMIT 5
        """
        
        return self._execute_query(distance_query, (spot_name,))

    def _execute_compound_filter(self, keywords):
        """执行复合条件查询，合并所有条件到一个SQL查询中"""
        if not keywords:
            return []
            
        # 构建SQL查询条件和参数
        conditions = []
        params = []
        
        for keyword in keywords:
            query_type = keyword.get("type")
            
            if query_type == "city_spots":
                city_name = keyword.get("city_name")
                if city_name:
                    conditions.append("c.name = %s")
                    params.append(city_name)
                    
            elif query_type == "ticket_price":
                price_info = keyword.get("price")
                if price_info:
                    operator = price_info.get("operator", "<=")
                    value = price_info.get("value")
                    conditions.append(f"s.cost {operator} %s")
                    params.append(value)
                    
            elif query_type == "rating_spots":
                rating_info = keyword.get("rating")
                if rating_info:
                    operator = rating_info.get("operator", ">=")
                    value = rating_info.get("value")
                    conditions.append(f"s.rating {operator} %s")
                    params.append(value)
        
        # 构建完整SQL查询
        base_query = self._get_common_query()
        
        if conditions:
            where_clause = " AND ".join(conditions)
            full_query = f"{base_query} WHERE {where_clause}"
        else:
            full_query = base_query
        
        # 执行单个查询
        return self._execute_query(full_query, tuple(params))

    def get_all_cities(self):
        """获取所有城市名称"""
        query = "SELECT name FROM cities"
        results = self._execute_query(query)
        return [row["name"] for row in results]

    def get_all_spots(self):
        """获取所有景点名称"""
        query = "SELECT name FROM scenic_spots"
        results = self._execute_query(query)
        return [row["name"] for row in results]