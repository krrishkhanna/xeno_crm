from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


class SegmentService:
    @staticmethod
    def build_customer_filters(segment_definition: dict) -> list:
        filters: list = []

        cities = segment_definition.get("cities")
        if cities:
            filters.append(Customer.city.in_(cities))

        customer_ids = segment_definition.get("customer_ids")
        if customer_ids:
            parsed_customer_ids = [uuid.UUID(str(customer_id)) for customer_id in customer_ids]
            filters.append(Customer.id.in_(parsed_customer_ids))

        min_orders = segment_definition.get("min_orders")
        if min_orders is not None:
            filters.append(Customer.total_orders >= int(min_orders))

        max_orders = segment_definition.get("max_orders")
        if max_orders is not None:
            filters.append(Customer.total_orders <= int(max_orders))

        exclude_tags = segment_definition.get("exclude_tags")
        if exclude_tags:
            exclude_conditions = [Customer.tags.contains([tag]) for tag in exclude_tags]
            filters.append(not_(or_(*exclude_conditions)))

        tags_all = segment_definition.get("tags_all")
        if tags_all:
            filters.extend(Customer.tags.contains([tag]) for tag in tags_all)

        tags_any = segment_definition.get("tags_any")
        if tags_any:
            filters.append(or_(*[Customer.tags.contains([tag]) for tag in tags_any]))

        last_order_within_days = segment_definition.get("last_order_within_days")
        if last_order_within_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(last_order_within_days))
            filters.append(Customer.last_order_date.is_not(None))
            filters.append(Customer.last_order_date >= cutoff)

        last_order_before_days = segment_definition.get("last_order_before_days")
        if last_order_before_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=int(last_order_before_days))
            filters.append(Customer.last_order_date.is_not(None))
            filters.append(Customer.last_order_date <= cutoff)

        include_null_last_order_date = segment_definition.get("include_null_last_order_date")
        if include_null_last_order_date is False:
            filters.append(Customer.last_order_date.is_not(None))

        return filters

    @staticmethod
    async def count_customers(session: AsyncSession, segment_definition: dict) -> int:
        filters = SegmentService.build_customer_filters(segment_definition)
        statement = select(func.count(Customer.id))
        if filters:
            statement = statement.where(and_(*filters))
        result = await session.execute(statement)
        return int(result.scalar_one() or 0)

    @staticmethod
    async def get_matching_customer_ids(session: AsyncSession, segment_definition: dict) -> list[uuid.UUID]:
        filters = SegmentService.build_customer_filters(segment_definition)
        statement = select(Customer.id)
        if filters:
            statement = statement.where(and_(*filters))
        result = await session.execute(statement.order_by(Customer.created_at.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_customer_preview(session: AsyncSession, segment_definition: dict, limit: int = 5) -> list[Customer]:
        filters = SegmentService.build_customer_filters(segment_definition)
        statement = select(Customer)
        if filters:
            statement = statement.where(and_(*filters))
        result = await session.execute(statement.order_by(Customer.created_at.asc()).limit(limit))
        return list(result.scalars().all())

