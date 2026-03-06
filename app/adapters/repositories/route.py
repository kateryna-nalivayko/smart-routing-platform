"""
adapters/repositories/route.py
"""

from datetime import date
from decimal import Decimal
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
        orm_route = self._to_orm(route)
        self.session.add(orm_route)

    async def get_by_technician_and_date(
        self, tech_id: UUID, target_date: date
    ) -> Route | None:
        result = await self.session.execute(
            select(RouteORM).where(
                RouteORM.technician_id == tech_id,
                RouteORM.route_date == target_date,
            )
        )
        orm_route = result.scalar_one_or_none()

        if not orm_route:
            return None

        return self._to_domain(orm_route)

    def _to_domain(self, orm: RouteORM) -> Route:
        from app.domain.aggregates import RouteStop
        from app.domain.value_objects import Distance, Duration, RouteStatus

        stops = []
        if orm.stops:
            for orm_stop in sorted(orm.stops, key=lambda s: s.sequence_number):
                stops.append(
                    RouteStop(
                        service_request_id=orm_stop.service_site_id,
                        sequence_number=orm_stop.sequence_number,
                        arrival_time=orm_stop.arrival_time,
                        departure_time=orm_stop.departure_time,
                        travel_time_from_previous=(
                            Duration(orm_stop.travel_time_from_previous_minutes)
                            if orm_stop.travel_time_from_previous_minutes is not None
                            else None
                        ),
                        distance_from_previous=(
                            Distance(Decimal(orm_stop.distance_from_previous_km))
                            if orm_stop.distance_from_previous_km is not None
                            else None
                        ),
                    )
                )

        return Route(
            id=orm.id,
            technician_id=orm.technician_id,
            date=orm.route_date,
            stops=stops,
            total_distance=Distance(Decimal(orm.total_distance_km)) if orm.total_distance_km is not None else None,
            total_duration_minutes=orm.total_duration_minutes,
            total_travel_time_minutes=orm.total_travel_time_minutes,
            status=RouteStatus(orm.status) if orm.status else RouteStatus.DRAFT,
        )

    def _to_orm(self, route: Route) -> RouteORM:
        from app.adapters.orm.route import RouteStop as RouteStopORM

        orm_stops = []
        for stop in route.stops:
            orm_stops.append(
                RouteStopORM(
                    service_site_id=stop.service_request_id,
                    sequence_number=stop.sequence_number,
                    arrival_time=stop.arrival_time,
                    departure_time=stop.departure_time,
                    travel_time_from_previous_minutes=(
                        stop.travel_time_from_previous.minutes if stop.travel_time_from_previous else None
                    ),
                    distance_from_previous_km=(
                        float(stop.distance_from_previous.kilometers) if stop.distance_from_previous else None
                    ),
                )
            )

        total_travel_time_minutes = sum(
            stop.travel_time_from_previous.minutes
            for stop in route.stops
            if stop.travel_time_from_previous is not None
        )

        return RouteORM(
            id=route.id,
            technician_id=route.technician_id,
            route_date=route.date,
            total_distance_km=float(route.total_distance.kilometers) if route.total_distance else None,
            total_duration_minutes=route.total_duration_minutes,
            total_travel_time_minutes=(
                route.total_travel_time_minutes
                if route.total_travel_time_minutes is not None
                else total_travel_time_minutes
            ),
            status=route.status.value if route.status else None,
            stops_count=len(route.stops),
            stops=orm_stops,
        )
