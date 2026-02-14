from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from enum import Enum
from uuid import UUID
from datetime import datetime


class SourceType(str, Enum):
    bayut = "bayut"
    propertyFinder = "propertyFinder"
    dubizzle = "dubizzle"
    website = "website"
    walk_in = "walk_in"
    referral = "referral"


class LanguagePreference(str, Enum):
    arabic = "arabic"
    english = "english"


class PropertyType(str, Enum):
    apartment = "apartment"
    villa = "villa"
    townhouse = "townhouse"
    commercial = "commercial"


class LeadStatus(str, Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    viewing_scheduled = "viewing_scheduled"
    negotiation = "negotiation"
    converted = "converted"
    lost = "lost"


class ActivityType(str, Enum):
    call = "call"
    email = "email"
    whatsapp = "whatsapp"
    viewing = "viewing"
    meeting = "meeting"
    offer_made = "offer_made"


class ActivityOutcome(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class InterestLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class LeadCreate(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    phone: str = Field(..., pattern=r"^\+971\d{9}$")
    nationality: str = Field(..., min_length=1)
    language_preference: LanguagePreference
    budget_min: float = Field(..., gt=0)
    budget_max: float = Field(..., gt=0)
    property_type: PropertyType
    preferred_areas: List[str] = Field(..., min_items=1)


class SourceDetailsCreate(BaseModel):
    campaign_id: Optional[str] = None
    referrer_agent_id: Optional[UUID] = None
    property_id: Optional[UUID] = None
    utm_source: Optional[str] = None


class LeadCaptureRequest(BaseModel):
    source_type: SourceType
    lead_data: LeadCreate
    source_details: SourceDetailsCreate


class AgentBasicOut(BaseModel):
    agent_id: UUID
    name: str
    phone: str


class LeadCaptureResponse(BaseModel):
    success: bool = True
    lead_id: UUID
    assigned_agent: AgentBasicOut
    lead_score: int = Field(..., ge=0, le=100)
    next_follow_up: datetime
    suggested_properties: List = Field(default_factory=list)


class ActivityUpdate(BaseModel):
    type: ActivityType
    notes: str
    outcome: ActivityOutcome
    next_follow_up: Optional[str] = None


class PropertyInterestUpdate(BaseModel):
    property_id: UUID
    interest_level: InterestLevel


class LeadUpdate(BaseModel):
    status: Optional[LeadStatus] = None
    activity: Optional[ActivityUpdate] = None
    property_interests: Optional[List[PropertyInterestUpdate]] = None


class LeadUpdateResponse(BaseModel):
    success: bool = True
