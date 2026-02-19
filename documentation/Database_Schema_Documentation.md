# ThinkRealty Database Schema

## Overview

The ThinkRealty database runs on PostgreSQL 15 and has 10 tables designed for UAE real estate lead management. Data integrity is enforced through foreign keys, check constraints, and indexes, while SQLAlchemy event listeners handle runtime concerns like auto-updating timestamps, refreshing workload counters, and logging status changes. All tables use UUID primary keys (generated via `gen_random_uuid()`).

**ORM:** SQLAlchemy async (models in `app/models/`)
**Migrations:** Alembic (13 revisions in `alembic/versions/`)

---

## Entity-Relationship Diagram

```
leads ──< lead_activities
  │         └──> agents
  ├──< lead_assignments ──> agents
  ├──< lead_property_interests
  ├──< lead_sources ──> agents (referrer)
  └──< lead_conversion_history ──> agents

agents ──< agent_performance_metrics
agents ──< follow_up_tasks ──> leads

lead_scoring_rules (standalone config table)
```

---

## Core Tables

### leads

**Purpose:** Central table storing all lead information and contact details.

| Column                | Type          | Nullable | Default             | Description                                                 |
| --------------------- | ------------- | -------- | ------------------- | ----------------------------------------------------------- |
| `lead_id`             | UUID          | PK       | `gen_random_uuid()` | Unique identifier                                           |
| `source_type`         | VARCHAR(50)   | NOT NULL | —                   | bayut, propertyFinder, dubizzle, website, walk_in, referral |
| `first_name`          | VARCHAR(100)  | NOT NULL | —                   | First name                                                  |
| `last_name`           | VARCHAR(100)  | NOT NULL | —                   | Last name                                                   |
| `email`               | VARCHAR(255)  | NULL     | —                   | Optional email                                              |
| `phone`               | VARCHAR(20)   | NOT NULL | —                   | UAE phone (+971XXXXXXXXX)                                   |
| `nationality`         | VARCHAR(50)   | NULL     | —                   | Client nationality (used in scoring)                        |
| `language_preference` | VARCHAR(20)   | NULL     | —                   | `arabic` or `english`                                       |
| `budget_min`          | NUMERIC(15,2) | NULL     | —                   | Minimum budget in AED                                       |
| `budget_max`          | NUMERIC(15,2) | NULL     | —                   | Maximum budget in AED                                       |
| `property_type`       | VARCHAR(50)   | NULL     | —                   | apartment, villa, townhouse, commercial                     |
| `preferred_areas`     | TEXT[]        | NULL     | —                   | Array of location preferences                               |
| `status`              | VARCHAR(50)   | NOT NULL | `'new'`             | Current lead status                                         |
| `score`               | INTEGER       | NOT NULL | `0`                 | Quality score 0–100                                         |
| `created_at`          | TIMESTAMPTZ   | NOT NULL | `now()`             | Creation timestamp                                          |
| `updated_at`          | TIMESTAMPTZ   | NOT NULL | `now()`             | Last update (auto-set by listener)                          |

**Constraints:**

| Name                             | Type  | Rule                                                                                   |
| -------------------------------- | ----- | -------------------------------------------------------------------------------------- |
| `idx_leads_phone_source_created` | INDEX | `(phone, source_type, created_at)` — optimises 24-hour duplicate-detection queries     |
| `ck_score_range`                 | CHECK | `score BETWEEN 0 AND 100`                                                              |
| `ck_lead_status`                 | CHECK | status IN (new, contacted, qualified, viewing_scheduled, negotiation, converted, lost) |
| `ck_source_type`                 | CHECK | source_type IN (bayut, propertyFinder, dubizzle, website, walk_in, referral)           |
| `ck_budget_min_lt_max`           | CHECK | `budget_min IS NULL OR budget_max IS NULL OR budget_min < budget_max`                  |

> **Note:** There is deliberately no `UNIQUE(phone, source_type)` constraint. Duplicate detection is enforced at the application level with a 24-hour window. The same lead may be re-submitted from the same source after 24 hours and treated as a new entry. See _ThinkRealty Backend Assessment: Error Handling, Duplicate Lead Detection_.

**Relationships:** assignments (1:many), activities (1:many), property_interests (1:many), conversion_history (1:many), sources (1:many)

---

### agents

**Purpose:** Stores real estate agent profiles and specialization information.

| Column                         | Type         | Nullable | Default             | Description                |
| ------------------------------ | ------------ | -------- | ------------------- | -------------------------- |
| `agent_id`                     | UUID         | PK       | `gen_random_uuid()` | Unique identifier          |
| `full_name`                    | VARCHAR(200) | NOT NULL | —                   | Complete name              |
| `email`                        | VARCHAR(255) | NOT NULL | —                   | Unique email               |
| `phone`                        | VARCHAR(20)  | NOT NULL | —                   | Unique phone               |
| `specialization_property_type` | TEXT[]       | NULL     | —                   | Property types handled     |
| `specialization_areas`         | TEXT[]       | NULL     | —                   | Geographic specializations |
| `language_skills`              | TEXT[]       | NULL     | —                   | Languages spoken           |
| `active_leads_count`           | INTEGER      | NOT NULL | `0`                 | Current workload counter   |
| `created_at`                   | TIMESTAMPTZ  | NOT NULL | `now()`             | Creation timestamp         |
| `updated_at`                   | TIMESTAMPTZ  | NOT NULL | `now()`             | Last update (auto-set)     |

**Constraints:**

| Name                     | Type   | Rule                       |
| ------------------------ | ------ | -------------------------- |
| `email`                  | UNIQUE | Unique email per agent     |
| `phone`                  | UNIQUE | Unique phone per agent     |
| `ck_active_leads_max`    | CHECK  | `active_leads_count <= 50` |
| `ck_active_leads_nonneg` | CHECK  | `active_leads_count >= 0`  |

**Relationships:** assignments (1:many), activities (1:many), tasks (1:many), performance_metrics (1:many)

---

### lead_assignments

**Purpose:** Tracks which agent is responsible for each lead.

| Column          | Type             | Nullable | Default             | Description            |
| --------------- | ---------------- | -------- | ------------------- | ---------------------- |
| `assignment_id` | UUID             | PK       | `gen_random_uuid()` | Unique identifier      |
| `lead_id`       | UUID FK → leads  | NOT NULL | —                   | Assigned lead          |
| `agent_id`      | UUID FK → agents | NOT NULL | —                   | Assigned agent         |
| `assigned_at`   | TIMESTAMPTZ      | NULL     | `now()`             | Assignment time        |
| `reassigned_at` | TIMESTAMPTZ      | NULL     | —                   | Last reassignment time |
| `reason`        | TEXT             | NULL     | —                   | Reassignment reason    |

**Constraints:**

| Name                 | Type   | Rule                                         |
| -------------------- | ------ | -------------------------------------------- |
| `uq_lead_assignment` | UNIQUE | `(lead_id)` — one active assignment per lead |

**FK Cascade:** Both `lead_id` and `agent_id` CASCADE on DELETE.

---

### lead_activities

**Purpose:** Records all interactions and communications with leads.

| Column        | Type             | Nullable | Default             | Description                  |
| ------------- | ---------------- | -------- | ------------------- | ---------------------------- |
| `activity_id` | UUID             | PK       | `gen_random_uuid()` | Unique identifier            |
| `lead_id`     | UUID FK → leads  | NOT NULL | —                   | Associated lead              |
| `agent_id`    | UUID FK → agents | NOT NULL | —                   | Agent who performed activity |
| `type`        | VARCHAR(50)      | NOT NULL | —                   | Activity type                |
| `notes`       | TEXT             | NULL     | —                   | Detailed description         |
| `outcome`     | VARCHAR(20)      | NULL     | —                   | positive, negative, neutral  |
| `activity_at` | TIMESTAMPTZ      | NULL     | `now()`             | When activity occurred       |

**Constraints:**

| Name                  | Type  | Rule                                                          |
| --------------------- | ----- | ------------------------------------------------------------- |
| `ck_activity_type`    | CHECK | type IN (call, email, whatsapp, viewing, meeting, offer_made) |
| `ck_activity_outcome` | CHECK | outcome IN (positive, negative, neutral) OR NULL              |

**Business Logic:** The `activity_at` column is used by the lead scoring engine to detect 7-day inactivity (−10 score penalty).

---

### follow_up_tasks

**Purpose:** Manages scheduled follow-up activities and deadlines.

| Column       | Type             | Nullable | Default             | Description                        |
| ------------ | ---------------- | -------- | ------------------- | ---------------------------------- |
| `task_id`    | UUID             | PK       | `gen_random_uuid()` | Unique identifier                  |
| `lead_id`    | UUID FK → leads  | NOT NULL | —                   | Related lead                       |
| `agent_id`   | UUID FK → agents | NOT NULL | —                   | Responsible agent                  |
| `type`       | VARCHAR(50)      | NOT NULL | —                   | call, email, whatsapp, viewing     |
| `due_date`   | TIMESTAMPTZ      | NOT NULL | —                   | Deadline                           |
| `priority`   | VARCHAR(20)      | NOT NULL | `'medium'`          | high, medium, low                  |
| `status`     | VARCHAR(20)      | NOT NULL | `'pending'`         | pending, completed, overdue        |
| `created_at` | TIMESTAMPTZ      | NULL     | `now()`             | Created time                       |
| `updated_at` | TIMESTAMPTZ      | NULL     | `now()`             | Last update (auto-set by listener) |

**Constraints:**

| Name               | Type  | Rule                                     |
| ------------------ | ----- | ---------------------------------------- |
| `ck_task_type`     | CHECK | type IN (call, email, whatsapp, viewing) |
| `ck_task_priority` | CHECK | priority IN (high, medium, low)          |
| `ck_task_status`   | CHECK | status IN (pending, completed, overdue)  |

**Business Logic:** Follow-up conflict detection prevents scheduling two tasks within 30 minutes of each other for the same agent.

---

### lead_property_interests

**Purpose:** Tracks specific properties that leads have shown interest in.

| Column           | Type            | Nullable | Default             | Description              |
| ---------------- | --------------- | -------- | ------------------- | ------------------------ |
| `interest_id`    | UUID            | PK       | `gen_random_uuid()` | Unique identifier        |
| `lead_id`        | UUID FK → leads | NOT NULL | —                   | Lead expressing interest |
| `property_id`    | UUID            | NOT NULL | —                   | External property ID     |
| `interest_level` | VARCHAR(20)     | NOT NULL | —                   | high, medium, low        |
| `created_at`     | TIMESTAMPTZ     | NULL     | `now()`             | When recorded            |

**Constraints:**

| Name                                | Type   | Rule                                          |
| ----------------------------------- | ------ | --------------------------------------------- |
| `uq_lead_property_interest`         | UNIQUE | `(lead_id, property_id)` — no duplicate pairs |
| `ix_property_interests_property_id` | INDEX  | `(property_id)` — supports suggestion queries |
| `ck_interest_level`                 | CHECK  | interest_level IN (high, medium, low)         |

---

### lead_sources

**Purpose:** Detailed source attribution and campaign tracking.

| Column              | Type             | Nullable | Default             | Description                          |
| ------------------- | ---------------- | -------- | ------------------- | ------------------------------------ |
| `source_id`         | UUID             | PK       | `gen_random_uuid()` | Unique identifier                    |
| `lead_id`           | UUID FK → leads  | NOT NULL | —                   | Associated lead                      |
| `source_type`       | VARCHAR(50)      | NOT NULL | —                   | Origin source type                   |
| `campaign_id`       | VARCHAR(100)     | NULL     | —                   | Marketing campaign ID                |
| `referrer_agent_id` | UUID FK → agents | NULL     | —                   | Referring agent (SET NULL on delete) |
| `property_id`       | UUID             | NULL     | —                   | Property inquiry trigger             |
| `utm_source`        | VARCHAR(100)     | NULL     | —                   | UTM source tracking                  |
| `created_at`        | TIMESTAMPTZ      | NULL     | `now()`             | Created time                         |

**Constraints:**

| Name                          | Type  | Rule                                                                         |
| ----------------------------- | ----- | ---------------------------------------------------------------------------- |
| `ck_lead_source_source_type`  | CHECK | source_type IN (bayut, propertyFinder, dubizzle, website, walk_in, referral) |
| `ix_lead_sources_source_type` | INDEX | `(source_type)` — supports analytics source-type filtering                   |

---

### lead_conversion_history

**Purpose:** Records all status transitions and deal details for leads.

| Column            | Type             | Nullable | Default             | Description                                                                          |
| ----------------- | ---------------- | -------- | ------------------- | ------------------------------------------------------------------------------------ |
| `history_id`      | UUID             | PK       | `gen_random_uuid()` | Unique identifier                                                                    |
| `lead_id`         | UUID FK → leads  | NOT NULL | —                   | Lead being tracked                                                                   |
| `status_from`     | VARCHAR(50)      | NULL     | —                   | Previous status                                                                      |
| `status_to`       | VARCHAR(50)      | NULL     | —                   | New status                                                                           |
| `changed_at`      | TIMESTAMPTZ      | NULL     | `now()`             | Transition timestamp                                                                 |
| `agent_id`        | UUID FK → agents | NULL     | —                   | Agent responsible                                                                    |
| `notes`           | TEXT             | NULL     | —                   | Transition notes                                                                     |
| `deal_value`      | NUMERIC(15,2)    | NULL     | —                   | Transaction amount in AED                                                            |
| `conversion_type` | VARCHAR(20)      | NULL     | —                   | sale, rental, or lost                                                                |
| `property_id`     | UUID             | NULL     | —                   | Property involved in the conversion (no FK constraint — FK was removed in migration) |

**Business Logic:** Rows are auto-inserted by the `before_flush` SQLAlchemy listener whenever a lead's status changes. Used by analytics queries for revenue attribution and agent performance rankings.

---

### agent_performance_metrics

**Purpose:** Aggregated performance statistics for agent evaluation and assignment weighting.

| Column                  | Type             | Nullable | Default             | Description                |
| ----------------------- | ---------------- | -------- | ------------------- | -------------------------- |
| `metric_id`             | UUID             | PK       | `gen_random_uuid()` | Unique identifier          |
| `agent_id`              | UUID FK → agents | NOT NULL | —                   | Evaluated agent            |
| `conversion_rate`       | NUMERIC(5,2)     | NULL     | —                   | Percentage rate            |
| `average_deal_size`     | NUMERIC(15,2)    | NULL     | —                   | Average deal value in AED  |
| `average_response_time` | INTERVAL         | NULL     | —                   | Mean time to first contact |
| `leads_handled`         | INTEGER          | NULL     | —                   | Total leads processed      |
| `updated_at`            | TIMESTAMPTZ      | NULL     | `now()`             | Last recalculation         |

**FK Cascade:** `agent_id` CASCADE on DELETE.

**Business Logic:** The `conversion_rate` is used during lead assignment to score agents: ≥30% → +3 pts, ≥20% → +2 pts, >0% → +1 pt. Metrics are eagerly loaded (`selectinload`) during agent selection to avoid N+1 queries.

---

### lead_scoring_rules

**Purpose:** Configurable lead scoring parameters stored as JSONB conditions.

| Column             | Type         | Nullable | Default             | Description            |
| ------------------ | ------------ | -------- | ------------------- | ---------------------- |
| `rule_id`          | UUID         | PK       | `gen_random_uuid()` | Unique identifier      |
| `rule_name`        | VARCHAR(100) | NOT NULL | —                   | Descriptive rule name  |
| `score_adjustment` | INTEGER      | NOT NULL | —                   | Points to add/subtract |
| `condition`        | JSONB        | NOT NULL | —                   | Matching criteria      |
| `created_at`       | TIMESTAMPTZ  | NULL     | `now()`             | Creation time          |

**Business Logic:** Enables dynamic lead scoring rule changes without code modifications. Conditions are stored as flexible JSONB objects.

---

## SQLAlchemy Event Listeners

The `app/models/listeners.py` module registers one active listener. All other runtime concerns (workload counters, status history logging, overdue task blocking) are handled by PostgreSQL triggers defined in migration `e7f8g9h10i11`.

### Auto-Timestamp Update

Fires `before_update` on Lead, Agent, and FollowUpTask to set `updated_at = now()`. This is kept as an ORM convenience for non-PostgreSQL backends (e.g. test suites using SQLite). On PostgreSQL, the `trg_leads_updated_at` and `trg_follow_up_tasks_updated_at` triggers perform the same operation — both set the timestamp to the current UTC time, so there's no risk of the two diverging.

### PostgreSQL Triggers (via migration `e7f8g9h10i11`)

The following business rules are enforced at the database level:

| Trigger                                  | Table              | Event                      | Function                                 |
| ---------------------------------------- | ------------------ | -------------------------- | ---------------------------------------- |
| `trg_enforce_status_transition`          | `leads`            | BEFORE UPDATE              | Validates status transitions             |
| `trg_block_overdue_follow_up`            | `follow_up_tasks`  | BEFORE INSERT              | Blocks tasks >30 days overdue            |
| `trg_leads_updated_at`                   | `leads`            | BEFORE UPDATE              | Auto-sets `updated_at = now()`           |
| `trg_follow_up_tasks_updated_at`         | `follow_up_tasks`  | BEFORE UPDATE              | Auto-sets `updated_at = now()`           |
| `trg_refresh_active_leads_on_assignment` | `lead_assignments` | AFTER INSERT/UPDATE/DELETE | Recalculates `agents.active_leads_count` |
| `trg_log_status_transition`              | `leads`            | AFTER UPDATE               | Inserts `lead_conversion_history` row    |
| `trg_enforce_agent_max_workload`         | `lead_assignments` | BEFORE INSERT              | Blocks assignment if agent at 50 leads   |

> **Note:** The previous SQLAlchemy listeners for `refresh_active_leads_count`, `validate_status_and_log`, and `block_overdue_task` were removed because they duplicated the PostgreSQL triggers above.

---

## Alembic Migrations

<!-- AUTO-CHECK: scripts/check_migration_docs.py validates this count -->
<!-- Run `python scripts/check_migration_docs.py` before committing new migrations -->

| #   | Revision          | Filename                                                     | Description                                                                     |
| --- | ----------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------- |
| 1   | `7762ee95a04c`    | `7762ee95a04c_clean_initial_schema.py`                       | Creates all 10 core tables (leads, agents, assignments, activities, etc.)       |
| 2   | `924be657aed4`    | `924be657aed4_add_timestamps_to_leads.py`                    | Adds `created_at`/`updated_at` timestamp columns to leads                       |
| 3   | `a3f1c8e92b10`    | `a3f1c8e92b10_add_deal_value_conversion_type_property.py`    | Adds `deal_value`, `conversion_type`, `property_id` to conversion history       |
| 4   | `b4c2d5f83a19`    | `b4c2d5f83a19_add_performance_indexes.py`                    | Adds performance indexes on leads, activities, tasks, and metrics tables        |
| 5   | `c5d3e6f94b20`    | `c5d3e6f94b20_add_timestamps_to_agents.py`                   | Adds `created_at`/`updated_at` timestamp columns to agents                      |
| 6   | `d6e4f7g85c21`    | `d6e4f7g85c21_fix_property_id_fk_and_add_partial_indexes.py` | Drops incorrect property_id FK; adds partial indexes for active/pending         |
| 7   | `e7f5g8h96d32`    | `e7f5g8h96d32_seed_default_scoring_rules.py`                 | Seeds canonical scoring rules into `lead_scoring_rules` (idempotent)            |
| 8   | `e7f8g9h10i11`    | `e7f8g9h10i11_add_postgresql_triggers.py`                    | Adds 7 DB triggers: status transitions, overdue tasks, workload, timestamps     |
| 9   | `f8g9h10i11j12`   | `f8g9h10i11j12_add_budget_check_constraint.py`               | Adds `ck_budget_min_lt_max` CHECK constraint on leads                           |
| 10  | `g9h10i11j12k13`  | `g9h10i11j12k13_replace_phone_source_unique_with_index.py`   | Replaces `UNIQUE(phone, source_type)` with composite index (24h app logic)      |
| 11  | `h10i11j12k13l14` | `h10i11j12k13l14_add_unique_constraint_and_fix_fk.py`        | Adds unique constraints and fixes foreign key references                        |
| 12  | `i11j12k13l14m15` | `i11j12k13l14m15_fix_constraint_names_and_checks.py`         | Fixes constraint names and CHECK expressions for consistency                    |
| 13  | `j12k13l14m15n16` | `j12k13l14m15n16_add_missing_query_indexes.py`               | Adds indexes on `property_interests.property_id` and `lead_sources.source_type` |

**Total migrations: 13**
**Current HEAD revision:** `j12k13l14m15n16`
**Last updated:** 2026-02-18

Run migrations: `alembic upgrade head`
