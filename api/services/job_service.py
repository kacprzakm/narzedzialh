import json
import secrets
import time

from api.core.config import get_settings
from api.core.redis import RedisClient
from api.models.job import JobResponse, JobResult, JobStatus


async def create_job(
    redis: RedisClient,
    label: str | None = None,
) -> JobResponse:
    settings = get_settings()

    job_id = secrets.token_urlsafe(12).replace("_", "-").lower()
    local_part = f"check-{job_id}"
    email = f"{local_part}@{settings.mail_domain}"

    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(
            f"job:{job_id}",
            mapping={
                "status": JobStatus.WAITING.value,
                "email": email,
                "label": label or "",
                "created_at": int(time.time()),
            },
        )
        pipe.expire(f"job:{job_id}", settings.job_ttl)
        pipe.set(f"rcpt:{local_part}", job_id, ex=settings.job_ttl)
        await pipe.execute()

    return JobResponse(
        job_id=job_id,
        email=email,
        status=JobStatus.WAITING,
        ttl_seconds=settings.job_ttl,
    )


async def get_job(redis: RedisClient, job_id: str) -> JobResult | None:
    data = await redis.hgetall(f"job:{job_id}")
    if not data:
        return None

    analysis = None
    if raw_result := data.get("result"):
        analysis = json.loads(raw_result)

    return JobResult(
        job_id=job_id,
        status=JobStatus(data["status"]),
        label=data.get("label") or None,
        email=data["email"],
        analysis=analysis,
    )
