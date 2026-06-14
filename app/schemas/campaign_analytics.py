from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CampaignAnalyticsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sent: int
    delivered: int
    opened: int
    clicked: int
    failed: int
    open_rate: float
    click_rate: float
    failure_rate: float

