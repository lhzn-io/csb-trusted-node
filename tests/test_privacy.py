from typing import Any

import pytest

from csb_trusted_node.privacy import distance_m, trim_features

HOME = (10.0, -30.0)  # synthetic, mid-ocean


def point(lat: float, lon: float) -> dict[str, Any]:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {}}


def test_distance_one_minute_of_latitude() -> None:
    assert distance_m(10.0, -30.0, 10.0 + 1 / 60, -30.0) == pytest.approx(1853.2, abs=1.0)


def test_trim_removes_points_inside_radius_only() -> None:
    near = point(HOME[0] + 0.01, HOME[1])  # about 1.1 km
    edge = point(HOME[0] + 0.0179, HOME[1])  # about 1.99 km
    far = point(HOME[0] + 0.02, HOME[1])  # about 2.2 km
    kept, removed = trim_features([near, edge, far], HOME, 2000.0)
    assert kept == [far]
    assert removed == 2


def test_trim_drops_features_without_point_geometry() -> None:
    kept, removed = trim_features([{"type": "Feature", "geometry": None, "properties": {}}], HOME, 2000.0)
    assert kept == [] and removed == 1
