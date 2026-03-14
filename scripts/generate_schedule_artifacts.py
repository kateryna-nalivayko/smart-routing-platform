import argparse
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.exporters.schedule_export import (
    write_constraints_json,
    write_schedule_excel,
    write_schedule_json,
)
from app.adapters.optimization.solver_adapter import MVPSolverAdapter
from app.config.settings import EXCEL_FILE_PATH, OUTPUT_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate schedule artifacts from the Excel workbook without running the API.",
    )
    parser.add_argument(
        "--week-start",
        type=date.fromisoformat,
        required=True,
        help="Week start date in ISO format, for example 2026-03-16.",
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=EXCEL_FILE_PATH,
        help="Path to the source Excel workbook.",
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="Optional task identifier for the output folder. By default a UUID is generated.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=OUTPUT_DIR,
        help="Root folder for generated artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.excel.exists():
        raise FileNotFoundError(f"Excel file not found: {args.excel}")

    task_id = args.task_id or str(uuid4())
    task_dir = args.output_root / task_id

    solver = MVPSolverAdapter(str(args.excel))
    result = solver.optimize_week(args.week_start)

    write_schedule_json(task_dir / "schedule_log.json", result.schedule_rows)
    write_schedule_excel(task_dir / "schedule_log.xlsx", result.schedule_rows)
    write_constraints_json(task_dir / "constraints_summary.json", result.constraints_summary)

    print(f"task_id={task_id}")
    print(f"schedule_json={task_dir / 'schedule_log.json'}")
    print(f"schedule_xlsx={task_dir / 'schedule_log.xlsx'}")
    print(f"constraints_json={task_dir / 'constraints_summary.json'}")
    print(f"routes={len(result.routes)}")
    print(f"dropped_visits={len(result.dropped_visit_ids)}")
    print(f"schedule_rows={len(result.schedule_rows)}")


if __name__ == "__main__":
    main()
