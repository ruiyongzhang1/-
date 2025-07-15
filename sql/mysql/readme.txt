如果你需要迁移或备份项目数据，只需关注自己创建的数据库（如示例中的 your_database），包含 users、conversations、messages 等表。具体步骤如下：

使用 MySQL Workbench 导出自己的数据库：
打开 Workbench → 连接到 MySQL → 选择 Server > Data Export。
在 Export Schemas 中，只勾选你自己的数据库名（如 your_database），不要勾选 sys、information_schema 等系统数据库。
配置导出选项，点击 Start Export。
导入到新环境：
在新的 MySQL 实例中，先创建同名数据库（此处应为scenic.spots.db）。
使用 Workbench 的 Data Import 功能，选择之前导出的 SQL 文件，导入到新数据库。