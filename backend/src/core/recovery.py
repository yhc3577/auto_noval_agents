"""异常恢复机制：服务启动时检查未完成项目、自动恢复进度"""

from datetime import datetime, timezone

from bson import ObjectId

from ..core.database import get_mongodb
from ..utils.logger import get_logger
from ..services.cache_service import save_progress

logger = get_logger(__name__)


async def check_and_recover():
    """服务启动时检查未完成项目，恢复进度"""
    db = await get_mongodb()

    # 查找所有状态为 writing 的项目（可能是服务异常中断）
    cursor = db["novel_projects"].find({"status": "writing"})
    recovered = 0

    async for project in cursor:
        project_id = str(project["_id"])
        logger.info(f"发现未完成项目: {project['title']}，恢复为暂停状态")

        # 将状态恢复为 paused
        await db["novel_projects"].update_one(
            {"_id": project["_id"]},
            {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}},
        )

        # 清理卡在非终态的章节，重置为 draft 以便恢复后重新生成
        reset_result = await db["chapters"].update_many(
            {"project_id": project_id, "status": {"$nin": ["completed", "draft"]}},
            {"$set": {"status": "draft"}},
        )
        if reset_result.modified_count > 0:
            logger.info(f"项目 {project_id} 重置了 {reset_result.modified_count} 个卡住的章节")

        # 恢复进度信息
        current_chapter = project.get("current_chapter", 0)
        await save_progress(project_id, {
            "current_chapter": current_chapter,
            "total_chapters": project["chapter_count"],
            "progress": current_chapter / project["chapter_count"] * 100 if project["chapter_count"] > 0 else 0,
            "status": "paused",
            "chapter_status": "",
            "log": "服务恢复，创作已暂停",
        })

        recovered += 1

    if recovered > 0:
        logger.info(f"恢复了 {recovered} 个未完成项目")
