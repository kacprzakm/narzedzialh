from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from api.core.config import get_settings

PROTECTED_PREFIX = "/api/"


def _origin_matches(value: str, allowed: set[str]) -> bool:
    if not value:
        return False
    parts = urlsplit(value)
    origin = f"{parts.scheme}://{parts.netloc}"
    return origin in allowed


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
        self.allowed_origins = set(settings.allowed_origins)
        self.enforce_origin = "*" not in self.allowed_origins
        self.limit = settings.rate_limit_requests
        self.window = settings.rate_limit_window
        self.trusted_hops = settings.trusted_proxy_hops

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(PROTECTED_PREFIX):
            return await call_next(request)

        if self.enforce_origin:
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            ok = False
            if origin is not None:
                ok = _origin_matches(origin, self.allowed_origins)
            elif referer is not None:
                ok = _origin_matches(referer, self.allowed_origins)
            if not ok:
                return JSONResponse(status_code=403, content={"detail": "Niedozwolone źródło żądania"})

        redis = getattr(request.app.state, "redis", None)
        if self.enforce_origin and redis is not None:
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
