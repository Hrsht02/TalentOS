# TalentOS

Autonomous AI-powered recruitment platform connecting students, companies, and recruitment agencies.

## Deployment architecture

- **Frontend:** React 18 + Vite on Vercel
- **Backend:** FastAPI on Render
- **Database:** Managed PostgreSQL with pgvector
- **Background jobs:** Redis + Celery worker and scheduler on Render
- **AI providers:** Gemini primary/fallback accounts and xAI Grok provider, configured by environment variables
- **Coding assessments:** Separate isolated judge service; student code is never executed inside the API
- **Containers:** Docker and Docker Compose are intentionally not used.

## Current implementation status

Phase 0: Architecture and requirements completed.
Phase 1: Initial database models and Alembic migration committed.
Phase 2: Initial JWT login/registration, admin overview, and temporary admin password change implemented.
Phase 3: Initial published job listing, employer draft/publish workflow, student applications, and student profile/skills/projects APIs implemented.
Frontend foundation: Login/register, responsive dashboards, job management, student profile editor, and Vercel SPA routing committed.
AI foundation: Gemini key 1 -> Gemini key 2 -> xAI Grok failover router and Celery task entrypoints committed.

These are early implementation slices, not a production-complete recruitment platform. Email verification, refresh-token rotation, full tenant policy tests, resume upload, assessment scheduling/evaluation, AI matching workflows, and isolated coding-judge integration remain in progress.

## Local development

Requires Python 3.11+ and a PostgreSQL instance with the pgvector extension available.

1. Create and activate a virtual environment.
2. Install backend dependencies: `pip install -r backend/requirements.txt`.
3. Copy `backend/.env.example` to `backend/.env` and set local database credentials.
4. From the repository root, run migrations with `cd backend && alembic upgrade head`.
5. Seed the development admin: `cd backend && python -m app.scripts.seed_admin`.

Do not commit `.env` files or credentials.

## Admin seed security

Development defaults are provided for convenience only. Change `ADMIN_SEED_EMAIL` and `ADMIN_SEED_PASSWORD` before any public deployment. The seed stores only a password hash and sets `must_change_password`. Do not expose seeded credentials in production.

## Deployment

- Configure Vercel with root directory `frontend`, build command `npm run build`, output directory `dist`.
- Configure a Render Python web service with root directory `backend` and start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT` once the API entrypoint is added.
- Configure a separate Render worker service for Celery after queue tasks are added.
- Set secrets using Render/Vercel environment settings. Never put API keys in source control.
- Run Alembic migrations as an explicit release/deploy step. Back up PostgreSQL before production migrations.

## AI provider failover

The intended provider chain is Gemini account/key 1 -> Gemini account/key 2 -> xAI Grok. Provider routing must detect quota/rate-limit and transient availability errors, apply bounded retries/timeouts and a cooldown per key, and continue to the next configured provider. Authentication errors and malformed requests should be surfaced rather than retried indefinitely. All provider keys are read from environment variables and must remain server-side.

## Hiring safety

AI produces recommendations and evidence-based explanations. It must not automatically reject or hire candidates. Human reviewers retain final decisions. Do not use protected characteristics in candidate scoring.


## Implemented API routes

- `GET /health` — liveness probe
- `GET /ready` — PostgreSQL readiness probe
- `POST /api/v1/auth/register` — student/company/agency registration (admin cannot self-register)
- `POST /api/v1/auth/login` — login and short-lived JWT
- `GET /api/v1/auth/me` — current authenticated user
- `POST /api/v1/auth/change-password` — change password, including seeded admin's first-login password
- `GET /api/v1/admin/overview` — protected admin counts
- `GET /api/v1/jobs` — published jobs
- `POST /api/v1/jobs` — company member creates a draft
- `GET /api/v1/jobs/mine` — jobs belonging to the user's company
- `POST /api/v1/jobs/{job_id}/publish` — publish a draft
- `POST /api/v1/jobs/{job_id}/apply` — student applies to a published job
- `GET /api/v1/student/profile` and `PATCH /api/v1/student/profile`
- `POST/DELETE /api/v1/student/profile/skills` — add/update or remove skills
- `POST/DELETE /api/v1/student/profile/projects` — add or remove projects

## Deploying the frontend on Vercel

1. Import `Hrsht02/TalentOS` in Vercel.
2. Set Root Directory to `frontend`.
3. Framework preset: Vite; Build Command: `npm run build`; Output Directory: `dist`.
4. Add `VITE_API_BASE_URL=https://YOUR-RENDER-SERVICE.onrender.com/api/v1`.
5. Deploy, then add the exact Vercel domain to Render's `FRONTEND_URL` and `CORS_ORIGINS`.

## Deploying the API on Render

1. Create a managed PostgreSQL database and a Redis instance.
2. Create a Python web service from this repository; Root Directory: `backend`.
3. Build Command: `pip install -r requirements.txt`.
4. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
5. Configure `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `FRONTEND_URL`, `CORS_ORIGINS`, and the provider API keys in Render's environment settings.
6. Run `alembic upgrade head` from the backend directory as a one-off/release step, then run `python -m app.scripts.seed_admin` once using a strong, unique `ADMIN_SEED_PASSWORD`.
7. Add a separate Render background worker with start command `celery -A app.worker.celery_app worker --loglevel=info` when using queued AI tasks.

Do not commit secrets. Before production, add email verification, refresh-token rotation, rate limiting, tenant-isolation tests, database backups, and monitoring. The repository is not yet production-ready.
