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
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# 配置日志：输出到文件+控制台
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 获取环境变量
API_KEY = os.getenv("AMAP_API_KEY")
logger.debug(f"环境变量加载 - API_KEY是否存在: {bool(API_KEY)}, 数据库密码是否存在: {bool(DB_PASSWORD)}")

# 城市信息缓存（避免重复插入相同城市/省份数据）
city_cache = {}  # 格式: {城市名称: (城市ID, 省份ID)}

# 高德景点分类代码（部分）
SCENIC_TYPES = {
    "风景名胜1": "110100",
    "风景名胜2": "110101",
    "风景名胜3": "110102",
    "风景名胜4": "110103",
    "风景名胜5": "110104",
    "风景名胜6": "110105",
    "风景名胜7": "110106",
    "风景名胜8": "110200",
    "风景名胜9": "110201",
    "风景名胜10": "110202",
    "风景名胜11": "110203",
    "风景名胜12": "110204",
    "风景名胜13": "110205",
    "风景名胜14": "110206",
    "风景名胜15": "110207",
    "风景名胜16": "110208",
    "风景名胜17": "110209",
    "风景名胜18": "110210",
    "科教文化1": "140100",
    "科教文化2": "140101",
    "科教文化3": "140102",
    "科教文化4": "140200",
    "科教文化5": "140201",
    "科教文化6": "140300",
    "科教文化7": "140400",
    "科教文化8": "140500",
    "科教文化9": "140600",
    "科教文化10": "140700",
}

# 景点词典路径
SCENIC_DICTIONARY_PATH = "scenic_dictionary.json"

def load_scenic_dictionary():
    """加载景点词典"""
    try:
        if os.path.exists(SCENIC_DICTIONARY_PATH):
            with open(SCENIC_DICTIONARY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"加载景点词典失败: {str(e)}")
        return []

def save_scenic_dictionary(dictionary):
    """保存景点词典"""
    try:
        with open(SCENIC_DICTIONARY_PATH, 'w', encoding='utf-8') as f:
            json.dump(list(dictionary), f, ensure_ascii=False, indent=2)
        logger.info(f"景点词典已保存，共 {len(dictionary)} 个景点")
    except Exception as e:
        logger.error(f"保存景点词典失败: {str(e)}")

def update_scenic_dictionary(new_names):
    """更新景点词典，去重并保存"""
    existing_names = set(load_scenic_dictionary())
    new_valid_names = [name for name in new_names if name and isinstance(name, str)]
    
    if not new_valid_names:
        logger.info("无新景点名称需要更新")
        return 0
    
    added_count = 0
    for name in new_valid_names:
        if name not in existing_names:
            existing_names.add(name)
            added_count += 1
    
    if added_count > 0:
        save_scenic_dictionary(existing_names)
        logger.info(f"新增 {added_count} 个景点到词典")
    
    return added_count

def detect_scenic_spots(text):
    """从文本中检测景点名称"""
    if not text:
        return []
    
    scenic_names = load_scenic_dictionary()
    if not scenic_names:
        logger.warning("景点词典为空，无法检测")
        return []
    
    # 使用最长匹配原则
    detected = []
    remaining_text = text
    
    while remaining_text:
        matched = False
        # 按名称长度排序，优先匹配长名称
        for name in sorted(scenic_names, key=len, reverse=True):
            if name in remaining_text:
                start_idx = remaining_text.index(name)
                detected.append({
                    "name": name,
                    "start": start_idx,
                    "end": start_idx + len(name)
                })
                # 从匹配位置之后继续检测
                remaining_text = remaining_text[start_idx + len(name):]
                matched = True
                break
        
        if not matched:
            break  # 没有更多匹配，退出循环
    
    return detected

def get_or_insert_city(city_name, province_name):
    """获取或插入城市/省份信息，使用悲观锁确保并发安全"""
    global city_cache
    cache_key = f"{province_name}_{city_name}"
    
    if cache_key in city_cache:
        logger.debug(f"缓存命中: {cache_key} -> {city_cache[cache_key]}")
        return city_cache[cache_key]
    
    config = {
        "host": "localhost",
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": "scenic_spots_db",
        "charset": "utf8mb4",
        "autocommit": False
    }
    
    try:
        with mysql.connector.connect(**config) as conn:
            cursor = conn.cursor()
            try:
                conn.start_transaction()
                
                # 查询并插入省份
                cursor.execute("SELECT id FROM provinces WHERE name = %s FOR UPDATE", (province_name,))
                province_result = cursor.fetchone()
                if province_result:
                    province_id = province_result[0]
                    logger.debug(f"省份已存在: {province_name} (ID={province_id})")
                else:
                    cursor.execute("INSERT INTO provinces (name) VALUES (%s)", (province_name,))
                    province_id = cursor.lastrowid
                    logger.info(f"插入新省份: {province_name} (ID={province_id})")
                
                # 查询并插入城市
                cursor.execute("SELECT id FROM cities WHERE name = %s AND province_id = %s FOR UPDATE", 
                              (city_name, province_id))
                city_result = cursor.fetchone()
                if city_result:
                    city_id = city_result[0]
                    logger.debug(f"城市已存在: {city_name} (ID={city_id})")
                else:
                    cursor.execute("INSERT INTO cities (name, province_id) VALUES (%s, %s)", 
                                  (city_name, province_id))
                    city_id = cursor.lastrowid
                    logger.info(f"插入新城市: {city_name} (ID={city_id})")
                
                conn.commit()
                city_cache[cache_key] = (city_id, province_id)
                return city_id, province_id
                
            except mysql.connector.IntegrityError as e:
                logger.error(f"唯一约束冲突: {str(e)}", exc_info=True)
                conn.rollback()
                return get_or_insert_city(city_name, province_name)
            except Exception as e:
                logger.critical(f"数据库操作失败: {str(e)}", exc_info=True)
                conn.rollback()
                raise
    except Exception as e:
        logger.error(f"获取城市/省份ID失败，返回默认值: {str(e)}")
        return 1, 1  # 失败时返回默认值（需确保默认ID存在）


def get_safe_str(value, default="", max_length=None):
    """安全转换为字符串，处理特殊类型和超长字符串"""
    if value is None:
        return default
    if isinstance(value, str):
        if max_length and len(value) > max_length:
            return value[:max_length]
        return value
    if isinstance(value, (list, dict)):
        try:
            json_str = json.dumps(value, ensure_ascii=False)
            return json_str[:max_length] if max_length and len(json_str) > max_length else json_str
        except:
            return str(value)
    return str(value)


def parse_opentime(time_str):
    """解析营业时间为start_time和end_time（HH:MM:SS格式）"""
    if not time_str:
        return None, None
    
    time_str_clean = get_safe_str(time_str).replace(" ", "")
    logger.debug(f"原始营业时间字符串: {time_str}, 清理后: {time_str_clean}")
    
    if "24小时营业" in time_str_clean or re.match(r'00:00-24:00', time_str_clean):
        return "00:00:00", "23:59:59"
    
    # 匹配HH:MM-HH:MM格式
    match = re.search(r'(\d{2}:\d{2})-(\d{2}:\d{2})', time_str_clean)
    if match:
        return f"{match.group(1)}:00", f"{match.group(2)}:00"
    
    # 处理带日期的格式（如"周一至周五 09:00-18:00"）
    time_part = re.search(r'(\d{1,2}:\d{2})-(\d{1,2}:\d{2})', time_str_clean)
    if time_part:
        start = time_part.group(1).zfill(5) + ":00"  # 补全为HH:MM:SS
        end = time_part.group(2).zfill(5) + ":00"
        return start, end
    
    logger.debug("未匹配到有效的营业时间格式")
    return None, None


def parse_number(value):
    """安全解析数值，处理特殊字符串"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list) and len(value) > 0:
        value = value[0]
    
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ["免费", "无", "未知"]:
            return 0.0
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_amap_data(keyword, city, page=1, limit=25, types=None, location=None, radius=None):
    """调用高德API v5获取景点数据（支持周边搜索）"""
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
        "show_fields": "business"  # 确保获取business字段（包含评分、营业时间等）
    }
    
    if types:
        params["types"] = types
    if location and radius:
        params["location"] = location
        params["radius"] = radius
        params["sortrule"] = "distance"  # 按距离排序
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.debug(f"发送API请求：{url}，参数：{params}")
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"API响应（前500字符）：{json.dumps(result, ensure_ascii=False)[:500]}...")
            
            if result.get("status") != "1":
                error_msg = f"API错误：{result.get('status')}，信息：{result.get('info')}"
                if attempt < max_retries - 1:
                    logger.warning(f"{error_msg}，重试({attempt+1}/{max_retries})")
                    time.sleep(2)
                    continue
                raise ValueError(error_msg)
            return result
        except json.JSONDecodeError as e:
            logger.error(f"API响应非JSON格式：{response.text[:200]}", exc_info=True)
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败：{str(e)}", exc_info=True)
        
        if attempt < max_retries - 1:
            logger.warning(f"重试({attempt+1}/{max_retries})")
            time.sleep(2)
    
    raise Exception(f"API请求失败，已重试{max_retries}次")


def get_db_connection():
    """获取数据库连接"""
    config = {
        "host": "localhost",
        "user": DB_USER,
        "password": DB_PASSWORD,
        "database": "scenic_spots_db",
        "charset": "utf8mb4",
        "autocommit": False
    }
    
    try:
        conn = mysql.connector.connect(**config)
        logger.info("数据库连接成功")
        return conn
    except Error as e:
        logger.critical(f"数据库连接失败: {str(e)}")
        raise


def import_to_mysql(spots):
    """导入景点数据到scenic_spots表（包含评分、营业时间等字段）并更新景点词典"""
    if not spots:
        logger.info("没有数据可导入")
        return 0, 0
    
    total_records = len(spots)
    success_count = 0
    fail_count = 0
    fail_reasons = []
    new_scenic_names = []  # 收集新增的景点名称
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.start_transaction()
        
        for idx, spot in enumerate(spots, 1):
            try:
                # 提取基础字段
                spot_id = spot.get("id", "")
                spot_name = get_safe_str(spot.get("name", "未知名称"), max_length=255)
                spot_type = get_safe_str(spot.get("type", ""), max_length=50)
                address = get_safe_str(spot.get("address", ""), max_length=255)
                
                # 解析经纬度
                location = spot.get("location", "")
                if not location or "," not in location:
                    raise ValueError(f"经纬度格式错误：{location}")
                lng_str, lat_str = location.split(",", 1)
                lng = float(lng_str.strip())
                lat = float(lat_str.strip())
                if not (-180 <= lng <= 180 and -90 <= lat <= 90):
                    raise ValueError(f"经纬度超出范围：{lng},{lat}")
                
                # 处理business字段（包含评分、费用、营业时间等）
                business = spot.get("business", {})
                if isinstance(business, str):
                    try:
                        business = json.loads(business)  # 解析JSON格式的business字段
                    except:
                        business = {}  # 解析失败则视为空
                
                # 解析评分和费用
                rating = parse_number(business.get("rating"))  # 评分（如4.5）
                cost = parse_number(business.get("cost"))      # 费用（如50.0元）
                
                # 解析营业时间
                opentime_week = get_safe_str(business.get("opentime_week", ""))  # 周营业时间
                opentime_today = get_safe_str(business.get("opentime_today", ""))  # 今日营业时间
                start_time, end_time = parse_opentime(opentime_week or opentime_today)  # 转换为标准时间格式
                
                # 处理商圈信息
                business_area = get_safe_str(business.get("business_area", ""), max_length=255)
                
                # 处理电话
                tel_raw = business.get("tel", "")
                tel = re.sub(r'[^\d,-]', '', tel_raw) if tel_raw else None  # 仅保留数字和符号
                if tel and len(tel) > 50:
                    tel = tel[:50]
                
                # 城市和省份信息
                city_name = get_safe_str(spot.get("cityname", ""))
                province_name = get_safe_str(spot.get("pname", ""))
                if not city_name or not province_name:
                    raise ValueError("城市或省份名称为空")
                city_id, province_id = get_or_insert_city(city_name, province_name)
                
                # 构建SQL（包含所有字段）
                sql = """
                INSERT INTO scenic_spots (
                    id, name, type, address, 
                    longitude, latitude, 
                    city_id, province_id, 
                    rating, cost,
                    open_time_start, open_time_end,
                    business_area, opentime_today, opentime_week,
                    tel
                ) VALUES (
                    %(id)s, %(name)s, %(type)s, %(address)s, 
                    %(longitude)s, %(latitude)s, 
                    %(city_id)s, %(province_id)s, 
                    %(rating)s, %(cost)s,
                    %(open_time_start)s, %(open_time_end)s,
                    %(business_area)s, %(opentime_today)s, %(opentime_week)s,
                    %(tel)s
                )
                ON DUPLICATE KEY UPDATE 
                    name = VALUES(name),
                    type = VALUES(type),
                    address = VALUES(address),
                    longitude = VALUES(longitude),
                    latitude = VALUES(latitude),
                    city_id = VALUES(city_id),
                    province_id = VALUES(province_id),
                    rating = VALUES(rating),
                    cost = VALUES(cost),
                    open_time_start = VALUES(open_time_start),
                    open_time_end = VALUES(open_time_end),
                    business_area = VALUES(business_area),
                    opentime_today = VALUES(opentime_today),
                    opentime_week = VALUES(opentime_week),
                    tel = VALUES(tel)
                """
                
                # 绑定参数（包含所有解析的字段）
                params = {
                    "id": spot_id,
                    "name": spot_name,
                    "type": spot_type,
                    "address": address,
                    "longitude": lng,
                    "latitude": lat,
                    "city_id": city_id,
                    "province_id": province_id,
                    "rating": rating,
                    "cost": cost,
                    "open_time_start": start_time,
                    "open_time_end": end_time,
                    "business_area": business_area,
                    "opentime_today": opentime_today,
                    "opentime_week": opentime_week,
                    "tel": tel
                }
                
                cursor.execute(sql, params)
                success_count += 1
                logger.info(f"第{idx}条数据插入成功：{spot_name}（评分：{rating or '无'}，费用：{cost or '无'}）")
                
                # 收集景点名称（用于更新词典）
                new_scenic_names.append(spot_name)
            
            except Exception as e:
                logger.error(f"处理景点数据时出错（跳过本条）: {str(e)}")
                fail_count += 1
                fail_reasons.append(f"第{idx}条（{spot_name}）：{str(e)}")
                continue
        
        conn.commit()
        logger.info(f"事务提交成功 - 总记录：{total_records}，成功：{success_count}，失败：{fail_count}")
        if fail_reasons:
            logger.warning(f"失败详情：{'; '.join(fail_reasons[:5])}...")
        
        # 更新景点词典
        if new_scenic_names:
            update_scenic_dictionary(new_scenic_names)
    
    except Error as e:
        logger.error(f"数据库错误: {str(e)}，回滚事务", exc_info=True)
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
        raise
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            logger.info("数据库连接已关闭")
    
    return success_count, fail_count


def search_scenic_spots_by_grid(city_id, radius=20000, grid_point_id=None):
    """基于grid_points表的网格点搜索周边景点并导入（支持指定单个网格点）"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        if grid_point_id:
            # 指定单个网格点
            cursor.execute("SELECT id, lng, lat FROM grid_points WHERE id = %s AND city_id = %s", 
                          (grid_point_id, city_id))
            grid_points = cursor.fetchall()
            if not grid_points:
                logger.warning(f"未找到网格点ID {grid_point_id}（城市ID {city_id}）")
                return 0
            logger.info(f"指定处理单个网格点：ID={grid_point_id}，坐标: {grid_points[0]['lng']},{grid_points[0]['lat']}")
        else:
            # 处理所有网格点
            cursor.execute("SELECT id, lng, lat FROM grid_points WHERE city_id = %s", (city_id,))
            grid_points = cursor.fetchall()
            total_points = len(grid_points)
            if total_points == 0:
                logger.warning(f"城市ID {city_id} 没有网格点数据，终止搜索")
                return 0
            logger.info(f"处理城市ID {city_id} 的所有网格点（共{total_points}个）")
        
        # 获取城市名称（用于API区域限制）
        cursor.execute("SELECT name FROM cities WHERE id = %s", (city_id,))
        city_result = cursor.fetchone()
        city_name = city_result['name'] if city_result else "未知城市"
        
        logger.info(f"开始查询 {city_name} 景点（半径：{radius}米）")
        total_spots = 0
        
        # 遍历每个网格点
        for idx, point in enumerate(grid_points, 1):
            grid_id = point['id']
            lng, lat = point['lng'], point['lat']
            logger.info(f"处理网格点 {idx}/{len(grid_points)}（ID: {grid_id}，坐标: {lng},{lat}）")
            
            # 按景点类型搜索（提高覆盖率）
            for category, type_code in SCENIC_TYPES.items():
                page = 1  # 修复页码从0开始的问题（原代码page=0会导致API请求异常）
                has_more = True
                
                while has_more:
                    try:
                        # 调用高德API周边搜索
                        result = get_amap_data(
                            keyword="",
                            city=city_name,
                            page=page,
                            limit=25,
                            types=type_code,
                            location=f"{lng},{lat}",
                            radius=radius
                        )
                        
                        pois = result.get("pois", [])
                        count = len(pois)
                        if count == 0:
                            logger.info(f"{category}在网格点{grid_id}周边无数据，结束查询")
                            has_more = False
                            break
                        
                        logger.info(f"{category}第{page}页获取 {count} 条数据")
                        
                        # 导入当前页数据
                        success, failed = import_to_mysql(pois)
                        total_spots += success
                        logger.info(f"成功导入 {success} 条{category}数据")
                        
                        # 判断是否有下一页
                        if count < 25:
                            has_more = False
                        else:
                            page += 1
                            time.sleep(0.5)  # 控制频率
                    
                    except Exception as e:
                        logger.error(f"查询网格点{grid_id}周边{category}数据时出错: {str(e)}")
                        has_more = False
                        time.sleep(2)  # 出错后等待
            
            # 每10个网格点更新进度（如果只处理1个网格点则跳过）
            if len(grid_points) > 1 and idx % 10 == 0:
                logger.info(f"进度: {idx}/{len(grid_points)} 个网格点，累计导入 {total_spots} 个景点")
            
            time.sleep(1)  # 避免API请求过于频繁
        
        logger.info(f"搜索完成，共导入 {total_spots} 个景点")
        return total_spots
    
    except Exception as e:
        logger.critical(f"网格点搜索出错: {str(e)}", exc_info=True)
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    try:
        # 输入城市ID（例如北京市ID=1）
        CITY_ID = 1  # 可根据实际城市ID修改
        SEARCH_RADIUS = 20000  # 搜索半径（米）
        
        # 指定测试的网格点ID（从数据库中查询获取）
        TEST_GRID_ID = None  # 设置为None则处理所有网格点，设置为具体ID则只处理单个网格点
        
        logger.info(f"开始导入景点数据（城市ID={CITY_ID}，网格点ID={TEST_GRID_ID}）")
        total_imported = search_scenic_spots_by_grid(CITY_ID, SEARCH_RADIUS, TEST_GRID_ID)
        logger.info(f"数据导入完成，共成功导入 {total_imported} 个景点")
        
        # 验证景点词典
        print("\n景点词典验证：")
        dictionary = load_scenic_dictionary()
        print(f"词典包含 {len(dictionary)} 个景点名称")
        if dictionary:
            print(f"前10个景点名称: {dictionary[:10]}")
        
        # 测试景点检测功能
        test_text = "我想去北京故宫和颐和园玩，明天去八达岭长城"
        print(f"\n测试文本: '{test_text}'")
        detected = detect_scenic_spots(test_text)
        if detected:
            print(f"检测到 {len(detected)} 个景点:")
            for spot in detected:
                print(f"- {spot['name']} (位置: {spot['start']}-{spot['end']})")
        else:
            print("未检测到景点")
            
    except Exception as e:
        logger.critical(f"程序运行失败：{str(e)}", exc_info=True)
        print(f"程序出错：{str(e)}（详情见app.log）")