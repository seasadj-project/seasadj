#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Data source: COVID-19 Data Repository by the Center for Systems Science
# and Engineering (CSSE) at Johns Hopkins University (CC BY 4.0).
# https://github.com/CSSEGISandData/COVID-19
"""Fetch and prepare JHU CSSE daily COVID-19 case counts for one country.

Downloads the (archived, read-only since 2023-03-10) JHU CSSE global
confirmed-cases time series, extracts one country's cumulative counts,
converts them to daily new cases (first-difference), and applies the
zero/negative -> 0.1 preprocessing used in Arita (2022, SJIAOS,
DOI: 10.3233/SJI-220932, section 2.1).

See examples/README.md for the full reproduction notes and caveats.
"""

import argparse
import csv
import datetime as dt
import hashlib
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/"
    "csse_covid_19_data/csse_covid_19_time_series/"
    "time_series_covid19_confirmed_global.csv"
)
ATTRIBUTION = (
    "COVID-19 Data Repository by the Center for Systems Science and "
    "Engineering (CSSE) at Johns Hopkins University"
)

# Country/Region values exactly as they appear in the JHU CSSE file
# (verified against the live file on 2026-08-06; see examples/README.md).
# This is also the string to pass as --country.
SUPPORTED_COUNTRIES = (
    "Germany", "Indonesia", "Iran", "Russia",
    "United Kingdom", "US", "Japan",
)

# Sample period used for the seasonal adjustment in Arita (2022), stated
# explicitly in section 2.4 "Data": "The data period is from March 22,
# 2020, to July 2, 2021."
DEFAULT_START = "2020-03-22"
DEFAULT_END = "2021-07-02"

DATA_DIR = Path(__file__).resolve().parent / "data"


def slug(country):
    return country.lower().replace(" ", "_").replace("/", "_")


def download(url, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "time_series_covid19_confirmed_global.csv"
    with urllib.request.urlopen(url) as resp:
        raw = resp.read()
    dest.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(dest_dir / "PROVENANCE.txt", "a", encoding="utf-8") as f:
        f.write(
            f"url: {url}\n"
            f"fetched_at (UTC): {fetched_at}\n"
            f"sha256: {digest}\n"
            f"attribution: {ATTRIBUTION}\n"
            f"license: CC BY 4.0\n"
            "note: repository archived (read-only) 2023-03-10; "
            "re-downloading is expected to reproduce the same bytes/hash.\n"
            "---\n"
        )
    print(f"Downloaded {len(raw)} bytes to {dest}")
    print(f"SHA-256: {digest}")
    return dest


def extract_country_series(csv_path, country):
    """Return (dates, cumulative_counts) for one Country/Region.

    If a row with an empty Province/State exists (the country-level total
    row), it is used alone; otherwise all Province/State rows for that
    country are summed. This matters for the United Kingdom, which has a
    mainland row (Province/State empty) plus separate overseas-territory
    rows (Anguilla, Bermuda, ...) that must not be folded in.
    """
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[4:]
        rows = [row for row in reader if row[1] == country]

    if not rows:
        raise SystemExit(
            f"Country/Region '{country}' not found in {csv_path}. "
            f"Supported values: {', '.join(SUPPORTED_COUNTRIES)}"
        )

    empty_province_rows = [r for r in rows if r[0] == ""]
    if empty_province_rows:
        chosen = empty_province_rows
        print(f"{country}: using the single Province/State-empty row "
              f"(ignoring {len(rows) - len(chosen)} other row(s), if any)")
    else:
        chosen = rows
        print(f"{country}: no Province/State-empty row; summing all "
              f"{len(rows)} row(s)")

    n = len(date_cols)
    totals = [0] * n
    for row in chosen:
        for i, v in enumerate(row[4:4 + n]):
            totals[i] += int(v)

    dates = [dt.datetime.strptime(c, "%m/%d/%y").date() for c in date_cols]
    return dates, totals


def daily_new_cases(dates, cumulative):
    """First-difference the cumulative series. The first date has no prior
    day to diff against and is dropped."""
    out_dates = dates[1:]
    out_values = [cumulative[i] - cumulative[i - 1] for i in range(1, len(cumulative))]
    return out_dates, out_values


def apply_floor(dates, values, floor):
    floored = []
    replaced = []
    for d, v in zip(dates, values):
        if floor > 0 and v <= 0:
            replaced.append((d, v))
            floored.append(floor)
        else:
            floored.append(v)
    return floored, replaced


def write_csv(path, dates, values):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "cases"])
        for d, v in zip(dates, values):
            w.writerow([d.isoformat(), v])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", required=True, choices=SUPPORTED_COUNTRIES,
                         help="Country/Region label as it appears in the JHU "
                              "CSSE file, e.g. Japan, US, 'United Kingdom'")
    parser.add_argument("--start", default=DEFAULT_START,
                         help=f"inclusive start date, YYYY-MM-DD "
                              f"(default: {DEFAULT_START}, the sample "
                              f"period stated in Arita 2022 section 2.4)")
    parser.add_argument("--end", default=DEFAULT_END,
                         help=f"inclusive end date, YYYY-MM-DD "
                              f"(default: {DEFAULT_END})")
    parser.add_argument("--floor", type=float, default=0.1,
                         help="replace non-positive daily counts with this "
                              "value (Arita 2022 section 2.1 preprocessing); "
                              "pass 0 to disable replacement")
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args(argv)

    csv_path = download(args.source_url, args.data_dir)

    dates, cumulative = extract_country_series(csv_path, args.country)
    daily_dates, daily_values = daily_new_cases(dates, cumulative)

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    window = [(d, v) for d, v in zip(daily_dates, daily_values) if start <= d <= end]
    if not window:
        raise SystemExit(f"No data in [{start}, {end}] for {args.country}")
    win_dates, win_values = zip(*window)

    country_slug = slug(args.country)
    raw_path = args.data_dir / f"{country_slug}_daily_cases_raw.csv"
    write_csv(raw_path, win_dates, win_values)

    floored_values, replaced = apply_floor(win_dates, win_values, args.floor)
    out_path = args.data_dir / f"{country_slug}_daily_cases.csv"
    write_csv(out_path, win_dates, floored_values)

    print(f"{args.country}: {len(win_dates)} observations, "
          f"{win_dates[0].isoformat()}..{win_dates[-1].isoformat()}")
    if args.floor > 0:
        print(f"{args.country}: {len(replaced)} day(s) floored to {args.floor}")
        for d, v in replaced:
            print(f"  {d.isoformat()}: {v} -> {args.floor}")
    else:
        nonpositive = sum(1 for v in win_values if v <= 0)
        print(f"{args.country}: --floor 0, replacement disabled; "
              f"{nonpositive} non-positive value(s) left as-is")
    print(f"Wrote {raw_path} (pre-floor values)")
    print(f"Wrote {out_path} (floored values, input to covid19_daily_cases.py)")


if __name__ == "__main__":
    main()
