import argparse
import asyncio
import sys
from datetime import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.optimization.excel_oasis_loader import DAY_CAP, WEEKDAYS, load_oasis_exterior_excel
from app.adapters.orm import OptimizationTask, Route, RouteStop, ServiceSite, ServiceTimeWindow, Technician
from app.adapters.orm.base import DayOfWeek, StartPoint, TaskStatus, TransportMode, VisitFrequency
from app.service_layer.unit_of_work import DEFAULT_SESSION_FACTORY


def minutes_to_time(value: int | None) -> time | None:
    if value is None:
        return None
    hours = value // 60
    minutes = value % 60
    return time(hour=hours, minute=minutes)


def map_visit_frequency(freq: int) -> VisitFrequency:
    if freq <= 1:
        return VisitFrequency.X1
    if freq == 2:
        return VisitFrequency.X2
    if freq == 3:
        return VisitFrequency.X3
    if freq == 4:
        return VisitFrequency.X4
    return VisitFrequency.X5


def map_day_of_week(day_key: str) -> DayOfWeek:
    mapping = {
        "mon": DayOfWeek.MONDAY,
        "tue": DayOfWeek.TUESDAY,
        "wed": DayOfWeek.WEDNESDAY,
        "thu": DayOfWeek.THURSDAY,
        "fri": DayOfWeek.FRIDAY,
        "sat": DayOfWeek.SATURDAY,
        "sun": DayOfWeek.SUNDAY,
    }
    return mapping[day_key]


async def truncate_tables(session) -> None:
    await session.execute(delete(RouteStop))
    await session.execute(delete(Route))
    await session.execute(delete(ServiceTimeWindow))
    await session.execute(delete(ServiceSite))
    await session.execute(delete(Technician))
    await session.execute(delete(OptimizationTask).where(OptimizationTask.status != TaskStatus.PROCESSING))


async def seed_from_excel(excel_path: Path, truncate: bool, dry_run: bool) -> None:
    sites, techs = load_oasis_exterior_excel(str(excel_path))

    print(f"Loaded from Excel: technicians={len(techs)}, service_sites={len(sites)}")

    if dry_run:
        print("Dry run mode: no changes will be written to database")
        return

    async with DEFAULT_SESSION_FACTORY() as session:
        if truncate:
            await truncate_tables(session)
            print("Existing data was truncated")

        for row in techs:
            technician = Technician(
                id=uuid4(),
                name=row.name,
                office_address=row.office_address,
                starts_from=StartPoint.OFFICE,
                finishes_at=StartPoint.OFFICE,
                transport_mode=TransportMode.CAR_VAN,
                monday_start=minutes_to_time(row.shift_from.get("mon")),
                monday_end=minutes_to_time(row.shift_to.get("mon")),
                tuesday_start=minutes_to_time(row.shift_from.get("tue")),
                tuesday_end=minutes_to_time(row.shift_to.get("tue")),
                wednesday_start=minutes_to_time(row.shift_from.get("wed")),
                wednesday_end=minutes_to_time(row.shift_to.get("wed")),
                thursday_start=minutes_to_time(row.shift_from.get("thu")),
                thursday_end=minutes_to_time(row.shift_to.get("thu")),
                friday_start=minutes_to_time(row.shift_from.get("fri")),
                friday_end=minutes_to_time(row.shift_to.get("fri")),
                saturday_start=minutes_to_time(row.shift_from.get("sat")),
                saturday_end=minutes_to_time(row.shift_to.get("sat")),
                sunday_start=minutes_to_time(row.shift_from.get("sun")),
                sunday_end=minutes_to_time(row.shift_to.get("sun")),
                max_hours_per_day=row.max_hours_day,
                max_hours_per_week=row.max_hours_week,
                break_duration_minutes=row.min_break_min,
                break_earliest_start=minutes_to_time(row.break_not_earlier),
                break_latest_start=minutes_to_time(row.break_not_later),
                can_do_physically_demanding=row.can_phys,
                comfortable_with_heights=row.can_heights,
                certified_with_lift=row.can_lift,
                has_pesticide_certification=row.can_pesticides,
                is_citizen=row.is_citizen,
                is_active=True,
            )
            session.add(technician)

        for idx, row in enumerate(sites, start=1):
            service_site = ServiceSite(
                id=uuid4(),
                site_code=f"SITE-{idx:04d}",
                site_name=row.location_name,
                address=row.address,
                duration_minutes=max(1, row.duration_min or 60),
                visit_frequency=map_visit_frequency(row.visit_frequency),
                is_physically_demanding=row.physically_demanding,
                requires_work_at_heights=row.work_at_heights,
                requires_lift_usage=row.requires_lift,
                requires_pesticide_application=row.requires_pesticides,
                requires_citizen_technician=row.requires_citizen,
                requires_permit=False,
            )

            for day_key in WEEKDAYS:
                tw_from = row.tw_from.get(day_key)
                tw_to = row.tw_to.get(day_key)
                if tw_from is None or tw_to is None:
                    continue
                start_time = minutes_to_time(tw_from)
                end_time = minutes_to_time(tw_to)
                if start_time is None or end_time is None or start_time >= end_time:
                    continue
                service_site.time_windows.append(
                    ServiceTimeWindow(
                        id=uuid4(),
                        day_of_week=map_day_of_week(day_key),
                        start_time=start_time,
                        end_time=end_time,
                    )
                )

            session.add(service_site)

        await session.commit()

    print("Seed completed successfully")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed PostgreSQL from OASIS Excel")
    parser.add_argument(
        "--excel",
        type=Path,
        default=Path("data/Routing_pilot_data_input_FINAL.xlsx"),
        help="Path to Excel file",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing entities before seed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input without writing to DB",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if not args.excel.exists():
        raise FileNotFoundError(f"Excel file not found: {args.excel}")

    await seed_from_excel(args.excel, truncate=args.truncate, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
