def writer_agent(user_request, context, llm):
    """Writer Agent: 根据Canon资料生成小说正文初稿。"""

    prompt = f"""
你是小说Writer Agent。

根据Canon资料生成剧情。

Canon:
{context}


用户需求:
{user_request}


要求：
1.符合人物设定
2.符合世界观
3.不要创造冲突设定
4.直接输出小说正文，不需要任何解释或前言

输出小说正文。
"""

    try:
        result = llm.invoke(prompt)
        content = result.content.strip()
        if not content:
            print("[Writer] LLM返回空内容，使用备用方案")
            content = _fallback_generate(user_request, llm)
        return content
    except Exception as e:
        print(f"[Writer] LLM调用失败: {e}")
        return _fallback_generate(user_request, llm)


def _fallback_generate(user_request, llm):
    """备用生成方案：不依赖RAG上下文，直接生成。"""
    prompt = f"""你是一位专业的小说创作AI。

请根据用户需求创作一段生动的小说正文。
要求：
- 内容有画面感，场景描写细腻
- 人物对话自然
- 有心理活动和情感表达
- 字数不少于200字
- 直接输出正文，不需要任何解释

用户需求：
{user_request}

小说正文："""

    try:
        result = llm.invoke(prompt)
        return result.content.strip()
    except Exception as e2:
        print(f"[Writer] 备用方案也失败了: {e2}")
        return f"（生成失败：{str(e2)}）"


if __name__ == "__main__":
    """独立测试入口：直接运行此文件可测试 writer_agent"""
    from dotenv import load_dotenv
    load_dotenv()
    import os
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "")
    
    if not api_key:
        print("错误：未配置 DASHSCOPE_API_KEY")
        exit(1)

    llm = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model="qwen-turbo",
        temperature=0.6
    )

    # 测试参数
    test_request = "写一段林黛玉和贾宝玉因为误会产生矛盾后的对话场景"
    test_context = """【人物设定】
林黛玉：敏感多疑，才情出众，说话尖刻但心地善良
贾宝玉：温润如玉，多情善感，对林黛玉格外用心

【世界观】
贾府，大观园，封建大家庭背景
"""

    print("=" * 50)
    print("测试 writer_agent")
    print(f"用户需求: {test_request}")
    print("=" * 50)

    result = writer_agent(test_request, test_context, llm)
    
    print("\n生成结果:")
    print("-" * 50)
    print(result)
    print("-" * 50)
    print(f"\n字数: {len(result)}")
