from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import MarketingAgentOrchestrator
from app.agent.schemas import AgentEventType, MarketingAgentEvent, MarketingAgentRequest, MarketingAgentResponse
from app.core.urls import get_callback_url
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

def _sse(event: MarketingAgentEvent) -> str:
    payload = event.model_dump(mode="json")
    return f"event: {event.event.value}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat", response_model=MarketingAgentResponse)
async def chat_agent(payload: MarketingAgentRequest, request: Request, session: AsyncSession = Depends(get_db)):
    callback_url = get_callback_url(request, "channel_delivery_callback")
    try:
        return await MarketingAgentOrchestrator.run(session, payload, callback_url=callback_url)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Marketing agent request failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Marketing agent failed") from exc


@router.post("/chat/stream")
async def chat_agent_stream(payload: MarketingAgentRequest, request: Request, session: AsyncSession = Depends(get_db)):
    callback_url = get_callback_url(request, "channel_delivery_callback")

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for event in MarketingAgentOrchestrator.stream(session, payload, callback_url=callback_url):
                yield _sse(event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Marketing agent stream failed")
            error_event = MarketingAgentEvent(
                event=AgentEventType.error,
                message="Marketing agent failed",
                payload={"detail": str(exc)},
                timestamp=datetime.now(timezone.utc),
            )
            yield _sse(error_event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
