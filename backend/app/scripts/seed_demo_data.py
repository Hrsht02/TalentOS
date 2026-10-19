"""Idempotently seed demo companies, jobs, HR accounts and student profiles.

Run once during a controlled Render deployment by setting DEMO_SEED_PASSWORD,
then temporarily using: python -m app.scripts.seed_demo_data && alembic upgrade head && uvicorn ...
All seeded accounts require a password change at first login.
"""
import asyncio
import os
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models import (
    AccountStatus, Company, CompanyJoinRequest, CompanyMember, Job, JobRequirement, JobStatus,
    Student, StudentEducation, StudentProject, StudentSkill, User, UserRole,
)

DEMO_PASSWORD = os.getenv("DEMO_SEED_PASSWORD", "").strip()

COMPANIES = [
    {"name":"NovaTech", "sector":"Software & AI", "description":"Product engineering, cloud platforms and applied AI."},
    {"name":"MediCore", "sector":"Healthcare Technology", "description":"Digital health, clinical workflow and healthcare data platforms."},
    {"name":"FinEdge", "sector":"Financial Services", "description":"Payments, risk systems and financial technology."},
    {"name":"GreenGrid", "sector":"Climate & Energy", "description":"Energy analytics, sustainability and smart-grid products."},
    {"name":"ShopSphere", "sector":"E-commerce", "description":"Retail technology, search, recommendations and marketplace systems."},
    {"name":"AutoNexus", "sector":"Automotive Technology", "description":"Connected mobility, embedded systems and vehicle data."},
    {"name":"LearnLoop", "sector":"Education Technology", "description":"Learning platforms, assessment and education analytics."},
]

JOB_TEMPLATES = [
    {"title":"Junior Software Engineer","description":"Build and maintain customer-facing product features, write readable tests, review code with teammates, and help improve service reliability. Work with product and design to deliver small features end to end.","type":"Full-time","location":"Bengaluru / Hybrid","min":0,"max":2,"skills":["Python","SQL","Git","REST APIs"]},
    {"title":"Data Analyst","description":"Turn business questions into reliable datasets, dashboards and clear recommendations. Write SQL queries, validate data quality, explain trends to stakeholders and document analysis for repeatable decisions.","type":"Full-time","location":"Remote, India","min":0,"max":2,"skills":["SQL","Python","Excel","Data Visualization"]},
    {"title":"AI / Machine Learning Intern","description":"Prototype and evaluate data-driven features, prepare datasets, establish meaningful baselines and document experiments. Collaborate with engineers to turn promising prototypes into testable product components.","type":"Internship","location":"Remote / Hybrid","min":0,"max":1,"skills":["Python","Machine Learning","Pandas","NumPy"]},
    {"title":"Frontend Developer","description":"Build accessible, responsive web interfaces using reusable components. Integrate REST APIs, handle loading and error states, test important user flows and work with design to improve usability.","type":"Full-time","location":"Patna / Remote","min":0,"max":3,"skills":["JavaScript","React","HTML","CSS","REST APIs"]},
]

STUDENTS = [
("Aarav Sharma","Computer Science student","Python, SQL, Git, REST APIs","B.Tech","Computer Science"),
("Diya Verma","Frontend developer in training","JavaScript, React, HTML, CSS","B.Tech","Information Technology"),
("Kabir Singh","Data analytics enthusiast","Python, SQL, Excel, Data Visualization","B.Tech","Data Science"),
("Ananya Gupta","AI and machine learning student","Python, Machine Learning, Pandas, NumPy","B.Tech","Computer Science"),
("Ishaan Kumar","Backend engineering learner","Python, SQL, Git, REST APIs","B.Tech","Computer Science"),
("Meera Patel","UI-focused frontend developer","JavaScript, React, HTML, CSS","BCA","Computer Applications"),
("Reyansh Das","Business and data analyst candidate","SQL, Python, Excel, Data Visualization","B.Sc","Statistics"),
("Saanvi Rao","Applied AI project builder","Python, Machine Learning, Pandas, NumPy","B.Tech","Artificial Intelligence"),
("Aditya Mishra","Software engineering candidate","Python, Git, REST APIs, SQL","B.Tech","Computer Science"),
("Myra Joshi","Frontend engineering candidate","JavaScript, React, CSS, HTML","B.Tech","Information Technology"),
("Vihaan Nair","Analytics and reporting candidate","SQL, Excel, Python, Data Visualization","B.Com","Finance"),
("Aadhya Iyer","Machine learning intern candidate","Python, NumPy, Pandas, Machine Learning","B.Tech","Data Science"),
("Arjun Mehta","Full-stack project contributor","JavaScript, React, SQL, REST APIs","B.Tech","Computer Science"),
("Pari Choudhary","Junior web developer","JavaScript, HTML, CSS, Git","BCA","Computer Applications"),
("Rohan Yadav","Data engineering learner","Python, SQL, Git, Pandas","B.Tech","Computer Science"),
("Ira Kapoor","AI research project student","Python, Machine Learning, NumPy, SQL","B.Tech","Artificial Intelligence"),
("Dev Malhotra","Software testing and API learner","Python, REST APIs, Git, SQL","B.Tech","Computer Science"),
("Kiara Shah","Product analytics candidate","SQL, Excel, Data Visualization, Python","BBA","Business Analytics"),
("Atharv Jain","React application developer","JavaScript, React, HTML, CSS","B.Tech","Information Technology"),
("Navya Reddy","Data science student","Python, Pandas, NumPy, Machine Learning","B.Tech","Data Science"),
("Krish Bansal","Backend and database learner","Python, SQL, REST APIs, Git","B.Tech","Computer Science"),
("Tara Sinha","Web design and frontend student","HTML, CSS, JavaScript, React","BCA","Computer Applications"),
("Yuvraj Pillai","Junior data analyst","SQL, Python, Excel, Data Visualization","B.Sc","Mathematics"),
("Anvi Kulkarni","AI product internship candidate","Python, Machine Learning, Pandas, SQL","B.Tech","Computer Science"),
]


def slugify(value: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "company")[:220]


async def upsert_user(db: AsyncSession, *, email: str, name: str, role: UserRole, password_hash: str) -> User:
    email = email.lower()
    user = await db.scalar(select(User).where(User.email == email))
    if user and user.role != role:
        raise RuntimeError(f"Refusing to overwrite existing account with a different role: {email}")
    if user is None:
        user = User(email=email, full_name=name, role=role, status=AccountStatus.ACTIVE,
                    password_hash=password_hash, must_change_password=True)
        db.add(user)
        await db.flush()
    else:
        user.full_name = name
        user.status = AccountStatus.ACTIVE
        user.password_hash = password_hash
        user.must_change_password = True
        user.deleted_at = None
    return user


async def seed() -> None:
    if len(DEMO_PASSWORD) < 12:
        raise RuntimeError("Set DEMO_SEED_PASSWORD in Render to a temporary password of at least 12 characters.")
    hashed = hash_password(DEMO_PASSWORD)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        company_count = 0
        job_count = 0
        hr_count = 0
        student_count = 0
        for company_info in COMPANIES:
            slug = slugify(company_info["name"])
            company = await db.scalar(select(Company).where(Company.slug == slug))
            if company is None:
                duplicate_name = await db.scalar(select(Company).where(Company.name.ilike(company_info["name"])))
                if duplicate_name:
                    company = duplicate_name
                else:
                    company = Company(name=company_info["name"], slug=slug, verified=True,
                                      suspended=False, description=company_info["description"],
                                      website=f"https://{slug}.example.com",
                                      metadata_json={"sector": company_info["sector"], "demo_seed": True})
                    db.add(company)
                    await db.flush()
            else:
                company.verified = True
                company.suspended = False
                company.description = company_info["description"]
                company.metadata_json = {**(company.metadata_json or {}), "sector": company_info["sector"], "demo_seed": True}
            company_count += 1

            owner_email = f"{slug.replace('-', '')}@talentos.com"
            owner = await upsert_user(db, email=owner_email, name=f"{company_info['name']} Company Account",
                                      role=UserRole.COMPANY_HR, password_hash=hashed)
            owner_member = await db.scalar(select(CompanyMember).where(
                CompanyMember.company_id == company.id, CompanyMember.user_id == owner.id))
            if owner_member is None:
                db.add(CompanyMember(company_id=company.id, user_id=owner.id, sub_role="OWNER", permissions=["*"], active=True))
            else:
                owner_member.sub_role = "OWNER"; owner_member.permissions = ["*"]; owner_member.active = True

            for index, hr_name in enumerate(["Aarav", "Diya"], start=1):
                hr_email = f"{hr_name.lower()}_{slug.replace('-', '')}@talentos.com"
                hr = await upsert_user(db, email=hr_email, name=f"{hr_name} {company_info['name']} Recruiter",
                                       role=UserRole.COMPANY_HR, password_hash=hashed)
                membership = await db.scalar(select(CompanyMember).where(
                    CompanyMember.company_id == company.id, CompanyMember.user_id == hr.id))
                if membership is None:
                    db.add(CompanyMember(company_id=company.id, user_id=hr.id, sub_role="HR",
                                         permissions=["JOBS_READ", "JOBS_WRITE", "CANDIDATES_READ"], active=True))
                else:
                    membership.sub_role = "HR"; membership.active = True
                hr_count += 1

            for template_index, template in enumerate(JOB_TEMPLATES):
                job_title = f"{template['title']} · {company_info['sector']}"
                job = await db.scalar(select(Job).where(Job.company_id == company.id, Job.title == job_title, Job.deleted_at.is_(None)))
                if job is None:
                    job = Job(company_id=company.id, created_by=owner.id, title=job_title,
                              description=template["description"], location=template["location"],
                              employment_type=template["type"], experience_min=template["min"],
                              experience_max=template["max"], openings=2 if template_index < 2 else 1,
                              deadline=now + timedelta(days=45), status=JobStatus.PUBLISHED,
                              requirements={"skills": template["skills"], "sector": company_info["sector"]},
                              eligibility={"graduation_year_min": 2023, "graduation_year_max": 2030},
                              published_at=now)
                    db.add(job)
                    await db.flush()
                    for skill in template["skills"]:
                        db.add(JobRequirement(job_id=job.id, skill=skill, requirement_type="MUST_HAVE", minimum_years=0, weight=1.0))
                    job_count += 1
                else:
                    job.status = JobStatus.PUBLISHED
                    job.published_at = job.published_at or now
                    job.deadline = job.deadline or now + timedelta(days=45)

        for idx, (name, headline, skill_text, degree, branch) in enumerate(STUDENTS, start=1):
            email = f"student{idx:02d}@talentos.com"
            student_user = await upsert_user(db, email=email, name=name, role=UserRole.STUDENT, password_hash=hashed)
            student = await db.scalar(select(Student).where(Student.user_id == student_user.id))
            if student is None:
                student = Student(user_id=student_user.id)
                db.add(student)
                await db.flush()
            student.headline = headline
            student.location = ["Patna, India", "Bengaluru, India", "Remote, India", "Hyderabad, India"][idx % 4]
            student.graduation_year = 2026 + (idx % 3)
            student.degree = degree
            student.branch = branch
            student.cgpa = round(7.0 + ((idx * 7) % 29) / 10, 2)
            student.backlogs = 0 if idx % 6 else 1
            student.profile_completion = 90
            skill_names = [s.strip() for s in skill_text.split(",")]
            existing_skills = set((await db.scalars(select(StudentSkill.skill).where(StudentSkill.student_id == student.id))).all())
            for skill in skill_names:
                if skill not in existing_skills:
                    db.add(StudentSkill(student_id=student.id, skill=skill, proficiency=["Intermediate", "Advanced", "Beginner"][idx % 3],
                                        years_experience=0.5 + (idx % 4) * 0.5, source="DEMO_SEED"))
            project_name = f"{name.split()[0]}'s {['Portfolio App','Analytics Dashboard','AI Study Assistant'][idx % 3]}"
            project_exists = await db.scalar(select(StudentProject.id).where(StudentProject.student_id == student.id, StudentProject.name == project_name))
            if not project_exists:
                db.add(StudentProject(student_id=student.id, name=project_name,
                                      description=f"Demo portfolio project demonstrating {', '.join(skill_names[:3])}. Includes documented design choices, implementation notes, and test cases.",
                                      technologies=skill_names, verified=False))
            education_exists = await db.scalar(select(StudentEducation.id).where(StudentEducation.student_id == student.id))
            if not education_exists:
                db.add(StudentEducation(student_id=student.id, institution=f"{['IIT Patna','NIT Patna','State Technical University'][idx % 3]}",
                                        degree=degree, field_of_study=branch, start_year=2022, end_year=student.graduation_year,
                                        grade=f"{student.cgpa}/10"))
            student_count += 1

        # Approve pending requests from active HR users for companies that have no current membership.
        pending_requests = (await db.scalars(select(CompanyJoinRequest).where(CompanyJoinRequest.status == "PENDING"))).all()
        approved_requests = 0
        for request in pending_requests:
            applicant = await db.get(User, request.user_id)
            company = await db.get(Company, request.company_id)
            if not applicant or applicant.role != UserRole.COMPANY_HR or applicant.status != AccountStatus.ACTIVE or not company or company.suspended:
                continue
            existing_membership = await db.scalar(select(CompanyMember).where(
                CompanyMember.user_id == applicant.id, CompanyMember.active.is_(True)
            ))
            if existing_membership:
                if existing_membership.company_id == company.id:
                    request.status = "APPROVED"
                    request.reviewed_at = now
                    approved_requests += 1
                continue
            db.add(CompanyMember(company_id=company.id, user_id=applicant.id, sub_role="HR",
                                 permissions=["JOBS_READ", "JOBS_WRITE", "CANDIDATES_READ"], active=True))
            request.status = "APPROVED"
            request.reviewed_at = now
            approved_requests += 1

        await db.commit()
        print(f"Demo seed complete: {company_count} companies, {job_count} newly created jobs (4 per company when absent), {hr_count} HR users, {student_count} students, {approved_requests} pending HR join requests approved.")
        print("All demo accounts require a password change on first login. Password values are intentionally not printed to logs.")


if __name__ == "__main__":
    asyncio.run(seed())
