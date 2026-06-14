from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.communication import CommunicationCallbackPayload, CommunicationCreate, CommunicationRead, CommunicationUpdate
from app.services.communication_service import CommunicationService

router = APIRouter()


@router.get("/", response_model=list[CommunicationRead])
async def list_communications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    return await CommunicationService.list_communications(session, skip=skip, limit=limit)


@router.post("/", response_model=CommunicationRead, status_code=status.HTTP_201_CREATED)
async def create_communication(payload: CommunicationCreate, session: AsyncSession = Depends(get_db)):
    try:
        return await CommunicationService.create_communication(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{communication_id}", response_model=CommunicationRead)
async def get_communication(communication_id: UUID, session: AsyncSession = Depends(get_db)):
    communication = await CommunicationService.get_communication(session, communication_id)
    if communication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found")
    return communication


@router.patch("/{communication_id}", response_model=CommunicationRead)
async def update_communication(
    communication_id: UUID,
    payload: CommunicationUpdate,
    session: AsyncSession = Depends(get_db),
):
    communication = await CommunicationService.get_communication(session, communication_id)
    if communication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found")
    return await CommunicationService.update_communication(session, communication, payload)


@router.post("/callbacks/channel-service", status_code=status.HTTP_202_ACCEPTED, name="channel_delivery_callback")
async def channel_delivery_callback(
    payload: CommunicationCallbackPayload,
    session: AsyncSession = Depends(get_db),
):
    try:
        await CommunicationService.apply_provider_callback(session, payload)
        return {"accepted": True}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
