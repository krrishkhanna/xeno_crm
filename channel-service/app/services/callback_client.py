from __future__ import annotations

import logging
import asyncio

import httpx

from app.core.config import settings
from app.schemas.delivery import ProviderCallbackPayload

logger = logging.getLogger(__name__)


class CallbackClient:
    @staticmethod
    async def send(callback_url: str, payload: ProviderCallbackPayload) -> None:
        timeout = httpx.Timeout(settings.callback_timeout_seconds)
        headers = {"User-Agent": settings.callback_user_agent}

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            for attempt in range(3):
                try:
                    response = await client.post(callback_url, json=payload.model_dump(mode="json"))
                    response.raise_for_status()
                    logger.info("Callback delivered to %s for communication %s", callback_url, payload.communication_id)
                    return
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    logger.warning(
                        "Callback attempt %s failed for communication %s: %s",
                        attempt + 1,
                        payload.communication_id,
                        exc,
                    )
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (attempt + 1))

        if last_error is not None:
            raise last_error
