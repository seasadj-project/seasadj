"""Fortran semantics helpers.

The port keeps the Fortran 1-based indexing (arrays have length max_t + 1
with index 0 unused) and must reproduce Fortran integer arithmetic exactly:
Fortran integer division truncates toward zero while Python's ``//`` floors,
and Fortran ``mod`` takes the sign of the dividend while Python's ``%`` takes
the sign of the divisor. Ported code always uses ``idiv``/``imod`` instead of
``//``/``%``.
"""


def idiv(a: int, b: int) -> int:
    """Fortran integer division: truncation toward zero."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def imod(a: int, b: int) -> int:
    """Fortran mod(a, b): result has the sign of the dividend a."""
    return a - idiv(a, b) * b


def alloc(n: int, val: float = 0.0) -> list:
    """1-based array of n elements (index 0 unused)."""
    return [val] * (n + 1)


def ialloc(n: int, val: int = 0) -> list:
    """1-based integer array of n elements (index 0 unused)."""
    return [val] * (n + 1)


def read_matrix(filename, rows: int, cols: int) -> list:
    """Read a rows x cols weight table as a 1-based matrix (m[i][j]).

    Mirrors the Fortran sequence of list-directed reads
    ``read(unit,*) (w(i,j), j=1,cols)``: the para/ files hold exactly
    ``cols`` values per record, so a flat fill is equivalent.
    """
    vals = []
    with open(filename, "r", encoding="ascii") as f:
        for line in f:
            vals.extend(float(tok) for tok in line.split())
    if len(vals) < rows * cols:
        raise ValueError(f"not enough values in {filename}")
    m = [[0.0] * (cols + 1) for _ in range(rows + 1)]
    k = 0
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            m[i][j] = vals[k]
            k += 1
    return m
