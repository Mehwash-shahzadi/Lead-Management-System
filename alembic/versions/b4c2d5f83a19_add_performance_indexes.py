"""add performance indexes

Revision ID: b4c2d5f83a19
Revises: a3f1c8e92b10
Create Date: 2026-02-16 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c2d5f83a19"
down_revision: Union[str, None] = "a3f1c8e92b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # leads — frequently filtered by status and source_type
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_source_type", "leads", ["source_type"])
    op.create_index("ix_leads_created_at", "leads", ["created_at"])
    op.create_index(
        "ix_leads_phone_source_created",
        "leads",
        ["phone", "source_type", "created_at"],
    )

    # lead_assignments — agent workload lookups
    op.create_index("ix_lead_assignments_agent_id", "lead_assignments", ["agent_id"])

    # lead_activities — per-lead activity timeline & last-activity queries
    op.create_index("ix_lead_activities_lead_id", "lead_activities", ["lead_id"])
    op.create_index(
        "ix_lead_activities_agent_id_at",
        "lead_activities",
        ["agent_id", "activity_at"],
    )

    # follow_up_tasks — dashboard pending-task queries
    op.create_index(
        "ix_follow_up_tasks_agent_status",
        "follow_up_tasks",
        ["agent_id", "status"],
    )
    op.create_index("ix_follow_up_tasks_due_date", "follow_up_tasks", ["due_date"])

    # lead_conversion_history — analytics joins
    op.create_index(
        "ix_conversion_history_lead_id",
        "lead_conversion_history",
        ["lead_id"],
    )
    op.create_index(
        "ix_conversion_history_agent_id",
        "lead_conversion_history",
        ["agent_id"],
    )

    # agent_performance_metrics — join on agent_id
    op.create_index(
        "ix_agent_perf_metrics_agent_id",
        "agent_performance_metrics",
        ["agent_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_perf_metrics_agent_id", table_name="agent_performance_metrics"
    )
    op.drop_index(
        "ix_conversion_history_agent_id", table_name="lead_conversion_history"
    )
    op.drop_index("ix_conversion_history_lead_id", table_name="lead_conversion_history")
    op.drop_index("ix_follow_up_tasks_due_date", table_name="follow_up_tasks")
    op.drop_index("ix_follow_up_tasks_agent_status", table_name="follow_up_tasks")
    op.drop_index("ix_lead_activities_agent_id_at", table_name="lead_activities")
    op.drop_index("ix_lead_activities_lead_id", table_name="lead_activities")
    op.drop_index("ix_lead_assignments_agent_id", table_name="lead_assignments")
    op.drop_index("ix_leads_phone_source_created", table_name="leads")
    op.drop_index("ix_leads_created_at", table_name="leads")
    op.drop_index("ix_leads_source_type", table_name="leads")
    op.drop_index("ix_leads_status", table_name="leads")
