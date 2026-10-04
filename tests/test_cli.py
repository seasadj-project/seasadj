"""CLI tests: working-directory mode (para/ fallback) and, below, CSV mode.

All data are synthetic (closed form); no private validation data is used.
"""

import math
import shutil

import pytest

from seasadj import var
from seasadj.__main__ import main
from seasadj.var import bundled_para_dir

from conftest import _write_i00, _write_series, _read_series

OUT_FILES = ["o16__S2.dat", "o17__A2.dat", "o18_TC3.dat", "o19__I3.dat"]


def synth(n, period):
    out = []
    for i in range(n):
        trend = 100.0 + 0.05 * i
        seas = 1.0 + 0.2 * math.sin(2 * math.pi * (i % period) / period)
        irr = 1.0 + 0.01 * math.sin(1.7 * i + 0.3)
        out.append(trend * seas * irr)
    return out


def make_workdir(path, data, para="full"):
    """Create a work directory. para: "full" (copy of all weight files),
    "none" (no para/), or a list of file names to copy."""
    (path / "in_data").mkdir(parents=True)
    _write_i00(path / "in_data" / "i00_inp.dat")
    _write_series(path / "in_data" / "i01_org_ser.dat", data)
    if para == "full":
        shutil.copytree(bundled_para_dir(), path / "para")
    elif para != "none":
        (path / "para").mkdir()
        for name in para:
            shutil.copy(bundled_para_dir() + "/" + name, path / "para" / name)
    return path


def read_outputs(wd):
    return {f: _read_series(wd / "out_data" / f) for f in OUT_FILES}


# ---------------------------------------------------------------------------
# working-directory mode (task A)

def test_workdir_mode_with_para_unchanged(tmp_path, capsys):
    data = synth(420, 7)
    wd = make_workdir(tmp_path / "wd", data)
    assert main([str(wd)]) == 0
    from seasadj import decompose
    r = decompose(data, 7)
    got = read_outputs(wd)
    assert got["o16__S2.dat"] == r.seasonal
    assert got["o18_TC3.dat"] == r.trend


def test_workdir_mode_without_para_falls_back_to_bundled(tmp_path):
    """Reproduces H4: a pip user's work directory has no para/."""
    data = synth(420, 7)
    with_para = make_workdir(tmp_path / "a", data)
    no_para = make_workdir(tmp_path / "b", data, para="none")
    assert main([str(with_para)]) == 0
    assert main([str(no_para)]) == 0
    assert not (no_para / "para").exists()
    assert read_outputs(no_para) == read_outputs(with_para)


def test_workdir_fallback_is_per_file(tmp_path):
    """Only some weight files present locally: the rest come from the package."""
    data = synth(420, 7)
    full = make_workdir(tmp_path / "a", data)
    partial = make_workdir(tmp_path / "b", data,
                           para=["3x3_mov_ave.dat", "13_henderson.dat"])
    assert main([str(full)]) == 0
    assert main([str(partial)]) == 0
    assert read_outputs(partial) == read_outputs(full)


def test_workdir_local_para_takes_precedence(tmp_path):
    """A locally edited weight file is used, not silently replaced by the
    bundled copy (Fortran-compatible behaviour)."""
    data = synth(420, 7)
    base = make_workdir(tmp_path / "a", data)
    edited = make_workdir(tmp_path / "b", data)
    f = edited / "para" / "3x3_mov_ave.dat"
    toks = f.read_text().split()
    f.write_text(f.read_text().replace(toks[0], repr(float(toks[0]) * 1.01), 1))
    assert main([str(base)]) == 0
    assert main([str(edited)]) == 0
    assert read_outputs(base) != read_outputs(edited)


def test_workdir_missing_input_is_a_clean_error(tmp_path, capsys):
    wd = tmp_path / "empty"
    wd.mkdir()
    assert main([str(wd)]) == 1
    out = capsys.readouterr().out
    assert "in_data" in out and "i00_inp.dat" in out
    assert "Traceback" not in out


def test_workdir_missing_weight_everywhere_is_a_clean_error(tmp_path, capsys,
                                                            monkeypatch):
    wd = make_workdir(tmp_path / "wd", synth(420, 7), para="none")
    empty = tmp_path / "nopara"
    empty.mkdir()
    monkeypatch.setattr(var, "bundled_para_dir", lambda: str(empty))
    assert main([str(wd)]) == 1
    out = capsys.readouterr().out
    assert "weight file not found" in out and "Traceback" not in out


# ---------------------------------------------------------------------------
# CSV mode (task B)

import csv

from seasadj import decompose
from seasadj.cli import build_output_rows, read_csv_series
from seasadj.reg import SeasadjError


def write_csv(path, values, header="cases", dates=True, extra=False):
    """CSV with optional header, date column and an extra (ignored) column
    placed between the date and the value column."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if header:
            w.writerow((["date"] if dates else [])
                       + (["other"] if extra else []) + [header])
        for i, v in enumerate(values):
            w.writerow(([f"d{i}"] if dates else [])
                       + (["9"] if extra else []) + [repr(v)])
    return path


def read_out(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def test_csv_mode_matches_decompose_exactly(tmp_path):
    data = synth(420, 7)
    src = write_csv(tmp_path / "data.csv", data)
    assert main([str(src), "--period", "7"]) == 0
    header, rows = read_out(tmp_path / "data_seasadj.csv")  # default output
    assert header == ["date", "observed", "prior_adjusted", "trend",
                      "seasonal", "irregular", "adjusted"]
    r = decompose(data, 7)
    assert len(rows) == len(data)
    for name in header[1:]:
        col = [float(row[header.index(name)]) for row in rows]
        assert col == getattr(r, name)  # exact, including the str round trip
    assert [row[0] for row in rows] == [f"d{i}" for i in range(len(data))]


def test_csv_summary_goes_to_stderr_and_quiet_suppresses(tmp_path, capsys):
    src = write_csv(tmp_path / "data.csv", synth(420, 7))
    main([str(src), "--period", "7"])
    cap = capsys.readouterr()
    assert cap.out == ""
    assert "period     : 7" in cap.err and "Henderson" in cap.err
    main([str(src), "--period", "7", "--quiet"])
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err == ""


def test_csv_output_to_stdout(tmp_path, capsys):
    src = write_csv(tmp_path / "data.csv", synth(420, 7))
    assert main([str(src), "--period", "7", "-o", "-", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("date,observed")
    assert not (tmp_path / "data_seasadj.csv").exists()


@pytest.mark.parametrize("variant", [
    "default", "by_name", "by_index", "no_header", "no_date",
])
def test_csv_layout_variants_give_same_numbers(tmp_path, variant):
    data = synth(420, 7)
    out = tmp_path / "o.csv"
    args = ["--period", "7", "-o", str(out), "--quiet"]
    if variant == "default":
        src = write_csv(tmp_path / "a.csv", data)
    elif variant == "by_name":
        src = write_csv(tmp_path / "a.csv", data, extra=True)
        args += ["--column", "cases"]
    elif variant == "by_index":
        src = write_csv(tmp_path / "a.csv", data, extra=True)
        args += ["--column", "2", "--date-column", "0"]
    elif variant == "no_header":
        src = write_csv(tmp_path / "a.csv", data, header=None)
        args += ["--no-header"]
    else:
        src = write_csv(tmp_path / "a.csv", data, dates=False)
    assert main([str(src)] + args) == 0
    header, rows = read_out(out)
    has_date = variant != "no_date"
    assert (header[0] == "date") == has_date
    seasonal = [float(r[header.index("seasonal")]) for r in rows]
    assert seasonal == decompose(data, 7).seasonal


def test_csv_blank_lines_and_bom_are_tolerated(tmp_path):
    data = synth(420, 7)
    src = tmp_path / "a.csv"
    src.write_text("﻿cases\n\n" + "\n".join(repr(v) for v in data)
                   + "\n\n", encoding="utf-8")
    values, labels, _ = read_csv_series(src)
    assert values == data and labels is None


def test_csv_options_are_passed_through(tmp_path):
    data = synth(420, 12)
    src = write_csv(tmp_path / "a.csv", data, dates=False)
    out = tmp_path / "o.csv"
    assert main([str(src), "--period", "12", "--model", "additive",
                 "--seasonal-ma", "5", "--sigma", "1.2", "2.8",
                 "--no-replace-extreme", "--first-position", "3",
                 "-o", str(out), "--quiet"]) == 0
    r = decompose(data, 12, model="additive", seasonal_ma=5, sigma=(1.2, 2.8),
                  replace_extreme=False, first_position=3)
    header, rows = read_out(out)
    assert [float(x[header.index("trend")]) for x in rows] == r.trend


def test_date_column_is_only_a_label(tmp_path):
    """Dates are never interpreted: nonsense labels give identical numbers."""
    data = synth(420, 7)
    a = write_csv(tmp_path / "a.csv", data)
    lines = a.read_text().splitlines()
    b = tmp_path / "b.csv"
    b.write_text("\n".join(
        [lines[0]] + [f"zzz{i}," + ln.split(",")[1]
                      for i, ln in enumerate(lines[1:])]) + "\n")
    main([str(a), "--period", "7", "-o", str(tmp_path / "oa.csv"), "--quiet"])
    main([str(b), "--period", "7", "-o", str(tmp_path / "ob.csv"), "--quiet"])
    assert [r[1:] for r in read_out(tmp_path / "oa.csv")[1]] == \
           [r[1:] for r in read_out(tmp_path / "ob.csv")[1]]


def test_output_rows_do_not_drop_forecast_period():
    """observed is shorter than the other series when there is a forecast."""
    data = synth(420, 7)
    r = decompose(data, 7, forecast=synth(14, 7))
    assert len(r.observed) < len(r.trend)
    header, rows = build_output_rows(r, None)
    assert len(rows) == len(r.trend)
    assert rows[-1][0] == ""  # no observed value for the forecast period
    assert rows[-1][2] != ""


def test_output_length_mismatch_is_an_error():
    r = decompose(synth(420, 7), 7)
    r.seasonal = r.seasonal[:-1]
    with pytest.raises(SeasadjError):
        build_output_rows(r, None)


def _fails_cleanly(argv, capsys, *needles):
    assert main(argv) == 1
    cap = capsys.readouterr()
    assert "Traceback" not in cap.err + cap.out
    for n in needles:
        assert n in cap.err


def test_csv_error_missing_period(tmp_path, capsys):
    src = write_csv(tmp_path / "a.csv", synth(420, 7))
    _fails_cleanly([str(src)], capsys, "--period")


def test_csv_error_missing_file(tmp_path, capsys):
    _fails_cleanly([str(tmp_path / "nope.csv"), "--period", "7"], capsys,
                   "not found")


def test_csv_error_unknown_column(tmp_path, capsys):
    src = write_csv(tmp_path / "a.csv", synth(420, 7))
    _fails_cleanly([str(src), "--period", "7", "--column", "zzz"], capsys,
                   "no such column")
    _fails_cleanly([str(src), "--period", "7", "--column", "9"], capsys,
                   "out of range")


def test_csv_error_non_numeric_cell_reports_row_and_value(tmp_path, capsys):
    data = [repr(v) for v in synth(420, 7)]
    data[41] = "n/a"
    src = tmp_path / "a.csv"
    src.write_text("cases\n" + "\n".join(data) + "\n")
    # data item 41 (0-based) sits on file row 43 (header row + 1-based)
    _fails_cleanly([str(src), "--period", "7"], capsys, "row 43", "'n/a'")


def test_csv_error_refuses_to_overwrite_input(tmp_path, capsys):
    src = write_csv(tmp_path / "a.csv", synth(420, 7))
    _fails_cleanly([str(src), "--period", "7", "-o", str(src)], capsys,
                   "overwrite")


def test_csv_decompose_validation_errors_pass_through(tmp_path, capsys):
    src = write_csv(tmp_path / "a.csv", synth(10, 7))  # too short
    assert main([str(src), "--period", "7"]) == 1
    assert capsys.readouterr().err.startswith("seasadj: error:")


def test_csv_options_rejected_for_directory(tmp_path):
    wd = make_workdir(tmp_path / "wd", synth(420, 7))
    with pytest.raises(SystemExit) as e:
        main([str(wd), "--period", "7"])
    assert e.value.code == 2


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert capsys.readouterr().out.startswith("seasadj ")
