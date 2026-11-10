"""Synthetic WIBL files with the GNSS faults seen on real loggers, at a made-up mid-ocean position."""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from wibl.core.logger_file import (
    GNSS,
    Depth,
    Metadata,
    SerialiserVersion,
    wibl_file_version_major,
    wibl_file_version_minor,
)

T0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC).timestamp()
LAT0, LON0 = 10.0, -30.0
SPEED_MS = 5.0  # due east
ELAPSED0_S = 30.0
PLACEHOLDER = datetime(2018, 3, 9, 12, 0, tzinfo=UTC).timestamp()
KEEP_DEPTH, OTHER_DEPTH = 5, 6
OTHER_DEPTH_VALUE = 99.0


def true_lon(t: float) -> float:
    metres = SPEED_MS * (t - T0)
    return LON0 + metres / (111_320.0 * math.cos(math.radians(LAT0)))


def depth_at(t: float) -> float:
    return 10.0 + 0.001 * (t - T0)


@dataclass
class Scenario:
    seconds: int = 600
    power_on: int = 5  # leading fixes with a placeholder date and position
    step: range = range(200, 260)  # fixes stamped 5 s fast
    jump: range = range(400, 410)  # fixes stamped 20,883 s fast
    gap: range = range(500, 521)  # no fixes at all
    extra: dict[int, float] = field(default_factory=dict)

    def offset_for(self, i: int) -> float:
        if i in self.step:
            return 5.0
        if i in self.jump:
            return 20_883.0
        return self.extra.get(i, 0.0)


def _gnss(elapsed_ms: int, t: float, lat: float, lon: float) -> GNSS:
    date = int(t // 86400)
    return GNSS(
        date=0, timestamp=0.0, elapsed_time=elapsed_ms, talker_id=6,
        msg_date=date, msg_timestamp=t - date * 86400, latitude=lat, longitude=lon, altitude=0.0,
        rx_type=0, rx_method=1, num_svs=10, horizontal_dop=0.9, position_dop=1.5, sep=0.0,
        n_refs=0, refs_type=0, refs_id=0, correction_age=0.0,
    )  # fmt: skip


def write_wibl(path: Path, s: Scenario | None = None) -> Scenario:
    s = s or Scenario()
    packets = [
        SerialiserVersion(
            major=wibl_file_version_major, minor=wibl_file_version_minor,
            n2000=(1, 2, 0), n0183=(1, 1, 0), imu=(1, 0, 0),
        ),
        Metadata(logger="TNODEID", shipname="Anonymous"),
    ]  # fmt: skip
    for i in range(s.seconds):
        t = T0 + i
        elapsed_ms = int((ELAPSED0_S + i) * 1000)
        if i < s.power_on:
            packets.append(_gnss(elapsed_ms, PLACEHOLDER + i, -40.0, 100.0))
        elif i not in s.gap:
            packets.append(_gnss(elapsed_ms, t + s.offset_for(i), LAT0, true_lon(t)))
        for half in (250, 750):
            te = t + half / 1000
            for talker, value in ((KEEP_DEPTH, depth_at(te)), (OTHER_DEPTH, OTHER_DEPTH_VALUE)):
                packets.append(
                    Depth(
                        date=0,
                        timestamp=0.0,
                        elapsed_time=elapsed_ms + half + talker,
                        talker_id=talker,
                        depth=value,
                        offset=0.0,
                        range=0.0,
                    )  # fmt: skip
                )
    with path.open("wb") as fh:
        for p in packets:
            p.serialise(fh)
    return s
