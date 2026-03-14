from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from math import atan2, ceil, cos, radians, sin, sqrt

from .or_tools_solver import LocationRef, TravelTimeProvider

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class TravelLegMetrics:
    distance_km: Decimal
    travel_minutes: int


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> Decimal:
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = EARTH_RADIUS_KM * c
    return Decimal(str(distance)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def estimate_travel_minutes(
    distance_km: Decimal,
    average_speed_kmh: float = 35.0,
) -> int:
    if distance_km <= 0:
        return 0
    minutes = (float(distance_km) / average_speed_kmh) * 60
    return max(1, ceil(minutes))


def build_leg_metrics(
    origin: LocationRef,
    destination: LocationRef,
    average_speed_kmh: float = 35.0,
) -> TravelLegMetrics:
    if None in (origin.lat, origin.lon, destination.lat, destination.lon):
        raise ValueError("Missing coordinates for travel leg calculation")

    distance_km = haversine_distance_km(
        float(origin.lat),
        float(origin.lon),
        float(destination.lat),
        float(destination.lon),
    )
    return TravelLegMetrics(
        distance_km=distance_km,
        travel_minutes=estimate_travel_minutes(distance_km, average_speed_kmh=average_speed_kmh),
    )


class HaversineTimeProvider(TravelTimeProvider):
    def __init__(self, average_speed_kmh: float = 35.0):
        self.average_speed_kmh = average_speed_kmh

    def build_time_matrix_minutes(self, locations: list[LocationRef]) -> list[list[int]]:
        matrix: list[list[int]] = []
        for origin in locations:
            row: list[int] = []
            for destination in locations:
                if origin is destination:
                    row.append(0)
                    continue
                leg = build_leg_metrics(
                    origin,
                    destination,
                    average_speed_kmh=self.average_speed_kmh,
                )
                row.append(leg.travel_minutes)
            matrix.append(row)
        return matrix
