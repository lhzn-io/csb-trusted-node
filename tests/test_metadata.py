import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from csb_trusted_node.metadata import TrustedNodeMetadata, new_unique_vessel_id
from csb_trusted_node.validation import validate_b12


def make_metadata(**overrides: Any) -> TrustedNodeMetadata:
    fields: dict[str, Any] = {
        "providerOrganizationName": "Long Horizon Observatory",
        "providerEmail": "csb@lhzn.io",
        "uniqueVesselID": new_unique_vessel_id("LHZN"),
        "dataLicense": "CC0 1.0",
        "providerLogger": "WIBL",
        "providerLoggerVersion": "1.7.0",
        "verticalReferenceOfDepth": "Transducer",
        "vesselPositionReferencePoint": "GNSS",
    }
    fields.update(overrides)
    return TrustedNodeMetadata(**fields)


def test_vessel_id_has_prefix_and_uuid() -> None:
    vid = new_unique_vessel_id("LHZN")
    assert vid.startswith("LHZN-")
    assert len(vid) == len("LHZN-") + 36


@pytest.mark.parametrize("prefix", ["", "1abc", "has-dash"])
def test_vessel_id_rejects_bad_prefix(prefix: str) -> None:
    with pytest.raises(ValueError):
        new_unique_vessel_id(prefix)


def test_rejects_malformed_vessel_id() -> None:
    with pytest.raises(ValidationError):
        make_metadata(uniqueVesselID="not-a-uuid")


def test_emitted_document_passes_csbschema(tmp_path: Path) -> None:
    """End-to-end: our trustedNode block, wrapped in a minimal FeatureCollection, is valid B-12 3.1."""
    document = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "properties": {"trustedNode": make_metadata().to_b12()},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-70.75, 43.07]},
                "properties": {"depth": 12.3, "time": "2026-10-05T14:00:00.000Z"},
            }
        ],
    }
    path = tmp_path / "submission.geojson"
    path.write_text(json.dumps(document), encoding="utf-8")

    result = validate_b12(path)
    assert result.valid, result.errors
