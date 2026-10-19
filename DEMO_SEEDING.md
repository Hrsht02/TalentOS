# TalentOS demo data seeding (Render + Neon)

This seeds 7 platform-managed company profiles, one company-owner account and two HR accounts per company, 4 published jobs per company, and 24 student profiles with skills, education, and projects. The script is idempotent for its demo records.

## 1. Configure Render environment

On the TalentOS API web service, set:

- `DEMO_SEED_PASSWORD`: temporary password for the demo accounts (at least 12 characters)
- `ADMIN_SEED_EMAIL`: your admin email
- `ADMIN_SEED_PASSWORD`: a unique admin password of at least 16 characters

Use a new admin password if an earlier password was shared in chat. Do not put database URLs or passwords in GitHub.

## 2. Run the seed once using a temporary Start Command

In Render > TalentOS API > Settings > Start Command, temporarily use:

```bash
alembic upgrade head && python -m app.scripts.seed_admin && python -m app.scripts.seed_demo_data && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Save and deploy the latest commit. Confirm the logs show the seed completion message and the service becomes Live. This works around the free-plan Shell limitation by running the seed during a normal deployment.

## 3. Restore the normal Start Command immediately

After the seed succeeds, restore:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Save and deploy again. Do not leave seeding in the normal start command: each start would reset all demo passwords and force password changes again.

## Demo account naming

Company owner accounts: `<companyslug>@talentos.com`

HR accounts: `aarav_<companyslug>@talentos.com` and `diya_<companyslug>@talentos.com`

Student accounts: `student01@talentos.com` through `student24@talentos.com`

All seeded accounts use the `DEMO_SEED_PASSWORD` environment value and have `must_change_password=true`. The seeder does not print credentials or password values to logs.

## Important

- Ensure Render `DATABASE_URL` points to the same Neon project/branch/database you inspect in the Neon SQL Editor.
- The seed creates demo profiles and published jobs but does not fabricate candidate assessment scores. Trigger matching from each job's company account after the worker is running.
- The sample data is fictional. Keep the demo password temporary and change it immediately after signing in.
