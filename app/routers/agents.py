from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, text
from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional

from app.database import get_db
from app.schemas.agent_dashboard import (
    AgentDashboardResponse,
    DateRange,
    StatusFilter,
    SourceFilter
)
from app.models.agent import Agent
from app.models.lead import Lead
from app.models.assignment import LeadAssignment
from app.models.task import FollowUpTask
from app.models.activity import LeadActivity
from app.models.conversion_history import LeadConversionHistory

router = APIRouter(prefix="/api/v1/agents")


@router.get("/{agent_id}/dashboard", response_model=AgentDashboardResponse)
async def get_agent_dashboard(
    agent_id: UUID,
    date_range: Optional[DateRange] = Query(None),
    status_filter: Optional[StatusFilter] = Query(None),
    source_filter: Optional[SourceFilter] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> AgentDashboardResponse:
    # Check if agent exists
    agent_query = select(Agent).where(Agent.agent_id == agent_id)
    agent_result = await db.execute(agent_query)
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Calculate date filter
    now = datetime.utcnow()
    date_filter = None
    if date_range:
        if date_range == DateRange.seven_days:
            date_filter = now - timedelta(days=7)
        elif date_range == DateRange.thirty_days:
            date_filter = now - timedelta(days=30)
        elif date_range == DateRange.ninety_days:
            date_filter = now - timedelta(days=90)
        # custom is handled by default (no filter)

    # Build base filters
    filters = [LeadAssignment.agent_id == agent_id]
    if date_filter:
        filters.append(Lead.created_at >= date_filter)
    if status_filter and status_filter != StatusFilter.all:
        if status_filter == StatusFilter.active:
            filters.append(Lead.status.notin_(["converted", "lost"]))
        elif status_filter == StatusFilter.converted:
            filters.append(Lead.status == "converted")
        elif status_filter == StatusFilter.lost:
            filters.append(Lead.status == "lost")
    if source_filter and source_filter != SourceFilter.all:
        filters.append(Lead.source_type == source_filter.value)

    # Agent Summary
    # Total active leads
    active_leads_query = select(func.count(Lead.lead_id)).select_from(
        Lead
    ).join(LeadAssignment, Lead.lead_id == LeadAssignment.lead_id).where(and_(*filters, Lead.status.notin_(["converted", "lost"])))
    active_leads_result = await db.execute(active_leads_query)
    total_active_leads = active_leads_result.scalar()

    # Overdue follow-ups
    overdue_query = select(func.count(FollowUpTask.task_id)).where(
        and_(FollowUpTask.agent_id == agent_id, FollowUpTask.due_date < now, FollowUpTask.status == "pending")
    )
    overdue_result = await db.execute(overdue_query)
    overdue_follow_ups = overdue_result.scalar()

    # This month conversions
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    conversions_query = select(func.count(LeadConversionHistory.history_id)).where(
        and_(LeadConversionHistory.agent_id == agent_id, LeadConversionHistory.changed_at >= month_start)
    )
    conversions_result = await db.execute(conversions_query)
    this_month_conversions = conversions_result.scalar()

    # Average response time (simplified - time from assignment to first activity)
    response_time_query = select(
        func.avg(
            func.extract('epoch', LeadActivity.activity_at - LeadAssignment.assigned_at) / 3600
        )
    ).select_from(
        LeadActivity
    ).join(LeadAssignment, LeadActivity.lead_id == LeadAssignment.lead_id).where(LeadAssignment.agent_id == agent_id)
    response_time_result = await db.execute(response_time_query)
    avg_response_time = response_time_result.scalar() or 0
    average_response_time = f"{avg_response_time:.1f} hours"

    # Lead score average
    score_query = select(func.avg(Lead.score)).select_from(
        Lead
    ).join(LeadAssignment, Lead.lead_id == LeadAssignment.lead_id).where(and_(*filters))
    score_result = await db.execute(score_query)
    lead_score_average = int(score_result.scalar() or 0)

    agent_summary = {
        "total_active_leads": total_active_leads,
        "overdue_follow_ups": overdue_follow_ups,
        "this_month_conversions": this_month_conversions,
        "average_response_time": average_response_time,
        "lead_score_average": lead_score_average
    }

    # Recent Leads (latest 10)
    recent_leads_query = select(
        Lead.lead_id,
        func.concat(Lead.first_name, ' ', Lead.last_name).label('name'),
        Lead.phone,
        Lead.source_type.label('source'),
        Lead.status,
        Lead.score,
        func.max(LeadActivity.activity_at).label('last_activity'),
        func.min(case((FollowUpTask.status == "pending", FollowUpTask.due_date), else_=None)).label('next_follow_up')
    ).select_from(
        Lead
    ).join(LeadAssignment, Lead.lead_id == LeadAssignment.lead_id).outerjoin(LeadActivity, Lead.lead_id == LeadActivity.lead_id).outerjoin(FollowUpTask, and_(Lead.lead_id == FollowUpTask.lead_id, FollowUpTask.agent_id == agent_id)).where(and_(*filters)).group_by(Lead.lead_id).order_by(func.max(LeadActivity.activity_at).desc()).limit(10)

    recent_leads_result = await db.execute(recent_leads_query)
    recent_leads = [
        {
            "lead_id": row.lead_id,
            "name": row.name,
            "phone": row.phone,
            "source": row.source,
            "status": row.status,
            "score": row.score,
            "last_activity": row.last_activity.isoformat() if row.last_activity else None,
            "next_follow_up": row.next_follow_up.isoformat() if row.next_follow_up else None
        }
        for row in recent_leads_result
    ]

    # Pending Tasks
    pending_tasks_query = select(
        FollowUpTask.task_id,
        func.concat(Lead.first_name, ' ', Lead.last_name).label('lead_name'),
        FollowUpTask.type.label('task_type'),
        FollowUpTask.due_date,
        FollowUpTask.priority
    ).select_from(
        FollowUpTask
    ).join(Lead, FollowUpTask.lead_id == Lead.lead_id).where(
        and_(FollowUpTask.agent_id == agent_id, FollowUpTask.status == "pending")
    ).order_by(FollowUpTask.due_date.asc())

    pending_tasks_result = await db.execute(pending_tasks_query)
    pending_tasks = [
        {
            "task_id": row.task_id,
            "lead_name": row.lead_name,
            "task_type": row.task_type,
            "due_date": row.due_date.isoformat(),
            "priority": row.priority
        }
        for row in pending_tasks_result
    ]

    # Performance Metrics
    # Conversion rate
    total_leads_query = select(func.count(Lead.lead_id)).select_from(
        Lead
    ).join(LeadAssignment, Lead.lead_id == LeadAssignment.lead_id).where(LeadAssignment.agent_id == agent_id)
    total_leads_result = await db.execute(total_leads_query)
    total_leads = total_leads_result.scalar()

    converted_leads_query = select(func.count(Lead.lead_id)).select_from(
        Lead
    ).join(LeadAssignment, Lead.lead_id == LeadAssignment.lead_id).where(and_(LeadAssignment.agent_id == agent_id, Lead.status == "converted"))
    converted_result = await db.execute(converted_leads_query)
    converted_leads = converted_result.scalar()

    conversion_rate = (converted_leads / total_leads) * 100 if total_leads > 0 else 0

    # Average deal size (simplified - using budget_max as deal size for converted leads)
    deal_size_query = select(func.avg(Lead.budget_max)).select_from(
        Lead
    ).join(LeadAssignment, Lead.lead_id == LeadAssignment.lead_id).where(and_(LeadAssignment.agent_id == agent_id, Lead.status == "converted"))
    deal_size_result = await db.execute(deal_size_query)
    average_deal_size = int(deal_size_result.scalar() or 0)

    # Response time rank (among all agents)
    rank_query = text("""
        SELECT rank FROM (
            SELECT la2.agent_id,
                   AVG(EXTRACT(EPOCH FROM (la.activity_at - la2.assigned_at)) / 3600) as avg_response,
                   RANK() OVER (ORDER BY AVG(EXTRACT(EPOCH FROM (la.activity_at - la2.assigned_at)) / 3600) ASC) as rank
            FROM lead_activities la
            JOIN lead_assignments la2 ON la.lead_id = la2.lead_id
            GROUP BY la2.agent_id
        ) ranks WHERE agent_id = :agent_id
    """)
    rank_result = await db.execute(rank_query, {"agent_id": agent_id})
    response_time_rank = rank_result.scalar() or 0

    performance_metrics = {
        "conversion_rate": conversion_rate,
        "average_deal_size": average_deal_size,
        "response_time_rank": response_time_rank
    }

    return AgentDashboardResponse(
        agent_summary=agent_summary,
        recent_leads=recent_leads,
        pending_tasks=pending_tasks,
        performance_metrics=performance_metrics
    )