from fastapi import APIRouter, Depends, HTTPException
import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Application, Job, JobStatus, Student, StudentProject, StudentSkill, User, UserRole
from app.schemas.profile import (
    ProjectCreate, ProjectResponse, SkillCreate, SkillResponse,
    StudentProfileResponse, StudentProfileUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/student/profile", tags=["student profile"], dependencies=[Depends(require_roles(UserRole.STUDENT))])


async def _queue_profile_refresh(db: AsyncSession, student_id):
    """Refresh matching for published jobs the student has already applied to."""
    job_ids = list((await db.scalars(
        select(Job.id).join(Application, Application.job_id == Job.id).where(
            Application.student_id == student_id, Job.status == JobStatus.PUBLISHED, Job.deleted_at.is_(None)
        ).distinct()
    )).all())
    if not job_ids:
        return
    try:
        from app.worker import celery_app
        for job_id in job_ids:
            celery_app.send_task("app.tasks.match_candidates", args=[str(job_id)])
    except Exception as exc:
        logger.warning("Profile refresh could not be queued student_id=%s error_type=%s",
                       student_id, type(exc).__name__)


async def _student_for_user(db: AsyncSession, user: User) -> Student:
    student = await db.scalar(select(Student).where(Student.user_id == user.id))
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student


def _completion(student: Student, skills_count: int, projects_count: int) -> int:
    checks = [
        bool(student.headline), bool(student.location), bool(student.degree),
        student.graduation_year is not None, student.cgpa is not None,
        skills_count > 0, projects_count > 0,
    ]
    return round(sum(checks) / len(checks) * 100)


@router.get("", response_model=StudentProfileResponse)
async def get_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    student = await _student_for_user(db, user)
    skills = list((await db.scalars(select(StudentSkill).where(StudentSkill.student_id == student.id).order_by(StudentSkill.skill))).all())
    projects = list((await db.scalars(select(StudentProject).where(StudentProject.student_id == student.id).order_by(StudentProject.created_at.desc()))).all())
    completion = _completion(student, len(skills), len(projects))
    if student.profile_completion != completion:
        student.profile_completion = completion
        await db.commit()
    return StudentProfileResponse(
        id=student.id, full_name=user.full_name, email=user.email, headline=student.headline,
        phone=student.phone, location=student.location, graduation_year=student.graduation_year,
        degree=student.degree, branch=student.branch, cgpa=student.cgpa, backlogs=student.backlogs,
        expected_salary_min=student.expected_salary_min, expected_salary_max=student.expected_salary_max,
        profile_completion=completion, skills=skills, projects=projects,
    )


@router.patch("", response_model=StudentProfileResponse)
async def update_profile(payload: StudentProfileUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    student = await _student_for_user(db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(student, field, value)
    await db.commit()
    await _queue_profile_refresh(db, student.id)
    return await get_profile(user=user, db=db)


@router.post("/skills", response_model=SkillResponse, status_code=201)
async def add_skill(payload: SkillCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    student = await _student_for_user(db, user)
    skill_name = payload.skill.strip()
    existing = await db.scalar(select(StudentSkill).where(StudentSkill.student_id == student.id, StudentSkill.skill.ilike(skill_name)))
    if existing:
        existing.proficiency = payload.proficiency
        existing.years_experience = payload.years_experience
        await db.commit()
        await db.refresh(existing)
        await _queue_profile_refresh(db, student.id)
        return existing
    item = StudentSkill(student_id=student.id, skill=skill_name, proficiency=payload.proficiency, years_experience=payload.years_experience, source="SELF_REPORTED")
    db.add(item)
    try:
        await db.commit()
        await db.refresh(item)
        await _queue_profile_refresh(db, student.id)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This skill is already in your profile")
    return item


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from uuid import UUID
    try:
        parsed_id = UUID(skill_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Skill not found")
    student = await _student_for_user(db, user)
    item = await db.scalar(select(StudentSkill).where(StudentSkill.id == parsed_id, StudentSkill.student_id == student.id))
    if not item:
        raise HTTPException(status_code=404, detail="Skill not found")
    await db.delete(item)
    await db.commit()
    await _queue_profile_refresh(db, student.id)


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def add_project(payload: ProjectCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    student = await _student_for_user(db, user)
    item = StudentProject(student_id=student.id, name=payload.name.strip(), description=payload.description,
                          url=payload.url, repository_url=payload.repository_url,
                          technologies=[t.strip() for t in payload.technologies if t.strip()][:40])
    db.add(item)
    await db.commit()
    await db.refresh(item)
    await _queue_profile_refresh(db, student.id)
    return item


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from uuid import UUID
    try:
        parsed_id = UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    student = await _student_for_user(db, user)
    item = await db.scalar(select(StudentProject).where(StudentProject.id == parsed_id, StudentProject.student_id == student.id))
    if not item:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(item)
    await db.commit()
    await _queue_profile_refresh(db, student.id)
