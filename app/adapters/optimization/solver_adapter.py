"""
app/adapters/optimization/solver_adapter.py

MVP Adapter: ???????? OR-Tools solver ? domain layer.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.adapters.optimization.excel_oasis_loader import load_oasis_exterior_excel
from app.adapters.optimization.oasis_week_builder import build_week_request_from_oasis
from app.adapters.optimization.or_tools_solver import ConstantTimeProvider, OrToolsSolver
from app.domain.aggregates import Route, RouteStop
from app.domain.value_objects import Distance, Duration


class MVPSolverAdapter:
    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.solver = OrToolsSolver(
            travel_time_provider=ConstantTimeProvider(minutes_between=15),
            time_limit_seconds=20,
        )

    def optimize_week(self, week_start: date) -> tuple[list[Route], list[str]]:
        sites, techs = load_oasis_exterior_excel(self.excel_path)

        request = build_week_request_from_oasis(
            week_start=week_start,
            sites=sites,
            techs=techs,
            address_to_latlon=None,
        )

        result = self.solver.solve_week(request)

        routes: list[Route] = []
        day_to_offset = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}

        for day_key, day_routes in result.routes.items():
            route_date = week_start + timedelta(days=day_to_offset.get(day_key, 0))
            for route_result in day_routes:
                stops: list[RouteStop] = []
                for idx, stop in enumerate(route_result.stops):
                    departure_time = stop.departure
                    if departure_time <= stop.arrival:
                        departure_time = stop.arrival + timedelta(minutes=1)
                    stops.append(
                        RouteStop(
                            service_request_id=uuid5(NAMESPACE_URL, f"site:{stop.site_name}"),
                            sequence_number=idx + 1,
                            arrival_time=stop.arrival,
                            departure_time=departure_time,
                            travel_time_from_previous=Duration(15) if idx > 0 else None,
                            distance_from_previous=Distance(Decimal("5.0")) if idx > 0 else None,
                        )
                    )

                routes.append(
                    Route(
                        id=uuid4(),
                        technician_id=uuid5(NAMESPACE_URL, route_result.technician_id),
                        date=route_date,
                        stops=stops,
                        total_distance=Distance(Decimal("50.0")),
                        total_duration_minutes=300,
                    )
                )

        return routes, result.dropped_visits
