from typing import Any

from app.models.lead_source import LeadSource
from app.repositories.base import BaseRepository


class LeadSourceRepository(BaseRepository):
    """Encapsulates queries against the ``lead_sources`` table."""

    async def create(self, **kwargs: Any) -> LeadSource:
        """Insert a new lead-source record."""
        source = LeadSource(**kwargs)
        self._db.add(source)
        return source
