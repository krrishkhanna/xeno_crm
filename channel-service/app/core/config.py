from __future__ import annotations

import os


class Settings:
    app_name: str = os.getenv("APP_NAME", "channel-service")
    callback_timeout_seconds: float = float(os.getenv("CALLBACK_TIMEOUT_SECONDS", "10"))
    provider_min_delay_seconds: float = float(os.getenv("PROVIDER_MIN_DELAY_SECONDS", "1"))
    provider_max_delay_seconds: float = float(os.getenv("PROVIDER_MAX_DELAY_SECONDS", "5"))
    callback_user_agent: str = os.getenv("CALLBACK_USER_AGENT", "channel-service/1.0")


settings = Settings()

