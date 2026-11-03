# seasadj

X-11 style seasonal adjustment, generalized to an arbitrary cycle length.
`period=7` for the day-of-week cycle of daily data, `period=24` for the
daily cycle of hourly data, or any other cycle length your data has —
the X-11 core of X-13ARIMA-SEATS accepts only periods 12 and 4 (monthly and
quarterly data), and this package covers the rest.

[日本語版 README](README.ja.md)

## Why this exists

X-13ARIMA-SEATS is the standard tool for seasonal adjustment, but its X-11
core is hard-wired for monthly (period 12) or quarterly (period 4) data.
More and more real series — daily data with a weekly cycle, hourly data
with a daily cycle, etc. — don't fit that mold.

This package takes the X-11 procedure apart: outlier, holiday and
level-shift adjustment and forecast extension are left to a RegARIMA
pre-adjustment such as X-13ARIMA-SEATS, which has a proven track record.
The cycle-length-bound X-11 core — moving averages, automatic seasonal
filter selection, extreme-value replacement — is reimplemented here with
the cycle length as a parameter. Some of X-11's decision rules keep their
monthly values; see [Algorithm](#algorithm).

## Features

- Multiplicative, additive and log-additive decomposition modes
- Log-additive mode includes the Thomson & Ozaki (2002) trend bias
  correction
- Outlier handling via SI ratios (X-11 extreme value replacement)
- Automatic seasonal filter selection (3x3/3x5/3x9) via the moving seasonality
  ratio (MSR)
- Automatic Henderson moving average term selection (9, 13 or 23 terms)
- Zero dependencies (standard library only)

## Install

```bash
pip install seasadj
```

## Quick start

Put your series in a CSV file (one value column, optionally with a header and
a date column) and run:

```bash
pip install seasadj
seasadj data.csv --period 7
```

This writes `data_seasadj.csv` next to the input, with the columns
`date,observed,prior_adjusted,trend,seasonal,irregular,adjusted` (the `date`
column is copied from your file, if it has one; it is only a label and is never
interpreted), and prints a short summary of the run. `--period` is the length
of the seasonal cycle (7 for the day-of-week cycle of daily data). Options:

| Option | Default | Description |
|---|---|---|
| `--period N` | required | Seasonal cycle length |
| `--column NAME\|INDEX` | last column | Column holding the observed values (header name or 0-based index) |
| `--date-column NAME\|INDEX` | first column | Label column, copied to the output heading only |
| `--no-header` | | The first row is data, not a header |
| `--first-position N` | `1` | Cycle position of the first value |
| `--model {multiplicative,additive,log}` | `multiplicative` | Decomposition model |
| `--seasonal-ma {3,5,9}` | `3` | Initial seasonal moving average term |
| `--sigma LOW UPPER` | `1.5 2.5` | Sigma limits for extreme-value replacement |
| `--no-replace-extreme` | | Turn off extreme-value replacement |
| `-o, --output PATH` | `<input>_seasadj.csv` | Output file (`-` for standard output) |
| `--quiet` | | No summary on standard error |

Forecast extension and holiday / outlier / level-shift adjustment are not
available in CSV mode; use the Python API or the file mode below for those.

## Three ways to use it

| Interface | Use it when |
|---|---|
| **CSV mode** — `seasadj data.csv --period 7` | You have a CSV file and want the result as a CSV file. The easiest start |
| **Python API** — `decompose(data, period)` | You work in Python, or need forecast extension, holiday/outlier/level-shift adjustment or the diagnostics |
| **File mode** — `seasadj <workdir>` | You are migrating from the Fortran version, or need its intermediate output files |

New to `seasadj`? The [tutorial](docs/tutorial.md) walks through one series
from start to finish. The complete reference for all three interfaces is
[docs/api.md](docs/api.md).

## Python API

```python
import math
from seasadj import decompose

# a synthetic series with a 7-day seasonal cycle
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

The multiplicative and log models require strictly positive `data` (and
`forecast`, if given); `decompose()` raises `SeasadjError` otherwise. The
additive model accepts zero and negative values.

## Examples

[examples/](examples/) reproduces the day-of-week seasonal adjustment
analysis of Arita (2022) — see the Citation section below — on real daily
COVID-19 case counts, using only public data. For a step-by-step
explanation on a synthetic series instead, see the
[tutorial](docs/tutorial.md).

## Preparing inputs with X-13ARIMA-SEATS

`decompose()` expects data that has already been adjusted for holidays,
outliers and level shifts (or you can pass those effects directly — see the
API reference below) and, optionally, a forecast extension. The usual way to
get these is a RegARIMA run in X-13ARIMA-SEATS. X-13's `transform` spec
applies only to the RegARIMA estimation; the tables it saves are on the
original scale of the series, and its choice decides the form of the saved
regression effects:

- **Multiplicative or log model**: run X-13 with `transform{function=log}`.
  The saved regression effects are then ratios (values near 1.0); pass them as
  `holiday_effect` / `ao_effect` / `ls_effect`. Whether you then use
  `model="multiplicative"` or `model="log"` is your choice: both take the
  effects as factors.
- **Additive model**: run X-13 with no transformation (the default). The
  saved regression effects are then on the scale of the series (values near
  0.0, the "amount to subtract"); pass them as the same arguments with
  `model="additive"`.

In both cases, X-13's saved forecasts (`forecast{save=(forecasts)}`) are on
the original scale and can be passed as `forecast`. The
[tutorial](docs/tutorial.md#7-prior-adjustment-with-x-13arima-seats) shows the
whole procedure.

Mixing the two — e.g. passing multiplicative-style effect factors while
`model="additive"` — will silently produce a wrong adjustment, since the
additive model treats the effect arguments as amounts to *subtract*, not
factors to divide by.

## File mode (Fortran-compatible CLI)

For compatibility with the original Fortran program, `seasadj` also has a
file-based mode that reads a working directory laid out as `in_data/`
(`para/` is optional: the weight files are bundled with the package) and
writes `out_data/`:

```bash
seasadj <workdir>
# or
python -m seasadj <workdir>
```

See [docs/file-formats.md](docs/file-formats.md) for the file formats. (The
module-to-Fortran-source mapping is in
[docs/porting-notes.ja.md](docs/porting-notes.ja.md); developer-facing,
Japanese.) For new work, the CSV mode or the Python API is recommended.

## API reference

Full reference: [docs/api.md](docs/api.md)

### `decompose(data, period, **kwargs) -> Decomposition`

| Argument | Default | Description |
|---|---|---|
| `data` | required | Observed values (list/tuple/`np.ndarray`/`pd.Series` of numbers) |
| `period` | required | Seasonal cycle length (2 or larger), e.g. 7 for a day-of-week cycle |
| `first_position` | `1` | Declares the cycle position of `data[0]` (1..period). The X-11 filters work on positions relative to the start of the series, so this does not normally change the decomposition; it affects the position column of the file-mode summary and the complete-cycle trim point used when the seasonal filter length is chosen, and through the latter can occasionally change the result |
| `model` | `"multiplicative"` | `"multiplicative"`, `"additive"` or `"log"` |
| `forecast` | `None` | Forecast-extension values (e.g. from X-13ARIMA-SEATS) |
| `holiday_effect` | `None` | Holiday prior-adjustment factor per period |
| `holiday_regressor` | `None` | Holiday regression variable; required if `holiday_effect` and `forecast` are both given |
| `holiday_coef` | `0.0` | Holiday regression coefficient |
| `ao_effect` | `None` | Additive-outlier prior-adjustment factor |
| `ls_effect` | `None` | Level-shift prior-adjustment factor |
| `seasonal_ma` | `3` | Initial seasonal moving average term: 3, 5 or 9 (3x3/3x5/3x9) |
| `replace_extreme` | `True` | Outlier replacement (X-11 extreme value replacement) |
| `sigma` | `(1.5, 2.5)` | `(lower, upper)` sigma limits for outlier replacement |
| `ft_o` | `1` | Running position of the first observation (rarely changed) |
| `verbose` | `False` | If `True`, print progress lines; otherwise they land in `diagnostics["log"]` |

Data length: at least 20 observations and a minimum that depends on
`period` (56 for `period=7` with the defaults; see
[docs/api.md](docs/api.md#13-data-length)), and **at most 7,300 values in
total, counting the forecast extension**.

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
trend.

This package takes the period as a parameter in the initial centred moving
average, the SI ratios and seasonal moving averages (applied to values at the
same cycle position), the moving seasonality ratio and the extreme-value
replacement. Some decision rules, however, keep the values of monthly X-11
for every period: the Henderson trend filter is chosen from 9, 13 or 23 terms
with the thresholds 1.0 and 3.5, the seasonal moving average is chosen with
the MSR thresholds 2.5, 3.5, 5.5 and 6.5, and the filter weights are read
from fixed tables. This is a design choice of v1.x; period-dependent rules
may be considered in a future version, outside v1.x because they would
change numerical results. Details:
[docs/api.md](docs/api.md#6-what-is-generalized-to-any-period-and-what-is-not).

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
> the IAOS*, 38(2), 363-383. https://doi.org/10.3233/SJI-220932

## License / Commercial use

`seasadj` is licensed under the GNU Affero General Public License v3.0 or
later (AGPL-3.0-or-later) — see [LICENSE](LICENSE).

If the AGPL's terms don't work for your use case (e.g. embedding in
proprietary software), or if you are interested in research collaboration
or customization, inquiries are welcome — please open an issue on GitHub
to get in touch.
