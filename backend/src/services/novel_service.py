"""小说项目服务：创建、查询、更新"""

import asyncio
from datetime import datetime, timezone

from bson import ObjectId

from ..core.database import get_mongodb
from ..utils.logger import get_logger

logger = get_logger(__name__)


async def create_project(user_id: str, data: dict) -> dict:
    """创建小说项目并生成大纲（或导入已有大纲）"""
    existing_outline = data.get("existing_outline")
    logger.info(f"开始创建项目: user_id={user_id}, title={data['title']}, has_existing_outline={bool(existing_outline)}")
    db = await get_mongodb()

    # 如果有已有大纲，先解析提取元数据
    outline_data = None
    if existing_outline:
        from ..agents.planner import parse_existing_outline
        try:
            logger.info("开始解析已有大纲...")
            outline_data = await parse_existing_outline(existing_outline)
            logger.info(f"大纲解析成功: chapter_count={outline_data.get('chapter_count')}, genre={outline_data.get('genre')}")
        except Exception as e:
            logger.error(f"大纲解析失败: {e}")
            return {"error": f"大纲解析失败: {str(e)}"}

    # 用解析的元数据覆盖项目字段
    genre = data["genre"] or (outline_data.get("genre", "") if outline_data else "")
    style = data["style"] or (outline_data.get("style", "") if outline_data else "")
    chapter_count = outline_data.get("chapter_count", data["chapter_count"]) if outline_data else data["chapter_count"]
    words_per_chapter = outline_data.get("words_per_chapter", data.get("words_per_chapter", 3000)) if outline_data else data.get("words_per_chapter", 3000)

    # 创建项目文档
    project = {
        "user_id": user_id,
        "title": data["title"],
        "genre": genre,
        "style": style,
        "world_setting": data["world_setting"],
        "chapter_count": chapter_count,
        "words_per_chapter": words_per_chapter,
        "status": "draft",
        "outline_status": "completed" if existing_outline else "pending",
        "current_volume": 1,
        "current_chapter": 0,
        "rewrite_count": 0,
        "copyright_threshold": 0.2,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db["novel_projects"].insert_one(project)
    project_id = str(result.inserted_id)
    logger.info(f"项目已创建: project_id={project_id}")

    # 创建角色（优先使用大纲提取的角色）
    characters = outline_data.get("characters", []) if outline_data else data.get("characters", [])
    logger.info(f"开始创建角色: project_id={project_id}, count={len(characters)}")
    for char_data in characters:
        await db["characters"].insert_one({
            "project_id": project_id,
            "name": char_data["name"],
            "role_type": char_data["role_type"],
            "personality": char_data["personality"],
            "background": char_data["background"],
            "relationships": char_data.get("relationships", []),
            "status_history": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
    logger.info(f"角色创建完成: project_id={project_id}")

    if existing_outline and outline_data:
        # 直接存储解析后的大纲
        outline_doc = {
            "project_id": project_id,
            "full_outline": outline_data.get("full_outline", ""),
            "volume_outlines": outline_data.get("volume_outlines", []),
            "chapter_outlines": outline_data.get("chapter_outlines", []),
            "version": 1,
            "created_at": datetime.now(timezone.utc),
        }
        await db["outlines"].insert_one(outline_doc)
        logger.info(f"已有大纲导入完成: project_id={project_id}")

        return {
            "project_id": project_id,
            "title": data["title"],
            "status": "draft",
            "outline_status": "completed",
            "message": "项目创建成功，大纲已导入",
        }
    else:
        # 后台异步生成大纲（不阻塞 API 响应）
        asyncio.create_task(_generate_outline_background(project_id, data))

        return {
            "project_id": project_id,
            "title": data["title"],
            "status": "draft",
            "outline_status": "pending",
            "message": "项目创建成功，大纲正在后台生成",
        }


async def _generate_outline_background(project_id: str, data: dict):
    """后台生成大纲（不阻塞 API 请求）"""
    from ..agents.planner import generate_outline

    logger.info(f"后台开始生成大纲: project_id={project_id}")
    try:
        await generate_outline(project_id, data)
        logger.info(f"后台大纲生成完成: project_id={project_id}")
    except Exception as e:
        logger.error(f"后台大纲生成失败: project_id={project_id}, error={e}")
        # 标记为失败状态
        db = await get_mongodb()
        await db["novel_projects"].update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {"outline_status": "failed"}},
        )


async def regenerate_outline(project_id: str, user_id: str) -> dict:
    """重新生成大纲"""
    db = await get_mongodb()

    project = await db["novel_projects"].find_one({
        "_id": ObjectId(project_id),
        "user_id": user_id,
    })
    if not project:
        return {"error": "项目不存在"}

    if project["status"] == "writing":
        return {"error": "项目正在创作中，无法重新生成大纲"}

    if project.get("outline_status") == "generating":
        return {"error": "大纲正在生成中，请稍候"}

    # 设置状态为 pending
    await db["novel_projects"].update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"outline_status": "pending"}},
    )

    # 获取角色信息
    cursor = db["characters"].find({"project_id": project_id})
    characters = []
    async for char in cursor:
        characters.append({
            "name": char["name"],
            "role_type": char["role_type"],
            "personality": char["personality"],
            "background": char["background"],
            "relationships": char.get("relationships", []),
        })

    data = {
        "title": project["title"],
        "genre": project["genre"],
        "style": project["style"],
        "world_setting": project["world_setting"],
        "chapter_count": project["chapter_count"],
        "characters": characters,
    }

    asyncio.create_task(_generate_outline_background(project_id, data))

    return {"project_id": project_id, "message": "大纲重新生成已启动"}


async def get_project_detail(project_id: str, user_id: str) -> dict | None:
    """获取项目详情含大纲和角色"""
    db = await get_mongodb()

    project = await db["novel_projects"].find_one({
        "_id": ObjectId(project_id),
        "user_id": user_id,
    })
    if not project:
        return None

    # 获取大纲
    outline = await db["outlines"].find_one({"project_id": project_id})

    # 获取角色
    cursor = db["characters"].find({"project_id": project_id})
    characters = []
    async for char in cursor:
        characters.append({
            "name": char["name"],
            "role_type": char["role_type"],
            "personality": char["personality"],
            "background": char["background"],
        })

    return {
        "project_id": str(project["_id"]),
        "title": project["title"],
        "genre": project["genre"],
        "style": project["style"],
        "world_setting": project["world_setting"],
        "chapter_count": project["chapter_count"],
        "words_per_chapter": project["words_per_chapter"],
        "status": project["status"],
        "outline_status": project.get("outline_status", "completed"),
        "current_chapter": project.get("current_chapter", 0),
        "outline": {
            "full_outline": outline["full_outline"] if outline else "",
            "volume_outlines": outline.get("volume_outlines", []) if outline else [],
            "chapter_outlines": outline.get("chapter_outlines", []) if outline else [],
        },
        "characters": characters,
        "created_at": project["created_at"].isoformat(),
    }


async def update_project(project_id: str, user_id: str, data: dict) -> dict | None:
    """更新项目设定"""

    logger.info(f"开始更新项目: project_id={project_id}, user_id={user_id}, fields={list(data.keys())}")
    db = await get_mongodb()

    project = await db["novel_projects"].find_one({
        "_id": ObjectId(project_id),
        "user_id": user_id,
    })
    if not project:
        logger.warning(f"项目不存在: project_id={project_id}")
        return None

    if project["status"] == "writing":
        logger.warning(f"项目正在创作中，不允许修改: project_id={project_id}")
        return {"error": "项目正在创作中，不允许修改"}

    update_fields = {}
    if data.get("world_setting"):
        update_fields["world_setting"] = data["world_setting"]
    if data.get("style"):
        update_fields["style"] = data["style"]
    if data.get("copyright_threshold") is not None:
        update_fields["copyright_threshold"] = data["copyright_threshold"]

    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        await db["novel_projects"].update_one(
            {"_id": ObjectId(project_id)},
            {"$set": update_fields},
        )
        logger.info(f"项目字段已更新: project_id={project_id}, fields={list(update_fields.keys())}")

    # 如果更新了角色，重新创建
    if data.get("characters"):
        characters = data["characters"]
        logger.info(f"重新创建角色: project_id={project_id}, count={len(characters)}")
        await db["characters"].delete_many({"project_id": project_id})
        for char_data in characters:
            await db["characters"].insert_one({
                "project_id": project_id,
                "name": char_data["name"],
                "role_type": char_data["role_type"],
                "personality": char_data["personality"],
                "background": char_data["background"],
                "relationships": char_data.get("relationships", []),
                "status_history": [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
        logger.info(f"角色重新创建完成: project_id={project_id}")

    # 如果世界观或角色有变化，后台重新生成大纲
    if data.get("world_setting") or data.get("characters"):
        logger.info(f"后台重新生成大纲: project_id={project_id}")
        asyncio.create_task(_generate_outline_background(project_id, {
            "title": project["title"],
            "genre": project["genre"],
            "style": data.get("style", project["style"]),
            "world_setting": data.get("world_setting", project["world_setting"]),
            "chapter_count": project["chapter_count"],
            "characters": data.get("characters", []),
        }))

    return {"project_id": project_id, "message": "项目设定已更新"}


async def delete_project(project_id: str, user_id: str) -> dict | None:
    """删除小说项目及其关联数据"""
    logger.info(f"开始删除项目: project_id={project_id}, user_id={user_id}")
    db = await get_mongodb()

    project = await db["novel_projects"].find_one({
        "_id": ObjectId(project_id),
        "user_id": user_id,
    })
    if not project:
        logger.warning(f"项目不存在: project_id={project_id}")
        return None

    if project["status"] == "writing":
        logger.warning(f"项目正在创作中，不允许删除: project_id={project_id}")
        return {"error": "项目正在创作中，请先暂停后再删除"}

    # 删除关联数据
    logger.info(f"删除关联数据: project_id={project_id}")
    await db["characters"].delete_many({"project_id": project_id})
    await db["outlines"].delete_many({"project_id": project_id})
    await db["chapters"].delete_many({"project_id": project_id})
    await db["copyright_records"].delete_many({"project_id": project_id})

    # 删除项目
    await db["novel_projects"].delete_one({"_id": ObjectId(project_id)})

    logger.info(f"项目已删除: project_id={project_id}")
    return {"project_id": project_id, "message": "项目已删除"}
