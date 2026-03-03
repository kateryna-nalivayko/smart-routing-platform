"""
domain/ports.py

Абстракції (інтерфейси) для infrastructure.
Domain залежить від цих абстракцій, Adapters їх реалізують.

"""

from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

# ══════════════════════════════════════════════════════════════════════
# REPOSITORIES (абстракції)
# ══════════════════════════════════════════════════════════════════════

class AbstractTechnicianRepository(ABC):
    """Репозиторій техніків."""

    @abstractmethod
    async def get(self, tech_id: UUID):
        """Знайти техніка за ID."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_ids(self, ids: list[UUID]) -> list:
        """Знайти техніків за списком ID."""
        raise NotImplementedError

    @abstractmethod
    async def get_active(self) -> list:
        """Всі активні техніки."""
        raise NotImplementedError

    @abstractmethod
    async def add(self, technician) -> None:
        """Додати техніка."""
        raise NotImplementedError


class AbstractServiceRequestRepository(ABC):
    """Репозиторій заявок."""

    @abstractmethod
    async def get(self, request_id: UUID):
        raise NotImplementedError

    @abstractmethod
    async def get_by_ids(self, ids: list[UUID]) -> list:
        raise NotImplementedError

    @abstractmethod
    async def get_pending(self) -> list:
        """Всі заявки зі статусом PENDING."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, service_request) -> None:
        raise NotImplementedError


class AbstractRouteRepository(ABC):
    """Репозиторій маршрутів."""

    @abstractmethod
    async def add(self, route) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_technician_and_date(self, tech_id: UUID, target_date: date):
        raise NotImplementedError


class AbstractOptimizationTaskRepository(ABC):
    """Репозиторій задач оптимізації."""

    @abstractmethod
    async def add(self, task) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, task_id: UUID):
        raise NotImplementedError

    @abstractmethod
    async def find_in_progress(self, target_date: date):
        """Знайти активну задачу (QUEUED або PROCESSING)."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, task) -> None:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════
# UNIT OF WORK
# ══════════════════════════════════════════════════════════════════════

class AbstractUnitOfWork(ABC):
    """
    Unit of Work — управління транзакцією БД.

    Usage:
        async with uow:
            await uow.technicians.add(tech)
            await uow.commit()

    ВАЖЛИВО:
      - __aenter__ має повертати self
      - Всі методи async (async def)
      - commit/rollback з await
    """

    technicians: AbstractTechnicianRepository
    service_requests: AbstractServiceRequestRepository
    routes: AbstractRouteRepository
    optimization_tasks: AbstractOptimizationTaskRepository

    @abstractmethod
    async def __aenter__(self):
        """Початок транзакції. Має повернути self!"""
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Rollback при помилці."""
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        """Закомітити. ВАЖЛИВО: await self.session.commit()"""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        """Відкотити. ВАЖЛИВО: await self.session.rollback()"""
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════
# OPTIMIZER
# ══════════════════════════════════════════════════════════════════════

class AbstractOptimizer(ABC):
    """
    Абстракція оптимізатора маршрутів.

    Реалізація: adapters/optimization/or_tools_solver.py
    """

    @abstractmethod
    async def solve(self, input):
        """
        Розв'язати Vehicle Routing Problem with Time Windows.

        Args:
            input: OptimizationInput (техніки, заявки, дата, timeout)

        Returns:
            OptimizationResult (маршрути + метрики)

        Raises:
            NoFeasibleSolutionError: OR-Tools не знайшов рішення
            OptimizationTimeoutError: Вичерпано timeout
        """
        raise NotImplementedError