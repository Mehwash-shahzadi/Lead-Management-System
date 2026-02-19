import logging
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import settings
from app.core.database import get_db
from app.models.agent import Agent
from app.core.exceptions import (
    AgentNotFoundError,
    AgentOverloadError,
    InvalidStatusTransitionError,
)
from app.core.constants import ALLOWED_TRANSITIONS
from app.schemas.common import LeadStatus
from app.services.lead_scoring import LeadScoringEngine
from app.services.lead_assignment import LeadAssignmentManager

logger = logging.getLogger(__name__)


class LeadValidator:
    """Validation logic for leads.

    Duplicate detection and follow-up conflict checks are handled by
    ``LeadCaptureService._check_duplicate()`` and
    ``TaskRepository.find_conflicts()`` respectively — no duplication here.
    """

    @staticmethod
    async def validate_status_transition(
        current_status: str, new_status: LeadStatus
    ) -> None:
        """Validate status transitions using the single source of truth."""
        allowed = ALLOWED_TRANSITIONS.get(current_status, [])
        if new_status.value not in allowed:
            raise InvalidStatusTransitionError(
                f"Cannot transition from {current_status} to {new_status.value}"
            )

    @staticmethod
    async def validate_agent_capacity(agent_id: UUID, db: AsyncSession) -> None:
        from app.core.constants import MAX_AGENT_ACTIVE_LEADS

        agent_query = select(Agent.active_leads_count).where(Agent.agent_id == agent_id)
        result = await db.execute(agent_query)
        active_count = result.scalar_one_or_none()

        if active_count is None:
            raise AgentNotFoundError("Agent not found")

        if active_count >= MAX_AGENT_ACTIVE_LEADS:
            raise AgentOverloadError(
                f"Agent {agent_id} has reached maximum capacity "
                f"of {MAX_AGENT_ACTIVE_LEADS} active leads"
            )

    @staticmethod
    async def validate_lead_data(lead_data: Dict[str, Any]) -> None:
        """Validate lead data fields (service-layer safety net).

        Budget range validation is intentionally **not** duplicated here.
        It is enforced at two levels already:

        1. **Pydantic schema** — ``LeadCreate.validate_budget_range()``
           rejects ``budget_min >= budget_max`` during request parsing
           (HTTP 422).
        2. **Database CHECK** — ``ck_budget_min_lt_max`` on the ``leads``
           table rejects invalid budgets at the storage level.

        This method remains as a hook for future service-layer-only
        validations that cannot be expressed in the Pydantic schema or
        database constraints.
        """
        # Currently a no-op — all existing validations are covered by
        # Pydantic (LeadCreate) and database constraints.
        pass


# ---------------------------------------------------------------------------
# Redis client factory
# ---------------------------------------------------------------------------


async def get_redis_client() -> Redis:
    """Get an async Redis client instance using connection pooling."""
    try:
        client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        await client.ping()
        return client
    except Exception:
        logger.warning("Redis unavailable – caching disabled for this request")
        return None  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Repository factory functions (one per repository, each gets the shared db)
# ---------------------------------------------------------------------------


async def get_lead_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.lead_repository import LeadRepository

    return LeadRepository(db)


async def get_agent_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.agent_repository import AgentRepository

    return AgentRepository(db)


async def get_assignment_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.assignment_repository import AssignmentRepository

    return AssignmentRepository(db)


async def get_task_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.task_repository import TaskRepository

    return TaskRepository(db)


async def get_activity_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.activity_repository import ActivityRepository

    return ActivityRepository(db)


async def get_source_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.lead_source_repository import LeadSourceRepository

    return LeadSourceRepository(db)


async def get_interest_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.property_interest_repository import PropertyInterestRepository

    return PropertyInterestRepository(db)


async def get_property_suggestion_service(
    interest_repo=Depends(get_interest_repo),
):
    """Build a :class:`PropertySuggestionService` with injected repository."""
    from app.services.property_suggestion_service import PropertySuggestionService

    return PropertySuggestionService(interest_repo=interest_repo)


async def get_conversion_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.conversion_history_repository import (
        ConversionHistoryRepository,
    )

    return ConversionHistoryRepository(db)


async def get_dashboard_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.dashboard_repository import DashboardRepository

    return DashboardRepository(db)


async def get_analytics_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.analytics_repository import AnalyticsRepository

    return AnalyticsRepository(db)


# ---------------------------------------------------------------------------
# Cache service factory
# ---------------------------------------------------------------------------


async def get_cache_service(
    redis_client: Redis = Depends(get_redis_client),
):
    """Build a :class:`CacheService` backed by the shared Redis client."""
    from app.core.cache import CacheService

    return CacheService(redis_client=redis_client)


# ---------------------------------------------------------------------------
# Service factory functions
# ---------------------------------------------------------------------------


async def get_scoring_rule_repo(
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.scoring_rule_repository import ScoringRuleRepository

    return ScoringRuleRepository(db)


async def get_scoring_engine(
    scoring_rule_repo=Depends(get_scoring_rule_repo),
    db: AsyncSession = Depends(get_db),
) -> LeadScoringEngine:
    from app.repositories.activity_repository import ActivityRepository

    activity_repo = ActivityRepository(db)
    return LeadScoringEngine(
        scoring_rule_repo=scoring_rule_repo,
        activity_repo=activity_repo,
    )


async def get_assignment_manager(
    cache=Depends(get_cache_service),
) -> LeadAssignmentManager:
    return LeadAssignmentManager(cache=cache)


async def get_lead_capture_service(
    scoring_engine: LeadScoringEngine = Depends(get_scoring_engine),
    assignment_manager: LeadAssignmentManager = Depends(get_assignment_manager),
    cache=Depends(get_cache_service),
    property_service=Depends(get_property_suggestion_service),
):
    """Build a :class:`LeadCaptureService` with injected dependencies."""
    from app.services.lead_capture_service import LeadCaptureService

    return LeadCaptureService(
        scoring_engine=scoring_engine,
        assignment_manager=assignment_manager,
        cache=cache,
        property_service=property_service,
    )


async def get_lead_update_service(
    scoring_engine: LeadScoringEngine = Depends(get_scoring_engine),
):
    """Build a :class:`LeadUpdateService` with injected dependencies."""
    from app.services.lead_update_service import LeadUpdateService

    return LeadUpdateService(scoring_engine=scoring_engine)


async def get_agent_dashboard_service(
    cache=Depends(get_cache_service),
):
    """Build an :class:`AgentDashboardService` with injected dependencies."""
    from app.services.agent_dashboard_service import AgentDashboardService

    return AgentDashboardService(cache=cache)


async def get_analytics_service(
    analytics_repo=Depends(get_analytics_repo),
):
    """Build a :class:`LeadAnalytics` service with injected repository."""
    from app.services.analytics import LeadAnalytics

    return LeadAnalytics(repo=analytics_repo)


# Dependency functions
async def get_validated_db() -> AsyncSession:
    """Get database session with validation setup."""
    return Depends(get_db)
