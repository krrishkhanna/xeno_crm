from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import CommunicationChannel, CommunicationStatus


class CommunicationBase(BaseModel):
    campaign_id: UUID
    customer_id: UUID
    message: str = Field(min_length=1)
    channel: CommunicationChannel
    status: CommunicationStatus = CommunicationStatus.queued
    sent_at: datetime | None = None
    provider_message_id: str | None = None
    failure_reason: str | None = None


class CommunicationCreate(CommunicationBase):
    pass


class CommunicationUpdate(BaseModel):
    message: str | None = Field(default=None, min_length=1)
    channel: CommunicationChannel | None = None
    status: CommunicationStatus | None = None
    sent_at: datetime | None = None
    provider_message_id: str | None = None
    failure_reason: str | None = None


class CommunicationCallbackPayload(BaseModel):
    communication_id: UUID
    customer_id: UUID
    status: CommunicationStatus
    message: str = Field(min_length=1)
    provider_message_id: str = Field(min_length=1)
    occurred_at: datetime
    source: str = Field(default="channel-service", min_length=1)
    failure_reason: str | None = None


class CommunicationRead(CommunicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    updated_at: datetime
