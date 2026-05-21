"""Prompt 模板服务：获取模板、格式化、用户覆盖管理

核心逻辑：
- 用户覆盖存储在 MongoDB prompt_templates 集合
- 默认值在 agents/default_prompts.py
- 读取时优先 DB（user_id 匹配），未找到则用默认值
"""

from ..agents.default_prompts import (
    DEFAULT_PROMPTS,
    get_all_default_prompt_keys,
    get_default_prompt,
    get_default_prompts_by_agent,
)
from ..core.database import get_mongodb
from ..utils.logger import get_logger

logger = get_logger(__name__)

# 各 agent_type 的中文标签
AGENT_LABELS = {
    "writer": "写作Agent",
    "auditor": "审核Agent",
    "summarizer": "摘要Agent",
    "planner": "规划Agent",
    "pipeline": "流水线(Trim/Expand)",
    "chapter_api": "章节API",
}


async def get_prompt_template(prompt_key: str, user_id: str | None = None) -> str:
    """获取 prompt 模板文本。

    优先取用户自定义覆盖，否则返回默认值。
    """
    if user_id:
        db = await get_mongodb()
        doc = await db["prompt_templates"].find_one({
            "prompt_key": prompt_key,
            "user_id": user_id,
        })
        if doc:
            return doc["template_content"]

    default = get_default_prompt(prompt_key)
    if default:
        return default["template_content"]

    raise KeyError(f"未找到 prompt 模板: {prompt_key}")


async def format_prompt(
    prompt_key: str,
    user_id: str | None = None,
    **kwargs,
) -> str:
    """获取并格式化 prompt 模板。

    等同于 get_prompt_template() + str.format(**kwargs)。
    未提供的变量保留原样（{var_name}），不会报错。
    """
    template = await get_prompt_template(prompt_key, user_id)
    if kwargs:
        # 使用 format_map + defaultdict 安全格式化：
        # 未提供的变量保留原样，不会抛 KeyError
        from collections import defaultdict

        class _SafeDict(defaultdict):
            def __missing__(self, key):
                return "{" + key + "}"

        template = template.format_map(_SafeDict(str, **kwargs))
    return template


async def list_prompts(
    user_id: str | None = None,
    agent_type: str | None = None,
) -> list[dict]:
    """列出所有 prompt 模板及其当前状态。

    返回每个 prompt_key 的默认值和用户覆盖状态。
    """
    # 获取所有用户自定义
    user_overrides: dict[str, dict] = {}
    if user_id:
        db = await get_mongodb()
        cursor = db["prompt_templates"].find({"user_id": user_id})
        async for doc in cursor:
            user_overrides[doc["prompt_key"]] = doc

    result = []
    for key in get_all_default_prompt_keys():
        default = get_default_prompt(key)
        if not default:
            continue
        if agent_type and default.get("agent_type") != agent_type:
            continue

        override = user_overrides.get(key)
        item = {
            "prompt_key": key,
            "name": default["name"],
            "description": default["description"],
            "agent_type": default["agent_type"],
            "agent_label": AGENT_LABELS.get(default["agent_type"], default["agent_type"]),
            "prompt_type": default["prompt_type"],
            "variables": default["variables"],
            "default_content": default["template_content"],
            "current_content": override["template_content"] if override else default["template_content"],
            "is_customized": override is not None,
            "version": override["version"] if override else 0,
            "updated_at": override["updated_at"].isoformat() if override else None,
        }
        result.append(item)

    return result


async def list_defaults_by_agent() -> list[dict]:
    """获取按 agent_type 分组的默认 prompt 列表（用于前端首次展示）"""
    grouped = get_default_prompts_by_agent()
    result = []
    for agent_type, prompts in grouped.items():
        result.append({
            "agent_type": agent_type,
            "agent_label": AGENT_LABELS.get(agent_type, agent_type),
            "prompts": [
                {
                    "prompt_key": p["prompt_key"],
                    "name": p["name"],
                    "description": p["description"],
                    "prompt_type": p["prompt_type"],
                    "variables": p["variables"],
                }
                for p in prompts
            ],
        })
    return result


async def save_prompt(
    prompt_key: str,
    template_content: str,
    user_id: str,
) -> dict:
    """保存用户自定义 prompt 模板（创建或更新）"""
    from datetime import datetime, timezone

    default = get_default_prompt(prompt_key)
    if not default:
        raise KeyError(f"未知的 prompt_key: {prompt_key}")

    db = await get_mongodb()
    existing = await db["prompt_templates"].find_one({
        "prompt_key": prompt_key,
        "user_id": user_id,
    })

    if existing:
        new_version = existing.get("version", 1) + 1
        await db["prompt_templates"].update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "template_content": template_content,
                "version": new_version,
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        logger.info(f"Prompt 模板已更新: {prompt_key}, version={new_version}")
        return {"prompt_key": prompt_key, "version": new_version, "message": "模板已更新"}
    else:
        from ..models.prompt_template import PromptTemplate

        doc = PromptTemplate.new_doc(
            prompt_key=prompt_key,
            user_id=user_id,
            name=default["name"],
            description=default["description"],
            agent_type=default["agent_type"],
            prompt_type=default["prompt_type"],
            template_content=template_content,
            variables=default["variables"],
        )
        await db["prompt_templates"].insert_one(doc)
        logger.info(f"Prompt 模板已创建: {prompt_key}")
        return {"prompt_key": prompt_key, "version": 1, "message": "模板已创建"}


async def reset_prompt(prompt_key: str, user_id: str) -> dict:
    """重置单个 prompt 为默认值（删除用户覆盖记录）"""
    db = await get_mongodb()
    result = await db["prompt_templates"].delete_one({
        "prompt_key": prompt_key,
        "user_id": user_id,
    })
    if result.deleted_count > 0:
        logger.info(f"Prompt 模板已重置为默认值: {prompt_key}")
        return {"prompt_key": prompt_key, "message": "已重置为默认值"}
    return {"prompt_key": prompt_key, "message": "无需重置（未自定义）"}


async def reset_all_prompts(user_id: str) -> dict:
    """重置所有 prompt 为默认值"""
    db = await get_mongodb()
    result = await db["prompt_templates"].delete_many({"user_id": user_id})
    count = result.deleted_count
    logger.info(f"已重置 {count} 个 Prompt 模板为默认值")
    return {"reset_count": count, "message": f"已重置 {count} 个模板为默认值"}
