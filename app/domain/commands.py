from dataclasses import dataclass
from datetime import date
from uuid import UUID

# ═══════════════════════════════════════════════════════════════════════════
# BASE COMMAND
# ═══════════════════════════════════════════════════════════════════════════

class Command:
    """Base class for all commands."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
# OPTIMIZATION COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OptimizeRoutes(Command):
    """
    Команда: Оптимізувати маршрути для конкретної дати.

    Використання:
        command = OptimizeRoutes(
            target_date=date(2026, 2, 25),
            technician_ids=[uuid1, uuid2],  # Optional
            service_request_ids=[uuid3, uuid4],  # Optional
            timeout_seconds=30
        )

        handler = optimize_routes_handler(command, uow)
    """
    target_date: date
    technician_ids: list[UUID] | None = None
    service_request_ids: list[UUID] | None = None
    timeout_seconds: int = 30


@dataclass(frozen=True)
class CancelOptimization(Command):
    """
    Команда: Скасувати оптимізацію.

    Використання:
        command = CancelOptimization(task_id=uuid1)
    """
    task_id: UUID


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE REQUEST COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AssignService(Command):
    """
    Команда: Призначити заявку техніку вручну.

    Використання:
        command = AssignService(
            service_request_id=uuid1,
            technician_id=uuid2
        )
    """
    service_request_id: UUID
    technician_id: UUID


@dataclass(frozen=True)
class UnassignService(Command):
    """
    Команда: Зняти призначення заявки.

    Використання:
        command = UnassignService(service_request_id=uuid1)
    """
    service_request_id: UUID


@dataclass(frozen=True)
class CompleteService(Command):
    """
    Команда: Позначити заявку як виконану.

    Використання:
        command = CompleteService(
            service_request_id=uuid1,
            notes="Все виконано успішно"
        )
    """
    service_request_id: UUID
    notes: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# TECHNICIAN COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CreateTechnician(Command):
    """
    Команда: Створити нового техніка.

    Примітка: Зазвичай техніки завантажуються з Excel,
    але ця команда може бути корисна для API.
    """
    name: str
    # ... інші поля за потреби


@dataclass(frozen=True)
class UpdateTechnician(Command):
    """
    Команда: Оновити дані техніка.
    """
    technician_id: UUID
    # ... поля для оновлення


@dataclass(frozen=True)
class DeactivateTechnician(Command):
    """
    Команда: Деактивувати техніка.

    Використання:
        command = DeactivateTechnician(technician_id=uuid1)
    """
    technician_id: UUID


# ═══════════════════════════════════════════════════════════════════════════
# ROUTE COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ApproveRoute(Command):
    """
    Команда: Затвердити маршрут.

    Використання:
        command = ApproveRoute(route_id=uuid1)
    """
    route_id: UUID


@dataclass(frozen=True)
class RejectRoute(Command):
    """
    Команда: Відхилити маршрут.

    Використання:
        command = RejectRoute(
            route_id=uuid1,
            reason="Маршрут не оптимальний"
        )
    """
    route_id: UUID
    reason: str
