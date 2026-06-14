from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes import api_router


def create_app() -> FastAPI:
    application = FastAPI(title=settings.app_name, version="1.0.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    return application


app = create_app()

