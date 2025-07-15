import os
from dotenv import load_dotenv
from question_processor import QuestionProcessor
from database import DatabaseManager
from response_generator import ResponseGenerator

load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def main():
    # 配置数据库连接信息
    host = 'localhost'
    user = DB_USER
    password = DB_PASSWORD
    database = 'scenic_spots_db'

    # 初始化核心组件
    db_manager = DatabaseManager(host, user, password, database)
    question_processor = QuestionProcessor(db_manager)
    response_generator = ResponseGenerator()

    while True:
        # 获取用户输入
        user_question = input("请输入你的问题（输入 'exit' 退出）：")
        if user_question.lower() == 'exit':
            break

        # 处理用户问题
        processed_questions = question_processor.process(user_question)
        
        # 执行数据库查询
        db_results = db_manager.query(processed_questions)
        
        # 生成响应
        response = response_generator.generate(processed_questions, db_results)

        # 输出结果
        print(response)


if __name__ == "__main__":
    main()