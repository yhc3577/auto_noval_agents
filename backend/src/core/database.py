"""数据库连接管理：MongoDB Motor 异步客户端、Redis 连接池"""

import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import settings

# MongoDB 客户端实例
_mongo_client: AsyncIOMotorClient | None = None
_redis_pool: aioredis.Redis | None = None


async def get_mongodb() -> AsyncIOMotorDatabase:
    """获取 MongoDB 数据库实例"""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(settings.mongodb_url)
    return _mongo_client[settings.mongodb_database]


async def get_redis() -> aioredis.Redis:
    """获取 Redis 连接实例"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
    return _redis_pool


async def close_database():
    """关闭所有数据库连接"""
    global _mongo_client, _redis_pool
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
