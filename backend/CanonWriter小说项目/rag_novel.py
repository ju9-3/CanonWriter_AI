from dotenv import load_dotenv
import os
import json
import faiss
import numpy as np

from sentence_transformers import SentenceTransformer
from langchain_openai import ChatOpenAI
from character_guard import get_character_prompt
from storage_config import get_faiss_path, get_chunks_path
 
# =====================
# 读取环境变量
# =====================

load_dotenv()

api_key = os.getenv("DASHSCOPE_API_KEY")
base_url = os.getenv("DASHSCOPE_BASE_URL")


# =====================
# 本地Embedding模型（自动检测路径）
# =====================

def _get_embedding_model():
    """获取embedding模型，支持环境变量配置或自动查找"""
    model_path = os.getenv("EMBEDDING_MODEL_PATH", "")
    
    if model_path and os.path.exists(model_path):
        return SentenceTransformer(model_path)
    
    # 自动查找常见路径
    import glob
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


embedding_model = _get_embedding_model()


# =====================
# Qwen生成模型
# =====================

llm = ChatOpenAI(
    api_key=api_key,
    base_url=base_url,
    model="qwen-turbo",
    temperature=0.6
)



def rag_answer(query):
    """问答模式：检索与问题最接近的文档片段。
    如果检索不到相关内容（相似度低于阈值），返回"无"。
    """
    try:
        faiss_path = get_faiss_path()
        chunks_path = get_chunks_path()
        
        if not os.path.exists(faiss_path) or not os.path.exists(chunks_path):
            return "无", ""

        print(f"[DEBUG] FAISS文件存在: {os.path.exists(faiss_path)}, 大小: {os.path.getsize(faiss_path)}")
        print(f"[DEBUG] Chunks文件存在: {os.path.exists(chunks_path)}")

        # 使用 deserialize 方式读取，与 upload_handler 保存方式匹配
        with open(faiss_path, "rb") as f:
            data = f.read()
            print(f"[DEBUG] FAISS数据大小: {len(data)} bytes")
        # 将 bytes 转换为 numpy 数组再传给 faiss
        data_np = np.frombuffer(data, dtype=np.uint8)
        index = faiss.deserialize_index(data_np)
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        query_vector = embedding_model.encode([query])
        print(f"[DEBUG] query_vector type: {type(query_vector)}, shape: {query_vector.shape if hasattr(query_vector, 'shape') else 'N/A'}")
        query_vector = np.array(query_vector).astype("float32")
        print(f"[DEBUG] query_vector after conversion: type={type(query_vector)}, shape={query_vector.shape}")
        print(f"[DEBUG] index type: {type(index)}, ntotal: {index.ntotal}")

        D, I = index.search(query_vector, k=3)
        print(f"[DEBUG] search results: D shape={D.shape}, I shape={I.shape}")

        # 计算相似度，过滤低于阈值的结果
        evidence_list = []
        scores = []
        context_parts = []
        SIMILARITY_THRESHOLD = 0.3

        for i, idx in enumerate(I[0]):
            if idx != -1:
                chunk = chunks[idx] if isinstance(chunks[idx], str) else chunks[idx]["text"]
                similarity = float(1 / (1 + D[0][i]))
                if similarity >= SIMILARITY_THRESHOLD:
                    context_parts.append(chunk)
                    evidence_list.append(chunk)
                    scores.append(similarity)

        if not context_parts:
            # 没有检索到相关内容
            return "无", ""

        context = "\n".join(context_parts)

        # 直接返回最相关的原文片段，不调用LLM生成
        answer = context_parts[0]
        if len(answer) > 500:
            answer = answer[:500] + "..."

        return answer, context
    except Exception as e:
        print(f"[ERROR] rag_answer failed: {e}")
        import traceback
        traceback.print_exc()
        return "无", ""


def retrieve_context(query):
    """仅检索，不调用LLM"""
    faiss_path = get_faiss_path()
    chunks_path = get_chunks_path()
    
    if not os.path.exists(faiss_path) or not os.path.exists(chunks_path):
        return "", [], []
    with open(faiss_path, "rb") as f:
        data = f.read()
    # 将 bytes 转换为 numpy 数组再传给 faiss
    data_np = np.frombuffer(data, dtype=np.uint8)
    index = faiss.deserialize_index(data_np)
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    query_vector = embedding_model.encode([query])
    query_vector = np.array(query_vector).astype("float32")
    D, I = index.search(query_vector, k=3)
    evidence_list = []
    scores = []
    context_parts = []
    for i, idx in enumerate(I[0]):
        if idx != -1:
            chunk = chunks[idx] if isinstance(chunks[idx], str) else chunks[idx]["text"]
            similarity = float(1 / (1 + D[0][i]))
            if similarity >= 0.3:  # 相关性门槛，低于0.3的过滤掉
                context_parts.append(chunk)
                evidence_list.append(chunk)
                scores.append(similarity)
    context = "\n".join(context_parts)
    return context, evidence_list, scores


def check_character_consistency(answer, context):
    """审核生成内容与Canon的一致性"""
    faiss_path = get_faiss_path()
    chunks_path = get_chunks_path()
    
    if not os.path.exists(faiss_path) or not os.path.exists(chunks_path):
        return "知识库为空，无法审核。"

    prompt = f"""
你是一名专业小说Canon审核专家。

请检查下面生成内容。

请从三个维度评分。

====================

【人物一致性】
检查：
- 性格是否符合
- 行为是否符合
- 是否违反人物设定

评分：
0-10分


====================

【世界观一致性】
检查：
- 是否符合时代背景
- 是否出现禁止元素
- 是否改变世界规则

评分：
0-10分


====================

【剧情规则一致性】
检查：
- 是否违反剧情限制
- 是否改变关键事件
- 是否创造不合理设定

评分：
0-10分


====================

【参考Canon】

{context}


【待审核内容】

{answer}


请严格按照下面格式输出：


人物一致性：
评分：__/10

问题：
无 / （具体问题）


世界观一致性：
评分：__/10

问题：
无 / （具体问题）


剧情规则一致性：
评分：__/10

问题：
无 / （具体问题）


综合评分：
__/30


审核结论：
通过 / 需要修改
"""

    result = llm.invoke(prompt)
    return result.content
from writer_agent import writer_agent
from reviewer_agent import reviewer_agent
from editor_agent import editor_agent


def generate_with_agents(query, llm):
    """Writer → Reviewer → Editor 多Agent顺序链路"""

    # 1. RAG检索
    context, evidence_list, scores = retrieve_context(query)
    print(f"[DEBUG] RAG检索完成, context长度: {len(context)}, evidences: {len(evidence_list)}")

    # 2. Writer生成初稿
    answer = writer_agent(query, context, llm)
    print(f"[DEBUG] Writer输出, answer长度: {len(answer) if answer else 0}")
    if not answer or len(answer.strip()) < 10:
        print("[DEBUG] Writer输出为空，尝试直接生成...")
        # 直接用LLM生成，不依赖RAG上下文
        answer = _direct_generate(query, llm)
        print(f"[DEBUG] 直接生成, answer长度: {len(answer) if answer else 0}")

    # 3. Reviewer审核
    review = reviewer_agent(answer, context, llm)

    # 4. 如果审核不通过 → Editor修改
    if "需要修改" in review:
        answer = editor_agent(answer, review, llm)
        print(f"[DEBUG] Editor修改后, answer长度: {len(answer) if answer else 0}")

    # 最终检查：如果answer仍为空，直接生成
    if not answer or len(answer.strip()) < 10:
        print("[DEBUG] 最终answer为空，再次直接生成...")
        answer = _direct_generate(query, llm)

    print(f"[DEBUG] 最终answer长度: {len(answer) if answer else 0}")
    return answer, context, review, evidence_list, scores


def _direct_generate(query, llm):
    """直接让LLM生成小说正文，不依赖RAG"""
    prompt = f"""你是一位专业的小说创作AI。

请根据用户需求创作一段小说正文。
要求：
1. 内容生动、有画面感
2. 人物对话自然
3. 有场景描写和心理活动
4. 字数不少于200字

用户需求：
{query}

请直接输出小说正文，不需要任何解释。"""

    try:
        result = llm.invoke(prompt)
        return result.content.strip()
    except Exception as e:
        print(f"[DEBUG] 直接生成失败: {e}")
        return ""
