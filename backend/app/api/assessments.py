from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import (
    Application, Assessment, AssessmentAttempt, AssessmentInvite, AssessmentStatus,
    AptitudeQuestion, CodingQuestion, CompanyMember, Job, Student, User, UserRole,
)
from app.schemas.coding import CodingSubmissionCreate
from app.schemas.assessments import (
    AssessmentCreate, AssessmentSubmitRequest, AptitudeQuestionCreate,
    CodingQuestionCreate, InviteCreate,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])


async def company_for_user(db: AsyncSession, user: User) -> UUID:
    result = await db.scalar(select(CompanyMember.company_id).where(
        CompanyMember.user_id == user.id, CompanyMember.active.is_(True)
    ).limit(1))
    if not result:
        raise HTTPException(status_code=403, detail="No active company membership")
    return result


async def student_for_user(db: AsyncSession, user: User) -> UUID:
    result = await db.scalar(select(Student.id).where(Student.user_id == user.id))
    if not result:
        raise HTTPException(status_code=409, detail="Student profile is missing")
    return result


def public_question(q: AptitudeQuestion) -> dict:
    # Whitelist option fields; never send answer keys or explanations during an assessment.
    return {
        "id": str(q.id), "category": q.category, "difficulty": q.difficulty,
        "prompt": q.prompt,
        "options": [{"id": option.get("id"), "text": option.get("text")} for option in q.options],
        "marks": q.marks, "negative_marks": q.negative_marks,
    }


@router.post("/questions/aptitude", status_code=201)
async def create_aptitude_question(payload: AptitudeQuestionCreate,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company_id = await company_for_user(db, user)
    question = AptitudeQuestion(
        owner_company_id=company_id, created_by=user.id, category=payload.category.strip(),
        difficulty=payload.difficulty, prompt=payload.prompt.strip(),
        options=[option.model_dump() for option in payload.options], answer_key=payload.answer_key,
        explanation=payload.explanation, marks=payload.marks, negative_marks=payload.negative_marks,
        active=True,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return {"id": str(question.id), "category": question.category, "difficulty": question.difficulty,
            "prompt": question.prompt}


@router.get("/questions/aptitude")
async def list_aptitude_questions(category: str | None = None, difficulty: str | None = None,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company_id = await company_for_user(db, user)
    query = select(AptitudeQuestion).where(
        AptitudeQuestion.active.is_(True),
        or_(AptitudeQuestion.owner_company_id.is_(None), AptitudeQuestion.owner_company_id == company_id),
    )
    if category:
        query = query.where(AptitudeQuestion.category == category)
    if difficulty:
        query = query.where(AptitudeQuestion.difficulty == difficulty.upper())
    questions = list((await db.scalars(query.order_by(AptitudeQuestion.created_at.desc()).limit(200))).all())
    return [{**public_question(q), "scope": "PLATFORM" if q.owner_company_id is None else "COMPANY"}
            for q in questions]


@router.post("/questions/coding", status_code=201)
async def create_coding_question(payload: CodingQuestionCreate,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company_id = await company_for_user(db, user)
    question = CodingQuestion(
        owner_company_id=company_id, created_by=user.id, title=payload.title.strip(), slug=payload.slug,
        statement=payload.statement.strip(), constraints_text=payload.constraints_text,
        difficulty=payload.difficulty, skills=[s.strip() for s in payload.skills if s.strip()][:30],
        starter_code=payload.starter_code, time_limit_ms=payload.time_limit_ms,
        memory_limit_mb=payload.memory_limit_mb, active=True,
    )
    db.add(question)
    try:
        await db.commit()
        await db.refresh(question)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A coding question with this slug already exists")
    return {"id": str(question.id), "title": question.title, "slug": question.slug,
            "difficulty": question.difficulty}


@router.get("/questions/coding")
async def list_coding_questions(difficulty: str | None = None,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company_id = await company_for_user(db, user)
    query = select(CodingQuestion).where(
        CodingQuestion.active.is_(True),
        or_(CodingQuestion.owner_company_id.is_(None), CodingQuestion.owner_company_id == company_id),
    )
    if difficulty:
        query = query.where(CodingQuestion.difficulty == difficulty.upper())
    questions = list((await db.scalars(query.order_by(CodingQuestion.created_at.desc()).limit(200))).all())
    return [{"id": str(q.id), "title": q.title, "slug": q.slug, "statement": q.statement,
             "constraints_text": q.constraints_text, "difficulty": q.difficulty, "skills": q.skills,
             "starter_code": q.starter_code, "time_limit_ms": q.time_limit_ms,
             "memory_limit_mb": q.memory_limit_mb,
             "scope": "PLATFORM" if q.owner_company_id is None else "COMPANY"} for q in questions]


@router.post("", status_code=201)
async def create_assessment(payload: AssessmentCreate,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company_id = await company_for_user(db, user)
    job = await db.scalar(select(Job).where(Job.id == payload.job_id, Job.company_id == company_id,
                                             Job.deleted_at.is_(None)))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    aptitude, coding = [], []
    if payload.aptitude_question_ids:
        aptitude = list((await db.scalars(select(AptitudeQuestion).where(
            AptitudeQuestion.id.in_(payload.aptitude_question_ids), AptitudeQuestion.active.is_(True),
            or_(AptitudeQuestion.owner_company_id.is_(None), AptitudeQuestion.owner_company_id == company_id),
        ))).all())
        if len(aptitude) != len(payload.aptitude_question_ids):
            raise HTTPException(status_code=422, detail="One or more aptitude questions are unavailable")
    if payload.coding_question_ids:
        coding = list((await db.scalars(select(CodingQuestion).where(
            CodingQuestion.id.in_(payload.coding_question_ids), CodingQuestion.active.is_(True),
            or_(CodingQuestion.owner_company_id.is_(None), CodingQuestion.owner_company_id == company_id),
        ))).all())
        if len(coding) != len(payload.coding_question_ids):
            raise HTTPException(status_code=422, detail="One or more coding questions are unavailable")
    assessment = Assessment(
        job_id=job.id, title=payload.title.strip(), assessment_type=payload.assessment_type,
        duration_minutes=payload.duration_minutes, max_attempts=payload.max_attempts,
        config={**payload.config, "aptitude_question_ids": [str(q.id) for q in aptitude],
                "coding_question_ids": [str(q.id) for q in coding]}, active=True,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    return {"id": str(assessment.id), "job_id": str(job.id), "title": assessment.title,
            "assessment_type": assessment.assessment_type, "duration_minutes": assessment.duration_minutes,
            "max_attempts": assessment.max_attempts, "question_count": len(aptitude) + len(coding)}


@router.get("/job/{job_id}")
async def list_job_assessments(job_id: UUID,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company_id = await company_for_user(db, user)
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.company_id == company_id,
                                             Job.deleted_at.is_(None)))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    assessments = list((await db.scalars(select(Assessment).where(Assessment.job_id == job_id)
                                          .order_by(Assessment.created_at.desc()))).all())
    return [{"id": str(a.id), "title": a.title, "assessment_type": a.assessment_type,
             "duration_minutes": a.duration_minutes, "max_attempts": a.max_attempts,
             "active": a.active, "question_count": len((a.config or {}).get("aptitude_question_ids", []))
             + len((a.config or {}).get("coding_question_ids", []))} for a in assessments]


@router.post("/{assessment_id}/invite", status_code=201)
async def invite_applicants(assessment_id: UUID, payload: InviteCreate,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company_id = await company_for_user(db, user)
    assessment = await db.scalar(select(Assessment).join(Job, Job.id == Assessment.job_id).where(
        Assessment.id == assessment_id, Job.company_id == company_id, Job.deleted_at.is_(None)))
    if not assessment or not assessment.active:
        raise HTTPException(status_code=404, detail="Active assessment not found")
    ids = list(dict.fromkeys(payload.application_ids))
    applications = list((await db.scalars(select(Application).join(Job, Job.id == Application.job_id).where(
        Application.id.in_(ids), Application.job_id == assessment.job_id,
        Job.company_id == company_id, Application.withdrawn_at.is_(None)))).all())
    if len(applications) != len(ids):
        raise HTTPException(status_code=422, detail="Every application must belong to this job and be active")
    now = datetime.now(timezone.utc)
    starts_before = payload.starts_before
    deadline = payload.deadline or (now + timedelta(days=7))
    if deadline.tzinfo is None or (starts_before and starts_before.tzinfo is None):
        raise HTTPException(status_code=422, detail="Assessment dates must include a timezone")
    if deadline <= now or (starts_before and starts_before >= deadline):
        raise HTTPException(status_code=422, detail="Assessment window is invalid")
    created, existing_ids = [], []
    for application in applications:
        existing = await db.scalar(select(AssessmentInvite).where(
            AssessmentInvite.assessment_id == assessment.id,
            AssessmentInvite.application_id == application.id))
        if existing:
            existing_ids.append(str(existing.id))
            continue
        invite = AssessmentInvite(assessment_id=assessment.id, application_id=application.id,
            status=AssessmentStatus.SCHEDULED, starts_before=starts_before, deadline=deadline)
        db.add(invite)
        created.append(invite)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Could not create assessment invitations")
    for invite in created:
        await db.refresh(invite)
    return {"created": [{"id": str(i.id), "application_id": str(i.application_id),
                         "deadline": i.deadline.isoformat()} for i in created],
            "already_invited": existing_ids}


@router.get("/my-invites")
async def list_my_invites(user: User = Depends(require_roles(UserRole.STUDENT)),
                          db: AsyncSession = Depends(get_db)):
    student_id = await student_for_user(db, user)
    rows = (await db.execute(select(AssessmentInvite, Assessment)
        .join(Assessment, Assessment.id == AssessmentInvite.assessment_id)
        .join(Application, Application.id == AssessmentInvite.application_id)
        .where(Application.student_id == student_id)
        .order_by(AssessmentInvite.deadline.asc()).limit(100))).all()
    return [{"id": str(i.id), "status": i.status.value, "deadline": i.deadline.isoformat(),
             "starts_before": i.starts_before.isoformat() if i.starts_before else None,
             "attempts_used": i.attempts_used,
             "assessment": {"id": str(a.id), "title": a.title, "assessment_type": a.assessment_type,
                            "duration_minutes": a.duration_minutes, "max_attempts": a.max_attempts}}
            for i, a in rows]


@router.get("/invites/{invite_id}")
async def get_my_assessment(invite_id: UUID, user: User = Depends(require_roles(UserRole.STUDENT)),
                            db: AsyncSession = Depends(get_db)):
    student_id = await student_for_user(db, user)
    row = (await db.execute(select(AssessmentInvite, Assessment)
        .join(Assessment, Assessment.id == AssessmentInvite.assessment_id)
        .join(Application, Application.id == AssessmentInvite.application_id)
        .where(AssessmentInvite.id == invite_id, Application.student_id == student_id))).first()
    if not row:
        raise HTTPException(status_code=404, detail="Assessment invitation not found")
    invite, assessment = row
    config = assessment.config or {}
    aptitude_ids = [UUID(value) for value in config.get("aptitude_question_ids", [])]
    aptitude = list((await db.scalars(select(AptitudeQuestion).where(
        AptitudeQuestion.id.in_(aptitude_ids), AptitudeQuestion.active.is_(True)))).all()) if aptitude_ids else []
    coding_ids = [UUID(value) for value in config.get("coding_question_ids", [])]
    coding = list((await db.scalars(select(CodingQuestion).where(
        CodingQuestion.id.in_(coding_ids), CodingQuestion.active.is_(True)))).all()) if coding_ids else []
    return {"id": str(invite.id), "status": invite.status.value, "deadline": invite.deadline.isoformat(),
        "starts_before": invite.starts_before.isoformat() if invite.starts_before else None,
        "attempts_used": invite.attempts_used,
        "assessment": {"id": str(assessment.id), "title": assessment.title,
            "assessment_type": assessment.assessment_type, "duration_minutes": assessment.duration_minutes,
            "max_attempts": assessment.max_attempts},
        "aptitude_questions": [public_question(q) for q in aptitude],
        "coding_questions": [{"id": str(q.id), "title": q.title, "statement": q.statement,
            "constraints_text": q.constraints_text, "difficulty": q.difficulty, "skills": q.skills,
            "starter_code": q.starter_code, "time_limit_ms": q.time_limit_ms,
            "memory_limit_mb": q.memory_limit_mb} for q in coding]}


@router.post("/invites/{invite_id}/start")
async def start_assessment(invite_id: UUID, user: User = Depends(require_roles(UserRole.STUDENT)),
                           db: AsyncSession = Depends(get_db)):
    student_id = await student_for_user(db, user)
    row = (await db.execute(select(AssessmentInvite, Assessment)
        .join(Assessment, Assessment.id == AssessmentInvite.assessment_id)
        .join(Application, Application.id == AssessmentInvite.application_id)
        .where(AssessmentInvite.id == invite_id, Application.student_id == student_id))).first()
    if not row:
        raise HTTPException(status_code=404, detail="Assessment invitation not found")
    invite, assessment = row
    now = datetime.now(timezone.utc)
    if invite.starts_before and now < invite.starts_before:
        raise HTTPException(status_code=409, detail="Assessment is not open yet")
    if now >= invite.deadline:
        invite.status = AssessmentStatus.EXPIRED
        await db.commit()
        raise HTTPException(status_code=410, detail="Assessment deadline has passed")
    if invite.status == AssessmentStatus.IN_PROGRESS:
        current = await db.scalar(select(AssessmentAttempt).where(
            AssessmentAttempt.assessment_invite_id == invite.id,
            AssessmentAttempt.status == "IN_PROGRESS").order_by(AssessmentAttempt.attempt_number.desc()))
        if current:
            if now >= current.started_at + timedelta(minutes=assessment.duration_minutes):
                current.status = "EXPIRED"
                current.submitted_at = now
                invite.status = AssessmentStatus.SUBMITTED
                await db.commit()
            else:
                return {"attempt_id": str(current.id), "attempt_number": current.attempt_number,
                    "status": current.status, "started_at": current.started_at.isoformat(),
                    "duration_minutes": assessment.duration_minutes, "deadline": invite.deadline.isoformat()}
    if invite.attempts_used >= assessment.max_attempts:
        invite.status = AssessmentStatus.EXPIRED
        await db.commit()
        raise HTTPException(status_code=409, detail="No attempts remaining")
    attempt = AssessmentAttempt(assessment_invite_id=invite.id, attempt_number=invite.attempts_used + 1,
                                status="IN_PROGRESS", answers={})
    invite.attempts_used += 1
    invite.status = AssessmentStatus.IN_PROGRESS
    db.add(attempt)
    try:
        await db.commit()
        await db.refresh(attempt)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Attempt already started; reload the assessment")
    return {"attempt_id": str(attempt.id), "attempt_number": attempt.attempt_number,
        "status": attempt.status, "started_at": attempt.started_at.isoformat(),
        "duration_minutes": assessment.duration_minutes, "deadline": invite.deadline.isoformat()}


@router.post("/invites/{invite_id}/submit")
async def submit_aptitude_assessment(invite_id: UUID, payload: AssessmentSubmitRequest,
    user: User = Depends(require_roles(UserRole.STUDENT)), db: AsyncSession = Depends(get_db)):
    student_id = await student_for_user(db, user)
    row = (await db.execute(select(AssessmentInvite, Assessment)
        .join(Assessment, Assessment.id == AssessmentInvite.assessment_id)
        .join(Application, Application.id == AssessmentInvite.application_id)
        .where(AssessmentInvite.id == invite_id, Application.student_id == student_id))).first()
    if not row:
        raise HTTPException(status_code=404, detail="Assessment invitation not found")
    invite, assessment = row
    if assessment.assessment_type == "CODING":
        raise HTTPException(status_code=409, detail="Coding-only submission requires an isolated coding judge")
    attempt = await db.scalar(select(AssessmentAttempt).where(
        AssessmentAttempt.assessment_invite_id == invite.id,
        AssessmentAttempt.status == "IN_PROGRESS").order_by(AssessmentAttempt.attempt_number.desc()))
    if not attempt:
        raise HTTPException(status_code=409, detail="Start an assessment attempt before submitting")
    now = datetime.now(timezone.utc)
    if now >= invite.deadline or now >= attempt.started_at + timedelta(minutes=assessment.duration_minutes):
        invite.status = AssessmentStatus.EXPIRED
        attempt.status = "EXPIRED"
        attempt.submitted_at = now
        await db.commit()
        raise HTTPException(status_code=410, detail="Assessment time limit has expired")
    ids = [UUID(value) for value in (assessment.config or {}).get("aptitude_question_ids", [])]
    questions = list((await db.scalars(select(AptitudeQuestion).where(
        AptitudeQuestion.id.in_(ids), AptitudeQuestion.active.is_(True)))).all()) if ids else []
    if not questions:
        raise HTTPException(status_code=409, detail="No aptitude questions are configured")
    allowed = {q.id for q in questions}
    if any(qid not in allowed for qid in payload.answers):
        raise HTTPException(status_code=422, detail="Answers contain a question outside this assessment")
    max_marks = sum(q.marks for q in questions)
    raw, correct, answered = 0.0, 0, 0
    for q in questions:
        selected = payload.answers.get(q.id)
        if selected is None:
            continue
        answered += 1
        if selected == q.answer_key:
            raw += q.marks
            correct += 1
        else:
            raw -= q.negative_marks
    score = round(max(0.0, min(100.0, raw / max_marks * 100)), 2) if max_marks else 0.0
    attempt.answers = {str(qid): answer for qid, answer in payload.answers.items()}
    attempt.score, attempt.max_score = score, 100.0
    aptitude_result = {"score": score, "correct": correct, "answered": answered,
                       "total": len(questions), "raw_score": round(raw, 2),
                       "raw_max_score": round(max_marks, 2)}
    if assessment.assessment_type == "MIXED" and (attempt.result_summary or {}).get("aptitude"):
        raise HTTPException(status_code=409, detail="The aptitude section has already been submitted")
    if assessment.assessment_type == "MIXED":
        # Keep the attempt open so the candidate can also submit its coding section.
        attempt.result_summary = {**(attempt.result_summary or {}), "aptitude": aptitude_result}
        await db.commit()
        return {"status": "aptitude_submitted", "attempt_id": str(attempt.id), "score": score,
                "max_score": 100, "correct": correct, "answered": answered,
                "total_questions": len(questions), "next_step": "complete_coding_section_and_finish"}
    attempt.status, attempt.submitted_at = "SUBMITTED", now
    attempt.result_summary = aptitude_result
    invite.status = AssessmentStatus.COMPLETED if invite.attempts_used >= assessment.max_attempts else AssessmentStatus.SUBMITTED
    await db.commit()
    return {"status": "submitted", "attempt_id": str(attempt.id), "score": score, "max_score": 100,
            "correct": correct, "answered": answered, "total_questions": len(questions)}


@router.post("/invites/{invite_id}/coding-submissions", status_code=202)
async def submit_coding_solution(
    invite_id: UUID,
    payload: CodingSubmissionCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=160),
    user: User = Depends(require_roles(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
):
    """Queue source code for an external sandbox; never execute user code in the API."""
    from app.core.config import settings
    from app.models import Submission, SubmissionStatus
    if not settings.judge0_api_url:
        raise HTTPException(status_code=503, detail="Coding judge is not configured yet. Ask the platform administrator to configure JUDGE0_API_URL.")

    student_id = await student_for_user(db, user)
    row = (await db.execute(
        select(AssessmentInvite, Assessment)
        .join(Assessment, Assessment.id == AssessmentInvite.assessment_id)
        .join(Application, Application.id == AssessmentInvite.application_id)
        .where(AssessmentInvite.id == invite_id, Application.student_id == student_id)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Assessment invitation not found")
    invite, assessment = row
    if assessment.assessment_type not in {"CODING", "MIXED"}:
        raise HTTPException(status_code=409, detail="This assessment has no coding section")
    now = datetime.now(timezone.utc)
    if invite.status != AssessmentStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Start the assessment before submitting code")
    if now >= invite.deadline:
        raise HTTPException(status_code=410, detail="Assessment deadline has passed")
    attempt = await db.scalar(select(AssessmentAttempt).where(
        AssessmentAttempt.assessment_invite_id == invite.id,
        AssessmentAttempt.status == "IN_PROGRESS"
    ).order_by(AssessmentAttempt.attempt_number.desc()))
    if not attempt:
        raise HTTPException(status_code=409, detail="No active assessment attempt")
    if now >= attempt.started_at + timedelta(minutes=assessment.duration_minutes):
        attempt.status = "EXPIRED"
        attempt.submitted_at = now
        invite.status = AssessmentStatus.EXPIRED
        await db.commit()
        raise HTTPException(status_code=410, detail="Assessment time limit has expired")

    configured_ids = {UUID(value) for value in (assessment.config or {}).get("coding_question_ids", [])}
    if payload.coding_question_id not in configured_ids:
        raise HTTPException(status_code=422, detail="Coding question is not part of this assessment")
    question = await db.scalar(select(CodingQuestion).where(
        CodingQuestion.id == payload.coding_question_id, CodingQuestion.active.is_(True)))
    if not question:
        raise HTTPException(status_code=404, detail="Coding question not found")

    existing = await db.scalar(select(Submission).where(
        Submission.assessment_invite_id == invite.id,
        Submission.idempotency_key == idempotency_key))
    if existing:
        if existing.coding_question_id != question.id or existing.source_code != payload.source_code:
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used for a different submission")
        return {"submission_id": str(existing.id), "status": existing.status.value,
                "attempt_number": existing.attempt_number, "duplicate": True}

    submission = Submission(
        assessment_invite_id=invite.id, coding_question_id=question.id, student_id=student_id,
        idempotency_key=idempotency_key, language=payload.language, source_code=payload.source_code,
        status=SubmissionStatus.QUEUED, attempt_number=attempt.attempt_number,
    )
    db.add(submission)
    try:
        await db.commit()
        await db.refresh(submission)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Submission could not be created")

    try:
        from app.worker import celery_app
        celery_app.send_task("app.tasks.evaluate_coding_submission", args=[str(submission.id)])
    except Exception as exc:
        submission.status = SubmissionStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=503, detail="Submission saved but the evaluation queue is unavailable; retry later with a new idempotency key") from exc
    return {"submission_id": str(submission.id), "status": submission.status.value,
            "attempt_number": submission.attempt_number, "duplicate": False}


@router.post("/invites/{invite_id}/finish")
async def finish_assessment(
    invite_id: UUID,
    user: User = Depends(require_roles(UserRole.STUDENT)),
    db: AsyncSession = Depends(get_db),
):
    """Finalize a coding or mixed attempt after queued code submissions have completed."""
    from app.models import Submission, SubmissionResult
    student_id = await student_for_user(db, user)
    row = (await db.execute(select(AssessmentInvite, Assessment)
        .join(Assessment, Assessment.id == AssessmentInvite.assessment_id)
        .join(Application, Application.id == AssessmentInvite.application_id)
        .where(AssessmentInvite.id == invite_id, Application.student_id == student_id))).first()
    if not row:
        raise HTTPException(status_code=404, detail="Assessment invitation not found")
    invite, assessment = row
    if assessment.assessment_type not in {"CODING", "MIXED"}:
        raise HTTPException(status_code=409, detail="Use the aptitude submission endpoint to finish this assessment")
    attempt = await db.scalar(select(AssessmentAttempt).where(
        AssessmentAttempt.assessment_invite_id == invite.id,
        AssessmentAttempt.status == "IN_PROGRESS"
    ).order_by(AssessmentAttempt.attempt_number.desc()))
    if not attempt:
        raise HTTPException(status_code=409, detail="No active attempt to finish")
    now = datetime.now(timezone.utc)
    if now >= invite.deadline or now >= attempt.started_at + timedelta(minutes=assessment.duration_minutes):
        invite.status = AssessmentStatus.EXPIRED
        attempt.status = "EXPIRED"
        attempt.submitted_at = now
        await db.commit()
        raise HTTPException(status_code=410, detail="Assessment time limit has expired")
    config = assessment.config or {}
    aptitude_ids = [UUID(value) for value in config.get("aptitude_question_ids", [])]
    if assessment.assessment_type == "MIXED" and aptitude_ids and not (attempt.result_summary or {}).get("aptitude"):
        raise HTTPException(status_code=409, detail="Submit the aptitude section before finishing")
    coding_ids = [UUID(value) for value in config.get("coding_question_ids", [])]
    if not coding_ids:
        raise HTTPException(status_code=409, detail="No coding questions are configured")
    rows = (await db.execute(select(Submission, SubmissionResult).outerjoin(
        SubmissionResult, SubmissionResult.submission_id == Submission.id
    ).where(
        Submission.assessment_invite_id == invite.id,
        Submission.attempt_number == attempt.attempt_number,
        Submission.coding_question_id.in_(coding_ids),
    ).order_by(Submission.created_at.desc()))).all()
    latest = {}
    for submission, result in rows:
        if submission.coding_question_id not in latest:
            latest[submission.coding_question_id] = (submission, result)
    missing = [str(qid) for qid in coding_ids if qid not in latest]
    pending = [str(qid) for qid in coding_ids if qid in latest and (
        latest[qid][0].status.value in {"QUEUED", "RUNNING"} or latest[qid][1] is None
    ) and latest[qid][0].status.value != "FAILED"]
    failed = [str(qid) for qid in coding_ids if qid in latest and latest[qid][0].status.value == "FAILED"]
    if missing:
        raise HTTPException(status_code=409, detail="Submit code for every coding question before finishing")
    if pending:
        raise HTTPException(status_code=409, detail="Some code submissions are still being evaluated; check again shortly")
    if failed:
        raise HTTPException(status_code=409, detail="A coding submission failed to evaluate. Submit that question again with a new Idempotency-Key.")
    coding_scores = [float(latest[qid][1].score) for qid in coding_ids]
    coding_score = round(sum(coding_scores) / len(coding_scores), 2)
    summary = {**(attempt.result_summary or {}), "coding": {
        "score": coding_score,
        "questions": [{"question_id": str(qid), "score": float(latest[qid][1].score),
                       "verdict": latest[qid][1].verdict,
                       "passed": latest[qid][1].passed_count, "total": latest[qid][1].total_count}
                      for qid in coding_ids],
    }}
    if assessment.assessment_type == "MIXED":
        aptitude_score = float(summary["aptitude"]["score"])
        overall = round((aptitude_score + coding_score) / 2, 2)
    else:
        overall = coding_score
    summary["overall_score"] = overall
    attempt.result_summary = summary
    attempt.score, attempt.max_score = overall, 100.0
    attempt.status, attempt.submitted_at = "SUBMITTED", now
    invite.status = AssessmentStatus.COMPLETED if invite.attempts_used >= assessment.max_attempts else AssessmentStatus.SUBMITTED
    await db.commit()
    return {"status": "submitted", "attempt_id": str(attempt.id), "score": overall,
            "max_score": 100, "result_summary": summary}
