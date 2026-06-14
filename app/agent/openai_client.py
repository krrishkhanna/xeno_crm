from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.agent.config import settings
from app.agent.schemas import AgentWorkflowPlan

logger = logging.getLogger(__name__)


class OpenAIPlannerError(RuntimeError):
    pass


@dataclass(slots=True)
class OpenAIPlanner:
    client: AsyncOpenAI
    model: str

    @classmethod
    def from_settings(cls) -> "OpenAIPlanner | None":
        if not settings.openai_api_key or "your-openai" in settings.openai_api_key or "placeholder" in settings.openai_api_key:
            return None
        client_kwargs: dict[str, object] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url.rstrip("/")
        return cls(
            client=AsyncOpenAI(**client_kwargs),
            model=settings.openai_model,
        )

    async def plan_workflow(self, user_message: str) -> AgentWorkflowPlan:
        system_prompt = (
            "You are a marketing CRM planning agent. "
            "Translate the user's instruction into a JSON workflow plan only. "
            "Return exactly these keys: objective, segment_definition, campaign_name, "
            "draft_tone, should_send, should_fetch_analytics, summary. "
            "Use segment_definition fields such as: cities, min_orders, max_orders, "
            "last_order_before_days, last_order_within_days, include_null_last_order_date, tags_any, tags_all. "
            "For win-back customers who have not ordered in N days, set last_order_before_days=N and include_null_last_order_date=false. "
            "For dormant customers, default to last_order_before_days=30 and include_null_last_order_date=false. "
            "For high-value customers, prefer min_orders=6 unless the user specifies otherwise. "
            "When the user mentions a city, include it in cities. "
            "Keep the campaign_name short and marketer-friendly. "
            "Set should_send to true unless the user explicitly asks only to draft or create. "
            "Set should_fetch_analytics to true unless the user explicitly asks not to send."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenAI planning request failed")
            raise OpenAIPlannerError("OpenAI request failed") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise OpenAIPlannerError("OpenAI returned an empty planning response")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("OpenAI returned invalid JSON planning output: %s", content)
            raise OpenAIPlannerError("OpenAI planning response was not valid JSON") from exc

        return AgentWorkflowPlan.model_validate(parsed)
