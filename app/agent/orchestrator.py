from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.config import settings
from app.agent.openai_client import OpenAIPlanner, OpenAIPlannerError
from app.agent.schemas import (
    AgentEventType,
    AgentProvider,
    AgentWorkflowPlan,
    CreateCampaignInput,
    CreateCampaignResult,
    DraftMessageInput,
    DraftMessageResult,
    GetCampaignAnalyticsInput,
    CampaignListItem,
    ListCampaignsInput,
    ListCampaignsResult,
    MarketingAgentEvent,
    MarketingAgentRequest,
    MarketingAgentResponse,
    QueryCustomersInput,
    QueryCustomersResult,
    SendCampaignInput,
    SendCampaignResult,
)
from app.agent.tools import openai_tool_definitions
from app.schemas.campaign import CampaignCreate
from app.schemas.campaign_dispatch import CampaignSendRequest
from app.schemas.common import CampaignStatus, CommunicationChannel
from app.services.campaign_dispatch_service import CampaignDispatchService
from app.services.campaign_service import CampaignService
from app.services.segment_service import SegmentService

logger = logging.getLogger(__name__)

WIN_BACK_DAYS_PATTERN = re.compile(r"(?:haven't|have not|has not|no)\s+ordered\s+in\s+(\d+)\s+days?", re.I)
WIN_BACK_KEYWORDS = ("win-back", "win back", "lapsed", "dormant", "re-engage", "reengage")
KNOWN_CITIES = ("Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai")


class MarketingAgentOrchestrator:
    @staticmethod
    def tool_definitions(provider: AgentProvider = AgentProvider.auto) -> list[dict]:
        return openai_tool_definitions()

    @staticmethod
    def _emit(event: AgentEventType, message: str, tool_name: str | None = None, payload: dict | None = None) -> MarketingAgentEvent:
        return MarketingAgentEvent(
            event=event,
            message=message,
            tool_name=tool_name,
            payload=payload,
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def _parse_intent(user_message: str) -> tuple[str, dict, str]:
        normalized = user_message.strip().lower()
        segment_definition: dict = {}
        objective = "campaign"
        campaign_name = "New Campaign"

        if any(keyword in normalized for keyword in WIN_BACK_KEYWORDS):
            objective = "win-back"
            campaign_name = "Win-back Campaign"
            segment_definition["last_order_before_days"] = 30
            segment_definition["include_null_last_order_date"] = False

        match = WIN_BACK_DAYS_PATTERN.search(normalized)
        if match:
            objective = "win-back"
            days = int(match.group(1))
            segment_definition["last_order_before_days"] = days
            segment_definition["include_null_last_order_date"] = False
            campaign_name = f"Win-back Campaign - {days} Days"

        cities = [city for city in KNOWN_CITIES if city.lower() in normalized]
        if cities:
            segment_definition["cities"] = cities
            if campaign_name == "New Campaign":
                campaign_name = f"{cities[0]} Campaign"

        is_loyalty_prompt = "loyal" in normalized
        is_high_value_prompt = "high value" in normalized or "high-value" in normalized

        if is_loyalty_prompt:
            objective = "loyalty"
            campaign_name = "Loyalty Campaign"
            segment_definition["min_orders"] = 4

        if is_high_value_prompt:
            if not is_loyalty_prompt:
                objective = "high-value"
                campaign_name = "High Value Campaign"
            segment_definition["min_orders"] = max(int(segment_definition.get("min_orders", 1)), 6)

        if "new customer" in normalized or "new customers" in normalized:
            objective = "welcome"
            campaign_name = "Welcome Campaign"
            segment_definition["max_orders"] = 1

        if not segment_definition:
            segment_definition["include_null_last_order_date"] = False

        return objective, segment_definition, campaign_name

    @staticmethod
    def _fallback_plan(user_message: str) -> AgentWorkflowPlan:
        objective, segment_definition, campaign_name = MarketingAgentOrchestrator._parse_intent(user_message)
        if objective == "win-back" and not campaign_name:
            campaign_name = "Win-back Campaign"
        return AgentWorkflowPlan(
            objective=objective,
            segment_definition=segment_definition,
            campaign_name=campaign_name,
            draft_tone="friendly",
            should_send=True,
            should_fetch_analytics=True,
            summary="Fallback plan generated locally because OpenAI planning was unavailable.",
        )

    @staticmethod
    async def _plan_workflow(user_message: str, provider: AgentProvider) -> AgentWorkflowPlan:
        preferred_provider = provider
        if preferred_provider == AgentProvider.auto:
            preferred_provider = AgentProvider.openai if settings.openai_api_key else AgentProvider.local

        if preferred_provider == AgentProvider.openai:
            planner = OpenAIPlanner.from_settings()
            if planner is not None:
                try:
                    return await planner.plan_workflow(user_message)
                except OpenAIPlannerError:
                    logger.exception("OpenAI planning failed; falling back to local planning")

        return MarketingAgentOrchestrator._fallback_plan(user_message)

    @staticmethod
    def _segment_summary(segment_size: int, segment_definition: dict) -> str:
        parts = [f"{segment_size} matching customers"]
        if cities := segment_definition.get("cities"):
            parts.append(f"cities: {', '.join(cities)}")
        if days := segment_definition.get("last_order_before_days"):
            parts.append(f"last order before {days} days")
        if min_orders := segment_definition.get("min_orders"):
            parts.append(f"min orders {min_orders}")
        if max_orders := segment_definition.get("max_orders"):
            parts.append(f"max orders {max_orders}")
        return "; ".join(parts)

    @staticmethod
    def _draft_message(objective: str, segment_size: int, segment_summary: str, tone: str = "friendly") -> DraftMessageResult:
        if objective == "win-back":
            campaign_name = "Win-back Campaign"
            message = (
                f"Hi from Brew & Co - we miss you. It's been a while since your last order, "
                f"and we'd love to welcome you back with something fresh and comforting. "
                f"Tap back in today and rediscover your next favorite cup."
            )
        elif objective == "loyalty":
            campaign_name = "Loyalty Campaign"
            message = (
                f"Thanks for being a regular at Brew & Co. We've prepared something special "
                f"for our most loyal guests - enjoy an exclusive perk on your next visit."
            )
        elif objective == "high-value":
            campaign_name = "Premium Offer Campaign"
            message = (
                f"As one of Brew & Co's valued customers, you're invited to a premium offer "
                f"crafted for customers who love our best blends and bundles."
            )
        elif objective == "welcome":
            campaign_name = "Welcome Campaign"
            message = (
                f"Welcome to Brew & Co. We're excited to have you with us - here's a warm hello "
                f"and a special reason to come back soon."
            )
        else:
            campaign_name = "Marketing Campaign"
            message = (
                f"Brew & Co has a new update for you. We've prepared a message for {segment_summary} "
                f"with a {tone} tone."
            )

        if segment_size <= 20 and objective == "win-back":
            message += " This is a focused offer for a small, highly relevant audience."

        return DraftMessageResult(campaign_name=campaign_name, message=message)

    @staticmethod
    async def _query_customers(session: AsyncSession, payload: QueryCustomersInput) -> QueryCustomersResult:
        segment_size = await SegmentService.count_customers(session, payload.segment_definition)
        preview_customers = await SegmentService.get_customer_preview(session, payload.segment_definition, payload.sample_size)
        sample_customers = [
            {
                "id": str(customer.id),
                "name": customer.name,
                "email": customer.email,
                "city": customer.city,
                "total_orders": customer.total_orders,
                "last_order_date": customer.last_order_date.isoformat() if customer.last_order_date else None,
                "tags": list(customer.tags or []),
            }
            for customer in preview_customers
        ]
        return QueryCustomersResult(
            segment_definition=payload.segment_definition,
            segment_size=segment_size,
            sample_customers=sample_customers,
        )

    @staticmethod
    async def _create_campaign(session: AsyncSession, payload: CreateCampaignInput) -> CreateCampaignResult:
        campaign = await CampaignService.create_campaign(
            session,
            CampaignCreate(
                name=payload.campaign_name,
                message=payload.message,
                segment_definition=payload.segment_definition,
                status=CampaignStatus.ready,
            ),
        )
        return CreateCampaignResult(campaign_id=campaign.id, campaign_name=campaign.name, status=campaign.status)

    @staticmethod
    async def _send_campaign(
        session: AsyncSession,
        payload: SendCampaignInput,
        callback_url: str,
    ) -> SendCampaignResult:
        result = await CampaignDispatchService.send_campaign(
            session,
            CampaignSendRequest(campaign_id=payload.campaign_id, channel=payload.channel),
            callback_url=callback_url,
        )
        return SendCampaignResult.model_validate(result.model_dump(mode="json"))

    @staticmethod
    async def _get_campaign_analytics(session: AsyncSession, payload: GetCampaignAnalyticsInput):
        return await CampaignService.get_campaign_analytics(session, payload.campaign_id)

    @staticmethod
    async def _list_campaigns(session: AsyncSession, payload: ListCampaignsInput) -> ListCampaignsResult:
        campaigns = await CampaignService.list_campaigns(session, skip=payload.skip, limit=payload.limit)
        return ListCampaignsResult(campaigns=[CampaignListItem.model_validate(campaign) for campaign in campaigns])

    @staticmethod
    async def _wait_for_analytics(
        session: AsyncSession,
        campaign_id: UUID,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        last_payload = None
        stable_rounds = 0

        while True:
            payload = await CampaignService.get_campaign_analytics(session, campaign_id)
            last_payload = payload
            terminal_count = payload.delivered + payload.opened + payload.clicked + payload.failed
            if terminal_count >= payload.sent and payload.sent > 0:
                stable_rounds += 1
                if stable_rounds >= 2:
                    return payload
            else:
                stable_rounds = 0

            if loop.time() >= deadline:
                return last_payload

            await asyncio.sleep(poll_interval_seconds)

    @staticmethod
    async def run(
        session: AsyncSession,
        request: MarketingAgentRequest,
        *,
        callback_url: str,
    ) -> MarketingAgentResponse:
        plan = await MarketingAgentOrchestrator._plan_workflow(request.message, request.provider)
        objective = plan.objective
        segment_definition = plan.segment_definition
        suggested_campaign_name = plan.campaign_name

        logger.info("Agent planning request objective=%s segment=%s", objective, segment_definition)

        query_result = await MarketingAgentOrchestrator._query_customers(
            session,
            QueryCustomersInput(segment_definition=segment_definition, sample_size=request.sample_size),
        )
        segment_summary = MarketingAgentOrchestrator._segment_summary(query_result.segment_size, segment_definition)

        draft_result = MarketingAgentOrchestrator._draft_message(
            objective=objective,
            segment_size=query_result.segment_size,
            segment_summary=segment_summary,
            tone=plan.draft_tone,
        )

        campaign_name = draft_result.campaign_name if draft_result.campaign_name else suggested_campaign_name
        if campaign_name == "Marketing Campaign":
            campaign_name = suggested_campaign_name

        campaign_result = await MarketingAgentOrchestrator._create_campaign(
            session,
            CreateCampaignInput(
                campaign_name=campaign_name,
                message=draft_result.message,
                segment_definition=segment_definition,
            ),
        )

        if plan.should_send:
            send_result = await MarketingAgentOrchestrator._send_campaign(
                session,
                SendCampaignInput(campaign_id=campaign_result.campaign_id, channel=request.channel),
                callback_url=callback_url,
            )
        else:
            send_result = SendCampaignResult(
                campaign_id=campaign_result.campaign_id,
                campaign_status="ready",
                matched_customers=query_result.segment_size,
                communications_created=0,
                communications_queued=0,
                communications_failed_to_queue=0,
                callback_url=callback_url,
                channel_service_url="",
                dispatched_at=datetime.now(timezone.utc),
            )

        analytics = await MarketingAgentOrchestrator._wait_for_analytics(
            session,
            campaign_result.campaign_id,
            request.analytics_timeout_seconds,
            settings.analytics_poll_interval_seconds,
        ) if plan.should_fetch_analytics else await CampaignService.get_campaign_analytics(
            session, campaign_result.campaign_id
        )

        summary = (
            f"Segment identified with {query_result.segment_size} customers. "
            f"Created campaign '{campaign_result.campaign_name}' and dispatched it on {request.channel.value}. "
            f"Analytics are now available."
        )

        return MarketingAgentResponse(
            objective=objective,
            segment_definition=segment_definition,
            segment_size=query_result.segment_size,
            campaign_id=campaign_result.campaign_id,
            campaign_name=campaign_result.campaign_name,
            campaign_status=send_result.campaign_status,
            draft_message=draft_result.message,
            analytics=analytics,
            summary=plan.summary or summary,
        )

    @staticmethod
    async def stream(
        session: AsyncSession,
        request: MarketingAgentRequest,
        *,
        callback_url: str,
    ) -> AsyncIterator[MarketingAgentEvent]:
        plan = await MarketingAgentOrchestrator._plan_workflow(request.message, request.provider)
        objective = plan.objective
        segment_definition = plan.segment_definition
        suggested_campaign_name = plan.campaign_name
        yield MarketingAgentOrchestrator._emit(
            AgentEventType.planning,
            f"Planning campaign workflow for objective '{objective}' using OpenAI-backed planning.",
            payload={"objective": objective, "segment_definition": segment_definition, "plan": plan.model_dump()},
        )

        query_input = QueryCustomersInput(segment_definition=segment_definition, sample_size=request.sample_size)
        yield MarketingAgentOrchestrator._emit(
            AgentEventType.tool_call,
            "Querying matching customers.",
            tool_name="query_customers",
            payload=query_input.model_dump(),
        )
        query_result = await MarketingAgentOrchestrator._query_customers(session, query_input)
        yield MarketingAgentOrchestrator._emit(
            AgentEventType.tool_result,
            f"Found {query_result.segment_size} matching customers.",
            tool_name="query_customers",
            payload=query_result.model_dump(),
        )

        segment_summary = MarketingAgentOrchestrator._segment_summary(query_result.segment_size, segment_definition)
        draft_input = DraftMessageInput(
            objective=objective,
            segment_summary=segment_summary,
            tone=plan.draft_tone,
            campaign_name_hint=suggested_campaign_name,
        )
        yield MarketingAgentOrchestrator._emit(
            AgentEventType.tool_call,
            "Drafting campaign message.",
            tool_name="draft_message",
            payload=draft_input.model_dump(),
        )
        draft_result = MarketingAgentOrchestrator._draft_message(
            objective=objective,
            segment_size=query_result.segment_size,
            segment_summary=segment_summary,
        )
        yield MarketingAgentOrchestrator._emit(
            AgentEventType.tool_result,
            f"Drafted campaign '{draft_result.campaign_name}'.",
            tool_name="draft_message",
            payload=draft_result.model_dump(),
        )

        create_input = CreateCampaignInput(
            campaign_name=draft_result.campaign_name if draft_result.campaign_name else suggested_campaign_name,
            message=draft_result.message,
            segment_definition=segment_definition,
        )
        yield MarketingAgentOrchestrator._emit(
            AgentEventType.tool_call,
            "Creating campaign record.",
            tool_name="create_campaign",
            payload=create_input.model_dump(),
        )
        campaign_result = await MarketingAgentOrchestrator._create_campaign(session, create_input)
        yield MarketingAgentOrchestrator._emit(
            AgentEventType.tool_result,
            f"Created campaign {campaign_result.campaign_name}.",
            tool_name="create_campaign",
            payload=campaign_result.model_dump(),
        )

        if plan.should_send:
            send_input = SendCampaignInput(campaign_id=campaign_result.campaign_id, channel=request.channel)
            yield MarketingAgentOrchestrator._emit(
                AgentEventType.tool_call,
                "Sending campaign to the channel service.",
                tool_name="send_campaign",
                payload=send_input.model_dump(),
            )
            send_result = await MarketingAgentOrchestrator._send_campaign(session, send_input, callback_url=callback_url)
            yield MarketingAgentOrchestrator._emit(
                AgentEventType.tool_result,
                f"Campaign dispatch queued for {send_result.communications_queued} customers.",
                tool_name="send_campaign",
                payload=send_result.model_dump(mode="json"),
            )
        else:
            send_result = SendCampaignResult(
                campaign_id=campaign_result.campaign_id,
                campaign_status="ready",
                matched_customers=query_result.segment_size,
                communications_created=0,
                communications_queued=0,
                communications_failed_to_queue=0,
                callback_url=callback_url,
                channel_service_url="",
                dispatched_at=datetime.now(timezone.utc),
            )
            yield MarketingAgentOrchestrator._emit(
                AgentEventType.status,
                "Campaign created but not dispatched because OpenAI planned a no-send workflow.",
                payload=send_result.model_dump(mode="json"),
            )

        analytics_input = GetCampaignAnalyticsInput(campaign_id=campaign_result.campaign_id)
        yield MarketingAgentOrchestrator._emit(
            AgentEventType.tool_call,
            "Polling campaign analytics.",
            tool_name="get_campaign_analytics",
            payload=analytics_input.model_dump(),
        )
        analytics = await MarketingAgentOrchestrator._wait_for_analytics(
            session,
            campaign_result.campaign_id,
            request.analytics_timeout_seconds,
            settings.analytics_poll_interval_seconds,
        )
        yield MarketingAgentOrchestrator._emit(
            AgentEventType.tool_result,
            "Analytics collected.",
            tool_name="get_campaign_analytics",
            payload=analytics.model_dump(),
        )

        yield MarketingAgentOrchestrator._emit(
            AgentEventType.final,
            f"Done. Sent a {objective} campaign to {query_result.segment_size} customers.",
            payload={
                "objective": objective,
                "segment_definition": segment_definition,
                "segment_size": query_result.segment_size,
                "campaign_id": str(campaign_result.campaign_id),
                "campaign_name": campaign_result.campaign_name,
                "analytics": analytics.model_dump(),
                "plan": plan.model_dump(),
            },
        )
