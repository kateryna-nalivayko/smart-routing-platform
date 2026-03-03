"""
adapters/repositories/route.py
"""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.orm import Route as RouteORM
from app.adapters.ports import AbstractRouteRepository
from app.domain.aggregates import Route


class SqlAlchemyRouteRepository(AbstractRouteRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, route: Route) -> None:
        """
        Зберегти маршрут (Domain → ORM).

        Mapping:
        - Domain Route → ORM Route
        - Domain RouteStop list → ORM RouteStop table
        """
        orm_route = self._to_orm(route)
        self.session.add(orm_route)

    async def get_by_technician_and_date(
        self, tech_id: UUID, target_date: date
    ) -> Route | None:
        """Знайти маршрут за техніком і датою."""
        result = await self.session.execute(
            select(RouteORM).where(
                RouteORM.technician_id == tech_id,
                RouteORM.route_date == target_date
            )
        )
        orm_route = result.scalar_one_or_none()

        if not orm_route:
            return None

        return self._to_domain(orm_route)

    def _to_domain(self, orm: RouteORM) -> Route:
        """
        Convert ORM Route → Domain Route.

        Включає RouteStop list.
        """
        from app.domain.aggregates import RouteStop
        from app.domain.value_objects import Distance, Duration

        # Convert stops (ORM list → Domain list)
        stops = []
        if orm.stops:
            for orm_stop in sorted(orm.stops, key=lambda s: s.sequence_number):
                stops.append(RouteStop(
                    service_request_id=orm_stop.service_request_id,
                    sequence_number=orm_stop.sequence_number,
                    arrival_time=orm_stop.arrival_time,
                    departure_time=orm_stop.departure_time,
                    travel_time_from_previous=Duration(orm_stop.travel_time_minutes) if orm_stop.travel_time_minutes else None,
                    distance_from_previous=Distance(orm_stop.distance_km) if orm_stop.distance_km else None
                ))

        # Create domain Route
        from app.domain.value_objects import RouteStatus

        return Route(
            id=orm.id,
            technician_id=orm.technician_id,
            date=orm.route_date,
            stops=stops,
            total_distance=Distance(orm.total_distance_km) if orm.total_distance_km else None,
            total_duration_minutes=orm.total_duration_minutes,
            total_travel_time_minutes=orm.total_travel_time_minutes,
            status=RouteStatus(orm.status) if orm.status else RouteStatus.DRAFT
        )

    def _to_orm(self, route: Route) -> RouteORM:
        """
        Convert Domain Route → ORM Route.

        Включає RouteStop list.
        """
        from app.adapters.orm.route import RouteStop as RouteStopORM

        # Convert stops (Domain list → ORM list)
        orm_stops = []
        for stop in route.stops:
            orm_stops.append(RouteStopORM(
                service_request_id=stop.service_request_id,
                sequence_number=stop.sequence_number,
                arrival_time=stop.arrival_time,
                departure_time=stop.departure_time,
                travel_time_minutes=stop.travel_time_from_previous.minutes if stop.travel_time_from_previous else None,
                distance_km=float(stop.distance_from_previous.kilometers) if stop.distance_from_previous else None
            ))

        return RouteORM(
            id=route.id,
            technician_id=route.technician_id,
            route_date=route.date,

            # Metrics
            total_distance_km=float(route.total_distance.kilometers) if route.total_distance else None,
            total_duration_minutes=route.total_duration_minutes,
            total_travel_time_minutes=route.total_travel_time_minutes,

            status=route.status.value if route.status else None,

            # Stops (буде збережено через relationship cascade)
            stops=orm_stops
        )