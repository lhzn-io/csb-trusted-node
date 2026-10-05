"""B-12 Trusted Node metadata.

Field names, enums and patterns mirror the ``TrustedNode`` and ``UniqueVesselID``
definitions in csbschema's ``CSB-schema-3_1_0-2024-04.json``. That schema is the
authority; :func:`csb_trusted_node.validation.validate_b12` checks our output against it.
"""

import re
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from csb_trusted_node import B12_CONVENTION

UNIQUE_VESSEL_ID_PATTERN = re.compile(
    r"^[a-zA-Z][a-zA-Z0-9]*-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
NODE_PREFIX_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9]*$")


class VerticalReference(StrEnum):
    TRANSDUCER = "Transducer"
    WATERLINE = "Waterline"
    UNKNOWN = "Unknown"


class PositionReference(StrEnum):
    GNSS = "GNSS"
    TRANSDUCER = "Transducer"
    REFERENCE_PLACE = "ReferencePlace"


def new_unique_vessel_id(node_prefix: str) -> str:
    """Allocate a B-12 ``uniqueVesselID`` (``<prefix>-<uuid4>``) under this node's prefix."""
    if not NODE_PREFIX_PATTERN.match(node_prefix):
        raise ValueError(f"node prefix must be alphanumeric and start with a letter: {node_prefix!r}")
    return f"{node_prefix}-{uuid.uuid4()}"


class TrustedNodeMetadata(BaseModel):
    """The ``properties.trustedNode`` block of a B-12 GeoJSON submission."""

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    provider_organization_name: str = Field(alias="providerOrganizationName", min_length=1)
    provider_email: EmailStr = Field(alias="providerEmail")
    unique_vessel_id: str = Field(alias="uniqueVesselID")
    convention: str = Field(default=B12_CONVENTION)
    data_license: str = Field(alias="dataLicense", min_length=1)
    provider_logger: str = Field(alias="providerLogger", min_length=1)
    provider_logger_version: str = Field(alias="providerLoggerVersion", min_length=1)
    navigation_crs: str = Field(default="EPSG:4326", alias="navigationCRS", pattern=r"^EPSG:\d+$")
    vertical_reference_of_depth: VerticalReference = Field(alias="verticalReferenceOfDepth")
    vessel_position_reference_point: PositionReference = Field(alias="vesselPositionReferencePoint")

    @field_validator("unique_vessel_id")
    @classmethod
    def _check_vessel_id(cls, value: str) -> str:
        if not UNIQUE_VESSEL_ID_PATTERN.match(value):
            raise ValueError(f"uniqueVesselID must look like <prefix>-<uuid>: {value!r}")
        return value

    @field_validator("convention")
    @classmethod
    def _check_convention(cls, value: str) -> str:
        if value != B12_CONVENTION:
            raise ValueError(f"convention must be {B12_CONVENTION!r}")
        return value

    def to_b12(self) -> dict[str, Any]:
        """Serialise with the B-12 camelCase keys."""
        return self.model_dump(by_alias=True)
