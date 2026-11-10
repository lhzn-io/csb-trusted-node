import json
from pathlib import Path

from synth import Scenario, write_wibl

from csb_trusted_node.config import NodeConfig
from csb_trusted_node.ingest import ingest_directory
from csb_trusted_node.ledger import SqliteLedgerStore, SubmissionState
from csb_trusted_node.privacy import distance_m


def setup_source(tmp_path: Path) -> Path:
    src = tmp_path / "wibl"
    src.mkdir()
    write_wibl(src / "raw00001.wbl")
    write_wibl(src / "raw00002.wbl", Scenario(seconds=300))  # never leaves the 2 km radius
    (src / "raw00003.wbl").write_bytes(b"")  # a stalled copy
    (src / "raw00004.wbl").write_bytes(b"\x00" * 900)  # header only
    (src / "raw00005.wbl.part").write_bytes(b"\x00" * 9000)
    return src


def test_ingest_trims_validates_and_is_idempotent(tmp_path: Path, config: NodeConfig) -> None:
    src, out = setup_source(tmp_path), tmp_path / "out"
    store = SqliteLedgerStore(tmp_path / "ledger.sqlite")

    first = {o.file: o for o in ingest_directory(src, config, out, store)}
    assert set(first) == {"raw00001.wbl", "raw00002.wbl", "raw00003.wbl", "raw00004.wbl"}
    assert first["raw00001.wbl"].state == "validated"
    assert first["raw00002.wbl"].state == "rejected"
    assert "privacy radius" in first["raw00002.wbl"].note
    assert first["raw00003.wbl"].state == "skipped"
    assert first["raw00004.wbl"].state == "skipped"

    (shared,) = (out / "shareable").iterdir()
    doc = json.loads(shared.read_text(encoding="utf-8"))
    assert len(doc["features"]) == first["raw00001.wbl"].soundings > 0
    for f in doc["features"]:
        lon, lat = f["geometry"]["coordinates"]
        assert distance_m(10.0, -30.0, lat, lon) > 2000.0
    assert len(list((out / "private").iterdir())) == 2

    second = {o.file: o for o in ingest_directory(src, config, out, store)}
    assert second["raw00001.wbl"].note == "already ingested"
    store.close()

    reopened = SqliteLedgerStore(tmp_path / "ledger.sqlite")
    sid = first["raw00001.wbl"].submission_id
    assert sid is not None
    record = reopened.get(sid)
    assert record is not None
    assert [e.state for e in record.history] == [
        SubmissionState.RECEIVED,
        SubmissionState.CONVERTED,
        SubmissionState.VALIDATED,
    ]
    assert all(e.sha256 for e in record.history)
    assert [r.submission_id for r in reopened.by_state(SubmissionState.VALIDATED)] == [sid]
    reopened.close()
