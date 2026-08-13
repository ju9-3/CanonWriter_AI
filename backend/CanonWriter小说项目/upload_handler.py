import os
import json
import faiss
import numpy as np
from io import BytesIO               
from docx import Document            

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

from character_builder import build_character_profile
from storage_config import get_faiss_path, get_chunks_path

load_dotenv()


# 加载embedding模型（自动检测路径）
def _get_embedding_model():
    """获取embedding模型，支持环境变量配置或自动查找"""
    model_path = os.getenv("EMBEDDING_MODEL_PATH", "")
    
    if model_path and os.path.exists(model_path):
        return SentenceTransformer(model_path)
    
    # 自动查找常见路径
    search_paths = [
        os.path.expanduser("~/.cache/modelscope/models/AI-ModelScope--bge-small-zh-v1.5/snapshots/master"),
        os.path.expanduser("~/.cache/modelscope/hub/AI-ModelScope/bge-small-zh-v1.5"),
    ]
    
    for path in search_paths:
        if os.path.exists(path):
            print(f"[Embedding] 找到模型: {path}")
            return SentenceTransformer(path)
    
    # 默认从 modelscope 下载
    print("[Embedding] 未找到本地模型，正在下载 bge-small-zh-v1.5...")
    try:
        from modelscope import snapshot_download
        model_dir = snapshot_download('AI-ModelScope/bge-small-zh-v1.5')
        print(f"[Embedding] 模型下载完成: {model_dir}")
        return SentenceTransformer(model_dir)
    except ImportError:
        print("[Embedding] modelscope 未安装，尝试直接使用 sentence-transformers 加载...")
        return SentenceTransformer('BAAI/bge-small-zh-v1.5')


model = _get_embedding_model()



def build_user_knowledge(files):

    # =====================
    # 逐个文件独立切块
    # =====================

    all_chunks = []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50
    )

    for file in files:
        try:
            if file.name.lower().endswith('.docx'):     # 处理 docx
                content = file.read()
                # 检查是否为有效的 docx 文件（docx 本质是 zip）
                if content[:4] == b'PK\x03\x04':
                    doc = Document(BytesIO(content))
                    text = "\n".join(p.text for p in doc.paragraphs)
                else:
                    # 可能是 .doc 格式（旧版），跳过
                    print(f"[WARN] 文件 {file.name} 不是有效的 docx 格式，跳过")
                    continue
            else:                                       # 处理 txt
                raw = file.read()
                # 尝试多种编码
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        text = raw.decode("gbk")
                    except UnicodeDecodeError:
                        try:
                            text = raw.decode("gb18030")
                        except UnicodeDecodeError:
                            text = raw.decode("latin-1", errors="ignore")
                if not text.strip():
                    print(f"[WARN] 文件 {file.name} 内容为空，跳过")
                    continue
            file_chunks = splitter.split_text(text)
            all_chunks.extend(file_chunks)
        except Exception as e:
            print(f"[WARN] 处理文件 {file.name} 时出错: {e}，跳过")
            continue

    chunks = all_chunks

    # =====================
    # 构建FAISS索引
    # =====================



    # =====================
    # 向量化
    # =====================

    embeddings = model.encode(
        chunks
    )


    embeddings = np.array(
        embeddings
    ).astype(
        "float32"
    )


    # =====================
    # 创建FAISS
    # =====================

    dimension = embeddings.shape[1]


    index = faiss.IndexFlatL2(
        dimension
    )


    index.add(
        embeddings
    )


    # =====================
    # 保存
    # =====================

    faiss_path = get_faiss_path()
    print(f"[DEBUG] FAISS保存路径: {faiss_path}")
    
    # 使用 serialize 方式保存，避免 Windows 下文件名解析问题
    serialized = faiss.serialize_index(index)
    with open(faiss_path, "wb") as f:
        f.write(serialized)


    with open(
        get_chunks_path(),
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            chunks,
            f,
            ensure_ascii=False
        )

    build_character_profile()


    return len(chunks)
