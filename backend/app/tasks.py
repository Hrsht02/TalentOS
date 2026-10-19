"""Background task entrypoints. Keep tasks idempotent and avoid logging user PII."""
import logging
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def health_probe(self) -> dict[str, str]:
    """Small smoke task used to verify queue connectivity during deployment."""
    logger.info("TalentOS queue health probe completed")
    return {"status": "ok", "task": "health_probe"}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_ai_text(self, prompt: str, temperature: float = 0.2) -> dict[str, str]:
    """Run AI work off the request path using the configured provider failover."""
    import asyncio
    from app.services.ai_provider import ai_provider

    try:
        result = asyncio.run(ai_provider.generate_text(prompt, temperature=temperature))
        return {"status": "completed", "text": result}
    except Exception as exc:
        logger.warning("AI background task failed type=%s", type(exc).__name__)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=20)
def match_candidates(self, job_id: str) -> dict[str, object]:
    """Compute explainable job-specific matches using structured profile evidence."""
    import asyncio
    import uuid
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal, engine
    from app.models import Job, JobStatus, Match, Student, StudentProject, StudentSkill

    async def run():
        parsed_job_id = uuid.UUID(job_id)
        async with AsyncSessionLocal() as db:
            job = await db.scalar(select(Job).where(Job.id == parsed_job_id, Job.status == JobStatus.PUBLISHED, Job.deleted_at.is_(None)))
            if not job:
                return {"status": "skipped", "reason": "job_not_published"}
            requirements = job.requirements or {}
            eligibility = job.eligibility or {}
            required_skills = [str(s).strip().lower() for s in requirements.get("skills", []) if str(s).strip()]
            min_cgpa = eligibility.get("minimum_cgpa", requirements.get("minimum_cgpa"))
            max_backlogs = eligibility.get("maximum_backlogs", requirements.get("maximum_backlogs"))
            allowed_graduation_years = eligibility.get("graduation_years")
            location_required = eligibility.get("location")
            students = list((await db.scalars(select(Student))).all())
            skills = list((await db.scalars(select(StudentSkill))).all())
            projects = list((await db.scalars(select(StudentProject))).all())
            skills_by_student = {}
            projects_by_student = {}
            for item in skills:
                skills_by_student.setdefault(item.student_id, set()).add(item.skill.strip().lower())
            for item in projects:
                projects_by_student.setdefault(item.student_id, []).append(item)
            processed = 0
            eligible_count = 0
            for student in students:
                student_skills = skills_by_student.get(student.id, set())
                matched_skills = sorted(student_skills.intersection(required_skills))
                gaps = sorted(set(required_skills) - student_skills)
                is_eligible = True
                reasons = []
                if min_cgpa is not None and (student.cgpa is None or student.cgpa < float(min_cgpa)):
                    is_eligible = False
                    reasons.append("Does not meet the configured minimum CGPA")
                if max_backlogs is not None and (student.backlogs is None or student.backlogs > int(max_backlogs)):
                    is_eligible = False
                    reasons.append("Does not meet the configured backlog limit")
                if allowed_graduation_years and student.graduation_year not in allowed_graduation_years:
                    is_eligible = False
                    reasons.append("Graduation year is outside the configured eligibility range")
                if location_required and student.location and str(location_required).lower() not in student.location.lower():
                    is_eligible = False
                    reasons.append("Location does not match the configured requirement")
                skill_score = (len(matched_skills) / len(required_skills) * 70) if required_skills else 35.0
                project_score = min(len(projects_by_student.get(student.id, [])), 3) / 3 * 15
                education_score = 15.0 if student.degree else 0.0
                score = round(min(100.0, skill_score + project_score + education_score), 2)
                explanation = (
                    f"Matched {len(matched_skills)} of {len(required_skills)} configured required skills; "
                    f"profile lists {len(projects_by_student.get(student.id, []))} projects. "
                    + ("Eligible under the configured hard filters." if is_eligible else "Eligibility review needed: " + "; ".join(reasons) + ".")
                )
                existing = await db.scalar(select(Match).where(Match.job_id == job.id, Match.student_id == student.id))
                values = dict(match_score=score, eligible=is_eligible, explanation=explanation,
                              evidence={"matched_skills": matched_skills, "required_skills": required_skills,
                                        "project_count": len(projects_by_student.get(student.id, [])),
                                        "degree_present": bool(student.degree), "eligibility_reasons": reasons},
                              skill_gaps=gaps, model_version="structured-rules-v1")
                if existing:
                    for key, value in values.items():
                        setattr(existing, key, value)
                else:
                    db.add(Match(job_id=job.id, student_id=student.id, **values))
                processed += 1
                eligible_count += int(is_eligible)
            await db.commit()
            return {"status": "completed", "job_id": job_id, "candidates_processed": processed, "eligible_candidates": eligible_count}
    try:
        return asyncio.run(run())
    except Exception as exc:
        logger.warning("Candidate matching failed type=%s", type(exc).__name__)
        raise self.retry(exc=exc)
    finally:
        # Celery is synchronous; each asyncio.run creates a fresh event loop.
        # Dispose pooled async connections so they are not reused across loops.
        asyncio.run(engine.dispose())
