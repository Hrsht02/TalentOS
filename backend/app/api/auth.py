from datetime import datetime, timezone
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import AccountStatus, Agency, AgencyMember, Company, CompanyMember, Student, User, UserRole
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])
PUBLIC_ROLES = {UserRole.STUDENT, UserRole.COMPANY_HR, UserRole.AGENCY_MEMBER}


def slugify(value: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "organization")[:200]


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if payload.role not in PUBLIC_ROLES:
        raise HTTPException(status_code=403, detail="This role cannot be self-registered")
    if payload.role != UserRole.STUDENT and not payload.organization_name:
        raise HTTPException(status_code=422, detail="organization_name is required for this account type")
    email = str(payload.email).lower().strip()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password),
                role=payload.role, status=AccountStatus.ACTIVE)
    db.add(user)
    try:
        await db.flush()
        if payload.role == UserRole.STUDENT:
            db.add(Student(user_id=user.id))
        elif payload.role == UserRole.COMPANY_HR:
            slug = slugify(payload.organization_name or "company")
            if await db.scalar(select(Company.id).where(Company.slug == slug)):
                slug = f"{slug}-{str(user.id)[:8]}"
            tenant = Company(name=payload.organization_name or "Company", slug=slug)
            db.add(tenant)
            await db.flush()
            db.add(CompanyMember(company_id=tenant.id, user_id=user.id, sub_role="OWNER", permissions=["*"]))
        else:
            slug = slugify(payload.organization_name or "agency")
            if await db.scalar(select(Agency.id).where(Agency.slug == slug)):
                slug = f"{slug}-{str(user.id)[:8]}"
            tenant = Agency(name=payload.organization_name or "Agency", slug=slug)
            db.add(tenant)
            await db.flush()
            db.add(AgencyMember(agency_id=tenant.id, user_id=user.id, sub_role="OWNER", permissions=["*"]))
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Account or organization already exists")
    return TokenResponse(access_token=create_access_token(str(user.id), user.role.value),
                         expires_in=settings.access_token_minutes * 60, user=user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = str(payload.email).lower().strip()
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is not active")
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id), user.role.value),
                         expires_in=settings.access_token_minutes * 60, user=user)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user



@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not user.password_hash or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=422, detail="New password must be different")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    await db.commit()
    return {"status": "ok", "message": "Password updated"}
