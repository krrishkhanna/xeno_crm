from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import CampaignStatus, CommunicationChannel


class CampaignSendRequest(BaseModel):
    campaign_id: UUID
    channel: CommunicationChannel = CommunicationChannel.sms


class CampaignSendResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: UUID
    campaign_status: CampaignStatus
    matched_customers: int
    communications_created: int
    communications_queued: int
    communications_failed_to_queue: int
    callback_url: str = Field(min_length=1)
    channel_service_url: str = Field(min_length=1)
    dispatched_at: datetime

