"""
domain/services.py

Domain Services - координують роботу між aggregates.

Domain Service використовується коли логіка:
1. Не належить одному aggregate
2. Потребує координації між кількома aggregates
3. Не має природного місця в жодному aggregate
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from ..adapters.ports import AbstractOptimizer
from .aggregates import Route, ServiceRequest, Technician
from .policies import RoutingPolicy

# ═══════════════════════════════════════════════════════════════════════════
# RESULT OBJECTS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OptimizationResult:
    """
    Результат оптимізації маршрутів.

    Містить:
    - Створені маршрути
    - Метрики оптимізації
    - Не призначені заявки
    """
    routes: list[Route]

    # Метрики
    total_distance_km: float
    total_duration_minutes: int
    sites_assigned: int
    sites_unassigned: int

    # Не призначені заявки
    unassigned_requests: list[ServiceRequest]

    # Час оптимізації
    optimization_time_seconds: float


@dataclass
class OptimizationInput:
    """
    Вхідні дані для оптимізації.

    Містить всі дані, необхідні для роботи OR-Tools.
    """
    technicians: list[Technician]
    service_requests: list[ServiceRequest]
    target_date: date
    timeout_seconds: int


# ═══════════════════════════════════════════════════════════════════════════
# ROUTING SERVICE
# ═══════════════════════════════════════════════════════════════════════════

class RoutingService:
    """
    Domain Service для координації оптимізації маршрутів.

    Відповідальність:
    1. Валідація можливості оптимізації (feasibility)
    2. Фільтрація неможливих призначень
    3. Координація з OR-Tools solver
    4. Створення Route aggregates з результатів

    Використання:
        service = RoutingService(optimizer=or_tools_optimizer)

        result = await service.optimize_routes(
            target_date=date(2026, 2, 25),
            technician_ids=[...],
            service_request_ids=[...],
            timeout_seconds=30
        )
    """

    def __init__(self, optimizer: AbstractOptimizer):
        """
        Args:
            optimizer: OR-Tools solver (через абстракцію)
        """
        self.optimizer = optimizer

    async def optimize_routes(
            self,
            target_date: date,
            technician_ids: list[UUID] | None = None,
            service_request_ids: list[UUID] | None = None,
            timeout_seconds: int = 30,
    ) -> OptimizationResult:
        """
        Оптимізувати маршрути для конкретної дати.

        Процес:
        1. Завантажити дані (technicians, service_requests)
        2. Валідувати можливість оптимізації (feasibility)
        3. Побудувати матрицю допустимих призначень
        4. Викликати OR-Tools solver
        5. Створити Route aggregates з результатів
        6. Повернути OptimizationResult

        Args:
            target_date: Дата для оптимізації
            technician_ids: Обмежити техніками (опціонально)
            service_request_ids: Обмежити заявками (опціонально)
            timeout_seconds: Тайм-аут для OR-Tools

        Returns:
            OptimizationResult з маршрутами та метриками

        Raises:
            ValueError: Якщо оптимізація неможлива (feasibility failed)
        """
        raise NotImplementedError(
            "RoutingService.optimize_routes() is a skeleton. "
            "Real implementation is in handlers.py with repositories."
        )

    @staticmethod
    def validate_assignment(
            technician: Technician,
            service_request: ServiceRequest
    ) -> tuple[bool, str]:
        """
        Валідувати чи може технік виконати заявку.

        Використовує RoutingPolicy.can_assign().

        Args:
            technician: Технік
            service_request: Заявка

        Returns:
            (can_assign: bool, reason: str)
        """
        return RoutingPolicy.can_assign(technician, service_request)

    @staticmethod
    def calculate_assignment_score(
            technician: Technician,
            service_request: ServiceRequest
    ) -> int:
        """
        Розрахувати оцінку призначення (для OR-Tools).

        Використовує RoutingPolicy.calculate_preference_score().

        Args:
            technician: Технік
            service_request: Заявка

        Returns:
            Оцінка (негативна = краще, позитивна = гірше)
        """
        return RoutingPolicy.calculate_preference_score(technician, service_request)


# ═══════════════════════════════════════════════════════════════════════════
# HELPER SERVICES
# ═══════════════════════════════════════════════════════════════════════════

class AssignmentService:
    """
    Domain Service для ручного призначення заявок.

    Використовується коли потрібно призначити заявку вручну
    (не через оптимізацію).
    """

    @staticmethod
    def assign_service_to_technician(
            service_request: ServiceRequest,
            technician: Technician
    ) -> None:
        """
        Призначити заявку техніку вручну.

        Валідує перед призначенням.

        Args:
            service_request: Заявка
            technician: Технік

        Raises:
            ValueError: Якщо призначення неможливе
        """
        # Validate
        can_assign, reason = RoutingPolicy.can_assign(technician, service_request)

        if not can_assign:
            raise ValueError(f"Cannot assign: {reason}")

        # Assign
        service_request.assign_to(technician.id)