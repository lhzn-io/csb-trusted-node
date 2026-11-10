"""Submission ledger: the auditable life of each file from ingest to DCDB acceptance.

Every state change is appended to the record's history with a UTC timestamp and a
content hash, so the node can show reviewers exactly what it received, what it
sent, and when. Storage is behind the :class:`LedgerStore` protocol so the backend
(SQLite, Postgres, object store) can be chosen per deployment.
"""

import hashlib
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class SubmissionState(StrEnum):
    RECEIVED = "received"
    CONVERTED = "converted"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


TRANSITIONS: dict[SubmissionState, frozenset[SubmissionState]] = {
    SubmissionState.RECEIVED: frozenset({SubmissionState.CONVERTED, SubmissionState.FAILED}),
    SubmissionState.CONVERTED: frozenset({SubmissionState.VALIDATED, SubmissionState.REJECTED}),
    SubmissionState.VALIDATED: frozenset({SubmissionState.SUBMITTED, SubmissionState.FAILED}),
    SubmissionState.SUBMITTED: frozenset({SubmissionState.ACCEPTED, SubmissionState.REJECTED}),
    # A failed step may be retried from the start once the cause is fixed.
    SubmissionState.FAILED: frozenset({SubmissionState.RECEIVED}),
    SubmissionState.ACCEPTED: frozenset(),
    SubmissionState.REJECTED: frozenset(),
}


class InvalidTransition(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class LedgerEvent:
    state: SubmissionState
    at: datetime
    sha256: str | None = None
    note: str = ""


@dataclass
class SubmissionRecord:
    submission_id: str
    unique_vessel_id: str
    history: list[LedgerEvent] = field(default_factory=list)

    @property
    def state(self) -> SubmissionState:
        return self.history[-1].state

    def advance(self, new_state: SubmissionState, *, sha256: str | None = None, note: str = "") -> None:
        if new_state not in TRANSITIONS[self.state]:
            raise InvalidTransition(f"{self.submission_id}: {self.state} -> {new_state} is not allowed")
        self.history.append(LedgerEvent(new_state, datetime.now(UTC), sha256, note))

    @classmethod
    def receive(
        cls, submission_id: str, unique_vessel_id: str, *, sha256: str, note: str = ""
    ) -> "SubmissionRecord":
        event = LedgerEvent(SubmissionState.RECEIVED, datetime.now(UTC), sha256, note)
        return cls(submission_id, unique_vessel_id, [event])


class LedgerStore(Protocol):
    def put(self, record: SubmissionRecord) -> None: ...
    def get(self, submission_id: str) -> SubmissionRecord | None: ...
    def by_state(self, state: SubmissionState) -> list[SubmissionRecord]: ...


class InMemoryLedgerStore:
    """Reference implementation for tests and local runs."""

    def __init__(self) -> None:
        self._records: dict[str, SubmissionRecord] = {}

    def put(self, record: SubmissionRecord) -> None:
        self._records[record.submission_id] = record

    def get(self, submission_id: str) -> SubmissionRecord | None:
        return self._records.get(submission_id)

    def by_state(self, state: SubmissionState) -> list[SubmissionRecord]:
        return [r for r in self._records.values() if r.state is state]


class SqliteLedgerStore:
    """Durable single-file store (stdlib ``sqlite3``). One writer at a time."""

    def __init__(self, path: Path) -> None:
        self._db = sqlite3.connect(path)
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS records (
                submission_id TEXT PRIMARY KEY,
                unique_vessel_id TEXT NOT NULL,
                state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                submission_id TEXT NOT NULL REFERENCES records(submission_id),
                seq INTEGER NOT NULL,
                state TEXT NOT NULL,
                at TEXT NOT NULL,
                sha256 TEXT,
                note TEXT NOT NULL,
                PRIMARY KEY (submission_id, seq)
            );
            CREATE INDEX IF NOT EXISTS records_state ON records(state);
            """
        )

    def close(self) -> None:
        self._db.close()

    def put(self, record: SubmissionRecord) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO records VALUES (?, ?, ?) ON CONFLICT(submission_id) "
                "DO UPDATE SET unique_vessel_id = excluded.unique_vessel_id, state = excluded.state",
                (record.submission_id, record.unique_vessel_id, record.state.value),
            )
            self._db.execute("DELETE FROM events WHERE submission_id = ?", (record.submission_id,))
            self._db.executemany(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (record.submission_id, i, e.state.value, e.at.isoformat(), e.sha256, e.note)
                    for i, e in enumerate(record.history)
                ],
            )

    def get(self, submission_id: str) -> SubmissionRecord | None:
        row = self._db.execute(
            "SELECT unique_vessel_id FROM records WHERE submission_id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            return None
        events = [
            LedgerEvent(SubmissionState(state), datetime.fromisoformat(at), sha, note)
            for state, at, sha, note in self._db.execute(
                "SELECT state, at, sha256, note FROM events WHERE submission_id = ? ORDER BY seq",
                (submission_id,),
            )
        ]
        return SubmissionRecord(submission_id, row[0], events)

    def by_state(self, state: SubmissionState) -> list[SubmissionRecord]:
        ids = [
            r[0]
            for r in self._db.execute("SELECT submission_id FROM records WHERE state = ?", (state.value,))
        ]
        return [rec for i in ids if (rec := self.get(i)) is not None]
