def editor_agent(answer, review, llm, instruction=None):
    """Editor Agent: 根据审核意见或用户修改意见修改小说正文。"""

    if instruction:
        prompt = f"""
你是小说编辑Agent。请根据作者的修改意见，重新修改小说正文。

原文：

{answer}


修改意见：

{instruction}


要求：
1. 严格按照修改意见进行修改
2. 保持原文的风格和叙事节奏
3. 只输出修改后的完整正文，不需要解释
4. 如果修改意见涉及剧情走向，请在保持人物设定一致的前提下调整

输出修改后的小说。
"""
    else:
        prompt = f"""
你是小说编辑Agent。


原文：

{answer}


审核意见：

{review}


请根据意见修改。
要求：
1. 如果审核说"无问题"，直接返回原文
2. 如果有具体问题，针对性修改
3. 保持原文的风格和节奏
4. 直接输出修改后的小说正文，不需要解释

输出修改后的小说。
"""

    try:
        result = llm.invoke(prompt)
        content = result.content.strip()
        if not content:
            print("[Editor] LLM返回空内容，保留原文")
            return answer
        return content
    except Exception as e:
        print(f"[Editor] LLM调用失败: {e}，保留原文")
        return answer
