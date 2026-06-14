from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    city: str | None = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    city: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = None


class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    total_orders: int
    last_order_date: datetime | None
    created_at: datetime
    updated_at: datetime
