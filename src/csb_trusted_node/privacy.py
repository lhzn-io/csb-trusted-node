"""Remove soundings near a vessel's home berth before anything is shared.

Every trip starts and ends at the berth, so a track that has not been trimmed reveals
where the owner keeps the boat. The home position is read from a private file at run
time and never stored, logged or written into output.
"""

import math
from typing import Any

EARTH_RADIUS_M = 6_371_000.0


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (haversine) distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def trim_features(
    features: list[dict[str, Any]], home: tuple[float, float], radius_m: float
) -> tuple[list[dict[str, Any]], int]:
    """Return the GeoJSON point features farther than ``radius_m`` from ``home``, and how many were removed.

    Features without a point geometry are removed too, since they can't be checked.
    """
    lat0, lon0 = home
    kept: list[dict[str, Any]] = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") if geometry.get("type") == "Point" else None
        if coords is None or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        if distance_m(lat0, lon0, lat, lon) > radius_m:
            kept.append(feature)
    return kept, len(features) - len(kept)
