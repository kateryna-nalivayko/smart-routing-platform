"""
service_layer/handlers.py

Command and Query handlers.
"""

from uuid import UUID

from app.domain.commands import OptimizeRoutes

from .unit_of_work import AbstractUnitOfWork
from app.config.settings import EXCEL_FILE_PATH
from app.adapters.optimization.solver_adapter import MVPSolverAdapter


async def optimize_routes_handler(command: OptimizeRoutes, uow):
    async with uow:
        # Check existing
        existing = await uow.optimization_tasks.find_in_progress(command.target_date)
        if existing:
            raise ValueError(f"Task for {command.target_date} already in progress")

        # Create task
        from app.adapters.orm.optimization import OptimizationTask
        from app.adapters.orm.base import TaskStatus

        task = OptimizationTask(
            target_date=command.target_date,
            status=TaskStatus.QUEUED,
        )

        await uow.optimization_tasks.add(task)
        await uow.commit()

        # МVP: Run solver synchronously (в production - Dramatiq)
        try:
            # Update status
            task.status = TaskStatus.PROCESSING
            await uow.commit()

            # Run solver
            adapter = MVPSolverAdapter(str(EXCEL_FILE_PATH))
            routes, dropped = adapter.optimize_week(command.target_date)

            # Save routes
            for route in routes:
                await uow.routes.add(route)

            # Update task
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