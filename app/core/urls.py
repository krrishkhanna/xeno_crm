from __future__ import annotations

from fastapi import Request

from app.core.config import settings


def get_callback_url(request: Request, route_name: str) -> str:
    if settings.crm_callback_url:
        return settings.crm_callback_url.rstrip("/")
    if settings.crm_public_url:
        return f"{settings.crm_public_url.rstrip('/')}{request.url_for(route_name).path}"
    return str(request.url_for(route_name))
