"""Prompt 模板管理接口：用户自定义 Agent prompt 的查询、更新、重置"""

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.auth import get_current_user
from ..core.database import get_mongodb
from ..services.prompt_service import (
    list_defaults_by_agent,
    list_prompts,
    reset_all_prompts,
    reset_prompt,
    save_prompt,
)
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


class UpdatePromptRequest(BaseModel):
    prompt_key: str = Field(..., min_length=1, max_length=100)
    template_content: str = Field(..., min_length=1)


class ResetPromptRequest(BaseModel):
    prompt_key: str = Field(..., min_length=1, max_length=100)


class PromptItem(BaseModel):
    prompt_key: str
    name: str
    description: str
    agent_type: str
    agent_label: str
    prompt_type: str
    variables: list[str]
    default_content: str
    current_content: str
    is_customized: bool
    version: int
    updated_at: str | None


class AgentGroup(BaseModel):
    agent_type: str
    agent_label: str
    prompts: list[dict]


@router.get("/list")
async def get_prompt_list(
    agent_type: str | None = None,
    user: dict = Depends(get_current_user),
):
    """列出所有 prompt 模板及当前状态（默认值 + 用户覆盖状态）"""
    try:
        items = await list_prompts(user_id=user["user_id"], agent_type=agent_type)
        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.error(f"获取 Prompt 列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取 Prompt 列表失败")


@router.get("/defaults")
async def get_prompt_defaults(user: dict = Depends(get_current_user)):
    """获取按 agent_type 分组的默认 prompt 定义"""
    try:
        groups = await list_defaults_by_agent()
        return {"agents": groups}
    except Exception as e:
        logger.error(f"获取默认 Prompt 定义失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取默认 Prompt 定义失败")


@router.put("/update")
async def update_prompt(
    req: UpdatePromptRequest,
    user: dict = Depends(get_current_user),
):
    """更新单个 prompt 模板（创建或更新用户自定义覆盖）"""
    try:
        result = await save_prompt(
            prompt_key=req.prompt_key,
            template_content=req.template_content,
            user_id=user["user_id"],
        )
        return result
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知的 prompt_key: {req.prompt_key}",
        )
    except Exception as e:
        logger.error(f"更新 Prompt 模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新 Prompt 模板失败")


@router.post("/reset")
async def reset_prompt_to_default(
    req: ResetPromptRequest,
    user: dict = Depends(get_current_user),
):
    """重置单个 prompt 为默认值"""
    try:
        result = await reset_prompt(
            prompt_key=req.prompt_key,
            user_id=user["user_id"],
        )
        return result
    except Exception as e:
        logger.error(f"重置 Prompt 模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="重置 Prompt 模板失败")


@router.post("/reset-all")
async def reset_all_prompts_to_default(
    user: dict = Depends(get_current_user),
):
    """重置所有 prompt 为默认值"""
    try:
        result = await reset_all_prompts(user_id=user["user_id"])
        return result
    except Exception as e:
        logger.error(f"重置所有 Prompt 模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="重置所有 Prompt 模板失败")
