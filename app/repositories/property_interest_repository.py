from typing import Any, List, Optional
from sqlalchemy import select, func, case, and_

from app.models.lead import Lead
from app.models.property_interest import LeadPropertyInterest
from app.repositories.base import BaseRepository


class PropertyInterestRepository(BaseRepository):
    """Encapsulates queries against the ``lead_property_interests`` table."""

    async def create(self, **kwargs: Any) -> LeadPropertyInterest:
        """Insert a new property-interest record."""
        interest = LeadPropertyInterest(**kwargs)
        self._db.add(interest)
        return interest

    async def find_suggestions(
        self,
        property_type: Optional[str] = None,
        preferred_areas: Optional[List[str]] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        limit: int = 5,
    ) -> List[str]:
        """Suggest properties via collaborative filtering.

        Since no ``properties`` table exists in the schema, this method
        implements a collaborative filtering stub: it looks at property
        interest records from *other* leads whose profile overlaps the
        incoming lead's preferences (property type, budget range, areas)
        and whose status indicates proven demand (converted, qualified,
        or in negotiation).

        Properties are ranked by a relevance score that combines:
        - Interest level weight (high=3, medium=2, low=1)
        - Number of distinct leads who showed interest (popularity)

        Returns a list of property UUID strings, capped at *limit*.
        """
        filters = []

        if property_type:
            filters.append(Lead.property_type == property_type)

        if preferred_areas:
            filters.append(Lead.preferred_areas.overlap(preferred_areas))

        if budget_min is not None and budget_max is not None:
            # Budget overlap: the lead's range intersects the matching
            # lead's range (i.e. not mutually exclusive).
            filters.append(Lead.budget_max >= budget_min)
            filters.append(Lead.budget_min <= budget_max)

        # Only consider leads with proven demand — their property
        # interests carry more signal.
        filters.append(Lead.status.in_(["converted", "qualified", "negotiation"]))

        # Relevance score: sum of interest-level weights across all
        # matching leads that expressed interest in each property.
        interest_weight = case(
            (LeadPropertyInterest.interest_level == "high", 3),
            (LeadPropertyInterest.interest_level == "medium", 2),
            else_=1,
        )

        relevance = func.sum(interest_weight).label("relevance")

        query = (
            select(
                LeadPropertyInterest.property_id,
                relevance,
            )
            .join(Lead, Lead.lead_id == LeadPropertyInterest.lead_id)
            .where(and_(*filters) if filters else True)
            .group_by(LeadPropertyInterest.property_id)
            .order_by(relevance.desc())
            .limit(limit)
        )

        result = await self._db.execute(query)
        rows = result.all()
        return [str(row.property_id) for row in rows]
