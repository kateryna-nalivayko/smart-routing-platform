"""
app/adapters/optimization/solver_adapter.py

MVP Adapter: інтегрує OR-Tools solver з domain layer.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from app.adapters.optimization.excel_oasis_loader import load_oasis_exterior_excel
from app.adapters.optimization.oasis_week_builder import build_week_request_from_oasis
from app.adapters.optimization.or_tools_solver import OrToolsSolver, ConstantTimeProvider

from app.domain.aggregates import Route, RouteStop, Technician, ServiceRequest
from app.domain.value_objects import Distance, Duration


class MVPSolverAdapter:

    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.solver = OrToolsSolver(
            travel_time_provider=ConstantTimeProvider(minutes_between=15),
            time_limit_seconds=20
        )

    def optimize_week(self, week_start: date) -> tuple[List[Route], List[str]]:

        sites, techs = load_oasis_exterior_excel(self.excel_path)

        # 2. Build OR-Tools request
        request = build_week_request_from_oasis(
            week_start=week_start,
            sites=sites,
            techs=techs,
            address_to_latlon=None
        )

        # 3. Solve
        result = self.solver.solve_week(request)

        # 4. Convert to Domain objects
        routes = []
        for day_key, day_routes in result.routes.items():
            for route_result in day_routes:
                # Convert OR-Tools route → Domain Route
                stops = []
                for idx, stop in enumerate(route_result.stops):
                    stops.append(RouteStop(
                        service_request_id=uuid4(),  # MVP: fake UUID
                        sequence_number=idx + 1,
                        arrival_time=stop.arrival,
                        departure_time=stop.departure,
                        travel_time_from_previous=Duration(15) if idx > 0 else None,
                        distance_from_previous=Distance(Decimal("5.0")) if idx > 0 else None,
                    ))

                routes.append(Route(
                    id=uuid4(),
                    technician_id=uuid4(),  # MVP: fake UUID
                    date=week_start,  # MVP: same date for all
                    stops=stops,
                    total_distance=Distance(Decimal("50.0")),  # MVP: fake
                    total_duration_minutes=300,  # MVP: fake
                ))

        return routes, result.dropped_visits
