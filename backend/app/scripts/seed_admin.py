"""Create or reset the configured TalentOS admin account.

Run manually from the Render API service Shell after setting ADMIN_SEED_EMAIL and
ADMIN_SEED_PASSWORD in that service's environment. Never print or log passwords.
"""
import asyncio

from pwdlib import PasswordHash
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models import AccountStatus, User, UserRole

password_hasher = PasswordHash.recommended()


async def seed_admin() -> None:
    email = settings.admin_seed_email.strip().lower()
    password = settings.admin_seed_password
    if not email or len(password) < 16:
        raise RuntimeError("Set ADMIN_SEED_EMAIL and a unique ADMIN_SEED_PASSWORD of at least 16 characters.")

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))

        if user is not None:
            if user.role != UserRole.ADMIN:
                raise RuntimeError(
                    "Seed email already belongs to a non-admin account; refusing role escalation."
                )
            user.password_hash = password_hasher.hash(password)
            user.status = AccountStatus.ACTIVE
            user.must_change_password = True
            await session.commit()
            print(f"Reset password for existing admin account: {email}. Sign in and change it immediately.")
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
        print(f"Seeded admin account: {email}. Sign in and change the password immediately.")


if __name__ == "__main__":
    asyncio.run(seed_admin())
