"""Submission ledger: the auditable life of each file from ingest to DCDB acceptance.

Every state change is appended to the record's history with a UTC timestamp and a
content hash, so the node can show reviewers exactly what it received, what it
sent, and when. Storage is behind the :class:`LedgerStore` protocol so the backend
(SQLite, Postgres, object store) can be chosen per deployment.
"""

import hashlib
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
