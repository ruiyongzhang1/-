#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地知识库搜索函数

专注于本地向量库检索，返回格式化的搜索结果
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# 导入本地向量库初始化
from agent.RAG.knowledge_base import init_vectorstore

@dataclass
class SearchResult:
    """搜索结果数据结构"""
    source: str  # "knowledge_base"
    title: str
    content: str
    score: Optional[float] = None
    metadata: Optional[Dict] = None

def search_local_knowledge(query: str, top_k: int = 5, score_threshold: float = 0.0) -> List[SearchResult]:
    """
    本地知识库搜索函数
    
    Args:
        query: 搜索查询
        top_k: 返回结果数量
        score_threshold: 相似度阈值（0.0-1.0，越小越严格）
    
    Returns:
        搜索结果列表
    """
    # 初始化向量库
    vectorstore = init_vectorstore()
    
    if not vectorstore:
        print("❌ 向量库未初始化")
        return []
    
    try:
        # 使用相似度搜索
        docs_with_scores = vectorstore.similarity_search_with_score(
            query, 
            k=top_k
        )
        
        results = []
        for doc, score in docs_with_scores:
            # 过滤低相似度结果
            if score <= score_threshold:
                continue
                
            # 提取文件名
            source_path = doc.metadata.get('source', 'Unknown')
            filename = os.path.basename(source_path) if source_path else 'Unknown'
            
            result = SearchResult(
                source="knowledge_base",
                title=f"📚 {filename}",
                content=doc.page_content,
                score=score,
                metadata=doc.metadata
            )
            results.append(result)
        
        print(f"✔ 找到 {len(results)} 个相关文档")
        return results
        
    except Exception as e:
        print(f"❌ 知识库检索失败: {e}")
        return []

def format_search_results(results: List[SearchResult]) -> str:
    """
    将搜索结果格式化为可读字符串
    
    Args:
        results: 搜索结果列表
    
    Returns:
        格式化的字符串
    """
    if not results:
        return "没有找到相关信息。"
    
    formatted_parts = []
    for i, result in enumerate(results, 1):
        part = f"文档 {i}: {result.title}\n"
        part += f"相似度: {result.score:.3f}\n" if result.score else ""
        part += f"内容: {result.content}\n"
        formatted_parts.append(part)
    
    return "\n" + "="*50 + "\n".join(formatted_parts)

def get_context_for_llm(results: List[SearchResult]) -> str:
    """
    为LLM生成上下文
    
    Args:
        results: 搜索结果列表
    
    Returns:
        LLM可用的上下文字符串
    """
    if not results:
        return "没有找到相关的本地文档信息。"
    
    context_parts = []
    for i, result in enumerate(results, 1):
        context_parts.append(f"参考文档 {i}:\n{result.content}")
    
    return "\n\n".join(context_parts)

def rag_search(query: str, top_k: int = 3) -> Dict[str, Any]:
    """
    RAG搜索接口 - 供tool调用
    
    Args:
        query: 搜索查询
        top_k: 返回结果数量
    
    Returns:
        包含搜索结果和格式化上下文的字典
    """
    # print(f"🔍 RAG搜索: {query}")
    
    # 搜索本地知识库
    results = search_local_knowledge(query, top_k=top_k)
    
    # 生成上下文
    context = get_context_for_llm(results)
    
    return {
        "query": query,
        "results": results,
        "context": context,
        "count": len(results)
    }