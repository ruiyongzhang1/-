import mysql.connector
from mysql.connector import Error
import logging

class DatabaseManager:
    def __init__(self, host, user, password, database):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None

    def connect(self):
        """建立数据库连接"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connection = mysql.connector.connect(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    use_pure=True
                )
                return True
        except Error as e:
            logging.error(f"数据库连接失败: {e}")
            return False
        return True

    def disconnect(self):
        """关闭数据库连接"""
        if self.connection and self.connection.is_connected():
            self.connection.close()

    def query(self, processed_question):
        """根据处理后的问题查询数据库"""
        if not processed_question or not isinstance(processed_question, dict):
            logging.error("无效的查询参数")
            return []
        
        query_type = processed_question.get("type")
        
        # 1. 附近景点查询
        if query_type == "nearby":
            lat = processed_question.get("latitude")
            lon = processed_question.get("longitude")
            name = processed_question.get("name")
            radius = processed_question.get("radius", 5.0)
            
            query = """
                SELECT 
                    s.name, 
                    s.type, 
                    s.address, 
                    s.longitude, 
                    s.latitude,
                    s.rating,
                    s.cost,
                    (6371 * acos(cos(radians(%s)) * cos(radians(s.latitude)) * 
                    cos(radians(s.longitude) - radians(%s)) + 
                    sin(radians(%s)) * sin(radians(s.latitude)))) AS distance
                FROM scenic_spots s
                WHERE s.name != %s
                HAVING distance <= %s
                ORDER BY distance ASC
                LIMIT 10;
            """
            params = (lat, lon, lat, name, radius)
            return self._execute_query(query, params)
        
        # 2. 营业时间查询
        elif query_type == "open_time":
            name = processed_question.get("name")
            query = """
                SELECT name, open_time_start, open_time_end, opentime_today, opentime_week
                FROM scenic_spots
                WHERE name = %s
            """
            return self._execute_query(query, (name,))
        
        # 3. 门票价格查询
        elif query_type == "ticket_price":
            name = processed_question.get("name")
            query = """
                SELECT name, cost
                FROM scenic_spots
                WHERE name = %s
            """
            return self._execute_query(query, (name,))
        
        # 4. 城市景点查询
        elif query_type == "city_spots":
            city_name = processed_question.get("city_name")
            query = """
                SELECT 
                    s.name AS name,           -- 显式指定别名
                    s.type AS type,           -- 显式指定别名
                    s.rating AS rating,       -- 显式指定别名
                    s.address AS address,     -- 显式指定别名
                    c.name AS city_name,      -- 显式指定别名
                    p.name AS province_name   -- 显式指定别名
                FROM scenic_spots s
                JOIN cities c ON s.city_id = c.id
                JOIN provinces p ON c.province_id = p.id
                WHERE c.name LIKE %s
                ORDER BY s.rating DESC
                LIMIT 5;
            """
            return self._execute_query(query, (f"%{city_name}%",))
        
        # 5. 评分查询
        elif query_type == "rating":
            name = processed_question.get("name")
            query = """
                SELECT name, rating
                FROM scenic_spots
                WHERE name = %s
            """
            return self._execute_query(query, (name,))
        
        # 6. 位置查询
        elif query_type == "location":
            name = processed_question.get("name")
            query = """
                SELECT 
                    s.name, 
                    s.address,
                    c.name AS city_name,
                    p.name AS province_name
                FROM scenic_spots s
                JOIN cities c ON s.city_id = c.id
                JOIN provinces p ON c.province_id = p.id
                WHERE s.name = %s
            """
            return self._execute_query(query, (name,))
        
    # 8. 联系方式查询
        elif query_type == "contact":
            name = processed_question.get("name")
            query = """
                SELECT name, tel
                FROM scenic_spots
                WHERE name = %s
            """
            return self._execute_query(query, (name,))
        
        # 9. 城市查询
        elif query_type == "city":
            name = processed_question.get("name")
            query = """
                SELECT 
                    s.name, 
                    c.name AS city_name
                FROM scenic_spots s
                JOIN cities c ON s.city_id = c.id
                WHERE s.name = %s
            """
            return self._execute_query(query, (name,))
        
        # 10. 省份查询
        elif query_type == "province":
            name = processed_question.get("name")
            query = """
                SELECT 
                    s.name, 
                    p.name AS province_name
                FROM scenic_spots s
                JOIN cities c ON s.city_id = c.id
                JOIN provinces p ON c.province_id = p.id
                WHERE s.name = %s
            """
            return self._execute_query(query, (name,))

        # 其他类型查询
        return []

    def _execute_query(self, query, params=None):
        """执行SQL查询并处理结果"""
        if not self.connect():
            return []
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            print(f"执行SQL: {query}")
            print(f"参数: {params}")
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            
            # 处理经纬度为浮点数
            for row in results:
                if 'latitude' in row and row['latitude'] is not None:
                    row['latitude'] = float(row['latitude'])
                if 'longitude' in row and row['longitude'] is not None:
                    row['longitude'] = float(row['longitude'])
                if 'rating' in row and row['rating'] is not None:
                    row['rating'] = float(row['rating'])
                if 'cost' in row and row['cost'] is not None:
                    row['cost'] = float(row['cost'])
            
            if results:
                print(f"结果数量: {len(results)}")
                print(f"第一条记录结构: {list(results[0].keys())}")
                print(f"第一条记录内容: {results[0]}")
            else:
                print("查询结果为空")
            
            return results
        except Error as e:
            logging.error(f"查询数据库失败: {e}")
            return []
        finally:
            self.disconnect()

    def get_all_spot_names(self):
        """获取所有景点名称，用于构建词典"""
        if not self.connect():
            return []
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = "SELECT name FROM scenic_spots"
            cursor.execute(query)
            return [row["name"] for row in cursor.fetchall()]
        except Error as e:
            logging.error(f"获取景点名称失败: {e}")
            return []
        finally:
            self.disconnect()

    def get_spot_coordinates(self, name):
        """查询景点的经纬度信息"""
        if not self.connect():
            return None
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = """
                SELECT 
                    name, 
                    latitude, 
                    longitude,
                    city_id
                FROM scenic_spots 
                WHERE name = %s
            """
            cursor.execute(query, (name,))
            result = cursor.fetchone()
            
            if result:
                # 确保经纬度转换为浮点数
                result['latitude'] = float(result['latitude'])
                result['longitude'] = float(result['longitude'])
            
            return result
        except Error as e:
            logging.error(f"查询经纬度失败: {e}")
            return None
        finally:
            self.disconnect()