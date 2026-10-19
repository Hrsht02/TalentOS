from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuestionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=1000)


class AptitudeQuestionCreate(BaseModel):
    category: str = Field(min_length=2, max_length=60)
    difficulty: Literal["EASY", "MEDIUM", "HARD"]
    prompt: str = Field(min_length=5, max_length=12000)
    options: list[QuestionOption] = Field(min_length=2, max_length=8)
    answer_key: str = Field(min_length=1, max_length=20)
    explanation: str | None = Field(default=None, max_length=4000)
    marks: float = Field(default=1.0, gt=0, le=100)
    negative_marks: float = Field(default=0.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_options(self):
        ids = [option.id for option in self.options]
        if self.answer_key not in ids:
            raise ValueError("answer_key must match one of the option IDs")
        if len(ids) != len(set(ids)):
            raise ValueError("Option IDs must be unique")
        if any(not option.id.strip() or not option.text.strip() for option in self.options):
            raise ValueError("Option IDs and text must not be blank")
        return self


class CodingQuestionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    slug: str = Field(min_length=3, max_length=260, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    statement: str = Field(min_length=10, max_length=30000)
    constraints_text: str | None = Field(default=None, max_length=12000)
    difficulty: Literal["EASY", "MEDIUM", "HARD"]
    skills: list[str] = Field(default_factory=list, max_length=30)
    starter_code: dict[str, str] = Field(default_factory=dict)
    time_limit_ms: int = Field(default=2000, ge=100, le=15000)
    memory_limit_mb: int = Field(default=256, ge=32, le=1024)


class AssessmentCreate(BaseModel):
    job_id: UUID
    title: str = Field(min_length=3, max_length=240)
    assessment_type: Literal["APTITUDE", "CODING", "MIXED"]
    duration_minutes: int = Field(ge=5, le=240)
    max_attempts: int = Field(default=1, ge=1, le=5)
    aptitude_question_ids: list[UUID] = Field(default_factory=list, max_length=100)
    coding_question_ids: list[UUID] = Field(default_factory=list, max_length=20)
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_question_selection(self):
        if self.assessment_type == "APTITUDE" and not self.aptitude_question_ids:
            raise ValueError("APTITUDE assessments require aptitude questions")
        if self.assessment_type == "CODING" and not self.coding_question_ids:
            raise ValueError("CODING assessments require coding questions")
        if self.assessment_type == "MIXED" and not (self.aptitude_question_ids or self.coding_question_ids):
            raise ValueError("MIXED assessments require at least one question")
        if len(set(self.aptitude_question_ids)) != len(self.aptitude_question_ids):
            raise ValueError("Duplicate aptitude question IDs are not allowed")
        if len(set(self.coding_question_ids)) != len(self.coding_question_ids):
            raise ValueError("Duplicate coding question IDs are not allowed")
        return self


class InviteCreate(BaseModel):
    application_ids: list[UUID] = Field(min_length=1, max_length=500)
    starts_before: datetime | None = None
    deadline: datetime | None = None


class AssessmentSubmitRequest(BaseModel):
    answers: dict[UUID, str] = Field(min_length=1, max_length=100)
