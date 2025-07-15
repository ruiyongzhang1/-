import mysql.connector
from mysql.connector import Error

def test_mysql_connection(host, user, password, database=None):
    """
    测试 MySQL 数据库连接
    参数:
        host: 数据库地址
        user: 用户名
        password: 密码
        database: 可选数据库名
    """
    try:
        # 建立连接
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            auth_plugin='mysql_native_password'
        )
        
        if connection.is_connected():
            print("✅ 数据库连接成功！")
            
            # 获取服务器信息
            db_info = connection.get_server_info()
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            
            print(f"▪ MySQL服务器版本: {version}")
            print(f"▪ 连接协议版本: {db_info}")
            
            # 显示当前数据库
            if database:
                cursor.execute("SELECT DATABASE()")
                print(f"▪ 当前数据库: {cursor.fetchone()[0]}")
            
            # 显示前5个表（如果有数据库）
            try:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                if tables:
                    print("▪ 数据库表:", ', '.join(table[0] for table in tables[:5]))
            except:
                pass
            
    except Error as e:
        print(f"❌ 连接失败: {e}")
    finally:
        # 确保连接关闭
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("▪ 连接已关闭")

# 使用示例
if __name__ == "__main__":
    # 配置信息（建议从环境变量获取）
    config = {
        'host': 'localhost',
        'user': 'root',
        'password': '123456',
        'database': 'scenic_spots_db'  # 可选
        'auth_plugin'='mysql_native_password'
    }
    
    print("正在测试数据库连接...")
    test_mysql_connection(**config)