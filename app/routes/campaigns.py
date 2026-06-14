from __future__ import annotations

from uuid import UUID

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.urls import get_callback_url
from app.database import get_db
from app.schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate
from app.schemas.campaign_analytics import CampaignAnalyticsRead
from app.schemas.campaign_dispatch import CampaignSendRequest, CampaignSendResponse
from app.services.campaign_service import CampaignService
from app.services.campaign_dispatch_service import CampaignDispatchService

logger = logging.getLogger(__name__)

send_router = APIRouter()
router = APIRouter()

@router.get("/", response_model=list[CampaignRead])
async def list_campaigns(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    return await CampaignService.list_campaigns(session, skip=skip, limit=limit)


@router.post("/", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(payload: CampaignCreate, session: AsyncSession = Depends(get_db)):
    return await CampaignService.create_campaign(session, payload)


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(campaign_id: UUID, session: AsyncSession = Depends(get_db)):
    campaign = await CampaignService.get_campaign(session, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


@router.get("/{campaign_id}/analytics", response_model=CampaignAnalyticsRead)
async def campaign_analytics(campaign_id: UUID, session: AsyncSession = Depends(get_db)):
    try:
        return await CampaignService.get_campaign_analytics(session, campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(campaign_id: UUID, payload: CampaignUpdate, session: AsyncSession = Depends(get_db)):
    campaign = await CampaignService.get_campaign(session, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return await CampaignService.update_campaign(session, campaign, payload)


@send_router.post("/campaigns/send", response_model=CampaignSendResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_campaign(
    payload: CampaignSendRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    callback_url = get_callback_url(request, "channel_delivery_callback")
    try:
        response = await CampaignDispatchService.send_campaign(session, payload, callback_url=callback_url)
        return response
    except ValueError as exc:
        message = str(exc)
        logger.warning("Campaign dispatch rejected for campaign_id=%s: %s", payload.campaign_id, message)
        if "not found" in message.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc
        if "already being sent" in message.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Campaign dispatch failed for campaign_id=%s", payload.campaign_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Campaign dispatch failed") from exc
