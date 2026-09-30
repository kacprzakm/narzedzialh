from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from api.core.config import get_settings

PROTECTED_PREFIX = "/api/"


def _client_ip(request: Request, trusted_hops: int) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        chain = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        if chain:
            idx = min(trusted_hops, len(chain))
            return chain[-idx]
    return request.client.host if request.client else "unknown"


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        settings = get_settings()
        self.limit = settings.rate_limit_requests
        self.window = settings.rate_limit_window
        self.trusted_hops = settings.trusted_proxy_hops

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(PROTECTED_PREFIX):
            return await call_next(request)

        redis = getattr(request.app.state, "redis", None)
        if redis is not None:
            ip = _client_ip(request, self.trusted_hops)
            key = f"rl:{ip}"
            try:
                count = await redis.incr(key)
                if count == 1:
                    await redis.expire(key, self.window)
                if count > self.limit:
                    ttl = await redis.ttl(key)
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Zbyt wiele żądań, spróbuj ponownie później"},
                        headers={"Retry-After": str(max(ttl, 1))},
                    )
            except Exception:
                pass

        return await call_next(request)
