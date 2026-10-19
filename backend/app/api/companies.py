from datetime import datetime, timezone
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    AccountStatus, Company, CompanyJoinRequest, CompanyMember, User, UserRole,
)

router = APIRouter(prefix="/companies", tags=["companies"])


def slugify(value: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "company")[:220]


async def _active_membership(db: AsyncSession, user: User):
    row = await db.execute(
        select(CompanyMember, Company).join(Company, Company.id == CompanyMember.company_id)
        .where(CompanyMember.user_id == user.id, CompanyMember.active.is_(True), Company.suspended.is_(False))
        .order_by(CompanyMember.created_at.asc())
    )
    return row.first()


async def _owner_company(db: AsyncSession, user: User) -> Company:
    row = await _active_membership(db, user)
    if not row:
        raise HTTPException(status_code=403, detail="You are not an active member of a company. Request to join a company first.")
    membership, company = row
    if membership.sub_role.upper() not in {"OWNER", "ADMIN"}:
        raise HTTPException(status_code=403, detail="Only company owners or admins can manage company members.")
    return company


class JoinRequestCreate(BaseModel):
    company_id: UUID
    message: str | None = Field(default=None, max_length=1000)


class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    website: str | None = Field(default=None, max_length=500)
    owner_name: str = Field(min_length=2, max_length=160)
    owner_email: EmailStr
    temporary_password: str = Field(min_length=12, max_length=128)


class AddMemberRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    temporary_password: str = Field(min_length=12, max_length=128)
    sub_role: str = Field(default="HR", pattern="^(HR|RECRUITER|ADMIN)$")


@router.get("/directory")
async def company_directory(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(
        select(Company).where(Company.suspended.is_(False)).order_by(Company.name.asc())
    )).all()
    return [{"id": str(c.id), "name": c.name, "slug": c.slug, "description": c.description,
             "website": c.website, "verified": c.verified} for c in rows]


@router.post("/join-requests", status_code=201)
async def request_company_membership(
    payload: JoinRequestCreate,
    user: User = Depends(require_roles(UserRole.COMPANY_HR)),
    db: AsyncSession = Depends(get_db),
):
    if await _active_membership(db, user):
        raise HTTPException(status_code=409, detail="This account already belongs to a company.")
    company = await db.scalar(select(Company).where(Company.id == payload.company_id, Company.suspended.is_(False)))
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    existing = await db.scalar(select(CompanyJoinRequest).where(
        CompanyJoinRequest.company_id == company.id, CompanyJoinRequest.user_id == user.id
    ))
    if existing:
        if existing.status == "PENDING":
            return {"id": str(existing.id), "status": existing.status, "message": "Your request is already pending."}
        if existing.status == "APPROVED":
            raise HTTPException(status_code=409, detail="Your request has already been approved.")
        existing.status = "PENDING"
        existing.message = payload.message
        existing.reviewed_by = None
        existing.reviewed_at = None
        await db.commit()
        return {"id": str(existing.id), "status": existing.status}
    request = CompanyJoinRequest(company_id=company.id, user_id=user.id, message=payload.message, status="PENDING")
    db.add(request)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A join request already exists.")
    await db.refresh(request)
    return {"id": str(request.id), "status": request.status, "company": company.name}


@router.get("/my-membership")
async def my_company_membership(user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    row = await _active_membership(db, user)
    if row:
        membership, company = row
        return {"has_company": True, "company": {"id": str(company.id), "name": company.name, "slug": company.slug},
                "sub_role": membership.sub_role, "can_manage_members": membership.sub_role.upper() in {"OWNER", "ADMIN"}}
    request = await db.scalar(select(CompanyJoinRequest).where(
        CompanyJoinRequest.user_id == user.id, CompanyJoinRequest.status == "PENDING"
    ).order_by(CompanyJoinRequest.created_at.desc()))
    if request:
        company = await db.get(Company, request.company_id)
        return {"has_company": False, "pending_request": {"id": str(request.id), "company_name": company.name if company else "Company"}}
    return {"has_company": False, "pending_request": None}


@router.get("/mine/members")
async def list_company_members(user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company = await _owner_company(db, user)
    rows = (await db.execute(
        select(CompanyMember, User).join(User, User.id == CompanyMember.user_id)
        .where(CompanyMember.company_id == company.id, CompanyMember.active.is_(True))
        .order_by(CompanyMember.sub_role.asc(), User.full_name.asc())
    )).all()
    return [{"membership_id": str(m.id), "user_id": str(u.id), "full_name": u.full_name,
             "email": u.email, "sub_role": m.sub_role, "must_change_password": u.must_change_password}
            for m, u in rows]


@router.get("/mine/join-requests")
async def list_join_requests(user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company = await _owner_company(db, user)
    rows = (await db.execute(
        select(CompanyJoinRequest, User).join(User, User.id == CompanyJoinRequest.user_id)
        .where(CompanyJoinRequest.company_id == company.id, CompanyJoinRequest.status == "PENDING")
        .order_by(CompanyJoinRequest.created_at.asc())
    )).all()
    return [{"id": str(r.id), "user_id": str(u.id), "full_name": u.full_name, "email": u.email,
             "message": r.message, "created_at": r.created_at.isoformat()} for r, u in rows]


@router.post("/mine/join-requests/{request_id}/approve")
async def approve_join_request(request_id: UUID, user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company = await _owner_company(db, user)
    request = await db.scalar(select(CompanyJoinRequest).where(
        CompanyJoinRequest.id == request_id, CompanyJoinRequest.company_id == company.id
    ))
    if not request:
        raise HTTPException(status_code=404, detail="Join request not found.")
    if request.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Request is already {request.status.lower()}.")
    applicant = await db.get(User, request.user_id)
    if not applicant or applicant.role != UserRole.COMPANY_HR or applicant.status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="The requesting HR account is not active.")
    current_membership = await db.scalar(select(CompanyMember).where(
        CompanyMember.user_id == applicant.id, CompanyMember.active.is_(True)
    ))
    if current_membership:
        raise HTTPException(status_code=409, detail="This HR account already belongs to a company.")
    db.add(CompanyMember(company_id=company.id, user_id=applicant.id, sub_role="HR", permissions=["JOBS_READ", "JOBS_WRITE", "CANDIDATES_READ"]))
    request.status = "APPROVED"
    request.reviewed_by = user.id
    request.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "APPROVED", "company": company.name, "member_email": applicant.email}


@router.post("/mine/join-requests/{request_id}/reject")
async def reject_join_request(request_id: UUID, user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company = await _owner_company(db, user)
    request = await db.scalar(select(CompanyJoinRequest).where(
        CompanyJoinRequest.id == request_id, CompanyJoinRequest.company_id == company.id
    ))
    if not request:
        raise HTTPException(status_code=404, detail="Join request not found.")
    if request.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Request is already {request.status.lower()}.")
    request.status = "REJECTED"
    request.reviewed_by = user.id
    request.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "REJECTED"}


@router.post("/mine/members", status_code=201)
async def add_company_member(payload: AddMemberRequest, user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company = await _owner_company(db, user)
    email = str(payload.email).lower().strip()
    existing = await db.scalar(select(User).where(func.lower(User.email) == email))
    if existing:
        if existing.role != UserRole.COMPANY_HR:
            raise HTTPException(status_code=409, detail="That email already belongs to a non-HR account.")
        if existing.status != AccountStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="That HR account is not active.")
        active_membership = await db.scalar(select(CompanyMember).where(
            CompanyMember.user_id == existing.id, CompanyMember.active.is_(True)
        ))
        if active_membership:
            raise HTTPException(status_code=409, detail="That HR account already belongs to a company.")
        member = existing
    else:
        member = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.temporary_password),
                      role=UserRole.COMPANY_HR, status=AccountStatus.ACTIVE, must_change_password=True)
        db.add(member)
        await db.flush()
    db.add(CompanyMember(company_id=company.id, user_id=member.id, sub_role=payload.sub_role,
                         permissions=["JOBS_READ", "JOBS_WRITE", "CANDIDATES_READ"] if payload.sub_role != "ADMIN" else ["*"]))
    await db.commit()
    return {"status": "created", "company": company.name, "email": member.email,
            "temporary_password_must_be_changed": True}


@router.delete("/mine/members/{user_id}")
async def remove_company_member(user_id: UUID, user: User = Depends(require_roles(UserRole.COMPANY_HR)), db: AsyncSession = Depends(get_db)):
    company = await _owner_company(db, user)
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot remove your own owner account.")
    member = await db.scalar(select(CompanyMember).where(
        CompanyMember.company_id == company.id, CompanyMember.user_id == user_id, CompanyMember.active.is_(True)
    ))
    if not member:
        raise HTTPException(status_code=404, detail="Active company member not found.")
    if member.sub_role.upper() == "OWNER":
        raise HTTPException(status_code=409, detail="Transfer ownership before removing the owner.")
    member.active = False
    await db.commit()
    return {"status": "removed", "user_id": str(user_id)}


@router.post("/admin/create", status_code=201)
async def admin_create_company(payload: CompanyCreate, user: User = Depends(require_roles(UserRole.ADMIN)), db: AsyncSession = Depends(get_db)):
    name = payload.name.strip()
    slug = slugify(name)
    existing_company = await db.scalar(select(Company).where(func.lower(Company.name) == name.lower()))
    if existing_company:
        raise HTTPException(status_code=409, detail="A company with this name already exists.")
    email = str(payload.owner_email).lower().strip()
    existing_user = await db.scalar(select(User).where(func.lower(User.email) == email))
    if existing_user:
        raise HTTPException(status_code=409, detail="The owner email is already in use.")
    if await db.scalar(select(Company.id).where(Company.slug == slug)):
        raise HTTPException(status_code=409, detail="A company with this slug already exists.")
    company = Company(name=name, slug=slug, description=payload.description, website=payload.website, verified=True)
    db.add(company)
    owner = User(email=email, full_name=payload.owner_name.strip(), password_hash=hash_password(payload.temporary_password),
                 role=UserRole.COMPANY_HR, status=AccountStatus.ACTIVE, must_change_password=True)
    db.add(owner)
    await db.flush()
    db.add(CompanyMember(company_id=company.id, user_id=owner.id, sub_role="OWNER", permissions=["*"]))
    await db.commit()
    return {"company_id": str(company.id), "company": company.name, "owner_email": owner.email,
            "temporary_password_must_be_changed": True, "created_by": str(user.id)}
