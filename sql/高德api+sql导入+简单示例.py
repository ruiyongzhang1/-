import requests
import mysql.connector
from mysql.connector import Error
import time
import json
import os
from dotenv import load_dotenv
import logging
import re

# --------------------------
# 初始化配置与日志
# --------------------------
load_dotenv()  # 加载环境变量

# 配置日志：输出到文件+控制台
logging.basicConfig(
    level=logging.DEBUG,  # 修改为DEBUG级别以查看详细日志
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 获取环境变量
API_KEY = os.getenv("AMAP_API_KEY")
PASSWORD = os.getenv("DB_PASSWORD")
logger.debug(f"环境变量加载 - API_KEY是否存在: {bool(API_KEY)}, 数据库密码是否存在: {bool(PASSWORD)}")

# 城市信息缓存（避免重复插入相同城市/省份数据）
city_cache = {}  # 格式: {城市名称: (城市ID, 省份ID)}

# 高德景点分类代码（部分）
SCENIC_TYPES = {
    "风景名胜": "110100",
    "公园": "110200",
    "博物馆": "120200",
    "寺庙道观": "120100",
    "主题乐园": "110300",
    "展览馆": "120300",
    "文物古迹": "120101",
    "自然保护区": "110103",
    "地质公园": "110104",
    # 可根据需要扩展更多分类
}

def serialize_if_list(value):
    """将列表类型转换为JSON字符串，其他类型保持不变"""
    if isinstance(value, list):
        return json.dumps(value) if value else None
    return value

def get_or_insert_city(city_name, province_name):
    """获取或插入城市/省份信息，使用悲观锁确保并发安全"""
    global city_cache
    cache_key = f"{province_name}_{city_name}"
    
    # 优先从缓存获取
    if cache_key in city_cache:
        logger.debug(f"缓存命中: {cache_key} -> {city_cache[cache_key]}")
        return city_cache[cache_key]
    
    config = {
        "host": "localhost",
        "user": "root",
        "password": PASSWORD,
        "database": "scenic_spots_db",
        "charset": "utf8mb4",
        "autocommit": False  # 必须为False，才能使用事务和锁
    }
    
    try:
        # 创建独立连接处理城市/省份插入
        with mysql.connector.connect(**config) as conn:
            cursor = conn.cursor()
            
            try:
                # 步骤1：开启事务
                conn.start_transaction()
                
                # 步骤2：查询省份（使用悲观锁 FOR UPDATE）
                cursor.execute(
                    "SELECT id FROM provinces WHERE name = %s FOR UPDATE",
                    (province_name,)
                )
                province_result = cursor.fetchone()
                
                if province_result:
                    province_id = province_result[0]
                    logger.debug(f"省份已存在: {province_name} (ID={province_id})")
                else:
                    # 插入新省份
                    cursor.execute(
                        "INSERT INTO provinces (name) VALUES (%s)",
                        (province_name,)
                    )
                    province_id = cursor.lastrowid
                    logger.info(f"插入新省份: {province_name} (ID={province_id})")
                
                # 步骤3：查询城市（同样使用悲观锁）
                cursor.execute(
                    "SELECT id FROM cities WHERE name = %s AND province_id = %s FOR UPDATE",
                    (city_name, province_id)
                )
                city_result = cursor.fetchone()
                
                if city_result:
                    city_id = city_result[0]
                    logger.debug(f"城市已存在: {city_name} (ID={city_id})")
                else:
                    # 插入新城市
                    cursor.execute(
                        "INSERT INTO cities (name, province_id) VALUES (%s, %s)",
                        (city_name, province_id)
                    )
                    city_id = cursor.lastrowid
                    logger.info(f"插入新城市: {city_name} (ID={city_id})")
                
                # 步骤4：提交事务
                conn.commit()
                
                # 更新缓存
                city_cache[cache_key] = (city_id, province_id)
                return city_id, province_id
                
            except mysql.connector.IntegrityError as e:
                # 处理唯一约束冲突（理论上不会发生，因为有FOR UPDATE）
                logger.error(f"唯一约束冲突: {str(e)}", exc_info=True)
                conn.rollback()
                # 回滚后重试查询（可能其他事务已插入）
                return get_or_insert_city(city_name, province_name)
                
            except Exception as e:
                logger.critical(f"数据库操作失败: {str(e)}", exc_info=True)
                conn.rollback()
                raise  # 向上层抛出异常
                
    except Exception as e:
        logger.error(f"获取城市/省份ID失败，返回默认值: {str(e)}")
        return 1, 1  # 失败时返回默认值（谨慎使用，可能导致外键约束冲突）

def import_to_mysql(spots):
    """导入景点数据到MySQL，使用独立事务处理城市/省份插入"""
    if not spots:
        logger.info("没有数据可导入")
        return 0, 0

    total_records = len(spots)
    success_count = 0
    fail_count = 0
    fail_reasons = []

    config = {
        "host": "localhost",
        "user": "root",
        "password": PASSWORD,
        "database": "scenic_spots_db",
        "charset": "utf8mb4",
        "autocommit": False
    }

    try:
        logger.debug(f"尝试连接数据库: {config['host']}/{config['database']}")
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        logger.info("数据库连接成功")

        # 开始主事务
        conn.start_transaction()

        for idx, spot in enumerate(spots, 1):
            try:
                logger.debug(f"开始处理第{idx}/{total_records}条数据")
                
                # 获取基本信息
                spot_id = spot.get("id", "")
                spot_name = get_safe_str(spot.get("name", "未知名称"))
                spot_type = get_safe_str(spot.get("type", ""))

                logger.debug(f"处理第{idx}条数据：{spot_name}（ID: {spot_id}）")

                # 记录原始数据结构
                if idx == 5:
                    logger.warning(f"数据结构检查 - 第{idx}条（{spot_name}）：{json.dumps(spot, ensure_ascii=False)}")

                # 解析经纬度
                location = spot.get("location", "")
                if not location:
                    raise ValueError("缺少经纬度信息")
                if "," not in location:
                    raise ValueError(f"经纬度格式错误：{location}")

                lng_str, lat_str = location.split(",", 1)
                lng = float(lng_str.strip())
                lat = float(lat_str.strip())

                if not (-180 <= lng <= 180 and -90 <= lat <= 90):
                    raise ValueError(f"经纬度超出范围：经度={lng}, 纬度={lat}")

                # 处理business字段
                business = spot.get("business", {})
                if isinstance(business, str):
                    try:
                        business = json.loads(business)
                    except:
                        business = {}

                # 处理营业时间
                opentime_week = get_safe_str(business.get("opentime_week", ""))
                opentime_today = get_safe_str(business.get("opentime_today", ""))
                start_time, end_time = parse_opentime(opentime_week or opentime_today)

                # 处理其他字段
                cost = parse_number(business.get("cost"))
                rating = parse_number(business.get("rating"))
                
                # 处理电话
                tel = None
                tel_raw = business.get("tel", "")
                if tel_raw:
                    tel = re.sub(r'[^\d,-]', '', tel_raw)
                    if not tel:
                        tel = None

                # 处理楼层信息
                indoor_info = spot.get("indoor_info", {})
                floor = get_safe_str(indoor_info.get("floor", ""))
                truefloor = get_safe_str(indoor_info.get("truefloor", ""))

                # 获取城市和省份信息
                city_name = get_safe_str(spot.get("cityname", ""))
                province_name = get_safe_str(spot.get("pname", ""))
                
                # 确保城市和省份名称有效
                if not city_name or not province_name:
                    logger.warning(f"城市或省份名称为空: {city_name}/{province_name}")
                    raise ValueError("城市或省份名称不能为空")
                
                # 获取或插入城市/省份信息（使用独立事务）
                city_id, province_id = get_or_insert_city(city_name, province_name)

                # 构建SQL
                sql = """
                INSERT INTO scenic_spots (
                    id, name, type, address, 
                    longitude, latitude, 
                    rating, cost, open_time_start, open_time_end,
                    business_area, opentime_today, opentime_week, tel,
                    floor, truefloor, city_id, province_id
                ) VALUES (
                    %(id)s, %(name)s, %(type)s, %(address)s, 
                    %(longitude)s, %(latitude)s, 
                    %(rating)s, %(cost)s, %(open_time_start)s, %(open_time_end)s,
                    %(business_area)s, %(opentime_today)s, %(opentime_week)s, %(tel)s,
                    %(floor)s, %(truefloor)s, %(city_id)s, %(province_id)s
                )
                ON DUPLICATE KEY UPDATE 
                    name = VALUES(name),
                    type = VALUES(type),
                    address = VALUES(address),
                    longitude = VALUES(longitude),
                    latitude = VALUES(latitude),
                    rating = VALUES(rating),
                    cost = VALUES(cost),
                    open_time_start = VALUES(open_time_start),
                    open_time_end = VALUES(open_time_end),
                    opentime_today = VALUES(opentime_today),
                    opentime_week = VALUES(opentime_week),
                    tel = VALUES(tel),
                    floor = VALUES(floor),
                    truefloor = VALUES(truefloor),
                    city_id = VALUES(city_id),
                    province_id = VALUES(province_id)
                """

                # 构建参数
                params = {
                    "id": spot_id,
                    "name": spot_name,
                    "type": spot_type,
                    "address": get_safe_str(spot.get("address", "")),
                    "longitude": lng,
                    "latitude": lat,
                    "open_time_start": start_time,
                    "open_time_end": end_time,
                    "opentime_today": opentime_today,
                    "opentime_week": opentime_week,
                    "tel": tel,
                    "floor": floor,
                    "truefloor": truefloor,
                    "rating": rating,
                    "cost": cost,
                    "business_area": get_safe_str(business.get("business_area", "")),
                    "city_id": city_id,
                    "province_id": province_id
                }

                logger.debug(f"插入数据库的参数: {json.dumps(params, ensure_ascii=False)}")

                # 执行插入
                cursor.execute(sql, params)
                success_count += 1
                logger.info(f"第{idx}条数据插入成功：{spot_name}")

            except Exception as e:
                logger.error(f"处理景点数据时出错（跳过本条）: {str(e)}", exc_info=True)
                fail_count += 1
                fail_reasons.append(f"第{idx}条（{spot_name}）：{str(e)}")
                continue  # 继续处理下一条数据

        # 提交主事务
        conn.commit()
        logger.info(f"事务提交成功 - 总记录：{total_records}，成功：{success_count}，失败：{fail_count}")
        
        if fail_reasons:
            logger.warning(f"失败详情：{'; '.join(fail_reasons[:5])}...（仅显示前5条）")

    except Error as e:
        logger.error(f"数据库错误: {str(e)}，回滚事务", exc_info=True)
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
        raise
    except Exception as e:
        logger.critical(f"导入过程发生未知错误: {str(e)}，回滚事务", exc_info=True)
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
        raise
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            logger.info("数据库连接已关闭")

    print(f"导入完成：成功{success_count}条，失败{fail_count}条（详情见日志）")
    return success_count, fail_count

def validate_city_province(cursor, city_id, province_id):
    """验证城市和省份ID是否有效"""
    # 检查省份ID
    cursor.execute("SELECT id FROM provinces WHERE id = %s", (province_id,))
    if not cursor.fetchone():
        logger.error(f"无效的省份ID: {province_id}")
        return False
    
    # 检查城市ID
    cursor.execute("SELECT id FROM cities WHERE id = %s", (city_id,))
    if not cursor.fetchone():
        logger.error(f"无效的城市ID: {city_id}")
        return False
    
    # 检查城市是否属于该省份
    cursor.execute("SELECT id FROM cities WHERE id = %s AND province_id = %s", 
                  (city_id, province_id))
    if not cursor.fetchone():
        logger.error(f"城市ID {city_id} 不属于省份ID {province_id}")
        return False
    
    return True

def get_province_id(cursor, province_name):
    """获取省份ID"""
    cursor.execute("SELECT id FROM provinces WHERE name = %s", (province_name,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_city_id(cursor, city_name, province_id):
    """获取城市ID"""
    cursor.execute("SELECT id FROM cities WHERE name = %s AND province_id = %s", 
                  (city_name, province_id))
    result = cursor.fetchone()
    return result[0] if result else None

def get_safe_str(value, default="", max_length=None):
    """将值安全转换为字符串，处理列表、字典等情况，可限制最大长度"""
    if value is None:
        return default
    if isinstance(value, str):
        if max_length and len(value) > max_length:
            return value[:max_length]  # 截断超长字符串
        return value
    if isinstance(value, (list, dict)):
        try:
            json_str = json.dumps(value, ensure_ascii=False)
            if max_length and len(json_str) > max_length:
                return json_str[:max_length]
            return json_str
        except:
            return str(value)
    return str(value)

def parse_opentime(time_str):
    """解析营业时间字符串，返回start_time和end_time（确保格式为HH:MM:SS）"""
    if not time_str:
        return None, None
    
    time_str_clean = get_safe_str(time_str).replace(" ", "")
    logger.debug(f"原始营业时间字符串: {time_str}, 清理后: {time_str_clean}")
    
    if "24小时营业" in time_str_clean:
        return "00:00:00", "23:59:59"  # MySQL TIME类型最大为23:59:59
    elif re.match(r'00:00-24:00', time_str_clean):
        return "00:00:00", "23:59:59"
    
    # 匹配HH:MM-HH:MM格式
    match = re.search(r'(\d{2}:\d{2})-(\d{2}:\d{2})', time_str_clean)
    if match:
        start = match.group(1) + ":00"  # 转为HH:MM:SS格式
        end = match.group(2) + ":00"
        logger.debug(f"解析结果: 开始时间 {start}, 结束时间 {end}")
        return start, end
    
    # 处理其他可能的格式（如"周一至周五 09:00-18:00"）
    time_part = re.search(r'(\d{1,2}:\d{2})-(\d{1,2}:\d{2})', time_str_clean)
    if time_part:
        start = time_part.group(1).zfill(5) + ":00"  # 确保HH:MM格式
        end = time_part.group(2).zfill(5) + ":00"
        logger.debug(f"解析结果: 开始时间 {start}, 结束时间 {end}")
        return start, end
    
    logger.debug("未匹配到有效的营业时间格式")
    return None, None

def parse_number(value):
    """安全解析数值类型，处理列表、非数字字符串等情况"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list) and len(value) > 0:
        value = value[0]  # 尝试提取列表第一个元素
    
    # 处理特殊字符串
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
        if value.lower() in ["免费", "无", "未知"]:
            return 0.0
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def get_amap_data(keyword, city, page=1, limit=25, types=None):
    """调用高德API v5版本获取景点数据，适配v5的数据结构"""
    if not API_KEY:
        raise EnvironmentError("未配置高德API密钥（AMAP_API_KEY）")

    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "key": API_KEY,
        "keywords": keyword,
        "region": city,
        "page_num": page,
        "page_size": limit,
        "output": "json",
        "show_fields": "business"
    }
    
    # 如果指定了类型，添加到参数中
    if types:
        params["types"] = types

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.debug(f"发送API v5请求：{url}，参数：{params}")
            response = requests.get(url, params=params, timeout=15)  # 增加超时时间
            response.raise_for_status()
            logger.info(f"API v5请求成功（页码：{page}），状态码：{response.status_code}")

            try:
                result = response.json()
                logger.debug(f"API v5响应数据：{json.dumps(result, ensure_ascii=False)[:500]}...（截断显示）")
                
                # 检查API返回状态
                status = result.get("status")
                if status != "1":
                    error_msg = f"API返回错误状态：{status}，信息：{result.get('info')}"
                    if attempt < max_retries - 1:
                        logger.warning(f"{error_msg}，尝试重试 ({attempt+1}/{max_retries})")
                        time.sleep(2)  # 重试前等待2秒
                        continue
                    else:
                        raise ValueError(error_msg)
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"API v5响应解析失败（非JSON格式）：{response.text[:200]}", exc_info=True)
                if attempt < max_retries - 1:
                    logger.warning(f"尝试重试 ({attempt+1}/{max_retries})")
                    time.sleep(2)
                    continue
                raise

        except requests.exceptions.RequestException as e:
            logger.error(f"API v5请求失败：{str(e)}", exc_info=True)
            if attempt < max_retries - 1:
                logger.warning(f"尝试重试 ({attempt+1}/{max_retries})")
                time.sleep(2)
                continue
            raise
    
    # 如果所有重试都失败
    raise Exception(f"API请求失败，已尝试{max_retries}次")

def get_all_spots_by_type(city, limit=25):
    """按景点类型分类获取所有数据"""
    all_spots = []
    
    for category, type_code in SCENIC_TYPES.items():
        logger.info(f"开始获取{city}的{category}数据（类型代码：{type_code}）")
        page = 1
        
        while True:
            try:
                result = get_amap_data(
                    keyword="",  # 留空，按类型搜索
                    city=city,
                    page=page,
                    limit=limit,
                    types=type_code  # 指定景点类型
                )
                
                pois = result.get("pois", [])
                if not pois:
                    logger.info(f"{category}第{page}页没有数据，结束搜索")
                    break
                    
                logger.info(f"{category}第{page}页获取 {len(pois)} 条数据")
                all_spots.extend(pois)
                
                # 如果当前页数据不足limit，说明已到最后一页
                if len(pois) < limit:
                    break
                    
                page += 1
                time.sleep(0.5)  # 控制请求频率
                
            except Exception as e:
                logger.error(f"处理{category}第{page}页时出错: {str(e)}")
                page += 1  # 继续尝试下一页
                time.sleep(2)  # 错误后等待2秒
    
    # 去重（基于景点ID）
    unique_spots = []
    spot_ids = set()
    for spot in all_spots:
        spot_id = spot.get("id")
        if spot_id and spot_id not in spot_ids:
            spot_ids.add(spot_id)
            unique_spots.append(spot)
    
    logger.info(f"共获取 {len(unique_spots)} 个景点数据")
    return unique_spots

def get_nearby_spots(lng, lat, radius_km=5, limit=10):
    """查询指定坐标附近的景点"""
    config = {
        "host": "localhost",
        "user": "root",
        "password": PASSWORD,
        "database": "scenic_spots_db",
        "charset": "utf8mb4"
    }

    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor(dictionary=True)

        sql = """
        SELECT 
            s.id, s.name, s.type, s.address,
            s.longitude, s.latitude,
            c.name AS city_name, p.name AS province_name,
            s.rating, s.cost, 
            s.open_time_start, s.open_time_end,
            s.business_area, s.opentime_today, s.opentime_week, s.tel,
            s.floor, s.truefloor,
            6371 * 2 * ASIN(SQRT(
                POWER(SIN((%(lat)s - s.latitude) * PI()/180 / 2), 2) +
                COS(%(lat)s * PI()/180) * COS(s.latitude * PI()/180) *
                POWER(SIN((%(lng)s - s.longitude) * PI()/180 / 2), 2)
            )) AS distance_km
        FROM scenic_spots s
        JOIN cities c ON s.city_id = c.id
        JOIN provinces p ON s.province_id = p.id
        WHERE 
            s.longitude BETWEEN %(lng)s - %(range)s AND %(lng)s + %(range)s
            AND s.latitude BETWEEN %(lat)s - %(range)s AND %(lat)s + %(range)s
        ORDER BY distance_km ASC
        LIMIT %(limit)s
        """

        range_deg = radius_km / 111.0
        cursor.execute(sql, {
            'lng': lng,
            'lat': lat,
            'range': range_deg,
            'limit': limit
        })

        return cursor.fetchall()

    except Error as e:
        logger.error(f"查询附近景点失败：{str(e)}", exc_info=True)
        raise
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    try:
        city = "北京"
        limit = 25
        
        logger.info(f"开始全面导入{city}的景点数据")
        
        # 使用分类搜索策略获取所有景点
        all_spots = get_all_spots_by_type(city, limit)
        
        if not all_spots:
            logger.warning("未获取到任何景点数据！")
        else:
            # 分批导入数据库
            batch_size = 25
            total_success = 0
            total_failed = 0
            
            for i in range(0, len(all_spots), batch_size):
                batch = all_spots[i:i+batch_size]
                logger.info(f"处理第 {i//batch_size + 1} 批次，共 {len(batch)} 条数据")
                
                success_count, fail_count = import_to_mysql(batch)
                total_success += success_count
                total_failed += fail_count
                
                time.sleep(0.5)  # 批次间等待
                
            logger.info(f"所有数据处理完成 - 总成功：{total_success}，总失败：{total_failed}")
            
            # 测试查询
            print("\n测试：查询天安门附近的景点")
            nearby = get_nearby_spots(116.4039, 39.9152, radius_km=2)
            for spot in nearby:
                print(f"{spot['name']} - 距离: {spot['distance_km']:.2f}km")
                print(f"城市/省份: {spot['city_name']}/{spot['province_name']}")
                print(f"营业时间: {spot['opentime_today'] or spot['opentime_week']}")
                print(f"电话: {spot['tel'] or '无'}")
                print(f"门票价格: {spot['cost'] or '未知'}元")
                print("-" * 30)

    except Exception as e:
        logger.critical(f"程序运行失败：{str(e)}", exc_info=True)
        print(f"程序出错：{str(e)}（详情见app.log）")