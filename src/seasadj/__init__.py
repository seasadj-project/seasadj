"""seasadj — X-11 style seasonal adjustment for an arbitrary cycle length.

Python port of the Fortran90 program Ver16_00 (2026-07-04).
"""

from .api import Decomposition, decompose
from .main import run
from .reg import AbortRun, SeasadjError

__version__ = "0.1.0"

__all__ = ["run", "decompose", "Decomposition", "SeasadjError", "AbortRun",
           "__version__"]
