from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.order import Order
from app.schemas.order import OrderCreate


class OrderService:
    @staticmethod
    async def list_orders(session: AsyncSession, skip: int = 0, limit: int = 100) -> list[Order]:
        result = await session.execute(select(Order).offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def get_order(session: AsyncSession, order_id) -> Order | None:
        return await session.get(Order, order_id)

    @staticmethod
    async def create_order(session: AsyncSession, payload: OrderCreate) -> Order:
        customer = await session.get(Customer, payload.customer_id)
        if customer is None:
            raise ValueError("Customer not found")

        created_at = datetime.now(timezone.utc)
        order = Order(
            customer_id=payload.customer_id,
            amount=payload.amount,
            product_category=payload.product_category,
            created_at=created_at,
        )
        session.add(order)

        customer.total_orders += 1
        customer.last_order_date = created_at

        await session.commit()
        await session.refresh(order)
        await session.refresh(customer)
        return order
