from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.order import OrderCreate, OrderRead
from app.services.order_service import OrderService

router = APIRouter()


@router.get("/", response_model=list[OrderRead])
async def list_orders(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    return await OrderService.list_orders(session, skip=skip, limit=limit)


@router.post("/", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, session: AsyncSession = Depends(get_db)):
    try:
        return await OrderService.create_order(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: UUID, session: AsyncSession = Depends(get_db)):
    order = await OrderService.get_order(session, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order

