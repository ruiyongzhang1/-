环境相关：
pip install python-dotenv
pip install mysql-connector-python
pip install jieba
pip install requests
pip install pymysql

代码使用：
核心功能已在main里演示，基本无需关注其他代码，环境，数据库，等配置完后，直接运行main就能跑通
一些范例问题：附近查询：白云观附近的景点，多属性查询：法海寺的评分，位置，联系方式，门票，营业时间，复合查询：北京有哪些评分不低于4.5，价格低于20元的景点。无效输入：按计划发卡行金葵花卡黄金卡很久，帮我做下旅行规划。


spot_dict的生成位置需要注意！！！！！！！！！！！！！！！！！！！！！！！！！

数据库相关：
需要安装mysql，workbench等工具
需要导入的数据库相关信息在mysql文件夹里。
相关配置文件在.env里
目前只包含北京的1300多条景点数据

有事微信群里问我