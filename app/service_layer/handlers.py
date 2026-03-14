"""
service_layer/handlers.py

Command and Query handlers.
"""

from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.adapters.exporters.schedule_export import (
    write_constraints_json,
    write_schedule_excel,
    write_schedule_json,
)
from app.adapters.optimization.solver_adapter import MVPSolverAdapter
from app.config.settings import EXCEL_FILE_PATH, OUTPUT_DIR
from app.domain.commands import OptimizeRoutes

from .unit_of_work import AbstractUnitOfWork


async def _ensure_route_dependencies(
    uow: AbstractUnitOfWork,
    routes: list,
    technician_catalog: dict,
    site_catalog: dict,
) -> None:
    from app.adapters.orm.base import VisitFrequency
    from app.adapters.orm.service_site import ServiceSite
    from app.adapters.orm.technician import Technician

    technician_ids = {route.technician_id for route in routes}
    site_ids = {
        stop.service_request_id
        for route in routes
        for stop in route.stops
    }

    if technician_ids:
        existing_tech_ids = set(
            (
                await uow.session.execute(
                    select(Technician.id).where(Technician.id.in_(technician_ids))
                )
            ).scalars().all()
        )
        missing_tech_ids = technician_ids - existing_tech_ids
        for technician_id in missing_tech_ids:
            tech_payload = technician_catalog.get(technician_id, {})
            uow.session.add(
                Technician(
                    id=technician_id,
                    name=tech_payload.get("name") or f"MVP Tech {str(technician_id)[:8]}",
                    office_address=tech_payload.get("office_address"),
                )
            )

    if site_ids:
        existing_site_ids = set(
            (
                await uow.session.execute(
                    select(ServiceSite.id).where(ServiceSite.id.in_(site_ids))
                )
            ).scalars().all()
        )
        missing_site_ids = site_ids - existing_site_ids
        for site_id in missing_site_ids:
            site_payload = site_catalog.get(site_id, {})
            uow.session.add(
                ServiceSite(
                    id=site_id,
                    site_code=site_payload.get("site_code") or f"MVP-{str(site_id)[:12]}",
                    site_name=site_payload.get("site_name") or f"MVP Site {str(site_id)[:8]}",
                    address=site_payload.get("address"),
                    duration_minutes=60,
                    visit_frequency=VisitFrequency.X1,
                )
            )


def _write_task_artifacts(
    task_id: UUID,
    schedule_rows: list[dict[str, object]],
    constraints_summary: dict[str, object],
) -> None:
    task_dir = Path(OUTPUT_DIR) / str(task_id)
    write_schedule_json(task_dir / "schedule_log.json", schedule_rows)
    write_schedule_excel(task_dir / "schedule_log.xlsx", schedule_rows)
    write_constraints_json(task_dir / "constraints_summary.json", constraints_summary)


async def optimize_routes_handler(command: OptimizeRoutes, uow: AbstractUnitOfWork):
    async with uow:
        existing = await uow.optimization_tasks.find_in_progress(command.target_date)
        if existing:
            raise ValueError(f"Task for {command.target_date} already in progress")

        from app.adapters.orm.base import TaskStatus
        from app.adapters.orm.optimization import OptimizationTask

        task = OptimizationTask(
            target_date=command.target_date,
            status=TaskStatus.QUEUED,
        )

        await uow.optimization_tasks.add(task)
        await uow.commit()

        try:
            task.status = TaskStatus.PROCESSING
            await uow.commit()

            adapter = MVPSolverAdapter(str(EXCEL_FILE_PATH))
            run_result = adapter.optimize_week(command.target_date)

            await _ensure_route_dependencies(
                uow,
                run_result.routes,
                run_result.technician_catalog,
                run_result.site_catalog,
            )
            for route in run_result.routes:
                await uow.routes.add(route)

            total_distance_km = sum(
                (route.total_distance.kilometers for route in run_result.routes if route.total_distance is not None),
                start=Decimal("0.00"),
            )

            _write_task_artifacts(
                task.id,
                run_result.schedule_rows,
                run_result.constraints_summary,
            )

            task.status = TaskStatus.SUCCESS
            task.routes_created = len(run_result.routes)
            task.sites_unassigned = len(run_result.dropped_visit_ids)
            task.total_distance_km = total_distance_km
            await uow.commit()

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            await uow.commit()

        return task.id


async def get_task_status_handler(
    task_id: UUID,
    uow: AbstractUnitOfWork,
) -> dict:
    """Get status of optimization task."""
    async with uow:
        task = await uow.optimization_tasks.get(task_id)
        if not task:
            raise ValueError("Task not found")

        return {
            "task_id": task.id,
            "status": task.status.value,
            "target_date": task.target_date,
            "routes_created": task.routes_created,
            "sites_unassigned": task.sites_unassigned,
            "total_distance_km": float(task.total_distance_km) if task.total_distance_km else None,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
        }
