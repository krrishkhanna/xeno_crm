from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.customer_service import CustomerService

router = APIRouter()


@router.get("/", response_model=list[CustomerRead])
async def list_customers(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    return await CustomerService.list_customers(session, skip=skip, limit=limit)


@router.post("/", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(payload: CustomerCreate, session: AsyncSession = Depends(get_db)):
    existing = await CustomerService.get_customer_by_email(session, payload.email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer email already exists")
    return await CustomerService.create_customer(session, payload)


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(customer_id: UUID, session: AsyncSession = Depends(get_db)):
    customer = await CustomerService.get_customer(session, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerRead)
async def update_customer(customer_id: UUID, payload: CustomerUpdate, session: AsyncSession = Depends(get_db)):
    customer = await CustomerService.get_customer(session, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return await CustomerService.update_customer(session, customer, payload)

