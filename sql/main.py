# main.py
import os
from dotenv import load_dotenv
from attraction_ezqa_service import AttractionQAService
from response_generator import ResponseGenerator

# 模拟大模型调用的函数，这里只是简单打印，实际使用时需要替换为真实的大模型调用
def call_large_model(prompt):
    print(f"将以下内容交给大模型处理: {prompt}")

def main():
    # 加载环境变量
    load_dotenv()

    # 读取数据库配置
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "password"),
        "database": os.getenv("DB_NAME", "tourism")
    }

    # 初始化景点问答服务
    qa_service = AttractionQAService(db_config)

    print("景点智能问答系统已启动，输入q退出")
    try:
        while True:
            user_input = input("您的问题：")
            if user_input.lower() == 'q':
                break
            answer = qa_service.get_answer(user_input)#从该函数中获得经由数据库查询系统的答案，根据是否可以解答，返回结果，并交给大模型按不同方式处理。

            if answer == ResponseGenerator.UNABLE_TO_ANSWER:
                # 无法解析的问题，直接将原问题交给大模型处理
                print("已经交由大模型处理")
                call_large_model(user_input)
            else:
                # 可以解析的问题，将结果转换成提示词模式交给大模型处理
                prompt = f"用户问题：{user_input}，系统已有部分信息：{answer}，请进一步完善回答。"
                call_large_model(prompt)
    finally:
        # 确保数据库连接被关闭
        qa_service.close()

if __name__ == "__main__":
    main()