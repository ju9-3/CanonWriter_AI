import json
import re
from collections import Counter
from storage_config import get_chunks_path, get_characters_path


def build_character_profile():
    """从 user_chunks.json 中提取角色信息。
    只使用 LLM 智能提取，确保结果质量。
    """
    chunks_path = get_chunks_path()
    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    except Exception:
        return {}

    text = "\n".join(chunks)

    # 策略1：匹配结构化标记
    characters = {}
    pattern_structured = r"(角色|人物|主角|配角|主要人物|角色介绍)[：:]\s*([^\n]+)"
    result = re.findall(pattern_structured, text)
    for item in result:
        name = item[1].strip()
        for n in re.split(r"[，,、/]", name):
            n = n.strip().strip("。.")
            if n and len(n) >= 2 and _is_valid_name(n):
                characters[n] = {"性格": "", "能力": "", "关系": ""}

    # 策略2：用 LLM 智能提取
    if len(characters) < 2:
        llm_chars = _extract_with_llm(text)
        for name, info in llm_chars.items():
            if name not in characters and _is_valid_name(name):
                characters[name] = info

    # 限制最多8个角色
    character_names = list(characters.keys())[:8]
    characters = {k: characters[k] for k in character_names}

    _save_characters(characters)
    return characters


def _is_valid_name(name):
    """严格验证是否为人名。"""
    # 必须是 2-3 个中文字符（大多数中文人名）
    if not re.match(r"^[\u4e00-\u9fa5]{2,3}$", name):
        return False

    # 排除常见动词短语
    bad_endings = ["的", "了", "着", "过", "吗", "呢", "啊", "吧", "呀"]
    for ending in bad_endings:
        if name.endswith(ending):
            return False

    # 排除常见称谓/职业/自然现象
    bad_words = {
        "少爷", "小姐", "公子", "姑娘", "丫鬟", "小厮",
        "师父", "徒弟", "师兄", "师姐", "师弟", "师妹",
        "父亲", "母亲", "娘亲", "爹", "娘", "爷爷", "奶奶",
        "哥哥", "姐姐", "弟弟", "妹妹", "叔叔", "阿姨",
        "将军", "宰相", "皇帝", "皇后", "太子", "公主",
        "长老", "方丈", "和尚", "道士", "尼姑",
        "老板", "掌柜", "伙计", "客人",
        "医生", "护士", "老师", "学生", "同学",
        "农夫", "猎户", "渔夫", "樵夫",
        "路人", "旁人", "来人", "去者", "众人",
        "微风", "冷风", "寒风", "春风", "狂风",
        "月色", "星光", "晨光", "暮色", "朝阳",
        "声音", "话语", "呼吸", "脚步", "心跳",
        "目光", "视线", "表情", "神色", "神情",
        "身影", "背影", "侧脸", "面容", "脸庞",
        "小镇", "村落", "城池", "宫殿", "楼阁",
        "树林", "山谷", "河畔", "山巅", "溪流",
        "夜色", "白昼", "清晨", "黄昏", "黎明",
        "心中", "脑海", "眼前", "耳边", "心底",
        "嘴角", "眼底", "眉间", "发间", "指间",
        "自己", "别人", "大家", "几人", "此人", "那人",
        "少年", "少女", "青年", "老人", "小孩", "孩子",
        "男人", "女人", "男子", "女子",
        "我", "你", "他", "她", "它", "我们", "你们", "他们",
        "什么人", "谁", "哪位", "任何人",
        "对方", "另一方", "主人公", "主角", "守光人",
        "微微", "轻轻", "缓缓", "渐渐", "慢慢", "急急",
    }
    if name in bad_words:
        return False

    return True


def _extract_with_llm(text):
    """使用 LLM 从小说文本中提取角色。"""
    try:
        from rag_novel import llm

        # 截取前 4000 字作为上下文
        sample = text[:4000]

        prompt = f"""你是一位专业的小说人物分析师。请从以下小说文本中识别所有出场角色的真实人名。

严格要求：
1. 只提取真实的人名（2-3个中文字符），例如"林墨白"、"苏晚"、"萧炎"
2. 绝对不要提取：称谓（少爷、小姐、师父）、短语（微微的哭、朝着微弱）、自然现象（微风、月色）
3. 人名必须是 2-3 个汉字，且在文本中作为角色被称呼
4. 最多提取 8 个角色，每个角色给出简短性格描述
5. 只输出 JSON，格式：{{"角色名": {{"性格": "描述"}}}}

小说文本：
{sample}"""

        response = llm.invoke(prompt)
        content = response.content.strip()

        # 清理 markdown 标记
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        # 尝试解析 JSON
        result = json.loads(content)
        if not isinstance(result, dict):
            return {}

        # 过滤并验证
        filtered = {}
        for name, info in result.items():
            if _is_valid_name(name):
                filtered[name] = info if isinstance(info, dict) else {"性格": str(info)}

        return filtered
    except Exception as e:
        print(f"[LLM] 角色提取失败: {e}")
        return {}


def _save_characters(characters):
    """保存角色数据。"""
    with open(get_characters_path(), "w", encoding="utf-8") as f:
        json.dump(characters, f, ensure_ascii=False, indent=4)
