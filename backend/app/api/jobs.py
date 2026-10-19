from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Application, ApplicationStatus, CompanyMember, Job, JobStatus, Student, User, UserRole
from app.schemas.jobs import ApplicationResponse, JobCreate, JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _company_for_user(db: AsyncSession, user: User) -> UUID:
    company_id = await db.scalar(
        select(CompanyMember.company_id).where(
            CompanyMember.user_id == user.id, CompanyMember.active.is_(True)
        ).limit(1)
    )
    if not company_id:
        raise HTTPException(status_code=403, detail="No active company membership is linked to this account")
    return company_id


@router.get("", response_model=list[JobResponse])
async def list_published_jobs(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Job).where(Job.status == JobStatus.PUBLISHED, Job.deleted_at.is_(None))
    if q and q.strip():
        query = query.where(Job.title.ilike(f"%{q.strip()}%"))
    query = query.order_by(Job.published_at.desc()).offset(offset).limit(limit)
    return list((await db.scalars(query)).all())


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    payload: JobCreate,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)),
    db: AsyncSession = Depends(get_db),
):
    company_id = await _company_for_user(db, user)
    if payload.experience_min is not None and payload.experience_max is not None and payload.experience_min > payload.experience_max:
        raise HTTPException(status_code=422, detail="experience_min cannot exceed experience_max")
    job = Job(company_id=company_id, created_by=user.id, title=payload.title.strip(),
              description=payload.description.strip(), location=payload.location,
              employment_type=payload.employment_type, experience_min=payload.experience_min,
              experience_max=payload.experience_max, openings=payload.openings,
              deadline=payload.deadline, requirements=payload.requirements,
              eligibility=payload.eligibility, status=JobStatus.DRAFT)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/mine", response_model=list[JobResponse])
async def list_my_jobs(
    user: User = Depends(require_roles(UserRole.COMPANY_HR, UserRole.AGENCY_MEMBER)),
    db: AsyncSession = Depends(get_db),
):
    company_ids = select(CompanyMember.company_id).where(
        CompanyMember.user_id == user.id, CompanyMember.active.is_(True)
    )
    query = select(Job).where(Job.company_id.in_(company_ids), Job.deleted_at.is_(None)).order_by(Job.created_at.desc()).limit(100)
    return list((await db.scalars(query)).all())


@router.post("/{job_id}/publish", response_model=JobResponse)
async def publish_job(
    job_id: UUID,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)),
    db: AsyncSession = Depends(get_db),
):
    company_id = await _company_for_user(db, user)
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.company_id == company_id, Job.deleted_at.is_(None)))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {JobStatus.DRAFT, JobStatus.PAUSED}:
        raise HTTPException(status_code=409, detail="Only draft or paused jobs can be published")
    if job.deadline and job.deadline <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Job deadline must be in the future")
    job.status = JobStatus.PUBLISHED
    job.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_id}/apply", response_model=ApplicationResponse, status_code=201)
async def apply_to_job(
    job_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=160),
    user: User = Depends(require_roles(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
):
    student_id = await db.scalar(select(Student.id).where(Student.user_id == user.id))
    if not student_id:
        raise HTTPException(status_code=409, detail="Student profile is missing")
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.status == JobStatus.PUBLISHED, Job.deleted_at.is_(None)))
    if not job:
        raise HTTPException(status_code=404, detail="Published job not found")
    existing = await db.scalar(select(Application).where(Application.job_id == job_id, Application.student_id == student_id))
    if existing:
        return existing
    application = Application(job_id=job_id, student_id=student_id, status=ApplicationStatus.APPLIED,
                              idempotency_key=idempotency_key, source="STUDENT")
    db.add(application)
    try:
        await db.commit()
        await db.refresh(application)
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(select(Application).where(Application.job_id == job_id, Application.student_id == student_id))
        if existing:
            return existing
        raise HTTPException(status_code=409, detail="Application could not be created")
    return application



@router.post("/{job_id}/match")
async def queue_candidate_matching(
    job_id: UUID,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)),
    db: AsyncSession = Depends(get_db),
):
    from app.worker import celery_app
    company_id = await _company_for_user(db, user)
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.company_id == company_id, Job.deleted_at.is_(None)))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.PUBLISHED:
        raise HTTPException(status_code=409, detail="Publish the job before running candidate matching")
    task = celery_app.send_task("app.tasks.match_candidates", args=[str(job.id)])
    return {"status": "queued", "job_id": str(job.id), "task_id": task.id}


@router.get("/{job_id}/matches")
async def get_candidate_matches(
    job_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles(UserRole.COMPANY_HR)),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Match, Student, User as UserModel
    company_id = await _company_for_user(db, user)
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.company_id == company_id, Job.deleted_at.is_(None)))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    query = (
        select(Match, Student, UserModel)
        .join(Student, Student.id == Match.student_id)
        .join(UserModel, UserModel.id == Student.user_id)
        .where(Match.job_id == job.id)
        .order_by(Match.eligible.desc(), Match.match_score.desc(), Match.created_at.asc())
        .offset(offset).limit(limit)
    )
    rows = (await db.execute(query)).all()
    return [{
        "student_id": str(student.id),
        "full_name": user_row.full_name,
        "headline": student.headline,
        "location": student.location,
        "graduation_year": student.graduation_year,
        "score": match.match_score,
        "eligible": match.eligible,
        "explanation": match.explanation,
        "skill_gaps": match.skill_gaps,
        "evidence": match.evidence,
    } for match, student, user_row in rows]
