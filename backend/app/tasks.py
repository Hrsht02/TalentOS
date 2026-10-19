"""Background task entrypoints. Keep tasks idempotent and avoid logging user PII."""
import logging
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def health_probe(self) -> dict[str, str]:
    """Small smoke task used to verify queue connectivity during deployment."""
    logger.info("TalentOS queue health probe completed")
    return {"status": "ok", "task": "health_probe"}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_ai_text(self, prompt: str, temperature: float = 0.2) -> dict[str, str]:
    """Run AI work off the request path using the configured provider failover."""
    import asyncio
    from app.services.ai_provider import ai_provider

    try:
        result = asyncio.run(ai_provider.generate_text(prompt, temperature=temperature))
        return {"status": "completed", "text": result}
    except Exception as exc:
        logger.warning("AI background task failed type=%s", type(exc).__name__)
        raise self.retry(exc=exc)
