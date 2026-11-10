import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from csb_trusted_node.config import NodeConfig  # noqa: E402

VESSEL = "LHZN-00000000-0000-4000-8000-000000000000"


def make_config(home_file: Path, **vessel: Any) -> NodeConfig:
    return NodeConfig.model_validate(
        {
            "node": {
                "provider_organization_name": "Long Horizon Observatory",
                "provider_email": "csb@example.org",
                "data_license": "CC BY 4.0",
            },
            "vessel": {
                "unique_vessel_id": VESSEL,
                "type": "Recreational",
                "depth_source": 5,
                "sounder": {"make": "Example", "model": "Example 200", "frequency": 200000},
                **vessel,
            },
            "privacy": {"home_file": str(home_file), "radius_m": 2000},
        }
    )


@pytest.fixture
def home_file(tmp_path: Path) -> Path:
    """A synthetic home at the start of the synthetic track (see synth.py)."""
    path = tmp_path / "home.json"
    path.write_text(json.dumps({"lat": 10.0, "lon": -30.0}), encoding="utf-8")
    return path


@pytest.fixture
def config(home_file: Path) -> NodeConfig:
    return make_config(home_file)
