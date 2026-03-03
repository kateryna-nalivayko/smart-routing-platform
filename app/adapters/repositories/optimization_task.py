"""
adapters/repositories/optimization_task.py
"""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.orm import OptimizationTask
from app.adapters.ports import AbstractOptimizationTaskRepository


class SqlAlchemyOptimizationTaskRepository(AbstractOptimizationTaskRepository):
    """
    Repository для OptimizationTask.

    NOTE: OptimizationTask використовується напряму як ORM model,
    без mapping до domain aggregate.

    ЧОМУ?
    1. OptimizationTask - це просто запис про статус оптимізації
    2. Немає складної domain логіки
    3. Не потребує invariants
    4. Простий CRUD

    У "чистій" DDD це б був окремий domain aggregate,
    але для простоти використовуємо ORM model напряму.

    Якщо з'явиться складна логіка - винесемо в domain.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, task: OptimizationTask) -> None:
        """
        Додати нову задачу.

        NOTE: task - це ORM model, не domain object!
        """
        self.session.add(task)

    async def get(self, task_id: UUID) -> OptimizationTask | None:
        """Знайти задачу за ID."""
        result = await self.session.execute(
            select(OptimizationTask).where(OptimizationTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def find_in_progress(self, target_date: date) -> OptimizationTask | None:
        """
        Знайти активну задачу (QUEUED або PROCESSING).

        Використовується для перевірки дублікатів.
        """
        from app.adapters.orm.base import TaskStatus
        result = await self.session.execute(
            select(OptimizationTask).where(
                OptimizationTask.target_date == target_date,
                OptimizationTask.status.in_([TaskStatus.QUEUED, TaskStatus.PROCESSING])
            )
        )
        return result.scalar_one_or_none()

    async def update(self, task: OptimizationTask) -> None:
        """
        Оновити задачу.

        NOTE: SQLAlchemy автоматично трекає зміни,
        тому просто змінюємо поля task і викликаємо uow.commit().
        """
        # SQLAlchemy tracks changes automatically
        pass