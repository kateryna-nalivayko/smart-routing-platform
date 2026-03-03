"""
Модель OptimizationTask — відстеження фонової задачі оптимізації маршрутів.

Потік роботи (Dramatiq + RabbitMQ):
  1. FastAPI: POST /optimize → створює запис (status=QUEUED)
  2. Dramatiq публікує повідомлення в RabbitMQ → зберігає dramatiq_message_id
  3. Воркер бере задачу → status=PROCESSING, started_at=now()
  4a. Успіх  → status=SUCCESS, заповнює routes_created, total_distance_km
  4b. Помилка → status=FAILED, error_message=traceback
  4c. Retry   → status=RETRYING, retry_count += 1
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TaskStatus


class OptimizationTask(Base):
    """
    Журнальний запис про одну задачу оптимізації маршрутів.

    Не має FK-зв'язків навмисно — OR-Tools отримує техніків та об'єкти
    через репозиторій у момент виконання. Результат зберігається в
    таблицях routes та route_stops.
    """
    __tablename__ = "optimization_tasks"

    # ── Ідентифікатор ─────────────────────────────────────────────────────────
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        comment="Первинний ключ — повертається клієнту одразу після POST /optimize",
    )

    # ── Параметри задачі ──────────────────────────────────────────────────────
    target_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="Дата, для якої будується розклад",
    )
    technician_ids: Mapped[str | None] = mapped_column(
        String(4000),
        comment="JSON-масив UUID техніків. NULL = всі активні техніки",
    )
    service_site_ids: Mapped[str | None] = mapped_column(
        String(4000),
        comment="JSON-масив UUID об'єктів. NULL = всі pending-заявки",
    )

    # ── Параметри OR-Tools solver ─────────────────────────────────────────────
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=30,
        comment="Ліміт часу для OR-Tools solver (сек)",
    )
    first_solution_strategy: Mapped[str] = mapped_column(
        String(100), default="PATH_CHEAPEST_ARC",
        comment="Стратегія першого рішення. Напр: PATH_CHEAPEST_ARC, PARALLEL_CHEAPEST_INSERTION",
    )
    local_search_metaheuristic: Mapped[str] = mapped_column(
        String(100), default="GUIDED_LOCAL_SEARCH",
        comment="Метаевристика локального пошуку. Напр: GUIDED_LOCAL_SEARCH, SIMULATED_ANNEALING",
    )

    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status_enum"), default=TaskStatus.QUEUED,
        comment="Поточний стан задачі в черзі Dramatiq",
    )
    dramatiq_message_id: Mapped[str | None] = mapped_column(
        String(255),
        comment="ID повідомлення в RabbitMQ — для трасування та відлагодження",
    )

    routes_created: Mapped[int | None] = mapped_column(Integer, comment="Скільки маршрутів побудовано")
    sites_unassigned: Mapped[int | None] = mapped_column(Integer, comment="Скільки об'єктів не вдалось включити")
    total_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2),
                                                              comment="Загальний пробіг по всіх маршрутах (км)")
    error_message: Mapped[str | None] = mapped_column(String(2000),
                                                      comment="Повідомлення про помилку або traceback (при FAILED)")

    retry_count: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="Кількість повторних спроб — Dramatiq збільшує при кожному retry",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow,
                                                 comment="Час створення (POST /optimize)")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Коли воркер взяв задачу")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                          comment="Час завершення (успіх або провал)")

    __table_args__ = (
        Index("ix_opt_tasks_status", "status"),
        Index("ix_opt_tasks_target_date", "target_date"),
        Index("ix_opt_tasks_message_id", "dramatiq_message_id"),
    )

    def __repr__(self) -> str:
        return f"<OptimizationTask id={self.id} date={self.target_date} status={self.status}>"
