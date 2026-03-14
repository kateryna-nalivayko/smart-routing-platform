from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
except Exception:  # pragma: no cover
    pywrapcp = None
    routing_enums_pb2 = None

@dataclass(frozen=True)
class LocationRef:
    """Use address always; optionally lat/lon if you have them."""
    address: str
    lat: float | None = None
    lon: float | None = None


@dataclass(frozen=True)
class TechnicianDTO:
    id: str
    name: str
    start: LocationRef
    end: LocationRef

    shift_from_min: int
    shift_to_min: int
    max_work_min_today: int

    skills: list[str]
    can_phys: bool
    can_heights: bool
    can_lift: bool
    can_pesticides: bool
    is_citizen: bool


@dataclass(frozen=True)
class VisitDTO:
    id: str
    site_name: str
    location: LocationRef

    service_min: int
    tw_from_min: int
    tw_to_min: int

    required_skill: str
    requires_phys: bool
    requires_heights: bool
    requires_lift: bool
    requires_pesticides: bool
    requires_citizen: bool
    requires_permit: bool
    permit_techs: list[str]

    preferred_techs: list[str]
    avoid_techs: list[str]

    # If not None -> multi-tech synchronized group
    group_id: str | None = None


@dataclass(frozen=True)
class DayPlanRequest:
    day_key: str  # "mon".."fri"
    date: date
    technicians: list[TechnicianDTO]
    visits: list[VisitDTO]


@dataclass(frozen=True)
class OrToolsRoutingRequest:
    week_start: date
    day_plans: list[DayPlanRequest]


@dataclass(frozen=True)
class StopResult:
    visit_id: str
    site_name: str
    arrival: datetime
    departure: datetime


@dataclass(frozen=True)
class RouteResult:
    technician_id: str
    technician_name: str
    stops: list[StopResult]


@dataclass(frozen=True)
class OptimizationResult:
    week_start: date
    routes: dict[str, list[RouteResult]]  # day_key -> routes
    dropped_visits: list[str]


# -------------------- Travel time providers --------------------

class TravelTimeProvider(Protocol):
    def build_time_matrix_minutes(self, locations: list[LocationRef]) -> list[list[int]]:
        """Return NxN matrix of travel time in minutes."""
        raise NotImplementedError


class ConstantTimeProvider:
    """Simple fallback: constant travel time between different points."""
    def __init__(self, minutes_between: int = 15):
        self.minutes_between = int(minutes_between)

    def build_time_matrix_minutes(self, locations: list[LocationRef]) -> list[list[int]]:
        n = len(locations)
        m = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    m[i][j] = self.minutes_between
        return m


# -------------------- Skill / eligibility helpers --------------------

_LEVEL = {"junior": 0, "medior": 1, "senior": 2}


def _parse_skill(skill: str) -> tuple[str, int]:
    """
    "exterior - medior" -> ("exterior", 1)
    "exterior" -> ("exterior", 0)
    """
    s = (skill or "").strip().lower()
    if not s:
        return "", 0
    if "-" not in s:
        return s, 0
    parts = [p.strip() for p in s.split("-") if p.strip()]
    if not parts:
        return "", 0
    domain = parts[0]
    lvl = parts[-1]
    return domain, _LEVEL.get(lvl, 0)


def _skill_ok(tech_skills: list[str], required: str) -> bool:
    req_domain, req_lvl = _parse_skill(required)
    if not req_domain:
        return True
    for ts in tech_skills:
        dom, lvl = _parse_skill(ts)
        if dom == req_domain and lvl >= req_lvl:
            return True
    return False


def _eligible_vehicle_ids(visit: VisitDTO, techs: list[TechnicianDTO]) -> list[int]:
    allowed: list[int] = []
    for i, t in enumerate(techs):
        # skills
        if not _skill_ok(t.skills, visit.required_skill):
            continue

        # flags
        if visit.requires_phys and not t.can_phys:
            continue
        if visit.requires_heights and not t.can_heights:
            continue
        if visit.requires_lift and not t.can_lift:
            continue
        if visit.requires_pesticides and not t.can_pesticides:
            continue
        if visit.requires_citizen and not t.is_citizen:
            continue
        if visit.requires_permit and t.name not in visit.permit_techs:
            continue

        # matchmaking preferences
        if visit.preferred_techs and t.name not in visit.preferred_techs:
            continue
        if visit.avoid_techs and t.name in visit.avoid_techs:
            continue

        allowed.append(i)
    return allowed


# -------------------- Solver --------------------

class OrToolsSolver:
    """
    Solves per-day (DayPlanRequest). Weekly wrapper calls it for Mon..Fri.

    Supports:
    - time windows
    - technician eligibility (skills + flags + preferred/avoid)
    - dropping visits (penalty)
    - multi-tech visit: N copies with same group_id -> same start time + different techs + drop all-or-none
    """

    def __init__(
        self,
        travel_time_provider: TravelTimeProvider | None = None,
        dropped_visit_penalty: int = 1_000_000,
        fixed_cost_per_vehicle: int = 5_000,
        time_limit_seconds: int = 20,
    ):
        self.travel_time_provider = travel_time_provider or ConstantTimeProvider(15)
        self.dropped_visit_penalty = int(dropped_visit_penalty)
        self.fixed_cost_per_vehicle = int(fixed_cost_per_vehicle)
        self.time_limit_seconds = int(time_limit_seconds)

    def solve_week(self, req: OrToolsRoutingRequest) -> OptimizationResult:
        if pywrapcp is None:
            raise RuntimeError(
                "OR-Tools is not installed. Add 'ortools' to requirements and install dependencies."
            )

        routes_by_day: dict[str, list[RouteResult]] = {}
        dropped: list[str] = []

        for day_plan in req.day_plans:
            day_routes, day_dropped = self._solve_day(day_plan)
            routes_by_day[day_plan.day_key] = day_routes
            dropped.extend(day_dropped)

        return OptimizationResult(
            week_start=req.week_start,
            routes=routes_by_day,
            dropped_visits=dropped,
        )

    def _solve_day(self, day_plan: DayPlanRequest) -> tuple[list[RouteResult], list[str]]:
        techs = day_plan.technicians
        visits = day_plan.visits

        if not techs:
            return [], [v.id for v in visits]

        max_visits_for_solve = max(30, len(techs) * 8)
        overflow_visit_ids: list[str] = []
        if len(visits) > max_visits_for_solve:
            overflow_visit_ids = [v.id for v in visits[max_visits_for_solve:]]
            visits = visits[:max_visits_for_solve]

        # For now: assume one common depot (office). Builder usually sets this.
        depot = techs[0].start
        locations: list[LocationRef] = [depot] + [v.location for v in visits]

        time_matrix = self.travel_time_provider.build_time_matrix_minutes(locations)
        if not time_matrix or len(time_matrix) != len(locations):
            raise ValueError("TravelTimeProvider returned invalid time matrix size")

        num_vehicles = len(techs)
        depot_index = 0

        manager = pywrapcp.RoutingIndexManager(len(locations), num_vehicles, depot_index)
        routing = pywrapcp.RoutingModel(manager)

        # Cost: pure travel time
        def travel_cb(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(time_matrix[from_node][to_node])

        travel_cb_index = routing.RegisterTransitCallback(travel_cb)
        routing.SetArcCostEvaluatorOfAllVehicles(travel_cb_index)

        # Fixed cost to discourage unused vehicles / too many routes
        for vid in range(num_vehicles):
            routing.SetFixedCostOfVehicle(self.fixed_cost_per_vehicle, vid)

        # Time dimension: travel + service (service is charged on "from" node)
        service_by_node = [0] + [max(0, int(v.service_min)) for v in visits]

        def time_cb(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(time_matrix[from_node][to_node] + service_by_node[from_node])

        time_cb_index = routing.RegisterTransitCallback(time_cb)

        max_shift_end = max(t.shift_to_min for t in techs)
        routing.AddDimension(
            time_cb_index,
            120,                 # waiting slack
            max_shift_end + 120,  # horizon
            False,               # don't force start at 0
            "Time",
        )
        time_dim = routing.GetDimensionOrDie("Time")
        solver = routing.solver()

        # Tech shift windows and max work time
        for vid, t in enumerate(techs):
            start_idx = routing.Start(vid)
            end_idx = routing.End(vid)

            # shift bounds
            time_dim.CumulVar(start_idx).SetRange(t.shift_from_min, t.shift_to_min)
            time_dim.CumulVar(end_idx).SetRange(t.shift_from_min, t.shift_to_min)

            # max work minutes: end - start <= max_work_min_today
            # (if max_work_min_today is 0/negative -> ignore)
            if t.max_work_min_today and t.max_work_min_today > 0:
                solver.Add(time_dim.CumulVar(end_idx) - time_dim.CumulVar(start_idx) <= t.max_work_min_today)

        # Visits: time windows + allowed techs + droppable
        group_to_indices: dict[str, list[int]] = {}
        idx_to_visit: dict[int, VisitDTO] = {}

        for j, v in enumerate(visits):
            node = 1 + j
            idx = manager.NodeToIndex(node)
            idx_to_visit[idx] = v

            # time window
            tw_from = int(v.tw_from_min)
            tw_to = int(v.tw_to_min)
            if tw_to < tw_from:
                # make it safe: swap if data is bad
                tw_from, tw_to = tw_to, tw_from
            time_dim.CumulVar(idx).SetRange(tw_from, tw_to)

            # eligibility
            allowed = _eligible_vehicle_ids(v, techs)
            if allowed:
                routing.VehicleVar(idx).SetValues(sorted(set(allowed + [-1])))
            # else: leave unrestricted but droppable (will likely drop due to penalty)

            # droppable
            routing.AddDisjunction([idx], self.dropped_visit_penalty)

            # multi-tech grouping
            if v.group_id:
                group_to_indices.setdefault(v.group_id, []).append(idx)

        # Multi-tech synchronization:
        # - same start time (Time cumul equality)
        # - different technicians (VehicleVar !=)
        # - drop all-or-none (ActiveVar equality)
        for _gid, idxs in group_to_indices.items():
            if len(idxs) <= 1:
                continue
            first = idxs[0]
            for other in idxs[1:]:
                solver.Add(time_dim.CumulVar(other) == time_dim.CumulVar(first))
                solver.Add(routing.ActiveVar(other) == routing.ActiveVar(first))

        # Solve
        sp = pywrapcp.DefaultRoutingSearchParameters()
        sp.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        sp.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        sp.time_limit.FromSeconds(self.time_limit_seconds)

        solution = routing.SolveWithParameters(sp)
        if solution is None:
            fallback_routes, fallback_dropped = self._solve_day_greedy(day_plan, visits)
            return fallback_routes, [*overflow_visit_ids, *fallback_dropped]

        dropped: list[str] = []
        for j, v in enumerate(visits):
            idx = manager.NodeToIndex(1 + j)
            if solution.Value(routing.NextVar(idx)) == idx:
                dropped.append(v.id)

        # Extract routes
        routes: list[RouteResult] = []
        base_day = day_plan.date

        for vid, tech in enumerate(techs):
            idx = routing.Start(vid)
            stops: list[StopResult] = []

            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                if node != depot_index:
                    v = visits[node - 1]
                    arr_min = solution.Value(time_dim.CumulVar(idx))
                    dep_min = arr_min + int(v.service_min)

                    arr_dt = datetime.combine(base_day, datetime.min.time()) + timedelta(minutes=arr_min)
                    dep_dt = datetime.combine(base_day, datetime.min.time()) + timedelta(minutes=dep_min)

                    stops.append(
                        StopResult(
                            visit_id=v.id,
                            site_name=v.site_name,
                            arrival=arr_dt,
                            departure=dep_dt,
                        )
                    )

                idx = solution.Value(routing.NextVar(idx))

            if stops:
                routes.append(
                    RouteResult(
                        technician_id=tech.id,
                        technician_name=tech.name,
                        stops=stops,
                    )
                )

        if not routes and len(dropped) == len(visits):
            fallback_routes, fallback_dropped = self._solve_day_greedy(day_plan, visits)
            return fallback_routes, [*overflow_visit_ids, *fallback_dropped]

        return routes, [*overflow_visit_ids, *dropped]

    def _solve_day_greedy(
        self,
        day_plan: DayPlanRequest,
        visits: list[VisitDTO],
    ) -> tuple[list[RouteResult], list[str]]:
        techs = day_plan.technicians
        base_day = day_plan.date
        travel_between = 15

        tech_state = {}
        for idx, tech in enumerate(techs):
            tech_state[idx] = {
                "time": tech.shift_from_min,
                "stops": [],
            }

        dropped: list[str] = []
        sorted_visits = sorted(visits, key=lambda v: (v.tw_to_min, v.tw_from_min, v.service_min))

        for visit in sorted_visits:
            assigned = False
            allowed = _eligible_vehicle_ids(visit, techs)
            if not allowed:
                dropped.append(visit.id)
                continue

            for vehicle_id in allowed:
                state = tech_state[vehicle_id]
                tech = techs[vehicle_id]
                arrival = max(state["time"] + travel_between, visit.tw_from_min)
                departure = arrival + visit.service_min
                worked = departure - tech.shift_from_min

                if departure > visit.tw_to_min:
                    continue
                if departure > tech.shift_to_min:
                    continue
                if worked > tech.max_work_min_today:
                    continue

                arr_dt = datetime.combine(base_day, datetime.min.time()) + timedelta(minutes=arrival)
                dep_dt = datetime.combine(base_day, datetime.min.time()) + timedelta(minutes=departure)
                state["stops"].append(
                    StopResult(
                        visit_id=visit.id,
                        site_name=visit.site_name,
                        arrival=arr_dt,
                        departure=dep_dt,
                    )
                )
                state["time"] = departure
                assigned = True
                break

            if not assigned:
                dropped.append(visit.id)

        routes: list[RouteResult] = []
        for vehicle_id, tech in enumerate(techs):
            stops = tech_state[vehicle_id]["stops"]
            if stops:
                routes.append(
                    RouteResult(
                        technician_id=tech.id,
                        technician_name=tech.name,
                        stops=stops,
                    )
                )

        return routes, dropped
