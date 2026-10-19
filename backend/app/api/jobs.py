from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
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



@router.get("/{job_id}/applications")
async def list_job_applications(
    job_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles(UserRole.COMPANY_HR)),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Match, Student, StudentSkill, User as UserModel
    company_id = await _company_for_user(db, user)
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.company_id == company_id, Job.deleted_at.is_(None)))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    query = (
        select(Application, Student, UserModel, Match)
        .join(Student, Student.id == Application.student_id)
        .join(UserModel, UserModel.id == Student.user_id)
        .outerjoin(Match, (Match.job_id == Application.job_id) & (Match.student_id == Application.student_id))
        .where(Application.job_id == job.id)
        .order_by(Match.match_score.desc().nullslast(), Application.created_at.desc())
        .offset(offset).limit(limit)
    )
    rows = (await db.execute(query)).all()
    results = []
    for application, student, candidate_user, match in rows:
        candidate_skills = list((await db.scalars(select(StudentSkill.skill).where(StudentSkill.student_id == student.id))).all())
        results.append({
            "application_id": str(application.id),
            "student_id": str(student.id),
            "full_name": candidate_user.full_name,
            "email": candidate_user.email,
            "headline": student.headline,
            "location": student.location,
            "graduation_year": student.graduation_year,
            "skills": candidate_skills,
            "status": application.status.value,
            "applied_at": application.created_at.isoformat(),
            "match_score": match.match_score if match else None,
            "match_eligible": match.eligible if match else None,
            "match_explanation": match.explanation if match else None,
        })
    return results


@router.post("/applications/{application_id}/shortlist")
async def approve_shortlist(
    application_id: UUID,
    reason: str | None = None,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)),
    db: AsyncSession = Depends(get_db),
):
    from app.models import AuditLog, Shortlist
    company_id = await _company_for_user(db, user)
    query = (
        select(Application)
        .join(Job, Job.id == Application.job_id)
        .where(Application.id == application_id, Job.company_id == company_id, Job.deleted_at.is_(None))
    )
    application = await db.scalar(query)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    existing = await db.scalar(select(Shortlist).where(Shortlist.application_id == application.id))
    if existing:
        existing.decision = "APPROVED"
        existing.recommended = True
        existing.reviewed_by = user.id
        existing.override_reason = reason
    else:
        db.add(Shortlist(job_id=application.job_id, application_id=application.id, recommended=True,
                         decision="APPROVED", reviewed_by=user.id, override_reason=reason))
    old_status = application.status.value
    application.status = ApplicationStatus.SHORTLISTED
    db.add(AuditLog(actor_user_id=user.id, tenant_type="COMPANY", tenant_id=company_id,
                    action="APPLICATION_SHORTLISTED", resource_type="APPLICATION",
                    resource_id=str(application.id), details={"reason": reason}))
    from app.models import ApplicationStatusHistory
    db.add(ApplicationStatusHistory(application_id=application.id, old_status=old_status,
                                    new_status=ApplicationStatus.SHORTLISTED.value, changed_by=user.id,
                                    reason=reason, event_metadata={"source": "hr_shortlist"}))
    await db.commit()
    return {"status": "shortlisted", "application_id": str(application.id), "decision": "APPROVED"}


@router.patch("/applications/{application_id}/status")
async def change_application_status(
    application_id: UUID,
    payload: dict,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)),
    db: AsyncSession = Depends(get_db),
):
    from app.models import ApplicationStatusHistory, AuditLog
    company_id = await _company_for_user(db, user)
    application = await db.scalar(
        select(Application).join(Job, Job.id == Application.job_id).where(
            Application.id == application_id, Job.company_id == company_id, Job.deleted_at.is_(None)
        )
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    requested = payload.get("status")
    allowed = {ApplicationStatus.ASSESSMENT_INVITED, ApplicationStatus.SHORTLISTED,
               ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER, ApplicationStatus.HIRED,
               ApplicationStatus.REJECTED}
    try:
        new_status = ApplicationStatus(requested)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid application status")
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail="This status cannot be set by the employer endpoint")
    old_status = application.status
    if old_status == new_status:
        return {"application_id": str(application.id), "status": new_status.value}
    application.status = new_status
    reason = payload.get("reason")
    db.add(ApplicationStatusHistory(application_id=application.id, old_status=old_status.value,
                                    new_status=new_status.value, changed_by=user.id, reason=reason,
                                    event_metadata={"source": "hr_status_update"}))
    db.add(AuditLog(actor_user_id=user.id, tenant_type="COMPANY", tenant_id=company_id,
                    action="APPLICATION_STATUS_CHANGED", resource_type="APPLICATION",
                    resource_id=str(application.id), details={"from": old_status.value, "to": new_status.value, "reason": reason}))
    await db.commit()
    return {"application_id": str(application.id), "status": new_status.value}



@router.get("/{job_id}/ranking")
async def get_job_ranking(
    job_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles(UserRole.COMPANY_HR)),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest score snapshot; shortlist recommendations are advisory."""
    from app.models import Ranking, Score, ScoreBreakdown, Shortlist, User as UserModel
    company_id = await _company_for_user(db, user)
    job = await db.scalar(select(Job).where(
        Job.id == job_id, Job.company_id == company_id, Job.deleted_at.is_(None)
    ))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    latest_version = select(func.max(Ranking.snapshot_version)).where(
        Ranking.job_id == job.id
    ).scalar_subquery()
    rows = (await db.execute(
        select(Ranking, Application, Score, Student, UserModel, Shortlist)
        .join(Application, Application.id == Ranking.application_id)
        .join(Score, Score.id == Ranking.score_id)
        .join(Student, Student.id == Application.student_id)
        .join(UserModel, UserModel.id == Student.user_id)
        .outerjoin(Shortlist, (Shortlist.application_id == Application.id) & (Shortlist.job_id == job.id))
        .where(Ranking.job_id == job.id, Ranking.snapshot_version == latest_version)
        .order_by(Ranking.rank.asc())
        .offset(offset).limit(limit)
    )).all()
    results = []
    for ranking, application, score, student, candidate_user, shortlist in rows:
        breakdown = list((await db.scalars(select(ScoreBreakdown).where(
            ScoreBreakdown.score_id == score.id
        ).order_by(ScoreBreakdown.criterion.asc()))).all())
        results.append({
            "rank": ranking.rank,
            "snapshot_version": ranking.snapshot_version,
            "application_id": str(application.id),
            "student_id": str(student.id),
            "full_name": candidate_user.full_name,
            "headline": student.headline,
            "location": student.location,
            "graduation_year": student.graduation_year,
            "application_status": application.status.value,
            "score": score.total_score,
            "score_explanation": score.explanation,
            "score_breakdown": [{
                "criterion": item.criterion, "score": item.raw_score,
                "weight": item.weight, "contribution": item.contribution,
            } for item in breakdown],
            "shortlist_recommended": shortlist.recommended if shortlist else False,
            "shortlist_decision": shortlist.decision if shortlist else "NOT_RECOMMENDED",
        })
    return {"job_id": str(job.id), "count": len(results),
            "snapshot_version": rows[0][0].snapshot_version if rows else None, "results": results}
