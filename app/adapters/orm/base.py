from __future__ import annotations

import enum

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовий клас для всіх ORM-моделей."""
    pass


class SkillType(enum.StrEnum):
    """
    Тип сервісу, яким може займатись технік або якого потребує об'єкт.
    """
    INTERIOR = "interior"
    EXTERIOR = "exterior"
    FLORAL = "floral"


class SkillLevel(enum.StrEnum):
    """
    Рівень кваліфікації техніка або мінімальний рівень для об'єкта.
    junior < medior < senior
    """
    JUNIOR = "junior"
    MEDIOR = "medior"
    SENIOR = "senior"


class StartPoint(enum.StrEnum):
    """
    Звідки технік починає / де закінчує робочий день.
    """
    HOME = "home"
    OFFICE = "office"
    EITHER_WORKS = "either_works"


class TransportMode(enum.StrEnum):
    """
    Вид транспорту для переміщення між об'єктами.
    """
    CAR_VAN = "car_van"
    WALK = "walk"
    DRIVE_TO_HUB_AND_WALK = "drive_to_hub_and_walk"


class VisitFrequency(enum.StrEnum):
    """
    Частота відвідування об'єкта на тиждень.
    """
    X1 = "1x_week"
    X2 = "2x_week"
    X3 = "3x_week"
    X4 = "4x_week"
    X5 = "5x_week"


class DayOfWeek(enum.StrEnum):
    """День тижня."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class ServiceStatus(enum.StrEnum):
    """Стан заявки у процесі виконання."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ServicePriority(enum.StrEnum):
    """Пріоритет заявки для оптимізатора."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RouteStatus(enum.StrEnum):
    """Стан маршруту техніка на день."""
    DRAFT = "draft"
    OPTIMIZED = "optimized"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskStatus(enum.StrEnum):
    """Стан фонової Dramatiq-задачі оптимізації."""
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
