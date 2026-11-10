import numpy as np
import pytest

from csb_trusted_node.gnss_time import NoGoodTime, repair_gnss_times

T0 = 1_768_478_400.0  # 2026-01-15 12:00 UTC
PLACEHOLDER = 1_520_596_800.0  # 2018-03-09 12:00 UTC


def series(n: int = 3000, *, offset: float = T0 - 30.0) -> tuple[np.ndarray, np.ndarray]:
    elapsed = 30.0 + np.arange(n, dtype=np.float64)
    return elapsed, elapsed + offset


def test_clean_series_is_untouched() -> None:
    elapsed, gnss = series()
    r = repair_gnss_times(elapsed, gnss)
    assert r.keep.all()
    assert r.retimed == 0 and r.dropped_power_on == 0
    np.testing.assert_array_equal(r.times, gnss)


def test_power_on_placeholders_are_dropped() -> None:
    elapsed, gnss = series()
    gnss[:3] = PLACEHOLDER + np.arange(3)
    r = repair_gnss_times(elapsed, gnss)
    assert r.dropped_power_on == 3
    assert not r.keep[:3].any() and r.keep[3:].all()
    assert np.isnan(r.times[:3]).all()


def test_midnight_rollover_is_retimed() -> None:
    elapsed, gnss = series()
    gnss[1500] += 86400.0  # date rolled over a second early
    r = repair_gnss_times(elapsed, gnss)
    assert r.retimed_indices == [1500]
    assert r.times[1500] == pytest.approx(T0 - 30.0 + elapsed[1500])


@pytest.mark.parametrize(
    ("start", "length", "shift"), [(1000, 600, 5.0), (1200, 540, 20_883.0), (900, 1, -9.0)]
)
def test_steps_are_retimed_and_kept(start: int, length: int, shift: float) -> None:
    elapsed, gnss = series()
    gnss[start : start + length] += shift
    r = repair_gnss_times(elapsed, gnss)
    assert r.keep.all()
    assert r.retimed_indices == list(range(start, start + length))
    np.testing.assert_allclose(r.times, elapsed + T0 - 30.0)


def test_late_wrong_date_is_retimed_not_treated_as_power_on() -> None:
    elapsed, gnss = series()
    gnss[10] -= 286 * 86400.0  # right time of day, wrong (but post-floor) date
    r = repair_gnss_times(elapsed, gnss)
    assert r.dropped_power_on == 0
    assert r.retimed_indices == [10]


def test_small_jitter_is_not_a_fault() -> None:
    elapsed, gnss = series()
    gnss += np.random.default_rng(1).normal(0.0, 0.2, len(gnss))
    assert repair_gnss_times(elapsed, gnss).retimed == 0


def test_no_plausible_fix_raises() -> None:
    elapsed, _ = series(10)
    with pytest.raises(NoGoodTime):
        repair_gnss_times(elapsed, PLACEHOLDER + elapsed)
