"""Pydantic schemas package – re-exports for convenience."""

# Common enums
from app.schemas.common import (
    SourceType as SourceType,
    LanguagePreference as LanguagePreference,
    PropertyType as PropertyType,
    LeadStatus as LeadStatus,
    ActivityType as ActivityType,
    ActivityOutcome as ActivityOutcome,
    InterestLevel as InterestLevel,
    SuccessResponse as SuccessResponse,
)

# Lead schemas
from app.schemas.lead import (
    LeadCreate as LeadCreate,
    SourceDetailsCreate as SourceDetailsCreate,
    LeadCaptureRequest as LeadCaptureRequest,
    LeadCaptureResponse as LeadCaptureResponse,
    LeadUpdate as LeadUpdate,
    LeadUpdateResponse as LeadUpdateResponse,
)

# Agent schemas
from app.schemas.agent import (
    AgentBasicOut as AgentBasicOut,
    AgentSummary as AgentSummary,
    RecentLead as RecentLead,
    PerformanceMetrics as PerformanceMetrics,
    AgentDashboardResponse as AgentDashboardResponse,
)

# Activity schemas
from app.schemas.lead_activity import (
    ActivityUpdate as ActivityUpdate,
    PropertyInterestUpdate as PropertyInterestUpdate,
)

# Follow-up schemas
from app.schemas.follow_up import PendingTask as PendingTask

# Analytics schemas
from app.schemas.analytics import (
    DateRange as DateRange,
    StatusFilter as StatusFilter,
    SourceFilter as SourceFilter,
)
