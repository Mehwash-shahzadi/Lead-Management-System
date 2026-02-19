from fastapi import APIRouter

from app.api.v1.endpoints import leads, agents, analytics, health

router = APIRouter(prefix="/api/v1")

router.include_router(leads.router)
router.include_router(agents.router)
router.include_router(analytics.router)
router.include_router(health.router)
