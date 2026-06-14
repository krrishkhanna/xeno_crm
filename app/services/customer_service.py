from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerService:
    @staticmethod
    async def list_customers(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Customer]:
        result = await session.execute(select(Customer).offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def get_customer(session: AsyncSession, customer_id) -> Customer | None:
        return await session.get(Customer, customer_id)

    @staticmethod
    async def get_customer_by_email(session: AsyncSession, email: str) -> Customer | None:
        result = await session.execute(select(Customer).where(Customer.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_customer(session: AsyncSession, payload: CustomerCreate) -> Customer:
        customer = Customer(**payload.model_dump())
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        return customer

    @staticmethod
    async def update_customer(session: AsyncSession, customer: Customer, payload: CustomerUpdate) -> Customer:
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(customer, key, value)
        await session.commit()
        await session.refresh(customer)
        return customer

