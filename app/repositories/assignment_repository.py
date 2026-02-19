"""Assignment repository – lead-assignment database operations."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func

from app.models.assignment import LeadAssignment
from app.repositories.base import BaseRepository


class AssignmentRepository(BaseRepository):
    """Encapsulates queries against the ``lead_assignments`` table."""

    async def get_by_lead_id(self, lead_id: UUID) -> Optional[LeadAssignment]:
        """Return the assignment for a given lead, or ``None``."""
        result = await self._db.execute(
            select(LeadAssignment).where(LeadAssignment.lead_id == lead_id)
        )
        return result.scalar_one_or_none()

    async def get_agent_id_for_lead(self, lead_id: UUID) -> Optional[UUID]:
        """Return the ``agent_id`` assigned to a lead, or ``None``."""
        result = await self._db.execute(
            select(LeadAssignment.agent_id).where(LeadAssignment.lead_id == lead_id)
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> LeadAssignment:
        """Insert a new assignment record."""
        assignment = LeadAssignment(**kwargs)
        self._db.add(assignment)
        return assignment

    async def reassign(
        self, assignment: LeadAssignment, new_agent_id: UUID, reason: str
    ) -> None:
        """Update an existing assignment to a new agent."""
        assignment.agent_id = new_agent_id
        assignment.reassigned_at = func.now()
        assignment.reason = reason
