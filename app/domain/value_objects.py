from dataclasses import dataclass
from datetime import time, timedelta
from decimal import Decimal
from enum import Enum


class SkillType(str, Enum):
    INTERIOR = "interior"
    EXTERIOR = "exterior"
    FLORAL = "floral"


class SkillLevel(str, Enum):
    JUNIOR = "junior"
    MEDIOR = "medior"
    SENIOR = "senior"

    @property
    def hierarchy_value(self) -> int:
        return {
            SkillLevel.JUNIOR: 1,
            SkillLevel.MEDIOR: 2,
            SkillLevel.SENIOR: 3,
        }[self]


class ServicePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

    def weight(self) -> int:
        return {
            ServicePriority.LOW: 1,
            ServicePriority.NORMAL: 2,
            ServicePriority.HIGH: 3,
            ServicePriority.URGENT: 5
        }[self]


class ServiceStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RouteStatus(str, Enum):
    DRAFT = "draft"
    OPTIMIZED = "optimized"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TransportMode(str, Enum):
    CAR_VAN = "car/van"
    WALK = "walk"
    DRIVE_TO_HUB_AND_WALK = "drive to a hub and then walk"


class StartEndPoint(str, Enum):
    HOME = "home"
    OFFICE = "office"
    EITHER_WORKS = "either works"


class VisitFrequency(str, Enum):
    X1 = "1x_week"
    X2 = "2x_week"
    X3 = "3x_week"
    X4 = "4x_week"
    X5 = "5x_week"


class DayOfWeek(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class PermitDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

    def bonus_weight(self) -> int:
        return {
            PermitDifficulty.EASY: 50,
            PermitDifficulty.MEDIUM: 150,
            PermitDifficulty.HARD: 300,
        }[self]


@dataclass(frozen=True)
class Location:
    latitude: Decimal
    longitude: Decimal

    def distance_to(self, other: 'Location') -> 'Distance':
        from math import radians, sin, cos, sqrt, atan2

        R = 6371.0  # Радіус Землі в км

        lat1 = radians(float(self.latitude))
        lon1 = radians(float(self.longitude))
        lat2 = radians(float(other.latitude))
        lon2 = radians(float(other.longitude))

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance_km = R * c
        return Distance(kilometers=Decimal(str(distance_km)))


@dataclass(frozen=True)
class TimeWindow:
    start: time
    end: time
    day_of_week: DayOfWeek

    def duration_minutes(self) -> int:
        from datetime import datetime, date

        dt_start = datetime.combine(date.today(), self.start)
        dt_end = datetime.combine(date.today(), self.end)

        delta = dt_end - dt_start
        return int(delta.total_seconds() / 60)

    def contains(self, time_point: time) -> bool:
        return self.start <= time_point <= self.end


@dataclass(frozen=True)
class Skill:
    service_type: SkillType
    level: SkillLevel

    def __str__(self) -> str:
        return f"{self.service_type.value} - {self.level.value}"


@dataclass(frozen=True)
class Distance:
    kilometers: Decimal

    @property
    def meters(self) -> int:
        return int(self.kilometers * 1000)

    @property
    def miles(self) -> Decimal:
        return self.kilometers * Decimal("0.621371")

    def __add__(self, other: 'Distance') -> 'Distance':
        return Distance(kilometers=self.kilometers + other.kilometers)

    def __lt__(self, other: 'Distance') -> bool:
        return self.kilometers < other.kilometers


@dataclass(frozen=True)
class Duration:
    minutes: int

    @property
    def hours(self) -> Decimal:
        return Decimal(self.minutes) / Decimal(60)

    @property
    def timedelta(self) -> timedelta:
        return timedelta(minutes=self.minutes)

    def __add__(self, other: 'Duration') -> 'Duration':
        return Duration(minutes=self.minutes + other.minutes)


@dataclass(frozen=True)
class TechnicianCapabilities:
    physically_demanding: bool = False
    living_walls: bool = False
    heights: bool = False
    lift: bool = False
    pesticides: bool = False
    citizenship: bool = False

    def can_satisfy(self, requirements: 'ServiceRequirements') -> bool:
        if requirements.physically_demanding and not self.physically_demanding:
            return False
        if requirements.living_walls and not self.living_walls:
            return False
        if requirements.heights and not self.heights:
            return False
        if requirements.lift and not self.lift:
            return False
        if requirements.pesticides and not self.pesticides:
            return False
        if requirements.citizenship and not self.citizenship:
            return False
        return True


@dataclass(frozen=True)
class ServiceRequirements:
    physically_demanding: bool = False
    living_walls: bool = False
    heights: bool = False
    lift: bool = False
    pesticides: bool = False
    citizenship: bool = False