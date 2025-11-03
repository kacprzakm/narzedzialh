import enum
from typing import Any

from pydantic import BaseModel


class JobStatus(enum.StrEnum):
    WAITING = "waiting"
    COMPLETED = "completed"
    EXPIRED = "expired"


class JobCreate(BaseModel):
    label: str | None = None


class JobResponse(BaseModel):
    job_id: str
    email: str
    status: JobStatus
    ttl_seconds: int


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    label: str | None
    email: str
    analysis: dict[str, Any] | None = None
