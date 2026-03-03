"""

Моделі Route та RouteStop.
  Route     — оптимізований маршрут техніка на один день
  RouteStop — одна зупинка в маршруті (відвідування об'єкта)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, RouteStatus

if TYPE_CHECKING:
    from .service_site import ServiceSite
    from .technician import Technician


class Route(Base):
    """
    Оптимізований маршрут одного техніка на один календарний день.
    Aggregate Root у доменній моделі.

    Створюється як результат OR-Tools (CVRPTW solver).
    Lifecycle: draft → optimized → in_progress → completed

    UNIQUE (technician_id, route_date) — один технік, одна дата, один маршрут.
    """
    __tablename__ = "routes"

    # ── Ідентифікатор ─────────────────────────────────────────────────────────
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # ── Власник маршруту ──────────────────────────────────────────────────────
    technician_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("technicians.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK на техніка — маршрут завжди належить конкретному спеціалісту",
    )
    route_date: Mapped[date] = mapped_column(Date, nullable=False, comment="Дата виконання маршруту")

    # ── Стан ──────────────────────────────────────────────────────────────────
    status: Mapped[RouteStatus] = mapped_column(
        SAEnum(RouteStatus, name="route_status_enum"), default=RouteStatus.DRAFT,
        comment="Поточний стан у lifecycle",
    )

    # ── Метрики (заповнює OR-Tools solver) ────────────────────────────────────
    total_distance_km:            Mapped[Decimal | None] = mapped_column(Numeric(10, 2), comment="Загальний пробіг за день (км)")
    total_duration_minutes:       Mapped[int | None]     = mapped_column(Integer,        comment="Тривалість від першої до останньої зупинки (хв)")
    total_travel_time_minutes:    Mapped[int | None]     = mapped_column(Integer,        comment="Чистий час у дорозі між зупинками (хв)")
    stops_count:                  Mapped[int]               = mapped_column(Integer, default=0, comment="Кількість об'єктів у маршруті")
    optimization_time_seconds:    Mapped[Decimal | None] = mapped_column(Numeric(10, 3), comment="Час роботи OR-Tools solver (сек)")
    optimization_objective_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), comment="Значення цільової функції OR-Tools (менше — краще)")

    # ── Audit timestamps ──────────────────────────────────────────────────────
    created_at:   Mapped[datetime]           = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    optimized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Коли OR-Tools завершив оптимізацію")
    started_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Коли технік виїхав")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Коли завершив усі зупинки")

    # ── Зв'язки ───────────────────────────────────────────────────────────────
    technician: Mapped[Technician] = relationship("Technician", back_populates="routes")
    stops: Mapped[list[RouteStop]] = relationship(
        "RouteStop", back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStop.sequence_number",
        lazy="selectin",
    )

    # ── Індекси та обмеження ──────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("technician_id", "route_date", name="uq_route_technician_date"),
        Index("ix_routes_technician_date", "technician_id", "route_date"),
        Index("ix_routes_status",          "status"),
        Index("ix_routes_date",            "route_date"),
    )

    def __repr__(self) -> str:
        return f"<Route id={self.id} date={self.route_date} tech={self.technician_id}>"


class RouteStop(Base):
    """
    Одна зупинка в маршруті — відвідування конкретного об'єкта.

    Зберігає час прибуття/відбуття та метрики шляху від попередньої точки.
    Порядок зупинок — sequence_number (1, 2, 3, …).

    UNIQUE (route_id, sequence_number).
    """
    __tablename__ = "route_stops"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # ── Прив'язки ─────────────────────────────────────────────────────────────
    route_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False,
        comment="FK на маршрут. Каскадне видалення разом із маршрутом",
    )
    service_site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("service_sites.id", ondelete="CASCADE"), nullable=False,
        comment="FK на об'єкт, який відвідується на цій зупинці",
    )

    # ── Порядок та час ────────────────────────────────────────────────────────
    sequence_number: Mapped[int]      = mapped_column(Integer,              nullable=False, comment="Порядковий номер зупинки (від 1). CHECK: > 0")
    arrival_time:    Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Розрахунковий час прибуття на об'єкт")
    departure_time:  Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Час відбуття = arrival_time + duration_minutes")

    # ── Метрики від попередньої точки ─────────────────────────────────────────
    travel_time_from_previous_minutes: Mapped[int | None]     = mapped_column(Integer,        comment="Час у дорозі від попередньої зупинки (хв)")
    distance_from_previous_km:         Mapped[Decimal | None] = mapped_column(Numeric(10, 2), comment="Відстань від попередньої зупинки (км), Haversine")

    # ── Зв'язки ───────────────────────────────────────────────────────────────
    route:        Mapped[Route]       = relationship("Route",       back_populates="stops")
    service_site: Mapped[ServiceSite] = relationship("ServiceSite", back_populates="route_stops")

    # ── Індекси та обмеження ──────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("route_id", "sequence_number", name="uq_route_stop_sequence"),
        Index("ix_route_stops_route_id", "route_id"),
        Index("ix_route_stops_site_id",  "service_site_id"),
        CheckConstraint("sequence_number > 0",           name="ck_route_stop_positive_seq"),
        CheckConstraint("arrival_time < departure_time", name="ck_route_stop_times"),
    )

    def __repr__(self) -> str:
        return f"<RouteStop route={self.route_id} seq={self.sequence_number}>"