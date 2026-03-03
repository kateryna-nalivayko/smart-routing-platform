"""
app/adapters/orm/technician.py

Модель Technician — технічний спеціаліст компанії.
Всі поля відповідають Excel-листу «Technicians».
"""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, Numeric, String, Time
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, StartPoint, TransportMode

if TYPE_CHECKING:
    # Уникаємо циклічних імпортів — використовуємо лише для type hints
    from .route import Route
    from .service_site import ServiceSite


class Technician(Base):
    """
    Технічний спеціаліст компанії. Aggregate Root у доменній моделі.

    Інваріанти:
      — завжди має ім'я та принаймні одну навичку (technician_skills)
      — робочі години по днях тижня (NULL = вихідний)
      — координати — звичайні NUMERIC, geocoding в Python
    """
    __tablename__ = "technicians"

    # ── Ідентифікатор ─────────────────────────────────────────────────────────
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        comment="Первинний ключ — UUID v4, генерується на рівні Python",
    )

    # ── Основна інформація ────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Повне ім'я техніка. З Excel: «Name»",
    )

    # ── Домашня адреса + координати ───────────────────────────────────────────
    # Координати — звичайна пара чисел (без PostGIS).
    # Geocoding: adapters/geo/geocoding.py через AWS Location Service.
    home_address:   Mapped[str | None]     = mapped_column(String(500), comment="З Excel: «Home address»")
    home_latitude:  Mapped[Decimal | None] = mapped_column(Numeric(10, 8), comment="Широта (-90..90)")
    home_longitude: Mapped[Decimal | None] = mapped_column(Numeric(11, 8), comment="Довгота (-180..180)")

    # ── Офісна адреса + координати ────────────────────────────────────────────
    office_address:   Mapped[str | None]     = mapped_column(String(500), comment="З Excel: «Office address»")
    office_latitude:  Mapped[Decimal | None] = mapped_column(Numeric(10, 8), comment="Широта офісу")
    office_longitude: Mapped[Decimal | None] = mapped_column(Numeric(11, 8), comment="Довгота офісу")

    # ── Точки старту та фінішу ────────────────────────────────────────────────
    starts_from: Mapped[StartPoint] = mapped_column(
        SAEnum(StartPoint, name="start_point_enum"), default=StartPoint.HOME,
        comment="Звідки технік починає день. З Excel: «Starts from»",
    )
    finishes_at: Mapped[StartPoint] = mapped_column(
        SAEnum(StartPoint, name="start_point_enum"), default=StartPoint.HOME,
        comment="Де технік закінчує день. З Excel: «Finishes at»",
    )

    # ── Транспорт ─────────────────────────────────────────────────────────────
    transport_mode: Mapped[TransportMode] = mapped_column(
        SAEnum(TransportMode, name="transport_mode_enum"), default=TransportMode.CAR_VAN,
        comment="Вид транспорту. Для оптимізації розраховується лише car_van",
    )

    # ── Робочий час по днях тижня ─────────────────────────────────────────────
    # NULL в обох полях = технік у цей день не працює.
    # З Excel: секція «Acceptable visit time» (Mon–Sun × from/to).
    monday_start:    Mapped[time | None] = mapped_column(Time, comment="Понеділок — початок")
    monday_end:      Mapped[time | None] = mapped_column(Time, comment="Понеділок — кінець")
    tuesday_start:   Mapped[time | None] = mapped_column(Time, comment="Вівторок — початок")
    tuesday_end:     Mapped[time | None] = mapped_column(Time, comment="Вівторок — кінець")
    wednesday_start: Mapped[time | None] = mapped_column(Time, comment="Середа — початок")
    wednesday_end:   Mapped[time | None] = mapped_column(Time, comment="Середа — кінець")
    thursday_start:  Mapped[time | None] = mapped_column(Time, comment="Четвер — початок")
    thursday_end:    Mapped[time | None] = mapped_column(Time, comment="Четвер — кінець")
    friday_start:    Mapped[time | None] = mapped_column(Time, comment="П'ятниця — початок")
    friday_end:      Mapped[time | None] = mapped_column(Time, comment="П'ятниця — кінець")
    saturday_start:  Mapped[time | None] = mapped_column(Time, comment="Субота — початок (часто NULL)")
    saturday_end:    Mapped[time | None] = mapped_column(Time, comment="Субота — кінець")
    sunday_start:    Mapped[time | None] = mapped_column(Time, comment="Неділя — початок (зазвичай NULL)")
    sunday_end:      Mapped[time | None] = mapped_column(Time, comment="Неділя — кінець")

    # ── Ліміти робочого часу ──────────────────────────────────────────────────
    max_hours_per_day: Mapped[int] = mapped_column(
        Integer, default=8,
        comment="Максимум годин за день. З Excel: «Maximum hours of work per day for service»",
    )
    max_hours_per_week: Mapped[int] = mapped_column(
        Integer, default=40,
        comment="Максимум годин за тиждень. З Excel: «Maximum hours of work per week for service»",
    )

    # ── Перерва ───────────────────────────────────────────────────────────────
    break_duration_minutes: Mapped[int | None]  = mapped_column(Integer, comment="З Excel: «Min break per day, minutes»")
    break_earliest_start:   Mapped[time | None] = mapped_column(Time,    comment="З Excel: «Break not earlier than»")
    break_latest_start:     Mapped[time | None] = mapped_column(Time,    comment="З Excel: «Break not later than»")

    # ── Здібності (capabilities) — hard constraints при матчингу ──────────────
    can_do_physically_demanding: Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Can do physically demanding job»")
    skilled_in_living_walls:     Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Skilled in living walls»")
    comfortable_with_heights:    Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Comfortable with work at heights»")
    certified_with_lift:         Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Certified with using the lift»")
    has_pesticide_certification: Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Pesticide applicator certification»")
    is_citizen:                  Mapped[bool] = mapped_column(Boolean, default=False, comment="З Excel: «Is a citizen»")

    # ── Стан + Audit ──────────────────────────────────────────────────────────
    is_active:  Mapped[bool]     = mapped_column(Boolean, default=True, comment="False = звільнений або тимчасово недоступний")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Зв'язки ───────────────────────────────────────────────────────────────
    routes: Mapped[list[Route]] = relationship(
        "Route", back_populates="technician",
        cascade="all, delete-orphan", lazy="selectin",
    )
    current_sites: Mapped[list[ServiceSite]] = relationship(
        "ServiceSite", foreign_keys="ServiceSite.current_technician_id",
        back_populates="current_technician", lazy="selectin",
    )

    # ── Індекси та обмеження ──────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_technicians_name",        "name"),
        Index("ix_technicians_is_active",   "is_active"),
        Index("ix_technicians_home_coords", "home_latitude", "home_longitude"),
        CheckConstraint("home_latitude  IS NULL OR home_latitude  BETWEEN -90  AND 90",  name="ck_technicians_home_lat"),
        CheckConstraint("home_longitude IS NULL OR home_longitude BETWEEN -180 AND 180", name="ck_technicians_home_lon"),
    )

    def __repr__(self) -> str:
        return f"<Technician id={self.id} name={self.name!r}>"