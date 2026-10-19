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
            try:
                ranking_task = rank_job_applicants.delay(job_id)
                ranking_task_id = ranking_task.id
            except Exception as queue_error:
                logger.warning("Ranking task could not be queued job_id=%s error_type=%s", job_id, type(queue_error).__name__)
                ranking_task_id = None
            return {"status": "completed", "job_id": job_id, "candidates_processed": processed,
                    "eligible_candidates": eligible_count, "ranking_task_id": ranking_task_id}
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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, name="app.tasks.rank_job_applicants")
def rank_job_applicants(self, job_id: str) -> dict[str, object]:
    """Score applicants from available job-related evidence and recommend a review shortlist."""
    import asyncio
    import uuid
    from sqlalchemy import func, select
    from app.db.session import AsyncSessionLocal, engine
    from app.models import (
        Application, Assessment, AssessmentAttempt, AssessmentInvite, Job, JobEvalConfig,
        JobStatus, Match, Ranking, Resume, Score, ScoreBreakdown, Shortlist, Student,
        StudentProject, StudentSkill, User,
    )

    parsed_job_id = uuid.UUID(job_id)

    async def run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            job = await db.scalar(select(Job).where(
                Job.id == parsed_job_id, Job.status == JobStatus.PUBLISHED, Job.deleted_at.is_(None)
            ))
            if not job:
                return {"status": "skipped", "reason": "job_not_published"}

            applications = list((await db.scalars(select(Application).where(
                Application.job_id == job.id, Application.withdrawn_at.is_(None)
            ))).all())
            if not applications:
                return {"status": "completed", "job_id": job_id, "ranked_applicants": 0, "shortlist_recommendations": 0}

            config = await db.scalar(select(JobEvalConfig).where(JobEvalConfig.job_id == job.id))
            weights = (config.weights if config and config.weights else {
                "aptitude": 0.20, "coding": 0.30, "skills": 0.20, "projects": 0.10, "resume": 0.20
            })
            assessment_types = set((await db.scalars(select(Assessment.assessment_type).where(
                Assessment.job_id == job.id, Assessment.active.is_(True)
            ))).all())
            has_aptitude = any(kind in {"APTITUDE", "MIXED"} for kind in assessment_types)
            has_coding = any(kind in {"CODING", "MIXED"} for kind in assessment_types)

            students = list((await db.scalars(select(Student).where(
                Student.id.in_([app.student_id for app in applications])
            ))).all())
            student_by_id = {student.id: student for student in students}
            matches = list((await db.scalars(select(Match).where(Match.job_id == job.id))).all())
            match_by_student = {match.student_id: match for match in matches}
            skills = list((await db.scalars(select(StudentSkill).where(
                StudentSkill.student_id.in_(list(student_by_id))
            ))).all())
            projects = list((await db.scalars(select(StudentProject).where(
                StudentProject.student_id.in_(list(student_by_id))
            ))).all())
            resumes = set((await db.scalars(select(Resume.student_id).where(
                Resume.student_id.in_(list(student_by_id))
            ))).all())
            skills_by_student: dict[uuid.UUID, set[str]] = {}
            projects_by_student: dict[uuid.UUID, int] = {}
            for skill in skills:
                skills_by_student.setdefault(skill.student_id, set()).add(skill.skill.strip().lower())
            for project in projects:
                projects_by_student[project.student_id] = projects_by_student.get(project.student_id, 0) + 1

            required_skills = [str(s).strip().lower() for s in (job.requirements or {}).get("skills", []) if str(s).strip()]
            aptitude_scores: dict[uuid.UUID, list[float]] = {}
            coding_scores: dict[uuid.UUID, list[float]] = {}
            for application in applications:
                rows = (await db.execute(
                    select(Assessment.assessment_type, AssessmentAttempt.score, AssessmentAttempt.result_summary)
                    .join(AssessmentInvite, AssessmentInvite.assessment_id == Assessment.id)
                    .join(AssessmentAttempt, AssessmentAttempt.assessment_invite_id == AssessmentInvite.id)
                    .where(AssessmentInvite.application_id == application.id,
                           AssessmentAttempt.status == "SUBMITTED")
                )).all()
                for kind, attempt_score, summary in rows:
                    summary = summary or {}
                    if kind == "APTITUDE":
                        value = float(attempt_score or 0)
                        aptitude_scores.setdefault(application.student_id, []).append(value)
                    elif kind == "CODING":
                        value = float(attempt_score or 0)
                        coding_scores.setdefault(application.student_id, []).append(value)
                    elif kind == "MIXED":
                        aptitude_part = summary.get("aptitude")
                        coding_part = summary.get("coding")
                        if aptitude_part and aptitude_part.get("score") is not None:
                            aptitude_scores.setdefault(application.student_id, []).append(float(aptitude_part["score"]))
                        if coding_part and coding_part.get("score") is not None:
                            coding_scores.setdefault(application.student_id, []).append(float(coding_part["score"]))

            latest_version = await db.scalar(select(func.max(Ranking.snapshot_version)).where(Ranking.job_id == job.id)) or 0
            snapshot_version = int(latest_version) + 1
            scored: list[tuple[Application, float, dict[str, dict[str, float]]]] = []
            for application in applications:
                student = student_by_id.get(application.student_id)
                if not student:
                    continue
                student_skills = skills_by_student.get(student.id, set())
                matched = student_skills.intersection(required_skills)
                skill_score = (len(matched) / len(set(required_skills)) * 100) if required_skills else min(100.0, len(student_skills) * 10.0)
                project_count = projects_by_student.get(student.id, 0)
                project_score = min(project_count, 3) / 3 * 100
                components: dict[str, dict[str, float]] = {
                    "skills": {"score": round(skill_score, 2), "weight": float(weights.get("skills", 0.20))},
                    "projects": {"score": round(project_score, 2), "weight": float(weights.get("projects", 0.10))},
                }
                if has_aptitude:
                    vals = aptitude_scores.get(student.id, [])
                    components["aptitude"] = {"score": round(sum(vals) / len(vals), 2) if vals else 0.0,
                                              "weight": float(weights.get("aptitude", 0.20))}
                if has_coding:
                    vals = coding_scores.get(student.id, [])
                    components["coding"] = {"score": round(sum(vals) / len(vals), 2) if vals else 0.0,
                                            "weight": float(weights.get("coding", 0.30))}
                if resumes:
                    components["resume"] = {"score": 100.0 if student.id in resumes else 0.0,
                                            "weight": float(weights.get("resume", 0.20))}
                valid = {key: value for key, value in components.items() if value["weight"] > 0}
                weight_sum = sum(value["weight"] for value in valid.values())
                total_score = round(sum(value["score"] * value["weight"] for value in valid.values()) / weight_sum, 2) if weight_sum else 0.0
                scored.append((application, total_score, valid))

            scored.sort(key=lambda item: (-item[1], item[0].created_at))
            top_count = min(len(scored), max(5, int(job.openings or 1) * 5))
            recommended_ids = {item[0].id for item in scored[:top_count]}
            existing_shortlists = {item.application_id: item for item in (await db.scalars(
                select(Shortlist).where(Shortlist.application_id.in_([app.id for app, _, _ in scored]))
            )).all()}

            for rank, (application, total_score, components) in enumerate(scored, start=1):
                score = Score(
                    application_id=application.id, total_score=total_score, scoring_version="job-rank-v1",
                    explanation="Job-specific score based on available skills, project, assessment, and resume evidence.",
                    calculated_from={"snapshot_version": snapshot_version, "weights": {key: val["weight"] for key, val in components.items()}},
                )
                db.add(score)
                await db.flush()
                for criterion, values in components.items():
                    db.add(ScoreBreakdown(
                        score_id=score.id, criterion=criterion, raw_score=values["score"],
                        weight=values["weight"], contribution=round(values["score"] * values["weight"], 2),
                        evidence={"source": "profile_or_completed_assessment"},
                    ))
                db.add(Ranking(job_id=job.id, application_id=application.id, score_id=score.id,
                               rank=rank, snapshot_version=snapshot_version))
                recommended = application.id in recommended_ids
                shortlist = existing_shortlists.get(application.id)
                if shortlist:
                    if shortlist.decision not in {"APPROVED", "REJECTED"}:
                        shortlist.recommended = recommended
                        shortlist.decision = "PENDING_REVIEW" if recommended else "NOT_RECOMMENDED"
                else:
                    db.add(Shortlist(job_id=job.id, application_id=application.id, recommended=recommended,
                                     decision="PENDING_REVIEW" if recommended else "NOT_RECOMMENDED"))
            await db.commit()
            return {"status": "completed", "job_id": job_id, "ranked_applicants": len(scored),
                    "snapshot_version": snapshot_version, "shortlist_recommendations": len(recommended_ids)}

    try:
        return asyncio.run(run())
    except Exception as exc:
        logger.warning("Applicant ranking failed job_id=%s error_type=%s", job_id, type(exc).__name__)
        raise self.retry(exc=exc)
    finally:
        asyncio.run(engine.dispose())
