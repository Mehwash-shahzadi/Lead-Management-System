# ThinkRealty Business Rules

## Introduction

This document explains the business rules that govern how ThinkRealty handles leads — from the moment a lead comes in, through scoring and assignment, all the way to conversion tracking. Rules are enforced at multiple levels (database constraints, application-level validators, SQLAlchemy event listeners) so nothing slips through even if one layer fails.

---

## 1. Duplicate Lead Detection

**Rule:** If the same phone number from the same source was already submitted within the last 24 hours, it's rejected as a duplicate. After 24 hours, the same person can submit again and it's treated as a fresh lead.

**How it works — two layers:**

| Layer               | What it does                                                                                                                                                            |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Redis (fast path)   | `lead_capture_service.py` checks a Redis key `lead_duplicate:{phone}:{source}` with a 24-hour TTL. If the key exists, the lead is rejected without ever hitting the DB. |
| Database (fallback) | `LeadRepository.find_duplicate()` queries for matching phone + source_type where `created_at` is within the last 24 hours. This kicks in if Redis is unavailable.       |

> **Note:** There is no permanent `UNIQUE(phone, source_type)` constraint on the `leads` table. Duplicate detection is purely application-level with a 24-hour window. A composite index `idx_leads_phone_source_created` on `(phone, source_type, created_at)` keeps the lookup fast.

**Error:** `DuplicateLeadError` → HTTP 409 with `type: duplicate_lead`.

---

## 2. Dynamic Lead Scoring (0–100)

Every lead gets an automated quality score. The scoring engine (`app/services/lead_scoring.py`) reads rules from the `lead_scoring_rules` database table, so you can tweak scoring without changing code. If the rules table is empty or unreachable, a neutral fallback score of 50 is used.

The canonical set of rules is defined in `app/core/default_scoring_rules.py` and seeded into the database via Alembic migration.

### Initial Score (at capture)

| Factor              | Condition                                 | Points |
| ------------------- | ----------------------------------------- | ------ |
| **Budget**          | > 10M AED                                 | +20    |
|                     | > 5M AED                                  | +15    |
|                     | > 2M AED                                  | +10    |
|                     | ≤ 2M AED                                  | +5     |
| **Source quality**  | referral                                  | +95    |
|                     | bayut                                     | +90    |
|                     | propertyfinder                            | +85    |
|                     | website                                   | +80    |
|                     | dubizzle                                  | +75    |
|                     | walk_in                                   | +70    |
|                     | (unknown)                                 | +50    |
| **Nationality**     | UAE / Emirati                             | +10    |
|                     | GCC (Saudi, Kuwait, Bahrain, Qatar, Oman) | +5     |
| **Property type**   | Any specified                             | +5     |
| **Preferred areas** | Any specified                             | +5     |
| **Referral bonus**  | Has `referrer_agent_id`                   | +10    |

Score is clamped to `[0, 100]`.

### Response Time Bonus (at initial scoring)

The scoring engine also checks how quickly the assigned agent made first contact. The first activity logged for a lead determines the response time.

| Agent Response Time | Points |
| ------------------- | ------ |
| ≤ 1 hour            | +15    |
| ≤ 4 hours           | +10    |
| ≤ 24 hours          | +5     |
| ≤ 72 hours          | 0      |
| > 72 hours / none   | −10    |

These tiers are also stored as `response_time` type rules in the `lead_scoring_rules` table.

### Score Recalculation (on update)

When a lead is updated via `PUT /leads/{id}/update`, the scoring engine recalculates:

| Activity / Condition            | Adjustment |
| ------------------------------- | ---------- |
| Positive outcome                | +5         |
| Property viewing                | +10        |
| Offer made                      | +20        |
| **7+ days since last activity** | **−10**    |

The 7-day inactivity check uses the `last_activity_at` value fetched from the `lead_activities` table (`ActivityRepository.get_last_activity_at()`). If the most recent activity is ≥7 days ago, the penalty applies automatically during score recalculation.

---

## 3. Intelligent Agent Assignment

When a new lead comes in, the system automatically picks the best available agent. This is handled by `LeadAssignmentManager` in `app/services/lead_assignment.py`.

### How Agents Are Scored

Each agent who isn't at capacity gets a match score based on how well they fit the lead:

| Factor                           | Condition                                                            | Points |
| -------------------------------- | -------------------------------------------------------------------- | ------ |
| **Property type specialization** | Lead's `property_type` ∈ agent's `specialization_property_type[]`    | +3     |
| **Area specialization**          | Any of lead's `preferred_areas[]` ∈ agent's `specialization_areas[]` | +2     |
| **Language preference**          | Lead's `language_preference` ∈ agent's `language_skills[]`           | +2     |
| **Performance metrics**          | Latest `conversion_rate` ≥ 30%                                       | +3     |
|                                  | Latest `conversion_rate` ≥ 20%                                       | +2     |
|                                  | Latest `conversion_rate` > 0%                                        | +1     |

### How the Winner Is Picked

1. **Sort** agents by score (highest first), then by `active_leads_count` (lowest first) as a tiebreaker for workload balance.
2. **Collect all agents sharing the top score** — regardless of their workload. Workload only affects ordering within this group, not membership.
3. **Round-robin** among the top-score group using a Redis counter (key: `round_robin:assignment:{score}`, 24-hour TTL). This ensures leads are distributed evenly even when multiple agents are equally qualified. If Redis is down, a class-level fallback counter is used instead.
4. The selected agent's ID is returned and the assignment is recorded in `lead_assignments`.

### Performance Metrics Loading

Agent records are loaded with `selectinload(Agent.performance_metrics)` to avoid N+1 queries when scoring. The most recent metric (by `updated_at`) is used for conversion rate scoring.

**Error:** If every agent is at capacity (50 active leads), the system returns `AgentOverloadError` → HTTP 503.

---

## 4. Status Transition Control

Lead status changes follow a strict state machine defined in `app/core/constants.py` (`ALLOWED_TRANSITIONS`):

```
new → contacted, lost
contacted → qualified, lost
qualified → viewing_scheduled, lost
viewing_scheduled → negotiation, qualified, lost
negotiation → converted, lost
converted → (terminal)
lost → (terminal)
```

### Enforcement

- **Single source of truth:** `LeadValidator.validate_status_transition()` in `app/dependencies.py` checks transitions against `ALLOWED_TRANSITIONS`.
- **Database backup:** CHECK constraint `ck_lead_status` ensures the `status` column only contains valid status values.
- **History logging:** The `before_flush` SQLAlchemy listener in `listeners.py` auto-inserts a `lead_conversion_history` row for every status change, recording `status_from`, `status_to`, `agent_id`, and `changed_at`.

**Error:** Invalid transitions → `InvalidStatusTransitionError` → HTTP 400.

---

## 5. Agent Workload Limits

| Rule                           | Value  |
| ------------------------------ | ------ |
| Maximum active leads per agent | **50** |

### Enforcement

- **Database CHECK:** `CHECK (active_leads_count <= 50)` on `agents` table prevents invalid values at the storage level.
- **Database trigger:** `trg_enforce_agent_max_workload` on `lead_assignments` fires before INSERT and raises an exception if the agent is already at 50 active leads.
- **Database trigger:** `trg_refresh_active_leads_on_assignment` automatically recalculates `active_leads_count` by counting non-terminal (not converted/lost) assignments whenever an assignment changes.
- **Application:** `get_available_agents(max_leads=50)` filters agents in the assignment query, and `LeadValidator.validate_agent_capacity()` uses the `MAX_AGENT_ACTIVE_LEADS` constant for a defense-in-depth pre-check with a consistent error message.

---

## 6. Follow-Up Conflict Detection

**Rule:** An agent cannot have two follow-up tasks scheduled within **30 minutes** of each other.

When a new follow-up is requested during lead update, the system queries existing pending tasks for that agent and checks if any fall within a 30-minute window of the proposed due date.

**Error:** `FollowUpConflictError` → HTTP 409 with `type: follow_up_conflict`.

The conflict window is configured via `FOLLOW_UP_CONFLICT_WINDOW_MINUTES` in `app/core/config.py` (default: 30).

---

## 7. Redis Caching Strategy

The system uses Redis 7 for two distinct caching purposes:

| Purpose                    | Key Pattern                       | TTL       | Fallback                                     |
| -------------------------- | --------------------------------- | --------- | -------------------------------------------- |
| **Duplicate detection**    | `lead_duplicate:{phone}:{source}` | 24 hours  | Falls back to DB query with 24h window       |
| **Dashboard caching**      | `dashboard:{agent_id}:{hash}`     | 5 minutes | Queries DB directly                          |
| **Round-robin assignment** | `round_robin:assignment:{score}`  | 24 hours  | Falls back to class-level in-process counter |

Redis is optional — `CacheService` in `app/core/cache.py` centralises all Redis operations and handles graceful degradation. If Redis goes down, every operation falls back to database-only or in-process paths without raising errors. Services use `CacheService` instead of direct Redis calls.

---

## Enforcement Summary

| Business Rule         | Database Layer                    | Application Layer                      | DB Trigger / Listener             |
| --------------------- | --------------------------------- | -------------------------------------- | --------------------------------- |
| Duplicate prevention  | Composite index (phone+source+ts) | Redis `lead_duplicate:` + DB 24h query | —                                 |
| Score range           | `CHECK score BETWEEN 0 AND 100`   | `min(100, max(0, score))`              | —                                 |
| Status values         | `CHECK status IN (...)`           | `LeadValidator`                        | —                                 |
| Status transitions    | `trg_enforce_status_transition`   | `ALLOWED_TRANSITIONS` dict             | `trg_log_status_transition`       |
| Agent capacity        | `CHECK active_leads_count <= 50`  | `get_available_agents` filter          | `trg_enforce_agent_max_workload`  |
| Workload counter sync | —                                 | —                                      | `trg_refresh_active_leads_count`  |
| Follow-up conflicts   | —                                 | 30-min window check                    | —                                 |
| Inactivity penalty    | —                                 | 7-day check in scoring engine          | —                                 |
| Budget validation     | `CHECK budget_min < budget_max`   | Pydantic `@model_validator` (500M cap) | —                                 |
| Response time scoring | —                                 | First-contact time bonus (±15 pts)     | —                                 |
| Timestamps            | `trg_leads_updated_at`            | —                                      | ORM `update_timestamp` listener   |
| Overdue task blocking | `trg_block_overdue_follow_up`     | —                                      | —                                 |

---

## 8. Property Suggestion Service

The `PropertySuggestionService` (`app/services/property_suggestion_service.py`) handles two concerns:

### Availability Check

| Mode       | Condition                       | Behaviour                                                                                      |
| ---------- | ------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Local**  | `PROPERTY_SERVICE_URL` is empty | Suggestions served via collaborative filtering from the database. Check passes immediately.    |
| **Remote** | `PROPERTY_SERVICE_URL` is set   | HTTP health check via `httpx`. Raises `PropertyServiceUnavailableError` (HTTP 503) on failure. |

### Collaborative Filtering

When no external property-suggestion micro-service is configured, the system uses **collaborative filtering** to recommend properties:

1. Finds `lead_property_interests` records from leads with **similar profiles** (matching property type, budget overlap, area overlap)
2. Only considers leads with **proven demand** (status: `converted`, `qualified`, `negotiation`)
3. Ranks properties by a composite **relevance score** (interest level weight × popularity)
4. Returns up to 5 property UUID strings matching the assessment response format

**Graceful degradation:** If the repository query fails, returns an empty list without raising an error.
