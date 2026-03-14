from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook

SCHEDULE_HEADERS = [
    "date",
    "day_of_week",
    "start_time",
    "end_time",
    "technician_name",
    "location_name",
    "location_to",
    "activity_type",
]


def write_schedule_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=True), encoding="utf-8")


def write_constraints_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def write_schedule_excel(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Schedule Log"
    worksheet.append(SCHEDULE_HEADERS)

    for row in rows:
        worksheet.append([row.get(header) for header in SCHEDULE_HEADERS])

    for column_cells in worksheet.columns:
        max_len = max(len(str(cell.value or "")) for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(max_len + 2, 40)

    workbook.save(path)
