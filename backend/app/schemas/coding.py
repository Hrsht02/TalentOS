from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class CodingSubmissionCreate(BaseModel):
    coding_question_id: UUID
    language: Literal["python", "cpp", "java", "javascript"]
    source_code: str = Field(min_length=1, max_length=50000)
