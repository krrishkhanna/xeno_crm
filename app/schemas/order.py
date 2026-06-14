from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrderBase(BaseModel):
    customer_id: UUID
    amount: Decimal = Field(gt=0)
    product_category: str = Field(min_length=1, max_length=120)


class OrderCreate(OrderBase):
    pass


class OrderRead(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime

