# File formats of the working-directory mode

`seasadj <workdir>` (and `python -m seasadj <workdir>`) runs the
Fortran-compatible **file mode**: it reads parameters and series from text
files in a working directory and writes the results to `out_data/`.

> This mode exists for compatibility with the original Fortran program, which
> uses the same files. **For new work, prefer the CSV mode
> (`seasadj data.csv --period 7`) or the `decompose()` API**; both need no
> parameter file. Use the file mode if you are migrating from the Fortran
> version, or if you need the intermediate series (`o08`–`o25`).

All files are plain text (UTF-8/ASCII). Numbers are read as the first
whitespace-separated token of a line; blank lines in series files are skipped;
Fortran-style exponents (`1.0D+2`) are accepted.

## 1. Directory layout

```
workdir/
├─ in_data/
│   ├─ i00_inp.dat        parameters (required)
│   ├─ i01_org_ser.dat    observed series (required)
│   ├─ i02_fct_ser.dat    forecast series        (only if B = 1)
│   ├─ i03_hol_reg.dat    holiday regression var (only if C = 1)
│   ├─ i04_hol_eff.dat    holiday effect         (only if C = 1)
│   ├─ i05_aol_eff.dat    additive-outlier effect(only if E = 1)
│   └─ i06_lvs_eff.dat    level-shift effect     (only if F = 1)
├─ para/                  moving-average weights (optional, see below)
└─ out_data/              created if missing; results are written here
```

`para/` holds the 11 weight files (`3x3_mov_ave.dat`, …, `23_henderson.dat`) of
the Fortran program. **It is optional**: each file is taken from
`workdir/para/` if present there, otherwise from the copy bundled in the
installed package (the two are identical). Put a file in `workdir/para/` only
if you want to override a weight table.

## 2. `i00_inp.dat` — parameters

Two header lines, then **13 blocks** (A–M). Each block is **two comment lines
followed by one value line**; only the value line is read (its first token),
the comment lines are skipped whatever they contain. All 13 blocks are
required, in this order.

| Block | Symbol | Meaning | Type / allowed values | `decompose()` argument (default) |
|---|---|---|---|---|
| A | `ini_o_day` | cycle position of the first observation | int, 1 … G | `first_position` (1) |
| B | `forecasting` | a forecast series is supplied in `i02` | 0 or 1 | `forecast` (None → 0) |
| C | `reg_hol` | holiday effect supplied (`i03`, `i04`) | 0 or 1 | `holiday_effect` / `holiday_regressor` (None → 0) |
| D | `hol_reg_p` | holiday regression coefficient | float | `holiday_coef` (0.0) |
| E | `reg_ao` | additive-outlier effect supplied (`i05`) | 0 or 1 | `ao_effect` (None → 0) |
| F | `reg_ls` | level-shift effect supplied (`i06`) | 0 or 1 | `ls_effect` (None → 0) |
| G | `term` | seasonal cycle length (period) | int, ≥ 2 | `period` (required) |
| H | `iwm_term` | initial seasonal moving average (3x3 / 3x5 / 3x9) | 3, 5 or 9 | `seasonal_ma` (3) |
| I | `ft_o` | running position of the first observation | int, ≥ 1 | `ft_o` (1) |
| J | `rep_si` | extreme SI-ratio replacement | 0 or 1 | `replace_extreme` (True) |
| K | `sig_l` | lower sigma limit (checked only if J = 1) | float, > 0 | `sigma[0]` (1.5) |
| L | `sig_u` | upper sigma limit (checked only if J = 1) | float, > K | `sigma[1]` (2.5) |
| M | `model` | decomposition model | 0 multiplicative, 1 additive, 2 log | `model` (`"multiplicative"`) |

A parameter outside its range stops the run with an error message. The file
has no defaults of its own: every block must be present.

`first_position` (A) declares which cycle position the first observation has.
The X-11 filters work on positions relative to the start of the series, so it
does not normally change the result (see the `decompose()` documentation).

## 3. `i01` – `i06` — input series

One value per line.

| File | Needed when | Content | Required length |
|---|---|---|---|
| `i01_org_ser.dat` | always | observed series | at least 20 values; at least `G × (H + 3)`; at least `G × 8` if J = 1; total with `i02` at most 7300 |
| `i02_fct_ser.dat` | B = 1 | forecast-extension values (e.g. from an X-13ARIMA-SEATS RegARIMA run), appended after the observed series | at least 1 |
| `i03_hol_reg.dat` | C = 1 (the file must exist) | holiday regression variable | with a forecast: observed + forecast values; its forecast-period part extends the holiday effect as `exp(D × value)` (additive model: `D × value`) |
| `i04_hol_eff.dat` | C = 1 | holiday effect for the observed period | one value per observation |
| `i05_aol_eff.dat` | E = 1 | additive-outlier effect | one value per observation |
| `i06_lvs_eff.dat` | F = 1 | level-shift effect | one value per observation |

Notes:

- When C, E or F is 0, the corresponding effect is treated as neutral and its
  file is not read.
- During the forecast period the AO and LS effects are neutral, and the
  holiday effect is derived from `i03` and D, as above.
- **Multiplicative and log models** (M = 0 or 2): the effect files hold
  multiplicative factors near 1.0 (values the data are *divided* by; they must
  be positive), and the observed and forecast values must be strictly
  positive. **Additive model** (M = 1): the effect files hold amounts near 0.0
  (values *subtracted*), and zero/negative data are allowed. Do not mix the
  two conventions.
- The same checks apply as in `decompose()`; violations stop the run with a
  message that names the problem.

## 4. `o01` – `o25` — output series

Written to `out_data/`, one value per line, full precision (`repr` of the
double). `n` = number of observations, `n_f` = number of forecast values
(0 if B = 0). For the log model (M = 2) all series are returned on the
original scale, so the multiplicative identity holds.

| File | Series | Length | `decompose()` field |
|---|---|---|---|
| `o01_org.dat` | observed | `n` | `observed` |
| `o07_adj.dat` | prior-adjusted series (after holiday/AO/LS adjustment) | `n + n_f` | `prior_adjusted` |
| `o08_TC1.dat` | trend-cycle, first pass | `n + n_f` (padded) | `internals["TC1"]` |
| `o09_SI1.dat` | seasonal-irregular, first pass | `n + n_f` (padded) | `internals["SI1"]` |
| `o10_S1p.dat` | preliminary seasonal, first pass | `n + n_f` | `internals["S1p"]` |
| `o11__S1.dat` | seasonal, first pass | `n + n_f` | `internals["S1"]` |
| `o12__A1.dat` | seasonally adjusted, first pass | `n + n_f` | `internals["A1"]` |
| `o13_TC2.dat` | trend-cycle, second pass | `n + n_f` | `internals["TC2"]` |
| `o14_SI2.dat` | seasonal-irregular, second pass | `n + n_f` | `internals["SI2"]` |
| `o15_S2p.dat` | preliminary seasonal, second pass | `n + n_f` | `internals["S2p"]` |
| **`o16__S2.dat`** | **final seasonal** | `n + n_f` | **`seasonal`** |
| **`o17__A2.dat`** | **final seasonally adjusted** | `n + n_f` | **`adjusted`** |
| **`o18_TC3.dat`** | **final trend-cycle** | `n + n_f` | **`trend`** |
| **`o19__I3.dat`** | **final irregular** | `n + n_f` | **`irregular`** |
| `o20_SUM.dat` | summary table (one header line, then one row per period: index, cycle position, observed, TC3, S2, I3, A2, three effects). Values are printed with fixed decimals, so use `o16`–`o19` for exact values | `n + n_f` rows | — |
| `o21_INT.dat` | internal data: the parameters used, the Henderson terms (`ih_term`, `fh_term`) and seasonal MA term (`swm_term`) selected, and the lengths of all series | text | `diagnostics` |
| `o22_SI1w.dat` | extreme-value weights for `SI1` | `n + n_f` (padded) | `internals["w1"]` |
| `o23_SI1r.dat` | `SI1` after extreme-value replacement | `n + n_f` (padded) | `internals["SI1r"]` |
| `o24_SI2w.dat` | extreme-value weights for `SI2` | `n + n_f` | `internals["w2"]` |
| `o25_SI2r.dat` | `SI2` after extreme-value replacement | `n + n_f` | `internals["SI2r"]` |

**Padding at the series edges.** Where a value cannot be computed, the file
still keeps the full length and the cell is filled with a fixed value:

- `o08_TC1`, `o09_SI1`, `o23_SI1r` (the first-pass moving average is not
  defined at the edges): `(G − 1) / 2` cells at each end for an odd period,
  `G / 2` cells at each end for an even period. Fill value: **0.0** for the
  multiplicative and log models, **−999.0** for the additive model.
- `o22_SI1w` (weights): the same edge cells are filled with **1.0**.
- The other series have no padding.

(`decompose()` exposes the same series in `internals` as plain lists with
the same fill convention; `internals` carries no backward-compatibility
guarantee.)

## 5. A minimal run

This creates a work directory with a synthetic 70-day series (period 7, no
forecast, no holiday/AO/LS adjustment, multiplicative model) and runs it.

```python
import math, pathlib

wd = pathlib.Path("demo"); (wd / "in_data").mkdir(parents=True, exist_ok=True)

values = [(100 + 0.5 * i) * (1 + 0.2 * math.sin(2 * math.pi * (i % 7) / 7))
          * (1 + 0.01 * math.sin(1.7 * i)) for i in range(70)]
(wd / "in_data" / "i01_org_ser.dat").write_text(
    "\n".join(repr(v) for v in values) + "\n")

params = [1, 0, 0, 0.0, 0, 0, 7, 3, 1, 1, 1.5, 2.5, 0]   # A ... M
lines = ["-" * 60, "Please set following 13 parameters"]
for letter, v in zip("ABCDEFGHIJKLM", params):
    lines += ["-" * 60, f"{letter}. parameter", str(v)]
(wd / "in_data" / "i00_inp.dat").write_text("\n".join(lines) + "\n")
```

```bash
seasadj demo
```

The final series appear in `demo/out_data/` as `o16__S2.dat` (seasonal),
`o17__A2.dat` (seasonally adjusted), `o18_TC3.dat` (trend-cycle) and
`o19__I3.dat` (irregular), each with 70 lines. For the multiplicative model
the observed series is, up to rounding, the product of `o18`, `o16` and `o19`.
`o21_INT.dat` shows which filters were selected.

On failure the program prints `ERROR: <reason>` and exits with status 1; for
example, a work directory without `in_data/i00_inp.dat` reports which file is
missing and the expected layout.
