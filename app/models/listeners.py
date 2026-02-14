from datetime import datetime, timedelta, timezone
from sqlalchemy import event, text, inspect
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.agent import Agent
from app.models.assignment import LeadAssignment
from app.models.task import FollowUpTask
from app.models.conversion_history import LeadConversionHistory


# Auto updated_at
@event.listens_for(Lead, "before_update")
@event.listens_for(Agent, "before_update")
@event.listens_for(FollowUpTask, "before_update")
def update_timestamp(mapper, connection, target):
    target.updated_at = datetime.now(timezone.utc)


# Active leads count refresh
@event.listens_for(LeadAssignment, "after_insert")
@event.listens_for(LeadAssignment, "after_delete")
@event.listens_for(Lead, "after_update")
def refresh_active_leads_count(mapper, connection, target):
    agent_id = getattr(target, "agent_id", None)
    if not agent_id and hasattr(target, "lead_id"):
        agent_id = connection.scalar(
            text("SELECT agent_id FROM lead_assignments WHERE lead_id = :lid"),
            {"lid": target.lead_id}
        )
    if agent_id:
        connection.execute(text("""
            UPDATE agents
            SET active_leads_count = (
                SELECT COUNT(*)
                FROM lead_assignments la
                JOIN leads l ON la.lead_id = l.lead_id
                WHERE la.agent_id = :aid
                AND l.status NOT IN ('converted', 'lost')
            )
            WHERE agent_id = :aid
        """), {"aid": agent_id})


# Status transition validation + history log
ALLOWED_TRANSITIONS = {
    "new": {"contacted"},
    "contacted": {"qualified"},
    "qualified": {"viewing_scheduled"},
    "viewing_scheduled": {"negotiation"},
    "negotiation": {"converted", "lost"},
    "converted": set(),
    "lost": set(),
}

@event.listens_for(Session, "before_flush")
def validate_status_and_log(session: Session, flush_context, instances):
    for obj in session.dirty:
        if isinstance(obj, Lead):
            state = inspect(obj)
            if state.attrs.status.history.has_changes():
                old = state.attrs.status.history.deleted[0] if state.attrs.status.history.deleted else None
                new = state.attrs.status.history.added[0]
                if old and new and new not in ALLOWED_TRANSITIONS.get(old, set()):
                    raise ValueError(f"Invalid transition: {old} → {new}")

                agent_id = session.execute(
                    text("SELECT agent_id FROM lead_assignments WHERE lead_id = :lid"),
                    {"lid": obj.lead_id}
                ).scalar()

                session.add(
                    LeadConversionHistory(
                        lead_id=obj.lead_id,
                        status_from=old,
                        status_to=new,
                        agent_id=agent_id
                    )
                )


# Block long-overdue follow-ups
@event.listens_for(FollowUpTask, "before_insert")
@event.listens_for(FollowUpTask, "before_update")
def block_overdue_task(mapper, connection, target):
    if target.due_date < datetime.now(timezone.utc) - timedelta(days=30):
        raise ValueError("Follow-up overdue >30 days not allowed")
