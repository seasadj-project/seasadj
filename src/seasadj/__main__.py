"""CLI: python -m seasadj [workdir] / seasadj [workdir]

The working directory must hold in_data/ and para/ (same layout as the
Fortran executable expects); out_data/ is created if missing.
"""

import sys

from .main import run
from .reg import SeasadjError


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    workdir = args[0] if args else "."
    try:
        run(workdir)
    except SeasadjError:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
