from fastapi import APIRouter

from app.routes.send import router as send_router

api_router = APIRouter()
api_router.include_router(send_router)

