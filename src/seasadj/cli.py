"""Command-line interface: CSV mode and the argument parser shared with the
working-directory mode (see __main__.py).

CSV mode reads one observed series from a CSV file, calls decompose() and
writes the components to a CSV file. It is a thin layer on top of
decompose(): the numerical core is untouched. A date/label column, if any, is
copied to the output as-is and is never used in the computation (in
particular first_position is never inferred from it).
"""

import argparse
import csv
import math
import sys
from pathlib import Path

from .api import decompose
from .reg import SeasadjError

OUTPUT_COLUMNS = ["observed", "prior_adjusted", "trend", "seasonal",
                  "irregular", "adjusted"]

# options that only make sense for CSV input (used to reject them in
# working-directory mode instead of silently ignoring them)
_CSV_ONLY = ("period", "column", "date_column", "no_header", "first_position",
             "model", "seasonal_ma", "sigma", "no_replace_extreme", "output",
             "quiet")


def build_parser():
    from . import __version__

    p = argparse.ArgumentParser(
        prog="seasadj",
        description=(
            "X-11 style seasonal adjustment for any cycle length. "
            "If PATH is a CSV file, it is adjusted and the result is written "
            "to a CSV file (CSV mode). If PATH is a directory (default: the "
            "current directory), it is treated as a Fortran-compatible working "
            "directory holding in_data/ (file mode; see docs/file-formats.md)."),
        epilog=(
            "CSV mode example:  seasadj data.csv --period 7 -o out.csv\n"
            "File mode example: seasadj path/to/workdir"),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", nargs="?", default=".", metavar="PATH",
                   help="CSV file (CSV mode) or working directory (file mode)")
    p.add_argument("--version", action="version",
                   version=f"seasadj {__version__}")

    g = p.add_argument_group("CSV mode options")
    g.add_argument("--period", type=int, metavar="N",
                   help="seasonal cycle length (required in CSV mode)")
    g.add_argument("--column", metavar="NAME|INDEX",
                   help="observed-value column: header name or 0-based index "
                        "(default: last column)")
    g.add_argument("--date-column", dest="date_column", metavar="NAME|INDEX",
                   help="date/label column, copied to the output heading only "
                        "(default: the first column unless it is the value "
                        "column)")
    g.add_argument("--no-header", dest="no_header", action="store_true",
                   help="do not treat the first row as a header")
    g.add_argument("--first-position", dest="first_position", type=int,
                   metavar="N", help="cycle position of the first value "
                   "(default: 1)")
    g.add_argument("--model", choices=["multiplicative", "additive", "log"],
                   help="decomposition model (default: multiplicative)")
    g.add_argument("--seasonal-ma", dest="seasonal_ma", type=int,
                   choices=[3, 5, 9],
                   help="initial seasonal moving average term (default: 3)")
    g.add_argument("--sigma", type=float, nargs=2, metavar=("LOW", "UPPER"),
                   help="sigma limits for extreme SI-ratio replacement "
                        "(default: 1.5 2.5)")
    g.add_argument("--no-replace-extreme", dest="no_replace_extreme",
                   action="store_true",
                   help="turn off extreme SI-ratio replacement")
    g.add_argument("-o", "--output", metavar="PATH",
                   help="output CSV (default: <input stem>_seasadj.csv next "
                        "to the input; '-' for standard output)")
    g.add_argument("--quiet", action="store_true",
                   help="suppress the summary printed to standard error")
    return p


def _err(msg):
    print(f"seasadj: error: {msg}", file=sys.stderr)


def _resolve_column(spec, header, ncols, what):
    """Return a 0-based column index from a name (needs a header) or index."""
    if header is not None and spec in header:
        return header.index(spec)
    try:
        idx = int(spec)
    except ValueError:
        if header is None:
            raise SeasadjError(
                f"--{what} {spec!r}: a column name needs a header row "
                "(use a 0-based column index with --no-header)")
        raise SeasadjError(
            f"--{what} {spec!r}: no such column; the header is {header}")
    if not 0 <= idx < ncols:
        raise SeasadjError(
            f"--{what} {spec}: column index out of range "
            f"(the file has {ncols} columns, indexed 0..{ncols - 1})")
    return idx


def read_csv_series(path, column=None, date_column=None, no_header=False):
    """Read (values, labels, column_description) from a CSV file.

    labels is None when there is no date/label column. Errors are reported as
    SeasadjError with the row number (1-based, as seen in the file)."""
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = [(i, r) for i, r in enumerate(csv.reader(f), start=1) if r]
    except OSError as e:
        raise SeasadjError(f"cannot read {path}: {e.strerror or e}")
    except UnicodeDecodeError:
        raise SeasadjError(
            f"cannot read {path} as UTF-8; please save the file as UTF-8 CSV")
    if not rows:
        raise SeasadjError(f"{path} is empty")

    ncols = max(len(r) for _, r in rows)
    first_row = rows[0][1]

    # -- value column (needs the header decision, which needs the column) --
    def try_float(s):
        try:
            return float(s)
        except ValueError:
            return None

    # Decide the header from the first row's value cell. For a name given in
    # --column the first row is the header by definition.
    header = None
    if no_header:
        has_header = False
    elif column is not None and column in first_row:
        has_header = True
    else:
        if column is None:
            probe = len(first_row) - 1
        else:
            try:
                probe = int(column)
            except ValueError:
                probe = None  # a name that is not in the first row
        if probe is None:
            has_header = True  # reported below as "no such column"
        elif 0 <= probe < len(first_row):
            has_header = try_float(first_row[probe].strip()) is None
        else:
            has_header = False
    if has_header:
        header = [h.strip() for h in first_row]
        rows = rows[1:]

    if column is None:
        vcol = ncols - 1
    else:
        vcol = _resolve_column(column, header, ncols, "column")
    if date_column is None:
        dcol = 0 if (ncols > 1 and vcol != 0) else None
    else:
        dcol = _resolve_column(date_column, header, ncols, "date-column")
        if dcol == vcol:
            raise SeasadjError("--date-column and --column are the same column")

    values, labels = [], []
    for lineno, r in rows:
        if vcol >= len(r):
            raise SeasadjError(
                f"{path}, row {lineno}: no value in column {vcol} "
                f"(the row has {len(r)} columns)")
        raw = r[vcol].strip()
        v = try_float(raw)
        if v is None or not math.isfinite(v):
            raise SeasadjError(
                f"{path}, row {lineno}: cannot use {raw!r} as a number "
                f"(column {vcol})")
        values.append(v)
        if dcol is not None:
            labels.append(r[dcol].strip() if dcol < len(r) else "")
    if not values:
        raise SeasadjError(f"{path} has a header but no data rows")

    if header is not None:
        col_desc = f'column "{header[vcol]}"'
    else:
        col_desc = f"column #{vcol}"
    return values, (labels if dcol is not None else None), col_desc


def build_output_rows(result, labels):
    """Header + rows for the output CSV. Series lengths are checked: the
    observed series is shorter than the others when there is a forecast
    extension, and a plain zip() would silently drop rows."""
    series = {name: getattr(result, name) for name in OUTPUT_COLUMNS}
    n_total = len(series["trend"])
    for name in ("prior_adjusted", "seasonal", "irregular", "adjusted"):
        if len(series[name]) != n_total:
            raise SeasadjError(
                f"internal error: series length mismatch ({name}: "
                f"{len(series[name])} != {n_total})")
    if len(series["observed"]) > n_total:
        raise SeasadjError("internal error: observed series longer than trend")

    header = (["date"] if labels is not None else []) + OUTPUT_COLUMNS
    rows = []
    for i in range(n_total):
        row = []
        if labels is not None:
            row.append(labels[i] if i < len(labels) else "")
        for name in OUTPUT_COLUMNS:
            s = series[name]
            row.append(repr(float(s[i])) if i < len(s) else "")
        rows.append(row)
    return header, rows


def _write_csv(out, header, rows):
    w = csv.writer(out, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)


def run_csv(args):
    """CSV mode. Raises SeasadjError on any user-facing failure."""
    from . import __version__

    path = Path(args.path)
    if args.period is None:
        raise SeasadjError(
            "--period is required in CSV mode (e.g. --period 7 for "
            "day-of-week seasonality in daily data)")

    values, labels, col_desc = read_csv_series(
        path, args.column, args.date_column, args.no_header)

    if args.output == "-":
        out_path = None
    elif args.output is not None:
        out_path = Path(args.output)
    else:
        out_path = path.with_name(path.stem + "_seasadj.csv")
    if out_path is not None and out_path.resolve() == path.resolve():
        raise SeasadjError("the output file would overwrite the input file")

    kwargs = {}
    if args.first_position is not None:
        kwargs["first_position"] = args.first_position
    if args.model is not None:
        kwargs["model"] = args.model
    if args.seasonal_ma is not None:
        kwargs["seasonal_ma"] = args.seasonal_ma
    if args.sigma is not None:
        kwargs["sigma"] = tuple(args.sigma)
    if args.no_replace_extreme:
        kwargs["replace_extreme"] = False

    result = decompose(values, args.period, **kwargs)
    header, rows = build_output_rows(result, labels)

    if out_path is None:
        _write_csv(sys.stdout, header, rows)
    else:
        try:
            with open(out_path, "w", encoding="utf-8", newline="") as f:
                _write_csv(f, header, rows)
        except OSError as e:
            raise SeasadjError(f"cannot write {out_path}: {e.strerror or e}")

    if not args.quiet:
        d = result.diagnostics
        ih, fh = d["h_terms"]
        print(f"seasadj {__version__}\n"
              f"  input      : {path.name}  ({col_desc}, {len(values)} rows)\n"
              f"  period     : {result.period}    first position: "
              f"{args.first_position or 1}    model: {result.model}\n"
              f"  seasonal MA: 3x{d['swm_term']}  (selected)      "
              f"Henderson: {ih} / {fh}  (initial / final)\n"
              f"  output     : {out_path.name if out_path else '<stdout>'}  "
              f"({len(rows)} rows)", file=sys.stderr)


def main(argv=None):
    from .main import run

    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    path = Path(args.path)

    try:
        if path.is_dir():
            used = [o for o in _CSV_ONLY if getattr(args, o)]
            if used:
                parser.error("these options apply to CSV input only, but "
                             f"{path} is a directory: "
                             + ", ".join("--" + o.replace("_", "-") for o in used))
            run(path)
        elif path.is_file():
            run_csv(args)
        else:
            raise SeasadjError(
                f"{path} not found (expected a CSV file, or a working "
                "directory holding in_data/)")
    except SeasadjError as e:
        # file mode (abort_run) has already printed "ERROR: ..." itself
        if not str(e) or path.is_dir():
            return 1
        _err(e)
        return 1
    return 0
