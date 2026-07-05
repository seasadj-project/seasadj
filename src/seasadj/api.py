"""Pythonic API: decompose() and the Decomposition result.

This module never touches the filesystem for input/output (only the
bundled para/ weight files, read-only). It normalizes plain Python
sequences into the 1-based arrays the ported core expects, runs the same
_pipeline() as run() (file mode), and converts the result back to
0-based lists.
"""

import io
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

from . import var
from .ftn import alloc
from .main import _pipeline
from .reg import SeasadjError, abort_run, det_hol_core, det_ao_core, det_ls_core

_MODEL_CODES = {"multiplicative": 0, "additive": 1, "log": 2}


@dataclass
class Decomposition:
    """Result of decompose(). All series are plain 0-based lists.

    n_total = n_observed + n_forecast (the Fortran adj_on): observed,
    prior_adjusted, trend, seasonal, irregular, adjusted and the effect
    series all run over the observed period plus any forecast extension;
    index n_observed onward is the forecast-extension period.

    Identities (within floating-point rounding):
      multiplicative / log : prior_adjusted ~= trend * seasonal * irregular
      additive              : prior_adjusted ~= trend + seasonal + irregular
    """

    observed: list
    prior_adjusted: list
    trend: list
    seasonal: list
    irregular: list
    adjusted: list
    holiday_effect: list
    ao_effect: list
    ls_effect: list
    n_observed: int
    n_forecast: int
    period: int
    model: str
    diagnostics: dict = field(default_factory=dict)
    internals: dict = field(default_factory=dict)


def _fill_1based(seq, max_t, name):
    """Copy a plain sequence into a fresh 1-based array. Mirrors read_data's
    "too many records" guard (reg.read_data), reworded for an in-memory
    argument rather than a file."""
    values = [float(v) for v in seq]
    n = len(values)
    if n > max_t:
        abort_run(f"{name} has too many observations"
                  f" ({n} > max_t={max_t}); this is a compile-time limit"
                  " in the ported Fortran core")
    arr = alloc(max_t)
    for i in range(1, n + 1):
        arr[i] = values[i - 1]
    return arr, n


def _weight_paths():
    para_dir = Path(var.bundled_para_dir())

    def w(rel):
        return str(para_dir / Path(rel).name)

    return {
        "wm3": w(var.wm3_w), "wm5": w(var.wm5_w), "wm9": w(var.wm9_w),
        "pwm3": w(var.pwm3_w), "pwm5": w(var.pwm5_w), "pwm9": w(var.pwm9_w),
        "h5": w(var.h5_w), "h7": w(var.h7_w), "h9": w(var.h9_w),
        "h13": w(var.h13_w), "h23": w(var.h23_w),
    }


def decompose(
    data,
    period,
    *,
    first_position=1,
    model="multiplicative",
    forecast=None,
    holiday_effect=None,
    holiday_regressor=None,
    holiday_coef=0.0,
    ao_effect=None,
    ls_effect=None,
    seasonal_ma=3,
    replace_extreme=True,
    sigma=(1.5, 2.5),
    ft_o=1,
    verbose=False,
):
    """Decompose a time series into trend, seasonal and irregular components
    (X-11 style, generalized to an arbitrary cycle length).

    Parameters (Fortran i00_inp.dat block / name in parenthesis):

      data               (required) : observed values, any sequence of
                                       numbers (list/tuple/np.ndarray/
                                       pd.Series). (i01_org_ser.dat)
      period             (required) : length of the seasonal cycle, e.g. 7
                                       for a day-of-week cycle in daily data.
                                       Must be 2 or larger. (G term)
      first_position=1              : cycle position of data[0] (1..period).
                                       (A ini_o_day)
      model="multiplicative"        : "multiplicative", "additive" or "log".
                                       (M model)
      forecast=None                 : forecast-extension values (e.g. from
                                       an X-13ARIMA-SEATS RegARIMA run), to
                                       extend the trend/seasonal estimate
                                       past the observed period.
                                       (B forecasting + i02_fct_ser.dat)
      holiday_effect=None           : holiday prior-adjustment factor per
                                       period (multiplicative: ~1; additive:
                                       ~0). (C reg_hol + i04_hol_eff.dat)
      holiday_regressor=None        : holiday regression variable; required
                                       when holiday_effect and forecast are
                                       both given (used to extend the
                                       holiday effect over the forecast
                                       period). (i03_hol_reg.dat)
      holiday_coef=0.0              : holiday regression coefficient.
                                       (D hol_reg_p)
      ao_effect=None                : additive-outlier prior-adjustment
                                       factor. (E reg_ao + i05_aol_eff.dat)
      ls_effect=None                : level-shift prior-adjustment factor.
                                       (F reg_ls + i06_lvs_eff.dat)
      seasonal_ma=3                 : initial seasonal moving average term,
                                       3, 5 or 9 (3x3/3x5/3x9). (H iwm_term)
      replace_extreme=True          : X-11 extreme SI-ratio replacement.
                                       (J rep_si)
      sigma=(1.5, 2.5)              : (lower, upper) sigma limits for extreme
                                       SI-ratio replacement. (K sig_l, L sig_u)
      ft_o=1                        : running position of the first
                                       observation (rarely changed from 1).
                                       (I ft_o)
      verbose=False                 : if True, print the same progress lines
                                       as the file-mode CLI; otherwise they
                                       are captured into
                                       diagnostics["log"] instead.

    Returns a Decomposition. Raises SeasadjError on invalid input (same
    conditions as the file-mode parameter/data validation).
    """
    if not isinstance(period, int) or period < 2:
        raise SeasadjError("period must be 2 or larger")
    term = period

    if not isinstance(first_position, int) or first_position < 1 or first_position > term:
        raise SeasadjError("first_position must be between 1 and period")

    if model not in _MODEL_CODES:
        raise SeasadjError("model must be 'multiplicative', 'additive' or 'log'"
                          " (numeric 0/1/2 is not accepted)")
    model_code = _MODEL_CODES[model]

    if seasonal_ma not in (3, 5, 9):
        raise SeasadjError("seasonal_ma must be 3, 5 or 9")

    if not isinstance(ft_o, int) or ft_o < 1:
        raise SeasadjError("ft_o must be 1 or larger")

    rep_si = 1 if replace_extreme else 0
    sig_l, sig_u = sigma
    if rep_si == 1:
        if sig_l <= 0.0:
            raise SeasadjError("sigma[0] (lower) must be positive")
        if sig_u <= sig_l:
            raise SeasadjError("sigma[1] (upper) must be larger than sigma[0]")

    if holiday_effect is not None and forecast is not None and holiday_regressor is None:
        raise SeasadjError("holiday_regressor is required when holiday_effect"
                          " and forecast are both given (to extend the"
                          " holiday effect over the forecast period)")

    max_t = var.max_t

    obs, max_on = _fill_1based(data, max_t, "data")

    if forecast is not None:
        lead_o, lead_on = _fill_1based(forecast, max_t, "forecast")
        forecasting = 1
    else:
        lead_o, lead_on = alloc(max_t), 0
        forecasting = 0

    reg_hol = 1 if holiday_effect is not None else 0
    if reg_hol == 1:
        hol_eff, hol_eff_n = _fill_1based(holiday_effect, max_t, "holiday_effect")
    else:
        hol_eff, hol_eff_n = alloc(max_t), 0
    if holiday_regressor is not None:
        hol_regdat, hol_regdat_n = _fill_1based(holiday_regressor, max_t, "holiday_regressor")
    else:
        hol_regdat, hol_regdat_n = None, 0
    hol_eff_n = det_hol_core(reg_hol, hol_eff, hol_eff_n, hol_regdat, hol_regdat_n,
                             holiday_coef, max_on, lead_on, model_code)

    reg_ao = 1 if ao_effect is not None else 0
    if reg_ao == 1:
        ao_eff, ao_eff_n = _fill_1based(ao_effect, max_t, "ao_effect")
    else:
        ao_eff, ao_eff_n = alloc(max_t), 0
    ao_eff_n = det_ao_core(reg_ao, ao_eff, ao_eff_n, max_on, lead_on, model_code)

    reg_ls = 1 if ls_effect is not None else 0
    if reg_ls == 1:
        ls_eff, ls_eff_n = _fill_1based(ls_effect, max_t, "ls_effect")
    else:
        ls_eff, ls_eff_n = alloc(max_t), 0
    ls_eff_n = det_ls_core(reg_ls, ls_eff, ls_eff_n, max_on, lead_on, model_code)

    weights = _weight_paths()

    log_buf = io.StringIO()
    if verbose:
        r = _pipeline(max_t, term, seasonal_ma, ft_o, rep_si, sig_l, sig_u,
                      model_code, forecasting, first_position, max_on, lead_on,
                      obs, lead_o, hol_eff, hol_eff_n, ao_eff, ao_eff_n,
                      ls_eff, ls_eff_n, weights)
    else:
        with redirect_stdout(log_buf):
            r = _pipeline(max_t, term, seasonal_ma, ft_o, rep_si, sig_l, sig_u,
                          model_code, forecasting, first_position, max_on,
                          lead_on, obs, lead_o, hol_eff, hol_eff_n, ao_eff,
                          ao_eff_n, ls_eff, ls_eff_n, weights)

    si_replaced = ([(r.rep1_cnt, r.rep1_checked), (r.rep2_cnt, r.rep2_checked)]
                  if r.rep1_printed or r.rep2_printed else [])

    diagnostics = {
        "h_terms": [r.ih_term, r.fh_term],
        "sum_ratios": [r.ih_ratio, r.fh_ratio],
        "swm_term": r.swm_term,
        "msr_ratio": r.msr_ratio,
        "msr_count": r.msr_count,
        "si_replaced": si_replaced,
        "bias_sig": r.bias_sig,
        "log": log_buf.getvalue(),
    }

    # internals: 1-based -> 0-based, using each series' own valid length
    # (the series-edge padding convention -- 0.0/-999.0/w=1.0 -- is the same
    # as the corresponding file output; see 05_Python/README.md)
    internals = {
        "TC1": r.TC1[1:r.adj_on + 1],
        "SI1": r.SI1[1:r.adj_on + 1],
        "w1": r.w1[1:r.adj_on + 1],
        "SI1r": r.SI1r[1:r.adj_on + 1],
        "S1p": r.S1p[1:r.S1p_n + 1],
        "S1": r.S1[1:r.S1_n + 1],
        "A1": r.A1[1:r.A1_n + 1],
        "TC2": r.TC2[1:r.TC2_n + 1],
        "SI2": r.SI2[1:r.SI2_n + 1],
        "w2": r.w2[1:r.w2_n + 1],
        "SI2r": r.SI2r[1:r.SI2r_n + 1],
        "S2p": r.S2p[1:r.S2p_n + 1],
        "ft_SI1": r.ft_SI1,
    }

    return Decomposition(
        observed=obs[1:max_on + 1],
        prior_adjusted=r.adj_o[1:r.adj_on + 1],
        trend=r.TC3[1:r.TC3_n + 1],
        seasonal=r.S2[1:r.S2_n + 1],
        irregular=r.I3[1:r.I3_n + 1],
        adjusted=r.A2[1:r.A2_n + 1],
        holiday_effect=hol_eff[1:r.adj_on + 1],
        ao_effect=ao_eff[1:r.adj_on + 1],
        ls_effect=ls_eff[1:r.adj_on + 1],
        n_observed=max_on,
        n_forecast=lead_on,
        period=term,
        model=model,
        diagnostics=diagnostics,
        internals=internals,
    )
