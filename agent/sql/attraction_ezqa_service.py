import os
from dotenv import load_dotenv
from agent.sql.question_processor import QuestionProcessor
from agent.sql.database import DatabaseManager
from agent.sql.response_generator import ResponseGenerator


load_dotenv()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER")
DB_AUTH_PLUGIN = os.getenv("DB_AUTH_PLUGIN", "auth_plugin")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DATABASE = os.getenv("DB_NAME", "tourism")

def myanswer(user_question: str) -> str:
    # 配置数据库连接信息
    host = DB_HOST
    user = DB_USER
    password = DB_PASSWORD
    auth_plugin = DB_AUTH_PLUGIN
    database = DB_DATABASE

    # 初始化核心组件
    db_manager = DatabaseManager(host, user, password, auth_plugin, database)
    question_processor = QuestionProcessor(db_manager)
    response_generator = ResponseGenerator()
    # 处理用户问题
    processed_questions = question_processor.process(user_question)
    
    # 执行数据库查询
    db_results = db_manager.query(processed_questions)
        
    # 生成响应
    response = response_generator.generate(processed_questions, db_results)
    
    return response