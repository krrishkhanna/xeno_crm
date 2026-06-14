from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, status

from app.schemas.delivery import SendRequest, SendResponse
from app.services.provider_simulator import ProviderSimulator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/send", response_model=SendResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_message(payload: SendRequest, background_tasks: BackgroundTasks) -> SendResponse:
    request_id = uuid4()
    background_tasks.add_task(
        ProviderSimulator.simulate_delivery,
        customer_id=payload.customer_id,
        communication_id=payload.communication_id,
        message=payload.message,
        callback_url=str(payload.callback_url),
    )
    logger.info("Queued communication %s for customer %s", payload.communication_id, payload.customer_id)
    return SendResponse(request_id=request_id)

