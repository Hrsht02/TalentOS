"""Idempotently seed the single initial admin account.

WARNING: Change ADMIN_SEED_EMAIL and ADMIN_SEED_PASSWORD before production.
The development password is intentionally not suitable for a live deployment.
"""
import asyncio
from sqlalchemy import select
from pwdlib import PasswordHash
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models import AccountStatus, User, UserRole

password_hasher = PasswordHash.recommended()


async def seed_admin() -> None:
    email = settings.admin_seed_email.strip().lower()
    password = settings.admin_seed_password
    if not email or len(password) < 12:
        raise RuntimeError("Admin seed email must be set and password must be at least 12 characters.")
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing:
            if existing.role != UserRole.ADMIN:
                raise RuntimeError("Seed email already belongs to a non-admin account; refusing role escalation.")
            print(f"Admin account already exists; leaving it unchanged: {email}")
            return
        user = User(
            email=email,
            full_name="TalentOS Administrator",
            password_hash=password_hasher.hash(password),
            role=UserRole.ADMIN,
            status=AccountStatus.ACTIVE,
            must_change_password=True,
        )
        session.add(user)
        await session.commit()
        print(f"Seeded admin account {email}. Change its password immediately after first login.")


if __name__ == "__main__":
    asyncio.run(seed_admin())
