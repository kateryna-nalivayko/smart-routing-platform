from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.domain.value_objects import OptimizationMetrics


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """
    Базовий клас для всіх доменних подій.

    kw_only=True дозволяє дочірнім класам мати обов'язкові поля
    без конфлікту з default полями базового класу.
    """
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ServiceAssigned(DomainEvent):
    service_request_id: UUID
    technician_id: UUID
    previous_technician_id: UUID | None = None
    assigned_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ServiceStarted(DomainEvent):
    """Подія: Початок виконання заявки"""
    service_request_id: UUID
    technician_id: UUID
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ServiceCompleted(DomainEvent):
    """Подія: Заявка виконана"""
    service_request_id: UUID
    technician_id: UUID
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ServiceCancelled(DomainEvent):
    """Подія: Заявка скасована"""
    service_request_id: UUID
    previous_status: str  # Статус як строка
    reason: str | None = None


@dataclass(frozen=True)
class RouteOptimized(DomainEvent):
    """Подія: Маршрут оптимізований"""
    route_id: UUID
    technician_id: UUID
    metrics: OptimizationMetrics  # Forward reference
    optimized_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class RouteStarted(DomainEvent):
    """Подія: Початок виконання маршруту"""
    route_id: UUID
    technician_id: UUID
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class RouteCompleted(DomainEvent):
    """Подія: Маршрут завершено"""
    route_id: UUID
    technician_id: UUID
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class StopAdded(DomainEvent):
    """Подія: Зупинка додана до маршруту"""
    route_id: UUID
    service_request_id: UUID
    sequence_number: int


@dataclass(frozen=True)
class TechnicianActivated(DomainEvent):
    """Подія: Технічник активований"""
    technician_id: UUID


@dataclass(frozen=True)
class TechnicianDeactivated(DomainEvent):
    """Подія: Технічник деактивований"""
    technician_id: UUID
    reason: str | None = None


@dataclass(frozen=True)
class OptimizationRequested(DomainEvent):
    """Подія: Запит на оптимізацію"""
    target_date: date
    technician_ids: list[UUID] | None = None
    service_request_ids: list[UUID] | None = None


@dataclass(frozen=True)
class OptimizationCompleted(DomainEvent):
    """Подія: Оптимізація завершена"""
    routes_created: int
    total_metrics: OptimizationMetrics  # Forward reference
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class OptimizationFailedEvent(DomainEvent):
    reason: str
    error_details: str | None = None
    target_date: date | None = None
