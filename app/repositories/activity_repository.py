from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, func

from app.models.activity import LeadActivity
from app.repositories.base import BaseRepository


class ActivityRepository(BaseRepository):
    """Encapsulates queries against the ``lead_activities`` table."""

    async def create(self, **kwargs: Any) -> LeadActivity:
        """Insert a new lead activity record."""
        activity = LeadActivity(**kwargs)
        self._db.add(activity)
        return activity

    async def get_last_activity_at(self, lead_id: UUID) -> Optional[datetime]:
        """Return the timestamp of the most recent activity for a lead."""
        result = await self._db.execute(
            select(func.max(LeadActivity.activity_at)).where(
                LeadActivity.lead_id == lead_id
            )
        )
        return result.scalar_one_or_none()

    async def find_first_contact_activity(
        self, lead_id: UUID
    ) -> Optional[LeadActivity]:
        """Return the earliest outbound contact activity for a lead.

        Only considers activity types that represent an agent reaching
        out to the lead (call, email, whatsapp, meeting).  This is used
        by the scoring engine to measure *response time to initial
        contact* per ThinkRealty Backend Assessment Task 3.1.
        """
        result = await self._db.execute(
            select(LeadActivity)
            .where(
                LeadActivity.lead_id == lead_id,
                LeadActivity.type.in_(["call", "email", "whatsapp", "meeting"]),
            )
            .order_by(LeadActivity.activity_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_activity_count(self, lead_id: UUID) -> int:
        """Return the total number of activities for a lead."""
        result = await self._db.execute(
            select(func.count())
            .select_from(LeadActivity)
            .where(LeadActivity.lead_id == lead_id)
        )
        return result.scalar() or 0

    async def get_first_activity_at(self, lead_id: UUID) -> Optional[datetime]:
        """Return the timestamp of the earliest activity for a lead."""
        result = await self._db.execute(
            select(LeadActivity.activity_at)
            .where(LeadActivity.lead_id == lead_id)
            .order_by(LeadActivity.activity_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()
