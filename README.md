# seasadj

X-11 style seasonal adjustment, generalized to an arbitrary cycle length.
`period=7` for the day-of-week cycle of daily data, `period=12` for monthly
data, or any other cycle length your data has — X-13ARIMA-SEATS only
handles monthly and quarterly data, and this package covers the rest.

[日本語版 README](README.ja.md)

## Why this exists

X-13ARIMA-SEATS is the standard tool for seasonal adjustment, but its X-11
core is hard-wired for monthly (period 12) or quarterly (period 4) data. Many
real series — daily data with a weekly cycle, weekly data with an annual
cycle, etc. — don't fit that mold.

This package takes the X-11 procedure apart: the parts that are genuinely
cycle-length-independent (outlier and holiday adjustment, level-shift
adjustment, forecast extension) are left to X-13ARIMA-SEATS's RegARIMA
pre-adjustment, which already does this well. Only the X-11 core — moving
averages, seasonal filter selection, extreme-value replacement — is
reimplemented here, generalized to any cycle length.

## Features

- Multiplicative, additive and log-additive decomposition modes
- Log-additive mode includes the Thomson & Ozaki (2002) trend bias
  correction
- X-11 extreme SI-ratio replacement
- Automatic seasonal filter selection (3x3/3x5/3x9) via the moving seasonality
  ratio (MSR)
- Automatic Henderson moving average term selection
- Zero dependencies (standard library only)

## Install

```bash
pip install seasadj
```

## Quick start

```python
import math
from seasadj import decompose

# a toy series with a 7-day seasonal cycle
data = [100 + 0.05 * i + 20 * math.sin(2 * math.pi * i / 7) for i in range(400)]

result = decompose(data, period=7)

print(result.trend[:5])      # trend-cycle component
print(result.seasonal[:5])   # seasonal component
print(result.adjusted[:5])   # seasonally adjusted series
print(result.irregular[:5])  # irregular component
```

`decompose()` returns a `Decomposition` with `trend`, `seasonal`, `adjusted`
and `irregular` series (all plain lists), plus the original `observed`
series and diagnostics. For multiplicative/log models,
`prior_adjusted ≈ trend * seasonal * irregular`; for the additive model,
`prior_adjusted ≈ trend + seasonal + irregular`.

## Preparing inputs with X-13ARIMA-SEATS

`decompose()` expects data that has already been adjusted for holidays,
outliers and level shifts (or you can pass those effects directly — see the
API reference below) and, optionally, a forecast extension. The usual way to
get these is a RegARIMA run in X-13ARIMA-SEATS:

- **Multiplicative or log model**: run X-13 without a `transform` (or with
  `transform function=none` for the regressors), and use its multiplicative
  effect estimates (values near 1.0) as `holiday_effect` / `ao_effect` /
  `ls_effect`.
- **Additive model**: run X-13 with `transform function=none`, and use its
  additive effect estimates (values near 0.0, the "amount to subtract") as
  the same arguments.

Mixing the two — e.g. passing multiplicative-style effect factors while
`model="additive"` — will silently produce a wrong adjustment, since the
additive model treats the effect arguments as amounts to *subtract*, not
factors to divide by.

## File mode (Fortran-compatible CLI)

For compatibility with the original Fortran program, `seasadj` also has a
file-based mode that reads a working directory laid out as
`in_data/` + `para/` and writes `out_data/`:

```bash
seasadj <workdir>
# or
python -m seasadj <workdir>
```

See [docs/porting-notes.ja.md](docs/porting-notes.ja.md) for the file
formats and module-to-Fortran-source mapping (developer-facing, Japanese).

## API reference

### `decompose(data, period, **kwargs) -> Decomposition`

| Argument | Default | Description |
|---|---|---|
| `data` | required | Observed values (list/tuple/`np.ndarray`/`pd.Series` of numbers) |
| `period` | required | Seasonal cycle length (2 or larger), e.g. 7 for a day-of-week cycle |
| `first_position` | `1` | Cycle position of `data[0]` (1..period) |
| `model` | `"multiplicative"` | `"multiplicative"`, `"additive"` or `"log"` |
| `forecast` | `None` | Forecast-extension values (e.g. from X-13ARIMA-SEATS) |
| `holiday_effect` | `None` | Holiday prior-adjustment factor per period |
| `holiday_regressor` | `None` | Holiday regression variable; required if `holiday_effect` and `forecast` are both given |
| `holiday_coef` | `0.0` | Holiday regression coefficient |
| `ao_effect` | `None` | Additive-outlier prior-adjustment factor |
| `ls_effect` | `None` | Level-shift prior-adjustment factor |
| `seasonal_ma` | `3` | Initial seasonal moving average term: 3, 5 or 9 (3x3/3x5/3x9) |
| `replace_extreme` | `True` | X-11 extreme SI-ratio replacement |
| `sigma` | `(1.5, 2.5)` | `(lower, upper)` sigma limits for extreme SI-ratio replacement |
| `ft_o` | `1` | Running position of the first observation (rarely changed) |
| `verbose` | `False` | If `True`, print progress lines; otherwise they land in `diagnostics["log"]` |

Raises `SeasadjError` on invalid input. Validation reports the first
failure it finds, checking data length before checking that values are
positive (relevant for the multiplicative and log models).

### `Decomposition`

All series are plain 0-based lists. `n_total = n_observed + n_forecast`;
index `n_observed` onward is the forecast-extension period.

| Field | Length | Content |
|---|---|---|
| `observed` | n_observed | The input data |
| `prior_adjusted` | n_total | Data after holiday/outlier/level-shift adjustment (log model: back-transformed to the original scale) |
| `trend` | n_total | Trend-cycle component |
| `seasonal` | n_total | Seasonal component |
| `irregular` | n_total | Irregular component |
| `adjusted` | n_total | Seasonally adjusted series |
| `holiday_effect` / `ao_effect` / `ls_effect` | n_total | The effect series actually applied |
| `n_observed` / `n_forecast` | int | Observed / forecast-extension length |
| `period` | int | Echoes the `period` argument |
| `model` | str | Echoes the `model` argument |
| `diagnostics` | dict | `h_terms`, `sum_ratios`, `swm_term`, `msr_ratio`, `msr_count`, `si_replaced`, `bias_sig`, `log` |
| `internals` | dict | Intermediate series (`TC1`, `SI1`, `w1`, `SI1r`, `S1p`, `S1`, `A1`, `TC2`, `SI2`, `w2`, `SI2r`, `S2p`) and `ft_SI1`; series-edge padding (0.0 / -999.0 / weight 1.0) follows the same convention as the file-mode output |

## Algorithm

The X-11 procedure estimates trend-cycle, seasonal and irregular components
in three passes (initial trend → intermediate estimate → final estimate),
each refining the previous one's seasonal factor and Henderson-filtered
trend. This package generalizes every step — the seasonal moving average,
the Henderson filter term selection, the moving seasonality ratio, the
extreme-value replacement — from the fixed periods of the original X-11 (12
or 4) to an arbitrary period.

References: Dagum, E. B. (1988), *The X-11-ARIMA/88 Seasonal Adjustment
Method*; the [JDemetra+ X-11 theory
documentation](https://jdemetradocumentation.github.io/JDemetra-documentation/pages/theory/SA_X11.html);
Thomson, P. and Ozaki, T. (2002), trend bias correction for log-additive
decomposition.

## Development / testing

This package is a port of an original Fortran90 implementation (Ver16_00),
verified against 7 frozen golden-test cases (not distributed with this
package — see [docs/porting-notes.ja.md](docs/porting-notes.ja.md)) to match
bit-for-bit. The tests distributed with this package
(`tests/test_api.py`) instead check the decomposition identity and the
equivalence of the API and file-mode code paths on artificial data.

```bash
pip install -e . pytest
python -m pytest tests/ -v
```

## Citation

If you use this package in research, please cite:

> Arita, Tetsuma (2022). "Assessment of the spread of COVID-19 in seven
> countries using a seasonal adjustment method." *Statistical Journal of
> the IAOS*. https://doi.org/10.3233/SJI-220932

A paper describing the Ver14-16 extensions implemented in this package
(extreme SI-ratio replacement, additive/log-additive modes, Thomson &
Ozaki trend bias correction) is in preparation; this citation will be
updated once it is available.

## License / Commercial use

`seasadj` is licensed under the GNU Affero General Public License v3.0 or
later (AGPL-3.0-or-later) — see [LICENSE](LICENSE).

If the AGPL's terms don't work for your use case (e.g. embedding in
proprietary software), a commercial license is available, as is
collaboration on research or customization. Please open an issue on
GitHub to get in touch.
