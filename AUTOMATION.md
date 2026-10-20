# TalentOS recruitment automation

## Scheduled runner (no paid Render worker required)

The repository includes a GitHub Actions workflow at `.github/workflows/scheduled-automation.yml`. It runs every 15 minutes and can also be started manually from GitHub Actions. It connects directly to Neon and runs the automation and stale matching/ranking task bodies inline; it does not require a continuously running Render background worker or Redis queue for this scheduled workflow.

### Required GitHub Actions secrets

Open GitHub → `Hrsht02/TalentOS` → Settings → Secrets and variables → Actions → New repository secret.

- `NEON_DATABASE_URL`: Neon connection string for the same project, branch, and database used by the Render API. Use the connection string format supported by the app (the settings normalizer converts `postgresql://` to asyncpg format).
- `TALENTOS_SECRET_KEY`: the same strong random secret used as `SECRET_KEY` in Render. Do not commit either value to the repository.

The runner checks that the database secret is present and does not point to localhost before starting. Never put database credentials in workflow YAML, source code, or logs.

### Run it

1. Add both repository secrets.
2. Open GitHub → Actions → **TalentOS Scheduled Automation**.
3. Select **Run workflow** to test immediately.
4. Open the run and inspect its logs for `TALENTOS_AUTOMATION_RESULT=` and the counts.
5. The workflow also runs every 15 minutes. GitHub scheduled jobs use UTC and may start later than the exact minute during periods of load; manual dispatch is available for testing.

The API admin endpoint can also run the automation inline. This can take time on a large database and may be subject to HTTP request timeouts, so the scheduled workflow is preferred.

## What the automation does

- Closes published jobs after their deadlines.
- Marks assessment invites expired after their deadlines.
- Creates in-app notifications for expired assessments.
- Creates in-app reminders approximately 24 hours before scheduled interviews.
- Refreshes stale matching for published jobs.
- Refreshes ranking for published jobs with applications.

Matching and ranking run inline in the GitHub Actions runner, rather than being queued for a Celery worker. The workflow therefore does not rely on Render Redis for its scheduled execution. Other app features that still enqueue Celery tasks through Redis will not run unless a worker is available; those need to be adapted to inline execution or a separately hosted worker.

## Current boundaries

- Notifications are stored in-app; no email/SMS/push delivery provider is configured.
- Interview reminders require an interview record already scheduled in TalentOS.
- Candidate applications are not submitted automatically without candidate authorization.
- Matching/ranking provides recommendations; final shortlisting, interviews, offers, and hiring decisions remain under human control.
- The workflow is guarded by GitHub Actions concurrency to prevent overlapping scheduled runs.
