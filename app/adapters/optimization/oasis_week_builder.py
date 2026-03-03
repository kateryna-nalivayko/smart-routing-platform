from __future__ import annotations

from datetime import date, timedelta

from app.adapters.optimization.or_tools_solver import (
    DayPlanRequest,
    LocationRef,
    OrToolsRoutingRequest,
    TechnicianDTO,
    VisitDTO,
)

from .excel_oasis_loader import OasisSiteRow, OasisTechnicianRow

DAY_PATTERNS = {
    1: ["mon"],
    2: ["mon", "thu"],
    3: ["mon", "wed", "fri"],  # ключове: не пн-вт-ср
    4: ["mon", "tue", "thu", "fri"],
    5: ["mon", "tue", "wed", "thu", "fri"],
}


def _week_dates(week_start: date) -> dict[str, date]:
    return {
        "mon": week_start,
        "tue": week_start + timedelta(days=1),
        "wed": week_start + timedelta(days=2),
        "thu": week_start + timedelta(days=3),
        "fri": week_start + timedelta(days=4),
    }


def build_week_request_from_oasis(
    week_start: date,
    sites: list[OasisSiteRow],
    techs: list[OasisTechnicianRow],
    address_to_latlon: dict[str, tuple[float, float]] | None = None,
) -> OrToolsRoutingRequest:
    dates = _week_dates(week_start)

    def loc(addr: str) -> LocationRef:
        lat = lon = None
        if address_to_latlon and addr in address_to_latlon:
            lat, lon = address_to_latlon[addr]
        return LocationRef(address=addr, lat=lat, lon=lon)

    # techs per day
    day_techs: dict[str, list[TechnicianDTO]] = {k: [] for k in dates}
    for t in techs:
        for day_key in dates:
            sf = t.shift_from.get(day_key)
            st = t.shift_to.get(day_key)
            if sf is None or st is None:
                continue
            office = loc(t.office_address)

            day_techs[day_key].append(
                TechnicianDTO(
                    id=f"tech:{t.name}",
                    name=t.name,
                    start=office,
                    end=office,
                    shift_from_min=sf,
                    shift_to_min=st,
                    max_work_min_today=int(t.max_hours_day * 60),
                    skills=t.skills,
                    can_phys=t.can_phys,
                    can_heights=t.can_heights,
                    can_lift=t.can_lift,
                    can_pesticides=t.can_pesticides,
                    is_citizen=t.is_citizen,
                )
            )

    # visits per day
    day_visits: dict[str, list[VisitDTO]] = {k: [] for k in dates}
    day_load = {k: 0 for k in dates}  # для балансування freq=1

    for s in sites:
        freq = s.visit_frequency
        if freq <= 0:
            continue

        if freq == 1:
            chosen_days = [min(day_load, key=lambda d: day_load[d])]
        else:
            chosen_days = (DAY_PATTERNS.get(freq, DAY_PATTERNS[3]))[:freq]

        for idx_occ, day_key in enumerate(chosen_days):
            tw_from = s.tw_from.get(day_key)
            tw_to = s.tw_to.get(day_key)
            if tw_from is None or tw_to is None:
                continue

            base = f"visit:{s.location_name}:{day_key}:{idx_occ}"
            group_id = base if s.techs_needed > 1 else None

            for copy in range(max(1, s.techs_needed)):
                day_visits[day_key].append(
                    VisitDTO(
                        id=f"{base}:copy{copy+1}",
                        site_name=s.location_name,
                        location=loc(s.address),
                        service_min=s.duration_min,
                        tw_from_min=tw_from,
                        tw_to_min=tw_to,
                        required_skill=s.skill_requirement,
                        requires_phys=s.physically_demanding,
                        requires_heights=s.work_at_heights,
                        requires_lift=s.requires_lift,
                        requires_pesticides=s.requires_pesticides,
                        requires_citizen=s.requires_citizen,
                        preferred_techs=s.preferred_techs,
                        avoid_techs=s.avoid_techs,
                        group_id=group_id,
                    )
                )

            day_load[day_key] += s.duration_min * max(1, s.techs_needed)

    day_plans = [
        DayPlanRequest(day_key=k, date=dates[k], technicians=day_techs[k], visits=day_visits[k])
        for k in dates
    ]
    return OrToolsRoutingRequest(week_start=week_start, day_plans=day_plans)