import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import LeadActivity
from app.models.assignment import LeadAssignment
from app.models.lead import Lead
from app.repositories.agent_repository import AgentRepository
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.lead_repository import LeadRepository
from app.services.lead_assignment import LeadAssignmentManager

logger = logging.getLogger(__name__)

# How often the background loop runs (in seconds)
_CHECK_INTERVAL_SECONDS: int = 3600
# Stale threshold — leads assigned for longer than this with no activity
_STALE_HOURS: int = 24


async def _find_stale_assignments(session: AsyncSession):
    """Return assignments older than 24 h with zero agent activity."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_STALE_HOURS)

    # Sub-query: leads that DO have at least one activity after assignment
    has_activity = (
        select(LeadActivity.lead_id)
        .where(
            and_(
                LeadActivity.lead_id == LeadAssignment.lead_id,
                LeadActivity.activity_at >= LeadAssignment.assigned_at,
            )
        )
        .correlate(LeadAssignment)
        .exists()
    )

    query = (
        select(LeadAssignment)
        .join(Lead, Lead.lead_id == LeadAssignment.lead_id)
        .where(
            and_(
                LeadAssignment.assigned_at <= cutoff,
                Lead.status.notin_(["converted", "lost"]),
                ~has_activity,
            )
        )
    )

    result = await session.execute(query)
    return result.scalars().all()


async def auto_reassign_stale_leads(
    session_factory: Callable[..., AsyncSession],
) -> int:
    """One-shot: find and reassign all stale leads.

    Parameters:
        session_factory: An async context-manager callable that yields
            an ``AsyncSession`` (e.g. ``AsyncSessionLocal``).

    Returns the number of reassigned leads.
    """
    reassigned = 0

    async with session_factory() as session:
        stale = await _find_stale_assignments(session)
        if not stale:
            return 0

        logger.info("Found %d stale assignment(s) for auto-reassignment", len(stale))

        agent_repo = AgentRepository(session)
        assignment_repo = AssignmentRepository(session)
        lead_repo = LeadRepository(session)
        manager = LeadAssignmentManager()  # no Redis needed for reassignment

        for assignment in stale:
            try:
                new_agent_id = await manager.reassign_lead(
                    lead_id=assignment.lead_id,
                    reason="Auto-reassigned: no response within 24 hours",
                    agent_repo=agent_repo,
                    assignment_repo=assignment_repo,
                    lead_repo=lead_repo,
                )
                reassigned += 1
                logger.info(
                    "Auto-reassigned lead %s → agent %s",
                    assignment.lead_id,
                    new_agent_id,
                )
            except Exception:
                logger.warning(
                    "Failed to auto-reassign lead %s",
                    assignment.lead_id,
                    exc_info=True,
                )

        await session.commit()

    return reassigned


async def start_auto_reassign_loop(
    session_factory: Callable[..., AsyncSession],
) -> None:
    """Infinite loop that runs auto-reassignment on a fixed interval.

    Parameters:
        session_factory: An async context-manager callable that yields
            an ``AsyncSession``.
    """
    logger.info(
        "Auto-reassignment background task started (interval=%ds, stale=%dh)",
        _CHECK_INTERVAL_SECONDS,
        _STALE_HOURS,
    )
    while True:
        try:
            count = await auto_reassign_stale_leads(session_factory)
            if count:
                logger.info("Auto-reassignment cycle complete: %d lead(s)", count)
        except Exception:
            logger.error("Auto-reassignment cycle failed", exc_info=True)
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
