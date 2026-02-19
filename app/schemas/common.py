from enum import Enum
from pydantic import BaseModel


class SourceType(str, Enum):
    BAYUT = "bayut"
    PROPERTY_FINDER = "propertyFinder"
    DUBIZZLE = "dubizzle"
    WEBSITE = "website"
    WALK_IN = "walk_in"
    REFERRAL = "referral"


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


class SuccessResponse(BaseModel):
    """Generic success response base."""

    success: bool = True
