from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, update

from app.models.lead import Lead
from app.repositories.base import BaseRepository


class LeadRepository(BaseRepository):
    """Encapsulates every SQL query that touches the ``leads`` table."""

    async def get_by_id(self, lead_id: UUID) -> Optional[Lead]:
        """Return a single lead by primary key, or ``None``."""
        result = await self._db.execute(select(Lead).where(Lead.lead_id == lead_id))
        return result.scalar_one_or_none()

    async def get_score(self, lead_id: UUID) -> int:
        """Return the current score for a lead."""
        result = await self._db.execute(
            select(Lead.score).where(Lead.lead_id == lead_id)
        )
        return result.scalar_one()

    async def find_duplicate(
        self, phone: str, source_type: str, since: datetime
    ) -> Optional[Lead]:
        """Find a lead with the same phone+source created after *since*.

        Duplicate detection is enforced at the APPLICATION level (24-hour
        window), not at the database constraint level.  The DB has no
        UNIQUE(phone, source_type) constraint — this is intentional.
        The same lead may be re-submitted from the same source after
        24 hours and should be treated as a new lead entry.

        See ThinkRealty Backend Assessment: Error Handling, Duplicate
        Lead Detection.
        """
        result = await self._db.execute(
            select(Lead).where(
                Lead.phone == phone,
                Lead.source_type == source_type,
                Lead.created_at >= since,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **kwargs: Any) -> Lead:
        """Insert a new lead and return the model instance."""
        lead = Lead(**kwargs)
        self._db.add(lead)
        return lead

    async def update_status(self, lead: Lead, new_status: str) -> None:
        """Update the status column on an existing lead instance."""
        lead.status = new_status

    async def update_score(self, lead_id: UUID, new_score: int) -> None:
        """Set the score for a lead by ID."""
        await self._db.execute(
            update(Lead).where(Lead.lead_id == lead_id).values(score=new_score)
        )
