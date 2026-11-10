"""Repair GNSS time fields against the logger's elapsed clock.

WIBL loggers stamp every packet with a monotonic elapsed-time counter, and wibl-python
maps that counter to real time through the GNSS fixes. Consumer receivers get those
fixes wrong in ways the positions don't share:

- After power-on, the first fixes carry a placeholder firmware date (2018 on the units seen), and
  their positions can be placeholders too.
- The date can roll over a second before the time at midnight UTC.
- The time field can step by seconds or hours for minutes at a time while the positions
  in the same packets stay current (confirmed against Signal K receive times).

The logger clock is steady, so the offset ``gnss_time - elapsed`` is nearly constant
within a file. This module finds the fixes whose offset disagrees with that consensus
and re-times them from the elapsed clock, keeping their positions. Fixes before the
first plausible date are dropped, positions included.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]

#: Fixes dated before this are placeholders (receivers fall back to a firmware date).
DEFAULT_FLOOR = datetime(2024, 1, 1, tzinfo=UTC).timestamp()


class NoGoodTime(ValueError):
    """No GNSS fix in the file has a usable time, so nothing can be time-stamped."""


@dataclass(frozen=True)
class RepairParameters:
    #: Fixes dated earlier than this (epoch seconds) are placeholders.
    floor: float = DEFAULT_FLOOR
    #: Whole-file check: offsets further than this (s) from the file median are faults.
    consensus_tol_s: float = 60.0
    #: Local check: offsets further than this (s) from the running median are faults.
    local_tol_s: float = 1.5
    #: Half-width (fixes) of the running median. It must exceed the longest fault run
    #: (600 s steps have been seen at 1 Hz), or the median follows the fault.
    local_half: int = 900
    #: Half-width (fixes) of the neighborhood whose good offsets re-time a faulty fix.
    anchor_half: int = 300

    def as_b12(self) -> dict[str, Any]:
        return {
            "floor": datetime.fromtimestamp(self.floor, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "consensusTolerance_s": self.consensus_tol_s,
            "localTolerance_s": self.local_tol_s,
            "localWindow_fixes": 2 * self.local_half + 1,
            "anchorWindow_fixes": 2 * self.anchor_half + 1,
        }


@dataclass(frozen=True)
class TimeRepair:
    #: Per fix: keep it (as a time reference and a position)?
    keep: BoolArray
    #: Per fix: the repaired time in epoch seconds (NaN where dropped).
    times: FloatArray
    dropped_power_on: int
    retimed: int
    retimed_indices: list[int] = field(default_factory=list)


def _running_nanmedian(values: FloatArray, half: int) -> FloatArray:
    out = np.empty_like(values)
    n = len(values)
    for i in range(n):
        window = values[max(0, i - half) : min(n, i + half + 1)]
        out[i] = np.nanmedian(window) if np.isfinite(window).any() else np.nan
    return out


def repair_gnss_times(
    elapsed_s: FloatArray, gnss_s: FloatArray, params: RepairParameters | None = None
) -> TimeRepair:
    """Return which fixes to keep and their repaired times.

    ``elapsed_s`` is the logger's elapsed clock and ``gnss_s`` the time each fix claims,
    both in seconds and in file order.
    """
    p = params or RepairParameters()
    elapsed = np.asarray(elapsed_s, dtype=np.float64)
    gnss = np.asarray(gnss_s, dtype=np.float64)
    if elapsed.shape != gnss.shape:
        raise ValueError("elapsed and GNSS times must have the same length")
    n = len(gnss)
    plausible = np.isfinite(gnss) & (gnss >= p.floor)
    if not plausible.any():
        raise NoGoodTime("no GNSS fix has a plausible date")

    # Rule 1: everything before the first plausible fix is power-on noise.
    first = int(np.argmax(plausible))
    keep = np.ones(n, dtype=bool)
    keep[:first] = False

    # Rule 2: faults after that are re-timed, not dropped.
    offset = gnss - elapsed
    fault = ~plausible
    fault[:first] = False
    live = keep & ~fault
    fault |= keep & (np.abs(offset - np.median(offset[live])) > p.consensus_tol_s)
    good = np.where(keep & ~fault, offset, np.nan)
    running = _running_nanmedian(good, p.local_half)
    fault |= keep & (np.abs(offset - running) > p.local_tol_s)

    good = np.where(keep & ~fault, offset, np.nan)
    if not np.isfinite(good).any():
        raise NoGoodTime("every GNSS fix disagrees with the logger clock")
    file_median = float(np.nanmedian(good))
    times = np.where(keep, gnss, np.nan)
    retimed = [int(i) for i in np.flatnonzero(fault & keep)]
    for i in retimed:
        window = good[max(0, i - p.anchor_half) : min(n, i + p.anchor_half + 1)]
        anchor = float(np.nanmedian(window)) if np.isfinite(window).any() else file_median
        times[i] = elapsed[i] + anchor
    return TimeRepair(keep, times, dropped_power_on=first, retimed=len(retimed), retimed_indices=retimed)
