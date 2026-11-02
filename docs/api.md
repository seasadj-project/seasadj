# API reference

This is the complete reference for `seasadj` 1.x. The README has a short
summary; where the two differ, this page is the authoritative one.

- [1. `decompose()`](#1-decompose)
- [2. `Decomposition`](#2-decomposition)
- [3. `diagnostics`](#3-diagnostics)
- [4. `run()`](#4-run)
- [5. Command line](#5-command-line)
- [6. What is generalized to any period, and what is not](#6-what-is-generalized-to-any-period-and-what-is-not)
- [7. Compatibility](#7-compatibility)

For a worked example from a raw series to an adjusted one, see the
[tutorial](tutorial.md). The file formats of the working-directory mode are
in [file-formats.md](file-formats.md).

## 1. `decompose()`

```python
from seasadj import decompose

result = decompose(data, period, *, first_position=1, model="multiplicative",
                   forecast=None, holiday_effect=None, holiday_regressor=None,
                   holiday_coef=0.0, ao_effect=None, ls_effect=None,
                   seasonal_ma=3, replace_extreme=True, sigma=(1.5, 2.5),
                   ft_o=1, verbose=False)
```

Decomposes `data` into trend-cycle, seasonal and irregular components and
returns a [`Decomposition`](#2-decomposition). Everything after `period` is
keyword-only.

### 1.1 Arguments

| Argument | Type | Default | Allowed values | Meaning |
|---|---|---|---|---|
| `data` | sequence of numbers | required | see [1.3](#13-data-length) | Observed values. Any sequence whose items convert with `float()` (list, tuple, `np.ndarray`, `pd.Series`) |
| `period` | `int` | required | 2 or larger | Length of the seasonal cycle: 7 for the day-of-week cycle of daily data, 24 for the daily cycle of hourly data. It is never inferred from the data |
| `first_position` | `int` | `1` | `1`..`period` | Declares the cycle position of `data[0]`. The filters work on positions relative to the start of the series, so this does not normally change the decomposition. It sets where the complete cycles end when the seasonal filter is chosen (see [`swm_term`](#swm_term)), and through that it can occasionally change the result. It also sets the position column of the file-mode summary output |
| `model` | `str` | `"multiplicative"` | `"multiplicative"`, `"additive"`, `"log"` | Decomposition model. Numeric codes 0/1/2 are not accepted |
| `forecast` | sequence of numbers or `None` | `None` | at least 1 value | Forecast extension appended after `data` (for example, forecasts from a RegARIMA model). The decomposition runs on `data` and the extension together, so the filters near the end of the observed period use the extension values; the components are returned for the extension as well |
| `holiday_effect` | sequence or `None` | `None` | see [1.2](#12-effect-arguments) | Holiday prior-adjustment effect for each observation |
| `holiday_regressor` | sequence or `None` | `None` | see [1.2](#12-effect-arguments) | Holiday regression variable. Used only to extend `holiday_effect` over the forecast extension |
| `holiday_coef` | `float` | `0.0` | any | Holiday regression coefficient. Used only together with `holiday_regressor` |
| `ao_effect` | sequence or `None` | `None` | see [1.2](#12-effect-arguments) | Additive-outlier prior-adjustment effect |
| `ls_effect` | sequence or `None` | `None` | see [1.2](#12-effect-arguments) | Level-shift prior-adjustment effect |
| `seasonal_ma` | `int` | `3` | `3`, `5`, `9` | Seasonal moving average of the first pass (3x3, 3x5 or 3x9). The final seasonal moving average is chosen automatically ([`swm_term`](#swm_term)) |
| `replace_extreme` | `bool` | `True` | | X-11 extreme SI-ratio replacement, in both the first and the second pass |
| `sigma` | pair of numbers | `(1.5, 2.5)` | `0 < lower < upper` | `(lower, upper)` sigma limits of the extreme-value replacement. SI ratios within `lower` standard deviations keep full weight, those beyond `upper` get weight 0, and the weight falls linearly in between. Checked only when `replace_extreme=True` |
| `ft_o` | `int` | `1` | 1 or larger | Running position of the first observation, the same as parameter I of the file mode. Rarely changed from 1 |
| `verbose` | `bool` | `False` | | `True` prints the progress lines of the file mode; `False` captures them in `diagnostics["log"]` |

### 1.2 Effect arguments

The effect arguments describe a prior adjustment that has already been
estimated elsewhere. Before the decomposition, the data (and the forecast
extension) are adjusted point by point:

| Model | Adjustment |
|---|---|
| `"multiplicative"` | `data / (holiday × ao × ls)` |
| `"log"` | `log(data / (holiday × ao × ls))`, then the additive pipeline on the logs |
| `"additive"` | `data − (holiday + ao + ls)` |

So for the multiplicative and log models the effects are **factors** (near
1.0), and for the additive model they are **amounts to subtract** (near 0.0).
Passing factors with `model="additive"` gives a wrong adjustment without any
error. An effect argument left at `None` is neutral (1.0, or 0.0 for the
additive model) over the whole series.

Lengths (`n_observed = len(data)`, `n_forecast = len(forecast)` or 0,
`n_total = n_observed + n_forecast`):

| Argument | Needed length | What is used |
|---|---|---|
| `holiday_effect` | at least `n_observed` | The first `n_observed` values. Over the forecast extension the holiday effect is computed from `holiday_regressor` (below); without a forecast extension, values beyond `n_observed` are ignored |
| `holiday_regressor` | at least `n_total` | **Required when `holiday_effect` and `forecast` are both given**, ignored otherwise. Only the values at index `n_observed` onward are used: the holiday effect there is `exp(holiday_coef × regressor)` for the multiplicative and log models, and `holiday_coef × regressor` for the additive model |
| `ao_effect`, `ls_effect` | at least `n_observed` | The first `n_observed` values. Over the forecast extension they are set to neutral (1.0, or 0.0 for the additive model) |

The effect series actually applied, including the forecast extension, are
returned in `Decomposition.holiday_effect` / `ao_effect` / `ls_effect`.

### 1.3 Data length

**Minimum.** All three of the following must hold. Note that the first
counts the observed values only, while the other two count the observed
values plus the forecast extension.

1. `n_observed >= 20`
2. `n_total >= period × (seasonal_ma + 3)`
3. if `replace_extreme=True`: `n_total >= period × 8` (the second-pass
   replacement always uses a 3x5 moving average: `period × (5 + 3)`)

The minimum length is therefore the largest of these. For example:

| `period` | `seasonal_ma=3` (default) | `seasonal_ma=3`, `replace_extreme=False` | `seasonal_ma=5` | `seasonal_ma=9` |
|---|---|---|---|---|
| 7 | 56 | 42 | 56 | 84 |
| 12 | 96 | 72 | 96 | 144 |
| 24 | 192 | 144 | 192 | 288 |

(With `seasonal_ma=5` or `9`, `replace_extreme` does not change the minimum.)

**Maximum.** `n_total` — the observed values plus the forecast extension —
can be at most **7,300**. For hourly data with `period=24` this is about 10
months; for daily data, about 20 years. A series of exactly 7,300
observations works from v1.1.0 on (earlier versions crashed on it when there
was no forecast extension). Longer input raises `SeasadjError`, including
the case where `data` and `forecast` are each within the limit but their sum
exceeds it (versions before 1.1.1 raised `IndexError` there).

### 1.4 Errors

`decompose()` raises `seasadj.SeasadjError` for invalid input. Validation
stops at the **first** failure, in this order:

1. the arguments themselves (`period`, `first_position`, `model`,
   `seasonal_ma`, `ft_o`, `sigma`, and `holiday_regressor` when it is
   required);
2. the maximum length: `data` or `forecast` longer than 7,300, then
   `n_total` over 7,300, then each effect argument longer than 7,300 or
   (`holiday_regressor`, when it is used) shorter than `n_total`;
3. data length: `data` empty, `forecast` given but empty, then the three
   minimum-length rules of [1.3](#13-data-length);
4. for the multiplicative and log models: every value of `data` and
   `forecast` must be positive;
5. each effect argument shorter than `n_observed`;
6. for the multiplicative and log models: every effect value, including the
   computed forecast-extension values, must be positive (they are divisors).

So data length is checked before the values are checked for being positive:
data that is both too short and non-positive reports the length error.

An argument of the wrong type can raise a plain Python error instead of
`SeasadjError` (for example, `sigma=1.5` instead of a pair raises
`TypeError`).

### 1.5 Inputs that are not validated

These inputs are not checked. Do not pass them:

- **Missing values (NaN) or infinities.** They are not rejected; they spread
  into the results, which then contain NaN. Fill gaps (for example by
  interpolation) before calling `decompose()`. The CSV mode of the command
  line rejects non-numeric and non-finite cells with the row number.
- **A series with no variation at all** (every value the same). The trend
  filter selection divides by the variation of the trend, and the call
  fails with `ZeroDivisionError`.

## 2. `Decomposition`

All series are plain Python lists of floats, indexed from 0. Index
`n_observed` onward is the forecast extension.

| Field | Length | Content |
|---|---|---|
| `observed` | `n_observed` | The input `data` |
| `prior_adjusted` | `n_total` | Data (and forecast extension) after the prior adjustment of [1.2](#12-effect-arguments). For the log model, back-transformed to the original scale |
| `trend` | `n_total` | Trend-cycle component. For the log model, includes the trend bias correction of Thomson & Ozaki (2002) (see [`bias_sig`](#bias_sig)) |
| `seasonal` | `n_total` | Seasonal component (factors near 1 for the multiplicative and log models, deviations near 0 for the additive model) |
| `irregular` | `n_total` | Irregular component. For the log model, `adjusted / trend` |
| `adjusted` | `n_total` | Seasonally adjusted series: `prior_adjusted / seasonal` (`− seasonal` for the additive model) |
| `holiday_effect`, `ao_effect`, `ls_effect` | `n_total` | The effect series actually applied |
| `n_observed`, `n_forecast` | `int` | Lengths of `data` and of the forecast extension |
| `period` | `int` | The `period` argument |
| `model` | `str` | The `model` argument |
| `diagnostics` | `dict` | The automatic choices made during the run — see [3](#3-diagnostics) |
| `internals` | `dict` | Intermediate series of the three passes (`TC1`, `SI1`, `w1`, `SI1r`, `S1p`, `S1`, `A1`, `TC2`, `SI2`, `w2`, `SI2r`, `S2p`) and `ft_SI1`. Entries at the series edges that have no value are padded with 0.0 (multiplicative and log), -999.0 (additive) or 1.0 (weights), as in the file-mode output. **Not covered by the compatibility guarantee**: keys and contents may change in any release |

Within floating-point rounding:

- multiplicative and log models: `prior_adjusted ≈ trend × seasonal × irregular`
- additive model: `prior_adjusted ≈ trend + seasonal + irregular`

## 3. `diagnostics`

`diagnostics` records which filters were chosen, and why. The procedure has
three passes: the first pass estimates an initial trend with a centred
`period`-term moving average and initial seasonal factors with the
`seasonal_ma` filter; the second pass chooses a Henderson trend filter and
the final seasonal filter; the third pass chooses the Henderson filter for the
final trend.

Example (the series of the README):

```python
import math
from seasadj import decompose

data = [100 + 0.05 * i + 20 * math.sin(2 * math.pi * i / 7) for i in range(400)]
d = decompose(data, period=7).diagnostics
for key in ("h_terms", "sum_ratios", "swm_term", "msr_ratio", "msr_count",
            "si_replaced", "bias_sig"):
    print(key, d[key])
```

```
h_terms [9, 9]
sum_ratios [0.13140492202804913, 0.17282288433561543]
swm_term 3
msr_ratio 0.040751508597009566
msr_count 0
si_replaced [(12, 394), (16, 400)]
bias_sig 0.0
```

### `h_terms`

`[initial, final]`: the number of terms of the Henderson moving average used
for the trend in the second pass (initial) and in the third pass (final).
**The only possible values are 9, 13 and 23.**

Rule (applied separately in each pass, to that pass's seasonally adjusted
series):

1. Smooth the series with a 13-term Henderson moving average (a preliminary
   trend), and divide the series by it (subtract, for the additive and log
   models) to get a preliminary irregular.
2. Over the observed period, leaving out the first and last 6 points (the
   forecast extension is not used), add up the absolute changes from one
   point to the next — percent changes for the multiplicative model,
   differences for the additive and log models — of the preliminary
   irregular and of the preliminary trend.
3. The ratio irregular / trend of these two sums (reported in
   [`sum_ratios`](#sum_ratios)) selects the filter:

| Ratio | Henderson terms |
|---|---|
| below 1.0 | 9 |
| 1.0 to 3.5 (inclusive) | 13 |
| above 3.5 | 23 |

The thresholds 1.0 and 3.5 are the same for every `period` (see
[6](#6-what-is-generalized-to-any-period-and-what-is-not)).

### `sum_ratios`

`[initial, final]`: the ratios of step 3 above, for the second and the third
pass. A large ratio means a noisy series relative to its trend, and so a
longer (smoother) Henderson filter.

### `swm_term`

The seasonal moving average chosen for the final seasonal factors: `3`
(3x3), `5` (3x5) or `9` (3x9). It is chosen in the second pass by the moving
seasonality ratio (MSR):

1. Smooth the SI ratios (after extreme-value replacement) with a 3x3
   seasonal moving average to get preliminary seasonal factors, and divide
   the SI ratios by them (subtract, for the additive and log models) to get
   a preliminary irregular.
2. For each cycle position, take the mean absolute change from one cycle to
   the next of the preliminary irregular and of the preliminary seasonal
   factors (percent changes for the multiplicative model, differences for
   the additive and log models). Weight each position by its number of
   changes plus one, and sum over the positions. The MSR is the irregular
   sum divided by the seasonal sum.
3. Only the observed period is used, up to the end of its last complete
   cycle (cycle boundaries follow `first_position`).
4. The MSR selects the filter:

| MSR | Seasonal moving average |
|---|---|
| below 2.5 | 3x3 |
| 2.5 to 3.5 (inclusive) | undecided: retry |
| above 3.5 and below 5.5 | 3x5 |
| 5.5 to 6.5 (inclusive) | undecided: retry |
| above 6.5 | 3x9 |

When the MSR falls in an undecided range, the MSR is computed again with one
more cycle left out at the end of the series. There are at most 6 attempts
(the first plus 5 retries). If none of them decides, 3x5 is used. An attempt
also counts as undecided if the preliminary seasonal factors show no change
at all.

The thresholds 2.5, 3.5, 5.5 and 6.5 are the same for every `period`.

### `msr_ratio`

The MSR of the last attempt: the one that decided `swm_term`, or the sixth
if none did. It is `inf` if the preliminary seasonal factors showed no change
in that attempt.

### `msr_count`

The number of undecided attempts. `0` means the first attempt decided;
`6` means no attempt decided and 3x5 was used by default.

### `si_replaced`

The extreme SI-ratio replacement, as a list of two `(replaced, checked)`
pairs: one for the first pass and one for the second. `checked` is the
number of SI ratios examined, and `replaced` the number that got a weight
below 1 and were replaced by a weighted average of themselves and the
nearest full-weight SI ratios at the same cycle position. The first pass
uses the `seasonal_ma` filter for its preliminary seasonal factors and the
second pass a 3x5 filter. In the first pass, `checked` is smaller than
`n_total` because the centred moving average of the initial trend leaves no
SI ratio at the series edges.

With `replace_extreme=False`, `si_replaced` is an empty list `[]`.

### `bias_sig`

The trend bias correction factor of the log model,
`exp(sum(I²) / (2n))`, where `I` is the final irregular in the log domain
over the `n` observed values (Thomson & Ozaki, 2002). The back-transformed
trend is multiplied by this factor and by the seasonal factors smoothed with
a `(2 × period − 1)`-term Henderson filter. For the multiplicative and
additive models, `bias_sig` is `0.0`.

### `log`

When `verbose=False`, the progress lines that the file mode prints (one line
per automatic choice). **The wording is not covered by the compatibility
guarantee**; read the other keys instead of parsing this text.

## 4. `run()`

```python
from seasadj import run

run(workdir=".")
```

Runs the working-directory (file) mode, the same as the original Fortran
program: reads the parameters and series from `workdir/in_data/`, writes 20
result files to `workdir/out_data/` and prints the progress lines. The weight
files are taken from `workdir/para/` if present, otherwise from the copy
bundled with the package. Raises `SeasadjError` (after printing
`ERROR: ...`) for invalid input. It returns a dict of internal values used by
the test suite; its contents are not covered by the compatibility guarantee.
See [file-formats.md](file-formats.md) for the files.

## 5. Command line

```
seasadj [PATH] [options]
python -m seasadj [PATH] [options]
```

If `PATH` is a file, it is read as CSV (CSV mode). If it is a directory —
or omitted, meaning the current directory — it is a working directory for
the file mode.

### 5.1 CSV mode

```
seasadj data.csv --period 7
```

Reads one column of values, runs `decompose()` and writes a CSV file with the
columns `date,observed,prior_adjusted,trend,seasonal,irregular,adjusted`
(`date` only if the input has a label column), one row per input row. Values
are written with full precision (Python `repr`).

| Option | Default | Meaning |
|---|---|---|
| `--period N` | required | Seasonal cycle length |
| `--column NAME\|INDEX` | last column | Column holding the values: header name or 0-based index |
| `--date-column NAME\|INDEX` | first column, unless it is the value column | Label column. Copied to the output as-is; never interpreted (in particular, `first_position` is not derived from it) |
| `--no-header` | | The first row is data. Without this option, the first row is taken as a header if its value cell is not a number |
| `--first-position N` | `1` | `first_position` |
| `--model {multiplicative,additive,log}` | `multiplicative` | `model` |
| `--seasonal-ma {3,5,9}` | `3` | `seasonal_ma` |
| `--sigma LOW UPPER` | `1.5 2.5` | `sigma` |
| `--no-replace-extreme` | | `replace_extreme=False` |
| `-o, --output PATH` | `<input stem>_seasadj.csv` next to the input | Output file; `-` for standard output. The input file is never overwritten |
| `--quiet` | | No summary on standard error |
| `--version` | | Print the version and exit |

A short summary (input, period, model, the chosen seasonal moving average
and Henderson terms, output) is printed to standard error. The input is read
as UTF-8 (a byte-order mark is accepted). Forecast extension and the effect
arguments are not available in CSV mode; use `decompose()` or the file mode.

### 5.2 File mode

```
seasadj path/to/workdir
```

Same as [`run()`](#4-run). The CSV-mode options are rejected with a directory
`PATH`.

### 5.3 Exit status

| Status | Meaning |
|---|---|
| 0 | Success |
| 1 | Invalid input or a file that cannot be read or written. CSV mode prints `seasadj: error: ...` to standard error; file mode prints `ERROR: ...` |
| 2 | Invalid command-line options (reported by `argparse`) |

## 6. What is generalized to any period, and what is not

`seasadj` follows the X-11 procedure. Some of its steps take the cycle
length as a parameter; others use the decision rules of monthly X-11 as they
are, for every period. This is a design choice of v1.x.

**Steps that take `period` as a parameter:**

- the centred moving average of the initial trend (`period` terms for an odd
  period; a centred 2 × `period` average for an even period);
- the SI ratios, the seasonal factors and the seasonal moving averages
  (3x3, 3x5, 3x9 applied to the values at the same cycle position);
- the moving seasonality ratio (computed per cycle position, over complete
  cycles only);
- the extreme SI-ratio replacement (judged per cycle, comparing values at the
  same cycle position);
- the smoothing of the seasonal factors in the log-model trend bias
  correction (a `(2 × period − 1)`-term Henderson filter).

**Rules that do not depend on `period`:**

- **Henderson trend filter**: chosen from 9, 13 or 23 terms with the
  thresholds 1.0 and 3.5 ([`h_terms`](#h_terms)). These are the values of
  monthly X-11.
- **Seasonal moving average selection**: MSR thresholds 2.5, 3.5, 5.5 and
  6.5 ([`swm_term`](#swm_term)). These are the values of monthly X-11.
- **Filter weights**: the Henderson and seasonal moving-average weights are
  read from fixed tables bundled with the package (`src/seasadj/para/*.dat`).
  Tables for 5- and 7-term Henderson filters are bundled too, but the
  selection rule above never chooses them.
- **Sigma limits** of the extreme-value replacement: the default
  `(1.5, 2.5)` is the monthly X-11 default (it can be changed with `sigma`).

Selection rules that depend on the period may be considered in a future
version; since they would change numerical results, they are outside v1.x.

## 7. Compatibility

Within the 1.x series:

- **Kept**: the arguments of `decompose()` and the fields of
  `Decomposition`, and the numerical results — the same input on the same
  platform gives bit-identical results in every 1.x release.
- **Not kept**: the contents of `Decomposition.internals` and the wording of
  `diagnostics["log"]`.
