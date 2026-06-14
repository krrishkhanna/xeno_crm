from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.campaign_analytics import CampaignAnalyticsRead
from app.schemas.common import CommunicationChannel


class AgentProvider(str, Enum):
    auto = "auto"
    openai = "openai"
    local = "local"


class AgentEventType(str, Enum):
    planning = "planning"
    tool_call = "tool_call"
    tool_result = "tool_result"
    status = "status"
    final = "final"
    error = "error"


class QueryCustomersInput(BaseModel):
    segment_definition: dict = Field(default_factory=dict)
    sample_size: int = Field(default=5, ge=1, le=20)


class QueryCustomersResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    segment_definition: dict
    segment_size: int
    sample_customers: list[dict]


class DraftMessageInput(BaseModel):
    objective: str = Field(min_length=1)
    segment_summary: str = Field(min_length=1)
    tone: str = Field(default="friendly", min_length=1, max_length=40)
    campaign_name_hint: str | None = None


class DraftMessageResult(BaseModel):
    campaign_name: str
    message: str


class CreateCampaignInput(BaseModel):
    campaign_name: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    segment_definition: dict = Field(default_factory=dict)


class CreateCampaignResult(BaseModel):
    campaign_id: UUID
    campaign_name: str
    status: str


class SendCampaignInput(BaseModel):
    campaign_id: UUID
    channel: CommunicationChannel = CommunicationChannel.sms


class SendCampaignResult(BaseModel):
    campaign_id: UUID
    campaign_status: str
    matched_customers: int
    communications_created: int
    communications_queued: int
    communications_failed_to_queue: int
    callback_url: str
    channel_service_url: str
    dispatched_at: datetime


class GetCampaignAnalyticsInput(BaseModel):
    campaign_id: UUID


class ListCampaignsInput(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=1, le=100)


class CampaignListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    created_at: datetime


class ListCampaignsResult(BaseModel):
    campaigns: list[CampaignListItem]


class MarketingAgentRequest(BaseModel):
    message: str = Field(min_length=1)
    provider: AgentProvider = AgentProvider.openai
    channel: CommunicationChannel = CommunicationChannel.sms
    stream: bool = True
    sample_size: int = Field(default=5, ge=1, le=20)
    analytics_timeout_seconds: int = Field(default=12, ge=1, le=60)


class AgentWorkflowPlan(BaseModel):
    objective: str = Field(min_length=1)
    segment_definition: dict = Field(default_factory=dict)
    campaign_name: str = Field(min_length=1)
    draft_tone: str = Field(default="friendly", min_length=1, max_length=40)
    should_send: bool = True
    should_fetch_analytics: bool = True
    summary: str | None = None


class MarketingAgentResponse(BaseModel):
    objective: str
    segment_definition: dict
    segment_size: int
    campaign_id: UUID
    campaign_name: str
    campaign_status: str
    draft_message: str
    analytics: CampaignAnalyticsRead
    summary: str


class MarketingAgentEvent(BaseModel):
    event: AgentEventType
    message: str
    tool_name: str | None = None
    payload: dict | None = None
    timestamp: datetime
