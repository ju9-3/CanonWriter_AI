import json
from storage_config import get_timeline_path, get_characters_path


def get_character_prompt(character, phase=None):
    """
    根据角色和时间阶段，返回角色约束Prompt。
    
    参数：
        character: 角色名
        phase: 阶段ID（如 "phase_1"），不传则返回全部阶段
    
    返回：
        str: 角色约束提示词
    """
    try:
        with open(get_timeline_path(), "r", encoding="utf-8") as f:
            timeline_data = json.load(f)
    except:
        try:
            with open(get_characters_path(), "r", encoding="utf-8") as f:
                old_data = json.load(f)
                profile = old_data.get(character, {})
                if not profile:
                    return ""
                return f"""请严格遵守以下角色设定：

角色：
{character}

性格：
{profile.get("性格", "")}

能力：
{profile.get("能力", "")}

关系：
{profile.get("关系", "")}

生成内容不能违背以上人物设定。"""
        except:
            return ""

    if character not in timeline_data:
        return f"角色【{character}】没有找到时间线设定。"

    timeline = timeline_data[character].get("timeline", [])

    if not phase:
        # 没指定阶段 → 返回全部阶段作为参考
        parts = []
        for p in timeline:
            parts.append(f"【阶段：{p.get('名称', '未命名')}】")
            parts.append(f"性格：{p.get('性格', '')}")
            parts.append(f"行为边界：{p.get('行为边界', '')}")
            if p.get("关系"):
                rels = "；".join([f"{k}：{v}" for k, v in p.get("关系", {}).items()])
                parts.append(f"关系：{rels}")
            if p.get("禁止行为"):
                bans = "、".join(p.get("禁止行为", []))
                parts.append(f"禁止行为：{bans}")
            parts.append("")
        return "\n".join(parts)

    # 指定了阶段 → 只返回该阶段的约束
    for p in timeline:
        if p.get("id") == phase:
            prompt_parts = [
                f"【角色：{character}】",
                f"【当前阶段：{p.get('名称', '未命名')}】",
                f"关键事件：{'、'.join(p.get('关键事件', []))}",
                f"性格：{p.get('性格', '')}",
                f"行为边界：{p.get('行为边界', '')}",
            ]
            if p.get("关系"):
                rels = "；".join([f"{k}：{v}" for k, v in p.get("关系", {}).items()])
                prompt_parts.append(f"关系：{rels}")
            if p.get("禁止行为"):
                bans = "、".join(p.get("禁止行为", []))
                prompt_parts.append(f"禁止行为：{bans}")
            prompt_parts.append("\n生成内容不能违背以上人物设定。")
            return "\n".join(prompt_parts)

    return f"角色【{character}】没有找到阶段【{phase}】的设定。"