import json
import random
from storage_config import get_trajectory_path


def load_trajectories():
    """加载情绪轨迹模板"""
    try:
        with open(get_trajectory_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def get_trajectory_keys():
    """获取所有轨迹名称列表"""
    data = load_trajectories()
    return list(data.keys())


def build_emotion_prompt(trajectory_name, character, user_request):
    """
    根据情绪轨迹模板 + 用户需求，构建结构化写作Prompt。
    
    返回 dict: {"emotion_context": 情绪结构文本, "writing_focus": 写作重心}
    以及合成后的完整 prompt_str
    """
    data = load_trajectories()
    template = data.get(trajectory_name)
    if not template:
        return {"error": f"找不到轨迹：{trajectory_name}"}

    # 随机选取各阶段的具体关键词（增加多样性）
    start = random.choice(template.get("情绪起点", ["待定"]))
    trigger = random.choice(template.get("转折触发", ["待定"]))
    moment = random.choice(template.get("关系瞬间", ["待定"]))
    landing = random.choice(template.get("情绪落点", ["待定"]))
    focus = template.get("写作重心", "心理描写 > 对话 > 动作描写")

    # 构建情绪结构文本
    emotion_context = f"""
【情绪轨迹】
情绪起点：{start}
转折触发：{trigger}
关系瞬间：{moment}
情绪落点：{landing}
"""

    # 合成最终 Prompt
    prompt = f"""
你正在创作一段小说片段。

请严格遵守以下情绪轨迹结构，不要平均铺开剧情。

{emotion_context}

【写作重心】
按以下优先级分配笔墨：
{focus}

【角色与设定】
角色：{character}
用户需求：{user_request}

要求：
1. 按 起点→转折→瞬间→落点 的顺序推进
2. 避免大段心理解释，用动作、对话、细节来体现情绪
3. 让"关系瞬间"成为片段的高密度情绪点
4. 不要写成"故事概要"，要写有现场感的正文
"""

    return {
        "emotion_context": emotion_context.strip(),
        "writing_focus": focus,
        "prompt": prompt.strip()
    }