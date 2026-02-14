# ThinkRealty Database Schema

## Overview

The ThinkRealty database is built on PostgreSQL and consists of 10 interconnected tables designed specifically for UAE real estate lead management. The schema enforces data integrity through foreign keys, unique constraints, and check constraints while supporting complex business rules like agent workload limits, status progression validation, and duplicate prevention. All tables use UUID primary keys and include timestamp tracking for audit purposes.

## Core Tables

### leads

**Purpose:** Central table storing all lead information and contact details

**Key Columns:**

- `lead_id` (UUID, Primary Key) - Unique identifier generated automatically
- `source_type` (VARCHAR(50), NOT NULL) - Lead origin: bayut, propertyFinder, dubizzle, website, walk_in, referral
- `first_name`, `last_name` (VARCHAR(100), NOT NULL) - Contact information
- `email` (VARCHAR(255)) - Optional email address
- `phone` (VARCHAR(20), NOT NULL) - Primary contact number
- `nationality` (VARCHAR(50)) - Client nationality for scoring
- `language_preference` (VARCHAR(20)) - arabic or english
- `budget_min`, `budget_max` (NUMERIC(15,2)) - Price range in AED
- `property_type` (VARCHAR(50)) - apartment, villa, townhouse, commercial
- `preferred_areas` (TEXT[]) - Array of location preferences
- `status` (VARCHAR(50), NOT NULL, DEFAULT 'new') - Current lead status
- `score` (INTEGER, NOT NULL, DEFAULT 0) - Calculated lead quality score 0-100
- `created_at`, `updated_at` (TIMESTAMP WITH TIME ZONE) - Audit timestamps

**Constraints:**

- Unique phone+source_type combination prevents duplicates within 24 hours
- Score must be between 0-100
- Status limited to: new, contacted, qualified, viewing_scheduled, negotiation, converted, lost

### agents

**Purpose:** Stores real estate agent profiles and specialization information

**Key Columns:**

- `agent_id` (UUID, Primary Key) - Unique agent identifier
- `full_name` (VARCHAR(200), NOT NULL) - Agent's complete name
- `email` (VARCHAR(255), UNIQUE, NOT NULL) - Contact email
- `phone` (VARCHAR(20), UNIQUE, NOT NULL) - Contact phone
- `specialization_property_type` (TEXT[]) - Array of property types agent handles
- `specialization_areas` (TEXT[]) - Array of geographic specializations
- `language_skills` (TEXT[]) - Supported languages for client communication
- `active_leads_count` (INTEGER, NOT NULL, DEFAULT 0) - Current workload

**Constraints:**

- Maximum 50 active leads per agent enforced by check constraint
- Active leads count cannot be negative

### lead_assignments

**Purpose:** Tracks which agent is responsible for each lead

**Key Columns:**

- `assignment_id` (UUID, Primary Key) - Unique assignment record
- `lead_id` (UUID, Foreign Key to leads, NOT NULL) - References the assigned lead
- `agent_id` (UUID, Foreign Key to agents, NOT NULL) - References the assigned agent
- `assigned_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW()) - Initial assignment time
- `reassigned_at` (TIMESTAMP WITH TIME ZONE) - If lead was reassigned
- `reason` (TEXT) - Explanation for reassignment

**Relationships:** One-to-one with leads (each lead has exactly one active assignment)
**Constraints:** Unique constraint ensures one assignment per lead

### lead_activities

**Purpose:** Records all interactions and communications with leads

**Key Columns:**

- `activity_id` (UUID, Primary Key) - Unique activity identifier
- `lead_id` (UUID, Foreign Key to leads, NOT NULL) - Associated lead
- `agent_id` (UUID, Foreign Key to agents, NOT NULL) - Agent who performed activity
- `type` (VARCHAR(50), NOT NULL) - Activity type: call, email, whatsapp, viewing, meeting, offer_made
- `notes` (TEXT) - Detailed activity description
- `outcome` (VARCHAR(20)) - Result: positive, negative, neutral, or null
- `activity_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW()) - When activity occurred

**Relationships:** Many-to-one with both leads and agents
**Business Logic:** Used for lead scoring updates and follow-up scheduling

### follow_up_tasks

**Purpose:** Manages scheduled follow-up activities and deadlines

**Key Columns:**

- `task_id` (UUID, Primary Key) - Unique task identifier
- `lead_id` (UUID, Foreign Key to leads, NOT NULL) - Related lead
- `agent_id` (UUID, Foreign Key to agents, NOT NULL) - Responsible agent
- `type` (VARCHAR(50), NOT NULL) - Task type: call, email, whatsapp, viewing
- `due_date` (TIMESTAMP WITH TIME ZONE, NOT NULL) - Deadline for completion
- `priority` (VARCHAR(20), NOT NULL, DEFAULT 'medium') - high, medium, or low
- `status` (VARCHAR(20), NOT NULL, DEFAULT 'pending') - pending, completed, or overdue
- `created_at`, `updated_at` (TIMESTAMP WITH TIME ZONE) - Audit timestamps

**Business Logic:** Automatically marked overdue when due_date passes; blocks new lead assignments for agents with overdue tasks

### lead_property_interests

**Purpose:** Tracks specific properties that leads have shown interest in

**Key Columns:**

- `interest_id` (UUID, Primary Key) - Unique interest record
- `lead_id` (UUID, Foreign Key to leads, NOT NULL) - Lead expressing interest
- `property_id` (UUID, NOT NULL) - External property system identifier
- `interest_level` (VARCHAR(20), NOT NULL) - high, medium, or low
- `created_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW()) - When interest was recorded

**Relationships:** Many-to-one with leads (leads can be interested in multiple properties)

### lead_sources

**Purpose:** Detailed source attribution and campaign tracking

**Key Columns:**

- `source_id` (UUID, Primary Key) - Unique source record
- `lead_id` (UUID, Foreign Key to leads, NOT NULL) - Associated lead
- `campaign_id` (VARCHAR(100)) - Marketing campaign identifier
- `utm_source` (VARCHAR(100)) - Traffic source tracking
- `referrer_agent_id` (UUID, Foreign Key to agents) - If referred by another agent
- `property_id` (UUID) - If lead came from specific property inquiry

**Purpose:** Enables detailed marketing attribution and agent referral tracking

### lead_conversion_history

**Purpose:** Records successful lead conversions and deal details

**Key Columns:**

- `conversion_id` (UUID, Primary Key) - Unique conversion record
- `lead_id` (UUID, Foreign Key to leads, NOT NULL) - Converted lead
- `agent_id` (UUID, Foreign Key to agents, NOT NULL) - Converting agent
- `property_id` (UUID) - Final property purchased/rented
- `deal_value` (NUMERIC(15,2)) - Transaction amount in AED
- `conversion_type` (VARCHAR(20)) - sale or rental
- `converted_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW()) - Conversion date

**Business Logic:** Used for agent performance metrics and commission calculations

### agent_performance_metrics

**Purpose:** Aggregated statistics for agent evaluation

**Key Columns:**

- `metric_id` (UUID, Primary Key) - Unique metric record
- `agent_id` (UUID, Foreign Key to agents, NOT NULL) - Evaluated agent
- `period_start`, `period_end` (DATE, NOT NULL) - Measurement period
- `leads_received` (INTEGER) - Total leads assigned
- `conversions` (INTEGER) - Successful conversions
- `total_deal_value` (NUMERIC(15,2)) - Sum of all deals
- `average_response_time` (INTERVAL) - Mean time to first contact
- `calculated_at` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW()) - Metric calculation time

### scoring_rules

**Purpose:** Configurable lead scoring parameters

**Key Columns:**

- `rule_id` (UUID, Primary Key) - Unique rule identifier
- `rule_name` (VARCHAR(100), NOT NULL) - Descriptive rule name
- `category` (VARCHAR(50), NOT NULL) - budget, source, nationality, property_type
- `condition_value` (TEXT, NOT NULL) - Matching criteria
- `score_points` (INTEGER, NOT NULL) - Points awarded when matched
- `active` (BOOLEAN, DEFAULT TRUE) - Whether rule is currently applied

**Business Logic:** Enables dynamic lead scoring without code changes

## Enforced Business Rules

The database schema enforces several critical business rules through constraints and relationships:

**Duplicate Prevention:** Unique constraint on phone+source_type prevents duplicate leads from the same source within 24 hours

**Agent Workload Management:** Check constraint limits agents to maximum 50 active leads; triggers update agent counters automatically

**Status Progression Control:** Check constraints ensure leads follow proper status transitions and cannot skip required stages

**Follow-up Compliance:** Foreign key relationships and status checks prevent new lead assignments to agents with overdue follow-up tasks
