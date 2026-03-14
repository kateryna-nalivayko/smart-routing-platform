from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.adapters.geocoding import CachedGeocoder
from app.adapters.optimization.excel_oasis_loader import (
    OasisSiteRow,
    OasisTechnicianRow,
    load_oasis_exterior_excel,
)
from app.adapters.optimization.oasis_week_builder import build_week_request_from_oasis
from app.adapters.optimization.or_tools_solver import (
    DayPlanRequest,
    LocationRef,
    OrToolsSolver,
)
from app.adapters.optimization.or_tools_solver import (
    OptimizationResult as SolverWeekResult,
)
from app.adapters.optimization.travel_metrics import HaversineTimeProvider, build_leg_metrics
from app.config.settings import GEOCODING_CACHE_PATH
from app.domain.aggregates import Route, RouteStop
from app.domain.value_objects import Distance, Duration


@dataclass(frozen=True)
class OptimizationRunResult:
    routes: list[Route]
    dropped_visit_ids: list[str]
    schedule_rows: list[dict[str, object]]
    constraints_summary: dict[str, object]
    technician_catalog: dict[UUID, dict[str, str | None]]
    site_catalog: dict[UUID, dict[str, str | None]]


class MVPSolverAdapter:
    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.geocoder = CachedGeocoder(GEOCODING_CACHE_PATH)
        self.solver = OrToolsSolver(
            travel_time_provider=HaversineTimeProvider(),
            time_limit_seconds=20,
        )

    def optimize_week(self, week_start: date) -> OptimizationRunResult:
        sites, techs = load_oasis_exterior_excel(self.excel_path)
        address_to_latlon = self._resolve_coordinates(sites, techs)

        request = build_week_request_from_oasis(
            week_start=week_start,
            sites=sites,
            techs=techs,
            address_to_latlon=address_to_latlon,
        )

        result = self.solver.solve_week(request)
        site_catalog = self._build_site_catalog(sites)
        technician_catalog = self._build_technician_catalog(techs)

        routes = self._build_domain_routes(
            request=request,
            result=result,
        )
        schedule_rows = self._build_schedule_rows(request, result)
        constraints_summary = self._build_constraints_summary()

        return OptimizationRunResult(
            routes=routes,
            dropped_visit_ids=result.dropped_visits,
            schedule_rows=schedule_rows,
            constraints_summary=constraints_summary,
            technician_catalog=technician_catalog,
            site_catalog=site_catalog,
        )

    def _resolve_coordinates(
        self,
        sites: list[OasisSiteRow],
        techs: list[OasisTechnicianRow],
    ) -> dict[str, tuple[float, float]]:
        addresses = {
            site.address.strip()
            for site in sites
            if site.address and site.address.strip()
        }
        addresses.update(
            tech.office_address.strip()
            for tech in techs
            if tech.office_address and tech.office_address.strip()
        )
        return self.geocoder.geocode_many(sorted(addresses))

    def _build_site_catalog(
        self,
        sites: list[OasisSiteRow],
    ) -> dict[UUID, dict[str, str | None]]:
        catalog: dict[UUID, dict[str, str | None]] = {}
        for site in sites:
            site_id = uuid5(NAMESPACE_URL, f"site:{site.location_name}")
            catalog[site_id] = {
                "site_name": site.location_name,
                "site_code": site.location_name,
                "address": site.address,
                "service_type": self._activity_type_from_skill(site.skill_requirement),
            }
        return catalog

    def _build_technician_catalog(
        self,
        techs: list[OasisTechnicianRow],
    ) -> dict[UUID, dict[str, str | None]]:
        catalog: dict[UUID, dict[str, str | None]] = {}
        for tech in techs:
            tech_id = uuid5(NAMESPACE_URL, f"tech:{tech.name}")
            catalog[tech_id] = {
                "name": tech.name,
                "office_address": tech.office_address,
            }
        return catalog

    def _build_domain_routes(
        self,
        request,
        result: SolverWeekResult,
    ) -> list[Route]:
        routes: list[Route] = []
        day_plan_by_key = {day.day_key: day for day in request.day_plans}

        for day_key, day_routes in result.routes.items():
            day_plan = day_plan_by_key[day_key]
            tech_index = {tech.id: tech for tech in day_plan.technicians}
            visit_index = {visit.id: visit for visit in day_plan.visits}

            for route_result in day_routes:
                technician_id = uuid5(NAMESPACE_URL, route_result.technician_id)
                technician_ref = tech_index[route_result.technician_id]
                route_stops: list[RouteStop] = []
                total_distance = Decimal("0.00")

                previous_location: LocationRef = technician_ref.start
                for idx, stop in enumerate(route_result.stops):
                    visit = visit_index[stop.visit_id]
                    leg = build_leg_metrics(previous_location, visit.location)
                    total_distance += leg.distance_km

                    departure_time = stop.departure
                    if departure_time <= stop.arrival:
                        departure_time = stop.arrival + timedelta(minutes=max(1, visit.service_min))

                    route_stops.append(
                        RouteStop(
                            service_request_id=uuid5(NAMESPACE_URL, f"site:{stop.site_name}"),
                            sequence_number=idx + 1,
                            arrival_time=stop.arrival,
                            departure_time=departure_time,
                            travel_time_from_previous=(
                                Duration(leg.travel_minutes) if idx >= 0 else None
                            ),
                            distance_from_previous=Distance(leg.distance_km),
                        )
                    )
                    previous_location = visit.location

                if route_result.stops:
                    end_leg = build_leg_metrics(previous_location, technician_ref.end)
                    total_distance += end_leg.distance_km
                else:
                    end_leg = None

                total_duration_minutes = 0
                if route_result.stops:
                    route_start = route_result.stops[0].arrival - timedelta(
                        minutes=route_stops[0].travel_time_from_previous.minutes
                    )
                    route_end = route_result.stops[-1].departure
                    if end_leg is not None:
                        route_end += timedelta(minutes=end_leg.travel_minutes)
                    total_duration_minutes = int((route_end - route_start).total_seconds() / 60)

                routes.append(
                    Route(
                        id=uuid4(),
                        technician_id=technician_id,
                        date=day_plan.date,
                        stops=route_stops,
                        total_distance=Distance(total_distance),
                        total_duration_minutes=total_duration_minutes,
                    )
                )

        return routes

    def _build_schedule_rows(
        self,
        request,
        result: SolverWeekResult,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        day_plan_by_key: dict[str, DayPlanRequest] = {day.day_key: day for day in request.day_plans}

        for day_key, day_routes in result.routes.items():
            day_plan = day_plan_by_key[day_key]
            tech_index = {tech.id: tech for tech in day_plan.technicians}
            visit_index = {visit.id: visit for visit in day_plan.visits}

            for route_result in day_routes:
                technician = tech_index[route_result.technician_id]
                current_location_name = "Office"
                current_location = technician.start

                for stop in route_result.stops:
                    visit = visit_index[stop.visit_id]
                    leg = build_leg_metrics(current_location, visit.location)
                    commute_start = stop.arrival - timedelta(minutes=leg.travel_minutes)

                    rows.append(
                        self._schedule_row(
                            route_date=day_plan.date,
                            technician_name=route_result.technician_name,
                            start_time=commute_start,
                            end_time=stop.arrival,
                            location_name=current_location_name,
                            location_to=stop.site_name,
                            activity_type="Commute",
                        )
                    )
                    rows.append(
                        self._schedule_row(
                            route_date=day_plan.date,
                            technician_name=route_result.technician_name,
                            start_time=stop.arrival,
                            end_time=stop.departure,
                            location_name=stop.site_name,
                            location_to=None,
                            activity_type=self._activity_type_from_skill(visit.required_skill),
                        )
                    )

                    current_location_name = stop.site_name
                    current_location = visit.location

                if route_result.stops:
                    final_leg = build_leg_metrics(current_location, technician.end)
                    rows.append(
                        self._schedule_row(
                            route_date=day_plan.date,
                            technician_name=route_result.technician_name,
                            start_time=route_result.stops[-1].departure,
                            end_time=route_result.stops[-1].departure + timedelta(minutes=final_leg.travel_minutes),
                            location_name=current_location_name,
                            location_to="Office",
                            activity_type="Commute",
                        )
                    )

        rows.sort(
            key=lambda row: (
                str(row["date"]),
                str(row["technician_name"]),
                str(row["start_time"]),
            )
        )
        return rows

    def _schedule_row(
        self,
        route_date: date,
        technician_name: str,
        start_time,
        end_time,
        location_name: str,
        location_to: str | None,
        activity_type: str,
    ) -> dict[str, object]:
        return {
            "date": route_date.isoformat(),
            "day_of_week": route_date.strftime("%A"),
            "start_time": start_time.strftime("%H:%M"),
            "end_time": end_time.strftime("%H:%M"),
            "technician_name": technician_name,
            "location_name": location_name,
            "location_to": location_to,
            "activity_type": activity_type,
        }

    def _build_constraints_summary(self) -> dict[str, object]:
        return {
            "accounted_constraints": [
                {
                    "name": "service_time_windows",
                    "status": "accounted",
                    "details": "Visit start times are constrained by site day/time windows in OR-Tools.",
                },
                {
                    "name": "travel_time_between_points",
                    "status": "accounted",
                    "details": "Travel time is calculated from geocoded coordinates using Haversine distance and average speed.",
                },
                {
                    "name": "service_duration",
                    "status": "accounted",
                    "details": "Each visit consumes its declared service duration in the time dimension.",
                },
                {
                    "name": "technician_capabilities_and_skills",
                    "status": "accounted",
                    "details": "Eligibility filters apply skill hierarchy plus physical/heights/lift/pesticide/citizen flags.",
                },
                {
                    "name": "preferred_and_avoided_technicians",
                    "status": "accounted_with_current_logic",
                    "details": "Preferred technicians are currently treated as a hard allow-list; avoided technicians are hard exclusions.",
                },
                {
                    "name": "permit_restrictions",
                    "status": "accounted",
                    "details": "If a site requires a permit, only technicians listed in the permit column remain eligible.",
                },
                {
                    "name": "max_daily_work_time",
                    "status": "accounted",
                    "details": "Route duration per day is bounded by technician shift and max hours per day.",
                },
                {
                    "name": "multi_tech_same_time_visit",
                    "status": "accounted",
                    "details": "Sites requiring multiple technicians are duplicated into a synchronized group with equal start time and different vehicles.",
                },
            ],
            "not_accounted_constraints": [
                {
                    "name": "weekly_work_limit",
                    "status": "not_accounted",
                    "details": "Maximum hours per week are parsed but not enforced across the whole week.",
                },
                {
                    "name": "break_window",
                    "status": "not_accounted",
                    "details": "Break duration and allowed break window are parsed but no break interval is inserted into the solver.",
                },
                {
                    "name": "home_start_finish_modes",
                    "status": "not_accounted",
                    "details": "Current builder routes technicians from office to office; home/either works is not yet modeled.",
                },
                {
                    "name": "non_consecutive_repeat_visit_rule",
                    "status": "partially_accounted",
                    "details": "Weekly frequency patterns spread some visits across the week, but there is no generic hard rule forbidding day-by-day assignments.",
                },
                {
                    "name": "hub_and_walk_multimodality",
                    "status": "not_accounted",
                    "details": "Drive-to-hub and walk chains are not modeled in the current solver.",
                },
                {
                    "name": "multi_week_cycle_2_3_4_week_recurrence",
                    "status": "not_accounted",
                    "details": "The MVP optimizes one work week; long recurring cycle generation is not implemented.",
                },
            ],
        }

    @staticmethod
    def _activity_type_from_skill(skill_value: str) -> str:
        domain = (skill_value or "").split("-", 1)[0].strip().lower()
        mapping = {
            "interior": "Interior",
            "exterior": "Exterior",
            "floral": "Floral",
        }
        return mapping.get(domain, "Service")
