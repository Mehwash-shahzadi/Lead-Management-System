import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import logging

from app.api.v1.router import router as api_v1_router
from app.core.exceptions import (
    AgentNotFoundError,
    AssignmentNotFoundError,
    DuplicateLeadError,
    AgentOverloadError,
    InvalidLeadDataError,
    FollowUpConflictError,
    InvalidStatusTransitionError,
    LeadNotFoundError,
    NoAgentAssignedError,
    OverdueTaskError,
    PropertyServiceUnavailableError,
)
from app.core.config import settings as app_settings
from app.core.rate_limit import limiter
from app.services.auto_reassign import start_auto_reassign_loop
from app.core.database import AsyncSessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application-level background tasks."""
    # Start the 24-hour auto-reassignment background loop
    reassign_task = asyncio.create_task(start_auto_reassign_loop(AsyncSessionLocal))
    logger.info("Background auto-reassignment task scheduled")
    yield
    # Shutdown: cancel the background task
    reassign_task.cancel()
    try:
        await reassign_task
    except asyncio.CancelledError:
        logger.info("Background auto-reassignment task stopped")


app = FastAPI(
    title="ThinkRealty Lead Management System",
    description="Professional lead management for UAE real estate with AI-powered scoring",
    version="0.1.0",
    lifespan=lifespan,
)

# Attach rate limiter state so slowapi middleware can find it
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware – restricted to configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip() for o in app_settings.CORS_ORIGINS.split(",") if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)


@app.exception_handler(AgentNotFoundError)
async def agent_not_found_handler(request: Request, exc: AgentNotFoundError):
    logger.warning("Agent not found: %s", exc.detail)
    return JSONResponse(
        status_code=404,
        content={"detail": exc.detail, "type": "agent_not_found"},
    )


@app.exception_handler(LeadNotFoundError)
async def lead_not_found_handler(request: Request, exc: LeadNotFoundError):
    logger.warning("Lead not found: %s", exc.detail)
    return JSONResponse(
        status_code=404,
        content={"detail": exc.detail, "type": "lead_not_found"},
    )


@app.exception_handler(NoAgentAssignedError)
async def no_agent_assigned_handler(request: Request, exc: NoAgentAssignedError):
    logger.warning("No agent assigned: %s", exc.detail)
    return JSONResponse(
        status_code=422,
        content={"detail": exc.detail, "type": "no_agent_assigned"},
    )


@app.exception_handler(AssignmentNotFoundError)
async def assignment_not_found_handler(request: Request, exc: AssignmentNotFoundError):
    logger.warning("Assignment not found: %s", exc.detail)
    return JSONResponse(
        status_code=404,
        content={"detail": exc.detail, "type": "assignment_not_found"},
    )


@app.exception_handler(DuplicateLeadError)
async def duplicate_lead_handler(request: Request, exc: DuplicateLeadError):
    logger.warning("Duplicate lead detected: %s", exc.detail)
    return JSONResponse(
        status_code=409,
        content={"detail": exc.detail, "type": "duplicate_lead"},
    )


@app.exception_handler(AgentOverloadError)
async def agent_overload_handler(request: Request, exc: AgentOverloadError):
    logger.error("Agent overload: %s", exc.detail)
    return JSONResponse(
        status_code=503,
        content={"detail": exc.detail, "type": "agent_overload"},
    )


@app.exception_handler(InvalidLeadDataError)
async def invalid_lead_data_handler(request: Request, exc: InvalidLeadDataError):
    logger.warning("Invalid lead data: %s", exc.detail)
    return JSONResponse(
        status_code=422,
        content={"detail": exc.detail, "type": "invalid_lead_data"},
    )


@app.exception_handler(FollowUpConflictError)
async def follow_up_conflict_handler(request: Request, exc: FollowUpConflictError):
    logger.warning("Follow-up conflict: %s", exc.detail)
    return JSONResponse(
        status_code=409,
        content={"detail": exc.detail, "type": "follow_up_conflict"},
    )


@app.exception_handler(InvalidStatusTransitionError)
async def invalid_status_transition_handler(
    request: Request, exc: InvalidStatusTransitionError
):
    logger.warning("Invalid status transition: %s", exc.detail)
    return JSONResponse(
        status_code=400,
        content={"detail": exc.detail, "type": "invalid_status_transition"},
    )


@app.exception_handler(PropertyServiceUnavailableError)
async def property_service_unavailable_handler(
    request: Request, exc: PropertyServiceUnavailableError
):
    logger.error("Property service unavailable: %s", exc.detail)
    return JSONResponse(
        status_code=503,
        content={"detail": exc.detail, "type": "property_service_unavailable"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Request validation error: %s", exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors(),
            "type": "validation_error",
        },
    )


@app.exception_handler(OverdueTaskError)
async def overdue_task_handler(request: Request, exc: OverdueTaskError):
    logger.warning("Overdue task blocked: %s", exc)
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "type": "overdue_task"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unexpected/unhandled exceptions.

    Returns a generic 500 response so that raw stack traces are never
    leaked to the client.
    """
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected internal error occurred. Please try again later.",
            "type": "internal_server_error",
        },
    )
