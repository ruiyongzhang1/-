import os
from turtle import rt
from dotenv import load_dotenv
from agent.sql.database import DatabaseManager
from agent.sql.question_processor import QuestionProcessor
from agent.sql.response_generator import ResponseGenerator


from agent.sql.database import DatabaseManager
from agent.sql.question_processor import QuestionProcessor
from agent.sql.response_generator import ResponseGenerator

class AttractionQAService:
    def __init__(self, db_config):
        """初始化景点问答服务"""
        self.db_manager = DatabaseManager(**db_config)
        self.question_processor = QuestionProcessor(self.db_manager)
        self.response_generator = ResponseGenerator()

    def get_answer(self, user_question):
        """处理用户问题并返回回答"""
        processed_question = self.question_processor.process(user_question)
        db_results = self.db_manager.query(processed_question)
        return self.response_generator.generate(processed_question, db_results)

    def close(self):
        """关闭数据库连接"""
        self.db_manager.close()

# 加载环境变量
load_dotenv()

# 读取数据库配置
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_DATABASE = os.getenv("DB_NAME", "tourism")

qa_service = AttractionQAService({
    "host": DB_HOST,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_DATABASE
})

def test_spot_extraction():
    # 使用环境变量配置初始化数据库管理器
    db_manager = DatabaseManager(DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE)
    processor = QuestionProcessor(db_manager)
    # 测试用例（覆盖简单、复杂、模糊场景）
    test_cases = [
        ("紫竹院公园的评分是多少？", "紫竹院公园"),
        ("从天安门到故宫怎么坐地铁？", "天安门"),  # 优先提取前一个景点
        ("北京环球度假区附近有什么酒店？", "北京环球度假区"),
        ("请问上海迪士尼乐园的门票价格？", "上海迪士尼乐园"),
        ("想知道成都宽窄巷子的开放时间", "宽窄巷子"),
        ("推荐几个像颐和园这样的景点", "颐和园"),
        ("八达岭长城和慕田峪长城哪个好？", "八达岭长城"),  # 按词典顺序取第一个
        ("这附近有类似圆明园遗址公园的公园吗？", "圆明园"),
        ("这附近有类似白云观的公园吗？", "白云观")
    ]
    
    '''print("提取效果测试：")
    for question, expected in test_cases:
        result = processor._extract_spot_name(question)
        status = "✓" if result == expected else "✗"
        print(f"问题：{question}\n预期：{expected}\n实际：{result} {status}\n")'''

def main():
    # 使用相同的配置初始化数据库管理器
    db_manager = DatabaseManager(DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE)
    response_generator = ResponseGenerator()
    question_processor = QuestionProcessor(db_manager)  # 注入数据库管理器
    
    print("景点智能问答系统已启动，输入q退出")
    while True:
        user_input = input("您的问题：")
        if user_input.lower() == 'q':
            break
        # 处理问题→查询数据库→生成回答
        processed_question = question_processor.process(user_input)
        db_results = db_manager.query(processed_question)
        response = response_generator.generate(processed_question, db_results)
        print(response)

if __name__ == "__main__":
    test_spot_extraction()
    main()