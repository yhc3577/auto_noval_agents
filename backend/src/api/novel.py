"""小说项目接口：创建、列表、详情、更新"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.auth import get_current_user
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
