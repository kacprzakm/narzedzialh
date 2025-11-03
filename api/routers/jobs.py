from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.core.redis import RedisClient, get_redis
from api.models.job import JobCreate, JobResponse, JobResult
from api.services import job_service

router = APIRouter()

RedisDep = Annotated[RedisClient, Depends(get_redis)]


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(body: JobCreate, redis: RedisDep) -> JobResponse:
    return await job_service.create_job(redis, label=body.label)


@router.get("/{job_id}", response_model=JobResult)
async def get_job(job_id: str, redis: RedisDep) -> JobResult:
    result = await job_service.get_job(redis, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return result
