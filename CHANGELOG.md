# Changelog

## 1.0.0 - 2026-07-06

First public release on PyPI. Numerical behavior is unchanged from 0.1.0
(bit-identical to Fortran90 Ver16_00); this release reflects documentation
and metadata updates from the pre-publication review only.

- Pre-publication documentation review (README updates).
- No changes to `src/seasadj/`.

## 0.1.0 - 2026-07-05

Initial release. Python port of the Fortran90 `seasonal_adj` program
(Ver16_00): X-11 style seasonal decomposition generalized to an arbitrary
cycle length, with multiplicative, additive and log-additive modes, X-11
extreme SI-ratio replacement, and the Thomson & Ozaki (2002) trend bias
correction for the log model.

- `decompose()` / `Decomposition`: the Pythonic, in-memory API.
- `run()` / `seasadj` CLI: the Fortran-compatible, file-based mode
  (`in_data/` + `para/` in, `out_data/` out).
