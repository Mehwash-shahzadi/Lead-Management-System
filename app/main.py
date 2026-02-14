"""FastAPI application entry point (Day 1: minimal setup)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging

from app.routers.leads import router as leads_router
from app.routers.agents import router as agents_router
from app.exceptions import (
    DuplicateLeadError,
    AgentOverloadError,
    InvalidLeadDataError,
    FollowUpConflictError,
    InvalidStatusTransitionError,
    PropertyServiceUnavailableError
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ThinkRealty Lead Management System",
    description="Professional lead management for UAE real estate with AI-powered scoring",
    version="0.1.0",
)

app.include_router(leads_router)
app.include_router(agents_router)


@app.exception_handler(DuplicateLeadError)
async def duplicate_lead_handler(request: Request, exc: DuplicateLeadError):
    logger.warning(f"Duplicate lead detected: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "duplicate_lead"}
    )


@app.exception_handler(AgentOverloadError)
async def agent_overload_handler(request: Request, exc: AgentOverloadError):
    logger.error(f"Agent overload: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "agent_overload"}
    )


@app.exception_handler(InvalidLeadDataError)
async def invalid_lead_data_handler(request: Request, exc: InvalidLeadDataError):
    logger.warning(f"Invalid lead data: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "invalid_lead_data"}
    )


@app.exception_handler(FollowUpConflictError)
async def follow_up_conflict_handler(request: Request, exc: FollowUpConflictError):
    logger.warning(f"Follow-up conflict: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "follow_up_conflict"}
    )


@app.exception_handler(InvalidStatusTransitionError)
async def invalid_status_transition_handler(request: Request, exc: InvalidStatusTransitionError):
    logger.warning(f"Invalid status transition: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "invalid_status_transition"}
    )


@app.exception_handler(PropertyServiceUnavailableError)
async def property_service_unavailable_handler(request: Request, exc: PropertyServiceUnavailableError):
    logger.error(f"Property service unavailable: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "property_service_unavailable"}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Request validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors(),
            "type": "validation_error"
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
