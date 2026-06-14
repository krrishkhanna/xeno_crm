import os


class AgentSettings:
    provider: str = os.getenv("MARKETING_AGENT_PROVIDER", "openai")
    default_channel: str = os.getenv("MARKETING_AGENT_DEFAULT_CHANNEL", "sms")

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL")
    openai_timeout_seconds: float = float(
        os.getenv("OPENAI_TIMEOUT_SECONDS", "30")
    )

    max_preview_customers: int = int(
        os.getenv("MARKETING_AGENT_PREVIEW_CUSTOMERS", "5")
    )

    analytics_timeout_seconds: int = int(
        os.getenv("MARKETING_AGENT_ANALYTICS_TIMEOUT_SECONDS", "12")
    )

    analytics_poll_interval_seconds: float = float(
        os.getenv("MARKETING_AGENT_ANALYTICS_POLL_INTERVAL_SECONDS", "1.0")
    )


settings = AgentSettings()
