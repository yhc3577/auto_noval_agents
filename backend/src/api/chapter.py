"""章节管理接口：目录、详情、编辑"""

import re

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.auth import get_current_user
from ..core.database import get_mongodb
from ..utils.logger import get_logger

logger = get_logger(__name__)

_THINK_PATTERN = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)

# 匹配 "——第X章 完——" 及其后的全部元数据
_CHAPTER_END_PATTERN = re.compile(
    r"\n+\*{0,2}[-—]{1,3}\s*第\d+章\s*[完终]\s*[-—]{1,3}\*{0,2}\s*\n+.*$",
    re.DOTALL,
)


def _strip_meta(text: str) -> str:
    """移除 LLM 输出中的思考过程标签和章节末尾元数据总结"""
    cleaned = _THINK_PATTERN.sub("", text).strip()
    result = _CHAPTER_END_PATTERN.sub("", cleaned)
    return result.strip()


# 向后兼容
_strip_thinking = _strip_meta

router = APIRouter()


class EditChapterRequest(BaseModel):
    chapter_id: str
    content: str


class ChapterIdRequest(BaseModel):
    chapter_id: str


class PolishRequest(BaseModel):
    chapter_id: str
    content: str
    instruction: str = ""


@router.get("/list")
async def list_chapters(
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """获取章节目录"""
    db = await get_mongodb()
    chapters = db["chapters"]

    skip = (page - 1) * page_size
    cursor = chapters.find({"project_id": project_id}).sort("chapter_number", 1).skip(skip).limit(page_size)
    items = []
    async for doc in cursor:
        items.append({
            "chapter_id": str(doc["_id"]),
            "chapter_number": doc["chapter_number"],
            "volume_number": doc.get("volume_number", 1),
            "title": doc["title"],
            "status": doc["status"],
            "word_count": doc.get("word_count", 0),
            "updated_at": doc["updated_at"].isoformat(),
        })

    total = await chapters.count_documents({"project_id": project_id})
    return {"total": total, "items": items}


@router.get("/detail")
async def get_chapter_detail(
    chapter_id: str,
    user: dict = Depends(get_current_user),
):
    """查看章节正文、摘要、审核意见、版权报告"""
    from bson import ObjectId

    db = await get_mongodb()

    chapter = await db["chapters"].find_one({"_id": ObjectId(chapter_id)})
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 获取审核记录
    audit_cursor = db["audit_records"].find({"chapter_id": chapter_id})
    audit_records = []
    async for record in audit_cursor:
        audit_records.append({
            "audit_type": record["audit_type"],
            "result": record["result"],
            "score": record.get("score"),
            "opinion": record["opinion"],
            "created_at": record["created_at"].isoformat(),
        })

    # 获取版权报告
    copyright_doc = await db["copyright_records"].find_one({"chapter_id": chapter_id})
    copyright_report = None
    if copyright_doc:
        copyright_report = {
            "originality_score": copyright_doc["originality_score"],
            "max_similarity": copyright_doc["max_similarity"],
            "passed": copyright_doc["passed"],
            "similar_entries": copyright_doc.get("similar_entries", []),
        }

    # 获取编辑历史
    edit_cursor = db["edit_history"].find({"chapter_id": chapter_id}).sort("created_at", -1)
    edit_history = []
    async for edit in edit_cursor:
        edit_history.append({
            "edited_at": edit["created_at"].isoformat(),
            "summary": f"字数变化: {edit.get('word_count_change', 'N/A')}",
        })

    raw_content = chapter.get("content", "")
    raw_summary = chapter.get("summary", "")
    content = _strip_thinking(raw_content)
    summary = _strip_thinking(raw_summary)

    # 如果过滤后内容有变化，同步更新数据库
    if content != raw_content.strip():
        await db["chapters"].update_one(
            {"_id": ObjectId(chapter_id)},
            {"$set": {"content": content, "word_count": len(content)}},
        )
    if summary != raw_summary.strip():
        await db["chapters"].update_one(
            {"_id": ObjectId(chapter_id)},
            {"$set": {"summary": summary}},
        )

    return {
        "chapter_id": str(chapter["_id"]),
        "chapter_number": chapter["chapter_number"],
        "title": chapter["title"],
        "outline": chapter.get("outline", ""),
        "content": content,
        "summary": summary,
        "word_count": len(content),
        "status": chapter["status"],
        "audit_records": audit_records,
        "copyright_report": copyright_report,
        "edit_history": edit_history,
    }


@router.put("/edit")
async def edit_chapter(
    req: EditChapterRequest,
    user: dict = Depends(get_current_user),
):
    """人工编辑章节内容"""
    from datetime import datetime, timezone

    from bson import ObjectId

    db = await get_mongodb()

    chapter = await db["chapters"].find_one({"_id": ObjectId(req.chapter_id)})
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    if chapter["status"] in ("writing", "auditing", "copyright_checking"):
        raise HTTPException(status_code=400, detail="当前章节状态不允许编辑")

    # 记录编辑历史
    old_content = chapter.get("content", "")
    await db["edit_history"].insert_one({
        "chapter_id": req.chapter_id,
        "user_id": user["user_id"],
        "content_before": old_content[:500],  # 存储前500字作为摘要
        "content_after": req.content[:500],
        "word_count_change": len(req.content) - len(old_content),
        "created_at": datetime.now(timezone.utc),
    })

    # 更新章节内容
    await db["chapters"].update_one(
        {"_id": ObjectId(req.chapter_id)},
        {
            "$set": {
                "content": req.content,
                "word_count": len(req.content),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    return {
        "chapter_id": req.chapter_id,
        "word_count": len(req.content),
        "message": "章节内容已更新",
    }


@router.delete("/delete")
async def delete_chapter(
    chapter_id: str,
    user: dict = Depends(get_current_user),
):
    """删除章节"""
    from bson import ObjectId

    db = await get_mongodb()

    chapter = await db["chapters"].find_one({"_id": ObjectId(chapter_id)})
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    project_id = chapter["project_id"]
    chapter_number = chapter["chapter_number"]

    # 检查项目是否正在创作中
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    if project and project.get("status") == "writing":
        raise HTTPException(status_code=400, detail="项目正在创作中，请先暂停后再删除章节")

    # 只允许删除最新的一章（章节号最大的）
    last_chapter = await db["chapters"].find_one(
        {"project_id": project_id},
        sort=[("chapter_number", -1)],
    )
    if last_chapter and chapter_number != last_chapter["chapter_number"]:
        raise HTTPException(status_code=400, detail="只能删除最新的一章")

    # 删除章节及相关数据
    await db["chapters"].delete_one({"_id": ObjectId(chapter_id)})
    await db["audit_records"].delete_many({"chapter_id": chapter_id})
    await db["copyright_records"].delete_many({"chapter_id": chapter_id})
    await db["edit_history"].delete_many({"chapter_id": chapter_id})

    # 读取当前创作进度，计算删除后的正确值
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    current = project.get("current_chapter", 0)
    new_chapter_count = project.get("chapter_count", 1) - 1

    # 计算新的 current_chapter：
    # - 删除的章节在当前进度之前 → 进度前移一章
    # - 删除的章节在当前进度之后 → 进度不变
    # - 不允许超过总章节数（全部删完时归零）
    if chapter_number <= current:
        new_current = max(0, current - 1)
    else:
        new_current = current
    # 兜底：确保 current_chapter 不超过 chapter_count
    new_current = min(new_current, new_chapter_count)

    await db["novel_projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {
            "chapter_count": new_chapter_count,
            "current_chapter": new_current,
        }},
    )

    # 重新编号后续章节
    await db["chapters"].update_many(
        {"project_id": project_id, "chapter_number": {"$gt": chapter_number}},
        {"$inc": {"chapter_number": -1}},
    )

    # 删除对应的章节记忆
    await db["chapter_memory"].delete_one({
        "project_id": project_id,
        "chapter_number": chapter_number,
    })

    # 重新编号后续章节记忆（与章节保持同步）
    await db["chapter_memory"].update_many(
        {"project_id": project_id, "chapter_number": {"$gt": chapter_number}},
        {"$inc": {"chapter_number": -1}},
    )

    # 清理 FAISS 索引中已删除章节的向量（标记重建）
    try:
        from ..services.vector_service import VectorService
        vs = VectorService()
        project_dir = vs._get_project_dir(project_id)
        mapping_file = project_dir / "mapping.json"
        if mapping_file.exists():
            import json
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            # 删除已删章节对应的条目，并更新重编号后的章节号
            new_mapping = []
            for entry in mapping:
                entry_cn = entry.get("chapter_number", 0)
                if entry_cn == chapter_number:
                    continue  # 删除
                if entry_cn > chapter_number:
                    entry["chapter_number"] = entry_cn - 1  # 重编号
                new_mapping.append(entry)
            with open(mapping_file, "w", encoding="utf-8") as f:
                json.dump(new_mapping, f, ensure_ascii=False)
            logger.info(f"FAISS 索引已同步: 删除 chapter={chapter_number}, 当前 {len(new_mapping)} 条向量")
    except Exception as e:
        logger.warning(f"FAISS 索引同步失败（不影响删除流程）: {e}")

    # 同步进度到 Redis，确保前端显示正确
    from ..services.cache_service import save_progress

    await save_progress(project_id, {
        "current_chapter": new_current,
        "total_chapters": new_chapter_count,
        "progress": (new_current / new_chapter_count * 100) if new_chapter_count > 0 else 0,
        "status": project.get("status", "paused"),
        "chapter_status": "",
        "log": f"已删除第{chapter_number}章",
    })

    logger.info(f"章节已删除: chapter_id={chapter_id}, project_id={project_id}")
    return {"message": "章节已删除"}


@router.post("/review")
async def review_chapter(
    req: ChapterIdRequest,
    user: dict = Depends(get_current_user),
):
    """AI审核章节：给出专业意见"""
    from bson import ObjectId

    from ..agents.writer import _strip_meta as _strip_thinking
    from ..core.llm import call_llm

    db = await get_mongodb()

    chapter = await db["chapters"].find_one({"_id": ObjectId(req.chapter_id)})
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    content = chapter.get("content", "")
    outline = chapter.get("outline", "")

    system_prompt = """你是一位资深小说编辑。请从以下维度审核章节内容，给出专业意见：
1. 剧情贴合度：是否符合大纲要求
2. 人设一致性：人物言行是否符合设定
3. 文笔质量：语句流畅度、节奏感、描写水准
4. 逻辑漏洞：是否有前后矛盾或不合理之处
5. 爽点/钩子：是否有效设置读者期待

请以结构化方式输出，每个维度给出评分(1-10)和具体意见，最后给出总体评价和修改建议。"""

    user_prompt = f"""章节细纲：
{outline}

章节正文：
{content}

请进行专业审核。"""

    try:
        result = await call_llm(system_prompt, user_prompt)
        result = _strip_thinking(result)

        # 持久化审核记录
        from datetime import datetime, timezone

        await db["audit_records"].insert_one({
            "chapter_id": req.chapter_id,
            "project_id": chapter["project_id"],
            "audit_type": "human_review",
            "result": "review",
            "score": None,
            "opinion": result,
            "created_at": datetime.now(timezone.utc),
        })

        return {"review": result}
    except Exception as e:
        logger.error(f"AI审核失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI审核失败")


@router.post("/polish")
async def polish_chapter(
    req: PolishRequest,
    user: dict = Depends(get_current_user),
):
    """AI润色章节：根据意见优化内容"""
    from ..agents.writer import _strip_meta as _strip_thinking
    from ..core.llm import call_llm

    db = await get_mongodb()

    chapter = await db["chapters"].find_one({"_id": ObjectId(req.chapter_id)})
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    outline = chapter.get("outline", "")

    system_prompt = """你是一位专业小说润色编辑。请根据用户的指示对章节内容进行润色优化。

要求：
- 保持原文的剧情走向和核心情节不变
- 提升文笔质量，优化语句表达
- 增强画面感和情感张力
- 保持人物对话的个性化特征
- 如果用户给出了具体修改意见，优先按照意见修改
- 直接输出润色后的完整正文，不要加任何说明或解释"""

    instruction_part = f"\n用户的修改意见：{req.instruction}" if req.instruction else ""

    user_prompt = f"""章节细纲：
{outline}

原文内容：
{req.content}
{instruction_part}

请润色后输出完整正文。"""

    try:
        result = await call_llm(system_prompt, user_prompt)
        result = _strip_thinking(result)
        return {"content": result, "word_count": len(result)}
    except Exception as e:
        logger.error(f"AI润色失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="AI润色失败")
