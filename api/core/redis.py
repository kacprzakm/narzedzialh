from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Request

RedisClient = aioredis.Redis


async def get_redis(request: Request) -> AsyncGenerator[RedisClient, None]:
    yield request.app.state.redis
