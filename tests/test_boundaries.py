"""Boundary-condition coverage for input validation (src/seasadj/reg.py
check_inputs and api.decompose's own argument checks).

None of test_api.py's existing tests probe the exact minimum-length
thresholds, the fixed validation order (length before sign), or the
successful side of the argument-range checks -- see
作業指示（偶数周期・境界条件テスト拡充）.md §3. This file adds that coverage with
deterministic, closed-form data (no RNG, no private data).
"""

import math

import pytest

from seasadj import decompose, SeasadjError
from seasadj.var import max_t as MAX_T


def _series(n):
    """Deterministic, positive series -- content is irrelevant to these
    tests, only the length and sign matter."""
    return [100.0 + 0.1 * i + 5.0 * math.sin(i * 0.37) for i in range(n)]


# ---------------------------------------------------------------------------
# B-1 / B-2: the three length thresholds in check_inputs, in the order they
# are evaluated:
#   (1) max_on < 20
#   (2) max_on + lead_on < term * (seasonal_ma + 3)
#   (3) rep_si and max_on + lead_on < term * 8      (rwm_term = 5 -> term*8)
#
# label, period, seasonal_ma, replace_extreme, min_len, message substring of
# whichever threshold actually binds at min_len - 1 (worked out by hand
# below, and cross-checked against the implementation by
# test_min_length_table_matches_formula).

CASES = [
    ("a", 2, 3, True, 20, "at least 20 observations"),
    ("b", 4, 3, True, 32, "too short for the extreme SI replacement"),
    ("c", 4, 3, False, 24, "too short for the seasonal filters"),
    ("d", 4, 9, True, 48, "too short for the seasonal filters"),
    ("e", 7, 3, True, 56, "too short for the extreme SI replacement"),
    ("f", 12, 3, True, 96, "too short for the extreme SI replacement"),
]


def _min_length(period, seasonal_ma, replace_extreme):
    thresholds = [20, period * (seasonal_ma + 3)]
    if replace_extreme:
        thresholds.append(period * 8)
    return max(thresholds)


@pytest.mark.parametrize("label,period,seasonal_ma,replace_extreme,min_len,message", CASES)
def test_min_length_table_matches_formula(label, period, seasonal_ma, replace_extreme,
                                          min_len, message):
    assert _min_length(period, seasonal_ma, replace_extreme) == min_len


@pytest.mark.parametrize("label,period,seasonal_ma,replace_extreme,min_len,message", CASES)
def test_min_length_succeeds_at_minimum(label, period, seasonal_ma, replace_extreme,
                                        min_len, message):
    data = _series(min_len)
    r = decompose(data, period, seasonal_ma=seasonal_ma, replace_extreme=replace_extreme)
    assert r.n_observed == min_len


@pytest.mark.parametrize("label,period,seasonal_ma,replace_extreme,min_len,message", CASES)
def test_min_length_fails_one_below_minimum(label, period, seasonal_ma, replace_extreme,
                                            min_len, message):
    data = _series(min_len - 1)
    with pytest.raises(SeasadjError, match=message):
        decompose(data, period, seasonal_ma=seasonal_ma, replace_extreme=replace_extreme)


# ---------------------------------------------------------------------------
# B-3: validation order is fixed -- length is checked before sign, so data
# that is both too short and non-positive raises the length error, not the
# positive-value error (引継ぎ資料.md §6; Fortran and Python agree on this
# order).

def test_length_error_precedes_positivity_error():
    period = 7
    min_len = _min_length(period, seasonal_ma=3, replace_extreme=True)  # 56
    data = [-1.0] * (min_len - 1)  # too short AND non-positive, multiplicative model
    with pytest.raises(SeasadjError, match="too short for the extreme SI replacement"):
        decompose(data, period)


# ---------------------------------------------------------------------------
# B-4: the successful side of argument-range checks (test_api.py's
# test_validation_errors only exercises the failing side)

def test_period_lower_bound_2_succeeds():
    data = _series(40)
    r = decompose(data, 2)
    assert r.period == 2


@pytest.mark.parametrize("first_position", [1, 4])
def test_first_position_boundaries_succeed_for_even_period(first_position):
    period = 4
    data = _series(period * 12)
    r = decompose(data, period, first_position=first_position)
    assert r.period == period


@pytest.mark.parametrize("seasonal_ma", [3, 5, 9])
def test_seasonal_ma_all_valid_values_succeed(seasonal_ma):
    period = 7
    n = period * 12
    data = _series(n)
    r = decompose(data, period, seasonal_ma=seasonal_ma)
    assert r.n_observed == n


def test_sigma_strict_inequality_succeeds():
    data = _series(56)
    r = decompose(data, 7, sigma=(1.5, 2.5))
    assert r.n_observed == 56


def test_sigma_equal_bounds_rejected():
    # reg.check_inputs / api.decompose require sig_u strictly greater than
    # sig_l (`if sig_u <= sig_l: abort`), so equal bounds are rejected, not
    # accepted -- confirmed by reading the implementation, not assumed.
    data = _series(56)
    with pytest.raises(SeasadjError, match="must be larger than"):
        decompose(data, 7, sigma=(2.0, 2.0))


# ---------------------------------------------------------------------------
# B-5: max_t upper bound (src/seasadj/var.py max_t = 7300; guarded in
# api._fill_1based)
#
# Known boundary defect (found while writing this section, 2026-09-01;
# confirmed independently by both a Fable-model subagent and a separate
# user-run Opus session): when max_on + lead_on == max_t exactly AND
# lead_on == 0, reg.week()'s min(max_on+lead_on+1, max_t) clamp leaves
# weekday[max_t] as the last filled slot, but st2.det_swm() unconditionally
# reads weekday[max_on + 1] (= weekday[max_t + 1], one past that fill and
# past the allocated array -- weekday = ialloc(max_t) has indices 0..max_t
# only) -- an unhandled IndexError instead of a successful (or cleanly
# rejected) result. Confirmed present in the Fortran reference too
# (03_reg.f90 week(), 06_st2.f90 det_swm(): identical clamp, identical +1
# read, weekday declared with no headroom) -- a latent defect in the
# original design, not a Python-port regression. Not fixed here (src/ must
# not change this month); tracked for a dedicated future work order
# (作業指示（max_t境界修正：weekday配列オーバーフロー）, targeted for
# v1.1.0/October). Measured (2026-09-01, this environment): n=7299 (no
# forecast) succeeds in ~0.25s; n=7300 (no forecast) raises IndexError in
# ~0.16s; n=7301 raises a clean SeasadjError immediately (length guard fires
# before any pipeline work); max_on=7293 + forecast=7 (also totalling 7300,
# but lead_on > 0) succeeds in ~0.23s, confirming the defect's trigger is
# exactly "== max_t AND lead_on == 0", not "== max_t" alone.

def test_max_t_upper_bound_succeeds_one_below_limit():
    data = _series(MAX_T - 1)
    r = decompose(data, 7)
    assert r.n_observed == MAX_T - 1


def test_max_t_upper_bound_succeeds_at_limit():
    data = _series(MAX_T)
    r = decompose(data, 7)
    assert r.n_observed == MAX_T


def test_max_t_upper_bound_rejected_just_above():
    data = _series(MAX_T + 1)
    with pytest.raises(SeasadjError, match="too many observations"):
        decompose(data, 7)


def test_max_t_upper_bound_succeeds_at_limit_with_forecast():
    # same total length as test_max_t_upper_bound_succeeds_at_limit (7300),
    # but split across data + forecast so lead_on > 0 -- the known defect
    # above only triggers when lead_on == 0, so this must succeed.
    n_observed = MAX_T - 7
    n_forecast = 7
    data = _series(n_observed)
    forecast = _series(n_forecast)
    r = decompose(data, 7, forecast=forecast)
    assert r.n_observed == n_observed
    assert r.n_forecast == n_forecast
    assert r.n_observed + r.n_forecast == MAX_T
