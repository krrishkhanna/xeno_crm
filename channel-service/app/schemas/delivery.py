from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class ProviderStatus(str, Enum):
    sent = "sent"
    delivered = "delivered"
    opened = "opened"
    clicked = "clicked"
    failed = "failed"


class SendRequest(BaseModel):
    customer_id: UUID
    communication_id: UUID
    message: str = Field(min_length=1)
    callback_url: HttpUrl


class SendResponse(BaseModel):
    request_id: UUID
    accepted: bool = True
    queued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProviderCallbackPayload(BaseModel):
    communication_id: UUID
    customer_id: UUID
    status: ProviderStatus
    message: str
    provider_message_id: str
    occurred_at: datetime
    source: str = "channel-service"
    failure_reason: str | None = None

    @classmethod
    def build(
        cls,
        *,
        communication_id: UUID,
        customer_id: UUID,
        status: ProviderStatus,
        message: str,
    ) -> "ProviderCallbackPayload":
        return cls(
            communication_id=communication_id,
            customer_id=customer_id,
            status=status,
            message=message,
            provider_message_id=f"msg_{uuid4().hex}",
            occurred_at=datetime.now(timezone.utc),
        )
