import pytest
from pydantic import ValidationError
from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from jose import jwt
from app.core.security import ALGORITHM


def test_password_hash_verifies_only_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("incorrect password", hashed)


def test_access_token_contains_expected_claims():
    token = create_access_token("123e4567-e89b-12d3-a456-426614174000", "STUDENT")
    claims = jwt.decode(token, Settings(_env_file=None).secret_key, algorithms=[ALGORITHM])
    assert claims["sub"] == "123e4567-e89b-12d3-a456-426614174000"
    assert claims["role"] == "STUDENT"
    assert claims["type"] == "access"
    assert "exp" in claims


def test_production_settings_reject_default_secret():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            secret_key="change-me-before-deployment",
            admin_seed_password="this-is-a-unique-long-password",
            debug=False,
            cors_origins="https://talentos.example",
        )


def test_production_settings_accept_strong_explicit_values():
    config = Settings(
        _env_file=None,
        environment="production",
        secret_key="s" * 48,
        admin_seed_password="this-is-a-unique-long-password",
        debug=False,
        cors_origins="https://talentos.example",
    )
    assert config.environment == "production"
    assert config.cors_origin_list == ["https://talentos.example"]
