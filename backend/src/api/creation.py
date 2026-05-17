"""创作控制接口：启动、暂停、进度查询"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..core.auth import get_current_user, get_current_user_flexible
from ..core.database import get_mongodb
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class StartRequest(BaseModel):
    project_id: str


class PauseRequest(BaseModel):
    project_id: str


@router.post("/start")
async def start_creation(
    req: StartRequest,
    user: dict = Depends(get_current_user),
):
    """启动或恢复6Agent全自动创作"""
    from ..services.creation_service import start_writing

    result = await start_writing(req.project_id, user["user_id"])
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/pause")
async def pause_creation(
    req: PauseRequest,
    user: dict = Depends(get_current_user),
):
    """暂停创作"""
    from ..services.creation_service import pause_writing

    result = await pause_writing(req.project_id, user["user_id"])
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/progress")
async def get_progress(
    project_id: str,
    token: str = Query(default=None),
    user: dict = Depends(get_current_user_flexible),
):
    """实时查询创作进度（SSE流式响应）"""

    async def event_generator():
        from ..services.cache_service import get_progress

        while True:
            progress = await get_progress(project_id)
            if progress:
                data = {
                    "project_id": project_id,
                    "current_chapter": int(progress.get("current_chapter", 0)),
                    "total_chapters": int(progress.get("total_chapters", 0)),
                    "progress": float(progress.get("progress", 0)),
                    "status": progress.get("status", "unknown"),
                    "chapter_status": progress.get("chapter_status", ""),
                    "log": progress.get("log", ""),
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                if data["status"] in ("completed", "paused"):
                    break
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/stream-content")
async def stream_content(
    project_id: str,
    token: str = Query(default=None),
    user: dict = Depends(get_current_user_flexible),
):
    """实时流式推送章节创作内容（SSE）"""

    async def event_generator():
        from ..services.cache_service import subscribe_stream

        async for message in subscribe_stream(project_id):
            yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
            if message.get("type") == "done":
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
