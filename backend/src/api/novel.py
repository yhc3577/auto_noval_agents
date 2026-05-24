"""小说项目接口：创建、列表、详情、更新"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core.auth import get_current_user, get_current_user_flexible
from ..core.database import get_mongodb
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class CharacterInput(BaseModel):
    name: str
    role_type: str = Field(..., pattern="^(protagonist|antagonist|supporting)$")
    personality: str
    background: str
    relationships: list[dict] = []


class CreateNovelRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)
    genre: str = ""
    style: str = ""
    world_setting: str = ""
    chapter_count: int = Field(default=100, ge=1, le=500)
    words_per_chapter: int = Field(default=3000, ge=2000, le=5000)
    characters: list[CharacterInput] = []
    existing_outline: str | None = None


class UpdateNovelRequest(BaseModel):
    project_id: str
    world_setting: str | None = None
    style: str | None = None
    characters: list[CharacterInput] | None = None
    copyright_threshold: float | None = Field(None, ge=0, le=1)


@router.post("/create", status_code=201)
async def create_novel(
    req: CreateNovelRequest,
    user: dict = Depends(get_current_user),
):
    """新建小说项目"""
    from ..services.novel_service import create_project

    result = await create_project(user["user_id"], req.model_dump())
    logger.info(f"创建小说项目: {req.title}")
    return result


@router.get("/list")
async def list_novels(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """获取用户的小说项目列表"""
    db = await get_mongodb()
    projects = db["novel_projects"]

    skip = (page - 1) * page_size
    cursor = projects.find({"user_id": user["user_id"]}).skip(skip).limit(page_size)
    items = []
    async for doc in cursor:
        items.append({
            "project_id": str(doc["_id"]),
            "title": doc["title"],
            "genre": doc["genre"],
            "status": doc["status"],
            "current_chapter": doc.get("current_chapter", 0),
            "chapter_count": doc["chapter_count"],
            "created_at": doc["created_at"].isoformat(),
        })

    total = await projects.count_documents({"user_id": user["user_id"]})
    return {"total": total, "items": items}


@router.get("/detail")
async def get_novel_detail(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """查看项目设定和完整大纲"""
    from ..services.novel_service import get_project_detail

    result = await get_project_detail(project_id, user["user_id"])
    if not result:
        raise HTTPException(status_code=404, detail="项目不存在")
    return result


@router.put("/update")
async def update_novel(
    req: UpdateNovelRequest,
    user: dict = Depends(get_current_user),
):
    """修改项目设定"""
    from ..services.novel_service import update_project

    result = await update_project(req.project_id, user["user_id"], req.model_dump())
    if not result:
        raise HTTPException(status_code=404, detail="项目不存在")
    return result


class DeleteNovelRequest(BaseModel):
    project_id: str


class RegenerateOutlineRequest(BaseModel):
    project_id: str


@router.post("/regenerate-outline")
async def regenerate_outline(
    req: RegenerateOutlineRequest,
    user: dict = Depends(get_current_user),
):
    """重新生成大纲"""
    from ..services.novel_service import regenerate_outline as svc_regenerate

    result = await svc_regenerate(req.project_id, user["user_id"])
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/delete")
async def delete_novel(
    req: DeleteNovelRequest,
    user: dict = Depends(get_current_user),
):
    """删除小说项目"""
    from ..services.novel_service import delete_project

    result = await delete_project(req.project_id, user["user_id"])
    if not result:
        raise HTTPException(status_code=404, detail="项目不存在")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class OutlineReviewRequest(BaseModel):
    project_id: str
    approved: bool
    feedback: str = ""


class UpdateOutlineRequest(BaseModel):
    project_id: str
    full_outline: str | None = None
    volume_outlines: list[dict] | None = None
    chapter_outlines: list[dict] | None = None


@router.post("/outline/review")
async def review_outline(
    req: OutlineReviewRequest,
    user: dict = Depends(get_current_user),
):
    """审核大纲：通过或驳回"""
    from ..services.novel_service import submit_outline_review

    result = await submit_outline_review(
        req.project_id, user["user_id"], req.approved, req.feedback
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.put("/outline/update")
async def update_outline(
    req: UpdateOutlineRequest,
    user: dict = Depends(get_current_user),
):
    """修改大纲内容（审核阶段）"""
    from ..services.novel_service import update_outline as svc_update_outline

    result = await svc_update_outline(
        req.project_id,
        user["user_id"],
        {k: v for k, v in req.model_dump().items() if v is not None and k != "project_id"},
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class OutlineChatRequest(BaseModel):
    project_id: str
    message: str
    history: list[dict] = []


class ApplySuggestionRequest(BaseModel):
    project_id: str
    target_type: str = Field(..., pattern="^(full_outline|volume_outline|chapter_outline)$")
    target_index: int | None = None
    instruction: str


class ReviewSectionRequest(BaseModel):
    project_id: str
    target_type: str = Field(..., pattern="^(full_outline|volume_outline|chapter_outline)$")
    target_index: int | None = None
    instruction: str = ""


@router.post("/outline/chat")
async def outline_chat(
    req: OutlineChatRequest,
    user: dict = Depends(get_current_user_flexible),
):
    """大纲审核 AI 助手：与 LLM 讨论大纲（SSE 流式）"""
    from ..core.database import get_mongodb
    from ..core.llm import call_llm_stream
    from bson import ObjectId

    db = await get_mongodb()

    project = await db["novel_projects"].find_one({
        "_id": ObjectId(req.project_id),
        "user_id": user["user_id"],
    })
    if not project:
        async def err_gen():
            yield f"data: {json.dumps({'type': 'error', 'content': '项目不存在'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(err_gen(), media_type="text/event-stream")

    outline = await db["outlines"].find_one({"project_id": req.project_id})
    chars_cursor = db["characters"].find({"project_id": req.project_id})
    characters = []
    async for c in chars_cursor:
        characters.append(f"- {c['name']}({c['role_type']}): {c['personality']}, {c['background']}")

    outline_text = _format_outline_for_chat(outline)
    char_text = "\n".join(characters) if characters else "暂无角色"

    system_prompt = _build_outline_chat_system_prompt(project, outline_text, char_text)

    # 将历史消息转为 user/assistant 交替的对话
    conversation_parts = []
    for h in req.history:
        role = "用户" if h.get("role") == "user" else "助手"
        conversation_parts.append(f"{role}: {h.get('content', '')}")
    conversation = "\n".join(conversation_parts)

    user_prompt = f"""以下是之前的对话：
{conversation if conversation else "(无历史对话)"}

用户最新消息：{req.message}

请根据用户的消息给出专业回答。如果用户要求修改大纲内容（如"优化""改成""重写""修改"等），务必使用 <<<MODIFY>>> 标记格式给出可直接应用的修改文本。"""

    async def event_generator():
        full_response = ""
        try:
            async for chunk in call_llm_stream(system_prompt, user_prompt, max_tokens=4096):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
            return
        yield f"data: {json.dumps({'type': 'done', 'content': full_response}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/outline/review-section")
async def review_section(
    req: ReviewSectionRequest,
    user: dict = Depends(get_current_user),
):
    """AI 审核指定大纲段落：返回原始内容和 AI 修改后的内容供 diff 对比"""
    from ..core.database import get_mongodb
    from ..core.llm import call_llm
    from bson import ObjectId

    db = await get_mongodb()

    project = await db["novel_projects"].find_one({
        "_id": ObjectId(req.project_id),
        "user_id": user["user_id"],
    })
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    outline = await db["outlines"].find_one({"project_id": req.project_id})
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")

    # 获取角色信息
    chars_cursor = db["characters"].find({"project_id": req.project_id})
    characters = []
    async for c in chars_cursor:
        characters.append(f"{c['name']}({c['role_type']}): {c['personality']}")

    # 获取要审核的目标内容，以及需要校验的上层大纲
    target_content = ""
    target_label = ""
    parent_context = ""  # 上层大纲用于冲突校验
    ch_start = 1
    ch_end = project.get("chapter_count", 100)

    if req.target_type == "full_outline":
        target_content = outline.get("full_outline", "")
        target_label = "全书大纲"

    elif req.target_type == "volume_outline" and req.target_index is not None:
        vols = outline.get("volume_outlines", [])
        if req.target_index < len(vols):
            vol = vols[req.target_index]
            target_content = json.dumps(vol, ensure_ascii=False, indent=2)
            vn = vol.get("volume_number", req.target_index + 1)
            ch_start = (vn - 1) * 10 + 1
            ch_end = min(vn * 10, project.get("chapter_count", 100))
            target_label = f"第{vn}卷 {vol.get('volume_title', '')}（应覆盖第{ch_start}-{ch_end}章）"
        # 分卷大纲需要校验与全书大纲的一致性
        if target_content:
            parent_context = f"""
## 章节范围约束（重要）
本卷仅覆盖第{ch_start}-{ch_end}章，大纲中提到的章节编号必须在此范围内，不得超出。

## 全书大纲（必须保持一致，不得冲突）
{outline.get('full_outline', '暂无')}"""

    elif req.target_type == "chapter_outline" and req.target_index is not None:
        chs = outline.get("chapter_outlines", [])
        if req.target_index < len(chs):
            ch = chs[req.target_index]
            target_content = json.dumps(ch, ensure_ascii=False, indent=2)
            target_label = f"第{ch.get('chapter_number', req.target_index + 1)}章 {ch.get('title', '')}"
            cn = ch.get("chapter_number", 0)
            cn = cn if cn > 0 else (req.target_index + 1)
        # 逐章细纲需要校验与全书大纲和所属分卷大纲的一致性
        if target_content:
            parent_vol = None
            vols = outline.get("volume_outlines", [])
            for v in vols:
                vn = v.get("volume_number", 0)
                start = (vn - 1) * 10 + 1 if vn > 0 else 0
                end = vn * 10 if vn > 0 else 0
                if start <= cn <= end:
                    parent_vol = v
                    break
            parent_context = f"""
## 全书大纲（必须保持一致，不得冲突）
{outline.get('full_outline', '暂无')}"""
            if parent_vol:
                parent_context += f"""

## 所属分卷大纲（必须保持一致，不得冲突）
第{parent_vol.get('volume_number', '?')}卷 {parent_vol.get('volume_title', '')}：
{parent_vol.get('content', '')}"""

    if not target_content:
        raise HTTPException(status_code=400, detail="目标内容为空")

    novel_context = f"""书名：{project.get('title', '')}
题材：{project.get('genre', '')}
文风：{project.get('style', '')}
世界观：{project.get('world_setting', '')}
总章节数：{project.get('chapter_count', 0)}
角色：{'; '.join(characters) if characters else '无'}"""

    # 冲突校验描述随 target_type 不同
    if req.target_type == "volume_outline":
        conflict_check = f"6. 【重要】分卷内容必须与全书大纲一致，情节走向、人物命运、关键事件不得与全书大纲冲突\n7. 【重要】本卷大纲中提到的章节编号必须严格在第{ch_start}-{ch_end}章范围内，不得出现超出此范围的章节编号"
    elif req.target_type == "chapter_outline":
        conflict_check = "6. 【重要】章节内容必须同时与全书大纲和所属分卷大纲保持一致，不得与上层大纲的任何设定冲突"
    else:
        conflict_check = ""

    system_prompt = f"""你是一个专业的小说大纲审核编辑。你需要审核指定的{target_label}，发现其中的问题并给出改进后的版本。

## 小说上下文
{novel_context}{parent_context}

## 审核标准
1. 情节是否合理、有吸引力
2. 与整体世界观和角色设定是否一致
3. 节奏是否恰当，是否有拖沓或仓促
4. 冲突和悬念设计是否到位
5. 文字表达是否清晰有力
{conflict_check}

## 输出要求
只返回改进后的完整内容，保持原格式不变。
- 如果是全书大纲：返回纯文本
- 如果是分卷大纲或章节细纲：返回 JSON 格式（保留原有字段结构）

不要加任何解释、不要加"修改建议"或"改进点"等前缀，直接给出修改后的内容。"""

    instruction_text = ""
    if req.instruction.strip():
        instruction_text = f"""

## 用户额外要求
{req.instruction.strip()}

请特别注意满足用户的要求。"""

    user_prompt = f"""请审核以下{target_label}的内容并给出改进版本：

{target_content}{instruction_text}

直接返回改进后的完整内容："""

    modified = await call_llm(system_prompt, user_prompt, max_tokens=4096)
    modified = _strip_thinking(modified)
    return {
        "original": target_content,
        "modified": modified.strip(),
        "target_type": req.target_type,
        "target_index": req.target_index,
        "target_label": target_label,
    }


def _strip_thinking(text: str) -> str:
    """去除 DeepSeek R1 等推理模型的 think 标签和 markdown 代码块"""
    import re
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    # 去除 markdown 代码块包裹（如 ```json ... ```）
    text = re.sub(r"^```(?:json|javascript|js|text|html|xml|yaml|python)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _format_outline_for_chat(outline: dict | None) -> str:
    """将大纲格式化为可读文本用于 AI 对话，并标注 target_index 供 AI 定位修改"""
    if not outline:
        return "暂无大纲"

    parts = []
    parts.append(f"【全书大纲】(target_type: full_outline)\n{outline.get('full_outline', '暂无')}")

    for idx, vol in enumerate(outline.get("volume_outlines", [])):
        vn = vol.get("volume_number", "?")
        vt = vol.get("volume_title", "")
        vc = vol.get("content", "")
        parts.append(f"\n【第{vn}卷 {vt}】(target_type: volume_outline, target_index: {idx})\n{vc}")

    parts.append("\n【逐章细纲】")
    for idx, ch in enumerate(outline.get("chapter_outlines", [])):
        cn = ch.get("chapter_number", "?")
        ct = ch.get("title", "")
        cc = ch.get("content", "")
        parts.append(f"[{idx}] 第{cn}章 {ct}: {cc}")

    return "\n".join(parts)


def _build_outline_chat_system_prompt(project: dict, outline_text: str, char_text: str) -> str:
    """构建大纲审核 AI 助手的系统提示"""
    return f"""你是一个专业的 AI 审核助手，负责帮助作者审核和直接修改小说大纲。你不仅可以分析建议，还能直接生成修改后的大纲内容供作者一键应用。

## 小说基本信息
- 书名：{project.get('title', '未知')}
- 题材：{project.get('genre', '未知')}
- 文风：{project.get('style', '未知')}
- 世界观：{project.get('world_setting', '未知')}
- 总章节数：{project.get('chapter_count', 0)}

## 角色设定
{char_text}

## 当前大纲
{outline_text}

## 重要：修改标记格式

当你需要给出具体的修改方案时（不仅是分析建议，而是直接给出修改后的文本），必须使用以下格式将修改内容包裹起来，这样系统才能识别并提供"一键应用"按钮：

```
<<<MODIFY
target_type:full_outline
>>>
修改后的全书大纲完整文本...
<<<ENDMODIFY>>>
```

修改分卷大纲（注意 target_index 是分卷在列表中的序号，从0开始）：
```
<<<MODIFY
target_type:volume_outline
target_index:0
>>>
修改后的分卷内容（保持 JSON 格式，包含 volume_number, volume_title, content 字段）...
<<<ENDMODIFY>>>
```

修改章节细纲（注意 target_index 是 [数字] 标记的序号）：
```
<<<MODIFY
target_type:chapter_outline
target_index:3
>>>
修改后的章节内容（保持 JSON 格式，包含 chapter_number, title, content 字段）...
<<<ENDMODIFY>>>
```

## 规则
1. 先分析问题，再给出修改方案
2. 如果要给出具体修改文本，必须使用上面的 <<<MODIFY>>> 标记
3. 每个修改块只包含一个要修改的目标
4. 标记外的文字是给用户看的分析说明，标记内的是可直接应用的修改内容
5. 修改内容必须完整（替换整个目标段落），不能只给增量diff
6. chapter_outline 和 volume_outline 的修改内容要保留原 JSON 结构
7. 如果用户说"把第3章改成xxx"或"优化一下全书大纲"等明确修改意图时，你必须使用 MODIFY 标记给出可直接应用的修改

请用专业但友好的语气回答，先分析再给出修改方案。"""


@router.get("/copyright/report")
async def get_copyright_report(
    chapter_id: str,
    user: dict = Depends(get_current_user),
):
    """获取单章版权查重报告"""
    db = await get_mongodb()
    report = await db["copyright_records"].find_one({"chapter_id": chapter_id})
    if not report:
        raise HTTPException(status_code=404, detail="版权报告不存在")
    report["_id"] = str(report["_id"])
    return report


@router.get("/recall")
async def recall_memory(
    project_id: str,
    query: str,
    top_k: int = Query(5, ge=1, le=20),
    user: dict = Depends(get_current_user),
):
    """手动语义召回前文剧情（FAISS 向量检索）"""
    from ..services.embedding_service import embed_text
    from ..services.vector_service import VectorService

    vs = VectorService()
    query_vector = embed_text(query)
    results = vs.search(project_id, query_vector, top_k)
    return {"results": results}
