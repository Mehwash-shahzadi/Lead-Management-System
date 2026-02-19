import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.core.cache import CacheService
from app.core.config import settings
from app.dependencies import LeadValidator
from app.core.constants import MAX_AGENT_ACTIVE_LEADS
from app.core.exceptions import AgentNotFoundError, AgentOverloadError
from app.repositories.agent_repository import AgentRepository
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.lead_source_repository import LeadSourceRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.lead import LeadCreate
from app.schemas.common import SourceType
from app.services.lead_assignment import LeadAssignmentManager
from app.services.lead_scoring import LeadScoringEngine
from app.services.property_suggestion_service import PropertySuggestionService

logger = logging.getLogger(__name__)


class LeadCaptureService:
    """Orchestrates the full lead-capture workflow.

    Dependencies are injected via the constructor so the class remains
    stateless and easily testable.
    """

    def __init__(
        self,
        scoring_engine: LeadScoringEngine,
        assignment_manager: LeadAssignmentManager,
        cache: Optional[CacheService] = None,
        property_service: Optional[PropertySuggestionService] = None,
    ) -> None:
        self._scoring_engine = scoring_engine
        self._assignment_manager = assignment_manager
        self._cache: CacheService = cache or CacheService()
        self._property_service = property_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def capture_lead(
        self,
        source_type: SourceType,
        lead_data: LeadCreate,
        source_details: Dict[str, Any],
        lead_repo: LeadRepository,
        agent_repo: AgentRepository,
        assignment_repo: AssignmentRepository,
        source_repo: LeadSourceRepository,
        task_repo: TaskRepository,
    ) -> Dict[str, Any]:
        """Execute the complete lead-capture pipeline.

        Steps:
        1. Validate lead data
        2. Check for duplicates (Redis-first, then DB fallback)
        3. Verify property service availability
        4. Score the lead
        5. Assign an agent
        6. Persist lead, source, assignment, and initial follow-up task
        7. Fetch suggested properties (stubbed)

        Returns a dict suitable for building ``LeadCaptureResponse``.

        Raises:
            DuplicateLeadError: If a matching lead exists within 24 h.
            AgentOverloadError: If no agent has capacity.
            InvalidLeadDataError: If business-rule validation fails.
            PropertyServiceUnavailableError: If the property service is down.
        """
        lead_dict = lead_data.model_dump()

        # 1. Validate lead data (business rules)
        await LeadValidator.validate_lead_data(lead_dict)

        # 2. Duplicate detection (Redis cache → DB fallback)
        await self._check_duplicate(lead_data.phone, source_type.value, lead_repo)

        # 3. Property service availability
        if self._property_service:
            await self._property_service.check_availability()

        # 4. Calculate lead score (pure business logic)
        source_details_with_type: Dict[str, Any] = {
            **source_details,
            "source_type": source_type.value,
        }
        lead_score: int = await self._scoring_engine.calculate_lead_score(
            lead_dict, source_details_with_type
        )

        # 5. Assign an agent (business rule: specialisation + workload)
        agent_id: Optional[UUID] = await self._assignment_manager.assign_lead(
            lead_dict, agent_repo
        )
        if not agent_id:
            raise AgentOverloadError(
                "All agents are at maximum capacity "
                f"({MAX_AGENT_ACTIVE_LEADS} active leads)"
            )

        # Defence-in-depth: verify the assigned agent still has capacity
        # (guards against race conditions between selection and persistence)
        active_count = await agent_repo.get_active_leads_count(agent_id)
        if active_count is None:
            raise AgentNotFoundError()
        if active_count >= MAX_AGENT_ACTIVE_LEADS:
            raise AgentOverloadError(
                f"Agent {agent_id} has reached maximum capacity "
                f"of {MAX_AGENT_ACTIVE_LEADS} active leads"
            )

        # 6. Persist all records via repositories
        lead_id = uuid4()
        lead, follow_up_task = await self._create_records(
            lead_id=lead_id,
            source_type=source_type,
            lead_data=lead_data,
            lead_score=lead_score,
            source_details=source_details,
            agent_id=agent_id,
            lead_repo=lead_repo,
            agent_repo=agent_repo,
            assignment_repo=assignment_repo,
            source_repo=source_repo,
            task_repo=task_repo,
        )

        # Cache the new lead phone+source for fast duplicate detection
        await self._cache_lead_duplicate_key(
            lead_data.phone, source_type.value, str(lead_id)
        )

        # 7. Suggested properties based on lead preferences
        suggested_properties: List[str] = await self._get_property_suggestions(
            lead_data
        )

        # Fetch agent details for the response
        agent = await agent_repo.get_by_id(agent_id)

        await lead_repo.commit()

        return {
            "lead_id": lead_id,
            "assigned_agent": {
                "agent_id": agent.agent_id,
                "name": agent.full_name,
                "phone": agent.phone,
            },
            "lead_score": lead_score,
            "next_follow_up": follow_up_task.due_date,
            "suggested_properties": suggested_properties,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _check_duplicate(
        self, phone: str, source_type: str, lead_repo: LeadRepository
    ) -> None:
        """Check for duplicate leads using Redis cache first, then DB.

        Duplicate detection is enforced at the APPLICATION level
        (24-hour window), not at the database constraint level.  The DB
        has no UNIQUE(phone, source_type) constraint — this is
        intentional.  The same lead may be re-submitted from the same
        source after 24 hours and should be treated as a new lead
        entry.

        Redis acts as a fast cache with a 24-hour TTL
        (``REDIS_DUPLICATE_CHECK_TTL = 86400``).  If Redis is
        unavailable the authoritative DB query still runs as a
        fallback — duplicate detection is never skipped.

        See ThinkRealty Backend Assessment: Error Handling, Duplicate
        Lead Detection.
        """
        cache_key = f"lead_duplicate:{phone}:{source_type}"

        # Try Redis first (fast path) via CacheService
        cached = await self._cache.get(cache_key)
        if cached is not None:
            from app.core.exceptions import DuplicateLeadError

            raise DuplicateLeadError()

        # Fallback: authoritative DB check via repository
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        existing = await lead_repo.find_duplicate(phone, source_type, since)
        if existing:
            from app.core.exceptions import DuplicateLeadError

            raise DuplicateLeadError()

    async def _cache_lead_duplicate_key(
        self, phone: str, source_type: str, lead_id: str
    ) -> None:
        """Store a duplicate-detection key in Redis with 24-hour TTL."""
        cache_key = f"lead_duplicate:{phone}:{source_type}"
        await self._cache.set(
            cache_key, lead_id, ttl=settings.REDIS_DUPLICATE_CHECK_TTL
        )

    async def _create_records(
        self,
        *,
        lead_id: UUID,
        source_type: SourceType,
        lead_data: LeadCreate,
        lead_score: int,
        source_details: Dict[str, Any],
        agent_id: UUID,
        lead_repo: LeadRepository,
        agent_repo: AgentRepository,
        assignment_repo: AssignmentRepository,
        source_repo: LeadSourceRepository,
        task_repo: TaskRepository,
    ) -> tuple:
        """Persist Lead, LeadSource, LeadAssignment, and FollowUpTask."""
        lead = await lead_repo.create(
            lead_id=lead_id,
            source_type=source_type,
            first_name=lead_data.first_name,
            last_name=lead_data.last_name,
            email=lead_data.email,
            phone=lead_data.phone,
            nationality=lead_data.nationality,
            language_preference=lead_data.language_preference,
            budget_min=lead_data.budget_min,
            budget_max=lead_data.budget_max,
            property_type=lead_data.property_type,
            preferred_areas=lead_data.preferred_areas,
            status="new",
            score=lead_score,
        )

        referrer_agent_id = await self._resolve_referrer(
            source_details.get("referrer_agent_id"), agent_repo
        )

        await source_repo.create(
            lead_id=lead_id,
            source_type=source_type,
            campaign_id=source_details.get("campaign_id"),
            referrer_agent_id=referrer_agent_id,
            property_id=source_details.get("property_id"),
            utm_source=source_details.get("utm_source"),
        )

        follow_up_task = await task_repo.create(
            lead_id=lead_id,
            agent_id=agent_id,
            type="call",
            due_date=datetime.now(timezone.utc) + timedelta(hours=24),
            priority="high",
            status="pending",
        )

        await assignment_repo.create(
            lead_id=lead_id,
            agent_id=agent_id,
            reason="Initial assignment",
        )

        return lead, follow_up_task

    async def _resolve_referrer(
        self, referrer_agent_id: Optional[UUID], agent_repo: AgentRepository
    ) -> Optional[UUID]:
        """Return the referrer agent ID only if the agent actually exists."""
        if referrer_agent_id is None:
            return None
        agent = await agent_repo.get_by_id(referrer_agent_id)
        return referrer_agent_id if agent else None

    async def _get_property_suggestions(
        self,
        lead_data: LeadCreate,
    ) -> List[str]:
        if self._property_service is None:
            return []

        return await self._property_service.get_suggestions(
            property_type=lead_data.property_type,
            preferred_areas=lead_data.preferred_areas,
            budget_min=lead_data.budget_min,
            budget_max=lead_data.budget_max,
        )
