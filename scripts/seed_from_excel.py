"""
scripts/seed_from_excel.py

Завантажує дані з Excel файлу в базу даних.
ОДИН РАЗ виконується для наповнення БД.
"""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.optimization.excel_oasis_loader import load_oasis_exterior_excel
from app.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from app.domain.aggregates import Technician, ServiceSite, ServiceRequest
from app.domain.value_objects import (
    Location, Skill, SkillLevel, WorkingHours, DayOfWeek,
    TimeWindow, VisitFrequency, TechnicianCapabilities
)


async def seed_technicians_from_excel(excel_path: str):
    """Наповнити БД техніками з Excel."""
    sites, techs = load_oasis_exterior_excel(excel_path)

    async with SqlAlchemyUnitOfWork(async_session_factory) as uow:
        print(f"📊 Loaded {len(techs)} technicians from Excel")

        for oasis_tech in techs:
            # Parse skills
            skills = frozenset(
                Skill(
                    skill_type=s.split('-')[0].strip() if '-' in s else s.strip(),
                    level=SkillLevel.SENIOR  # Default
                )
                for s in oasis_tech.skills
            )

            # Home location (fake if not provided)
            home_location = Location(
                latitude=Decimal("40.7128"),  # NYC fake
                longitude=Decimal("-74.0060")
            )

            # Office location (fake if not provided)
            office_location = Location(
                latitude=Decimal("40.7580"),
                longitude=Decimal("-73.9855")
            )

            # Working hours (fake - Mon-Fri 9-17)
            working_hours = {
                DayOfWeek.MONDAY: WorkingHours(start_minutes=540, end_minutes=1020),
                DayOfWeek.TUESDAY: WorkingHours(start_minutes=540, end_minutes=1020),
                DayOfWeek.WEDNESDAY: WorkingHours(start_minutes=540, end_minutes=1020),
                DayOfWeek.THURSDAY: WorkingHours(start_minutes=540, end_minutes=1020),
                DayOfWeek.FRIDAY: WorkingHours(start_minutes=540, end_minutes=1020),
            }

            # Capabilities
            capabilities = TechnicianCapabilities(
                can_work_at_heights=oasis_tech.can_heights,
                can_use_lift=oasis_tech.can_lift,
                can_apply_pesticides=oasis_tech.can_pesticides,
                is_citizen=oasis_tech.is_citizen,
                is_physically_demanding=oasis_tech.can_phys,
            )

            # Create Domain Technician
            tech = Technician(
                name=oasis_tech.name,
                home_location=home_location,
                office_location=office_location,
                skills=skills,
                working_hours=working_hours,
                capabilities=capabilities,
            )

            await uow.technicians.add(tech)
            print(f"  ✅ Added: {tech.name}")

        await uow.commit()
        print(f"🎉 Successfully added {len(techs)} technicians!")


async def seed_service_sites_from_excel(excel_path: str):
    """Наповнити БД сервісними сайтами з Excel."""
    sites, _ = load_oasis_exterior_excel(excel_path)

    async with SqlAlchemyUnitOfWork(async_session_factory) as uow:
        print(f"📊 Loaded {len(sites)} service sites from Excel")

        for oasis_site in sites:
            # Location (fake if not provided)
            location = Location(
                latitude=Decimal("40.7128"),
                longitude=Decimal("-74.0060")
            )

            # Required skill
            required_skill = None
            if oasis_site.skill_requirement:
                required_skill = Skill(
                    skill_type=oasis_site.skill_requirement.split('-')[0].strip(),
                    level=SkillLevel.JUNIOR
                )

            # Time windows (fake - Mon-Fri 8-18)
            time_windows = {
                DayOfWeek.MONDAY: TimeWindow(start_minutes=480, end_minutes=1080),
                DayOfWeek.TUESDAY: TimeWindow(start_minutes=480, end_minutes=1080),
                DayOfWeek.WEDNESDAY: TimeWindow(start_minutes=480, end_minutes=1080),
                DayOfWeek.THURSDAY: TimeWindow(start_minutes=480, end_minutes=1080),
                DayOfWeek.FRIDAY: TimeWindow(start_minutes=480, end_minutes=1080),
            }

            # Visit frequency
            freq_map = {
                1: VisitFrequency.WEEKLY,
                2: VisitFrequency.TWICE_WEEKLY,
                3: VisitFrequency.THREE_TIMES_WEEKLY,
                5: VisitFrequency.DAILY,
            }
            visit_frequency = freq_map.get(oasis_site.visit_frequency, VisitFrequency.WEEKLY)

            # Create Domain ServiceSite
            site = ServiceSite(
                site_code=oasis_site.location_name[:50],  # Max 50 chars
                location=location,
                required_skill=required_skill,
                time_windows=time_windows,
                visit_frequency=visit_frequency,
                service_duration_minutes=oasis_site.duration_min or 60,
                requires_permit=False,  # Default
                requires_multiple_technicians=oasis_site.techs_needed > 1,
            )

            await uow.service_sites.add(site)
            print(f"  ✅ Added: {site.site_code}")

        await uow.commit()
        print(f"🎉 Successfully added {len(sites)} service sites!")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("🌱 SEED DATABASE FROM EXCEL")
    print("=" * 60)

    # Path to Excel file
    excel_path = "data/Routing_pilot_data_input__Oasis__-_exterior_only_-_FINAL.xlsx"

    if not Path(excel_path).exists():
        print(f"❌ Excel file not found: {excel_path}")
        print("   Copy the file to data/ folder first!")
        sys.exit(1)

    try:
        # Seed technicians
        print("\n1️⃣ Seeding Technicians...")
        await seed_technicians_from_excel(excel_path)

        # Seed service sites
        print("\n2️⃣ Seeding Service Sites...")
        await seed_service_sites_from_excel(excel_path)

        print("\n" + "=" * 60)
        print("✅ DATABASE SEEDED SUCCESSFULLY!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Start API: uvicorn app.entrypoints.api.main:app --reload")
        print("2. Open: http://localhost:8000/docs")
        print("3. Try: POST /api/v1/optimize")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())