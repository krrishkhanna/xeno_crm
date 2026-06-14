from __future__ import annotations

from sqlalchemy import Float, Numeric, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.communication import Communication
from app.schemas.campaign import CampaignCreate, CampaignUpdate
from app.schemas.campaign_analytics import CampaignAnalyticsRead
from app.schemas.common import CampaignStatus, CommunicationStatus


class CampaignService:
    @staticmethod
    async def list_campaigns(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Campaign]:
        result = await session.execute(select(Campaign).offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def get_campaign(session: AsyncSession, campaign_id) -> Campaign | None:
        return await session.get(Campaign, campaign_id)

    @staticmethod
    async def create_campaign(session: AsyncSession, payload: CampaignCreate) -> Campaign:
        data = payload.model_dump()
        if isinstance(data.get("status"), CampaignStatus):
            data["status"] = data["status"].value
        campaign = Campaign(**data)
        session.add(campaign)
        await session.commit()
        await session.refresh(campaign)
        return campaign

    @staticmethod
    async def update_campaign(session: AsyncSession, campaign: Campaign, payload: CampaignUpdate) -> Campaign:
        updates = payload.model_dump(exclude_unset=True)
        if isinstance(updates.get("status"), CampaignStatus):
            updates["status"] = updates["status"].value
        for key, value in updates.items():
            setattr(campaign, key, value)
        await session.commit()
        await session.refresh(campaign)
        return campaign

    @staticmethod
    async def get_campaign_analytics(session: AsyncSession, campaign_id) -> CampaignAnalyticsRead:
        campaign = await session.get(Campaign, campaign_id)
        if campaign is None:
            raise ValueError("Campaign not found")

        sent_expression = func.count(Communication.id).filter(Communication.status != CommunicationStatus.queued.value)
        delivered_expression = func.count(Communication.id).filter(
            Communication.status == CommunicationStatus.delivered.value
        )
        opened_expression = func.count(Communication.id).filter(
            Communication.status == CommunicationStatus.opened.value
        )
        clicked_expression = func.count(Communication.id).filter(
            Communication.status == CommunicationStatus.clicked.value
        )
        failed_expression = func.count(Communication.id).filter(
            Communication.status == CommunicationStatus.failed.value
        )

        open_rate_expression = func.coalesce(
            func.round(
                cast((opened_expression * 100.0) / func.nullif(sent_expression, 0), Numeric),
                2,
            ),
            0.0,
        ).cast(Float)
        click_rate_expression = func.coalesce(
            func.round(
                cast((clicked_expression * 100.0) / func.nullif(sent_expression, 0), Numeric),
                2,
            ),
            0.0,
        ).cast(Float)
        failure_rate_expression = func.coalesce(
            func.round(
                cast((failed_expression * 100.0) / func.nullif(sent_expression, 0), Numeric),
                2,
            ),
            0.0,
        ).cast(Float)

        statement = (
            select(
                sent_expression.label("sent"),
                delivered_expression.label("delivered"),
                opened_expression.label("opened"),
                clicked_expression.label("clicked"),
                failed_expression.label("failed"),
                open_rate_expression.label("open_rate"),
                click_rate_expression.label("click_rate"),
                failure_rate_expression.label("failure_rate"),
            )
            .where(Communication.campaign_id == campaign_id)
        )

        result = await session.execute(statement)
        row = result.one()

        return CampaignAnalyticsRead(
            sent=int(row.sent or 0),
            delivered=int(row.delivered or 0),
            opened=int(row.opened or 0),
            clicked=int(row.clicked or 0),
            failed=int(row.failed or 0),
            open_rate=float(row.open_rate or 0.0),
            click_rate=float(row.click_rate or 0.0),
            failure_rate=float(row.failure_rate or 0.0),
        )
