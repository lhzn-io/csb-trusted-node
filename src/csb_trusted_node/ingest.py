"""Ingest a directory of WIBL files: receive, convert, trim, validate, and record each step.

Output layout under ``out_dir``:

- ``private/``: the converted document before the privacy trim. It contains the home
  berth, so it never leaves the node (directory mode 0700).
- ``shareable/``: the trimmed document that passed ``csbschema``. Only these are
  candidates for submission.

A file is identified by the SHA-256 of its bytes, so re-running over the same
directory only processes new files (and retries failed ones).
"""

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from csb_trusted_node.config import NodeConfig, load_home
from csb_trusted_node.convert import ConversionError, convert_wibl
from csb_trusted_node.ledger import LedgerStore, SubmissionRecord, SubmissionState, sha256_file
from csb_trusted_node.privacy import trim_features
from csb_trusted_node.validation import validate_b12

#: Files smaller than this hold only a header (a power-on with no traffic).
DEFAULT_MIN_BYTES = 2048
WIBL_SUFFIXES = (".wbl", ".wibl")


@dataclass(frozen=True)
class IngestOutcome:
    file: str
    submission_id: str | None
    state: str
    soundings: int = 0
    note: str = ""


def candidates(src: Path, min_bytes: int) -> Iterator[tuple[Path, str | None]]:
    """Yield each WIBL file in ``src`` with a reason to skip it, or None to process it."""
    for path in sorted(src.iterdir()):
        if not path.is_file() or path.suffix.lower() not in WIBL_SUFFIXES:
            continue
        size = path.stat().st_size
        if size == 0:
            yield path, "empty (incomplete copy?)"
        elif size < min_bytes:
            yield path, f"header only ({size} bytes)"
        else:
            yield path, None


def _write_json(path: Path, document: dict[str, object]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def ingest_directory(
    src: Path,
    config: NodeConfig,
    out_dir: Path,
    store: LedgerStore,
    *,
    min_bytes: int = DEFAULT_MIN_BYTES,
) -> list[IngestOutcome]:
    home = load_home(config.privacy.home_file)
    private_dir, share_dir = out_dir / "private", out_dir / "shareable"
    private_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(private_dir, 0o700)
    share_dir.mkdir(parents=True, exist_ok=True)
    vessel = config.vessel.unique_vessel_id

    outcomes: list[IngestOutcome] = []
    for path, skip in candidates(src, min_bytes):
        if skip:
            outcomes.append(IngestOutcome(path.name, None, "skipped", note=skip))
            continue
        sha = sha256_file(path)
        sid = f"wibl-{sha[:16]}"
        record = store.get(sid)
        if record is not None and record.state is not SubmissionState.FAILED:
            outcomes.append(IngestOutcome(path.name, sid, record.state.value, note="already ingested"))
            continue
        if record is None:
            record = SubmissionRecord.receive(sid, vessel, sha256=sha, note=path.name)
        else:
            record.advance(SubmissionState.RECEIVED, sha256=sha, note=f"retry {path.name}")
        store.put(record)

        try:
            conversion = convert_wibl(path, config)
        except ConversionError as e:
            record.advance(SubmissionState.FAILED, note=str(e))
            store.put(record)
            outcomes.append(IngestOutcome(path.name, sid, record.state.value, note=str(e)))
            continue

        document = conversion.document
        private_path = private_dir / f"{path.stem}.{sid}.geojson"
        _write_json(private_path, document)
        report = conversion.report
        record.advance(
            SubmissionState.CONVERTED,
            sha256=sha256_file(private_path),
            note=f"{report.soundings} soundings; {report.retimed} fixes re-timed; "
            f"{report.power_on_dropped} power-on fixes dropped",
        )
        store.put(record)

        kept, removed = trim_features(document["features"], home, config.privacy.radius_m)
        if not kept:
            note = f"no soundings outside the {config.privacy.radius_m:g} m privacy radius"
            record.advance(SubmissionState.REJECTED, note=note)
            store.put(record)
            outcomes.append(IngestOutcome(path.name, sid, record.state.value, note=note))
            continue
        shareable = {**document, "features": kept}
        share_path = share_dir / f"{path.stem}.{sid}.geojson"
        _write_json(share_path, shareable)
        result = validate_b12(share_path)
        if result.valid:
            record.advance(
                SubmissionState.VALIDATED,
                sha256=sha256_file(share_path),
                note=f"{len(kept)} soundings after removing {removed} within the privacy radius",
            )
            outcome_note = f"{removed} removed by the privacy trim"
        else:
            share_path.unlink()
            errors = "; ".join(str(e) for e in result.errors[:3])
            record.advance(SubmissionState.REJECTED, note=f"csbschema: {errors}")
            outcome_note = f"csbschema: {errors}"
        store.put(record)
        outcomes.append(IngestOutcome(path.name, sid, record.state.value, len(kept), outcome_note))
    return outcomes
