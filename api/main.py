from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI

from api.core.config import get_settings
from api.core.security import SecurityMiddleware
from api.routers import dns, jobs, ssl


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    pool = aioredis.ConnectionPool.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )
    redis = aioredis.Redis(connection_pool=pool)

    try:
        await redis.ping()
        app.state.redis = redis
        yield
    finally:
        await redis.aclose()
        await pool.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
    title="narzedzia.lh.pl",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    )

    app.add_middleware(SecurityMiddleware)

    app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["mail-tester"])
    app.include_router(ssl.router, prefix="/api/v1/ssl", tags=["ssl-checker"])
    app.include_router(dns.router, prefix="/api/v1/dns", tags=["dns-checker"])

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
