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



@celery_app.task(bind=True, max_retries=2, default_retry_delay=15, name="app.tasks.evaluate_coding_submission")
def evaluate_coding_submission(self, submission_id: str) -> dict[str, object]:
    """Evaluate one submission through a configured Judge0-compatible sandbox API."""
    import asyncio
    import base64
    import time
    import uuid
    import httpx
    from sqlalchemy import select
    from app.core.config import settings
    from app.db.session import AsyncSessionLocal, engine
    from app.models import CodingQuestion, Submission, SubmissionResult, SubmissionStatus, TestCase

    language_ids = {"python": 71, "cpp": 54, "java": 62, "javascript": 63}
    parsed_id = uuid.UUID(submission_id)

    async def run() -> dict[str, object]:
        try:
            if not settings.judge0_api_url:
                raise RuntimeError("JUDGE0_API_URL is not configured")
            async with AsyncSessionLocal() as db:
                submission = await db.scalar(select(Submission).where(Submission.id == parsed_id))
                if not submission:
                    return {"status": "skipped", "reason": "submission_not_found"}
                question = await db.scalar(select(CodingQuestion).where(CodingQuestion.id == submission.coding_question_id))
                cases = list((await db.scalars(select(TestCase).where(
                    TestCase.coding_question_id == submission.coding_question_id
                ).order_by(TestCase.position.asc()).limit(50))).all())
                if not question or not cases:
                    raise RuntimeError("Coding question or its test cases are missing")
                if submission.language not in language_ids:
                    raise RuntimeError("Unsupported coding language")
                submission.status = SubmissionStatus.RUNNING
                await db.commit()
                source_code = submission.source_code
                language = submission.language
                time_limit_ms = question.time_limit_ms
                memory_limit_mb = question.memory_limit_mb
                case_data = [{
                    "id": str(case.id), "input": case.input_data, "expected": case.expected_output,
                    "weight": max(0.0, case.weight),
                } for case in cases]

            base_url = settings.judge0_api_url.rstrip("/")
            headers = {"Content-Type": "application/json"}
            if settings.judge0_api_key:
                headers["X-Auth-Token"] = settings.judge0_api_key
            deadline = time.monotonic() + max(10, settings.judge0_timeout_seconds)
            summaries, verdicts = [], []
            passed_count, passed_weight = 0, 0.0
            total_weight = sum(case["weight"] for case in case_data)
            with httpx.Client(timeout=10.0, headers=headers) as client:
                for case in case_data:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Judge0 evaluation exceeded its configured total time budget")
                    payload = {
                        "source_code": base64.b64encode(source_code.encode()).decode(),
                        "language_id": language_ids[language],
                        "stdin": base64.b64encode(case["input"].encode()).decode(),
                        "expected_output": base64.b64encode(case["expected"].encode()).decode(),
                        "cpu_time_limit": max(0.1, time_limit_ms / 1000),
                        "memory_limit": memory_limit_mb * 1024,
                    }
                    response = client.post(base_url + "/submissions",
                        params={"base64_encoded": "true", "wait": "false"}, json=payload)
                    response.raise_for_status()
                    token = response.json().get("token")
                    if not token:
                        raise RuntimeError("Judge0 did not return a submission token")
                    result = None
                    while time.monotonic() < deadline:
                        poll = client.get(base_url + "/submissions/" + token,
                            params={"base64_encoded": "true", "fields": "status,stdout,stderr,compile_output,time,memory"})
                        poll.raise_for_status()
                        result = poll.json()
                        status = result.get("status") or {}
                        if status.get("id", 0) not in (1, 2):
                            break
                        time.sleep(max(0.25, settings.judge0_poll_interval_seconds))
                    if not result or (result.get("status") or {}).get("id") in (1, 2):
                        raise TimeoutError("Judge0 did not finish before the evaluation time budget")
                    status = result.get("status") or {}
                    status_id = status.get("id")
                    accepted = status_id == 3
                    passed_count += int(accepted)
                    passed_weight += case["weight"] if accepted else 0.0
                    verdict = status.get("description", "Unknown")
                    verdicts.append(verdict)
                    summaries.append({
                        "test_case_id": case["id"], "status_id": status_id,
                        "status": verdict, "passed": accepted,
                        "runtime": result.get("time"), "memory": result.get("memory"),
                    })
                    if status_id in (6, 13, 14):
                        break

            score = round((passed_weight / total_weight) * 100, 2) if total_weight else 0.0
            all_tests_finished = len(summaries) == len(case_data)
            verdict = "ACCEPTED" if all_tests_finished and summaries and all(t["passed"] for t in summaries) else (
                "PARTIAL" if passed_count else (verdicts[-1].upper().replace(" ", "_") if verdicts else "ERROR")
            )
            runtimes = [float(item["runtime"]) for item in summaries if item["runtime"] is not None]
            memories = [int(item["memory"]) for item in summaries if item["memory"] is not None]
            async with AsyncSessionLocal() as db:
                submission = await db.scalar(select(Submission).where(Submission.id == parsed_id))
                if not submission:
                    return {"status": "skipped", "reason": "submission_disappeared"}
                existing = await db.scalar(select(SubmissionResult).where(SubmissionResult.submission_id == parsed_id))
                values = {
                    "score": score, "passed_count": passed_count, "total_count": len(case_data),
                    "runtime_ms": int(max(runtimes) * 1000) if runtimes else None,
                    "memory_kb": max(memories) if memories else None, "verdict": verdict,
                    "result_details": {"tests": summaries},
                }
                if existing:
                    for key, value in values.items():
                        setattr(existing, key, value)
                else:
                    db.add(SubmissionResult(submission_id=parsed_id, **values))
                submission.status = SubmissionStatus.COMPLETED
                await db.commit()
            logger.info("Coding evaluation completed submission_id=%s verdict=%s", submission_id, verdict)
            return {"status": "completed", "submission_id": submission_id, "verdict": verdict, "score": score}
        except Exception:
            # Persist terminal failure only when Celery has exhausted its retries.
            if self.request.retries >= self.max_retries:
                async with AsyncSessionLocal() as db:
                    submission = await db.scalar(select(Submission).where(Submission.id == parsed_id))
                    if submission:
                        submission.status = SubmissionStatus.FAILED
                        await db.commit()
            raise

    try:
        try:
            return asyncio.run(run())
        except Exception as exc:
            logger.warning("Coding evaluation failed submission_id=%s error_type=%s", submission_id, type(exc).__name__)
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc)
            raise
    finally:
        asyncio.run(engine.dispose())
