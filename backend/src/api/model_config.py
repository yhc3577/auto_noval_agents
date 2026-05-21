"""模型配置接口：用户自定义 LLM 模型的 CRUD 管理"""

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.auth import get_current_user
from ..core.database import get_mongodb
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# 支持的 Provider 列表及其默认 base_url
PROVIDER_DEFAULTS = {
    "vllm": "http://localhost:8000/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "minimax": "https://api.minimax.chat/v1",
    "minimax2.7": "https://api.minimax.chat/v1",
    "openai": "https://api.openai.com/v1",
}


class CreateModelConfigRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    provider: str = Field(..., min_length=1, max_length=30)
    model: str = Field(..., min_length=1, max_length=100)
    api_key: str = Field(default="", max_length=200)
    base_url: str = Field(default="", max_length=300)
    max_tokens: int = Field(default=8192, ge=256, le=65536)


class UpdateModelConfigRequest(BaseModel):
    config_id: str
    name: str | None = Field(default=None, max_length=50)
    provider: str | None = Field(default=None, max_length=30)
    model: str | None = Field(default=None, max_length=100)
    api_key: str | None = Field(default=None, max_length=200)
    base_url: str | None = Field(default=None, max_length=300)
    max_tokens: int | None = Field(default=None, ge=256, le=65536)


class DeleteModelConfigRequest(BaseModel):
    config_id: str


class ActivateModelConfigRequest(BaseModel):
    config_id: str


class ModelConfigItem(BaseModel):
    config_id: str
    name: str
    provider: str
    model: str
    base_url: str
    api_key_masked: str
    is_active: bool
    max_tokens: int = 8192


class ModelConfigListResponse(BaseModel):
    configs: list[ModelConfigItem]
    active_config_id: str | None
    available_providers: list[dict]


def _mask_api_key(key: str) -> str:
    """遮蔽 API key，仅显示前4后4字符"""
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "****"
    return key[:4] + "****" + key[-4:]


@router.get("/list", response_model=ModelConfigListResponse)
async def list_model_configs(user: dict = Depends(get_current_user)):
    """获取当前用户的所有模型配置"""
    db = await get_mongodb()
    user_id = user["user_id"]

    configs_cursor = db["model_configs"].find({"user_id": user_id}).sort("created_at", -1)
    configs = []
    async for doc in configs_cursor:
        configs.append(doc)

    # 读取用户的活跃配置 ID
    user_doc = await db["users"].find_one({"_id": ObjectId(user_id)})
    active_id = user_doc.get("active_model_config_id") if user_doc else None

    items = []
    for c in configs:
        is_active = str(c["_id"]) == active_id
        items.append(ModelConfigItem(
            config_id=str(c["_id"]),
            name=c["name"],
            provider=c["provider"],
            model=c["model"],
            base_url=c.get("base_url", ""),
            api_key_masked=_mask_api_key(c.get("api_key", "")),
            is_active=is_active,
            max_tokens=c.get("max_tokens", 8192),
        ))

    available = [
        {"value": k, "label": k, "default_base_url": v}
        for k, v in PROVIDER_DEFAULTS.items()
    ]

    return ModelConfigListResponse(
        configs=items,
        active_config_id=active_id,
        available_providers=available,
    )


@router.post("/create", status_code=201)
async def create_model_config(req: CreateModelConfigRequest, user: dict = Depends(get_current_user)):
    """创建新的模型配置"""
    db = await get_mongodb()
    user_id = user["user_id"]

    if req.provider not in PROVIDER_DEFAULTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的 provider: {req.provider}，可选值: {', '.join(PROVIDER_DEFAULTS.keys())}",
        )

    base_url = req.base_url or PROVIDER_DEFAULTS.get(req.provider, "")

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "name": req.name,
        "provider": req.provider,
        "model": req.model,
        "api_key": req.api_key,
        "base_url": base_url,
        "max_tokens": req.max_tokens,
        "created_at": now,
        "updated_at": now,
    }
    result = await db["model_configs"].insert_one(doc)
    config_id = str(result.inserted_id)

    # 自动激活新创建的配置
    await db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"active_model_config_id": config_id}},
    )

    logger.info(f"用户 {user['username']} 创建并激活模型配置: {req.name} ({req.provider}/{req.model})")

    return {
        "config_id": config_id,
        "name": req.name,
        "provider": req.provider,
        "model": req.model,
        "base_url": base_url,
        "max_tokens": req.max_tokens,
        "api_key_masked": _mask_api_key(req.api_key),
    }


@router.put("/update")
async def update_model_config(req: UpdateModelConfigRequest, user: dict = Depends(get_current_user)):
    """更新模型配置"""
    db = await get_mongodb()
    user_id = user["user_id"]

    config = await db["model_configs"].find_one({
        "_id": ObjectId(req.config_id),
        "user_id": user_id,
    })
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")

    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.provider is not None:
        if req.provider not in PROVIDER_DEFAULTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的 provider: {req.provider}",
            )
        updates["provider"] = req.provider
    if req.model is not None:
        updates["model"] = req.model
    if req.api_key is not None:
        updates["api_key"] = req.api_key
    if req.base_url is not None:
        updates["base_url"] = req.base_url
    if req.max_tokens is not None:
        updates["max_tokens"] = req.max_tokens

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        await db["model_configs"].update_one(
            {"_id": ObjectId(req.config_id)},
            {"$set": updates},
        )
        logger.info(f"用户 {user['username']} 更新模型配置: {config['name']}")

    return {"config_id": req.config_id, "message": "配置已更新"}


@router.delete("/delete")
async def delete_model_config(req: DeleteModelConfigRequest, user: dict = Depends(get_current_user)):
    """删除模型配置"""
    db = await get_mongodb()
    user_id = user["user_id"]

    config = await db["model_configs"].find_one({
        "_id": ObjectId(req.config_id),
        "user_id": user_id,
    })
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")

    await db["model_configs"].delete_one({"_id": ObjectId(req.config_id)})

    # 如果删除的是活跃配置，清除用户的活跃配置引用
    user_doc = await db["users"].find_one({"_id": ObjectId(user_id)})
    if user_doc and user_doc.get("active_model_config_id") == req.config_id:
        await db["users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"active_model_config_id": None}},
        )

    logger.info(f"用户 {user['username']} 删除模型配置: {config['name']}")
    return {"config_id": req.config_id, "message": "配置已删除"}


@router.post("/activate")
async def activate_model_config(req: ActivateModelConfigRequest, user: dict = Depends(get_current_user)):
    """设置模型配置为活跃"""
    db = await get_mongodb()
    user_id = user["user_id"]

    config = await db["model_configs"].find_one({
        "_id": ObjectId(req.config_id),
        "user_id": user_id,
    })
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")

    await db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"active_model_config_id": req.config_id}},
    )

    logger.info(f"用户 {user['username']} 激活模型配置: {config['name']} ({config['provider']}/{config['model']})")
    return {"config_id": req.config_id, "message": "配置已激活"}
