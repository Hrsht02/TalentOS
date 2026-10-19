"""AI provider failover: Gemini key 1 -> Gemini key 2 -> xAI Grok.

All credentials are read from server-side environment variables. The provider
router never logs keys or prompt contents. Cooldowns are process-local in this
initial implementation; a Redis-backed shared cooldown is planned for multi-worker
deployments. API callers should enqueue non-interactive work rather than block
request handlers on repeated provider failures.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIProviderUnavailable(RuntimeError):
    """Raised when every configured provider is unavailable or rate-limited."""


@dataclass(frozen=True)
class Provider:
    name: str
    key: str
    model: str
    kind: str


class AIProviderRouter:
    def __init__(self) -> None:
        self._cooldowns: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _providers(self) -> list[Provider]:
        providers: list[Provider] = []
        if settings.gemini_api_key:
            providers.append(Provider("gemini_primary", settings.gemini_api_key, settings.gemini_model, "gemini"))
        if settings.gemini_api_key_2:
            providers.append(Provider("gemini_secondary", settings.gemini_api_key_2, settings.gemini_model_2, "gemini"))
        grok_key = settings.xai_api_key or settings.grok_api_key
        if grok_key:
            providers.append(Provider("xai_grok", grok_key, settings.xai_model, "openai_compatible"))
        return providers

    async def _is_cooling_down(self, name: str) -> bool:
        async with self._lock:
            until = self._cooldowns.get(name, 0.0)
            if until <= time.monotonic():
                self._cooldowns.pop(name, None)
                return False
            return True

    async def _cool_down(self, name: str) -> None:
        async with self._lock:
            self._cooldowns[name] = time.monotonic() + max(1, settings.ai_provider_cooldown_seconds)

    @staticmethod
    def _quota_error(response: httpx.Response | None) -> bool:
        if response is None:
            return False
        body = response.text.lower()
        return any(term in body for term in (
            "resource_exhausted", "quota exceeded", "quota_exceeded",
            "rate limit", "rate_limit", "too many requests",
        ))

    @classmethod
    def _should_fail_over(cls, status_code: int | None, error: Exception) -> bool:
        # Some quota exhaustion responses are HTTP 400/403 with a provider error code.
        if isinstance(error, (httpx.TimeoutException, httpx.TransportError)):
            return True
        response = error.response if isinstance(error, httpx.HTTPStatusError) else None
        if cls._quota_error(response):
            return True
        if status_code in (408, 409, 425, 429) or (status_code is not None and status_code >= 500):
            return True
        return False

    async def _generate_gemini(self, client: httpx.AsyncClient, provider: Provider, prompt: str, temperature: float) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{provider.model}:generateContent"
        response = await client.post(
            url,
            params={"key": provider.key},
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature},
            },
        )
        if response.is_error:
            raise httpx.HTTPStatusError(
                f"Gemini provider returned HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
        payload = response.json()
        candidates = payload.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        if not text.strip():
            raise ValueError("Gemini returned empty text")
        return text.strip()

    async def _generate_grok(self, client: httpx.AsyncClient, provider: Provider, prompt: str, temperature: float) -> str:
        response = await client.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {provider.key}"},
            json={
                "model": provider.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            },
        )
        if response.is_error:
            raise httpx.HTTPStatusError(
                f"xAI provider returned HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
        payload: dict[str, Any] = response.json()
        choices = payload.get("choices") or []
        text = choices[0].get("message", {}).get("content") if choices else None
        if not isinstance(text, str) or not text.strip():
            raise ValueError("xAI returned empty text")
        return text.strip()

    async def generate_text(self, prompt: str, *, temperature: float = 0.2) -> str:
        """Generate text using the first available provider, failing over on quota/outage.

        Never pass passwords, access tokens, API keys, or unnecessary PII in prompts.
        """
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        providers = self._providers()
        if not providers:
            raise AIProviderUnavailable(
                "No AI provider configured. Set GEMINI_API_KEY, GEMINI_API_KEY_2, and/or XAI_API_KEY."
            )

        errors: list[str] = []
        timeout = httpx.Timeout(max(1.0, settings.ai_request_timeout_seconds))
        async with httpx.AsyncClient(timeout=timeout) as client:
            for provider in providers:
                if await self._is_cooling_down(provider.name):
                    logger.warning("Skipping AI provider in cooldown: %s", provider.name)
                    continue
                for attempt in range(max(1, settings.ai_max_retries_per_provider + 1)):
                    try:
                        if provider.kind == "gemini":
                            result = await self._generate_gemini(client, provider, prompt, temperature)
                        else:
                            result = await self._generate_grok(client, provider, prompt, temperature)
                        logger.info("AI request completed provider=%s model=%s attempt=%s", provider.name, provider.model, attempt + 1)
                        return result
                    except Exception as exc:
                        response = exc.response if isinstance(exc, httpx.HTTPStatusError) else None
                        status = response.status_code if response is not None else None
                        # 401/403 and invalid-request errors usually mean bad configuration;
                        # skip that provider but avoid marking it as a quota cooldown.
                        retryable = self._should_fail_over(status, exc)
                        message = f"{provider.name}: {type(exc).__name__}"
                        errors.append(message)
                        logger.warning("AI provider failure provider=%s status=%s retryable=%s error_type=%s",
                                       provider.name, status, retryable, type(exc).__name__)
                        if status == 429 or self._quota_error(response) or (status is not None and status >= 500) or isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
                            await self._cool_down(provider.name)
                        if not retryable:
                            break
                        if attempt < max(1, settings.ai_max_retries_per_provider + 1) - 1:
                            await asyncio.sleep(min(2 ** attempt, 3))
                        else:
                            break

        raise AIProviderUnavailable(
            "All configured AI providers failed or are cooling down. "
            "Queue this task for retry rather than blocking the user workflow. "
            f"Provider failures: {', '.join(errors) if errors else 'all providers cooling down'}"
        )


ai_provider = AIProviderRouter()
