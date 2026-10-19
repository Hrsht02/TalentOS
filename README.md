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
Phase 1: Database foundation and initial migration in progress.
Later phases will add authentication, domain APIs, AI matching, assessments, and frontend workflows.

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
