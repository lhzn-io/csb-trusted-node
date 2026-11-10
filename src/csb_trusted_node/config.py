"""Node configuration: who we are, which vessel a logger belongs to, and the privacy trim.

Loaded from a TOML file kept outside the repository (see ``configs/node.example.toml``),
because it names a real vessel and points at the private home-position file.
"""

import json
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from csb_trusted_node.metadata import (
    UNIQUE_VESSEL_ID_PATTERN,
    PositionReference,
    TrustedNodeMetadata,
    VerticalReference,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NodeSection(_Strict):
    provider_organization_name: str = Field(min_length=1)
    provider_email: EmailStr
    data_license: str = Field(min_length=1)


class SounderSection(_Strict):
    make: str = Field(min_length=1)
    model: str = Field(min_length=1)
    #: Offsets from the position reference point, metres, NED (bow, starboard, down).
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    draft: float | None = None
    frequency: float | None = None


class VesselSection(_Strict):
    unique_vessel_id: str
    type: str = Field(min_length=1)
    name: str | None = None
    length: int | None = Field(default=None, ge=1)
    vertical_reference_of_depth: VerticalReference = VerticalReference.TRANSDUCER
    position_reference: PositionReference = PositionReference.GNSS
    #: NMEA 2000 source address of the depth to keep, when more than one is on the bus.
    depth_source: int | None = Field(default=None, ge=0, le=253)
    sounder: SounderSection | None = None
    #: True only once the sounder and GNSS offsets have been measured on the vessel.
    position_offsets_documented: bool = False

    @field_validator("unique_vessel_id")
    @classmethod
    def _check_vessel_id(cls, value: str) -> str:
        if not UNIQUE_VESSEL_ID_PATTERN.match(value):
            raise ValueError(f"unique_vessel_id must look like <prefix>-<uuid>: {value!r}")
        return value


class PrivacySection(_Strict):
    #: JSON file with ``lat`` and ``lon`` (decimal degrees) of the vessel's home berth.
    home_file: Path
    radius_m: float = Field(default=2000.0, gt=0)


class ConversionSection(_Strict):
    #: Drop soundings with no kept GNSS fix within this many seconds.
    max_fix_gap_s: float = Field(default=2.0, gt=0)


class NodeConfig(_Strict):
    node: NodeSection
    vessel: VesselSection
    privacy: PrivacySection
    conversion: ConversionSection = ConversionSection()

    def trusted_node(self, logger_version: str) -> TrustedNodeMetadata:
        return TrustedNodeMetadata(
            providerOrganizationName=self.node.provider_organization_name,
            providerEmail=self.node.provider_email,
            uniqueVesselID=self.vessel.unique_vessel_id,
            dataLicense=self.node.data_license,
            providerLogger="WIBL",
            providerLoggerVersion=logger_version,
            verticalReferenceOfDepth=self.vessel.vertical_reference_of_depth,
            vesselPositionReferencePoint=self.vessel.position_reference,
        )

    def platform_b12(self) -> dict[str, Any]:
        v = self.vessel
        platform: dict[str, Any] = {"uniqueID": v.unique_vessel_id, "type": v.type}
        if v.name:
            platform["name"] = v.name
        if v.length is not None:
            platform["length"] = v.length
        if v.sounder is not None:
            sounder: dict[str, Any] = {
                "type": "Sounder",
                "make": v.sounder.make,
                "model": v.sounder.model,
                "position": list(v.sounder.position),
            }
            if v.sounder.draft is not None:
                sounder["draft"] = v.sounder.draft
            if v.sounder.frequency is not None:
                sounder["frequency"] = v.sounder.frequency
            platform["sensors"] = [sounder]
        platform["soundSpeedDocumented"] = False
        platform["positionOffsetsDocumented"] = v.position_offsets_documented
        # csbschema requires true whenever a processing block is present (ours records the time
        # repair). Depths themselves are as logged: no draft, sound speed or tide applied.
        platform["dataProcessed"] = True
        return platform


def load_config(path: Path) -> NodeConfig:
    with path.open("rb") as fh:
        return NodeConfig.model_validate(tomllib.load(fh))


Home = tuple[float, float]


def load_home(path: Path) -> Home:
    """Read the private home position. Never log or echo the result."""
    data = json.loads(path.read_text(encoding="utf-8"))
    lat, lon = float(data["lat"]), float(data["lon"])
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f"{path}: home position is out of range")
    return lat, lon
