from __future__ import annotations

import asyncio
import random
import logging
from uuid import UUID, uuid4

from app.core.config import settings
from app.schemas.delivery import ProviderCallbackPayload, ProviderStatus
from app.services.callback_client import CallbackClient

logger = logging.getLogger(__name__)


class ProviderSimulator:
    @staticmethod
    def _should_fail() -> bool:
        return random.random() < 0.05

    @staticmethod
    def _should_deliver() -> bool:
        return random.random() < 0.80

    @staticmethod
    def _should_open() -> bool:
        return random.random() < 0.60

    @staticmethod
    def _should_click() -> bool:
        return random.random() < 0.30

    @staticmethod
    async def _emit_callback(callback_url: str, payload: ProviderCallbackPayload) -> None:
        try:
            await CallbackClient.send(callback_url, payload)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Callback delivery failed for communication %s with status %s",
                payload.communication_id,
                payload.status.value,
            )

    @staticmethod
    async def simulate_delivery(
        *,
        customer_id: UUID,
        communication_id: UUID,
        message: str,
        callback_url: str,
    ) -> None:
        provider_message_id = f"provider_{uuid4().hex}"
        base_delay = random.uniform(settings.provider_min_delay_seconds, settings.provider_max_delay_seconds)
        await asyncio.sleep(base_delay)

        if ProviderSimulator._should_fail():
            await ProviderSimulator._emit_callback(
                callback_url,
                ProviderCallbackPayload(
                    communication_id=communication_id,
                    customer_id=customer_id,
                    status=ProviderStatus.failed,
                    message=message,
                    provider_message_id=provider_message_id,
                    occurred_at=ProviderSimulator._now(),
                    failure_reason="Simulated provider failure",
                ),
            )
            return

        await ProviderSimulator._emit_callback(
            callback_url,
            ProviderCallbackPayload(
                communication_id=communication_id,
                customer_id=customer_id,
                status=ProviderStatus.sent,
                message=message,
                provider_message_id=provider_message_id,
                occurred_at=ProviderSimulator._now(),
            ),
        )

        await asyncio.sleep(random.uniform(0.5, 1.5))

        if not ProviderSimulator._should_deliver():
            await ProviderSimulator._emit_callback(
                callback_url,
                ProviderCallbackPayload(
                    communication_id=communication_id,
                    customer_id=customer_id,
                    status=ProviderStatus.failed,
                    message=message,
                    provider_message_id=provider_message_id,
                    occurred_at=ProviderSimulator._now(),
                    failure_reason="Simulated provider undeliverable failure",
                ),
            )
            return

        await ProviderSimulator._emit_callback(
            callback_url,
            ProviderCallbackPayload(
                communication_id=communication_id,
                customer_id=customer_id,
                status=ProviderStatus.delivered,
                message=message,
                provider_message_id=provider_message_id,
                occurred_at=ProviderSimulator._now(),
            ),
        )

        if ProviderSimulator._should_open():
            await asyncio.sleep(random.uniform(1.0, 2.5))
            await ProviderSimulator._emit_callback(
                callback_url,
                ProviderCallbackPayload(
                    communication_id=communication_id,
                    customer_id=customer_id,
                    status=ProviderStatus.opened,
                    message=message,
                    provider_message_id=provider_message_id,
                    occurred_at=ProviderSimulator._now(),
                ),
            )

            if ProviderSimulator._should_click():
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await ProviderSimulator._emit_callback(
                    callback_url,
                    ProviderCallbackPayload(
                        communication_id=communication_id,
                        customer_id=customer_id,
                        status=ProviderStatus.clicked,
                        message=message,
                        provider_message_id=provider_message_id,
                        occurred_at=ProviderSimulator._now(),
                    ),
                )

    @staticmethod
    def _now():
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)
