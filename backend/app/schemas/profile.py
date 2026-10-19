from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class StudentProfileUpdate(BaseModel):
    headline: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    degree: str | None = Field(default=None, max_length=120)
    branch: str | None = Field(default=None, max_length=120)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    backlogs: int | None = Field(default=None, ge=0, le=100)
    expected_salary_min: int | None = Field(default=None, ge=0)
    expected_salary_max: int | None = Field(default=None, ge=0)


class SkillCreate(BaseModel):
    skill: str = Field(min_length=1, max_length=100)
    proficiency: str | None = Field(default=None, max_length=40)
    years_experience: float | None = Field(default=None, ge=0, le=60)


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    skill: str
    proficiency: str | None
    years_experience: float | None
    source: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    url: str | None = Field(default=None, max_length=1000)
    repository_url: str | None = Field(default=None, max_length=1000)
    technologies: list[str] = Field(default_factory=list, max_length=40)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    url: str | None
    repository_url: str | None
    technologies: list[str]
    verified: bool


class StudentProfileResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    headline: str | None
    phone: str | None
    location: str | None
    graduation_year: int | None
    degree: str | None
    branch: str | None
    cgpa: float | None
    backlogs: int | None
    expected_salary_min: int | None
    expected_salary_max: int | None
    profile_completion: int
    skills: list[SkillResponse]
    projects: list[ProjectResponse]
