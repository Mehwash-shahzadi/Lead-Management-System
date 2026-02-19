from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.follow_up import PendingTask


class AgentBasicOut(BaseModel):
    """Minimal agent info returned inside lead-capture responses."""

    agent_id: UUID
    name: str
    phone: str


class AgentSummary(BaseModel):
    total_active_leads: int
    overdue_follow_ups: int
    this_month_conversions: int
    average_response_time: str = Field(..., description="X.Y hours")
    lead_score_average: int


class RecentLead(BaseModel):
    lead_id: UUID
    name: str
    phone: str
    source: str
    status: str
    score: int
    last_activity: Optional[datetime] = None
    next_follow_up: Optional[datetime] = None


class PerformanceMetrics(BaseModel):
    conversion_rate: float
    average_deal_size: int
    response_time_rank: int


class AgentDashboardResponse(BaseModel):
    agent_summary: AgentSummary
    recent_leads: List[RecentLead]
    pending_tasks: List[PendingTask]
    performance_metrics: PerformanceMetrics
