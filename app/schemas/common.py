from __future__ import annotations

from enum import Enum


class CampaignStatus(str, Enum):
    draft = "draft"
    ready = "ready"
    sending = "sending"
    sent = "sent"
    failed = "failed"


class CommunicationStatus(str, Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    opened = "opened"
    clicked = "clicked"
    failed = "failed"


class CommunicationChannel(str, Enum):
    sms = "sms"
    email = "email"
    whatsapp = "whatsapp"
