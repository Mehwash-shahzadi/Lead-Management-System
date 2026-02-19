from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, and_

from app.models.conversion_history import LeadConversionHistory
from app.repositories.base import BaseRepository


class ConversionHistoryRepository(BaseRepository):
    """Encapsulates queries against ``lead_conversion_history``."""

    async def create(self, **kwargs: Any) -> LeadConversionHistory:
        """Insert a new conversion-history record."""
        record = LeadConversionHistory(**kwargs)
        self._db.add(record)
        return record

    async def count_conversions_since(self, agent_id: UUID, since: datetime) -> int:
        """Count conversion records for an agent since a given date."""
        query = select(func.count(LeadConversionHistory.history_id)).where(
            and_(
                LeadConversionHistory.agent_id == agent_id,
                LeadConversionHistory.changed_at >= since,
            )
        )
        return (await self._db.execute(query)).scalar()
