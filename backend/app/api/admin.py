from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_roles
from app.db.session import get_db
from app.models import AccountStatus, Application, Company, Job, Student, User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles(UserRole.ADMIN))])


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    async def count(model, *conditions):
        return await db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0

    return {
        "users": await count(User, User.deleted_at.is_(None)),
        "students": await count(Student),
        "companies": await count(Company),
        "jobs": await count(Job),
        "applications": await count(Application),
        "suspended_users": await count(User, User.status == AccountStatus.SUSPENDED),
    }
