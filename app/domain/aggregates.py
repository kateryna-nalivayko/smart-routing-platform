"""
Smart Routing Platform - Complete Domain Layer

Інтеграція з:
- OR-Tools для оптимізації маршрутів
- Дані з Excel (Service Sites, Technicians)

Структура:
1. Value Objects - незмінні об'єкти значень
2. Entities - об'єкти з ідентичністю
3. Aggregates - кореневі агрегати
4. Domain Events - події домену
5. Commands - команди
6. Domain Exceptions - доменні винятки
7. Domain Policies - бізнес-правила
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.domain.events import (  #
    RouteCompleted,
    RouteOptimized,
    RouteStarted,
    ServiceAssigned,
    ServiceCancelled,
    ServiceCompleted,
    ServiceStarted,
    StopAdded,
    TechnicianActivated,
    TechnicianDeactivated,
)
from app.domain.exceptions import (  #
    InvalidRouteOperation,
    InvalidServiceStatusTransition,
    ServiceTimeWindowViolation,
)
from app.domain.value_objects import (
    Break,
    DayOfWeek,
    Distance,
    Duration,
    Location,
    OptimizationMetrics,
    RouteStatus,
    ServiceDuration,
    ServicePriority,
    ServiceRequirements,
    ServiceStatus,
    Skill,
    StartEndPoint,
    TechnicianCapabilities,
    TimeWindow,
    TransportMode,
    VisitFrequency,
    WeeklySchedule,
)


# =============================================================================
# 1. VALUE OBJECTS
# 3. AGGREGATES (Aggregate Roots)
# =============================================================================

class DomainEvent:
    pass


@dataclass
class Technician:
    id: str
    name: str
    home_location: Location
    office_location: Location | None

    skills: frozenset[Skill]
    capabilities: TechnicianCapabilities

    weekly_schedule: WeeklySchedule

    daily_break: Break | None
    max_work_hours_per_day: int = 8
    max_work_hours_per_week: int = 40

    starts_from: StartEndPoint = StartEndPoint.HOME
    finishes_at: StartEndPoint = StartEndPoint.HOME

    # Транспорт
    transport_mode: TransportMode = TransportMode.CAR_VAN

    # Стан
    is_active: bool = True

    # Aggregate internal state
    _version: int = field(default=0, init=False, repr=False)
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self):
        if not self.id or not self.id.strip():
            raise ValueError("Technician ID cannot be empty")
        if not self.name or not self.name.strip():
            raise ValueError("Technician name cannot be empty")
        if not self.skills:
            raise ValueError("Technician must have at least one skill")

    def has_skill(self, required_skill: Skill) -> bool:
        """Перевірка наявності навички"""
        return any(skill.can_handle(required_skill) for skill in self.skills)

    def meets_capabilities(self, requirements: ServiceRequirements) -> bool:
        checks = [
            (not requirements.is_physically_demanding or self.capabilities.can_do_physically_demanding),
            (not requirements.has_living_walls or self.capabilities.skilled_in_living_walls),
            (not requirements.requires_work_at_heights or self.capabilities.comfortable_with_heights),
            (not requirements.requires_lift_usage or self.capabilities.certified_with_lift),
            (not requirements.requires_pesticide_application or self.capabilities.has_pesticide_certification),
            (not requirements.requires_citizen_technician or self.capabilities.is_citizen),
        ]
        return all(checks)

    def can_work_on_date(self, date: datetime) -> bool:
        """Чи може працювати в цю дату"""
        if not self.is_active:
            return False

        day_of_week = DayOfWeek(date.strftime('%A').lower())
        return self.weekly_schedule.is_working_on(day_of_week)

    def get_working_window_for_date(self, date: datetime) -> TimeWindow | None:
        """Отримати робоче вікно для дати"""
        day_of_week = DayOfWeek(date.strftime('%A').lower())
        working_hours = self.weekly_schedule.get_working_hours_for_day(day_of_week)

        if not working_hours:
            return None

        return working_hours.get_working_window_for_date(date)

    def get_start_location(self) -> Location:
        """Отримати початкову локацію"""
        if self.starts_from == StartEndPoint.HOME:
            return self.home_location
        elif self.starts_from == StartEndPoint.OFFICE and self.office_location:
            return self.office_location
        return self.home_location  # Fallback

    def get_end_location(self) -> Location:
        """Отримати кінцеву локацію"""
        if self.finishes_at == StartEndPoint.HOME:
            return self.home_location
        elif self.finishes_at == StartEndPoint.OFFICE and self.office_location:
            return self.office_location
        return self.home_location  # Fallback

    def deactivate(self):

        if not self.is_active:
            return
        self.is_active = False
        self._add_event(TechnicianDeactivated(technician_id=self.id))

    def activate(self):

        if self.is_active:
            return
        self.is_active = True
        self._add_event(TechnicianActivated(technician_id=self.id))

    def _add_event(self, event: DomainEvent):

        self._events.append(event)
        self._version += 1

    def collect_events(self) -> list[DomainEvent]:

        events = self._events.copy()
        self._events.clear()
        return events

    def __eq__(self, other):
        if not isinstance(other, Technician):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)


@dataclass
class ServiceRequest:
    """
    Aggregate Root: Заявка на обслуговування
    Інваріант: Завжди має унікальний ID, локацію та часове вікно

    Mapped з Excel sheet "Service sites"
    """
    id: str
    site_code: str
    site_name: str | None
    location: Location

    # Часові вікна з Excel (Acceptable visit time)
    time_windows: list[TimeWindow]

    required_skills: frozenset[Skill]
    requirements: ServiceRequirements

    # Тривалість та частота з Excel
    duration: ServiceDuration
    visit_frequency: VisitFrequency

    # Пріоритет
    priority: ServicePriority = ServicePriority.NORMAL

    # Matchmaking preferences з Excel
    preferred_technician_ids: set[str] = field(default_factory=set)
    forbidden_technician_ids: set[str] = field(default_factory=set)
    current_technician_id: str | None = None  # З Excel "Current technician"

    # Транспорт та доступ з Excel
    best_accessed_by: TransportMode | None = None
    requires_permit: bool = False
    permit_holders: set[str] = field(default_factory=set)  # IDs техніків з дозволом

    # Стан
    status: ServiceStatus = ServiceStatus.PENDING
    assigned_technician_id: str | None = None
    assigned_at: datetime | None = None
    completed_at: datetime | None = None

    # Aggregate internal state
    _version: int = field(default=0, init=False, repr=False)
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self):
        if not self.id or not self.id.strip():
            raise ValueError("Service Request ID cannot be empty")
        if not self.required_skills:
            raise ValueError("Service request must require at least one skill")
        if not self.time_windows:
            raise ValueError("Service request must have at least one time window")

        # Перевірка, що тривалість вміщується хоча б в одне вікно
        if not any(tw.can_fit_duration(self.duration.minutes) for tw in self.time_windows):
            raise ValueError(
                f"Service duration {self.duration.minutes} minutes does not fit "
                f"in any time window"
            )

    def can_be_served_by(self, technician: Technician) -> tuple[bool, str | None]:

        if not technician.is_active:
            return False, "Technician is not active"

        if technician.id in self.forbidden_technician_ids:
            return False, f"Technician {technician.name} is forbidden for this site"

        # Перевірка навичок
        if not all(technician.has_skill(skill) for skill in self.required_skills):
            missing_skills = [
                str(skill) for skill in self.required_skills
                if not technician.has_skill(skill)
            ]
            return False, f"Missing skills: {', '.join(missing_skills)}"

        # Перевірка здібностей
        if not technician.meets_capabilities(self.requirements):
            return False, "Does not meet capability requirements"

        # Перевірка дозволу
        if self.requires_permit and technician.id not in self.permit_holders:
            return False, "Technician does not have required permit"

        return True, None

    def calculate_preference_score(self, technician: Technician) -> int:

        score = 0

        # Бонус за preferred technician
        if technician.id in self.preferred_technician_ids:
            score += 100

        # Великий бонус, якщо це поточний технічник
        if technician.id == self.current_technician_id:
            score += 200

        # Штраф за forbidden (але вже має відсіятись раніше)
        if technician.id in self.forbidden_technician_ids:
            score -= 1000

        return score

    def assign_to(self, technician_id: str, at_time: datetime):

        if self.status not in [ServiceStatus.PENDING, ServiceStatus.ASSIGNED]:
            raise InvalidServiceStatusTransition(
                f"Cannot assign service in status {self.status}"
            )

        old_technician_id = self.assigned_technician_id

        self.assigned_technician_id = technician_id
        self.assigned_at = at_time
        self.status = ServiceStatus.ASSIGNED

        self._add_event(ServiceAssigned(
            service_request_id=self.id,
            technician_id=technician_id,
            previous_technician_id=old_technician_id,
            assigned_at=at_time
        ))

    def start_work(self, at_time: datetime):
        """Почати виконання роботи"""
        if self.status != ServiceStatus.ASSIGNED:
            raise InvalidServiceStatusTransition(
                f"Cannot start work on service in status {self.status}"
            )

        # Перевірка, що час в межах хоча б одного вікна
        if not any(tw.contains(at_time) for tw in self.time_windows):
            raise ServiceTimeWindowViolation(
                f"Work start time {at_time} is outside all time windows"
            )

        self.status = ServiceStatus.IN_PROGRESS

        self._add_event(ServiceStarted(
            service_request_id=self.id,
            technician_id=self.assigned_technician_id,
            started_at=at_time
        ))

    def complete(self, at_time: datetime):
        """Завершити виконання роботи"""
        if self.status != ServiceStatus.IN_PROGRESS:
            raise InvalidServiceStatusTransition(
                f"Cannot complete service in status {self.status}"
            )

        self.status = ServiceStatus.COMPLETED
        self.completed_at = at_time

        self._add_event(ServiceCompleted(
            service_request_id=self.id,
            technician_id=self.assigned_technician_id,
            completed_at=at_time
        ))

    def cancel(self, reason: str | None = None):
        """Скасувати заявку"""
        if self.status in [ServiceStatus.COMPLETED, ServiceStatus.CANCELLED]:
            raise InvalidServiceStatusTransition(
                f"Cannot cancel service in status {self.status}"
            )

        old_status = self.status
        self.status = ServiceStatus.CANCELLED

        self._add_event(ServiceCancelled(
            service_request_id=self.id,
            previous_status=old_status,
            reason=reason
        ))

    def _add_event(self, event: DomainEvent):
        """Додати доменну подію"""
        self._events.append(event)
        self._version += 1

    def collect_events(self) -> list[DomainEvent]:
        """Зібрати та очистити події"""
        events = self._events.copy()
        self._events.clear()
        return events

    def __eq__(self, other):
        if not isinstance(other, ServiceRequest):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)


@dataclass
class RouteStop:
    """
    Зупинка в маршруті техніка - відвідування одного сервісного об'єкта.

    Value object всередині Route aggregate.

    Приклад:
        stop = RouteStop(
            service_request_id=uuid4(),
            sequence_number=1,
            arrival_time=datetime(2026, 2, 25, 9, 0),
            departure_time=datetime(2026, 2, 25, 10, 30),
            travel_time_from_previous=Duration(15),
            distance_from_previous=Distance(Decimal("5.2"))
        )
    """
    service_request_id: UUID
    sequence_number: int

    # Часи відвідування
    arrival_time: datetime
    departure_time: datetime

    # Метрики від попередньої зупинки
    travel_time_from_previous: Duration | None = None
    distance_from_previous: Distance | None = None

    def __post_init__(self):
        """Валідація інваріантів"""
        if self.sequence_number < 0:
            raise ValueError(f"Sequence number cannot be negative: {self.sequence_number}")

        if self.arrival_time >= self.departure_time:
            raise ValueError(
                f"Arrival time must be before departure: "
                f"{self.arrival_time} >= {self.departure_time}"
            )

    @property
    def service_duration(self) -> Duration:
        """Тривалість обслуговування на цій зупинці"""
        delta = self.departure_time - self.arrival_time
        minutes = int(delta.total_seconds() / 60)
        return Duration(minutes)

    def __repr__(self) -> str:
        return (
            f"RouteStop(seq={self.sequence_number}, "
            f"service={str(self.service_request_id)[:8]}..., "
            f"duration={self.service_duration})"
        )


@dataclass
class Route:
    id: str
    technician_id: str
    date: date
    stops: list[RouteStop] = field(default_factory=list)

    # Стан
    status: RouteStatus = RouteStatus.DRAFT

    # Метрики (заповнюються після оптимізації)
    optimization_metrics: OptimizationMetrics | None = None
    total_distance: Distance | None = None
    total_duration_minutes: int | None = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    optimized_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Aggregate internal state
    _version: int = field(default=0, init=False, repr=False)
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self):
        if not self.id or not self.id.strip():
            raise ValueError("Route ID cannot be empty")
        if not self.technician_id or not self.technician_id.strip():
            raise ValueError("Technician ID cannot be empty")

    def add_stop(
            self,
            service_request: ServiceRequest,
            arrival_time: datetime,
            departure_time: datetime,
            sequence_number: int | None = None,
            travel_time_from_previous: int | None = None,
            distance_from_previous: Distance | None = None
    ):
        """Додати зупинку до маршруту"""
        if self.status not in [RouteStatus.DRAFT, RouteStatus.OPTIMIZED]:
            raise InvalidRouteOperation(
                f"Cannot add stops to route in status {self.status}"
            )

        if sequence_number is None:
            sequence_number = len(self.stops) + 1

        stop = RouteStop(
            service_request_id=service_request.id,
            location=service_request.location,
            arrival_time=arrival_time,
            departure_time=departure_time,
            sequence_number=sequence_number,
            service_duration=service_request.duration,
            travel_time_from_previous=travel_time_from_previous,
            distance_from_previous=distance_from_previous
        )

        self.stops.append(stop)
        self.stops.sort(key=lambda s: s.sequence_number)

        self._add_event(StopAdded(
            route_id=self.id,
            service_request_id=service_request.id,
            sequence_number=sequence_number
        ))

    def optimize(self, metrics: OptimizationMetrics, technician_home: Location):
        """Оптимізувати маршрут (викликається після OR-Tools)"""
        if self.status not in [RouteStatus.DRAFT, RouteStatus.OPTIMIZED]:
            raise InvalidRouteOperation(
                f"Cannot optimize route in status {self.status}"
            )

        self.status = RouteStatus.OPTIMIZED
        self.optimization_metrics = metrics
        self.optimized_at = datetime.utcnow()

        # Розрахувати загальні метрики
        self.total_distance = self.calculate_total_distance(technician_home)
        self.total_duration_minutes = self.calculate_total_duration()

        self._add_event(RouteOptimized(
            route_id=self.id,
            technician_id=self.technician_id,
            metrics=metrics,
            optimized_at=self.optimized_at
        ))

    def start(self):
        """Почати виконання маршруту"""
        if self.status != RouteStatus.OPTIMIZED:
            raise InvalidRouteOperation(
                f"Cannot start route in status {self.status}. Route must be optimized first."
            )

        if not self.stops:
            raise InvalidRouteOperation("Cannot start route with no stops")

        self.status = RouteStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()

        self._add_event(RouteStarted(
            route_id=self.id,
            technician_id=self.technician_id
        ))

    def complete(self):
        """Завершити маршрут"""
        if self.status != RouteStatus.IN_PROGRESS:
            raise InvalidRouteOperation(
                f"Cannot complete route in status {self.status}"
            )

        self.status = RouteStatus.COMPLETED
        self.completed_at = datetime.utcnow()

        self._add_event(RouteCompleted(
            route_id=self.id,
            technician_id=self.technician_id
        ))

    def calculate_total_distance(self, technician_home: Location) -> Distance:
        """Розрахувати загальну відстань маршруту"""
        if not self.stops:
            return Distance(kilometers=Decimal('0'))

        total = Distance(kilometers=Decimal('0'))

        # Від дому до першої зупинки
        total = total + technician_home.distance_to(self.stops[0].location)

        # Між зупинками
        for i in range(len(self.stops) - 1):
            distance = self.stops[i].location.distance_to(self.stops[i + 1].location)
            total = total + distance

        # Від останньої зупинки додому
        total = total + self.stops[-1].location.distance_to(technician_home)

        return total

    def calculate_total_duration(self) -> int:
        """Розрахувати загальну тривалість маршруту в хвилинах"""
        if not self.stops:
            return 0

        start = self.stops[0].arrival_time
        end = self.stops[-1].departure_time

        return int((end - start).total_seconds() / 60)

    def _add_event(self, event: DomainEvent):
        """Додати доменну подію"""
        self._events.append(event)
        self._version += 1

    def collect_events(self) -> list[DomainEvent]:
        """Зібрати та очистити події"""
        events = self._events.copy()
        self._events.clear()
        return events

    def __eq__(self, other):
        if not isinstance(other, Route):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)
