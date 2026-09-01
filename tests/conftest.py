import sys
from pathlib import Path

# make src/seasadj importable without installation
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# repository root (holds 01_プログラム/ and 04_検証データ/)
REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO_ROOT / "04_検証データ"
PARA_DIR = REPO_ROOT / "01_プログラム" / "para"


# ---------------------------------------------------------------------------
# i00_inp.dat / series file helpers, shared by test_api.py, test_periods.py
# and test_boundaries.py (moved here from test_api.py so the new test files
# do not need to duplicate them; test_api.py's own tests are unchanged).

def _write_i00(path, *, ini_o_day=1, forecasting=0, reg_hol=0, hol_reg_p=0.0,
               reg_ao=0, reg_ls=0, term=7, iwm_term=3, ft_o=1, rep_si=1,
               sig_l=1.5, sig_u=2.5, model=0):
    """Write i00_inp.dat in the format read_para expects: 2 header lines,
    then 13 blocks of (2 comment lines + 1 value line)."""
    values = [ini_o_day, forecasting, reg_hol, hol_reg_p, reg_ao, reg_ls,
              term, iwm_term, ft_o, rep_si, sig_l, sig_u, model]
    lines = ["-" * 60, "Please set following 13 parameters"]
    for letter, value in zip("ABCDEFGHIJKLM", values):
        lines.append("-" * 60)
        lines.append(f"{letter}. parameter")
        lines.append(repr(value))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def _write_series(path, values):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for v in values:
            f.write(f"{v!r}\n")


def _read_series(path):
    vals = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            toks = line.split()
            if toks:
                vals.append(float(toks[0]))
    return vals
