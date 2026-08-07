#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Decompose a daily COVID-19 case series with seasadj.

Reproduces the day-of-week seasonal adjustment analysis in Arita (2022,
SJIAOS, DOI: 10.3233/SJI-220932) for one of the paper's seven countries,
using the public JHU CSSE data fetched by fetch_covid_data.py and calling
decompose() with no pre-adjustment (no RegARIMA holiday/outlier effects --
the paper's fitted effects are not redistributable). See examples/README.md
for what this does and does not reproduce.

Usage:
    python fetch_covid_data.py --country Japan
    python covid19_daily_cases.py --country Japan
"""

import argparse
import csv
import datetime as dt
from pathlib import Path

from seasadj import decompose, SeasadjError

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# date.weekday(): Monday=0 .. Sunday=6
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                  "Saturday", "Sunday"]


def slug(country):
    return country.lower().replace(" ", "_").replace("/", "_")


def load_series(path, start=None, end=None):
    dates, values = [], []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = dt.date.fromisoformat(row["date"])
            if start and d < start:
                continue
            if end and d > end:
                continue
            dates.append(d)
            values.append(float(row["cases"]))
    return dates, values


def identity_error(result):
    """Max relative error of prior_adjusted ~= trend*seasonal*irregular
    (multiplicative/log), or max absolute error of the additive identity."""
    max_err = 0.0
    for pa, t, s, i in zip(result.prior_adjusted, result.trend,
                            result.seasonal, result.irregular):
        if result.model == "additive":
            err = abs(pa - (t + s + i))
        else:
            predicted = t * s * i
            err = abs(pa - predicted) / abs(pa) if pa != 0 else abs(pa - predicted)
        max_err = max(max_err, err)
    return max_err


def weekday_seasonal_table(dates, seasonal):
    buckets = {i: [] for i in range(7)}
    for d, s in zip(dates, seasonal):
        buckets[d.weekday()].append(s)
    return [(WEEKDAY_NAMES[i], sum(v) / len(v) if v else float("nan"))
            for i, v in buckets.items()]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", required=True,
                         help="same value passed to fetch_covid_data.py, "
                              "e.g. Japan, US, 'United Kingdom'")
    parser.add_argument("--model", default="multiplicative",
                         choices=["multiplicative", "additive", "log"])
    parser.add_argument("--no-replace-extreme", action="store_true",
                         help="disable X-11 extreme SI-ratio replacement, "
                              "which the program version used in Arita "
                              "(2022) did not have (added in Ver14)")
    parser.add_argument("--start", default=None, help="further-trim the "
                         "loaded series, inclusive, YYYY-MM-DD")
    parser.add_argument("--end", default=None)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--plot", action="store_true",
                         help="write a PNG plot (requires matplotlib)")
    args = parser.parse_args(argv)

    country_slug = slug(args.country)
    csv_path = args.data_dir / f"{country_slug}_daily_cases.csv"
    if not csv_path.exists():
        raise SystemExit(
            f"{csv_path} not found. Run:\n"
            f"  python fetch_covid_data.py --country '{args.country}'"
        )

    start = dt.date.fromisoformat(args.start) if args.start else None
    end = dt.date.fromisoformat(args.end) if args.end else None
    dates, values = load_series(csv_path, start, end)
    if not dates:
        raise SystemExit(f"No rows in {csv_path} within the requested window")

    # first_position convention: ISO weekday of the first observation
    # (Monday=1 .. Sunday=7, i.e. date.weekday() + 1). Seasonal-factor
    # position p therefore always corresponds to weekday p-1 in Python's
    # date.weekday() numbering (0=Monday). Get this wrong and the seasonal
    # factors are silently assigned to the wrong day of the week.
    first_position = dates[0].weekday() + 1

    try:
        result = decompose(
            values,
            period=7,
            first_position=first_position,
            model=args.model,
            replace_extreme=not args.no_replace_extreme,
        )
    except SeasadjError as exc:
        raise SystemExit(f"seasadj rejected the input: {exc}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / f"{country_slug}_decomposition.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "observed", "trend", "seasonal", "irregular", "adjusted"])
        for d, o, t, s, i, a in zip(dates, result.observed, result.trend,
                                     result.seasonal, result.irregular,
                                     result.adjusted):
            w.writerow([d.isoformat(), o, t, s, i, a])

    diag = result.diagnostics
    print(f"{args.country}: {len(dates)} observations, "
          f"{dates[0].isoformat()}..{dates[-1].isoformat()}, model={args.model}")
    print(f"h_terms (Step1, Step2) = {diag['h_terms']}")
    print(f"swm_term = {diag['swm_term']}, msr_ratio = {diag['msr_ratio']:.4f}, "
          f"msr_count = {diag['msr_count']}")
    print(f"si_replaced [(count, checked), ...] = {diag['si_replaced']}")
    if args.model == "log":
        print(f"trend bias correction (sig) = {diag['bias_sig']}")

    max_err = identity_error(result)
    label = "max absolute error" if args.model == "additive" else "max relative error"
    print(f"Identity check, prior_adjusted vs trend/seasonal/irregular "
          f"({label}): {max_err:.3e}")

    print("Average seasonal factor by day of week:")
    for name, avg in weekday_seasonal_table(dates, result.seasonal):
        print(f"  {name:9s} {avg:.4f}")

    print(f"Wrote {out_path}")

    if args.plot:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed; skipping --plot "
                  "(pip install matplotlib to enable it)")
        else:
            fig, axes = plt.subplots(2, 1, figsize=(10, 6))
            axes[0].plot(dates, result.observed, label="observed", linewidth=0.7)
            axes[0].plot(dates, result.trend, label="trend", linewidth=1.5)
            axes[0].set_title(f"{args.country}: observed vs trend")
            axes[0].legend()
            names, avgs = zip(*weekday_seasonal_table(dates, result.seasonal))
            axes[1].bar(names, avgs)
            axes[1].axhline(1.0 if args.model != "additive" else 0.0,
                             color="gray", linewidth=0.7)
            axes[1].set_title("Average seasonal factor by day of week")
            fig.tight_layout()
            plot_path = args.output_dir / f"{country_slug}_plot.png"
            fig.savefig(plot_path, dpi=120)
            print(f"Wrote {plot_path}")


if __name__ == "__main__":
    main()
