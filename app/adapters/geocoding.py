from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class GeocodedPoint:
    latitude: float
    longitude: float


class GeocodingCache:
    def __init__(self, path: Path):
        self.path = path
        self._data = self._load()

    def _load(self) -> dict[str, GeocodedPoint]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            address: GeocodedPoint(
                latitude=float(payload["latitude"]),
                longitude=float(payload["longitude"]),
            )
            for address, payload in raw.items()
        }

    def get(self, address: str) -> GeocodedPoint | None:
        return self._data.get(address)

    def set(self, address: str, point: GeocodedPoint) -> None:
        self._data[address] = point

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            address: {
                "latitude": point.latitude,
                "longitude": point.longitude,
            }
            for address, point in sorted(self._data.items())
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )


class NominatimGeocoder:
    def __init__(
        self,
        user_agent: str = "smart-routing-platform/0.1",
        request_delay_seconds: float = 1.0,
    ):
        self.user_agent = user_agent
        self.request_delay_seconds = request_delay_seconds

    def geocode(self, address: str) -> GeocodedPoint | None:
        for candidate in self._candidate_queries(address):
            query = urlencode({"q": candidate, "format": "jsonv2", "limit": 1})
            request = Request(
                url=f"https://nominatim.openstreetmap.org/search?{query}",
                headers={"User-Agent": self.user_agent},
            )
            try:
                with urlopen(request, timeout=15) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, TimeoutError) as exc:
                raise RuntimeError(f"Geocoding request failed for '{candidate}': {exc}") from exc

            time.sleep(self.request_delay_seconds)

            if not payload:
                continue

            first = payload[0]
            return GeocodedPoint(
                latitude=float(first["lat"]),
                longitude=float(first["lon"]),
            )

        return None

    def _candidate_queries(self, address: str) -> list[str]:
        normalized = " ".join(address.split())
        candidates = [normalized]

        simplified = re.sub(
            r"\b\d+(?:st|nd|rd|th)?\s+(?:floor|fl|suite|ste|unit|room|rm)\b",
            "",
            normalized,
            flags=re.IGNORECASE,
        )
        simplified = re.sub(r"#\s*[\w-]+", "", simplified)
        simplified = re.sub(r"\s+,", ",", simplified)
        simplified = re.sub(r"\s{2,}", " ", simplified).strip(" ,")
        if simplified and simplified not in candidates:
            candidates.append(simplified)

        tokens = [part.strip() for part in simplified.split(",") if part.strip()]
        if len(tokens) > 1:
            without_second = ", ".join(
                part for part in tokens if not re.search(r"\b(floor|suite|ste|unit|room|rm)\b", part, re.IGNORECASE)
            )
            if without_second and without_second not in candidates:
                candidates.append(without_second)

            if not re.match(r"^\d", tokens[0]) and re.match(r"^\d", tokens[1]):
                without_prefix = ", ".join(tokens[1:])
                if without_prefix not in candidates:
                    candidates.append(without_prefix)
            if "&" in tokens[0]:
                without_intersection = ", ".join(tokens[1:])
                if without_intersection and without_intersection not in candidates:
                    candidates.append(without_intersection)

        return candidates


class CachedGeocoder:
    def __init__(self, cache_path: Path):
        self.cache = GeocodingCache(cache_path)
        provider_name = os.environ.get("SMART_ROUTING_GEOCODER", "cache_only").strip().lower()
        self.provider = NominatimGeocoder() if provider_name == "nominatim" else None

    def geocode_many(self, addresses: list[str]) -> dict[str, tuple[float, float]]:
        resolved: dict[str, tuple[float, float]] = {}
        missing: list[str] = []

        for raw_address in addresses:
            address = raw_address.strip()
            if not address:
                continue
            cached = self.cache.get(address)
            if cached is not None:
                resolved[address] = (cached.latitude, cached.longitude)
                continue
            missing.append(address)

        if missing and self.provider is None:
            missing_preview = ", ".join(missing[:5])
            raise RuntimeError(
                "Missing coordinates for addresses in geocoding cache. "
                "Populate data/geocoding_cache.json or set SMART_ROUTING_GEOCODER=nominatim. "
                f"First unresolved addresses: {missing_preview}"
            )

        for address in missing:
            point = self.provider.geocode(address) if self.provider is not None else None
            if point is None:
                continue
            self.cache.set(address, point)
            resolved[address] = (point.latitude, point.longitude)

        if missing:
            self.cache.save()

        unresolved = [address for address in missing if address not in resolved]
        if unresolved:
            preview = ", ".join(unresolved[:10])
            raise RuntimeError(
                "Geocoder returned no coordinates for some addresses. "
                f"Unresolved count: {len(unresolved)}. "
                f"First unresolved addresses: {preview}"
            )

        return resolved
