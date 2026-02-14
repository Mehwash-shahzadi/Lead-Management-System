"""Day 1 compliant sample data seeder — strict PDF match"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text

from app.config import settings
from app.models import (
    Base,
    Lead,
    Agent,
    LeadAssignment,
    LeadActivity,
    FollowUpTask,
    LeadPropertyInterest,
    LeadSource,
    LeadConversionHistory,
)


SOURCE_TYPES = ["bayut", "propertyFinder", "dubizzle", "website", "walk_in", "referral"]
STATUS_VALUES = ["new", "contacted", "qualified", "viewing_scheduled", "negotiation", "converted", "lost"]
ACTIVITY_TYPES = ["call", "email", "whatsapp", "viewing", "meeting", "offer_made"]
OUTCOMES = ["positive", "negative", "neutral"]
TASK_TYPES = ["call", "email", "whatsapp", "viewing"]
PRIORITIES = ["high", "medium", "low"]


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        print("Seeding Day 1 sample data (PDF compliant)")

        # Clear existing data to allow re-running the seed
        await session.execute(text("DELETE FROM lead_conversion_history"))
        await session.execute(text("DELETE FROM lead_property_interests"))
        await session.execute(text("DELETE FROM follow_up_tasks"))
        await session.execute(text("DELETE FROM lead_activities"))
        await session.execute(text("DELETE FROM lead_assignments"))
        await session.execute(text("DELETE FROM lead_sources"))
        await session.execute(text("DELETE FROM leads"))
        await session.execute(text("DELETE FROM agents"))
        await session.commit()
        print("Cleared existing data")

        # 1. Agents (10+ with different specializations)
        agents = []
        specs = [
            (["apartment", "villa"], ["Downtown Dubai", "Marina"], ["arabic", "english"]),
            (["villa", "townhouse"], ["Palm Jumeirah"], ["arabic", "english"]),
            (["commercial"], ["Business Bay"], ["english"]),
            (["apartment"], ["JBR", "Downtown Dubai"], ["arabic", "french"]),
            (["villa"], ["Arabian Ranches"], ["arabic", "english", "hindi"]),
            (["apartment", "townhouse"], ["Dubai Hills Estate"], ["arabic", "english"]),
            (["commercial", "villa"], ["Downtown Dubai"], ["arabic", "english"]),
            (["apartment"], ["Marina", "JBR"], ["arabic", "english", "french"]),
            (["villa"], ["Palm Jumeirah"], ["arabic", "english"]),
            (["apartment", "townhouse"], ["The Greens"], ["english"]),
        ]
        for i, (ptypes, areas, langs) in enumerate(specs, 1):
            agent = Agent(
                full_name=f"Agent {i} Example",
                email=f"agent{i}@thinkrealty.ae",
                phone=f"+9715012345{i:02d}",
                specialization_property_type=ptypes,
                specialization_areas=areas,
                language_skills=langs,
                active_leads_count=0,
            )
            session.add(agent)
            agents.append(agent)
        await session.flush()
        print(f"Created {len(agents)} agents")

        # 2. Lead sources — per-lead table, create empty placeholders first
        # (real sources attached per lead below)
        print("LeadSource table ready (populated per lead)")

        # 3. Leads — 120 with variety
        leads = []
        nationalities = ["UAE", "Saudi Arabia", "India", "Pakistan", "Egypt", "UK"]
        languages = ["arabic", "english"]
        budgets_min = [300000, 500000, 800000, 1200000, 2000000]
        property_types = ["apartment", "villa", "townhouse", "commercial"]
        areas_lists = [
            ["Downtown Dubai", "Marina"],
            ["JBR", "Palm Jumeirah"],
            ["Business Bay", "Dubai Hills Estate"],
        ]

        for i in range(120):
            lead = Lead(
                source_type=SOURCE_TYPES[i % len(SOURCE_TYPES)],
                first_name=["Ahmed", "Fatima", "Mohammed", "Layla", "Hassan"][i % 5],
                last_name=["Al Mansoori", "Khan", "Al Naqbi", "Patel", "Smith"][i % 5],
                email=f"lead{i}@example.com",
                phone=f"+97150{i%10}{500000 + i:06d}",
                nationality=nationalities[i % len(nationalities)],
                language_preference=languages[i % 2],
                budget_min=Decimal(budgets_min[i % len(budgets_min)]),
                budget_max=Decimal(budgets_min[i % len(budgets_min)] + 400000 + (i % 8) * 100000),
                property_type=property_types[i % len(property_types)],
                preferred_areas=areas_lists[i % len(areas_lists)],
                status=STATUS_VALUES[i % len(STATUS_VALUES)],
                score=30 + (i % 71),
            )
            session.add(lead)
            leads.append(lead)
        await session.flush()
        print(f"Created {len(leads)} leads")

        # 4. Assign EVERY lead (mandatory rule)
        assignments = []
        for i, lead in enumerate(leads):
            agent = agents[i % len(agents)]
            ass = LeadAssignment(
                lead_id=lead.lead_id,
                agent_id=agent.agent_id,
                assigned_at=datetime.now(timezone.utc) - timedelta(days=90 - (i % 90)),
            )
            session.add(ass)
            assignments.append(ass)
        await session.flush()
        print(f"Created {len(assignments)} assignments (all leads assigned)")

        # 5. Lead activities ≥50
        activities = []
        for i in range(70):
            lead = leads[i % len(leads)]
            agent = agents[i % len(agents)]
            act = LeadActivity(
                lead_id=lead.lead_id,
                agent_id=agent.agent_id,
                type=ACTIVITY_TYPES[i % len(ACTIVITY_TYPES)],
                notes=f"Activity {i+1}",
                outcome=OUTCOMES[i % len(OUTCOMES)],
                activity_at=datetime.now(timezone.utc) - timedelta(days=45 - (i % 45)),
            )
            session.add(act)
            activities.append(act)
        await session.flush()
        print(f"Created {len(activities)} activities")

        # 6. Follow-up tasks ≥50 (combined with activities meets "50+ activities and follow-ups")
        tasks = []
        for i in range(60):
            lead = leads[i % len(leads)]
            agent = agents[i % len(agents)]
            task = FollowUpTask(
                lead_id=lead.lead_id,
                agent_id=agent.agent_id,
                type=TASK_TYPES[i % len(TASK_TYPES)],
                due_date=datetime.now(timezone.utc) + timedelta(days=(i % 20) - 10),
                priority=PRIORITIES[i % len(PRIORITIES)],
            )
            session.add(task)
            tasks.append(task)
        await session.flush()
        print(f"Created {len(tasks)} follow-up tasks")

        # 7. Property interests ≥20
        interests = []
        for i in range(30):
            lead = leads[i % len(leads)]
            interest = LeadPropertyInterest(
                lead_id=lead.lead_id,
                property_id=uuid4(),
                interest_level=["high", "medium", "low"][i % 3],
            )
            session.add(interest)
            interests.append(interest)
        await session.flush()
        print(f"Created {len(interests)} property interests")

        # 8. Conversion history — various outcomes
        history = []
        for i in range(40):
            lead = leads[i % len(leads)]
            hist = LeadConversionHistory(
                lead_id=lead.lead_id,
                status_from="new",
                status_to=lead.status,
                changed_at=datetime.now(timezone.utc) - timedelta(days=60 - (i % 60)),
                agent_id=agents[i % len(agents)].agent_id,
            )
            session.add(hist)
            history.append(hist)
        await session.flush()
        print(f"Created {len(history)} conversion history records")

        # 9. Attach per-lead sources
        for i, lead in enumerate(leads):
            src = LeadSource(
                lead_id=lead.lead_id,
                source_type=lead.source_type,
                campaign_id=f"camp_{lead.source_type}_{i%5}",
                utm_source=f"utm_{lead.source_type}",
            )
            session.add(src)
        await session.flush()
        print("Attached per-lead sources")

        await session.commit()

        # Validation
        lead_cnt = (await session.execute(select(Lead))).scalars().all().__len__()
        ass_cnt = (await session.execute(select(LeadAssignment))).scalars().all().__len__()
        unassigned = lead_cnt - ass_cnt

        print("\nValidation:")
        print(f"  Leads: {lead_cnt}")
        print(f"  Assignments: {ass_cnt}")
        print(f"  Unassigned: {unassigned}")
        print("Seeding complete — compliant with PDF Day 1 sample requirements")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())