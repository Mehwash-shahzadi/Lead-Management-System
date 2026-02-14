# ThinkRealty Lead Management API

## Overview

The ThinkRealty Lead Management API provides a comprehensive RESTful interface for managing real estate leads in the UAE market. Built on FastAPI, the system offers automated lead scoring, intelligent agent assignment, and complete activity tracking capabilities. The API follows RESTful conventions and returns JSON responses with standardized error handling.

## Core Endpoints

### POST /api/v1/leads/capture

**Description:** Captures new leads from various sources including Bayut, PropertyFinder, company website, and walk-ins. The system automatically scores the lead, assigns it to the most suitable agent, and creates all necessary database records.

**Request Body:**

```json
{
  "source_type": "website",
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
    "utm_source": "google",
    "referrer_agent_id": null,
    "property_id": null
  }
}
```

**Success Response:**

```json
{
  "success": true,
  "lead_id": "123e4567-e89b-12d3-a456-426614174000",
  "score": 85,
  "assigned_agent": {
    "agent_id": "456e7890-e89b-12d3-a456-426614174001",
    "full_name": "Sara Al Hassan",
    "specialization": ["apartment", "Downtown Dubai"]
  },
  "message": "Lead captured and assigned successfully"
}
```

**Error Responses:**

- `400 Bad Request`: "Duplicate lead detected - same phone number from this source within 24 hours"
- `503 Service Unavailable`: "All agents have reached maximum capacity (50 leads)"
- `422 Unprocessable Entity`: "Invalid lead data - missing required fields"

### PUT /api/v1/leads/{lead_id}/update

**Description:** Updates an existing lead's status, adds new activities, records property interests, and manages follow-up tasks. This endpoint enforces status transition rules and automatically updates lead scores based on activity outcomes.

**Request Body:**

```json
{
  "status": "qualified",
  "activity": {
    "type": "call",
    "notes": "Client expressed strong interest in 2BR apartments in Marina area. Budget confirmed at 1.2M AED.",
    "outcome": "positive",
    "next_follow_up": "2026-02-12T14:00:00Z"
  },
  "property_interests": [
    {
      "property_id": "789e0123-e89b-12d3-a456-426614174002",
      "interest_level": "high"
    }
  ]
}
```

**Success Response:**

```json
{
  "success": true,
  "updated_fields": ["status", "activity", "property_interests"],
  "new_score": 92,
  "follow_up_created": true,
  "message": "Lead updated successfully"
}
```

**Error Responses:**

- `404 Not Found`: "Lead not found"
- `400 Bad Request`: "Invalid status transition from 'converted' to 'qualified'"
- `403 Forbidden`: "Agent has overdue follow-ups - complete existing tasks before adding new ones"

### GET /api/v1/agents/{agent_id}/dashboard

**Description:** Provides comprehensive agent performance data including active leads, conversion metrics, pending tasks, and recent activity summaries. Supports filtering by date ranges, lead status, and source types for detailed analysis.

**Query Parameters:**

- `date_range`: "7d", "30d", "90d", or "custom" (optional)
- `status_filter`: "all", "active", "converted", "lost" (optional)
- `source_filter`: "all", "bayut", "propertyFinder", "dubizzle", "website" (optional)

**Success Response:**

```json
{
  "agent_summary": {
    "total_active_leads": 23,
    "overdue_follow_ups": 2,
    "this_month_conversions": 4,
    "average_response_time": "2.3 hours",
    "lead_score_average": 78
  },
  "recent_leads": [
    {
      "lead_id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Ahmed Al Mansouri",
      "status": "qualified",
      "score": 85,
      "source": "website",
      "created_at": "2026-02-08T10:30:00Z",
      "last_activity": "2026-02-08T16:45:00Z"
    }
  ],
  "pending_tasks": [
    {
      "task_id": "456e7890-e89b-12d3-a456-426614174003",
      "lead_name": "Fatima Al Zahra",
      "type": "call",
      "due_date": "2026-02-09T11:00:00Z",
      "priority": "high",
      "overdue": false
    }
  ],
  "performance_metrics": {
    "conversion_rate": 18.5,
    "average_days_to_conversion": 12.4,
    "response_time_compliance": 94.2
  }
}
```

**Error Responses:**

- `404 Not Found`: "Agent not found"
- `422 Unprocessable Entity`: "Invalid date range or filter parameters"
