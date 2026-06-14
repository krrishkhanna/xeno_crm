from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import CampaignStatus


class CampaignBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    segment_definition: dict
    status: CampaignStatus = CampaignStatus.draft


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    message: str | None = Field(default=None, min_length=1)
    segment_definition: dict | None = None
    status: CampaignStatus | None = None


class CampaignRead(CampaignBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime

