import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.core.cache import CacheService
from app.core.constants import MAX_AGENT_ACTIVE_LEADS
from app.core.exceptions import (
    AgentOverloadError,
    AssignmentNotFoundError,
    InvalidLeadDataError,
)
from app.repositories.agent_repository import AgentRepository
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.lead_repository import LeadRepository

logger = logging.getLogger(__name__)

# Redis key prefix for per-score-group round-robin counters
_ROUND_ROBIN_KEY_PREFIX = "round_robin:assignment"
# TTL for round-robin keys (24 hours) — daily counter reset
_ROUND_ROBIN_TTL = 86400


class LeadAssignmentManager:
    """Smart lead assignment based on specialisation, workload, language, and performance.

    Uses a weighted scoring algorithm that considers agent specialization,
    area match, language preference, performance metrics (conversion rate),
    and round-robin workload balancing.

    The round-robin counter is persisted in Redis so it survives app
    restarts and is shared across worker processes.  If Redis is
    unavailable, an in-process fallback counter is used.
    """

    # In-process fallback when Redis is unavailable
    _fallback_counter: int = 0

    def __init__(self, cache: Optional[CacheService] = None) -> None:
        self._cache: CacheService = cache or CacheService()

    async def _find_best_agent_id(
        self, lead_data: Dict[str, Any], agent_repo: AgentRepository
    ) -> UUID:
        """Score every available agent and return the best match's ID.

        Scoring factors (weighted):
        - Property type specialization match  (+3)
        - Area specialization match           (+2)
        - Language preference match            (+2)
        - Performance metrics (conversion rate) (+0 to +3)
        - Round-robin with workload balancing   (tiebreaker)

        Pre-filtering:
        Agents at or above ``MAX_AGENT_ACTIVE_LEADS`` (50) are excluded
        **before** scoring.  This ensures the business rule is enforced
        at the application level and the system never selects an agent
        who would be rejected by the DB trigger or CHECK constraint.

        Raises ``AgentOverloadError`` if no agents have capacity.
        """

        agents = await agent_repo.get_available_agents(max_leads=MAX_AGENT_ACTIVE_LEADS)
        agents = [a for a in agents if a.active_leads_count < MAX_AGENT_ACTIVE_LEADS]

        if not agents:
            raise AgentOverloadError(
                "All agents are at maximum capacity "
                f"({MAX_AGENT_ACTIVE_LEADS} active leads)"
            )

        # Normalise input
        if hasattr(lead_data, "model_dump"):
            lead_dict = lead_data.model_dump()
        elif hasattr(lead_data, "dict"):
            lead_dict = lead_data.dict()
        else:
            lead_dict = lead_data

        lead_property_type = lead_dict.get("property_type")
        lead_areas = lead_dict.get("preferred_areas", [])
        lead_language = lead_dict.get("language_preference")

        scored_agents: List[tuple] = []

        for agent in agents:
            score = 0

            # Specialization matching
            if lead_property_type and lead_property_type in (
                agent.specialization_property_type or []
            ):
                score += 3
            if any(area in (agent.specialization_areas or []) for area in lead_areas):
                score += 2

            # Language preference
            if lead_language and lead_language in (agent.language_skills or []):
                score += 2

            # Performance metrics – boost agents with higher conversion rate
            perf_bonus = 0
            if agent.performance_metrics:
                # Use the most recent metric record
                latest_metric = max(
                    agent.performance_metrics,
                    key=lambda m: m.updated_at or datetime.min,
                )
                rate = latest_metric.conversion_rate
                if rate is not None:
                    rate_float = float(rate) if isinstance(rate, Decimal) else rate
                    if rate_float >= 30:
                        perf_bonus = 3
                    elif rate_float >= 20:
                        perf_bonus = 2
                    elif rate_float > 0:
                        perf_bonus = 1
            score += perf_bonus

            scored_agents.append((score, agent))

        selected = await self._select_agent_with_roundrobin(scored_agents)
        return selected.agent_id

    async def _select_agent_with_roundrobin(
        self,
        scored_agents: List[tuple],
    ):
        """Pick the best agent using score-group-aware round-robin.

        Selection strategy per ThinkRealty Assessment Task 3.2:

        1. Find the maximum score among all agents.
        2. Collect **all** agents sharing that top score — regardless
           of their current workload.
        3. Sort the top-score group by ``active_leads_count`` ASC so
           that workload acts as a stable secondary ordering.
        4. Rotate through the sorted list using a Redis counter that
           is scoped to the score value (``round_robin:assignment:{score}``).

        Workload is **not** a filter — it only determines the order
        in which equally-scored agents are visited by the round-robin
        pointer.  This ensures every agent at the top score eventually
        receives leads even if their workload is temporarily higher.
        """
        max_score = max(s for s, _ in scored_agents)

        top_agents = [agent for s, agent in scored_agents if s == max_score]

        # Stable ordering: lowest workload first
        top_agents.sort(key=lambda a: a.active_leads_count)

        if len(top_agents) == 1:
            return top_agents[0]

        # Per-score-group Redis key
        rr_key = f"{_ROUND_ROBIN_KEY_PREFIX}:{max_score}"

        counter = await self._cache.incr(rr_key, ttl=_ROUND_ROBIN_TTL)
        if counter is not None:
            return top_agents[(counter - 1) % len(top_agents)]

        # In-process fallback when Redis is unavailable
        counter = LeadAssignmentManager._fallback_counter
        LeadAssignmentManager._fallback_counter += 1
        return top_agents[counter % len(top_agents)]

    async def assign_lead(
        self, lead_data: Dict[str, Any], agent_repo: AgentRepository
    ) -> UUID:
        """Determine and return the best agent ID for a new lead."""
        return await self._find_best_agent_id(lead_data, agent_repo)

    async def reassign_lead(
        self,
        lead_id: UUID,
        reason: str,
        agent_repo: AgentRepository,
        assignment_repo: AssignmentRepository,
        lead_repo: LeadRepository,
        new_agent_id: Optional[UUID] = None,
    ) -> UUID:
        """Re-assign a lead to a different agent.

        If *new_agent_id* is ``None``, the best available agent is
        chosen automatically.
        """
        assignment = await assignment_repo.get_by_lead_id(lead_id)
        if not assignment:
            raise AssignmentNotFoundError("Assignment not found")

        old_agent_id = assignment.agent_id

        # Guard: prevent no-op reassignment to the same agent
        if new_agent_id is not None and new_agent_id == old_agent_id:
            raise InvalidLeadDataError("Cannot reassign lead to the same agent")

        if new_agent_id is None:
            lead = await lead_repo.get_by_id(lead_id)
            lead_data = {
                "lead_id": lead.lead_id,
                "property_type": lead.property_type,
                "preferred_areas": lead.preferred_areas,
                "language_preference": lead.language_preference,
            }
            new_agent_id = await self._find_best_agent_id(lead_data, agent_repo)

            # Guard: auto-selected agent must differ from current
            if new_agent_id == old_agent_id:
                raise InvalidLeadDataError(
                    "No alternative agent available; lead is already assigned "
                    "to the best-matching agent"
                )
        else:
            agent = await agent_repo.get_by_id(new_agent_id)
            if not agent or agent.active_leads_count >= MAX_AGENT_ACTIVE_LEADS:
                raise AgentOverloadError(
                    f"Agent {new_agent_id} has reached maximum capacity "
                    f"of {MAX_AGENT_ACTIVE_LEADS} active leads"
                )

        # Update via repositories
        await assignment_repo.reassign(assignment, new_agent_id, reason)
        await agent_repo.decrement_active_leads(old_agent_id)
        await agent_repo.increment_active_leads(new_agent_id)

        return new_agent_id
