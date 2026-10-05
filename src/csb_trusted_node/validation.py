"""Thin wrapper over csbschema so the rest of the node depends on one validation entry point."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from csbschema.validators import validate_b12_3_1_0_2024_04


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[Any] = field(default_factory=list)


def validate_b12(document_path: Path | str) -> ValidationResult:
    """Validate a B-12 GeoJSON file against CSB schema 3.1.0 (2024-04)."""
    valid, detail = validate_b12_3_1_0_2024_04(document_path)
    return ValidationResult(valid=valid, errors=list(detail.get("errors", [])))
