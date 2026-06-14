from __future__ import annotations

import asyncio
import random
import sys
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import cast

from faker import Faker
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import AsyncSessionLocal, create_db_tables
from app.models.campaign import Campaign
from app.models.communication import Communication
from app.models.customer import Customer
from app.models.order import Order

SEED = 42
TOTAL_CUSTOMERS = 200
TOTAL_ORDERS = 800

CITIES = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"]
CUSTOMER_TYPE_COUNTS = {
    "loyal": 55,
    "high_value": 25,
    "dormant": 50,
    "new_customer": 70,
}
GROUP_ORDER_BUDGETS = {
    "loyal": 440,
    "high_value": 190,
    "dormant": 70,
    "new_customer": 100,
}
GROUP_ORDER_BOUNDS = {
    "loyal": (6, 12),
    "high_value": (4, 10),
    "dormant": (1, 3),
    "new_customer": (0, 2),
}
GROUP_DATE_WINDOWS = {
    "loyal": (150, 0),
    "high_value": (240, 7),
    "dormant": (365, 120),
    "new_customer": (45, 0),
}
GROUP_CATEGORY_POOL = {
    "loyal": ["latte", "cappuccino", "cold_brew", "snacks", "dessert"],
    "high_value": ["single_origin_beans", "gift_box", "cold_brew_case", "premium_bundle", "subscription_recharge"],
    "dormant": ["espresso", "filter_coffee", "pastry", "snack_combo"],
    "new_customer": ["welcome_latte", "starter_pack", "croissant_combo", "mini_cold_brew"],
}
GROUP_AMOUNT_RANGE = {
    "loyal": (120.0, 320.0),
    "high_value": (380.0, 1800.0),
    "dormant": (90.0, 240.0),
    "new_customer": (80.0, 180.0),
}
GROUP_WEIGHTS = {
    "loyal": (0.8, 1.8),
    "high_value": (1.2, 2.4),
    "dormant": (0.5, 1.0),
    "new_customer": (0.2, 0.9),
}

fake = Faker()
Faker.seed(SEED)
fake.seed_instance(SEED)
random.seed(SEED)


@dataclass(slots=True)
class CustomerPlan:
    customer_type: str
    name: str
    email: str
    phone: str
    city: str
    tags: list[str]
    order_target: int
    order_dates: list[datetime]


def slugify_name(name: str) -> str:
    return "-".join(part.lower() for part in name.split() if part)


def build_tags(customer_type: str, city: str) -> list[str]:
    base_tags = {
        "loyal": ["frequent-buyer", "morning-regular", "rewards-sensitive"],
        "high_value": ["premium-shopper", "bundle-friendly", "new-launch"],
        "dormant": ["lapsed", "winback", "seasonal-only"],
        "new_customer": ["first-time", "welcome-series", "trial-stage"],
    }
    coffee_tags = {
        "loyal": ["latte", "cold-brew"],
        "high_value": ["beans", "gift-box"],
        "dormant": ["espresso", "pastry"],
        "new_customer": ["starter-drink", "croissant"],
    }
    return [city.lower(), *base_tags[customer_type], *coffee_tags[customer_type]]


def distribute_orders(
    plans: list[CustomerPlan],
    customer_type: str,
    budget: int,
) -> None:
    type_plans = [plan for plan in plans if plan.customer_type == customer_type]
    if not type_plans:
        return

    minimum, maximum = GROUP_ORDER_BOUNDS[customer_type]
    counts = {id(plan): minimum for plan in type_plans}
    remaining = budget - minimum * len(type_plans)

    if remaining < 0:
        raise ValueError(f"Order budget for {customer_type} is too small")

    while remaining > 0:
        eligible = [plan for plan in type_plans if counts[id(plan)] < maximum]
        if not eligible:
            raise ValueError(f"Order budget for {customer_type} exceeds maximum capacity")

        weights = [random.uniform(*GROUP_WEIGHTS[customer_type]) for _ in eligible]
        selected = random.choices(eligible, weights=weights, k=1)[0]
        counts[id(selected)] += 1
        remaining -= 1

    for plan in type_plans:
        plan.order_target = counts[id(plan)]


def build_order_dates(customer_type: str, order_count: int) -> list[datetime]:
    if order_count <= 0:
        return []

    oldest_days, newest_days = GROUP_DATE_WINDOWS[customer_type]
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=oldest_days)
    end = now - timedelta(days=newest_days)
    if end < start:
        start, end = end, start

    span_seconds = max(int((end - start).total_seconds()), 1)

    if order_count == 1:
        return [start + timedelta(seconds=span_seconds)]

    offsets = sorted(random.betavariate(1.8, 1.2) for _ in range(order_count))
    return [start + timedelta(seconds=int(span_seconds * offset)) for offset in offsets]


def build_amount(customer_type: str, product_category: str) -> Decimal:
    minimum, maximum = GROUP_AMOUNT_RANGE[customer_type]
    value = random.uniform(minimum, maximum)

    if product_category in {"single_origin_beans", "premium_bundle", "subscription_recharge"}:
        value *= 1.18
    elif product_category in {"gift_box", "cold_brew_case"}:
        value *= 1.12
    elif product_category in {"pastry", "snack_combo", "starter_pack"}:
        value *= 0.9

    return Decimal(f"{value:.2f}")


def build_plan(customer_type: str, index: int) -> CustomerPlan:
    name = fake.name()
    email = f"{slugify_name(name)}.{customer_type}.{index + 1}@brewandco.in"
    phone = f"+91-{random.randint(6000000000, 9999999999)}"
    city = random.choice(CITIES)
    tags = build_tags(customer_type, city)
    return CustomerPlan(
        customer_type=customer_type,
        name=name,
        email=email,
        phone=phone,
        city=city,
        tags=tags,
        order_target=0,
        order_dates=[],
    )


def generate_customer_plans() -> list[CustomerPlan]:
    plans: list[CustomerPlan] = []
    for customer_type, count in CUSTOMER_TYPE_COUNTS.items():
        plans.extend(build_plan(customer_type, index) for index in range(count))

    random.shuffle(plans)

    for customer_type, budget in GROUP_ORDER_BUDGETS.items():
        distribute_orders(plans, customer_type, budget)

    for plan in plans:
        plan.order_dates = build_order_dates(plan.customer_type, plan.order_target)

    return plans


def build_customer_models(plans: Iterable[CustomerPlan]) -> list[Customer]:
    now = datetime.now(timezone.utc)
    customers: list[Customer] = []

    for plan in plans:
        last_order_date = plan.order_dates[-1] if plan.order_dates else None
        created_at = (
            plan.order_dates[0] - timedelta(days=random.randint(2, 14))
            if plan.order_dates
            else now - timedelta(days=random.randint(0, 60))
        )

        customer = Customer(
            id=uuid.uuid4(),
            name=plan.name,
            email=plan.email,
            phone=plan.phone,
            city=plan.city,
            total_orders=plan.order_target,
            last_order_date=last_order_date,
            tags=plan.tags,
            created_at=created_at,
            updated_at=created_at,
        )
        customers.append(customer)

    return customers


def build_order_models(customers: list[Customer], plans: list[CustomerPlan]) -> list[Order]:
    orders: list[Order] = []
    customer_to_plan = {customer.email: plan for customer, plan in zip(customers, plans)}

    for customer in customers:
        plan = cast(CustomerPlan, customer_to_plan[customer.email])
        for order_date in plan.order_dates:
            category = random.choice(GROUP_CATEGORY_POOL[plan.customer_type])
            orders.append(
                Order(
                    customer_id=customer.id,
                    amount=build_amount(plan.customer_type, category),
                    product_category=category,
                    created_at=order_date,
                )
            )

    return orders


async def reset_tables(session: AsyncSession) -> None:
    await session.execute(delete(Communication))
    await session.execute(delete(Campaign))
    await session.execute(delete(Order))
    await session.execute(delete(Customer))
    await session.commit()


async def seed_database() -> None:
    await create_db_tables()

    plans = generate_customer_plans()
    customers = build_customer_models(plans)

    async with AsyncSessionLocal() as session:
        await reset_tables(session)

        session.add_all(customers)
        await session.flush()

        orders = build_order_models(customers, plans)
        session.add_all(orders)
        await session.commit()


def validate_counts(customers: list[Customer], orders: list[Order]) -> None:
    if len(customers) != TOTAL_CUSTOMERS:
        raise RuntimeError(f"Expected {TOTAL_CUSTOMERS} customers, got {len(customers)}")
    if len(orders) != TOTAL_ORDERS:
        raise RuntimeError(f"Expected {TOTAL_ORDERS} orders, got {len(orders)}")


async def main() -> None:
    plans = generate_customer_plans()
    customers = build_customer_models(plans)
    orders = build_order_models(customers, plans)
    validate_counts(customers, orders)

    async with AsyncSessionLocal() as session:
        await create_db_tables()
        await reset_tables(session)
        session.add_all(customers)
        await session.flush()
        session.add_all(orders)
        await session.commit()

    type_counts = {customer_type: sum(1 for plan in plans if plan.customer_type == customer_type) for customer_type in CUSTOMER_TYPE_COUNTS}
    print("Seed complete")
    print(f"Customers: {len(customers)}")
    print(f"Orders: {len(orders)}")
    print(f"Customer mix: {type_counts}")


if __name__ == "__main__":
    asyncio.run(main())
