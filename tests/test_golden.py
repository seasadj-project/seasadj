"""Golden tests: run the Python engine on the frozen inputs of
04_検証データ/G1〜G7 and compare every output with the Fortran Ver16_00
expected outputs.

Pass criteria:
  - numeric series             : |a - b| <= atol + rtol*|b|, rtol = atol = 1e-10
  - padding values (0 / -999)  : exact match (bit-level as parsed doubles)
  - weight files (o22/o24) 1.0 : exact match
  - o21_INT integer items      : exact match
  - o21_INT real items         : match within the printed f8.5 precision
  - console discrete decisions : exact match (SI replaced counts, h_term,
                                 swm_term, count)
  - o20_SUM                    : excluded from numeric comparison (existence
                                 and row count only)
"""

import re
import shutil

import pytest

from conftest import GOLDEN_DIR, PARA_DIR

if not GOLDEN_DIR.is_dir() or not PARA_DIR.is_dir():
    pytest.skip("golden data not available (private)", allow_module_level=True)

from seasadj import run

RTOL = 1e-10
ATOL = 1e-10

# outputs compared value-by-value with the tolerance rule
SERIES_FILES = [
    "o01_org.dat", "o07_adj.dat", "o08_TC1.dat", "o09_SI1.dat",
    "o10_S1p.dat", "o11__S1.dat", "o12__A1.dat", "o13_TC2.dat",
    "o14_SI2.dat", "o15_S2p.dat", "o16__S2.dat", "o17__A2.dat",
    "o18_TC3.dat", "o19__I3.dat", "o22_SI1w.dat", "o23_SI1r.dat",
    "o24_SI2w.dat", "o25_SI2r.dat",
]

# values requiring exact match when they appear in the expected output
PAD_VALUES = {0.0, -999.0}
WEIGHT_FILES = {"o22_SI1w.dat", "o24_SI2w.dat"}  # 1.0 must also match exactly


def golden_cases():
    if not GOLDEN_DIR.is_dir():
        return []
    return sorted(d.name for d in GOLDEN_DIR.iterdir()
                  if d.is_dir() and d.name.startswith("G"))


def read_series(path):
    """One value per line; tolerates CR and trailing blanks of Fortran output."""
    vals = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            toks = line.split()
            if toks:
                vals.append(float(toks[0].replace("d", "e").replace("D", "E")))
    return vals


def numeric_tokens(path):
    """Whitespace-delimited tokens that parse as numbers, in file order.

    Label fragments like 'additive=1)' are not whitespace-delimited numbers,
    so both the Fortran and the Python o21_INT yield the same token sequence.
    """
    toks = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            for tok in line.split():
                try:
                    toks.append(float(tok))
                except ValueError:
                    pass
    return toks


@pytest.fixture(params=golden_cases())
def case_dir(request, tmp_path):
    """Copy a golden case's in_data/ and the repo para/ into a tmp workdir."""
    src = GOLDEN_DIR / request.param
    wd = tmp_path / request.param
    wd.mkdir()
    shutil.copytree(src / "in_data", wd / "in_data")
    shutil.copytree(PARA_DIR, wd / "para")
    return (request.param, src, wd)


def test_golden(case_dir, capsys):
    name, src, wd = case_dir

    result = run(wd)
    console = capsys.readouterr().out

    expected_dir = src / "expected"

    # ---- numeric series files -------------------------------------------
    for fname in SERIES_FILES:
        exp = read_series(expected_dir / fname)
        act = read_series(wd / "out_data" / fname)
        assert len(act) == len(exp), f"{name}/{fname}: line count {len(act)} != {len(exp)}"
        for k, (a, b) in enumerate(zip(act, exp), start=1):
            if b in PAD_VALUES or (fname in WEIGHT_FILES and b == 1.0):
                assert a == b, f"{name}/{fname} line {k}: pad {a!r} != {b!r}"
            else:
                assert abs(a - b) <= ATOL + RTOL * abs(b), \
                    f"{name}/{fname} line {k}: {a!r} != {b!r} (diff {abs(a - b):.3e})"

    # ---- o20_SUM: existence and row count only --------------------------
    with open(expected_dir / "o20_SUM.dat", "r", encoding="utf-8", errors="replace") as f:
        exp_rows = sum(1 for _ in f)
    with open(wd / "out_data" / "o20_SUM.dat", "r", encoding="utf-8", errors="replace") as f:
        act_rows = sum(1 for _ in f)
    assert act_rows == exp_rows, f"{name}/o20_SUM.dat: row count {act_rows} != {exp_rows}"

    # ---- o21_INT: integers exact, reals within printed precision --------
    exp_toks = numeric_tokens(expected_dir / "o21_INT.dat")
    act_toks = numeric_tokens(wd / "out_data" / "o21_INT.dat")
    assert len(act_toks) == len(exp_toks), \
        f"{name}/o21_INT.dat: token count {len(act_toks)} != {len(exp_toks)}"
    for k, (a, b) in enumerate(zip(act_toks, exp_toks), start=1):
        if b == int(b) and a == int(a):
            assert a == b, f"{name}/o21_INT.dat token {k}: {a} != {b}"
        else:
            assert abs(a - b) <= 1.5e-5, f"{name}/o21_INT.dat token {k}: {a} != {b}"

    # ---- console discrete decisions vs frozen console.log ---------------
    exp_console = (src / "console.log").read_text(encoding="utf-8", errors="replace")

    exp_rep = [(int(m.group(1)), int(m.group(2))) for m in
               re.finditer(r"SI replaced =\s*(\d+)\s*SI checked =\s*(\d+)", exp_console)]
    act_rep = result["si_replaced"]
    assert act_rep == exp_rep, f"{name}: SI replaced {act_rep} != {exp_rep}"

    exp_h = [int(m.group(1)) for m in re.finditer(r"h_term =\s*(\d+)", exp_console)]
    assert result["h_terms"] == exp_h, f"{name}: h_term {result['h_terms']} != {exp_h}"

    m = re.search(r"swm_term =\s*(\d+)", exp_console)
    assert result["swm_term"] == int(m.group(1)), \
        f"{name}: swm_term {result['swm_term']} != {m.group(1)}"

    m = re.search(r"count\s+=\s*(\d+)", exp_console)
    assert result["msr_count"] == int(m.group(1)), \
        f"{name}: count {result['msr_count']} != {m.group(1)}"

    m = re.search(r"trend bias corr : sig =\s*([\d.]+)", exp_console)
    if m:
        assert abs(result["bias_sig"] - float(m.group(1))) <= 1.5e-5, \
            f"{name}: bias sig {result['bias_sig']} != {m.group(1)}"
    else:
        assert result["params"]["model"] != 2

    # the Python console must contain the same discrete lines (smoke check)
    assert len(re.findall(r"h_term =\s*\d+", console)) == 2
