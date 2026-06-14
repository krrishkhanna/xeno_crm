from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.communication import Communication
from app.models.customer import Customer
from app.schemas.common import CommunicationStatus
from app.schemas.communication import CommunicationCallbackPayload, CommunicationCreate, CommunicationUpdate

STATUS_PRIORITY = {
    CommunicationStatus.queued.value: 0,
    CommunicationStatus.sent.value: 1,
    CommunicationStatus.delivered.value: 2,
    CommunicationStatus.opened.value: 3,
    CommunicationStatus.clicked.value: 4,
    CommunicationStatus.failed.value: 5,
}


class CommunicationService:
    @staticmethod
    async def list_communications(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Communication]:
        result = await session.execute(select(Communication).offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def get_communication(session: AsyncSession, communication_id) -> Communication | None:
        return await session.get(Communication, communication_id)

    @staticmethod
    async def create_communication(session: AsyncSession, payload: CommunicationCreate) -> Communication:
        campaign = await session.get(Campaign, payload.campaign_id)
        if campaign is None:
            raise ValueError("Campaign not found")

        customer = await session.get(Customer, payload.customer_id)
        if customer is None:
            raise ValueError("Customer not found")

        communication = Communication(
            campaign_id=payload.campaign_id,
            customer_id=payload.customer_id,
            message=payload.message,
            channel=payload.channel.value,
            status=payload.status.value,
            sent_at=payload.sent_at,
        )
        session.add(communication)
        await session.commit()
        await session.refresh(communication)
        return communication

    @staticmethod
    async def mark_as_sent(session: AsyncSession, communication_ids: list, sent_at: datetime) -> None:
        if not communication_ids:
            return

        await session.execute(
            update(Communication)
            .where(Communication.id.in_(communication_ids))
            .where(Communication.status == CommunicationStatus.queued.value)
            .values(
                status=CommunicationStatus.sent.value,
                sent_at=sent_at,
                updated_at=func.now(),
            )
        )

    @staticmethod
    async def mark_as_failed(session: AsyncSession, communication_ids: list, reason: str) -> None:
        if not communication_ids:
            return

        await session.execute(
            update(Communication)
            .where(Communication.id.in_(communication_ids))
            .where(Communication.status.in_([CommunicationStatus.queued.value, CommunicationStatus.sent.value]))
            .values(
                status=CommunicationStatus.failed.value,
                failure_reason=reason,
                updated_at=func.now(),
            )
        )

    @staticmethod
    async def update_communication(
        session: AsyncSession,
        communication: Communication,
        payload: CommunicationUpdate,
    ) -> Communication:
        updates = payload.model_dump(exclude_unset=True)
        if "channel" in updates and updates["channel"] is not None:
            updates["channel"] = updates["channel"].value
        if "status" in updates and updates["status"] is not None:
            updates["status"] = updates["status"].value

        for key, value in updates.items():
            setattr(communication, key, value)

        await session.commit()
        await session.refresh(communication)
        return communication

    @staticmethod
    async def apply_provider_callback(session: AsyncSession, payload: CommunicationCallbackPayload) -> Communication:
        communication = await session.get(Communication, payload.communication_id)
        if communication is None:
            raise ValueError("Communication not found")

        incoming_status = payload.status.value
        current_status = communication.status

        current_priority = STATUS_PRIORITY.get(current_status, 0)
        incoming_priority = STATUS_PRIORITY.get(incoming_status, 0)
        terminal_success_statuses = {
            CommunicationStatus.delivered.value,
            CommunicationStatus.opened.value,
            CommunicationStatus.clicked.value,
        }

        if current_status == CommunicationStatus.failed.value:
            if incoming_status != CommunicationStatus.failed.value:
                return communication
        elif current_status in terminal_success_statuses:
            if incoming_status not in terminal_success_statuses or incoming_priority < current_priority:
                return communication
        elif incoming_priority < current_priority:
            return communication

        communication.status = incoming_status
        communication.provider_message_id = payload.provider_message_id
        communication.failure_reason = payload.failure_reason

        if payload.status in {
            CommunicationStatus.sent,
            CommunicationStatus.delivered,
            CommunicationStatus.opened,
            CommunicationStatus.clicked,
        } and communication.sent_at is None:
            communication.sent_at = payload.occurred_at

        communication.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(communication)
        return communication
