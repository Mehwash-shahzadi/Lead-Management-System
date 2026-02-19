from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from uuid import UUID

from app.schemas.common import ActivityType, ActivityOutcome, InterestLevel


class ActivityUpdate(BaseModel):
    """Payload for logging a new lead activity."""

    type: ActivityType
    notes: str
    outcome: ActivityOutcome
    next_follow_up: Optional[datetime] = None


class PropertyInterestUpdate(BaseModel):
    """Payload for recording a property interest on a lead."""

    property_id: UUID
    interest_level: InterestLevel
