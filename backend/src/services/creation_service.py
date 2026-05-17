"""创作服务：启动、暂停、断点续写"""

from datetime import datetime, timezone

from bson import ObjectId

from ..core.database import get_mongodb
from ..utils.logger import get_logger
from .cache_service import acquire_lock, release_lock, save_progress, save_state

logger = get_logger(__name__)


async def start_writing(project_id: str, user_id: str) -> dict:
    """启动全自动创作"""
    logger.info(f"启动创作请求: project_id={project_id}, user_id={user_id}")
    db = await get_mongodb()

    # 验证项目归属
    project = await db["novel_projects"].find_one({
        "_id": ObjectId(project_id),
        "user_id": user_id,
    })
    if not project:
        logger.warning(f"项目不存在: project_id={project_id}")
        return {"error": "项目不存在"}

    if project["status"] == "writing":
        logger.warning(f"项目已在创作中: project_id={project_id}")
        return {"error": "项目已在创作中"}

    if project["status"] == "completed":
        logger.warning(f"项目已完成: project_id={project_id}")
        return {"error": "项目已完成"}

    if project.get("chapter_count", 0) <= 0:
        logger.warning(f"项目章节数为0，无法启动创作: project_id={project_id}")
        return {"error": "请先设置章节数量"}

    # 获取分布式锁
    locked = await acquire_lock(project_id)
    if not locked:
        logger.warning(f"获取锁失败，已有创作任务在运行: project_id={project_id}")
        return {"error": "已有创作任务在运行"}

    logger.info(f"获取锁成功，开始创作: project_id={project_id}, title={project['title']}")

    # 更新项目状态
    await db["novel_projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"status": "writing", "updated_at": datetime.now(timezone.utc)}},
    )

    # 初始化进度
    start_chapter = project.get("current_chapter", 0) + 1
    await save_progress(project_id, {
        "current_chapter": start_chapter,
        "total_chapters": project["chapter_count"],
        "progress": 0,
        "status": "writing",
        "chapter_status": "pending",
        "log": "创作启动中...",
    })
    logger.info(f"进度已初始化: project_id={project_id}, start_chapter={start_chapter}, total_chapters={project['chapter_count']}")

    # 启动后台创作任务
    import asyncio

    asyncio.create_task(_run_writing_pipeline(project_id))
    logger.info(f"后台创作任务已启动: project_id={project_id}")

    return {
        "project_id": project_id,
        "status": "writing",
        "message": "创作已启动",
    }


async def pause_writing(project_id: str, user_id: str) -> dict:
    """暂停创作"""
    logger.info(f"暂停创作请求: project_id={project_id}, user_id={user_id}")
    db = await get_mongodb()

    project = await db["novel_projects"].find_one({
        "_id": ObjectId(project_id),
        "user_id": user_id,
    })
    if not project:
        logger.warning(f"项目不存在: project_id={project_id}")
        return {"error": "项目不存在"}

    if project["status"] != "writing":
        logger.warning(f"项目当前不在创作状态: project_id={project_id}, status={project['status']}")
        return {"error": "项目当前不在创作状态"}

    # 更新项目状态
    await db["novel_projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}},
    )

    # 更新进度
    current_chapter = project.get("current_chapter", 0)
    await save_progress(project_id, {
        "current_chapter": current_chapter,
        "total_chapters": project["chapter_count"],
        "progress": current_chapter / project["chapter_count"] * 100,
        "status": "paused",
        "chapter_status": "",
        "log": "创作已暂停",
    })

    await release_lock(project_id)
    logger.info(f"创作已暂停: project_id={project_id}, current_chapter={current_chapter}")

    return {
        "project_id": project_id,
        "status": "paused",
        "current_chapter": current_chapter,
        "message": "创作已暂停，进度已保存",
    }


async def _run_writing_pipeline(project_id: str):
    """运行6Agent创作流水线"""
    from ..agents.pipeline import run_pipeline

    try:
        await run_pipeline(project_id)
    except Exception as e:
        logger.error(f"创作流水线异常: {e}", exc_info=True)
        db = await get_mongodb()
        await db["novel_projects"].update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}},
        )
        await save_progress(project_id, {
            "status": "paused",
            "log": f"创作异常暂停: {str(e)}",
        })
    finally:
        await release_lock(project_id)
