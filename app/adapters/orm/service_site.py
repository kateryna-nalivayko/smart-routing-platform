"""
app/adapters/orm/service_site.py

Моделі ServiceSite та ServiceTimeWindow.
  ServiceSite       — клієнтський об'єкт, що потребує обслуговування
  ServiceTimeWindow — часове вікно доступності об'єкта по днях тижня
"""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Time,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import (
    Base,
    DayOfWeek,
    ServicePriority,
    ServiceStatus,
    TransportMode,
    VisitFrequency,
)

if TYPE_CHECKING:
    from .route import RouteStop
    from .technician import Technician


class ServiceSite(Base):
    """
    Клієнтський об'єкт, який потребує регулярного обслуговування.
    Aggregate Root у доменній моделі.

    Всі поля —  «Service sites».

    Constraint-логіка для OR-Tools:
      Hard: required_skills, capabilities, permit, forbidden_technicians
      Soft: preferred_technicians, current_technician
    """
    __tablename__ = "service_sites"

    # ── Ідентифікатор ─────────────────────────────────────────────────────────
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        comment="Первинний ключ — UUID v4",
    )

    # ── Код та назва ──────────────────────────────────────────────────────────
    site_code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True,
        comment="Унікальний код об'єкта. З Excel: «Site name or code» (напр. KY-0001-INT)",
    )
    site_name: Mapped[str | None] = mapped_column(String(255), comment="Назва об'єкта")

    # ── Адреса + координати ───────────────────────────────────────────────────
    address:   Mapped[str | None]     = mapped_column(String(500),   comment="З Excel: «Site address»")
    latitude:  Mapped[Decimal | None] = mapped_column(Numeric(10, 8), comment="Широта (-90..90)")
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(11, 8), comment="Довгота (-180..180)")

    # ── Доступ та транспорт ───────────────────────────────────────────────────
    best_accessed_by: Mapped[TransportMode | None] = mapped_column(
        SAEnum(TransportMode, name="transport_mode_enum"),
        comment="З Excel: «Site best accessed by»",
    )
    requires_permit: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment=(
            "Потрібен дозвіл служби безпеки. "
            "Якщо true — технік має бути у service_permit_holders. "
            "З Excel: «Entrance permit»"
        ),
    )

    # ── Параметри візиту ──────────────────────────────────────────────────────
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Планова тривалість візиту (хв). З Excel: «Est duration of the visit, minutes»",
    )
    visit_frequency: Mapped[VisitFrequency] = mapped_column(
        SAEnum(VisitFrequency, name="visit_frequency_enum"), default=VisitFrequency.X1,
        comment="Частота відвідувань. З Excel: «Visit frequency» (1x–5x a week)",
    )

    # ── Вимоги до виконавця (hard constraints) ────────────────────────────────
    is_physically_demanding:        Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Physically demanding job»")
    has_living_walls:               Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Has living walls»")
    requires_work_at_heights:       Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Work at heights»")
    requires_lift_usage:            Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Requires using the lift»")
    requires_pesticide_application: Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Requires application of pesticides»")
    requires_citizen_technician:    Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Requires a citizen technician»")

    # ── Стан та пріоритет ─────────────────────────────────────────────────────
    status: Mapped[ServiceStatus] = mapped_column(
        SAEnum(ServiceStatus, name="service_status_enum"), default=ServiceStatus.PENDING,
        comment="Стан заявки у lifecycle",
    )
    priority: Mapped[ServicePriority] = mapped_column(
        SAEnum(ServicePriority, name="service_priority_enum"), default=ServicePriority.NORMAL,
        comment="Пріоритет — вага штрафу за невиконання в OR-Tools",
    )

    # ── Прив'язані техніки (FK) ───────────────────────────────────────────────
    current_technician_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("technicians.id", ondelete="SET NULL"),
        comment="Поточний закріплений технік (soft constraint). З Excel: «Current technician»",
    )
    assigned_technician_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("technicians.id", ondelete="SET NULL"),
        comment="Технік, призначений після оптимізації OR-Tools",
    )

    # ── Audit ─────────────────────────────────────────────────────────────────
    assigned_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:   Mapped[datetime]           = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at:   Mapped[datetime]           = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Зв'язки ───────────────────────────────────────────────────────────────
    current_technician: Mapped[Technician | None] = relationship(
        "Technician", foreign_keys=[current_technician_id], back_populates="current_sites",
    )
    assigned_technician: Mapped[Technician | None] = relationship(
        "Technician", foreign_keys=[assigned_technician_id],
    )
    time_windows: Mapped[list[ServiceTimeWindow]] = relationship(
        "ServiceTimeWindow", back_populates="service_site",
        cascade="all, delete-orphan", lazy="selectin",
    )
    route_stops: Mapped[list[RouteStop]] = relationship(
        "RouteStop", back_populates="service_site", lazy="selectin",
    )

    # ── Індекси та обмеження ──────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_service_sites_site_code", "site_code"),
        Index("ix_service_sites_status",    "status"),
        Index("ix_service_sites_priority",  "priority"),
        Index("ix_service_sites_coords",    "latitude", "longitude"),
        CheckConstraint("duration_minutes > 0",                                      name="ck_service_sites_positive_duration"),
        CheckConstraint("latitude  IS NULL OR latitude  BETWEEN -90  AND 90",        name="ck_service_sites_lat"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180",       name="ck_service_sites_lon"),
    )

    def __repr__(self) -> str:
        return f"<ServiceSite id={self.id} site_code={self.site_code!r}>"


class ServiceTimeWindow(Base):
    """
    Часове вікно доступності об'єкта в конкретний день тижня.
    Один ServiceSite → багато ServiceTimeWindow (1-to-Many).

    Приклад (KY-0001-INT):
      monday 08:00–16:00, tuesday 08:00–16:00, ... (субота/неділя відсутні)

    OR-Tools використовує як time_window constraints.
    """
    __tablename__ = "service_time_windows"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    service_site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("service_sites.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK на об'єкт. Каскадне видалення разом з об'єктом",
    )
    day_of_week: Mapped[DayOfWeek] = mapped_column(
        SAEnum(DayOfWeek, name="day_of_week_enum"), nullable=False,
        comment="День тижня, у який діє це вікно",
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False, comment="Початок вікна (напр. 08:00)")
    end_time:   Mapped[time] = mapped_column(Time, nullable=False, comment="Кінець вікна (напр. 16:00). CHECK: > start_time")

    # ── Зв'язок ───────────────────────────────────────────────────────────────
    service_site: Mapped[ServiceSite] = relationship("ServiceSite", back_populates="time_windows")

    # ── Індекси та обмеження ──────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_service_time_windows_site_id", "service_site_id"),
        CheckConstraint("start_time < end_time", name="ck_time_window_valid"),
    )

    def __repr__(self) -> str:
        return f"<ServiceTimeWindow {self.day_of_week} {self.start_time}–{self.end_time}>"