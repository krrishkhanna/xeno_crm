from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_name: str = os.getenv("APP_NAME", "xeno-crm")
    channel_service_url: str = os.getenv("CHANNEL_SERVICE_URL", "http://localhost:8001").rstrip("/")
    channel_service_timeout_seconds: float = float(os.getenv("CHANNEL_SERVICE_TIMEOUT_SECONDS", "15"))
    crm_public_url: str | None = os.getenv("CRM_PUBLIC_URL", "").strip() or None
    crm_callback_url: str | None = os.getenv("CRM_CALLBACK_URL", "").strip() or None


settings = Settings()
