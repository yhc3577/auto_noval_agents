"""Redis 缓存服务：状态快照、分布式锁、进度缓存、记忆管理"""

import json
from datetime import datetime, timezone

import redis.asyncio as aioredis

from ..core.database import get_mongodb, get_redis


async def save_state(project_id: str, state: dict):
    """保存 LangGraph State 快照到 Redis"""
    redis = await get_redis()
    key = f"novel:{project_id}:state"
    await redis.set(key, json.dumps(state, ensure_ascii=False))


async def load_state(project_id: str) -> dict | None:
    """从 Redis 加载 LangGraph State 快照"""
    redis = await get_redis()
    key = f"novel:{project_id}:state"
    data = await redis.get(key)
    if data:
        return json.loads(data)
    return None


async def save_progress(project_id: str, progress: dict):
    """保存创作进度到 Redis"""
    redis = await get_redis()
    key = f"novel:{project_id}:progress"
    await redis.hset(key, mapping={k: str(v) for k, v in progress.items()})


async def get_progress(project_id: str) -> dict:
    """获取创作进度"""
    redis = await get_redis()
    key = f"novel:{project_id}:progress"
    return await redis.hgetall(key)


async def acquire_lock(project_id: str, timeout: int = 30) -> bool:
    """获取项目分布式锁，防止并发创作"""
    redis = await get_redis()
    key = f"novel:{project_id}:lock"
    return await redis.set(key, "1", nx=True, ex=timeout)


async def release_lock(project_id: str):
    """释放项目分布式锁"""
    redis = await get_redis()
    key = f"novel:{project_id}:lock"
    await redis.delete(key)


async def refresh_lock(project_id: str, timeout: int = 30):
    """刷新项目分布式锁的过期时间"""
    redis = await get_redis()
    key = f"novel:{project_id}:lock"
    await redis.expire(key, timeout)


async def save_summary(project_id: str, summary: str):
    """保存全局滚动摘要（Redis + MongoDB 双写）"""
    # 写入 Redis（快速读取）
    redis = await get_redis()
    key = f"novel:{project_id}:summary"
    await redis.set(key, summary)

    # 写入 MongoDB（持久化备份）
    db = await get_mongodb()
    await db["project_memory"].update_one(
        {"project_id": project_id, "type": "global_summary"},
        {
            "$set": {
                "content": summary,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )


async def get_summary(project_id: str) -> str:
    """获取全局滚动摘要（优先 Redis，fallback MongoDB）"""
    # 先从 Redis 读取
    redis = await get_redis()
    key = f"novel:{project_id}:summary"
    result = await redis.get(key)
    if result:
        return result

    # Redis 没有，从 MongoDB 恢复
    db = await get_mongodb()
    doc = await db["project_memory"].find_one({
        "project_id": project_id,
        "type": "global_summary",
    })
    if doc:
        # 恢复到 Redis
        await redis.set(key, doc["content"])
        return doc["content"]

    return ""


async def save_chapter_memory(
    project_id: str,
    chapter_number: int,
    chapter_summary: str,
    key_events: list[str],
    character_changes: list[str] | None = None,
    foreshadowing: list[str] | None = None,
):
    """保存章节记忆到 MongoDB（用于记忆检索和向量检索）"""
    db = await get_mongodb()
    doc = {
        "project_id": project_id,
        "chapter_number": chapter_number,
        "summary": chapter_summary,
        "key_events": key_events,
        "character_changes": character_changes or [],
        "foreshadowing": foreshadowing or [],
        "updated_at": datetime.now(timezone.utc),
    }
    await db["chapter_memory"].update_one(
        {"project_id": project_id, "chapter_number": chapter_number},
        {"$set": doc},
        upsert=True,
    )


async def get_chapter_memories(project_id: str, limit: int = 10) -> list[dict]:
    """获取最近 N 章的记忆"""
    db = await get_mongodb()
    cursor = db["chapter_memory"].find(
        {"project_id": project_id}
    ).sort("chapter_number", -1).limit(limit)

    memories = []
    async for doc in cursor:
        memories.append({
            "chapter_number": doc["chapter_number"],
            "summary": doc.get("summary", ""),
            "key_events": doc.get("key_events", []),
            "character_changes": doc.get("character_changes", []),
            "foreshadowing": doc.get("foreshadowing", []),
        })
    return list(reversed(memories))  # 按章节顺序返回


async def search_related_memories(project_id: str, keywords: list[str], limit: int = 10) -> list[dict]:
    """根据关键词搜索相关章节记忆（同时搜索摘要、关键事件、人物变化、伏笔）"""
    db = await get_mongodb()

    regex_pattern = "|".join(keywords) if keywords else ""

    if regex_pattern:
        cursor = db["chapter_memory"].find({
            "project_id": project_id,
            "$or": [
                {"summary": {"$regex": regex_pattern, "$options": "i"}},
                {"key_events": {"$regex": regex_pattern, "$options": "i"}},
                {"character_changes": {"$regex": regex_pattern, "$options": "i"}},
                {"foreshadowing": {"$regex": regex_pattern, "$options": "i"}},
            ]
        }).sort("chapter_number", -1).limit(limit)
    else:
        cursor = db["chapter_memory"].find(
            {"project_id": project_id}
        ).sort("chapter_number", -1).limit(limit)

    memories = []
    async for doc in cursor:
        memories.append({
            "chapter_number": doc["chapter_number"],
            "summary": doc.get("summary", ""),
            "key_events": doc.get("key_events", []),
            "character_changes": doc.get("character_changes", []),
            "foreshadowing": doc.get("foreshadowing", []),
        })
    return memories


async def publish_stream_token(project_id: str, token: str):
    """发布一个流式 token 到项目的 Redis 频道"""
    redis = await get_redis()
    channel = f"novel:{project_id}:stream"
    await redis.publish(channel, json.dumps({"type": "token", "content": token}, ensure_ascii=False))


async def publish_stream_done(project_id: str):
    """发布流式完成信号"""
    redis = await get_redis()
    channel = f"novel:{project_id}:stream"
    await redis.publish(channel, json.dumps({"type": "done"}))


async def subscribe_stream(project_id: str):
    """订阅项目的流式 token 频道，返回 async generator"""
    redis = await get_redis()
    pubsub = redis.pubsub()
    channel = f"novel:{project_id}:stream"
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                yield data
                if data.get("type") == "done":
                    break
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
