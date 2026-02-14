# ThinkRealty Business Rules

## Introduction

The ThinkRealty Lead Management System implements sophisticated business rules designed specifically for the UAE real estate market. These rules ensure data quality, optimize agent productivity, maintain client service standards, and prevent system overload. The rules are enforced through a combination of database constraints, application logic, and automated triggers to guarantee consistent system behavior.

## Core Business Rules

### Duplicate Lead Detection

The system prevents duplicate lead entries by monitoring phone numbers and source combinations within 24-hour windows. When a new lead is captured, the system checks if the same phone number has already been registered from the same source (Bayut, PropertyFinder, website, etc.) in the past 24 hours and rejects the submission with a clear error message. This rule is enforced through a unique database constraint and validated during the capture process to maintain data integrity and prevent agent confusion.

### Intelligent Agent Assignment

New leads are automatically assigned to the most suitable agent based on a sophisticated matching algorithm that considers property type specialization, geographic area expertise, and language skills. The system calculates a match score for each available agent by awarding points for property type alignment, preferred area overlap, and language compatibility, then assigns the lead to the highest-scoring agent with the lowest current workload. This rule is implemented through the LeadAssignmentManager service and ensures optimal lead distribution.

### Dynamic Lead Scoring

Every lead receives an automated quality score between 0 and 100 based on multiple factors including budget range, source quality, client nationality, and property preferences. High-budget leads from premium sources like Bayut or direct referrals receive maximum points, while UAE nationals and GCC citizens get additional scoring bonuses reflecting their market significance. The scoring engine recalculates scores after significant activities, allowing the system to adapt to changing lead quality throughout the sales process.

### Status Transition Control

Lead status changes must follow a logical progression from new → contacted → qualified → viewing_scheduled → negotiation → converted/lost, preventing agents from skipping critical sales stages. The system validates each status change request and rejects invalid transitions, such as moving directly from "new" to "negotiation" without proper qualification steps. These transitions are enforced through database check constraints and application-level validation to maintain process integrity.

### Agent Workload Limits

Each agent is restricted to a maximum of 50 active leads to ensure quality service and prevent agent burnout. When the system attempts to assign a new lead, it first verifies that the target agent has available capacity and blocks the assignment if they have reached their limit. The active lead count is automatically updated when leads are assigned, converted, or marked as lost, maintaining accurate real-time workload tracking through database triggers.

### Follow-up Compliance Management

Agents with overdue follow-up tasks cannot receive new lead assignments until their outstanding obligations are completed, ensuring existing clients receive proper attention before new prospects are added. The system automatically marks tasks as overdue when their due dates pass and blocks new assignments for non-compliant agents. This rule is enforced through the task management service and promotes consistent client follow-up standards across the organization.

## Enforcement Mechanisms

These business rules are implemented through multiple layers of protection including database constraints that provide foundational data integrity, application-level services that handle complex logic and decision-making, and automated triggers that maintain real-time data consistency. The dual-layer approach ensures rules cannot be bypassed through direct database access while providing clear feedback to users when rule violations are attempted. Critical constraints like agent capacity limits and duplicate prevention are enforced at both the database and application levels for maximum reliability.
