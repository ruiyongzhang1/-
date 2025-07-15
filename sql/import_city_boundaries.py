import requests
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import logging
import time

# 配置日志

logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('import_boundaries.log'),  # 日志文件
        logging.StreamHandler()  # 控制台输出
    ]
)
logger = logging.getLogger(__name__)

# 加载环境变量（复用现有数据库配置）
load_dotenv()
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD"),
    "database": "scenic_spots_db",  # 直接使用现有数据库
    "charset": "utf8mb4"
}
AMAP_API_KEY = os.getenv("AMAP_API_KEY")

# 需要获取边界的城市列表（可根据需求扩展）
TARGET_CITIES = [
    {"city_name": "北京市", "province_name": "北京市"},
    {"city_name": "上海市", "province_name": "上海市"},
    {"city_name": "广州市", "province_name": "广东省"},
    {"city_name": "深圳市", "province_name": "广东省"},
    {"city_name": "杭州市", "province_name": "浙江省"}
]


def get_db_connection():
    """获取数据库连接（复用现有库）"""
    try:
        conn = mysql.connector.connect(** DB_CONFIG)
        logger.info("成功连接到现有 scenic_spots_db 数据库")
        return conn
    except Error as e:
        logger.error(f"数据库连接失败: {str(e)}")
        raise


def get_city_id(city_name, province_name):
    """从现有 cities 表中获取城市ID（复用已有数据）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 先查省份ID
        cursor.execute("SELECT id FROM provinces WHERE name = %s", (province_name,))
        province = cursor.fetchone()
        if not province:
            logger.warning(f"省份 {province_name} 不存在于现有数据库，跳过")
            return None
        province_id = province[0]
        
        # 再查城市ID
        cursor.execute(
            "SELECT id FROM cities WHERE name = %s AND province_id = %s",
            (city_name, province_id)
        )
        city = cursor.fetchone()
        if not city:
            logger.warning(f"城市 {city_name}（{province_name}）不存在于现有数据库，跳过")
            return None
        return city[0]
    finally:
        cursor.close()
        conn.close()


def fetch_city_boundary(city_name, province_name):
    """调用高德API获取城市整体边界坐标（而非行政区边界）"""
    if not AMAP_API_KEY:
        raise ValueError("未配置高德API密钥（AMAP_API_KEY）")
    
    url = "https://restapi.amap.com/v3/config/district"
    params = {
        "key": AMAP_API_KEY,
        "keywords": f"{city_name}",  # 直接搜索城市名
        "subdistrict": 0,  # 不获取下级行政区（确保返回城市整体边界）
        "extensions": "all",  # 必须为all才能返回边界
        "filter": f"province:{province_name}"  # 过滤省份，避免重名
    }
    
    try:
        logger.info(f"获取 {province_name}-{city_name} 整体边界数据...")
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") != "1":
            logger.error(f"API返回错误: {result.get('info')}")
            return None
        
        districts = result.get("districts", [])
        if not districts:
            logger.error("未找到对应城市数据")
            return None
        
        # 提取城市整体边界（而非行政区边界）
        boundary = districts[0].get("polyline")
        logger.debug(f"高德API返回的原始边界（前500字符）: {boundary[:500]}...")
        return boundary if boundary else None
    except Exception as e:
        logger.error(f"获取边界失败: {str(e)}")
        return None

def save_boundary_to_db(city_id, boundary):
    """将边界数据保存到新表 city_boundaries"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 检查是否已存在
        cursor.execute("SELECT id FROM city_boundaries WHERE city_id = %s", (city_id,))
        if cursor.fetchone():
            logger.info(f"城市ID {city_id} 的边界已存在，更新数据")
            cursor.execute(
                "UPDATE city_boundaries SET boundary = %s WHERE city_id = %s",
                (boundary, city_id)
            )
        else:
            logger.info(f"新增城市ID {city_id} 的边界数据")
            cursor.execute(
                "INSERT INTO city_boundaries (city_id, boundary) VALUES (%s, %s)",
                (city_id, boundary)
            )
        conn.commit()
    except Error as e:
        logger.error(f"保存边界数据失败: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def generate_grid_points(city_id, grid_size=0.1):
    """根据城市边界生成网格点，支持处理包含多个地块的边界数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 查询边界数据
        cursor.execute("SELECT boundary FROM city_boundaries WHERE city_id = %s", (city_id,))
        boundary_data = cursor.fetchone()
        if not boundary_data or not boundary_data[0]:
            logger.warning(f"城市ID {city_id} 无有效边界数据，无法生成网格")
            return
        
        boundary = boundary_data[0]
        logger.debug(f"城市ID {city_id} 的原始边界数据（前200字符）: {boundary[:200]}...")
        
        # 处理可能包含多个地块的边界数据（地块之间用 | 分隔）
        all_coordinates = []
        
        # 尝试按 | 分割多个地块
        land_parcels = boundary.split("|")
        for parcel in land_parcels:
            if not parcel.strip():
                continue
                
            # 每个地块内的坐标点用 ; 分隔，经纬度用 , 分隔
            points = parcel.split(";")
            for point in points:
                if not point.strip():
                    continue
                    
                try:
                    # 分割经纬度
                    lng, lat = point.split(",", 1)
                    all_coordinates.append((float(lng.strip()), float(lat.strip())))
                except (ValueError, IndexError) as e:
                    logger.warning(f"坐标解析失败: {point}，错误: {str(e)}")
        
        if not all_coordinates:
            logger.error(f"城市ID {city_id} 的边界数据无法解析为有效坐标")
            return
            
        logger.info(f"成功解析城市ID {city_id} 的边界数据，共 {len(all_coordinates)} 个坐标点")
        
        # 计算经纬度范围
        min_lng = min(coord[0] for coord in all_coordinates)
        max_lng = max(coord[0] for coord in all_coordinates)
        min_lat = min(coord[1] for coord in all_coordinates)
        max_lat = max(coord[1] for coord in all_coordinates)
        
        # 生成网格点
        grid_points = []
        lng = min_lng
        while lng <= max_lng:
            lat = min_lat
            while lat <= max_lat:
                grid_points.append((city_id, lng, lat))
                lat += grid_size
            lng += grid_size
        
        # 批量插入网格点
        cursor.execute("DELETE FROM grid_points WHERE city_id = %s", (city_id,))
        cursor.executemany(
            "INSERT INTO grid_points (city_id, lng, lat) VALUES (%s, %s, %s)",
            grid_points
        )
        conn.commit()
        logger.info(f"城市ID {city_id} 生成 {len(grid_points)} 个网格点")
        
    except Error as e:
        logger.error(f"生成网格点失败: {str(e)}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
def main():
    """主流程：获取城市ID → 拉取边界 → 保存边界 → 生成网格"""
    for city in TARGET_CITIES:
        city_name = city["city_name"]
        province_name = city["province_name"]
        
        # 1. 获取现有城市ID（复用已有数据）
        city_id = get_city_id(city_name, province_name)
        if not city_id:
            continue
        
        # 2. 拉取边界数据
        boundary = fetch_city_boundary(city_name, province_name)
        if not boundary:
            continue
        
        # 3. 保存边界到数据库
        save_boundary_to_db(city_id, boundary)
        
        # 4. 生成网格点
        generate_grid_points(city_id, grid_size=0.2)  # 可调整网格密度
        
        time.sleep(1)  # 控制API请求频率


if __name__ == "__main__":
    try:
        logger.info("===== 开始导入城市边界数据到现有数据库 =====")
        main()
        logger.info("===== 边界数据导入完成 =====")
    except Exception as e:
        logger.critical(f"程序执行失败: {str(e)}", exc_info=True)
        print(f"出错: {str(e)}（详情见 boundary_import.log）")