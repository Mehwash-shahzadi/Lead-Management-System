# ThinkRealty Lead Management API

## Overview

This is the REST API for the ThinkRealty lead management system. It handles everything from capturing new real estate leads to scoring them, assigning them to agents, tracking activities, and running analytics.

The API is built with FastAPI and follows a layered architecture (API → Services → Repositories → Models). All endpoints live under `/api/v1` and return JSON.

**Base URL:** `http://localhost:8000/api/v1`
**Interactive Docs:** `http://localhost:8000/docs`

---

## Core Endpoints

### POST /api/v1/leads/capture

**What it does:** Takes in a new lead from any of the six sources (Bayut, PropertyFinder, Dubizzle, website, walk-in, or referral). Behind the scenes, the system checks for duplicates (same phone + source within 24 hours), scores the lead based on budget, source quality, nationality, and other factors, picks the best available agent, and creates an initial follow-up task.

**Request Body:**

```json
{
  "source_type": "bayut",
  "lead_data": {
    "first_name": "Ahmed",
    "last_name": "Al Mansouri",
    "email": "ahmed.mansouri@example.com",
    "phone": "+971501234567",
    "nationality": "UAE",
    "language_preference": "arabic",
    "budget_min": 800000,
    "budget_max": 1500000,
    "property_type": "apartment",
    "preferred_areas": ["Downtown Dubai", "Business Bay"]
  },
  "source_details": {
    "campaign_id": "summer_2026",
    "utm_source": "google_ads",
    "referrer_agent_id": null,
    "property_id": null
  }
}
```

**Field Validation:**

| Field                      | Rule                                                                            |
| -------------------------- | ------------------------------------------------------------------------------- |
| `source_type`              | One of: `bayut`, `propertyFinder`, `dubizzle`, `website`, `walk_in`, `referral` |
| `phone`                    | Must match UAE format: `+971XXXXXXXXX` (regex `^\+971\d{9}$`)                   |
| `email`                    | Valid email format (optional)                                                   |
| `budget_min`, `budget_max` | Must be > 0. `budget_min` must be less than `budget_max`. Max ceiling is 500M AED. Validated at the Pydantic schema level via `@model_validator`. |
| `language_preference`      | `arabic` or `english`                                                           |
| `property_type`            | One of: `apartment`, `villa`, `townhouse`, `commercial`                         |
| `preferred_areas`          | At least 1 area required                                                        |

**Success Response (201 Created):**

```json
{
  "success": true,
  "lead_id": "123e4567-e89b-12d3-a456-426614174000",
  "assigned_agent": {
    "agent_id": "456e7890-e89b-12d3-a456-426614174001",
    "name": "Sara Al Hassan",
    "phone": "+971501234568"
  },
  "lead_score": 85,
  "next_follow_up": "2026-02-17T10:00:00Z",
  "suggested_properties": []
}
```

**Error Responses:**

| Status | Type                           | Description                                         |
| ------ | ------------------------------ | --------------------------------------------------- |
| `409`  | `duplicate_lead`               | Same phone number from this source within 24 hours  |
| `503`  | `agent_overload`               | All agents have reached maximum capacity (50 leads) |
| `422`  | `invalid_lead_data`            | Budget min must be less than budget max, or budget exceeds 500M AED ceiling |
| `422`  | `validation_error`             | Missing required fields or invalid formats          |
| `503`  | `property_service_unavailable` | Property suggestion service unavailable             |

---

### PUT /api/v1/leads/{lead_id}/update

**What it does:** Updates a lead's status, logs a new activity, records property interests, and manages follow-up tasks. The system enforces status transitions (you can't jump from "new" to "converted"), recalculates the lead score based on the activity outcome, and checks for 7-day inactivity penalties.

**Path Parameters:**

- `lead_id` (UUID) — The lead to update

**Request Body:**

```json
{
  "status": "qualified",
  "activity": {
    "type": "call",
    "notes": "Client expressed strong interest in 2BR apartments in Marina area. Budget confirmed at 1.2M AED.",
    "outcome": "positive",
    "next_follow_up": "2026-02-18T14:00:00Z"
  },
  "property_interests": [
    {
      "property_id": "789e0123-e89b-12d3-a456-426614174002",
      "interest_level": "high"
    }
  ]
}
```

**Field Details:**

| Field                                 | Type                  | Description                                                                              |
| ------------------------------------- | --------------------- | ---------------------------------------------------------------------------------------- |
| `status`                              | Optional enum         | `new`, `contacted`, `qualified`, `viewing_scheduled`, `negotiation`, `converted`, `lost` |
| `activity.type`                       | Enum                  | `call`, `email`, `whatsapp`, `viewing`, `meeting`, `offer_made`                          |
| `activity.outcome`                    | Enum                  | `positive`, `negative`, `neutral`                                                        |
| `activity.next_follow_up`             | Optional ISO datetime | Schedules a follow-up task                                                               |
| `property_interests[].interest_level` | Enum                  | `high`, `medium`, `low`                                                                  |

**Score Adjustments on Update:**

| Activity                    | Points |
| --------------------------- | ------ |
| Positive outcome            | +5     |
| Property viewing            | +10    |
| Offer made                  | +20    |
| 7+ days since last activity | -10    |

**Response Time Bonus (applied on first activity):**

The response time bonus is based on how quickly the assigned agent makes first contact with the lead. It's calculated when the first activity is logged via `update_lead_score`, not at initial capture (since the agent hasn't responded yet at capture time).

| Agent Response Time | Points |
| ------------------- | ------ |
| ≤ 1 hour             | +15    |
| ≤ 4 hours            | +10    |
| ≤ 24 hours           | +5     |
| ≤ 72 hours           | 0      |
| > 72 hours / none   | −10    |

**Success Response (200 OK):**

```json
{
  "success": true,
  "lead_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "qualified",
  "score": 90
}
```

**Error Responses:**

| Status | Type                        | Description                                               |
| ------ | --------------------------- | --------------------------------------------------------- |
| `404`  | Not Found                   | Lead not found                                            |
| `400`  | `invalid_status_transition` | Cannot transition from current status to requested status |
| `409`  | `follow_up_conflict`        | Agent has conflicting follow-up(s) within 30 minutes      |
| `422`  | Not Found                   | No agent assigned to lead                                 |

---

### GET /api/v1/agents/{agent_id}/dashboard

**What it does:** Returns a snapshot of an agent's current workload and performance — active leads, recent leads, pending tasks, and key metrics. You can filter by date range, lead status, or source. Responses are cached in Redis for 5 minutes to keep things fast.

**Path Parameters:**

- `agent_id` (UUID) — The agent whose dashboard to retrieve

**Query Parameters:**

| Parameter       | Values                                                                         | Default         |
| --------------- | ------------------------------------------------------------------------------ | --------------- |
| `date_range`    | `7d`, `30d`, `90d`, `custom`                                                   | None (all time) |
| `status_filter` | `all`, `active`, `converted`, `lost`                                           | None            |
| `source_filter` | `all`, `bayut`, `propertyFinder`, `dubizzle`, `website`, `walk_in`, `referral` | None            |

**Success Response (200 OK):**

```json
{
  "agent_summary": {
    "total_active_leads": 23,
    "overdue_follow_ups": 2,
    "this_month_conversions": 4,
    "average_response_time": "4.5 hours",
    "lead_score_average": 67
  },
  "recent_leads": [
    {
      "lead_id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Ahmed Al Mansouri",
      "phone": "+971501234567",
      "source": "bayut",
      "status": "qualified",
      "score": 85,
      "last_activity": "2026-02-15T14:30:00Z",
      "next_follow_up": "2026-02-16T10:00:00Z"
    }
  ],
  "pending_tasks": [
    {
      "task_id": "456e7890-e89b-12d3-a456-426614174003",
      "lead_name": "Fatima Hassan",
      "task_type": "call",
      "due_date": "2026-02-16T10:00:00Z",
      "priority": "high"
    }
  ],
  "performance_metrics": {
    "conversion_rate": 15.5,
    "average_deal_size": 1200000,
    "response_time_rank": 3
  }
}
```

**Error Responses:**

| Status | Description     |
| ------ | --------------- |
| `404`  | Agent not found |

---

### GET /api/v1/health

**What it does:** A simple health check. Returns `{"status": "ok"}` if the service is running.

**Response:**

```json
{
  "status": "ok"
}
```

---

## Analytics Endpoints

All analytics endpoints live under `/api/v1/analytics/` and return paginated results. Each response includes `data` (the current page), `total` (the full count of matching rows across all pages), `skip`, `limit`, and optionally `next_cursor` for keyset-based pagination.

### Lead Performance Analytics

| Endpoint                             | Description                                 |
| ------------------------------------ | ------------------------------------------- |
| `GET /analytics/conversion-rates`    | Lead conversion rates by source and agent   |
| `GET /analytics/avg-conversion-time` | Average time to conversion by property type |
| `GET /analytics/monthly-trends`      | Monthly lead volume trends                  |
| `GET /analytics/agent-rankings`      | Agent performance rankings (CTE-based)      |
| `GET /analytics/revenue-attribution` | Revenue attribution by lead source          |

### Lead Quality Analysis

| Endpoint                                  | Description                                             |
| ----------------------------------------- | ------------------------------------------------------- |
| `GET /analytics/high-score-not-converted` | High-scoring leads (>80) that didn't convert            |
| `GET /analytics/low-score-converted`      | Low-scoring leads (<50) that converted                  |
| `GET /analytics/source-quality`           | Source quality comparison over time (monthly avg score) |
| `GET /analytics/follow-up-timing`         | Optimal follow-up timing analysis (window functions)    |

### Agent Workload Optimization

| Endpoint                                           | Description                                             |
| -------------------------------------------------- | ------------------------------------------------------- |
| `GET /analytics/workload-distribution`             | Current workload distribution across agents             |
| `GET /analytics/approaching-capacity?threshold=40` | Agents approaching max capacity (default threshold: 40) |
| `GET /analytics/specialized-vs-general`            | Specialized vs general agent performance comparison     |
| `GET /analytics/response-time-correlation`         | Lead response time correlation with conversion rate     |

---

## Error Handling

All custom exceptions are caught by global exception handlers in `main.py` and return consistent JSON responses:

```json
{
  "detail": "Error description",
  "type": "error_type"
}
```

| Exception                         | HTTP Status | Type                           |
| --------------------------------- | ----------- | ------------------------------ |
| `LeadNotFoundError`               | 404         | `lead_not_found`               |
| `AgentNotFoundError`              | 404         | `agent_not_found`              |
| `AssignmentNotFoundError`         | 404         | `assignment_not_found`         |
| `NoAgentAssignedError`            | 422         | `no_agent_assigned`            |
| `DuplicateLeadError`              | 409         | `duplicate_lead`               |
| `AgentOverloadError`              | 503         | `agent_overload`               |
| `InvalidLeadDataError`            | 422         | `invalid_lead_data`            |
| `FollowUpConflictError`           | 409         | `follow_up_conflict`           |
| `InvalidStatusTransitionError`    | 400         | `invalid_status_transition`    |
| `PropertyServiceUnavailableError` | 503         | `property_service_unavailable` |
| `OverdueTaskError`                | 400         | `overdue_task`                 |
| `RequestValidationError`          | 422         | `validation_error`             |
