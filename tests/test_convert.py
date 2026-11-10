import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from synth import LAT0, OTHER_DEPTH_VALUE, T0, Scenario, depth_at, true_lon, write_wibl

from csb_trusted_node.config import NodeConfig
from csb_trusted_node.convert import FMT_TIME, convert_wibl
from csb_trusted_node.validation import validate_b12


def epoch(feature: dict[str, object]) -> float:
    props = feature["properties"]
    assert isinstance(props, dict)
    return datetime.strptime(props["time"], FMT_TIME).replace(tzinfo=UTC).timestamp()


@pytest.fixture
def converted(tmp_path: Path, config: NodeConfig) -> tuple[Scenario, object]:
    path = tmp_path / "raw00001.wbl"
    scenario = write_wibl(path)
    return scenario, convert_wibl(path, config)


def test_faults_are_repaired(converted: tuple[Scenario, object]) -> None:
    s, c = converted
    report = c.report  # type: ignore[attr-defined]
    assert report.power_on_dropped == s.power_on
    assert report.retimed == len(s.step) + len(s.jump)
    features = c.document["features"]  # type: ignore[attr-defined]
    times = [epoch(f) for f in features]
    assert min(times) >= T0 + s.power_on - 1
    assert max(times) <= T0 + s.seconds


def test_positions_follow_the_true_track(converted: tuple[Scenario, object]) -> None:
    _, c = converted
    for f in c.document["features"]:  # type: ignore[attr-defined]
        lon, lat = f["geometry"]["coordinates"]
        t = epoch(f)
        assert lat == pytest.approx(LAT0, abs=1e-9)
        assert lon == pytest.approx(true_lon(t), abs=2e-5)  # about 2 m
        assert f["properties"]["depth"] == pytest.approx(depth_at(t), abs=0.02)


def test_only_the_configured_depth_source_is_kept(converted: tuple[Scenario, object]) -> None:
    s, c = converted
    depths = [f["properties"]["depth"] for f in c.document["features"]]  # type: ignore[attr-defined]
    assert OTHER_DEPTH_VALUE not in depths
    assert c.report.depth_other_sources == 2 * s.seconds  # type: ignore[attr-defined]


def test_soundings_in_a_fix_gap_are_dropped(converted: tuple[Scenario, object]) -> None:
    s, c = converted
    gap_start, gap_end = T0 + s.gap.start, T0 + s.gap.stop - 1
    inside = [f for f in c.document["features"] if gap_start + 2.5 < epoch(f) < gap_end - 2.5]  # type: ignore[attr-defined]
    assert inside == []
    assert c.report.dropped_no_fix > 0  # type: ignore[attr-defined]


def test_metadata_blocks_and_schema(converted: tuple[Scenario, object], tmp_path: Path) -> None:
    _, c = converted
    props = c.document["properties"]  # type: ignore[attr-defined]
    assert props["trustedNode"]["uniqueVesselID"] == props["platform"]["uniqueID"]
    assert props["trustedNode"]["dataLicense"] == "CC BY 4.0"
    assert "TNODEID" not in json.dumps(props) and "Anonymous" not in json.dumps(props)
    assert {p["type"] for p in props["processing"]} == {"TimeStampInterpolation", "Algorithm"}
    out = tmp_path / "doc.geojson"
    out.write_text(json.dumps(c.document), encoding="utf-8")  # type: ignore[attr-defined]
    result = validate_b12(out)
    assert result.valid, result.errors
