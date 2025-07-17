from agent.sql.attraction_ezqa_service import myanswer

user_message = input("请输入您的问题: ")
answer = myanswer(user_message)
if answer == '':
    print(f"🔍 [SQL查询] 未找到相关信息。")
else:
    print(f"🔍 [SQL查询] 找到相关信息:", answer)