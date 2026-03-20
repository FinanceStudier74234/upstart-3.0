"""
Application settings loaded from environment / .env file.
Single source of truth for all configuration.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Core ──
    app_env: str = "development"
    app_port: int = 8000
    app_host: str = "0.0.0.0"
    app_secret_key: str = ""  # MUST be set via APP_SECRET_KEY env var in production
    app_debug: bool = False  # MUST be explicitly enabled via APP_DEBUG=true
    log_level: str = "INFO"

    # ── Database ──
    database_url: str = "postgresql+asyncpg://upst:upst@localhost:5432/upst_hub"
    database_echo: bool = False
    database_pool_size: int = 20

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── Market Data Keys ──
    polygon_api_key: str = ""
    polygon_plan: str = "basic"
    alpha_vantage_api_key: str = ""
    fred_api_key: str = ""
    finnhub_api_key: str = ""
    tradier_api_key: str = ""
    tradier_sandbox: bool = True
    ortex_api_key: str = ""
    fintel_api_key: str = ""
    newsapi_key: str = ""
    sec_edgar_user_agent: str = "upst-hub@example.com"

    # ── Scheduling ──
    scheduler_enabled: bool = True
    market_data_refresh_seconds: int = 60
    options_data_refresh_seconds: int = 300
    macro_data_refresh_seconds: int = 3600
    news_refresh_seconds: int = 600
    short_data_refresh_seconds: int = 1800

    # ── Mock Mode ──
    mock_mode: bool = False

    # ── Derived helpers ──
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate_production(self):
        """Raise if production settings are unsafe."""
        if self.is_production:
            if not self.app_secret_key or self.app_secret_key in ("change-me", ""):
                raise ValueError("APP_SECRET_KEY must be set to a strong random value in production")
            if self.app_debug:
                raise ValueError("APP_DEBUG must be False in production")

    def has_polygon(self) -> bool:
        return bool(self.polygon_api_key)

    def has_fred(self) -> bool:
        return bool(self.fred_api_key)


settings = Settings()
