import pytest

from csb_trusted_node.ledger import (
    InMemoryLedgerStore,
    InvalidTransition,
    SubmissionRecord,
    SubmissionState,
)

VESSEL = "LHZN-00000000-0000-4000-8000-000000000000"


def test_happy_path_is_recorded_in_order() -> None:
    record = SubmissionRecord.receive("sub-1", VESSEL, sha256="aa")
    for state in (
        SubmissionState.CONVERTED,
        SubmissionState.VALIDATED,
        SubmissionState.SUBMITTED,
        SubmissionState.ACCEPTED,
    ):
        record.advance(state)
    assert [e.state for e in record.history] == [
        SubmissionState.RECEIVED,
        SubmissionState.CONVERTED,
        SubmissionState.VALIDATED,
        SubmissionState.SUBMITTED,
        SubmissionState.ACCEPTED,
    ]
    assert record.history[0].sha256 == "aa"


def test_cannot_skip_validation() -> None:
    record = SubmissionRecord.receive("sub-2", VESSEL, sha256="bb")
    record.advance(SubmissionState.CONVERTED)
    with pytest.raises(InvalidTransition):
        record.advance(SubmissionState.SUBMITTED)


def test_terminal_states_are_final() -> None:
    record = SubmissionRecord.receive("sub-3", VESSEL, sha256="cc")
    record.advance(SubmissionState.CONVERTED)
    record.advance(SubmissionState.REJECTED, note="schema: missing depth")
    with pytest.raises(InvalidTransition):
        record.advance(SubmissionState.RECEIVED)


def test_store_filters_by_state() -> None:
    store = InMemoryLedgerStore()
    a = SubmissionRecord.receive("a", VESSEL, sha256="1")
    b = SubmissionRecord.receive("b", VESSEL, sha256="2")
    b.advance(SubmissionState.FAILED, note="decode error")
    store.put(a)
    store.put(b)
    assert [r.submission_id for r in store.by_state(SubmissionState.FAILED)] == ["b"]
    assert store.get("a") is a
