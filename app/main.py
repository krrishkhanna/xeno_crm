from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_tables
from app.models import Campaign, Communication, Customer, Order  # noqa: F401
from app.routes import api_router
from app.routes.campaigns import send_router as campaign_send_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_tables()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Xeno CRM Backend",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix="/api/v1")
    application.include_router(campaign_send_router)

    @application.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    @application.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {"message": "Xeno CRM Backend"}

    return application


app = create_app()
