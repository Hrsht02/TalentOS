from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index,
    Integer, JSON, Numeric, String, Text, UniqueConstraint, func, text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


def enum_type(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, native_enum=True, values_callable=lambda items: [e.value for e in items])


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    STUDENT = "STUDENT"
    COMPANY_HR = "COMPANY_HR"
    AGENCY_MEMBER = "AGENCY_MEMBER"


class AccountStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class JobStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PUBLISHED = "PUBLISHED"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class ApplicationStatus(str, enum.Enum):
    APPLIED = "APPLIED"
    ASSESSMENT_INVITED = "ASSESSMENT_INVITED"
    ASSESSMENT_COMPLETED = "ASSESSMENT_COMPLETED"
    SHORTLIST_RECOMMENDED = "SHORTLIST_RECOMMENDED"
    SHORTLISTED = "SHORTLISTED"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    HIRED = "HIRED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class AssessmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SubmissionStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Timestamped(TimestampMixin, Base):
    __abstract__ = True
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(Timestamped):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole, "user_role"), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(enum_type(AccountStatus, "account_status"), default=AccountStatus.PENDING_VERIFICATION, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_users_role_status", "role", "status"),)


class AuthIdentity(Timestamped):
    __tablename__ = "auth_identities"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_provider_subject"),)


class RefreshToken(Timestamped):
    __tablename__ = "refresh_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("refresh_tokens.id"))


class OneTimeToken(Timestamped):
    __abstract__ = True
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetToken(OneTimeToken):
    __tablename__ = "password_reset_tokens"


class EmailVerification(OneTimeToken):
    __tablename__ = "email_verifications"


class Student(Timestamped):
    __tablename__ = "students"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    headline: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    location: Mapped[str | None] = mapped_column(String(160))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    degree: Mapped[str | None] = mapped_column(String(120))
    branch: Mapped[str | None] = mapped_column(String(120))
    cgpa: Mapped[float | None] = mapped_column(Float)
    backlogs: Mapped[int | None] = mapped_column(Integer)
    expected_salary_min: Mapped[int | None] = mapped_column(Integer)
    expected_salary_max: Mapped[int | None] = mapped_column(Integer)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    visibility: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    profile_completion: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class StudentEducation(Timestamped):
    __tablename__ = "student_education"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    institution: Mapped[str] = mapped_column(String(200), nullable=False)
    degree: Mapped[str] = mapped_column(String(120), nullable=False)
    field_of_study: Mapped[str | None] = mapped_column(String(160))
    start_year: Mapped[int | None] = mapped_column(Integer)
    end_year: Mapped[int | None] = mapped_column(Integer)
    grade: Mapped[str | None] = mapped_column(String(40))


class StudentExperience(Timestamped):
    __tablename__ = "student_experience"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class StudentProject(Timestamped):
    __tablename__ = "student_projects"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000))
    repository_url: Mapped[str | None] = mapped_column(String(1000))
    technologies: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class StudentSkill(Timestamped):
    __tablename__ = "student_skills"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    proficiency: Mapped[str | None] = mapped_column(String(40))
    years_experience: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40), default="SELF_REPORTED", nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "skill", name="uq_student_skill"),)


class IntegrationAccount(Timestamped):
    __tablename__ = "integrations_accounts"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    external_username: Mapped[str | None] = mapped_column(String(200))
    encrypted_credentials: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "provider", name="uq_student_integration_provider"),)


class IntegrationSnapshot(Timestamped):
    __tablename__ = "integration_snapshots"
    integration_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("integrations_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Resume(Timestamped):
    __tablename__ = "resumes"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    parsed_profile: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Company(Timestamped):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    website: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(1000))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class CompanyMember(Timestamped):
    __tablename__ = "company_members"
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sub_role: Mapped[str] = mapped_column(String(40), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("company_id", "user_id", name="uq_company_member"),)


class CompanyJoinRequest(Timestamped):
    __tablename__ = "company_join_requests"
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("company_id", "user_id", name="uq_company_join_request_user"),)


class Invitation(Timestamped):
    __tablename__ = "invitations"
    tenant_type: Mapped[str] = mapped_column(String(30), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    sub_role: Mapped[str] = mapped_column(String(40), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)


class Agency(Timestamped):
    __tablename__ = "agencies"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class AgencyMember(Timestamped):
    __tablename__ = "agency_members"
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sub_role: Mapped[str] = mapped_column(String(40), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("agency_id", "user_id", name="uq_agency_member"),)


class AgencyClient(Timestamped):
    __tablename__ = "agency_clients"
    agency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    access_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    __table_args__ = (UniqueConstraint("agency_id", "company_id", name="uq_agency_client"),)


class Job(Timestamped):
    __tablename__ = "jobs"
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    employment_type: Mapped[str | None] = mapped_column(String(60))
    experience_min: Mapped[float | None] = mapped_column(Float)
    experience_max: Mapped[float | None] = mapped_column(Float)
    openings: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[JobStatus] = mapped_column(enum_type(JobStatus, "job_status"), default=JobStatus.DRAFT, nullable=False)
    requirements: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    eligibility: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_jobs_status_deadline", "status", "deadline"),)


class JobRequirement(Timestamped):
    __tablename__ = "job_requirements"
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    skill: Mapped[str] = mapped_column(String(120), nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(30), default="NICE_TO_HAVE", nullable=False)
    minimum_years: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class JobEvalConfig(Timestamped):
    __tablename__ = "job_eval_config"
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB, default=lambda: {"aptitude": 0.2, "coding": 0.3, "skills": 0.2, "projects": 0.1, "resume": 0.2}, nullable=False)
    passing_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    window_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    scoring_rule: Mapped[str] = mapped_column(String(20), default="BEST", nullable=False)


class JobEmbedding(Timestamped):
    __tablename__ = "job_embeddings"
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)


class StudentEmbedding(Timestamped):
    __tablename__ = "student_embeddings"
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)


class Match(Timestamped):
    __tablename__ = "matches"
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    skill_gaps: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint("job_id", "student_id", name="uq_job_student_match"), CheckConstraint("match_score >= 0 AND match_score <= 100", name="ck_match_score_range"))


class Application(Timestamped):
    __tablename__ = "applications"
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[ApplicationStatus] = mapped_column(enum_type(ApplicationStatus, "application_status"), default=ApplicationStatus.APPLIED, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(40), default="STUDENT", nullable=False)
    consented_auto_apply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("job_id", "student_id", name="uq_application_job_student"), UniqueConstraint("student_id", "idempotency_key", name="uq_application_idempotency"))


class ApplicationStatusHistory(Timestamped):
    __tablename__ = "application_status_history"
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Assessment(Timestamped):
    __tablename__ = "assessments"
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AssessmentInvite(Timestamped):
    __tablename__ = "assessment_invites"
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[AssessmentStatus] = mapped_column(enum_type(AssessmentStatus, "assessment_status"), default=AssessmentStatus.SCHEDULED, nullable=False)
    starts_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AptitudeQuestion(Timestamped):
    __tablename__ = "aptitude_questions"
    owner_company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    answer_key: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    marks: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    negative_marks: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CodingQuestion(Timestamped):
    __tablename__ = "coding_questions"
    owner_company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    slug: Mapped[str] = mapped_column(String(260), unique=True, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    constraints_text: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    starter_code: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict, nullable=False)
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TestCase(Timestamped):
    __tablename__ = "test_cases"
    coding_question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("coding_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Submission(Timestamped):
    __tablename__ = "submissions"
    assessment_invite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assessment_invites.id", ondelete="CASCADE"), nullable=False, index=True)
    coding_question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("coding_questions.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    language: Mapped[str] = mapped_column(String(40), nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(enum_type(SubmissionStatus, "submission_status"), default=SubmissionStatus.QUEUED, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("assessment_invite_id", "idempotency_key", name="uq_submission_idempotency"),)


class SubmissionResult(Timestamped):
    __tablename__ = "submission_results"
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), unique=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    runtime_ms: Mapped[int | None] = mapped_column(Integer)
    memory_kb: Mapped[int | None] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(40), nullable=False)
    result_details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Score(Timestamped):
    __tablename__ = "scores"
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(80), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    calculated_from: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    __table_args__ = (CheckConstraint("total_score >= 0 AND total_score <= 100", name="ck_score_range"),)


class ScoreBreakdown(Timestamped):
    __tablename__ = "score_breakdowns"
    score_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scores.id", ondelete="CASCADE"), nullable=False, index=True)
    criterion: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Ranking(Timestamped):
    __tablename__ = "rankings"
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    score_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scores.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("job_id", "application_id", "snapshot_version", name="uq_ranking_snapshot"),)


class Shortlist(Timestamped):
    __tablename__ = "shortlists"
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    recommended: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), default="PENDING_REVIEW", nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    override_reason: Mapped[str | None] = mapped_column(Text)


class Interview(Timestamped):
    __tablename__ = "interviews"
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location_or_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), default="SCHEDULED", nullable=False)
    calendar_event_id: Mapped[str | None] = mapped_column(String(255))


class InterviewFeedback(Timestamped):
    __tablename__ = "interview_feedback"
    interview_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    scorecard: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    comments: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Timestamped):
    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)


class NotificationPreference(Timestamped):
    __tablename__ = "notification_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    channels: Mapped[dict[str, bool]] = mapped_column(JSONB, default=lambda: {"in_app": True, "email": True, "push": False}, nullable=False)
    event_preferences: Mapped[dict[str, bool]] = mapped_column(JSONB, default=dict, nullable=False)


class AuditLog(Timestamped):
    __tablename__ = "audit_logs"
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    tenant_type: Mapped[str | None] = mapped_column(String(30), index=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class AIUsageLog(Timestamped):
    __tablename__ = "ai_usage_logs"
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(String(80), index=True)
    error_code: Mapped[str | None] = mapped_column(String(80))


class FeatureFlag(Timestamped):
    __tablename__ = "feature_flags"
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Setting(Timestamped):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class CandidateComment(Timestamped):
    __tablename__ = "candidate_comments"
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(30), default="INTERNAL", nullable=False)


class ConsentRecord(Timestamped):
    __tablename__ = "consent_records"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))



class AssessmentAttempt(Timestamped):
    __tablename__ = "assessment_attempts"
    assessment_invite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_invites.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="IN_PROGRESS", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(Float)
    max_score: Mapped[float | None] = mapped_column(Float)
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    result_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    __table_args__ = (
        UniqueConstraint("assessment_invite_id", "attempt_number", name="uq_assessment_attempt_number"),
        CheckConstraint("attempt_number >= 1", name="ck_assessment_attempt_positive"),
    )
