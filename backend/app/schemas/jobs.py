from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=30, max_length=30000)
    location: str | None = Field(default=None, max_length=200)
    employment_type: str | None = Field(default=None, max_length=60)
    experience_min: float | None = Field(default=None, ge=0, le=60)
    experience_max: float | None = Field(default=None, ge=0, le=60)
    openings: int = Field(default=1, ge=1, le=10000)
    deadline: datetime | None = None
    requirements: dict = Field(default_factory=dict)
    eligibility: dict = Field(default_factory=dict)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    title: str
    description: str
    location: str | None
    employment_type: str | None
    experience_min: float | None
    experience_max: float | None
    openings: int
    deadline: datetime | None
    status: str
    requirements: dict
    eligibility: dict
    published_at: datetime | None
    created_at: datetime


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    student_id: UUID
    status: str
    created_at: datetime
