from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


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


class PendingTask(BaseModel):
    task_id: UUID
    lead_name: str
    task_type: str  # "call|email|whatsapp|viewing"
    due_date: datetime
    priority: str  # "high|medium|low"


class PerformanceMetrics(BaseModel):
    conversion_rate: float
    average_deal_size: int
    response_time_rank: int


class AgentDashboardResponse(BaseModel):
    agent_summary: AgentSummary
    recent_leads: List[RecentLead]
    pending_tasks: List[PendingTask]
    performance_metrics: PerformanceMetrics