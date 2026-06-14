from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.campaign import Campaign
from app.models.communication import Communication
from app.schemas.campaign_dispatch import CampaignSendRequest, CampaignSendResponse
from app.schemas.common import CampaignStatus, CommunicationChannel, CommunicationStatus
from app.services.communication_service import CommunicationService
from app.services.segment_service import SegmentService

logger = logging.getLogger(__name__)

CHANNEL_SEND_PATH = "/send"


class CampaignDispatchService:
    @staticmethod
    def _build_customer_filters(segment_definition: dict) -> list:
        return SegmentService.build_customer_filters(segment_definition)

    @staticmethod
    async def _find_matching_customer_ids(session: AsyncSession, campaign: Campaign) -> list[uuid.UUID]:
        return await SegmentService.get_matching_customer_ids(session, campaign.segment_definition or {})

    @staticmethod
    async def _queue_channel_send(
        client: httpx.AsyncClient,
        *,
        communication_id: uuid.UUID,
        customer_id: uuid.UUID,
        campaign_message: str,
        callback_url: str,
        channel: CommunicationChannel,
    ) -> tuple[uuid.UUID, bool, str | None]:
        try:
            response = await client.post(
                f"{settings.channel_service_url}{CHANNEL_SEND_PATH}",
                json={
                    "customer_id": str(customer_id),
                    "communication_id": str(communication_id),
                    "message": campaign_message,
                    "callback_url": callback_url,
                },
                headers={"X-Channel": channel.value},
            )
            response.raise_for_status()
            if response.status_code == 202:
                return communication_id, True, None
            return communication_id, False, f"Unexpected status code {response.status_code}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to queue communication %s", communication_id)
            return communication_id, False, str(exc)

    @staticmethod
    async def send_campaign(
        session: AsyncSession,
        payload: CampaignSendRequest,
        *,
        callback_url: str,
    ) -> CampaignSendResponse:
        logger.info("Starting campaign dispatch for campaign_id=%s", payload.campaign_id)

        campaign = await session.scalar(
            select(Campaign).where(Campaign.id == payload.campaign_id).with_for_update()
        )
        if campaign is None:
            raise ValueError("Campaign not found")

        if campaign.status == CampaignStatus.sending.value:
            raise ValueError("Campaign is already being sent")

        customer_ids = await CampaignDispatchService._find_matching_customer_ids(session, campaign)
        if not customer_ids:
            raise ValueError("No customers match the campaign segment")

        dispatched_at = datetime.now(timezone.utc)
        communication_rows: list[dict[str, object]] = []
        communication_ids: list[uuid.UUID] = []

        for customer_id in customer_ids:
            communication_id = uuid.uuid4()
            communication_ids.append(communication_id)
            communication_rows.append(
                {
                    "id": communication_id,
                    "campaign_id": campaign.id,
                    "customer_id": customer_id,
                    "message": campaign.message,
                    "channel": payload.channel.value,
                    "status": CommunicationStatus.queued.value,
                    "sent_at": None,
                    "provider_message_id": None,
                    "failure_reason": None,
                }
            )

        await session.execute(Communication.__table__.insert(), communication_rows)
        campaign.status = CampaignStatus.sending.value
        await session.commit()

        logger.info(
            "Queued %s communications for campaign_id=%s, dispatching to %s",
            len(communication_ids),
            payload.campaign_id,
            settings.channel_service_url,
        )

        sent_ids: list[uuid.UUID] = []
        failed_items: list[tuple[uuid.UUID, str]] = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.channel_service_timeout_seconds)) as client:
            tasks = [
                CampaignDispatchService._queue_channel_send(
                    client,
                    communication_id=communication_id,
                    customer_id=customer_id,
                    campaign_message=campaign_message,
                    callback_url=callback_url,
                    channel=payload.channel,
                )
                for communication_id, customer_id, campaign_message in (
                    (row["id"], row["customer_id"], row["message"]) for row in communication_rows
                )
            ]
            dispatch_results = await asyncio.gather(*tasks)

        for communication_id, is_queued, error_message in dispatch_results:
            if is_queued:
                sent_ids.append(communication_id)
            else:
                failed_items.append((communication_id, error_message or "Channel service rejected request"))

        if sent_ids:
            await CommunicationService.mark_as_sent(session, sent_ids, dispatched_at)

        for communication_id, reason in failed_items:
            await CommunicationService.mark_as_failed(session, [communication_id], reason)

        campaign = await session.scalar(
            select(Campaign).where(Campaign.id == payload.campaign_id)
        )
        if campaign is not None:
            campaign.status = CampaignStatus.sent.value if sent_ids else CampaignStatus.failed.value

        await session.commit()

        logger.info(
            "Campaign dispatch complete for campaign_id=%s: matched=%s queued=%s failed=%s",
            payload.campaign_id,
            len(customer_ids),
            len(sent_ids),
            len(failed_items),
        )

        return CampaignSendResponse(
            campaign_id=payload.campaign_id,
            campaign_status=CampaignStatus.sent if sent_ids else CampaignStatus.failed,
            matched_customers=len(customer_ids),
            communications_created=len(communication_ids),
            communications_queued=len(sent_ids),
            communications_failed_to_queue=len(failed_items),
            callback_url=callback_url,
            channel_service_url=settings.channel_service_url,
            dispatched_at=dispatched_at,
        )
