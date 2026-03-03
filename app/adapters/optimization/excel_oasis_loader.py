from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

import pandas as pd

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_CAP = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}


@dataclass(frozen=True)
class OasisSiteRow:
    location_name: str
    address: str
    techs_needed: int
    visit_frequency: int
    duration_min: int
    tw_from: dict[str, int | None]
    tw_to: dict[str, int | None]
    skill_requirement: str
    physically_demanding: bool
    work_at_heights: bool
    requires_lift: bool
    requires_pesticides: bool
    requires_citizen: bool
    preferred_techs: list[str]
    avoid_techs: list[str]


@dataclass(frozen=True)
class OasisTechnicianRow:
    name: str
    office_address: str
    shift_from: dict[str, int | None]
    shift_to: dict[str, int | None]
    min_break_min: int
    break_not_earlier: int | None
    break_not_later: int | None
    max_hours_day: int
    max_hours_week: int
    skills: list[str]
    can_phys: bool
    can_heights: bool
    can_lift: bool
    can_pesticides: bool
    is_citizen: bool


def _to_minutes(v) -> int | None:
    if pd.isna(v):
        return None
    if isinstance(v, time):
        return v.hour * 60 + v.minute
    if isinstance(v, datetime):
        return v.hour * 60 + v.minute
    s = str(v).strip()
    if not s:
        return None
    parts = s.split(":")
    if len(parts) >= 2:
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            return None
    return None


def _parse_yes_no(v) -> bool:
    if pd.isna(v):
        return False
    s = str(v).strip().lower()
    return s in {"yes", "y", "true", "1"}


def _parse_duration_min(v) -> int:
    if pd.isna(v):
        return 0
    s = str(v).strip().lower()
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else 0


def _parse_frequency_per_week(v) -> int:
    if pd.isna(v):
        return 0
    s = str(v).strip().lower()
    if "x" in s:
        left = s.split("x", 1)[0].strip()
        digits = "".join(ch for ch in left if ch.isdigit())
        if digits:
            return int(digits)
    return 0


def _split_names(v) -> list[str]:
    if pd.isna(v):
        return []
    s = str(v).strip()
    if not s or s.lower() in {"no preference", "none", "nan"}:
        return []
    return [p.strip() for p in s.split(",") if p.strip() and p.strip().lower() != "no preference"]


def _build_cols_two_header_rows(df_raw: pd.DataFrame) -> list[str]:
    # header rows are index 1 and 2 (row 0 is group labels / merged)
    h1 = df_raw.iloc[1].tolist()
    h2 = df_raw.iloc[2].tolist()

    # forward-fill h1 (for "Mon ...", "Tue ..." where "to" col is blank in h1)
    filled = []
    last = ""
    for v in h1:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            filled.append(last)
        else:
            s = str(v).replace("\n", " ").strip()
            if not s or s.lower() == "nan":
                filled.append(last)
            else:
                last = s
                filled.append(last)

    cols: list[str] = []
    for a, b in zip(filled, h2, strict=False):
        parts = []
        if a and a.lower() != "nan":
            parts.append(a)
        if b is not None and not (isinstance(b, float) and pd.isna(b)):
            s = str(b).replace("\n", " ").strip()
            if s and s.lower() != "nan":
                parts.append(s)
        cols.append(" ".join(parts).strip())
    return cols


def load_oasis_exterior_excel(xlsx_path: str) -> tuple[list[OasisSiteRow], list[OasisTechnicianRow]]:
    xl = pd.ExcelFile(xlsx_path)

    df_sites_raw = xl.parse("Service sites (exterior FINAL)", header=None)
    df_tech_raw = xl.parse("Technicians", header=None)

    # ---------- SITES ----------
    df_sites = df_sites_raw.iloc[3:].copy()  # data starts at row index 3
    df_sites.columns = _build_cols_two_header_rows(df_sites_raw)
    df_sites = df_sites.reset_index(drop=True)

    df_sites = df_sites[df_sites["Location name  (from ETLocationList)"].notna()].copy()

    sites: list[OasisSiteRow] = []
    for _, r in df_sites.iterrows():
        tw_from = {}
        tw_to = {}
        for dk in WEEKDAYS:
            cap = DAY_CAP[dk]
            tw_from[dk] = _to_minutes(r.get(f"{cap} from"))
            tw_to[dk] = _to_minutes(r.get(f"{cap} to"))

        sites.append(
            OasisSiteRow(
                location_name=str(r.get("Location name  (from ETLocationList)", "")).strip(),
                address=str(r.get("Site address", "")).strip(),
                techs_needed=int(r.get("How many techs needed") or 1),
                visit_frequency=_parse_frequency_per_week(r.get("Visit freqency")),
                duration_min=_parse_duration_min(r.get("Est duration of the visit, minutes")),
                tw_from=tw_from,
                tw_to=tw_to,
                skill_requirement=str(r.get("Service skill requirement", "")).strip(),
                physically_demanding=_parse_yes_no(r.get("Physically demanding job")),
                work_at_heights=_parse_yes_no(r.get("Work at heights")),
                requires_lift=_parse_yes_no(r.get("Requires using the lift")),
                requires_pesticides=_parse_yes_no(r.get("Requires application of pesticides")),
                requires_citizen=_parse_yes_no(r.get("Requires a citizen technician")),
                preferred_techs=_split_names(r.get("Should be serviced by specific technician(s)")),
                avoid_techs=_split_names(r.get("Should NOT be serviced by the following technician(s)")),
            )
        )

    # ---------- TECHNICIANS ----------
    df_tech = df_tech_raw.iloc[3:].copy()
    df_tech.columns = _build_cols_two_header_rows(df_tech_raw)
    df_tech = df_tech.reset_index(drop=True)

    df_tech = df_tech[df_tech["Name"].notna()].copy()
    df_tech = df_tech[df_tech["Name"].astype(str).str.lower() != "no preference"].copy()

    techs: list[OasisTechnicianRow] = []
    for _, r in df_tech.iterrows():
        shift_from = {}
        shift_to = {}
        for dk in WEEKDAYS:
            cap = DAY_CAP[dk]
            shift_from[dk] = _to_minutes(r.get(f"{cap} from"))
            shift_to[dk] = _to_minutes(r.get(f"{cap} to"))

        techs.append(
            OasisTechnicianRow(
                name=str(r.get("Name", "")).strip(),
                office_address=str(r.get("Office address", "")).strip(),
                shift_from=shift_from,
                shift_to=shift_to,
                min_break_min=int(r.get("Min break per day, minutes") or 0),
                break_not_earlier=_to_minutes(r.get("Break should be taken not earlier than")),
                break_not_later=_to_minutes(r.get("Break should be taken not later than")),
                max_hours_day=int(r.get("Maximum hours of work per day for service") or 8),
                max_hours_week=int(r.get("Maximum hours of work per week for service") or 40),
                skills=_split_names(r.get("Service skills")) or ([str(r.get("Service skills")).strip()] if not pd.isna(r.get("Service skills")) else []),
                can_phys=_parse_yes_no(r.get("Can do physically demanding job")),
                can_heights=_parse_yes_no(r.get("Comfortable with work at heights")),
                can_lift=_parse_yes_no(r.get("Certified with using the lift")),
                can_pesticides=_parse_yes_no(r.get("Pesticide applicator certification")),
                is_citizen=_parse_yes_no(r.get("Is a citizen")),
            )
        )

    return sites, techs