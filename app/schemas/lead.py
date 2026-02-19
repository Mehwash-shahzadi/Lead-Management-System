"""Lead-specific Pydantic schemas (capture, update, response)."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, model_validator
from typing_extensions import Self

from app.schemas.common import (
    SourceType,
    LanguagePreference,
    PropertyType,
    LeadStatus,
    SuccessResponse,
)
from app.schemas.lead_activity import ActivityUpdate, PropertyInterestUpdate
from app.schemas.agent import AgentBasicOut


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


# Maximum budget ceiling for UAE real estate (500 million AED)
_MAX_BUDGET_AED = 500_000_000


class LeadCreate(BaseModel):
    """Core lead data submitted during capture."""

    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: str = Field(..., pattern=r"^\+971\d{9}$")
    nationality: str = Field(..., min_length=1)
    language_preference: LanguagePreference
    budget_min: float = Field(..., gt=0)
    budget_max: float = Field(..., gt=0)
    property_type: PropertyType
    preferred_areas: List[str] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_budget_range(self) -> Self:
        """Enforce budget_min < budget_max at schema validation time.

        Per ThinkRealty Backend Assessment input validation requirements.
        Raises ``ValueError`` (HTTP 422) during request parsing, before
        the request reaches the service layer.
        """
        if self.budget_min is not None and self.budget_max is not None:
            if self.budget_min >= self.budget_max:
                raise ValueError(
                    f"budget_min ({self.budget_min} AED) must be strictly less "
                    f"than budget_max ({self.budget_max} AED)"
                )
            if self.budget_max > _MAX_BUDGET_AED:
                raise ValueError(
                    f"budget_max exceeds maximum allowed value of "
                    f"{_MAX_BUDGET_AED:,} AED"
                )
        return self


class SourceDetailsCreate(BaseModel):
    """Optional source metadata attached to a captured lead."""

    campaign_id: Optional[str] = None
    referrer_agent_id: Optional[UUID] = None
    property_id: Optional[UUID] = None
    utm_source: Optional[str] = None


class LeadCaptureRequest(BaseModel):
    """Top-level request body for POST /api/v1/leads/capture."""

    source_type: SourceType
    lead_data: LeadCreate
    source_details: SourceDetailsCreate


class LeadUpdate(BaseModel):
    """Request body for PUT /api/v1/leads/{lead_id}/update."""

    status: Optional[LeadStatus] = None
    activity: Optional[ActivityUpdate] = None
    property_interests: Optional[List[PropertyInterestUpdate]] = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class LeadCaptureResponse(BaseModel):
    """Response body returned after a successful lead capture."""

    success: bool = True
    lead_id: UUID
    assigned_agent: AgentBasicOut
    lead_score: int = Field(..., ge=0, le=100)
    next_follow_up: datetime
    suggested_properties: List[str] = Field(default_factory=list)


class LeadUpdateResponse(SuccessResponse):
    """Response body returned after a successful lead update."""

    lead_id: UUID
    status: str
    score: int = Field(..., ge=0, le=100)
