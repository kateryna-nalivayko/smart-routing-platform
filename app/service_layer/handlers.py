"""
service_layer/handlers.py

Command and Query handlers.
"""

from uuid import UUID

from sqlalchemy import select

from app.adapters.optimization.solver_adapter import MVPSolverAdapter
from app.config.settings import EXCEL_FILE_PATH
from app.domain.commands import OptimizeRoutes

from .unit_of_work import AbstractUnitOfWork


async def _ensure_route_dependencies(uow: AbstractUnitOfWork, routes: list) -> None:
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
            uow.session.add(
                Technician(
                    id=technician_id,
                    name=f"MVP Tech {str(technician_id)[:8]}",
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
            uow.session.add(
                ServiceSite(
                    id=site_id,
                    site_code=f"MVP-{str(site_id)[:12]}",
                    site_name=f"MVP Site {str(site_id)[:8]}",
                    duration_minutes=60,
                    visit_frequency=VisitFrequency.X1,
                )
            )


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
            routes, dropped = adapter.optimize_week(command.target_date)

            await _ensure_route_dependencies(uow, routes)
            for route in routes:
                await uow.routes.add(route)

            task.status = TaskStatus.SUCCESS
            task.routes_created = len(routes)
            task.sites_unassigned = len(dropped)
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
