"""
Smart Routing Platform - Complete Domain Layer

Інтеграція з:
- OR-Tools для оптимізації маршрутів
- Дані  (Service Sites, Technicians)

Структура:
1. Value Objects - незмінні об'єкти значень
2. Entities - об'єкти з ідентичністю
3. Aggregates - кореневі агрегати
4. Domain Events - події домену
5. Commands - команди
6. Domain Exceptions - доменні винятки
7. Domain Policies - бізнес-правила
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum

import pandas as pd

# =============================================================================
# 1. VALUE OBJECTS
# =============================================================================

# --------------- ENUMS ---------------

class SkillLevel(StrEnum):
    """Рівень кваліфікації (junior/medior/senior)"""
    JUNIOR = "junior"
    MEDIOR = "medior"  # Використовується в Excel замість MIDDLE
    SENIOR = "senior"

    @property
    def hierarchy_value(self) -> int:
        """Ієрархія для порівняння"""
        return {
            SkillLevel.JUNIOR: 1,
            SkillLevel.MEDIOR: 2,
            SkillLevel.SENIOR: 3,
        }[self]


class ServiceType(StrEnum):
    """Тип сервісу (interior/exterior/floral)"""
    INTERIOR = "interior"
    EXTERIOR = "exterior"
    FLORAL = "floral"


class ServicePriority(StrEnum):
    """Пріоритет заявки"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

    def weight(self) -> int:
        """Вага для оптимізації"""
        return {
            ServicePriority.LOW: 1,
            ServicePriority.NORMAL: 2,
            ServicePriority.HIGH: 3,
            ServicePriority.URGENT: 5
        }[self]


class ServiceStatus(StrEnum):
    """Статус виконання заявки"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RouteStatus(StrEnum):
    """Статус маршруту"""
    DRAFT = "draft"
    OPTIMIZED = "optimized"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TransportMode(StrEnum):
    """Режим транспортування ()"""
    CAR_VAN = "car/van"
    WALK = "walk"
    DRIVE_TO_HUB_AND_WALK = "drive to a hub and then walk"


class StartEndPoint(StrEnum):
    """Точка старту/фінішу техніка ()"""
    HOME = "home"
    OFFICE = "office"
    EITHER_WORKS = "either works"


class PermitDifficulty(StrEnum):
    """Складність отримання дозволу ()"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class VisitFrequency(StrEnum):
    """Частота візитів"""
    ONCE_A_WEEK = "1x a week"
    TWICE_A_WEEK = "2x a week"
    THRICE_A_WEEK = "3x a week"
    FOUR_TIMES_A_WEEK = "4x a week"
    FIVE_TIMES_A_WEEK = "5x a week"

    def times_per_week(self) -> int:
        """Кількість разів на тиждень"""
        return {
            VisitFrequency.ONCE_A_WEEK: 1,
            VisitFrequency.TWICE_A_WEEK: 2,
            VisitFrequency.THRICE_A_WEEK: 3,
            VisitFrequency.FOUR_TIMES_A_WEEK: 4,
            VisitFrequency.FIVE_TIMES_A_WEEK: 5,
        }[self]

    @staticmethod
    def from_string(freq_str: str) -> VisitFrequency:
        """Парсинг з рядка Excel"""
        mapping = {
            "1x a week": VisitFrequency.ONCE_A_WEEK,
            "2x a week": VisitFrequency.TWICE_A_WEEK,
            "3x a week": VisitFrequency.THRICE_A_WEEK,
            "4x a week": VisitFrequency.FOUR_TIMES_A_WEEK,
            "5x a week": VisitFrequency.FIVE_TIMES_A_WEEK,
        }
        return mapping.get(freq_str.lower(), VisitFrequency.ONCE_A_WEEK)


class PhysicalDemand(StrEnum):
    """Фізична складність роботи"""
    LIGHT = "light"
    MEDIUM = "medium"
    HARD = "hard"


class DayOfWeek(StrEnum):
    """День тижня"""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# --------------- VALUE OBJECTS ---------------

@dataclass(frozen=True)
class Location:
    """Географічні координати об'єкта або техніка."""
    latitude: float
    longitude: float
    address: str | None = None

    def __post_init__(self):
        if not (-90 <= self.latitude <= 90):
            raise ValueError(f"Latitude must be between -90 and 90, got {self.latitude}")
        if not (-180 <= self.longitude <= 180):
            raise ValueError(f"Longitude must be between -180 and 180, got {self.longitude}")

    def distance_to(self, other: Location) -> Distance:
        """Haversine formula для відстані між двома точками"""
        from math import atan2, cos, radians, sin, sqrt

        R = 6371.0  # Радіус Землі в км

        lat1, lon1 = float(self.latitude), float(self.longitude)
        lat2, lon2 = float(other.latitude), float(other.longitude)

        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)

        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance_km = R * c
        return Distance(kilometers=Decimal(str(round(distance_km, 2))))

    def to_postgis_point(self) -> str:
        """Конвертація в PostGIS POINT формат"""
        return f"POINT({self.longitude} {self.latitude})"

    @staticmethod
    def from_excel(address: str) -> Location | None:
        """
        Парсинг локації .
        Потребує geocoding через AWS Location Service або Google Maps API
        """
        # Placeholder - потрібно буде інтегрувати з geocoding service
        return None

    def __str__(self):
        if self.address:
            return f"{self.address} ({self.latitude}, {self.longitude})"
        return f"({self.latitude}, {self.longitude})"


@dataclass(frozen=True)
class TimeWindow:
    """Value Object для часового вікна доступності (для OR-Tools)"""
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError(f"Start time {self.start} must be before end time {self.end}")

    def overlaps_with(self, other: TimeWindow) -> bool:
        """Чи перетинаються два часові вікна"""
        return self.start < other.end and other.start < self.end

    def contains(self, dt: datetime) -> bool:
        """Чи містить часове вікно вказаний час"""
        return self.start <= dt <= self.end

    def duration_minutes(self) -> int:
        """Тривалість вікна в хвилинах (для OR-Tools)"""
        return int((self.end - self.start).total_seconds() / 60)

    def can_fit_duration(self, duration_minutes: int) -> bool:
        """Чи вміщується вказана тривалість"""
        return self.duration_minutes() >= duration_minutes

    def to_ortools_window(self) -> tuple[int, int]:
        """Конвертація в OR-Tools time window (секунди від початку дня)"""
        start_seconds = int((self.start - datetime.combine(self.start.date(), time.min)).total_seconds())
        end_seconds = int((self.end - datetime.combine(self.end.date(), time.min)).total_seconds())
        return (start_seconds, end_seconds)

    def __str__(self):
        return f"{self.start.strftime('%Y-%m-%d %H:%M')} - {self.end.strftime('%H:%M')}"


@dataclass(frozen=True)
class Skill:
    """Value Object для навички/компетенції"""
    service_type: ServiceType
    level: SkillLevel

    def can_handle(self, required_skill: Skill) -> bool:
        """Чи може технічник з цією навичкою виконати роботу"""
        if self.service_type != required_skill.service_type:
            return False

        return self.level.hierarchy_value >= required_skill.level.hierarchy_value

    def __hash__(self):
        return hash((self.service_type, self.level))

    def __str__(self):
        return f"{self.service_type.value} - {self.level.value}"

    @staticmethod
    def from_excel(skill_str: str) -> Skill | None:
        """
        Парсинг  формату: "interior - senior", "exterior - medior"
        """
        if not skill_str or pd.isna(skill_str):
            return None

        parts = skill_str.strip().lower().split('-')
        if len(parts) != 2:
            return None

        service_type_str, level_str = parts[0].strip(), parts[1].strip()

        try:
            service_type = ServiceType(service_type_str)
            level = SkillLevel(level_str)
            return Skill(service_type=service_type, level=level)
        except ValueError:
            return None


@dataclass(frozen=True)
class WorkingHours:
    """Value Object для робочих годин"""
    start_time: time
    end_time: time

    def __post_init__(self):
        if self.start_time >= self.end_time:
            raise ValueError("Start time must be before end time")

    def is_working_time(self, dt: datetime) -> bool:
        """Чи є вказаний час робочим"""
        current_time = dt.time()
        return self.start_time <= current_time <= self.end_time

    def get_working_window_for_date(self, date: datetime) -> TimeWindow:
        """Отримати TimeWindow для конкретної дати"""
        start_dt = datetime.combine(date.date(), self.start_time)
        end_dt = datetime.combine(date.date(), self.end_time)
        return TimeWindow(start=start_dt, end=end_dt)

    def duration_hours(self) -> float:
        """Тривалість робочого дня в годинах"""
        start_seconds = self.start_time.hour * 3600 + self.start_time.minute * 60
        end_seconds = self.end_time.hour * 3600 + self.end_time.minute * 60
        return (end_seconds - start_seconds) / 3600

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"


@dataclass(frozen=True)
class WeeklySchedule:
    """Value Object для тижневого розкладу ()"""
    monday: WorkingHours | None = None
    tuesday: WorkingHours | None = None
    wednesday: WorkingHours | None = None
    thursday: WorkingHours | None = None
    friday: WorkingHours | None = None
    saturday: WorkingHours | None = None
    sunday: WorkingHours | None = None

    def is_working_on(self, day: DayOfWeek) -> bool:
        """Чи працює в цей день"""
        day_mapping = {
            DayOfWeek.MONDAY: self.monday,
            DayOfWeek.TUESDAY: self.tuesday,
            DayOfWeek.WEDNESDAY: self.wednesday,
            DayOfWeek.THURSDAY: self.thursday,
            DayOfWeek.FRIDAY: self.friday,
            DayOfWeek.SATURDAY: self.saturday,
            DayOfWeek.SUNDAY: self.sunday,
        }
        return day_mapping[day] is not None

    def get_working_hours_for_day(self, day: DayOfWeek) -> WorkingHours | None:
        """Отримати робочі години для дня"""
        day_mapping = {
            DayOfWeek.MONDAY: self.monday,
            DayOfWeek.TUESDAY: self.tuesday,
            DayOfWeek.WEDNESDAY: self.wednesday,
            DayOfWeek.THURSDAY: self.thursday,
            DayOfWeek.FRIDAY: self.friday,
            DayOfWeek.SATURDAY: self.saturday,
            DayOfWeek.SUNDAY: self.sunday,
        }
        return day_mapping[day]


@dataclass(frozen=True)
class ServiceDuration:
    """Value Object для тривалості сервісу"""
    minutes: int

    def __post_init__(self):
        if self.minutes <= 0:
            raise ValueError(f"Duration must be positive, got {self.minutes}")
        if self.minutes > 480:  # 8 годин
            raise ValueError(f"Duration cannot exceed 480 minutes (8 hours), got {self.minutes}")

    def to_timedelta(self) -> timedelta:
        return timedelta(minutes=self.minutes)

    def hours(self) -> float:
        return self.minutes / 60

    def __str__(self):
        hours = self.minutes // 60
        mins = self.minutes % 60
        if hours > 0:
            return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
        return f"{mins}m"


@dataclass(frozen=True)
class Distance:
    """Value Object для відстані (для OR-Tools)"""
    kilometers: Decimal

    def __post_init__(self):
        if self.kilometers < 0:
            raise ValueError(f"Distance cannot be negative, got {self.kilometers}")

    def to_meters(self) -> Decimal:
        return self.kilometers * Decimal('1000')

    def to_ortools_distance(self) -> int:
        """Конвертація в OR-Tools формат (метри як ціле число)"""
        return int(self.to_meters())

    def travel_time_minutes(self, speed_kmh: float = 30.0) -> int:
        """
        Приблизний час подорожі за відстанню.

        Args:
            speed_kmh: Швидкість в км/год (default: 30 - міський трафік)

        Returns:
            Час в хвилинах
        """
        hours = float(self.kilometers) / speed_kmh
        return int(hours * 60)

    def __str__(self) -> str:
        return f"{self.kilometers} km"

    def __add__(self, other: Distance) -> Distance:
        return Distance(kilometers=self.kilometers + other.kilometers)

    def __sub__(self, other: Distance) -> Distance:
        result = self.kilometers - other.kilometers
        if result < 0:
            raise ValueError("Cannot subtract larger distance from smaller")
        return Distance(kilometers=result)

    def __mul__(self, factor: float) -> Distance:
        return Distance(kilometers=self.kilometers * Decimal(str(factor)))

    def __lt__(self, other: Distance) -> bool:
        return self.kilometers < other.kilometers

    def __le__(self, other: Distance) -> bool:
        return self.kilometers <= other.kilometers


@dataclass(frozen=True)
class Duration:
    """
    Тривалість візиту або роботи.

    Використання:
        duration = Duration(90)  # 90 хвилин
        print(duration.hours)  # 1.5
    """
    minutes: int

    def __post_init__(self):
        if self.minutes < 0:
            raise ValueError(f"Duration cannot be negative: {self.minutes}")

    @property
    def hours(self) -> float:
        """Тривалість в годинах"""
        return self.minutes / 60.0

    @property
    def seconds(self) -> int:
        """Тривалість в секундах"""
        return self.minutes * 60

    def __str__(self) -> str:
        if self.minutes < 60:
            return f"{self.minutes} min"
        hours = self.minutes // 60
        mins = self.minutes % 60
        return f"{hours}h {mins}min" if mins > 0 else f"{hours}h"

    def __add__(self, other: Duration) -> Duration:
        """Додавання тривалостей"""
        return Duration(self.minutes + other.minutes)


@dataclass(frozen=True)
class Break:
    """Value Object для перерви техніка ()"""
    duration_minutes: int
    earliest_start: time
    latest_start: time

    def __post_init__(self):
        if self.duration_minutes <= 0:
            raise ValueError("Break duration must be positive")
        if self.earliest_start >= self.latest_start:
            raise ValueError("Earliest start must be before latest start")


@dataclass(frozen=True)
class TechnicianCapabilities:
    """Value Object для додаткових здібностей техніка ()"""
    can_do_physically_demanding: bool = False
    skilled_in_living_walls: bool = False
    comfortable_with_heights: bool = False
    certified_with_lift: bool = False
    has_pesticide_certification: bool = False
    is_citizen: bool = False


@dataclass(frozen=True)
class ServiceRequirements:
    """Value Object для вимог до заявки ()"""
    is_physically_demanding: bool = False
    has_living_walls: bool = False
    requires_work_at_heights: bool = False
    requires_lift_usage: bool = False
    requires_pesticide_application: bool = False
    requires_citizen_technician: bool = False
    requires_permit: bool = False
    permit_difficulty: PermitDifficulty | None = None



@dataclass(frozen=True)
class OptimizationMetrics:
    """
    Метрики оптимізації маршрутів.

    Використовується для збереження результатів оптимізації.

    Приклад:
        metrics = OptimizationMetrics(
            total_distance_km=Decimal("125.5"),
            total_duration_minutes=480,
            routes_count=5,
            services_assigned=23,
            services_unassigned=2
        )
    """
    # Основні метрики
    total_distance_km: Decimal
    total_duration_minutes: int
    routes_count: int

    # Призначення заявок
    services_assigned: int
    services_unassigned: int

    # Додаткові метрики (опціонально)
    total_travel_time_minutes: int = 0
    total_service_time_minutes: int = 0
    average_route_distance_km: Decimal = Decimal("0")

    def __post_init__(self):
        """Розрахунок derived metrics"""
        # Якщо average не задано - розраховуємо
        if self.average_route_distance_km == Decimal("0") and self.routes_count > 0:
            object.__setattr__(
                self,
                'average_route_distance_km',
                self.total_distance_km / self.routes_count
            )

    @property
    def assignment_rate(self) -> float:
        """Відсоток призначених заявок"""
        total = self.services_assigned + self.services_unassigned
        if total == 0:
            return 0.0
        return (self.services_assigned / total) * 100

    @property
    def total_time_minutes(self) -> int:
        """Загальний час (подорожі + обслуговування)"""
        return self.total_travel_time_minutes + self.total_service_time_minutes

    def __str__(self) -> str:
        return (
            f"OptimizationMetrics("
            f"routes={self.routes_count}, "
            f"assigned={self.services_assigned}/{self.services_assigned + self.services_unassigned}, "
            f"distance={self.total_distance_km}km)"
        )


@dataclass(frozen=True)
class ServiceStatus:
    """
    Статус сервісної заявки.

    Enum-подібний value object для статусів.

    Можливі статуси:
    - PENDING: Очікує призначення
    - ASSIGNED: Призначена технічнику
    - IN_PROGRESS: Виконується
    - COMPLETED: Виконана
    - CANCELLED: Скасована
    """
    value: str

    # Константи
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    def __post_init__(self):
        """Валідація"""
        valid_statuses = {
            self.PENDING,
            self.ASSIGNED,
            self.IN_PROGRESS,
            self.COMPLETED,
            self.CANCELLED
        }

        if self.value not in valid_statuses:
            raise ValueError(
                f"Invalid status: {self.value}. "
                f"Must be one of {valid_statuses}"
            )

    @classmethod
    def pending(cls) -> ServiceStatus:
        return cls(cls.PENDING)

    @classmethod
    def assigned(cls) -> ServiceStatus:
        return cls(cls.ASSIGNED)

    @classmethod
    def in_progress(cls) -> ServiceStatus:
        return cls(cls.IN_PROGRESS)

    @classmethod
    def completed(cls) -> ServiceStatus:
        return cls(cls.COMPLETED)

    @classmethod
    def cancelled(cls) -> ServiceStatus:
        return cls(cls.CANCELLED)

    def can_transition_to(self, new_status: ServiceStatus) -> bool:
        """Перевірка чи можливий перехід до нового статусу"""
        transitions = {
            self.PENDING: {self.ASSIGNED, self.CANCELLED},
            self.ASSIGNED: {self.IN_PROGRESS, self.CANCELLED},
            self.IN_PROGRESS: {self.COMPLETED, self.CANCELLED},
            self.COMPLETED: set(),  # Фінальний статус
            self.CANCELLED: set(),  # Фінальний статус
        }

        return new_status.value in transitions.get(self.value, set())

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other) -> bool:
        if isinstance(other, ServiceStatus):
            return self.value == other.value
        return False