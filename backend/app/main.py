from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.db.session import engine
from app.core.config import settings
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.jobs import router as jobs_router
from app.api.profile import router as profile_router
from app.api.assessments import router as assessments_router

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Autonomous AI-powered recruitment platform API",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
)


app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix=settings.api_v1_prefix)
app.include_router(jobs_router, prefix=settings.api_v1_prefix)
app.include_router(profile_router, prefix=settings.api_v1_prefix)
app.include_router(assessments_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "talentos-api"}


@app.get("/ready", tags=["system"])
async def ready() -> dict[str, str]:
    # Fail readiness if PostgreSQL is unreachable.
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ready", "service": "talentos-api"}
