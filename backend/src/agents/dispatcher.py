"""调度Agent：初始化状态、调度其他Agent、异常处理、重写防护"""

from datetime import datetime, timezone

from bson import ObjectId

from ..core.database import get_mongodb
from ..services.cache_service import save_progress
from ..utils.logger import get_logger

logger = get_logger(__name__)


async def dispatch_chapter(project_id: str, chapter_number: int) -> dict:
    """调度单章创作流程"""
    db = await get_mongodb()

    # 获取项目配置
    project = await db["novel_projects"].find_one({"_id": ObjectId(project_id)})
    if not project:
        return {"error": "项目不存在"}

    # 检查暂停状态
    if project["status"] != "writing":
        return {"status": "paused"}

    # 检查重写次数
    rewrite_count = project.get("rewrite_count", 0)
    if rewrite_count >= 3:
        logger.warning(f"章节 {chapter_number} 重写次数超限，标记人工介入")
        await _mark_chapter_manual_review(project_id, chapter_number)
        return {"status": "manual_review", "chapter": chapter_number}

    # 获取章节细纲和标题
    outline = await db["outlines"].find_one({"project_id": project_id})
    chapter_outline = ""
    chapter_title = f"第{chapter_number}章"
    if outline:
        for ch in outline.get("chapter_outlines", []):
            if ch["chapter_number"] == chapter_number:
                chapter_outline = ch["content"]
                chapter_title = ch.get("title", chapter_title)
                break

    # 获取角色信息
    cursor = db["characters"].find({"project_id": project_id})
    characters = []
    async for char in cursor:
        characters.append(
            f"- {char['name']}（{char['role_type']}）：{char['personality']}"
        )
    char_text = "\n".join(characters)

    # 获取全局摘要
    from ..services.cache_service import get_summary

    global_summary = await get_summary(project_id)

    # 更新进度
    await save_progress(project_id, {
        "current_chapter": chapter_number,
        "total_chapters": project["chapter_count"],
        "progress": (chapter_number - 1) / project["chapter_count"] * 100,
        "status": "writing",
        "chapter_status": "writing",
        "log": f"正在创作第{chapter_number}章...",
    })

    return {
        "status": "ready",
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "chapter_outline": chapter_outline,
        "character_info": char_text,
        "global_summary": global_summary,
        "world_setting": project["world_setting"],
        "style": project["style"],
        "words_per_chapter": project["words_per_chapter"],
        "copyright_threshold": project.get("copyright_threshold", 0.2),
    }


async def _mark_chapter_manual_review(project_id: str, chapter_number: int):
    """标记章节需要人工介入"""
    db = await get_mongodb()

    await db["chapters"].update_one(
        {"project_id": project_id, "chapter_number": chapter_number},
        {
            "$set": {
                "status": "manual_review",
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    # 重置重写次数，准备下一章
    await db["novel_projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"rewrite_count": 0}},
    )
