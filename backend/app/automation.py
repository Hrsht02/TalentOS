"""Periodic, idempotent recruitment workflow automation.

The periodic job handles deadline transitions and reminders, and refreshes stale
matching/ranking snapshots. It never submits applications on a candidate's behalf
and never finalizes a hiring decision.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, name="app.automation.run_recruitment_automation")
def run_recruitment_automation(self) -> dict[str, int]:
    """Run the periodic automation pass; safe to retry."""
    from app.db.session import AsyncSessionLocal, engine
    from app.models import (
        Application, Assessment, AssessmentInvite, AssessmentStatus, Interview,
        Job, JobStatus, Match, Notification, Ranking, Student, User,
    )

    now = datetime.now(timezone.utc)
    match_job_ids: list[str] = []
    rank_job_ids: list[str] = []
    counts = {"jobs_closed": 0, "invites_expired": 0, "notifications_created": 0,
              "matching_queued": 0, "ranking_queued": 0}

    async def run() -> None:
        async with AsyncSessionLocal() as db:
            # Close published jobs whose deadline has passed.
            expired_jobs = list((await db.scalars(select(Job).where(
                Job.status == JobStatus.PUBLISHED,
                Job.deadline.is_not(None),
                Job.deadline <= now,
                Job.deleted_at.is_(None),
            ))).all())
            for job in expired_jobs:
                job.status = JobStatus.CLOSED
                counts["jobs_closed"] += 1

            # Expire assessment invitations that passed their deadline.
            expired_invites = list((await db.scalars(select(AssessmentInvite).where(
                AssessmentInvite.status.in_([AssessmentStatus.SCHEDULED, AssessmentStatus.IN_PROGRESS]),
                AssessmentInvite.deadline <= now,
            ))).all())
            for invite in expired_invites:
                invite.status = AssessmentStatus.EXPIRED
                counts["invites_expired"] += 1
                application = await db.get(Application, invite.application_id)
                if application:
                    student_user_id = await db.scalar(select(Student.user_id).where(Student.id == application.student_id))
                    existing = await db.scalar(select(Notification.id).where(
                        Notification.user_id == student_user_id,
                        Notification.kind == "ASSESSMENT_EXPIRED",
                        Notification.payload["assessment_invite_id"].astext == str(invite.id),
                    ).limit(1)) if student_user_id else None
                    if student_user_id and not existing:
                        db.add(Notification(
                            user_id=student_user_id, kind="ASSESSMENT_EXPIRED",
                            title="Assessment window expired",
                            body="Your assessment window has ended. Check the assessment page for status or contact the recruiter if you believe this is incorrect.",
                            payload={"assessment_invite_id": str(invite.id), "job_id": str(application.job_id)},
                            delivery_status="PENDING",
                        ))
                        counts["notifications_created"] += 1

            # Send one in-app reminder per interview approximately 24 hours before it starts.
            reminder_start = now + timedelta(hours=23)
            reminder_end = now + timedelta(hours=25)
            interviews = (await db.execute(
                select(Interview, Application, Student.user_id)
                .join(Application, Application.id == Interview.application_id)
                .join(Student, Student.id == Application.student_id)
                .where(Interview.status == "SCHEDULED",
                       Interview.starts_at >= reminder_start,
                       Interview.starts_at < reminder_end)
            )).all()
            for interview, application, student_user_id in interviews:
                exists = await db.scalar(select(Notification.id).where(
                    Notification.user_id == student_user_id,
                    Notification.kind == "INTERVIEW_REMINDER",
                    Notification.payload["interview_id"].astext == str(interview.id),
                ).limit(1))
                if not exists:
                    db.add(Notification(
                        user_id=student_user_id, kind="INTERVIEW_REMINDER",
                        title="Interview coming up",
                        body=f"Your interview is scheduled for {interview.starts_at.isoformat()}. Check the interview details in TalentOS.",
                        payload={"interview_id": str(interview.id), "application_id": str(application.id)},
                        delivery_status="PENDING",
                    ))
                    counts["notifications_created"] += 1

            # Refresh matching at most once per day for published jobs.
            published_jobs = list((await db.scalars(select(Job).where(
                Job.status == JobStatus.PUBLISHED, Job.deleted_at.is_(None)
            ))).all())
            stale_before = now - timedelta(hours=24)
            for job in published_jobs:
                latest_match = await db.scalar(select(func.max(Match.updated_at)).where(Match.job_id == job.id))
                if latest_match is None or latest_match < stale_before:
                    match_job_ids.append(str(job.id))
                application_count = await db.scalar(select(func.count()).select_from(Application).where(
                    Application.job_id == job.id, Application.withdrawn_at.is_(None)
                )) or 0
                if application_count:
                    latest_rank = await db.scalar(select(func.max(Ranking.created_at)).where(Ranking.job_id == job.id))
                    if latest_rank is None or latest_rank < stale_before:
                        rank_job_ids.append(str(job.id))

            await db.commit()

    try:
        asyncio.run(run())
        # Run these tasks inline so the scheduled GitHub Actions runner can
        # execute automation without a permanently running Celery worker.
        # Celery's apply() executes locally and does not contact the broker.
        from app.tasks import match_candidates, rank_job_applicants
        for job_id in dict.fromkeys(match_job_ids):
            result = match_candidates.apply(args=[job_id], throw=True)
            result.get()
            counts["matching_queued"] += 1
        for job_id in dict.fromkeys(rank_job_ids):
            result = rank_job_applicants.apply(args=[job_id], throw=True)
            result.get()
            counts["ranking_queued"] += 1
        logger.info("Recruitment automation pass complete counts=%s", counts)
        return counts
    except Exception as exc:
        logger.warning("Recruitment automation pass failed error_type=%s", type(exc).__name__)
        raise self.retry(exc=exc)
    finally:
        asyncio.run(engine.dispose())
