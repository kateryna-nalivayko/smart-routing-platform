"""
app/adapters/orm/__init__.py

Публічний інтерфейс пакету orm.
Імпортуй звідси — не з окремих файлів.

Приклад:
    from app.adapters.orm import Base, Technician, ServiceSite, Route
"""

# Base — має імпортуватись першим (щоб metadata зібрався до моделей)
# Association tables — потрібні для роботи M2M relationship
from .associations import (
    service_forbidden_technicians,
    service_permit_holders,
    service_preferred_technicians,
    service_required_skills,
    technician_skills,
)
from .base import (
    Base,
    DayOfWeek,
    RouteStatus,
    ServicePriority,
    ServiceStatus,
    SkillLevel,
    SkillType,
    StartPoint,
    TaskStatus,
    TransportMode,
    VisitFrequency,
)
from .optimization import OptimizationTask
from .route import Route, RouteStop
from .service_site import ServiceSite, ServiceTimeWindow

# Моделі — порядок важливий через forward references
from .technician import Technician

__all__ = [
    # Base
    "Base",
    # Enums
    "SkillType", "SkillLevel", "StartPoint", "TransportMode",
    "VisitFrequency", "DayOfWeek", "ServiceStatus", "ServicePriority",
    "RouteStatus", "TaskStatus",
    # Association tables
    "technician_skills", "service_required_skills",
    "service_preferred_technicians", "service_forbidden_technicians",
    "service_permit_holders",
    # Models
    "Technician", "ServiceSite", "ServiceTimeWindow",
    "Route", "RouteStop", "OptimizationTask",
]