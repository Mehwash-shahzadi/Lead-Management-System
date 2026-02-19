"""add postgresql triggers for data validation

Revision ID: e7f8g9h10i11
Revises: d6e4f7g85c21
Create Date: 2026-02-17 10:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e7f8g9h10i11"
down_revision = "e7f5g8h96d32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # Trigger 1: Enforce valid status transitions on leads table
    # ---------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION enforce_status_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Allow inserts without transition checks
            IF TG_OP = 'INSERT' THEN
                RETURN NEW;
            END IF;

            -- No change in status → allow
            IF OLD.status = NEW.status THEN
                RETURN NEW;
            END IF;

            -- Terminal states cannot transition further
            IF OLD.status IN ('converted', 'lost') THEN
                RAISE EXCEPTION 'Cannot transition from terminal status: %', OLD.status;
            END IF;

            -- Validate allowed transitions
            IF NOT (
                (OLD.status = 'new' AND NEW.status IN ('contacted', 'lost'))
                OR (OLD.status = 'contacted' AND NEW.status IN ('qualified', 'lost'))
                OR (OLD.status = 'qualified' AND NEW.status IN ('viewing_scheduled', 'lost'))
                OR (OLD.status = 'viewing_scheduled' AND NEW.status IN ('negotiation', 'qualified', 'lost'))
                OR (OLD.status = 'negotiation' AND NEW.status IN ('converted', 'lost'))
            ) THEN
                RAISE EXCEPTION 'Invalid status transition from % to %', OLD.status, NEW.status;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_enforce_status_transition
        BEFORE UPDATE ON leads
        FOR EACH ROW
        EXECUTE FUNCTION enforce_status_transition();
    """)

    # ---------------------------------------------------------------
    # Trigger 2: Block overdue follow-up tasks (>30 days past due)
    # ---------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION block_overdue_follow_up()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.due_date < (NOW() - INTERVAL '30 days') THEN
                RAISE EXCEPTION 'Follow-up task overdue by more than 30 days is not allowed';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_block_overdue_follow_up
        BEFORE INSERT OR UPDATE ON follow_up_tasks
        FOR EACH ROW
        EXECUTE FUNCTION block_overdue_follow_up();
    """)

    # ---------------------------------------------------------------
    # Trigger 3: Auto-update updated_at timestamp on leads
    # ---------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_leads_updated_at
        BEFORE UPDATE ON leads
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE TRIGGER trg_follow_up_tasks_updated_at
        BEFORE UPDATE ON follow_up_tasks
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # ---------------------------------------------------------------
    # Trigger 4: Refresh agent active_leads_count on assignment changes
    # ---------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_agent_active_leads_count()
        RETURNS TRIGGER AS $$
        DECLARE
            target_agent_id UUID;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                target_agent_id := OLD.agent_id;
            ELSE
                target_agent_id := NEW.agent_id;
            END IF;

            UPDATE agents
            SET active_leads_count = (
                SELECT COUNT(*)
                FROM lead_assignments la
                JOIN leads l ON la.lead_id = l.lead_id
                WHERE la.agent_id = target_agent_id
                AND l.status NOT IN ('converted', 'lost')
            )
            WHERE agent_id = target_agent_id;

            -- Also refresh the old agent's count on reassignment
            IF TG_OP = 'UPDATE' AND OLD.agent_id != NEW.agent_id THEN
                UPDATE agents
                SET active_leads_count = (
                    SELECT COUNT(*)
                    FROM lead_assignments la
                    JOIN leads l ON la.lead_id = l.lead_id
                    WHERE la.agent_id = OLD.agent_id
                    AND l.status NOT IN ('converted', 'lost')
                )
                WHERE agent_id = OLD.agent_id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_refresh_active_leads_on_assignment
        AFTER INSERT OR UPDATE OR DELETE ON lead_assignments
        FOR EACH ROW
        EXECUTE FUNCTION refresh_agent_active_leads_count();
    """)

    # ---------------------------------------------------------------
    # Trigger 5: Log status transitions to lead_conversion_history
    # ---------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION log_status_transition()
        RETURNS TRIGGER AS $$
        DECLARE
            assigned_agent_id UUID;
        BEGIN
            IF OLD.status IS DISTINCT FROM NEW.status THEN
                SELECT agent_id INTO assigned_agent_id
                FROM lead_assignments
                WHERE lead_id = NEW.lead_id
                LIMIT 1;

                INSERT INTO lead_conversion_history (lead_id, status_from, status_to, agent_id)
                VALUES (NEW.lead_id, OLD.status, NEW.status, assigned_agent_id);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_log_status_transition
        AFTER UPDATE ON leads
        FOR EACH ROW
        EXECUTE FUNCTION log_status_transition();
    """)

    # ---------------------------------------------------------------
    # Trigger 6: Enforce agent max workload (50 active leads)
    # ---------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION enforce_agent_max_workload()
        RETURNS TRIGGER AS $$
        DECLARE
            current_count INTEGER;
        BEGIN
            SELECT active_leads_count INTO current_count
            FROM agents
            WHERE agent_id = NEW.agent_id;

            IF current_count >= 50 THEN
                RAISE EXCEPTION 'Agent % has reached maximum capacity of 50 active leads', NEW.agent_id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_enforce_agent_max_workload
        BEFORE INSERT ON lead_assignments
        FOR EACH ROW
        EXECUTE FUNCTION enforce_agent_max_workload();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute(
        "DROP TRIGGER IF EXISTS trg_enforce_agent_max_workload ON lead_assignments;"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_log_status_transition ON leads;")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_refresh_active_leads_on_assignment ON lead_assignments;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_follow_up_tasks_updated_at ON follow_up_tasks;"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_leads_updated_at ON leads;")
    op.execute("DROP TRIGGER IF EXISTS trg_block_overdue_follow_up ON follow_up_tasks;")
    op.execute("DROP TRIGGER IF EXISTS trg_enforce_status_transition ON leads;")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS enforce_agent_max_workload();")
    op.execute("DROP FUNCTION IF EXISTS log_status_transition();")
    op.execute("DROP FUNCTION IF EXISTS refresh_agent_active_leads_count();")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    op.execute("DROP FUNCTION IF EXISTS block_overdue_follow_up();")
    op.execute("DROP FUNCTION IF EXISTS enforce_status_transition();")
