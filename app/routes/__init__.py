from fastapi import APIRouter

from app.routes.agent import router as agent_router
from app.routes.campaigns import router as campaigns_router
from app.routes.communications import router as communications_router
from app.routes.customers import router as customers_router
from app.routes.orders import router as orders_router

api_router = APIRouter()
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])
api_router.include_router(customers_router, prefix="/customers", tags=["customers"])
api_router.include_router(orders_router, prefix="/orders", tags=["orders"])
api_router.include_router(campaigns_router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(communications_router, prefix="/communications", tags=["communications"])
