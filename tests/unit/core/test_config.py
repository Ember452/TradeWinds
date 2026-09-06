"""get_settings() 配置加载测试。"""

import pytest
from pydantic import ValidationError

from tradewinds.core.config import get_settings

REQUIRED_ENV = {
    "TRADEWINDS_DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/tw",
    "TRADEWINDS_REDIS_URL": "redis://localhost:6379/0",
    "TRADEWINDS_JWT_SECRET": "test-secret",
    "TRADEWINDS_LLM_API_BASE": "https://llm.example.com/v1",
    "TRADEWINDS_LLM_API_KEY": "test-key",
    "TRADEWINDS_MODEL_LOW": "test-low",
    "TRADEWINDS_MODEL_MID": "test-mid",
}


@pytest.fixture
def clean_env(monkeypatch):
    """清掉本机可能存在的 TRADEWINDS_* 环境变量,保证用例自给自足。"""
    for key in [*REQUIRED_ENV, "TRADEWINDS_JWT_EXPIRE_MINUTES", "TRADEWINDS_QUOTA_TOPICS_MAX"]:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_get_settings_reads_env(clean_env) -> None:
    for key, value in REQUIRED_ENV.items():
        clean_env.setenv(key, value)

    settings = get_settings()

    assert settings.database_url == REQUIRED_ENV["TRADEWINDS_DATABASE_URL"]
    assert settings.redis_url == REQUIRED_ENV["TRADEWINDS_REDIS_URL"]
    assert settings.jwt_secret == "test-secret"
    assert settings.model_low == "test-low"
    assert settings.model_mid == "test-mid"


def test_get_settings_is_cached(clean_env) -> None:
    for key, value in REQUIRED_ENV.items():
        clean_env.setenv(key, value)

    assert get_settings() is get_settings()


def test_missing_required_config_fails_fast(clean_env) -> None:
    for key, value in REQUIRED_ENV.items():
        if key != "TRADEWINDS_JWT_SECRET":
            clean_env.setenv(key, value)

    with pytest.raises(ValidationError) as exc_info:
        get_settings()

    assert "jwt_secret" in str(exc_info.value)


def test_defaults(clean_env) -> None:
    for key, value in REQUIRED_ENV.items():
        clean_env.setenv(key, value)

    settings = get_settings()

    assert settings.jwt_expire_minutes == 1440
    assert settings.quota_topics_max == 5
    assert settings.log_level == "INFO"
