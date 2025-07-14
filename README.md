
"""
RAG 知识库系统调用说明
"""

# 导入两个模块
from retriever import init_vectorstore          # 向量库初始化
from retriever import rag_search         # 知识库搜索

# 1. 
result = rag_search("用户提问", top_k=3)
query = "澳门的最佳旅游时间"

# RAG搜索
vs=init_vectorstore()  #该函数用于建立向量库，成功返回vs对象,失败返回None
rag_result = rag_search(query, top_k=3) #从向量库中找到与查询最相似的前top_k个文档块


# LLM调用
if rag_result['count'] > 0:
    message = HumanMessage(content=f"问题：{query}\n参考信息：{rag_result['context']}")
    response = llm.invoke([message])
    print(f"LLM回答: {response.content}")
else:
    print("没有找到相关信息")

# ============================================================================
# 配置好环境，运行tes1.py。
# ============================================================================
# 需要的环境变量配置 (.env文件)
# ============================================================================
  
# DOC_DIR=./pdf  （110个pdf的位置）
# VECTOR_DIR=./vector_db/knowledge.demo      （词向量库建立成功后，存在的的文件位置）
# COLLECTION_NAME=travel_information          （向量库集合名）
# EMBED_MODEL=text-embedding-ada-002            （模型名称）
    
    
