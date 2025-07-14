#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
retriever.py  —  目录下 TXT / PDF 向量库初始化脚本

仅负责：
  1. 读取目录下所有 .txt/.pdf 文件
  2. 切块并生成嵌入
  3. 持久化到 Chroma 向量库
  4. 更新资料，请删除chroma.sqlite3

不包含 LLM 调用或问答功能。
由 RAG 上层逻辑调用。
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader, PyPDFLoader, UnstructuredPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# 加载环境变量
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# 基本配置 - 从环境变量读取
DOC_DIR = Path(os.getenv("DOC_DIR"))          # 文档目录
VECTOR_DIR = Path(os.getenv("VECTOR_DIR"))    # 向量库存放目录
COLLECTION = os.getenv("COLLECTION_NAME")     # 向量集合名称
EMBED_MODEL = os.getenv("EMBED_MODEL")        # 嵌入模型

api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

# 嵌入与切块配置
embeddings = OpenAIEmbeddings(
    model=EMBED_MODEL,
    openai_api_key=api_key,
    openai_api_base=api_base,
)
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=150,
    separators=["\n\n", "\n", "。", ".", "!", "?", " "],
)

def load_docs_from_path(path: Path):
    """
    单文件加载并切分，支持 .txt 和 .pdf（含扫描版）。
    返回 List[Document]
    """
    ext = path.suffix.lower()
    if ext == ".txt":
        loader = TextLoader(str(path), encoding="utf-8")
    elif ext == ".pdf":
        try:
            loader = PyPDFLoader(str(path))
        except Exception:
            loader = UnstructuredPDFLoader(str(path), mode="elements")
    else:
        return []
    return splitter.split_documents(loader.load())

def load_all_docs(dir_path: Path):
    """
    遍历目录下所有 .txt/.pdf 文件并切分，返回所有文档块。
    """
    docs = []
    for file in dir_path.iterdir():
        if file.is_file() and file.suffix.lower() in {".txt", ".pdf"}:
            docs.extend(load_docs_from_path(file))
    return docs


def init_vectorstore():
    """
    初始化向量库：
    - 如果向量库不存在，创建新的向量库
    - 如果向量库已存在，直接返回现有实例
     
    如果需要重建，请先删除 VECTOR_DIR 目录
    """
    # 如果向量库已存在，直接返回
    if VECTOR_DIR.exists() and any(VECTOR_DIR.iterdir()):
        print(f"✔ 向量库已存在，直接加载")
        vs = Chroma(
            embedding_function=embeddings,
            persist_directory=str(VECTOR_DIR),
            collection_name=COLLECTION,
        )
        print(f"✔ 向量库加载完成，共 {vs._collection.count()} chunks")
        return vs
     
    # 创建新的向量库
    print("🔄 开始构建向量库...")
    docs = load_all_docs(DOC_DIR)
     
    if not docs:
        print("❌ 没有找到任何文档")
        return None
    
    print(f"📚 总共需要处理 {len(docs)} 个文档块")
    
    # 分批处理，避免单次请求token过多
    batch_size = 100  # 每批100个文档块，可根据实际情况调整
    vs = None
    
    try:
        for i in range(0, len(docs), batch_size):
            batch_docs = docs[i:i+batch_size]
            current_batch = i // batch_size + 1
            total_batches = (len(docs) + batch_size - 1) // batch_size
            
            print(f"📦 处理第 {current_batch}/{total_batches} 批，共 {len(batch_docs)} 个文档块")
            
            if vs is None:
                # 第一批：创建向量库
                vs = Chroma.from_documents(
                    batch_docs,
                    embeddings,
                    persist_directory=str(VECTOR_DIR),
                    collection_name=COLLECTION,
                )
                print(f"✅ 第1批处理完成，已创建向量库")
            else:
                # 后续批次：添加到现有向量库
                vs.add_documents(batch_docs)
                print(f"✅ 第{current_batch}批处理完成")
            
            # 每批处理后都保存
            vs.persist()
        
        final_count = vs._collection.count()
        print(f"🎉 向量库构建完成！")
        print(f"📊 总文档块数: {final_count}")
        print(f"📊 处理批次数: {total_batches}")
        return vs
        
    except Exception as e:
        print(f"❌ 向量库构建失败: {e}")
        # 如果构建失败，清理可能的残留文件
        if VECTOR_DIR.exists():
            import shutil
            try:
                shutil.rmtree(VECTOR_DIR)
                print("🧹 已清理失败的向量库文件")
            except:
                pass
        return None
    """
    初始化向量库：
    - 如果向量库不存在，创建新的向量库
    - 如果向量库已存在，直接返回现有实例
    
    如果需要重建，请先删除 VECTOR_DIR 目录
    """
    # 如果向量库已存在，直接返回
    if VECTOR_DIR.exists() and any(VECTOR_DIR.iterdir()):
        print(f" 向量库已存在，直接加载")
        vs = Chroma(
            embedding_function=embeddings,
            persist_directory=str(VECTOR_DIR),
            collection_name=COLLECTION,
        )
        print(f"✔ 向量库加载完成，共 {vs._collection.count()} chunks")
        return vs
    
    # 创建新的向量库
    print("开始构建向量库...")
    docs = load_all_docs(DOC_DIR)
    
    if not docs:
        print("没有找到任何文档")
        return None
    
    vs = Chroma.from_documents(
        docs,
        embeddings,
        persist_directory=str(VECTOR_DIR),
        collection_name=COLLECTION,
    )
    vs.persist()
    print(f"✔ 向量库构建完成，共 {len(docs)} chunks")
    return vs