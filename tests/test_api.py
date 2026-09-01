"""Public tests for the Pythonic API (decompose/Decomposition).

Uses only deterministic, artificial data (no private golden data), so this
file runs in any environment the package is installed in. See test_golden.py
for the (private-data-only) Fortran-output regression tests.
"""

import math
import shutil

import pytest

from seasadj import decompose, run, SeasadjError
from seasadj.var import bundled_para_dir

from conftest import _write_i00, _write_series, _read_series


def synth(n, period, phase=0):
    """Deterministic, positive, mildly seasonal series (closed-form, no RNG)."""
    out = []
    for i in range(n):
        trend = 100.0 + 0.05 * i
        seas = 1.0 + 0.2 * math.sin(2 * math.pi * ((i + phase) % period) / period)
        irr = 1.0 + 0.01 * math.sin(1.7 * i + 0.3)
        out.append(trend * seas * irr)
    return out


# ---------------------------------------------------------------------------
# 1. API / file mode equivalence
# (_write_i00 / _write_series / _read_series now live in conftest.py, shared
# with test_periods.py and test_boundaries.py)


def test_api_matches_file_mode(tmp_path):
    data = synth(420, 7)

    wd = tmp_path / "wd"
    (wd / "in_data").mkdir(parents=True)
    shutil.copytree(bundled_para_dir(), wd / "para")

    _write_i00(wd / "in_data" / "i00_inp.dat")
    _write_series(wd / "in_data" / "i01_org_ser.dat", data)

    run(wd)

    exp_seasonal = _read_series(wd / "out_data" / "o16__S2.dat")
    exp_adjusted = _read_series(wd / "out_data" / "o17__A2.dat")
    exp_trend = _read_series(wd / "out_data" / "o18_TC3.dat")
    exp_irregular = _read_series(wd / "out_data" / "o19__I3.dat")

    r = decompose(data, 7)

    assert r.seasonal == exp_seasonal
    assert r.adjusted == exp_adjusted
    assert r.trend == exp_trend
    assert r.irregular == exp_irregular


# ---------------------------------------------------------------------------
# 2. Identity: prior_adjusted ~= trend (op) seasonal (op) irregular

@pytest.mark.parametrize("model", ["multiplicative", "additive", "log"])
def test_identity_holds(model):
    data = synth(420, 7)
    r = decompose(data, 7, model=model)
    for pa, t, s, irr in zip(r.prior_adjusted, r.trend, r.seasonal, r.irregular):
        combined = (t + s + irr) if model == "additive" else (t * s * irr)
        assert abs(pa - combined) <= 1e-9 * (1 + abs(pa))


# ---------------------------------------------------------------------------
# 3. Even period

def test_even_period():
    data = synth(360, 12)
    r = decompose(data, 12)
    n_total = r.n_observed + r.n_forecast
    assert len(r.trend) == n_total
    assert len(r.seasonal) == n_total
    assert len(r.irregular) == n_total
    assert len(r.adjusted) == n_total
    for pa, t, s, irr in zip(r.prior_adjusted, r.trend, r.seasonal, r.irregular):
        assert abs(pa - t * s * irr) <= 1e-9 * (1 + abs(pa))


# ---------------------------------------------------------------------------
# 4. forecast + AO/LS path

def test_forecast_and_ao_ls():
    data = synth(420, 7)
    forecast = synth(21, 7, phase=420)
    ao_effect = [0.0] * 441
    ao_effect[50] = 3.0
    ls_effect = [0.0] * 441
    ls_effect[300] = -2.0

    r = decompose(data, 7, model="additive", forecast=forecast,
                  ao_effect=ao_effect, ls_effect=ls_effect)

    assert r.n_forecast == 21
    assert r.n_observed == 420
    n_total = r.n_observed + r.n_forecast
    assert len(r.trend) == n_total
    for pa, t, s, irr in zip(r.prior_adjusted, r.trend, r.seasonal, r.irregular):
        assert abs(pa - (t + s + irr)) <= 1e-9 * (1 + abs(pa))


# ---------------------------------------------------------------------------
# 5. Validation errors

def test_validation_errors():
    data = synth(420, 7)
    forecast = synth(21, 7, phase=420)

    with pytest.raises(SeasadjError):
        decompose(data, 1)
    with pytest.raises(SeasadjError):
        decompose(data, 7, first_position=0)
    with pytest.raises(SeasadjError):
        decompose(data, 7, first_position=8)
    with pytest.raises(SeasadjError):
        decompose(data, 7, model="foo")
    with pytest.raises(SeasadjError):
        decompose(data, 7, seasonal_ma=4)
    with pytest.raises(SeasadjError):
        decompose(data, 7, sigma=(2.5, 1.5))
    with pytest.raises(SeasadjError):
        decompose(data, 7, holiday_effect=[1.0] * 420, forecast=forecast,
                  holiday_regressor=None)


# ---------------------------------------------------------------------------
# 6. Determinism

def test_deterministic():
    data = synth(420, 7)
    r1 = decompose(data, 7)
    r2 = decompose(data, 7)
    assert r1.trend == r2.trend
    assert r1.seasonal == r2.seasonal
    assert r1.irregular == r2.irregular
    assert r1.adjusted == r2.adjusted
    assert r1.diagnostics == r2.diagnostics


# ---------------------------------------------------------------------------
# 7. verbose

def test_verbose_default_silent(capsys):
    data = synth(420, 7)
    r = decompose(data, 7)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "h_term" in r.diagnostics["log"]


def test_verbose_true_prints(capsys):
    data = synth(420, 7)
    decompose(data, 7, verbose=True)
    captured = capsys.readouterr()
    assert "h_term" in captured.out
