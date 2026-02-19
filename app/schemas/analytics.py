from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class DateRange(str, Enum):
    seven_days = "7d"
    thirty_days = "30d"
    ninety_days = "90d"
    custom = "custom"


class StatusFilter(str, Enum):
    all = "all"
    active = "active"
    converted = "converted"
    lost = "lost"


class SourceFilter(str, Enum):
    all = "all"
    bayut = "bayut"
    propertyFinder = "propertyFinder"
    dubizzle = "dubizzle"
    website = "website"
    walk_in = "walk_in"
    referral = "referral"


class PaginatedResponse(BaseModel):
    data: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = Field(0, description="Total number of matching rows")
    skip: int = Field(0, ge=0, description="Number of rows skipped")
    limit: int = Field(50, ge=1, description="Maximum rows returned")
    next_cursor: Optional[str] = Field(
        None,
        description=(
            "Opaque cursor pointing to the start of the next page. "
            "Pass as ?cursor= to use keyset pagination."
        ),
    )
