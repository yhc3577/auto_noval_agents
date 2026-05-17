"""导出接口：全书导出"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..core.auth import get_current_user
from ..core.database import get_mongodb
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/export")
async def export_novel(
    project_id: str,
    format: str = Query("txt", pattern="^(txt|markdown)$"),
    user: dict = Depends(get_current_user),
):
    """全书导出"""
    from bson import ObjectId

    db = await get_mongodb()

    # 验证项目归属
    project = await db["novel_projects"].find_one({
        "_id": ObjectId(project_id),
        "user_id": user["user_id"],
    })
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 获取所有已完成的章节
    cursor = db["chapters"].find({
        "project_id": project_id,
        "status": "completed",
    }).sort("chapter_number", 1)

    chapters = []
    async for chapter in cursor:
        chapters.append(chapter)

    if not chapters:
        raise HTTPException(status_code=400, detail="没有已完成的章节可导出")

    # 生成导出内容
    title = project["title"]
    if format == "txt":
        content = f"{title}\n{'=' * 40}\n\n"
        for ch in chapters:
            content += f"第{ch['chapter_number']}章 {ch['title']}\n"
            content += "-" * 30 + "\n"
            content += ch.get("content", "") + "\n\n"
        media_type = "text/plain"
        ext = "txt"
    else:
        content = f"# {title}\n\n"
        for ch in chapters:
            content += f"## 第{ch['chapter_number']}章 {ch['title']}\n\n"
            content += ch.get("content", "") + "\n\n"
        media_type = "text/markdown"
        ext = "md"

    logger.info(f"导出小说: {title}, 格式: {format}, 章节数: {len(chapters)}")

    # RFC 5987: 用 UTF-8 编码非 ASCII 文件名
    ascii_filename = f"novel.{ext}"
    utf8_filename = quote(f"{title}.{ext}")

    return Response(
        content=content.encode("utf-8"),
        media_type=f"{media_type}; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}"
        },
    )
