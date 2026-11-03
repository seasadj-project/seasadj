# Tutorial: from a raw series to an adjusted series

This tutorial is for readers who know seasonal adjustment but have not used
X-11 on anything other than monthly or quarterly data. It walks through one
daily series with a day-of-week cycle, from building the series to reading
which filters were chosen.

Everything below runs with the standard library and `seasadj` only
(`pip install seasadj`). The outputs shown are those of the code as written.
The [examples/](../examples/) directory is different: it reproduces the
analysis of a published paper on real data, while this tutorial explains the
steps.

## 1. Prepare a series

We build 52 weeks of daily data: a slowly rising trend with a half-year wave,
a fixed day-of-week pattern, 2% multiplicative noise, and three outliers.

```python
import math
import random

rng = random.Random(2026)
weekly = [1.10, 1.05, 1.00, 0.98, 1.02, 0.90, 0.95]  # averages to 1.0

data = []
for t in range(364):  # 52 weeks of daily data
    trend = 200 + 0.3 * t + 15 * math.sin(2 * math.pi * t / 182)
    irregular = 1 + rng.gauss(0, 0.02)
    data.append(trend * weekly[t % 7] * irregular)

# three outliers
for t, factor in ((50, 1.6), (120, 0.5), (300, 1.4)):
    data[t] *= factor

print(len(data), round(data[0], 2), round(data[50], 2))
```

```
364 223.81 385.66
```

With your own data, `data` is any sequence of numbers: a list, a NumPy
array or a pandas Series.

## 2. Choose the period

The period is the length of the seasonal cycle, and **you state it
explicitly**: `seasadj` does not detect it from the data. Typical values:

| Data | Cycle | `period` |
|---|---|---|
| Daily | day of the week | 7 |
| Hourly | hour of the day | 24 |
| Monthly | month of the year | 12 |
| Quarterly | quarter of the year | 4 |

Our series is daily with a weekly cycle, so `period=7`.

`first_position` tells `decompose()` where in the cycle `data[0]` falls (1
to `period`). How you number the positions is up to you (for example 1 =
Monday). It does not normally change the decomposition, so the default `1` is
fine here; see [the API reference](api.md#11-arguments) for the one case
where it can matter.

## 3. Check the length

A series must be long enough for the seasonal filters. With the defaults and
`period=7`, the minimum is 56 observations; with `period=24`, it is 192. The
maximum, including any forecast extension, is 7,300 observations — about 20
years of daily data, or about 10 months of hourly data. The rules and a
table are in [the API reference](api.md#13-data-length).

Our 364 observations are well within both limits.

## 4. Choose the model

| Model | Use it when | Decomposition |
|---|---|---|
| `"multiplicative"` (default) | The seasonal swings grow with the level of the series. All values must be positive | `trend × seasonal × irregular` |
| `"log"` | As multiplicative, but decomposed additively on the logarithm, with the Thomson & Ozaki (2002) trend bias correction. All values must be positive | `trend × seasonal × irregular` |
| `"additive"` | The seasonal swings do not depend on the level, or the series has zeros or negative values | `trend + seasonal + irregular` |

Our series has a day-of-week pattern that scales with the level, so we use
the multiplicative model.

## 5. Decompose

In Python:

```python
from seasadj import decompose

result = decompose(data, period=7)
print(result.n_observed, result.n_forecast, len(result.trend))
```

```
364 0 364
```

The same from the command line, starting from a CSV file. First write the
series with a date column:

```python
import csv
from datetime import date, timedelta

start = date(2025, 1, 6)
with open("series.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "value"])
    for t, v in enumerate(data):
        w.writerow([(start + timedelta(days=t)).isoformat(), v])
```

Then:

```bash
seasadj series.csv --period 7
```

```
seasadj 1.1.0
  input      : series.csv  (column "value", 364 rows)
  period     : 7    first position: 1    model: multiplicative
  seasonal MA: 3x5  (selected)      Henderson: 23 / 23  (initial / final)
  output     : series_seasadj.csv  (364 rows)
```

The summary goes to standard error, and the result to `series_seasadj.csv`:

```
date,observed,prior_adjusted,trend,seasonal,irregular,adjusted
2025-01-06,223.80983855076855,223.80983855076855,200.53851917817124,1.0974513716607017,1.0169417668210512,203.93599600872673
2025-01-07,214.2498437465532,214.2498437465532,200.90670437430967,1.0665088942406664,0.9999115905705064,200.88894232719448
```

The date column is copied as a label only; it is never interpreted. The
command-line options are listed in [the API reference](api.md#51-csv-mode).
The rest of this tutorial uses the Python result.

## 6. Read the results

**Components.** `trend`, `seasonal`, `irregular` and `adjusted` are plain
lists of the same length as the input (plus the forecast extension, if any).
The seasonal factors of the first and the last week, compared with the
pattern we built in (1.10, 1.05, 1.00, 0.98, 1.02, 0.90, 0.95):

```python
print([round(s, 3) for s in result.seasonal[:7]])
print([round(s, 3) for s in result.seasonal[-7:]])
```

```
[1.097, 1.067, 1.004, 0.993, 0.997, 0.911, 0.932]
[1.112, 1.034, 0.993, 0.975, 1.029, 0.901, 0.956]
```

The seasonal factors are allowed to change slowly over time, so they differ
somewhat between the two ends. `adjusted` is the series divided by these
factors.

**Identity.** For the multiplicative model,
`prior_adjusted = trend × seasonal × irregular` holds within rounding
(`prior_adjusted` equals the input here, since no prior adjustment was
passed):

```python
worst = max(
    abs(p - t * s * i) / p
    for p, t, s, i in zip(result.prior_adjusted, result.trend,
                          result.seasonal, result.irregular)
)
print(worst < 1e-12)
```

```
True
```

**Which filters were chosen.** X-11 chooses the length of its filters from
the data. `diagnostics` records the choices:

```python
d = result.diagnostics
print("seasonal filter: 3x%d" % d["swm_term"])
print("MSR:", round(d["msr_ratio"], 2), "retries:", d["msr_count"])
print("Henderson terms (initial, final):", d["h_terms"])
print("irregular/trend ratios:", [round(x, 2) for x in d["sum_ratios"]])
print("SI ratios replaced (replaced, checked):", d["si_replaced"])
```

```
seasonal filter: 3x5
MSR: 3.64 retries: 0
Henderson terms (initial, final): [23, 23]
irregular/trend ratios: [4.98, 5.34]
SI ratios replaced (replaced, checked): [(50, 358), (56, 364)]
```

Read it as follows:

- The moving seasonality ratio (MSR) is 3.64, between 3.5 and 5.5, so the
  3x5 seasonal moving average was chosen on the first attempt.
- The day-to-day changes of the irregular are about 5 times those of the
  trend (above 3.5), so the 23-term Henderson filter was chosen for the trend
  in both passes. The 2% daily noise is large compared with the slow trend.
- The extreme-value replacement gave a reduced weight to 50 of 358 SI ratios
  in the first pass and 56 of 364 in the second (the first pass has fewer
  SI ratios because the initial centred moving average leaves none at the
  edges). Replacement protects the seasonal factors from outliers; the
  outliers themselves stay in the irregular component:

```python
for t in (50, 120, 300):
    print(t, round(result.irregular[t], 3))
```

```
50 1.464
120 0.569
300 1.29
```

Each key of `diagnostics`, and the exact selection rules, are described in
[the API reference](api.md#3-diagnostics).

## 7. Prior adjustment with X-13ARIMA-SEATS

`seasadj` reimplements only the X-11 core. Holiday, outlier and level-shift
effects, and a forecast extension, are estimated beforehand with a RegARIMA
model — typically in X-13ARIMA-SEATS — and passed to `decompose()`. This is
how the daily series of Arita (2022) were adjusted; the dates and values
below are made up for the series of this tutorial.

The statements about X-13ARIMA-SEATS in this section follow its Reference
Manual (version 1.1); section numbers refer to that manual.

### 7.1 Run the RegARIMA model

A spec file for our series could look like this:

```
series{file="series.dat" start=1.1 period=7}
transform{function=log}
arima{model=(0 1 1)(0 1 1)}
regression{variables=(ao8.2 ao18.2 ao43.7)
           save=(aoutlier levelshift holiday)}
forecast{maxlead=14 save=(forecasts)}
```

- `period=7`: with no `x11` or `seats` spec (no seasonal adjustment in X-13),
  the series spec accepts any seasonal period up to 12 (§7.15; the limit can
  be raised by recompiling, §2.8). Hourly data with `period=24` therefore
  needs a recompiled X-13.
- Dates follow X-13's `year.period` format (§3.3), with the cycle number in
  place of the year: `start=1.1` is position 1 of the first week, and
  `ao8.2` is position 2 of week 8 — our outlier at `data[50]` (observation
  51). Level shifts are written the same way (`ls<date>`).
- A holiday regressor of your own is added with `user=(...)`,
  `usertype=holiday` and `file="..."` in the regression spec. Its values
  must also cover the forecast period (§4.7).
- `transform{function=log}` is used only for estimating the RegARIMA model
  (§7.18). It decides the form of the saved effects:

| X-13 `transform` | Saved regression effects | `seasadj` model |
|---|---|---|
| `function=log` | ratios, near 1.0 | `"multiplicative"` or `"log"` — your choice; both take the effects as factors |
| none (the default) | on the scale of the series, near 0.0 | `"additive"` |

The manual states this restriction for X-13's own seasonal adjustment as
well: a log transformation for multiplicative or log-additive adjustment, no
transformation for additive adjustment (§7.18, DETAILS). Passing ratio-form
effects with `model="additive"` gives a wrong adjustment without any error.

### 7.2 Map the X-13 output to the arguments

X-13 saves each table requested with `save` to a file whose extension is the
table's short name (§3.2), for example `series.ao` for the `aoutlier` table.

| X-13 output | `decompose()` argument | Notes |
|---|---|---|
| `forecasts` (`fct`) | `forecast` | The forecast column. Forecasts are transformed back to the original scale (§4.7) |
| `aoutlier` (`ao`, table A8.AO) | `ao_effect` | At least `len(data)` values |
| `levelshift` (`ls`, table A8.LS) | `ls_effect` | At least `len(data)` values |
| `holiday` (`hol`, table A7) | `holiday_effect` | At least `len(data)` values |
| your holiday regressor file | `holiday_regressor` | Needed when `holiday_effect` and `forecast` are both given; must cover the observed and the forecast period |
| the estimate of that regressor in the "Regression Model" table of the main output | `holiday_coef` | With `transform{function=log}` this is a log-scale coefficient: `seasadj` computes the holiday effect of the forecast period as `exp(holiday_coef × regressor)` |

Over the forecast period, `seasadj` sets the outlier and level-shift effects
to neutral and computes the holiday effect from the regressor (see
[the API reference](api.md#12-effect-arguments)).

In the files saved by X-13 version 1.1, two heading lines are followed by one
line per observation: the date, then the value(s). A small reader:

```python
def read_x13_table(path, column=1):
    """Values of one column of a table saved by X-13ARIMA-SEATS."""
    with open(path) as f:
        lines = f.read().splitlines()[2:]  # skip the two heading lines
    return [float(line.split()[column]) for line in lines if line.strip()]
```

Then:

```python
result = decompose(
    data,
    period=7,
    forecast=read_x13_table("series.fct"),
    ao_effect=read_x13_table("series.ao"),
)
print(result.n_observed, result.n_forecast, len(result.trend))
```

```
364 14 378
```

### 7.3 What the forecast extension changes

With a forecast extension, the decomposition runs on the observed values and
the forecasts together. The filters near the end of the observed period then
use the forecasts instead of relying on the end of the series alone, and every
component is also returned for the forecast period: here the lists have
364 + 14 = 378 values, and index 364 onward is the forecast period.

## 8. Limits

- The period is never detected automatically (step 2).
- Missing values (NaN) and series with no variation are not validated: fill
  gaps before calling `decompose()`, and do not pass a constant series (see
  [the API reference](api.md#15-inputs-that-are-not-validated)).
- Some X-11 decision rules are applied with their monthly values for every
  period: the Henderson filter is chosen from 9, 13 or 23 terms with the
  thresholds 1.0 and 3.5, and the seasonal moving average with the MSR
  thresholds 2.5, 3.5, 5.5 and 6.5. See
  [the API reference](api.md#6-what-is-generalized-to-any-period-and-what-is-not)
  for what is and is not generalized to any period.

## Optional: plot the result

If you have matplotlib installed (it is not a dependency of `seasadj`):

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(3, 1, sharex=True, figsize=(8, 6))
axes[0].plot(result.observed, label="observed", lw=0.8)
axes[0].plot(result.adjusted, label="adjusted", lw=0.8)
axes[0].plot(result.trend, label="trend")
axes[0].legend()
axes[1].plot(result.seasonal)
axes[1].set_ylabel("seasonal")
axes[2].plot(result.irregular)
axes[2].set_ylabel("irregular")
plt.show()
```
