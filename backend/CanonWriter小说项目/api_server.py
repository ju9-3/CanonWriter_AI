"""
CanonWriter API 网关
=====================
复用 FanForge_AI 已有的 RAG / Agent / 情感曲线 / 上传逻辑，
包装成 REST 接口供前端 (canonwriter-front) 调用。

启动方式（必须在 FanForge_AI小说项目 目录下运行，以保证相对路径生效）：
    pip install fastapi "uvicorn[standard]" python-multipart
    python -m uvicorn api_server:app --reload --port 8000

启动后：
    接口文档: http://localhost:8000/docs
    健康检查: http://localhost:8000/api/health
"""
import os
import json
import random
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from storage_config import (
    get_faiss_path, get_chunks_path, get_files_path,
    get_characters_path, get_timeline_path
)

# ====== 延迟导入重型模块 ======
# faiss / sentence_transformers 等重型库可能未安装，
# 改成使用时才导入，确保服务器能先启动
HAS_RAG = False
_generate_with_agents = None
_rag_answer = None
_llm = None
_build_user_knowledge = None
_get_trajectory_keys = None
_load_trajectories = None
_editor_agent = None

def _ensure_rag():
    global HAS_RAG, _generate_with_agents, _rag_answer, _llm
    global _build_user_knowledge, _get_trajectory_keys, _load_trajectories
    global _editor_agent
    if HAS_RAG:
        return
    try:
        from rag_novel import generate_with_agents, rag_answer, llm
        from upload_handler import build_user_knowledge
        from emotional_trajectory import get_trajectory_keys, load_trajectories
        from editor_agent import editor_agent
        _generate_with_agents = generate_with_agents
        _rag_answer = rag_answer
        _llm = llm
        _build_user_knowledge = build_user_knowledge
        _get_trajectory_keys = get_trajectory_keys
        _load_trajectories = load_trajectories
        _editor_agent = editor_agent
        HAS_RAG = True
        print("[RAG] 重型模块加载成功")
    except ImportError as e:
        print(f"[RAG] 重型模块加载失败: {e}")
        print("[RAG] 将使用模拟数据模式")
        HAS_RAG = False

app = FastAPI(title="CanonWriter API 网关", version="1.0.0")

# ====== CORS：允许前端跨域 ======
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ====== 请求 / 响应模型 ======
class GenerateRequest(BaseModel):
    query: str
    mode: str = "create"


class EmotionPlanRequest(BaseModel):
    trajectory: str
    character: str = ""
    user_request: str = ""


# ====== 工具类 ======
class _FileLike:
    def __init__(self, filename: str, content: bytes):
        self.name = filename
        self._content = content

    def read(self) -> bytes:
        return self._content


# ====== 模拟数据 ======
def _mock_generate(query, mode):
    """没有 RAG 时的模拟生成"""
    return {
        "answer": f"（演示模式）根据你的需求「{query}」，AI 正在创作一段精彩的小说正文...\n\n"
                  f"这里是一个示例段落：\n\n"
                  f"月色如练，洒在庭院的青石板上。{query[:20] if query else '主角'}缓缓抬起头，"
                  f"目光望向远处的山峦。风穿过竹林，发出沙沙的声响，仿佛在诉说着什么。\n\n"
                  f"「你来了。」一个低沉的声音从身后传来。\n\n"
                  f"他没有回头，只是轻轻握紧了手中的长剑。剑身在月光下泛着冷冽的寒光，"
                  f"映照出他坚定的眼神。\n\n"
                  f"这一刻，命运的齿轮开始转动……",
        "context": "（演示模式）知识库检索功能需要安装 faiss 库才能使用。",
        "review": "【人物一致性】\n评分：8/10\n\n问题：\n无\n\n【世界观一致性】\n评分：9/10\n\n问题：\n无\n\n【剧情规则一致性】\n评分：8/10\n\n问题：\n无\n\n综合评分：25/30\n\n审核结论：\n通过",
        "evidence_list": [],
        "scores": [],
    }


def _generate_timeline_from_characters():
    """根据 characters.json 中的角色和文档内容，生成详细的 character_timeline.json。
    使用 LLM 分析每个角色的经历和关键事件，生成多个阶段的时间线。
    """
    global _llm
    print("[RAG] 开始生成角色时间线...")
    
    characters_path = get_characters_path()
    timeline_path = get_timeline_path()
    chunks_path = get_chunks_path()
    
    characters_data = {}
    if os.path.exists(characters_path):
        try:
            with open(characters_path, "r", encoding="utf-8") as f:
                characters_data = json.load(f)
        except Exception as e:
            print(f"[RAG] 读取 characters.json 失败: {e}")
            pass

    if not characters_data:
        print("[RAG] 没有提取到角色，跳过时间线生成")
        if os.path.exists(timeline_path):
            os.remove(timeline_path)
        return

    # 读取文档内容用于分析
    doc_text = ""
    if os.path.exists(chunks_path):
        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            doc_text = "\n".join(chunks)[:6000]  # 截取前6000字作为上下文
            print(f"[RAG] 读取文档内容: {len(doc_text)} 字")
        except Exception as e:
            print(f"[RAG] 读取 user_chunks.json 失败: {e}")
            pass

    if not doc_text:
        print("[RAG] 没有文档内容，生成简化版本时间线")
        timeline = {}
        for name, info in characters_data.items():
            timeline[name] = {
                "timeline": [
                    {
                        "id": "phase_1",
                        "时序": 1,
                        "名称": "登场",
                        "关键事件": [],
                        "性格": info.get("性格", "") if isinstance(info, dict) else "",
                        "行为边界": "",
                        "关系": info.get("关系", "") if isinstance(info, dict) else "",
                        "禁止行为": []
                    }
                ]
            }
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(timeline, f, ensure_ascii=False, indent=2)
        return

    # 使用 LLM 为每个角色生成详细时间线
    if _llm is None:
        print("[RAG] LLM 未初始化，生成简化版本时间线")
        # 如果 LLM 未初始化，生成简化版本
        timeline = {}
        for name, info in characters_data.items():
            timeline[name] = {
                "timeline": [
                    {
                        "id": "phase_1",
                        "时序": 1,
                        "名称": "登场",
                        "关键事件": [],
                        "性格": info.get("性格", "") if isinstance(info, dict) else "",
                        "行为边界": "",
                        "关系": info.get("关系", "") if isinstance(info, dict) else "",
                        "禁止行为": []
                    }
                ]
            }
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(timeline, f, ensure_ascii=False, indent=2)
        return

    character_names = list(characters_data.keys())
    characters_str = "、".join(character_names)

    prompt = f"""你是一位专业的小说分析师。请根据以下小说文本，为角色生成详细的人物时间线。

角色列表：{characters_str}

小说文本：
{doc_text}

请为每个角色生成3-5个成长阶段的时间线，包含：
- 阶段名称（如：初入江湖、崭露头角、遭遇挫折、逆袭崛起、圆满结局等）
- 关键事件（2-3个具体事件）
- 性格特征（该阶段的性格特点）
- 行为边界（该阶段能做什么、不能做什么）
- 人物关系变化

输出严格的 JSON 格式，示例：
{{
  "角色名": {{
    "timeline": [
      {{
        "id": "phase_1",
        "时序": 1,
        "名称": "登场/初始阶段",
        "关键事件": ["事件1", "事件2"],
        "性格": "性格描述",
        "行为边界": "行为边界描述",
        "关系": ["关系1", "关系2"],
        "禁止行为": ["禁止的行为1"]
      }},
      {{
        "id": "phase_2",
        "时序": 2,
        "名称": "发展阶段",
        "关键事件": ["事件1", "事件2"],
        "性格": "性格描述",
        "行为边界": "行为边界描述",
        "关系": ["关系1", "关系2"],
        "禁止行为": ["禁止的行为1"]
      }}
    ]
  }}
}}

请确保：
1. 每个角色至少有3个阶段
2. 阶段名称要生动具体，不要用"起始阶段"这种通用词
3. 关键事件要从文本中提取具体内容
4. 严格只输出 JSON，不要有其他文字"""

    try:
        response = _llm.invoke(prompt)
        content = response.content.strip()

        # 清理 markdown 标记
        if content.startswith("```"):
            import re
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        timeline = json.loads(content)

        # 验证并补充缺失的角色
        for name in character_names:
            if name not in timeline:
                info = characters_data.get(name, {})
                timeline[name] = {
                    "timeline": [
                        {
                            "id": "phase_1",
                            "时序": 1,
                            "名称": "登场",
                            "关键事件": [],
                            "性格": info.get("性格", "") if isinstance(info, dict) else "",
                            "行为边界": "",
                            "关系": info.get("关系", "") if isinstance(info, dict) else "",
                            "禁止行为": []
                        }
                    ]
                }

        # 确保每个角色的 timeline 格式正确
        for name in timeline:
            if "timeline" not in timeline[name]:
                timeline[name]["timeline"] = []
            if len(timeline[name]["timeline"]) == 0:
                timeline[name]["timeline"].append({
                    "id": "phase_1",
                    "时序": 1,
                    "名称": "登场",
                    "关键事件": [],
                    "性格": "",
                    "行为边界": "",
                    "关系": [],
                    "禁止行为": []
                })
            # 确保每个阶段都有必要的字段
            for phase in timeline[name]["timeline"]:
                for field in ["关键事件", "关系", "禁止行为"]:
                    if field not in phase:
                        phase[field] = []
                    elif not isinstance(phase[field], list):
                        # 如果是字符串，包装成列表
                        if isinstance(phase[field], str) and phase[field]:
                            phase[field] = [phase[field]]
                        else:
                            phase[field] = []
                if "性格" not in phase:
                    phase["性格"] = ""
                if "行为边界" not in phase:
                    phase["行为边界"] = ""

        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(timeline, f, ensure_ascii=False, indent=2)
        print(f"[RAG] 角色时间线生成成功：{len(timeline)} 个角色")

    except Exception as e:
        print(f"[RAG] LLM 生成时间线失败，使用简化版本: {e}")
        # 失败时使用简化版本
        timeline = {}
        for name, info in characters_data.items():
            timeline[name] = {
                "timeline": [
                    {
                        "id": "phase_1",
                        "时序": 1,
                        "名称": "登场",
                        "关键事件": [],
                        "性格": info.get("性格", "") if isinstance(info, dict) else "",
                        "行为边界": "",
                        "关系": info.get("关系", "") if isinstance(info, dict) else "",
                        "禁止行为": []
                    }
                ]
            }
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(timeline, f, ensure_ascii=False, indent=2)


def _mock_upload(files):
    """没有 RAG 时的模拟上传"""
    count = 0
    for f in files:
        content = f.read()
        count += len(content) // 100 + 1
    return count or 1


def _mock_trajectories():
    """模拟情绪轨迹数据"""
    return {
        "keys": ["误会与和解", "热血崛起", "悲伤离别", "甜蜜相遇"],
        "detail": {
            "误会与和解": {
                "说明": "因误会产生隔阂，最终冰释前嫌",
                "情绪起点": ["两人因小事产生误会", "一方心生芥蒂"],
                "转折触发": ["第三者挑拨", "关键时刻发现真相"],
                "关系瞬间": ["冰释前嫌的拥抱", "雨中对话"],
                "情绪落点": ["重归于好", "更加珍惜彼此"],
                "写作重心": "心理描写 > 对话 > 动作描写"
            },
            "热血崛起": {
                "说明": "主角从低谷中崛起的热血篇章",
                "情绪起点": ["遭受打击", "陷入低谷"],
                "转折触发": ["获得机缘", "遇到贵人指点"],
                "关系瞬间": ["击败强敌", "一战成名"],
                "情绪落点": ["踏上新征程", "立下誓言"],
                "写作重心": "动作描写 > 心理描写 > 环境描写"
            },
            "悲伤离别": {
                "说明": "感人至深的离别场景",
                "情绪起点": ["意识到即将分别", "强装镇定"],
                "转折触发": ["说出心里话", "时间所剩无几"],
                "关系瞬间": ["最后的拥抱", "含泪微笑"],
                "情绪落点": ["目送远去", "留下约定"],
                "写作重心": "细节描写 > 对话 > 环境描写"
            },
            "甜蜜相遇": {
                "说明": "浪漫甜蜜的初次相遇",
                "情绪起点": ["初次见面的悸动", "心跳加速"],
                "转折触发": ["意外肢体接触", "四目相对"],
                "关系瞬间": ["第一次牵手", "交换信物"],
                "情绪落点": ["约定下次相见", "各自心中小鹿乱撞"],
                "写作重心": "心理描写 > 细节描写 > 对话"
            }
        }
    }


def _mock_characters():
    """模拟角色数据"""
    return {
        "characters": {
            "林黛玉": {
                "timeline": [
                    {"时序": 1, "名称": "初入贾府", "关键事件": ["初见贾母", "与宝玉初识"], "性格": "敏感聪慧，才情过人", "行为边界": "举止得体，不越礼数", "关系": {"宝玉": "青梅竹马"}, "禁止行为": ["失言", "失态"]},
                    {"时序": 2, "名称": "互生情愫", "关键事件": ["共读西厢", "葬花吟"], "性格": "多愁善感，对宝玉深情", "行为边界": "诗社夺魁，泪题帕", "关系": {"宝玉": "情投意合"}, "禁止行为": ["离宝玉", "接受他人"]},
                    {"时序": 3, "名称": "泪尽而亡", "关键事件": ["焚稿断痴情", "魂归离恨天"], "性格": "心如死灰，魂牵梦萦", "行为边界": "完成还泪宿命", "关系": {"宝玉": "永诀"}, "禁止行为": ["再世情缘"]}
                ]
            },
            "贾宝玉": {
                "timeline": [
                    {"时序": 1, "名称": "衔玉而生", "关键事件": ["降诞荣国府", "初识黛玉"], "性格": "痴情公子，怜香惜玉", "行为边界": "不与世俗女子亲近", "关系": {"黛玉": "一见倾心"}, "禁止行为": ["仕途经济"]},
                    {"时序": 2, "名称": "叛逆期", "关键事件": ["砸玉抗婚", "出家为僧"], "性格": "反抗封建礼教", "行为边界": "与黛玉同生同死", "关系": {"黛玉": "生死相许"}, "禁止行为": ["妥协", "放弃"]}
                ]
            }
        }
    }


# =====================================================================
# 接口
# =====================================================================

@app.get("/api/health")
def health():
    _ensure_rag()
    ready = os.path.exists(get_faiss_path()) and os.path.exists(get_chunks_path())
    traj_keys = _get_trajectory_keys() if HAS_RAG else _mock_trajectories()["keys"]
    return {
        "status": "ok",
        "knowledge_ready": ready,
        "trajectories": traj_keys,
        "rag_mode": "full" if HAS_RAG else "mock",
    }


# ---------- Lore 库：上传 ----------

@app.post("/api/upload")
async def upload(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="未收到文件")

    wrappers = []
    file_meta_list = []
    for f in files:
        content = await f.read()
        if not content:
            continue
        wrappers.append(_FileLike(f.filename or "untitled.txt", content))
        ext = (f.filename or "txt").split(".")[-1].lower()
        file_meta_list.append({
            "id": int(random.random() * 1e9),
            "name": f.filename or "untitled.txt",
            "size": len(content),
            "type": ext,
            "uploaded_at": json.dumps(__import__('datetime').datetime.now(), default=str)
        })

    if not wrappers:
        raise HTTPException(status_code=400, detail="文件内容为空")

    _ensure_rag()
    try:
        if HAS_RAG:
            num = _build_user_knowledge(wrappers)
            # 根据上传内容提取的角色，生成基础时间线
            _generate_timeline_from_characters()
        else:
            num = _mock_upload(wrappers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识库构建失败: {e}")

    # 保存文件元数据到文件
    files_path = get_files_path()
    existing = []
    if os.path.exists(files_path):
        try:
            with open(files_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except:
            pass
    existing.extend(file_meta_list)
    with open(files_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return {"chunks": num, "message": f"知识库构建完成，共 {num} 个文本片段", "files": file_meta_list}


@app.get("/api/lore/files")
def lore_files():
    file_list = []
    files_path = get_files_path()
    if os.path.exists(files_path):
        try:
            with open(files_path, "r", encoding="utf-8") as f:
                file_list = json.load(f)
        except:
            pass

    total = 0
    chunks_path = get_chunks_path()
    if os.path.exists(chunks_path):
        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
                total = len(chunks)
        except:
            pass

    # 格式化文件大小
    for item in file_list:
        size = item.get("size", 0)
        if size > 1024 * 1024:
            item["size_display"] = f"{size / 1024 / 1024:.1f} MB"
        elif size > 1024:
            item["size_display"] = f"{size / 1024:.1f} KB"
        else:
            item["size_display"] = f"{size} B"

    return {"files": file_list, "total": total}


@app.delete("/api/lore/files/{file_id}")
def delete_lore_file(file_id: int):
    files_path = get_files_path()
    if not os.path.exists(files_path):
        raise HTTPException(status_code=404, detail="文件列表不存在")
    with open(files_path, "r", encoding="utf-8") as f:
        files = json.load(f)
    files = [f for f in files if f.get("id") != file_id]
    with open(files_path, "w", encoding="utf-8") as f:
        json.dump(files, f, ensure_ascii=False, indent=2)
    return {"ok": True}


@app.post("/api/lore/rebuild")
def rebuild_characters():
    """重新从已上传文档中提取角色并生成时间线。"""
    try:
        from character_builder import build_character_profile
        chars = build_character_profile()
        _generate_timeline_from_characters()
        return {"characters": list(chars.keys()), "count": len(chars)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重建失败: {e}")


# ---------- 情感曲线 ----------

@app.get("/api/emotion/trajectories")
def emotion_trajectories():
    _ensure_rag()
    if HAS_RAG:
        data = _load_trajectories()
        return {"keys": list(data.keys()), "detail": data}
    else:
        return _mock_trajectories()


@app.post("/api/emotion/plan")
def emotion_plan(req: EmotionPlanRequest):
    _ensure_rag()
    if HAS_RAG and _llm:
        data = _load_trajectories()
        template = data.get(req.trajectory)
        if not template:
            template = {
                "情绪起点": ["平静开局", "暗流涌动", "日常铺垫"],
                "转折触发": ["突发事件", "意外相遇", "秘密揭露"],
                "关系瞬间": ["情感爆发", "内心挣扎", "关键抉择"],
                "情绪落点": ["成长领悟", "关系升华", "新的开始"],
                "写作重心": "对话 > 心理描写 > 动作描写",
                "说明": f"自定义轨迹：{req.trajectory}"
            }
        
        traj_name = req.trajectory
        user_req = req.user_request
        character = req.character or ""
        
        prompt = f"""你是一名小说剧情规划师。请根据用户的剧情需求，围绕「{traj_name}」这个情绪轨迹，为四个阶段各写一句简短的剧情规划描述（20-40字）。

角色：{character}
剧情需求：{user_req}

情绪轨迹模板提示：
- 情绪起点：{random.choice(template.get("情绪起点", ["待定"]))}
- 转折触发：{random.choice(template.get("转折触发", ["待定"]))}
- 关系瞬间：{random.choice(template.get("关系瞬间", ["待定"]))}
- 情绪落点：{random.choice(template.get("情绪落点", ["待定"]))}

请严格按以下格式返回（每阶段一句，描述该阶段发生了什么事、有什么情感）：
起点：[一句描述]
转折：[一句描述]
高潮：[一句描述]
落点：[一句描述]"""

        try:
            response = _llm.invoke(prompt)
            lines = [l.strip() for l in response.content.strip().split("\n") if l.strip()]
            
            start_desc = twist_desc = climax_desc = end_desc = ""
            for line in lines:
                if line.startswith("起点：") or line.startswith("起点:"):
                    start_desc = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                elif line.startswith("转折：") or line.startswith("转折:"):
                    twist_desc = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                elif line.startswith("高潮：") or line.startswith("高潮:"):
                    climax_desc = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                elif line.startswith("落点：") or line.startswith("落点:"):
                    end_desc = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            
            if not start_desc: start_desc = random.choice(template.get("情绪起点", ["待定"]))
            if not twist_desc: twist_desc = random.choice(template.get("转折触发", ["待定"]))
            if not climax_desc: climax_desc = random.choice(template.get("关系瞬间", ["待定"]))
            if not end_desc: end_desc = random.choice(template.get("情绪落点", ["待定"]))
        except Exception as e:
            print(f"[RAG] LLM 生成情感规划失败: {e}")
            start_desc = random.choice(template.get("情绪起点", ["待定"]))
            twist_desc = random.choice(template.get("转折触发", ["待定"]))
            climax_desc = random.choice(template.get("关系瞬间", ["待定"]))
            end_desc = random.choice(template.get("情绪落点", ["待定"]))
        
        focus = template.get("写作重心", "心理描写 > 对话 > 动作描写")
        return {
            "trajectory": req.trajectory,
            "description": template.get("说明", ""),
            "writing_focus": focus,
            "start": {"label": "情感起点", "desc": start_desc, "value": 30},
            "twist": {"label": "转折", "desc": twist_desc, "value": 20},
            "climax": {"label": "高潮", "desc": climax_desc, "value": 85},
            "end": {"label": "落点", "desc": end_desc, "value": 65},
        }
    elif HAS_RAG:
        data = _load_trajectories()
        template = data.get(req.trajectory)
        if not template:
            template = {
                "情绪起点": ["平静开局", "暗流涌动", "日常铺垫"],
                "转折触发": ["突发事件", "意外相遇", "秘密揭露"],
                "关系瞬间": ["情感爆发", "内心挣扎", "关键抉择"],
                "情绪落点": ["成长领悟", "关系升华", "新的开始"],
                "写作重心": "对话 > 心理描写 > 动作描写",
                "说明": f"自定义轨迹：{req.trajectory}"
            }
        start = random.choice(template.get("情绪起点", ["待定"]))
        twist = random.choice(template.get("转折触发", ["待定"]))
        climax = random.choice(template.get("关系瞬间", ["待定"]))
        end = random.choice(template.get("情绪落点", ["待定"]))
        focus = template.get("写作重心", "心理描写 > 对话 > 动作描写")
        return {
            "trajectory": req.trajectory,
            "description": template.get("说明", ""),
            "writing_focus": focus,
            "start": {"label": "情感起点", "desc": start, "value": 30},
            "twist": {"label": "转折", "desc": twist, "value": 20},
            "climax": {"label": "高潮", "desc": climax, "value": 85},
            "end": {"label": "落点", "desc": end, "value": 65},
        }
    else:
        mock = _mock_trajectories()
        template = mock["detail"].get(req.trajectory)
        if not template:
            first_key = list(mock["detail"].keys())[0]
            template = mock["detail"][first_key]
        start = template["情绪起点"][0]
        twist = template["转折触发"][0]
        climax = template["关系瞬间"][0]
        end = template["情绪落点"][0]
        focus = template.get("写作重心", "心理描写 > 对话 > 动作描写")
        return {
            "trajectory": req.trajectory,
            "description": template.get("说明", ""),
            "writing_focus": focus,
            "start": {"label": "情感起点", "desc": start, "value": 30},
            "twist": {"label": "转折", "desc": twist, "value": 20},
            "climax": {"label": "高潮", "desc": climax, "value": 85},
            "end": {"label": "落点", "desc": end, "value": 65},
        }


# ---------- 时间线 ----------

@app.get("/api/characters")
def characters():
    """返回从已上传设定文件中提取的角色列表。
    如果没有 character_timeline.json 文件，返回空列表（前端提示先上传）。
    """
    timeline_path = get_timeline_path()
    if os.path.exists(timeline_path):
        try:
            with open(timeline_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"characters": data, "count": len(data)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取角色数据失败: {e}")
    return {"characters": {}, "count": 0}


@app.get("/api/timeline/{character}")
def timeline(character: str):
    """返回指定角色的时间线。需要先上传设定文件生成 character_timeline.json。"""
    timeline_path = get_timeline_path()
    if not os.path.exists(timeline_path):
        raise HTTPException(status_code=400, detail="请先上传设定文件以提取角色时间线")
    with open(timeline_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if character not in data:
        raise HTTPException(status_code=404, detail=f"未找到角色：{character}")
    return {"character": character, "data": data[character]}


# ---------- 生成正文 ----------

class GenerateRequest(BaseModel):
    query: str
    mode: str = "create"

class ReviseRequest(BaseModel):
    original: str
    instruction: str
    query: str = ""

@app.post("/api/revise")
def revise(req: ReviseRequest):
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="修改意见不能为空")
    
    _ensure_rag()
    
    if not HAS_RAG or not _llm or not _editor_agent:
        # 没有LLM时返回模拟修改
        return {
            "answer": f"（演示模式）根据修改意见「{req.instruction}」，已对正文进行修改：\n\n"
                      f"{req.original[:200]}...\n\n[修改后内容]",
            "review": ""
        }
    
    try:
        # 使用 Editor Agent 根据用户修改意见重新生成
        revised = _editor_agent(req.original, "", _llm, instruction=req.instruction)
        return {"answer": revised, "review": ""}
    except Exception as e:
        print(f"[ERROR] revise failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"修改失败: {e}")

@app.post("/api/generate")
def generate(req: GenerateRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="创作需求不能为空")

    _ensure_rag()

    if not HAS_RAG:
        return _mock_generate(req.query, req.mode)

    if not (os.path.exists(get_faiss_path()) and os.path.exists(get_chunks_path())):
        raise HTTPException(status_code=400, detail="请先上传文档构建知识库")

    try:
        print(f"[DEBUG] generate called: mode={req.mode}, query={req.query[:50]}")
        if req.mode == "qa":
            # 问答模式：检索文档中最接近问题的文本片段
            # 需要同时获取 evidence_list 和 scores
            from rag_novel import retrieve_context
            print("[DEBUG] QA mode: calling _rag_answer")
            answer, context = _rag_answer(req.query)
            print(f"[DEBUG] QA mode: _rag_answer returned, answer={len(answer) if answer else 0}")
            # 重新检索以获取 evidence_list 和 scores 用于前端展示
            print("[DEBUG] QA mode: calling retrieve_context")
            _, evidence_list, scores = retrieve_context(req.query)
            print(f"[DEBUG] QA answer: {str(answer)[:100] if answer else '(empty)'}, evidences: {len(evidence_list)}")
            return {"answer": answer, "context": context, "review": "", "evidence_list": evidence_list, "scores": scores}
        else:
            # 创作模式：多Agent生成小说正文
            print("[DEBUG] Create mode: calling _generate_with_agents")
            answer, context, review, evidence_list, scores = _generate_with_agents(req.query, _llm)
            print(f"[DEBUG] create answer length: {len(answer) if answer else 0}, review length: {len(review) if review else 0}")
            print(f"[DEBUG] create answer preview: {str(answer)[:300] if answer else '(empty)'}")
            print(f"[DEBUG] create review preview: {str(review)[:300] if review else '(empty)'}")
            # 检查 answer 和 review 是否相同
            if answer == review:
                print("[ERROR] answer 和 review 相同！这是错误的！")
            print(f"[DEBUG] 返回给前端的数据: answer={len(answer)}字, review={len(review)}字")
            return {"answer": answer, "context": context, "review": review, "evidence_list": evidence_list, "scores": scores}
    except Exception as e:
        print(f"[ERROR] generate failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")


if __name__ == "__main__":
    import uvicorn
    import os
    # 云端部署（Render/Heroku等）会设置 PORT 环境变量
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port)
