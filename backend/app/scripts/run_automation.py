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
    result = run_recruitment_automation.apply(throw=True)
    payload = result.get()
    print("TALENTOS_AUTOMATION_RESULT=" + json.dumps(payload, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
