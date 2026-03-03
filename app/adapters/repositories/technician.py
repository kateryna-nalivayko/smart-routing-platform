"""
adapters/repositories/technician.py

Technician repository implementation using SQLAlchemy.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.orm import Technician as TechnicianORM
from app.adapters.ports import AbstractTechnicianRepository
from app.domain.aggregates import Technician


class SqlAlchemyTechnicianRepository(AbstractTechnicianRepository):
    """SQLAlchemy implementation of Technician repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, tech_id: UUID) -> Technician | None:
        """Get technician by ID."""
        result = await self.session.execute(
            select(TechnicianORM).where(TechnicianORM.id == tech_id)
        )
        orm_tech = result.scalar_one_or_none()

        if not orm_tech:
            return None

        return self._to_domain(orm_tech)

    async def get_by_ids(self, ids: list[UUID]) -> list[Technician]:
        """Get multiple technicians by IDs."""
        result = await self.session.execute(
            select(TechnicianORM).where(TechnicianORM.id.in_(ids))
        )
        orm_techs = result.scalars().all()

        return [self._to_domain(t) for t in orm_techs]

    async def get_active(self) -> list[Technician]:
        """Get all active technicians."""
        result = await self.session.execute(
            select(TechnicianORM).where(TechnicianORM.is_active)
        )
        orm_techs = result.scalars().all()

        return [self._to_domain(t) for t in orm_techs]

    async def add(self, technician: Technician) -> None:
        """Add new technician."""
        orm_tech = self._to_orm(technician)
        self.session.add(orm_tech)

    def _to_domain(self, orm_tech: TechnicianORM) -> Technician:
        """
        Convert ORM model to domain aggregate.

        Це ключовий метод Repository Pattern!
        Перетворює database record → domain object.
        """
        from app.domain.aggregates import TechnicianCapabilities
        from app.domain.value_objects import (
            Location,
            Skill,
            SkillLevel,
            SkillType,
            StartEndPoint,
            TimeWindow,
            TransportMode,
        )

        # Skills (ORM list → Domain frozenset)
        skills = frozenset([
            Skill(
                service_type=SkillType(s.service_type),
                level=SkillLevel(s.skill_level)
            )
            for s in (orm_tech.skills or [])
        ])

        # Locations
        home_location = Location(
            latitude=orm_tech.home_latitude,
            longitude=orm_tech.home_longitude
        ) if orm_tech.home_latitude and orm_tech.home_longitude else None

        office_location = Location(
            latitude=orm_tech.office_latitude,
            longitude=orm_tech.office_longitude
        ) if orm_tech.office_latitude and orm_tech.office_longitude else None

        # Capabilities
        capabilities = TechnicianCapabilities(
            physically_demanding=orm_tech.is_physically_demanding or False,
            living_walls=orm_tech.has_living_walls or False,
            heights=orm_tech.can_work_at_heights or False,
            lift=orm_tech.can_use_lift or False,
            pesticides=orm_tech.can_apply_pesticides or False,
            citizenship=orm_tech.is_citizen or False
        )

        # Working hours (ORM list → Domain dict)
        working_hours = {}
        if orm_tech.working_hours:
            from app.domain.value_objects import DayOfWeek
            for wh in orm_tech.working_hours:
                working_hours[DayOfWeek(wh.day_of_week)] = TimeWindow(
                    start=wh.start_time,
                    end=wh.end_time
                )

        # Create domain Technician
        return Technician(
            id=orm_tech.id,
            name=orm_tech.name,
            skills=skills,
            home_location=home_location,
            office_location=office_location,
            starts_from=StartEndPoint(orm_tech.starts_from) if orm_tech.starts_from else StartEndPoint.HOME,
            finishes_at=StartEndPoint(orm_tech.finishes_at) if orm_tech.finishes_at else StartEndPoint.HOME,
            transport_mode=TransportMode(orm_tech.transport_mode) if orm_tech.transport_mode else TransportMode.CAR_VAN,
            capabilities=capabilities,
            working_hours=working_hours,
            max_hours_per_day=orm_tech.max_hours_per_day or 8,
            max_hours_per_week=orm_tech.max_hours_per_week or 40,
            break_duration_minutes=orm_tech.break_duration_minutes,
            break_time_window=TimeWindow(
                start=orm_tech.break_start_time,
                end=orm_tech.break_end_time
            ) if orm_tech.break_start_time and orm_tech.break_end_time else None,
            is_active=orm_tech.is_active if hasattr(orm_tech, 'is_active') else True
        )

    def _to_orm(self, technician: Technician) -> TechnicianORM:
        """
        Convert domain aggregate to ORM model.

        Зворотня операція до _to_domain().
        Перетворює domain object → database record.
        """
        return TechnicianORM(
            id=technician.id,
            name=technician.name,

            # Location (Domain Location → ORM columns)
            home_latitude=technician.home_location.latitude if technician.home_location else None,
            home_longitude=technician.home_location.longitude if technician.home_location else None,
            office_latitude=technician.office_location.latitude if technician.office_location else None,
            office_longitude=technician.office_location.longitude if technician.office_location else None,

            # Transport
            starts_from=technician.starts_from.value if technician.starts_from else None,
            finishes_at=technician.finishes_at.value if technician.finishes_at else None,
            transport_mode=technician.transport_mode.value if technician.transport_mode else None,

            # Capabilities (Domain TechnicianCapabilities → ORM columns)
            is_physically_demanding=technician.capabilities.physically_demanding,
            has_living_walls=technician.capabilities.living_walls,
            can_work_at_heights=technician.capabilities.heights,
            can_use_lift=technician.capabilities.lift,
            can_apply_pesticides=technician.capabilities.pesticides,
            is_citizen=technician.capabilities.citizenship,

            # Working hours
            max_hours_per_day=technician.max_hours_per_day,
            max_hours_per_week=technician.max_hours_per_week,

            # Break
            break_duration_minutes=technician.break_duration_minutes,
            break_start_time=technician.break_time_window.start if technician.break_time_window else None,
            break_end_time=technician.break_time_window.end if technician.break_time_window else None,

            # Status
            is_active=technician.is_active,

            # NOTE: Skills та working_hours - це separate ORM tables.
            # Вони додаються через relationships або окремо.
            # Якщо налаштувати cascade="all, delete-orphan" в ORM,
            # SQLAlchemy зробить це автоматично.
        )