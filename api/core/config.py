from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mail_domain: str = "test.example.com"
    postfix_hostname: str = "mx.example.com"

    redis_url: str = "redis://redis:6379/0"
    job_ttl: int = 3600

    rspamd_url: str = "http://rspamd:11333"

    rate_limit_requests: int = 30
    rate_limit_window: int = 60
    trusted_proxy_hops: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
