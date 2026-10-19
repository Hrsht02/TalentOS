import httpx
from app.services.ai_provider import AIProviderRouter


def test_quota_errors_trigger_failover():
    request = httpx.Request("POST", "https://example.invalid")
    response = httpx.Response(429, request=request, json={"error": {"message": "quota exceeded"}})
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)
    assert AIProviderRouter._should_fail_over(429, error)


def test_quota_code_in_bad_request_triggers_failover():
    request = httpx.Request("POST", "https://example.invalid")
    response = httpx.Response(400, request=request, json={"error": {"status": "RESOURCE_EXHAUSTED"}})
    error = httpx.HTTPStatusError("quota", request=request, response=response)
    assert AIProviderRouter._should_fail_over(400, error)


def test_invalid_input_does_not_retry_same_provider():
    request = httpx.Request("POST", "https://example.invalid")
    response = httpx.Response(400, request=request, json={"error": {"message": "invalid prompt"}})
    error = httpx.HTTPStatusError("invalid", request=request, response=response)
    assert not AIProviderRouter._should_fail_over(400, error)
