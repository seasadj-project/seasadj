"""CLI: python -m seasadj [PATH] / seasadj [PATH]

PATH is a CSV file (CSV mode: needs --period) or a working directory holding
in_data/ (file mode, the same layout as the Fortran executable; para/ is
optional). Without PATH the current directory is used as the working
directory. Run with --help for the options. See cli.py.
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
