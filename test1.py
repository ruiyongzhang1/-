#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm.py - 测试RAG系统的LLM调用

测试 retriever.py 和 knowledge_base.py 的集成使用
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from retriever import init_vectorstore          # 向量库初始化
from retriever import rag_search


load_dotenv(override=True)

# 初始化LLM
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.1,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    openai_api_base=os.getenv("OPENAI_API_BASE")
)

# 测试问题
query = "澳门的最佳旅游时间"
vs=init_vectorstore()
# RAG搜索
rag_result = rag_search(query, top_k=3)


# LLM调用
if rag_result['count'] > 0:
    message = HumanMessage(content=f"问题：{query}\n参考信息：{rag_result['context']}")
    response = llm.invoke([message])
    print(f"LLM回答: {response.content}")
else:
    print("没有找到相关信息")