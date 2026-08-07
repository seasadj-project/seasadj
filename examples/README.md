# Example: COVID-19 daily case counts (Arita 2022 reproduction)

This example reproduces the day-of-week seasonal adjustment analysis of
Arita, Tetsuma (2022), *"Assessment of the spread of COVID-19 in seven
countries using a seasonal adjustment method,"* Statistical Journal of the
IAOS 38, 363-383, DOI: [10.3233/SJI-220932](https://doi.org/10.3233/SJI-220932)
— for the paper's seven countries (Germany, Indonesia, Iran, Russia, the
United Kingdom, the United States, and Japan) — using only public data and
`pip install seasadj`.

## What this reproduces, and what it doesn't

**This is a reproduction of the analysis, not a reproduction of the
published numbers.** It differs from the paper in several ways that matter:

- **No pre-adjustment.** The paper pre-adjusts each country's series with
  an X-13ARIMA-SEATS RegARIMA run: a fitted ARIMA model, moving-holiday
  regressors (e.g. Christmas/Easter for the UK, Golden Week/Silver
  Week/Obon for Japan, Idul Fitri for Indonesia), and additive outliers
  (see the paper's Table 1). The fitted regressors and outlier dates are
  not part of the paper's public data release, so this example calls
  `decompose()` directly on the raw (floored) daily case counts, with no
  holiday/outlier/level-shift effects. Whatever those effects would have
  removed — moving-holiday dips, one-off reporting anomalies — remains
  mixed into the irregular component here.
- **Different program version.** The paper's analysis used the
  Ver9_00-era program. This package's extreme SI-ratio replacement
  (`replace_extreme`, on by default) and the additive/log-additive modes
  were added later (Ver14 and Ver15/16); they were not part of the 2022
  analysis. Pass `--no-replace-extreme` to run closer to that program
  version; see "Options" below.
- **Sample period.** Arita (2022) section 2.4 states the sample period as
  **March 22, 2020 - July 2, 2021**; this example uses that same window by
  default (`fetch_covid_data.py`'s `--start`/`--end` defaults).
- **Markov-switching / pseudo real-time analysis are out of scope.** This
  example only covers the seasonal-adjustment decomposition (trend,
  seasonal, irregular); it does not reproduce the paper's sections 2.5-2.6.

**Numbers from this example will not match the paper's published figures.**
Please don't read a close visual match (e.g. the weekend dip in the
seasonal-factor table) as "reproduced the paper" — it's evidence the
package extracts a day-of-week pattern, not a validation against the
paper's fitted results.

## Data source and attribution

[COVID-19 Data Repository](https://github.com/CSSEGISandData/COVID-19) by
the Center for Systems Science and Engineering (CSSE) at Johns Hopkins
University, file
`csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv`,
licensed CC BY 4.0. The repository was archived (read-only) on
2023-03-10, so re-running `fetch_covid_data.py` today reproduces the same
bytes (verified: SHA-256
`e6234a59eec4359d2577358b5220e1a7e3da74c162913cdb7d882db1413f98c2`,
downloaded 2026-08-06). Arita (2022) itself draws on the same underlying
source (via Johns Hopkins University / Our World in Data, section 2.4);
this example fetches directly from the JHU CSSE repository rather than
Our World in Data because the JHU repository is frozen, so results here
won't drift as external datasets are revised.

Downloaded data is **not** committed to this repository (see
`.gitignore`); `fetch_covid_data.py` re-downloads it and records the
URL, fetch time and SHA-256 to `examples/data/PROVENANCE.txt` on every
run.

## Preprocessing: zero/negative values

Daily new-case counts are derived from JHU's cumulative counts by
first-differencing, and retroactive corrections in the source data
occasionally make a day's difference zero or negative. Arita (2022)
section 2.1 handles this by replacing such values with 0.1 before seasonal
adjustment ("*zero or negative values are replaced with 0.1 as part of
the initial data preprocessing*"); `fetch_covid_data.py` follows the same
rule (`--floor 0.1`, the default). The pre-replacement values are kept in
`<country>_daily_cases_raw.csv` so the effect of this step can be
inspected. Actual counts for the default 2020-03-22 to 2021-07-02 window:

| Country | Replaced days |
|---|---|
| Germany | 3 (2020-12-25, 2021-01-01, 2021-06-19) |
| Indonesia | 0 |
| Iran | 0 |
| Russia | 0 |
| United Kingdom | 2 (2021-04-09, 2021-05-18) |
| United States | 0 |
| Japan | 0 |

Pass `--floor 0` to disable replacement; `decompose()` will then raise
`SeasadjError` for any country/window that still has non-positive values
(the multiplicative model requires positive input) — this is intentional,
to show the validation behavior rather than silently produce a wrong
result.

## Running it

Two steps per country: fetch, then decompose.

```bash
python fetch_covid_data.py --country Japan
python covid19_daily_cases.py --country Japan
```

All seven countries (note `US`, not `"United States"`, and that "United
Kingdom" needs quoting because of the space):

```bash
python fetch_covid_data.py --country Germany
python fetch_covid_data.py --country Indonesia
python fetch_covid_data.py --country Iran
python fetch_covid_data.py --country Russia
python fetch_covid_data.py --country "United Kingdom"
python fetch_covid_data.py --country US
python fetch_covid_data.py --country Japan

python covid19_daily_cases.py --country Germany
python covid19_daily_cases.py --country Indonesia
python covid19_daily_cases.py --country Iran
python covid19_daily_cases.py --country Russia
python covid19_daily_cases.py --country "United Kingdom"
python covid19_daily_cases.py --country US
python covid19_daily_cases.py --country Japan
```

The United Kingdom's JHU rows include overseas territories (Anguilla,
Bermuda, Gibraltar, ...) as separate `Province/State` rows in addition to
a mainland total row (`Province/State` empty). `fetch_covid_data.py` uses
the empty-`Province/State` row alone when one exists, and only sums all
rows when it doesn't — so the UK figures here are the mainland total, not
mainland-plus-territories.

Output: `examples/output/<country>_decomposition.csv`
(`date,observed,trend,seasonal,irregular,adjusted`) plus a console summary
(diagnostics, the identity check, and the day-of-week seasonal-factor
table).

### Options

- `--model {multiplicative,additive,log}` (default `multiplicative`, the
  mode used in Arita 2022; the additive and log-additive modes did not
  exist in the program version used for the paper)
- `--no-replace-extreme` — disable X-11 extreme SI-ratio replacement, to
  run closer to the paper's program version (see "What this reproduces"
  above)
- `--start` / `--end` (`covid19_daily_cases.py`) — further trim the loaded
  series
- `--plot` — write a PNG (observed/trend + day-of-week seasonal factors)
  if `matplotlib` is installed; otherwise prints a note and exits
  normally. `matplotlib` is optional and not a dependency of `seasadj`
  itself.

### `first_position`

`decompose()` needs to know which day of the week the series starts on
(`first_position`, 1..7). This example computes it from the first
observation's date using Python's ISO convention:
`first_position = date.weekday() + 1`, i.e. **Monday = 1 ... Sunday = 7**.
Getting this wrong silently assigns the seasonal factors to the wrong day
of the week, so if you adapt this example to your own data, keep the same
convention (or a consistent one of your own).

## Reading the results

The console summary ends with the average seasonal factor by day of week
— for a multiplicative/log model, a value below 1.0 means that day
under-reports relative to the weekly average, and above 1.0 means it
over-reports. Every country in this example shows a Monday dip (reporting
lag over the weekend) and a mid-to-late-week peak, consistent with the
weekly reporting-cycle effect Arita (2022) section 3.3 describes, though
the exact factors won't match the paper's (see "What this reproduces").

## Disclaimer

This example is for illustrating the software's usage on real data. It is
not an epidemiological analysis, and the trend/seasonal/irregular series
it produces should not be used to draw conclusions about the actual course
of the pandemic in any of the countries shown.
