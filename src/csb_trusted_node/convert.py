"""Convert one WIBL file to a B-12 GeoJSON document with wibl-python.

wibl-python does the decoding and the time interpolation. This module adds what a
Trusted Node needs on top:

- GNSS time repair (:mod:`csb_trusted_node.gnss_time`) before interpolation;
- one depth source, chosen by NMEA 2000 source address, when the bus carries several;
- no sounding without a kept GNSS fix within ``max_fix_gap_s``, so gaps left by dropped
  fixes are never bridged by a straight line;
- the node's own ``trustedNode``, ``platform`` and ``processing`` blocks.

The repair hooks into wibl-python by swapping ``wibl.core.timestamping.load_file`` for
the duration of one call (see :func:`_repairing_loader`). That is not thread-safe; run
conversions in separate processes if they need to be parallel. An upstream packet-filter
hook in wibl-python would remove the need for it.
"""

import io
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import wibl.core.timestamping as wibl_ts
from wibl.core import Lineage
from wibl.core.logger_file import GNSS, Depth

from csb_trusted_node import __version__
from csb_trusted_node.config import NodeConfig
from csb_trusted_node.gnss_time import RepairParameters, repair_gnss_times

SECONDS_PER_DAY = 86400.0
#: WIBL elapsed times are 32-bit milliseconds.
ELAPSED_TIME_QUANTUM = 1 << 32
FMT_TIME = "%Y-%m-%dT%H:%M:%S.%fZ"


class ConversionError(RuntimeError):
    pass


@dataclass
class ConversionReport:
    gnss_fixes: int = 0
    power_on_dropped: int = 0
    retimed: int = 0
    depth_packets: int = 0
    depth_other_sources: int = 0
    soundings_interpolated: int = 0
    dropped_no_fix: int = 0
    dropped_bad_depth: int = 0
    soundings: int = 0
    depth_sources: dict[int, int] = field(default_factory=dict)
    fix_times: list[float] = field(default_factory=list, repr=False)


@dataclass
class Conversion:
    document: dict[str, Any]
    report: ConversionReport
    start: datetime | None
    end: datetime | None


def _repair_packets(
    packets: list[Any], depth_source: int | None, params: RepairParameters, report: ConversionReport
) -> None:
    fixes = [p for p in packets if isinstance(p, GNSS) and p.elapsed is not None]
    report.gnss_fixes = len(fixes)
    if fixes:
        elapsed = np.array([p.elapsed / 1000.0 for p in fixes])
        claimed = np.array([p.msg_date * SECONDS_PER_DAY + p.msg_timestamp for p in fixes])
        repair = repair_gnss_times(elapsed, claimed, params)
        report.power_on_dropped = repair.dropped_power_on
        report.retimed = repair.retimed
        for fix, keep, t in zip(fixes, repair.keep, repair.times, strict=True):
            if not keep:
                fix.elapsed = None  # wibl-python skips packets without an elapsed time
                continue
            fix.msg_date = int(t // SECONDS_PER_DAY)
            fix.msg_timestamp = float(t - fix.msg_date * SECONDS_PER_DAY)
        report.fix_times = sorted(float(t) for t, k in zip(repair.times, repair.keep, strict=True) if k)

    for p in packets:
        if isinstance(p, Depth) and p.elapsed is not None:
            source = int(getattr(p, "talker_id", 0))
            report.depth_sources[source] = report.depth_sources.get(source, 0) + 1
            if depth_source is not None and source != depth_source:
                p.elapsed = None
                report.depth_other_sources += 1
            else:
                report.depth_packets += 1


@contextmanager
def _repairing_loader(
    depth_source: int | None, params: RepairParameters, report: ConversionReport
) -> Iterator[None]:
    original: Callable[..., Any] = wibl_ts.load_file

    def load_and_repair(filename: str, *args: Any, **kwargs: Any) -> Any:
        stats, time_source, packets, algorithms = original(filename, *args, **kwargs)
        _repair_packets(packets, depth_source, params, report)
        return stats, time_source, packets, algorithms

    wibl_ts.load_file = load_and_repair
    try:
        yield
    finally:
        wibl_ts.load_file = original


def _features(data: dict[str, Any], max_gap_s: float, report: ConversionReport) -> list[dict[str, Any]]:
    depth = data["depth"]
    t = np.asarray(depth["t"], dtype=np.float64)
    z = np.asarray(depth["z"], dtype=np.float64)
    lat = np.asarray(depth["lat"], dtype=np.float64)
    lon = np.asarray(depth["lon"], dtype=np.float64)
    report.soundings_interpolated = len(t)

    fixes = np.asarray(report.fix_times, dtype=np.float64)
    if len(fixes) == 0:
        near = np.zeros(len(t), dtype=bool)
    else:
        i = np.searchsorted(fixes, t)
        before = fixes[np.clip(i - 1, 0, len(fixes) - 1)]
        after = fixes[np.clip(i, 0, len(fixes) - 1)]
        near = np.minimum(np.abs(t - before), np.abs(after - t)) <= max_gap_s
    good_depth = np.isfinite(z) & (z > 0) & np.isfinite(lat) & np.isfinite(lon)
    report.dropped_no_fix = int((~near).sum())
    report.dropped_bad_depth = int((near & ~good_depth).sum())

    features = []
    for k in np.flatnonzero(near & good_depth):
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon[k]), float(lat[k])]},
                "properties": {
                    "depth": round(float(z[k]), 2),
                    "time": datetime.fromtimestamp(float(t[k]), UTC).strftime(FMT_TIME),
                },
            }
        )
    report.soundings = len(features)
    return features


def convert_wibl(path: Path, config: NodeConfig, params: RepairParameters | None = None) -> Conversion:
    """Decode, repair, time-interpolate and package ``path`` as a B-12 3.1 document (not yet trimmed)."""
    params = params or RepairParameters()
    report = ConversionReport()
    sink = io.StringIO()
    try:
        with redirect_stdout(sink), _repairing_loader(config.vessel.depth_source, params, report):
            data = wibl_ts.time_interpolation(
                str(path), Lineage(), ELAPSED_TIME_QUANTUM, fault_limit=10, process_algorithms=False
            )
    except Exception as e:  # wibl-python raises a variety of exception types
        raise ConversionError(f"{path.name}: {type(e).__name__}: {e}") from e

    features = _features(data, config.conversion.max_fix_gap_s, report)
    now = datetime.now(UTC).strftime(FMT_TIME)
    wibl_version = version("wibl-python")
    processing: list[dict[str, Any]] = [
        {
            "type": "TimeStampInterpolation",
            "timestamp": now,
            "method": "Linear interpolation of the logger elapsed clock against GNSS time",
            "algorithm": "wibl-python time_interpolation after csb-trusted-node GNSS time repair",
            "version": f"wibl-python {wibl_version}; csb-trusted-node {__version__}",
        },
        {
            "type": "Algorithm",
            "timestamp": now,
            "name": "gnss-time-repair",
            "source": "csb-trusted-node",
            "version": __version__,
            "parameters": {
                **params.as_b12(),
                "powerOnFixesDropped": report.power_on_dropped,
                "fixesRetimed": report.retimed,
            },
            "comment": "Fixes whose time disagrees with the logger clock are re-timed from it; "
            "fixes before the first plausible date are dropped.",
        },
        {
            "type": "Algorithm",
            "timestamp": now,
            "name": "sounding-selection",
            "source": "csb-trusted-node",
            "version": __version__,
            "parameters": {
                "depthSource": config.vessel.depth_source,
                "maxFixGap_s": config.conversion.max_fix_gap_s,
                "otherSourceDepthsDropped": report.depth_other_sources,
                "droppedNoNearbyFix": report.dropped_no_fix,
                "droppedInvalidDepth": report.dropped_bad_depth,
            },
        },
    ]
    document = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "properties": {
            "trustedNode": config.trusted_node(str(data.get("loggerversion") or "unknown")).to_b12(),
            "platform": config.platform_b12(),
            "processing": processing,
        },
        "features": features,
    }
    times = sorted(f["properties"]["time"] for f in features)
    start = datetime.strptime(times[0], FMT_TIME).replace(tzinfo=UTC) if times else None
    end = datetime.strptime(times[-1], FMT_TIME).replace(tzinfo=UTC) if times else None
    return Conversion(document, report, start, end)
