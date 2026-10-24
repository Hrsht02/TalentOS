"""Run TalentOS periodic automation without a persistent Celery worker."""
import json
import logging
import os

# This entrypoint is intended for a trusted scheduled runner such as GitHub Actions.
# It connects directly to the configured PostgreSQL database and executes Celery
# task bodies locally via apply(), so no Redis broker or worker is required.
os.environ.setdefault("ENVIRONMENT", "development")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")

from app.automation import run_recruitment_automation


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url or "localhost" in database_url or "127.0.0.1" in database_url:
        raise SystemExit("DATABASE_URL secret is missing or points to localhost. Add the Neon connection string as GitHub Actions secret NEON_DATABASE_URL.")
    payload = run_recruitment_automation.run()
    print("TALENTOS_AUTOMATION_RESULT=" + json.dumps(payload, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
