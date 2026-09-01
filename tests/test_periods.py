"""Even-period coverage for the public test suite.

The private golden data (G1~G7) exercises period=4 (G4/G5) and period=7, but
those tests are skipped wherever the golden data is not present (see
test_golden.py) -- i.e. for every pip install and every JOSS reviewer. This
file gives the even/odd branch in `st1.mov_ave` (and the parallel branches in
`Ini_SI`/`std_sf`) public, decision-independent coverage across periods
2/4/12/24 and all three models, using only deterministic closed-form data (no
RNG, no private data). See 引継ぎ資料.md §6 and CHANGELOG.md.
"""

import math
import shutil

import pytest

from seasadj import decompose, run, SeasadjError
from seasadj.var import bundled_para_dir

from conftest import _write_i00, _write_series, _read_series


# ---------------------------------------------------------------------------
# 0. Synthetic data generators with an explicit, known seasonal factor
# (unlike test_api.py's synth(), which only has an implicit sine-wave
# seasonal shape). Mirrors the design of the private G4/G5 golden cases
# (04_検証データ/README.md §3).

def make_multiplicative(n, period, factors, phase_len=3, t0=0):
    """trend x seasonal x irregular. factors is length period, average 1.0.

    irregular's own period (phase_len) must be coprime with period, so it
    does not alias into the seasonal component.
    """
    out = []
    for k in range(n):
        t = t0 + k
        trend = 100.0 + 0.05 * t
        seasonal = factors[t % period]
        irregular = 1.0 + 0.005 * math.sin(2 * math.pi * t / phase_len)
        out.append(trend * seasonal * irregular)
    return out


def make_additive(n, period, factors, phase_len=3, t0=0):
    """trend + seasonal + irregular. factors is length period, summing to 0.0."""
    out = []
    for k in range(n):
        t = t0 + k
        trend = 100.0 + 0.05 * t
        seasonal = factors[t % period]
        irregular = 0.05 * math.sin(2 * math.pi * t / phase_len)
        out.append(trend + seasonal + irregular)
    return out


def _coprime_phase(period):
    """A phase_len coprime with period, for the irregular component above."""
    for candidate in (3, 5, 7, 11, 13):
        if math.gcd(period, candidate) == 1:
            return candidate
    raise AssertionError(f"no coprime phase_len found for period={period}")


def _mult_factors(period, amplitude=0.10):
    """Generic factors for A-1/A-4/A-5/A-6/A-7 (average exactly 1.0 -- the
    mean of a full cosine cycle over integer sample points is 0)."""
    return [1.0 + amplitude * math.cos(2 * math.pi * k / period) for k in range(period)]


def _add_factors(period, amplitude=10.0):
    """Generic factors for A-1/A-3/A-7 (summing to exactly 0.0, same reasoning)."""
    return [amplitude * math.cos(2 * math.pi * k / period) for k in range(period)]


def _identity_ok(model, pa, t, s, irr):
    combined = (t + s + irr) if model == "additive" else (t * s * irr)
    return abs(pa - combined) <= 1e-9 * (1 + abs(pa))


# ---------------------------------------------------------------------------
# A-1: even period x all models -- identity and lengths

@pytest.mark.parametrize("model", ["multiplicative", "additive", "log"])
@pytest.mark.parametrize("period", [2, 4, 12, 24])
def test_even_period_identity_and_length(period, model):
    n = max(20, period * 12)
    phase_len = _coprime_phase(period)
    if model == "additive":
        data = make_additive(n, period, _add_factors(period), phase_len)
    else:
        data = make_multiplicative(n, period, _mult_factors(period), phase_len)

    r = decompose(data, period, model=model)

    n_total = r.n_observed + r.n_forecast
    assert n_total == n
    assert len(r.trend) == n_total
    assert len(r.seasonal) == n_total
    assert len(r.irregular) == n_total
    assert len(r.adjusted) == n_total
    assert r.period == period

    for pa, t, s, irr in zip(r.prior_adjusted, r.trend, r.seasonal, r.irregular):
        assert _identity_ok(model, pa, t, s, irr)


# ---------------------------------------------------------------------------
# A-2: recovery of a known seasonal pattern (the only test that checks the
# even branch is *correct*, not just that it runs)

def _position_means(seasonal, period, n_total, skip=None):
    """Average `seasonal` by cycle position (index % period), excluding the
    first and last `skip` observations (default: one full period) -- series
    edges are weak estimates since the moving averages are not centered
    there."""
    if skip is None:
        skip = period
    sums = [0.0] * period
    counts = [0] * period
    for i, s in enumerate(seasonal):
        if i < skip or i >= n_total - skip:
            continue
        p = i % period
        sums[p] += s
        counts[p] += 1
    assert all(c > 0 for c in counts), "not enough data to cover every cycle position"
    return [sums[p] / counts[p] for p in range(period)]


def test_even_period_recovers_multiplicative_pattern_period4():
    period = 4
    factors = [1.08, 0.97, 0.98, 0.97]  # same values as the private G5 case
    n = period * 30
    data = make_multiplicative(n, period, factors, phase_len=3)

    r = decompose(data, period)
    means = _position_means(r.seasonal, period, n)
    errors = [abs(m - f) for m, f in zip(means, factors)]
    max_err = max(errors)

    # measured (2026-09-01, this environment): max_err ~= 0.00997 (~0.9% of
    # the seasonal swing, amplitude 0.11). Threshold set to ~3x that, rounded.
    assert max_err <= 0.03, f"errors={errors}"


def test_even_period_recovers_additive_pattern_period4():
    period = 4
    factors = [8.0, -3.0, -2.0, -3.0]  # same values as the private G4 case
    n = period * 30
    data = make_additive(n, period, factors, phase_len=3)

    r = decompose(data, period, model="additive")
    means = _position_means(r.seasonal, period, n)
    errors = [abs(m - f) for m, f in zip(means, factors)]
    max_err = max(errors)

    # measured (2026-09-01, this environment): max_err ~= 0.045 (amplitude 8,
    # i.e. well under 1%). Threshold set to ~3x that, rounded.
    assert max_err <= 0.15, f"errors={errors}"


def test_even_period_recovers_multiplicative_pattern_period12():
    period = 12
    factors = _mult_factors(period, amplitude=0.08)  # monthly-like, even period > 4
    n = period * 30
    data = make_multiplicative(n, period, factors, phase_len=_coprime_phase(period))

    r = decompose(data, period)
    means = _position_means(r.seasonal, period, n)
    errors = [abs(m - f) for m, f in zip(means, factors)]
    max_err = max(errors)

    # measured (2026-09-01, this environment): max_err ~= 0.0012 (amplitude
    # 0.08). Threshold set to ~3x that, rounded.
    assert max_err <= 0.005, f"errors={errors}"


# ---------------------------------------------------------------------------
# A-3: even period, file-mode / API strict equality (existing coverage in
# test_api.py is period=7, multiplicative, default parameters only)

def test_even_period_api_matches_file_mode(tmp_path):
    period = 4
    n = period * 12
    factors = _add_factors(period)
    data = make_additive(n, period, factors, phase_len=3)

    wd = tmp_path / "wd"
    (wd / "in_data").mkdir(parents=True)
    shutil.copytree(bundled_para_dir(), wd / "para")

    _write_i00(wd / "in_data" / "i00_inp.dat", term=period, rep_si=0, model=1)
    _write_series(wd / "in_data" / "i01_org_ser.dat", data)

    run(wd)

    exp_seasonal = _read_series(wd / "out_data" / "o16__S2.dat")
    exp_adjusted = _read_series(wd / "out_data" / "o17__A2.dat")
    exp_trend = _read_series(wd / "out_data" / "o18_TC3.dat")
    exp_irregular = _read_series(wd / "out_data" / "o19__I3.dat")

    r = decompose(data, period, model="additive", replace_extreme=False)

    assert r.seasonal == exp_seasonal
    assert r.adjusted == exp_adjusted
    assert r.trend == exp_trend
    assert r.irregular == exp_irregular


# ---------------------------------------------------------------------------
# A-4: even period x first_position, all positions

@pytest.mark.parametrize("first_position", [1, 2, 3, 4])
def test_even_period_first_position_valid(first_position):
    period = 4
    n = period * 12
    data = make_multiplicative(n, period, _mult_factors(period), phase_len=3)

    r = decompose(data, period, first_position=first_position)
    n_total = r.n_observed + r.n_forecast
    for pa, t, s, irr in zip(r.prior_adjusted, r.trend, r.seasonal, r.irregular):
        assert _identity_ok("multiplicative", pa, t, s, irr)


def test_even_period_first_position_invariant():
    """first_position (ini_o_day) must NOT change the decomposition itself --
    this is a regression guard, not a demonstration that the argument "does
    something": relabeling which cycle position data[0] belongs to must not
    change what the seasonal pattern *is*.

    Confirmed (design consult 2026-09-01, cross-checked independently by
    both a Fable-model subagent and a separate user-run Opus session; both
    agree, correcting this task's original instruction which wrongly
    expected `seasonal` to differ): the core filters (st1.mov_ave/Ini_SI/
    std_sf, wma.wm_ave) key off the series' own relative position and never
    read `weekday`/ini_o_day at all -- confirmed absent from the Fortran
    reference's 05_st1.f90 too. The only numeric consumer of `weekday` is
    st2.det_swm()'s Global MSR calculation, in two ways: (a) bucketing
    indices by `weekday[k] == j` -- first_position only relabels which
    bucket an index falls into, and since det_swm sums every bucket
    together this cancels out; (b) `edge = max_on - weekday[max_on+1] + 1`,
    an edge-trim point that genuinely does shift with first_position, so
    msr_ratio *can* differ (must not be asserted equal here -- see below).
    `seasonal` only moves if a different msr_ratio happens to cross one of
    det_swm's four fixed thresholds (c_AB/c_BC/c_CD/c_DE) and so picks a
    different swm_term (3/5/9); that crossing case is real (confirmed with
    period=12, n=160, irregular amplitude 0.08: msr_ratio 6.08-6.51 straddles
    c_DE=6.5) but is deliberately NOT exercised here -- it sits right on a
    threshold and would be unstable across the CI matrix (2 OSes x 3 Python
    versions). This test's invariance therefore only holds because the
    chosen data keeps msr_ratio far from every threshold -- if a future
    edit narrows that margin, this test's own construction stops being
    valid before the assertion does.

    measured (2026-09-01, this environment): msr_ratio = 120.3 / 121.6 /
    134.0 / 145.9 for first_position 1/2/3/4 -- all far above c_DE=6.5, so
    swm_term stays 9 throughout and `seasonal` is bit-identical across all
    four positions.
    """
    period = 4
    factors = [1.08, 0.97, 0.98, 0.97]  # same data as the A-2 recovery test
    n = period * 30
    data = make_multiplicative(n, period, factors, phase_len=3)

    results = [decompose(data, period, first_position=fp) for fp in (1, 2, 3, 4)]

    seasonal_set = {tuple(r.seasonal) for r in results}
    trend_set = {tuple(r.trend) for r in results}
    irregular_set = {tuple(r.irregular) for r in results}
    adjusted_set = {tuple(r.adjusted) for r in results}

    assert len(seasonal_set) == 1, "seasonal changed with first_position"
    assert len(trend_set) == 1, "trend changed with first_position"
    assert len(irregular_set) == 1, "irregular changed with first_position"
    assert len(adjusted_set) == 1, "adjusted changed with first_position"


# ---------------------------------------------------------------------------
# A-5: even period x forecast extension

def test_even_period_forecast_extension():
    period = 4
    n = period * 12
    n_forecast = period * 2
    factors = _mult_factors(period)
    data = make_multiplicative(n, period, factors, phase_len=3)
    forecast = make_multiplicative(n_forecast, period, factors, phase_len=3, t0=n)

    r = decompose(data, period, forecast=forecast)

    assert r.n_forecast == n_forecast
    n_total = r.n_observed + r.n_forecast
    assert n_total == n + n_forecast
    assert len(r.trend) == n_total
    assert len(r.seasonal) == n_total
    for pa, t, s, irr in zip(r.prior_adjusted, r.trend, r.seasonal, r.irregular):
        assert _identity_ok("multiplicative", pa, t, s, irr)


# ---------------------------------------------------------------------------
# A-6: even period x seasonal_ma x replace_extreme grid

@pytest.mark.parametrize("replace_extreme", [True, False])
@pytest.mark.parametrize("seasonal_ma", [3, 5, 9])
def test_even_period_seasonal_ma_and_replace_extreme(seasonal_ma, replace_extreme):
    period = 4
    n = period * 12  # covers the seasonal_ma=9 minimum (period*(9+3))
    data = make_multiplicative(n, period, _mult_factors(period), phase_len=3)

    r = decompose(data, period, seasonal_ma=seasonal_ma, replace_extreme=replace_extreme)
    n_total = r.n_observed + r.n_forecast
    assert n_total == n
    for pa, t, s, irr in zip(r.prior_adjusted, r.trend, r.seasonal, r.irregular):
        assert _identity_ok("multiplicative", pa, t, s, irr)


# ---------------------------------------------------------------------------
# A-7: even/odd branch actually taken -- edge padding count in o08_TC1.dat

@pytest.mark.parametrize("model,model_code,pad_val", [
    ("multiplicative", 0, 0.0),
    ("additive", 1, -999.0),
])
@pytest.mark.parametrize("period", [4, 7])
def test_tc1_edge_padding_count_matches_even_odd_formula(tmp_path, period, model,
                                                          model_code, pad_val):
    n = period * 12
    phase_len = _coprime_phase(period)
    if model == "additive":
        data = make_additive(n, period, _add_factors(period), phase_len)
    else:
        data = make_multiplicative(n, period, _mult_factors(period), phase_len)

    wd = tmp_path / "wd" / f"{period}-{model}"
    (wd / "in_data").mkdir(parents=True)
    shutil.copytree(bundled_para_dir(), wd / "para")

    _write_i00(wd / "in_data" / "i00_inp.dat", term=period, model=model_code)
    _write_series(wd / "in_data" / "i01_org_ser.dat", data)

    run(wd)

    tc1 = _read_series(wd / "out_data" / "o08_TC1.dat")

    leading = 0
    for v in tc1:
        if v == pad_val:
            leading += 1
        else:
            break
    trailing = 0
    for v in reversed(tc1):
        if v == pad_val:
            trailing += 1
        else:
            break

    # mov_ave: odd term pads (term-1)/2 per side (term-1 total),
    # even term pads term/2 per side (term total) -- see 05_st1.f90 / st1.mov_ave
    expected_per_side = (period - 1) // 2 if period % 2 == 1 else period // 2
    assert leading == expected_per_side, f"leading={leading}, expected={expected_per_side}"
    assert trailing == expected_per_side, f"trailing={trailing}, expected={expected_per_side}"
