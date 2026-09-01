# Changelog

## Unreleased

- Fixed: the bibliographic record for Arita (2022) in `paper.bib` gave the
  wrong page range (353-361); the correct range is 363-383. The Citation
  section of both READMEs now carries volume, issue and pages as well.
- Docs: removed the placeholder `TODO` markers from `paper.md`, and the
  outdated statement that a follow-up methods paper is in preparation for
  the Statistical Journal of the IAOS.

No changes to `src/seasadj/`.

## 1.0.1 - 2026-08-06

- Fixed: `seasadj.__version__` reported `0.1.0` instead of the released
  version.
- Added: `examples/` with a reproduction of the Arita (2022) daily
  COVID-19 seasonal adjustment analysis on public JHU CSSE data
  (documentation only; not part of the installed package).
- Docs: README (English and Japanese) and docstring improvements,
  including removal of an outdated "in preparation" citation note.

No changes to numerical behavior — `src/seasadj/` differs from 1.0.0 only
in docstrings, comments, and the `__version__` string; still bit-identical
to Fortran90 Ver16_00.

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
