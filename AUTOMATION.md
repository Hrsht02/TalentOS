# TalentOS recruitment automation

## What runs automatically

The Celery worker now loads `app.automation` and includes a Celery Beat schedule every 15 minutes. The periodic pass:

- Closes published jobs after their deadline.
- Marks assessment invites expired after their deadline.
- Creates an in-app notification for an expired assessment.
- Creates an in-app reminder roughly 24 hours before a scheduled interview.
- Re-queues stale candidate matching for published jobs (at most daily per job based on match update timestamps).
- Re-queues ranking refreshes for published jobs that have applications (at most daily per job based on ranking snapshot timestamps).

Job publication and application/assessment changes also use existing event-triggered matching and ranking tasks. Candidate matching is based on profile evidence and configured eligibility. Ranking generates recommendations; it does not automatically reject candidates, approve a shortlist, or make a hiring decision.

## Deployment requirements

1. Render API must have the correct Neon `DATABASE_URL`.
2. Render worker must have the same `DATABASE_URL` and a working `REDIS_URL`.
3. The worker process must run Celery Beat. For the Render worker Start Command, use:

   ```bash
   celery -A app.worker.celery_app worker --beat --loglevel=info --concurrency=2
   ```

   If the worker is already managed through the dashboard rather than a Blueprint, changing `render.yaml` alone does not change its current Start Command; update the service settings manually.
4. Deploy the backend commit, then deploy the frontend commit on Vercel.
5. As the platform administrator, use **Run automation now** on the dashboard to queue a one-off pass. Check Render worker logs to confirm completion.
6. Open **Notifications** from the sidebar or bell to view and mark in-app notifications as read.

## Current boundaries

- The automation is in-app; it does not send email/SMS/push notifications without a configured delivery provider.
- Interview reminders require an interview record already scheduled in TalentOS.
- Auto-apply is intentionally not enabled. TalentOS must not submit applications without candidate authorization.
- Human HR/company users retain control over final shortlist approval, interviews, offers and hiring decisions.
- This scheduler is designed for a single Celery Beat instance. Do not run multiple beat schedulers against the same queue without configuring a distributed scheduler/lock.
