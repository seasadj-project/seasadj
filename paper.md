---
title: 'seasadj: X-11 style seasonal adjustment for arbitrary cycle lengths'
tags:
  - Python
  - seasonal-adjustment
  - time-series
  - decomposition
  - X-11
  - trend
  - seasonality
authors:
  - name: Tetsuma ARITA
    orcid: 0000-0003-1335-4572
    affiliation: 1
affiliations:
  - name: Bank of Japan, Japan
    index: 1
date: TODO(user) # fill in at submission time, e.g. 25 July 2026
bibliography: paper.bib
---

# Summary

Seasonal adjustment removes recurring within-cycle patterns from a time
series so that the underlying trend and genuinely new movements can be
seen. The X-11 method [@Shiskin1967; @Dagum1988], which forms the core of
the U.S. Census Bureau's X-13ARIMA-SEATS [@X13Manual], decomposes a series
into trend-cycle, seasonal, and irregular components through iterated
moving averages, with data-driven selection of the seasonal and trend
filters and replacement of extreme values. `seasadj` implements the X-11
procedure generalized to an arbitrary seasonal period: period 7 for the
day-of-week cycle of daily data, period 24 for the daily cycle of hourly
data, or any other cycle length. It is designed to work together with
X-13ARIMA-SEATS rather than replace it: the pre-adjustment steps that do
not depend on the period — estimation of holiday, outlier, and level-shift
effects and forecast extension via RegARIMA — are left to X-13ARIMA-SEATS,
while the period-bound X-11 core is reimplemented here for any period.

`seasadj` provides multiplicative, additive, and log-additive
decomposition modes; the log-additive mode includes the trend bias
correction of @ThomsonOzaki2002. The generalized X-11 core covers
automatic seasonal filter selection (3x3, 3x5, or 3x9) by the moving
seasonality ratio, automatic selection of the Henderson trend filter
length, and X-11 extreme-value replacement of seasonal-irregular (SI)
ratios [@JDemetraX11]. The package is pure Python with no third-party
dependencies and offers two interfaces: a `decompose()` function that
returns all components together with diagnostics, and a file-based
command-line mode compatible with the original Fortran research
implementation.

# Statement of need

The standard production tools for seasonal adjustment are built around
monthly and quarterly data. Yet series observed at higher frequencies are
increasingly common in official statistics, epidemiology, and business
monitoring, and they carry seasonality at other periods — most typically a
day-of-week cycle in daily data. The COVID-19 pandemic made this need
concrete: daily case counts in many countries showed strong day-of-week
reporting patterns that had to be removed before the epidemic's momentum
could be assessed, which is precisely the analysis in @Arita2022 using the
method implemented in this package.

The intended users are analysts of official statistics, epidemiological
surveillance series, and operational business time series who already
work with X-13ARIMA-SEATS or JDemetra+ and need the same style of
adjustment at other frequencies, as well as researchers who want a
dependency-free, scriptable X-11 building block. For these users,
methodological continuity matters: moving from monthly to daily data
should not force a switch to a different decomposition philosophy with
different filters, diagnostics, and interpretation.

# State of the field

Production-grade X-11 implementations are bound to monthly and quarterly
data: the X-11 core of X-13ARIMA-SEATS [@X13Manual] accepts only periods
12 and 4, wrappers such as the R package `seasonal` [@SaxEddelbuettel2018]
inherit that restriction, and JDemetra+, the tool recommended for official
statistics in the European Statistical System, likewise targets monthly
and quarterly series [@JDemetraX11]. Open tools that do accept an
arbitrary period cover adjacent needs: STL [@Cleveland1990] and its
multi-seasonal extension MSTL, as implemented in `statsmodels`, are
loess-based smoothers and do not provide the X-11 framework —
moving-seasonality-ratio based automatic filter selection, extreme
SI-ratio replacement, and Henderson trend filters — on which
long-standing official-statistics practice and its diagnostics are built.
The R package `dsa` [@Ollech2021] targets daily data specifically, but it
approaches the problem by combining STL with regression models rather
than by generalizing X-11 itself. To the author's knowledge, no other
publicly installable implementation of the X-11 methodology for arbitrary
periods exists; providing one is the purpose of `seasadj`.

# Software design

The package reimplements only what is period-bound. The pre-adjustment
stage of X-13ARIMA-SEATS — RegARIMA estimation of holiday, outlier, and
level-shift effects and forecast extension — does not depend on the
seasonal period, so `seasadj` deliberately leaves it to X-13ARIMA-SEATS
and accepts its output as prior-adjustment factors. This keeps the
package small and lets institutions retain their existing pre-treatment
workflow while replacing only the decomposition core.

Within the core, the seasonal period is a parameter rather than a set of
built-in constants. All filters are generated from closed-form
expressions — Henderson weights of any length, the seasonal moving
averages, and the $(2p-1)$-term triangular filter used in the trend bias
correction of @ThomsonOzaki2002 — so the fixed filter tables of
X-13ARIMA-SEATS arise as special cases at periods 12 and 4.

`seasadj` is pure Python with no third-party dependencies. In
official-statistics settings this keeps the code auditable end to end and
installation friction-free; performance is not a limiting factor because
the X-11 procedure consists of moving averages whose cost is essentially
linear in the series length.

Two interfaces expose the same engine: the `decompose()` API, which
returns all components together with diagnostics, and a file-based mode
whose input and output formats are compatible with the author's Fortran
research implementation. The file mode is also the package's verification
harness: it allows the Python implementation to be run on inputs
identical to those of the Fortran reference, and a frozen suite of golden
tests spanning all three decomposition modes, even and odd periods,
extreme-value replacement on and off, and holiday regression matches the
reference bit for bit. Because the golden datasets are not
redistributable, those tests skip automatically when the data are absent;
the distributed test suite instead checks the decomposition identity and
the equivalence of the API and file modes on artificial data, and runs in
continuous integration on Linux and Windows across supported Python
versions.

# Research impact statement

The method implemented in `seasadj` was developed for, and used in,
published research: @Arita2022 applied it to daily COVID-19 case counts
from seven countries to separate day-of-week reporting patterns from the
underlying course of the epidemic. Until now the method existed only as
an unpublished Fortran research program, so that analysis could not be
reproduced or extended without access to the author's environment;
`seasadj` makes the method installable by anyone. A follow-up methods
paper covering the extensions implemented in this package — extreme
SI-ratio replacement generalized to arbitrary periods, additive and
log-additive decomposition modes, and trend bias correction after log
transformation — is in preparation for the Statistical Journal of the
IAOS [TODO(update at submission): reflect the actual status — e.g.
"under review" or a citation if accepted], with all of its computations
performed with `seasadj`.

# AI usage disclosure

`seasadj` was developed with substantial assistance from AI coding
agents (Claude Code, Anthropic). Under the author's direction and
review, AI assistance was used to port the author's Fortran reference
implementation to Python, to write tests and documentation, and to
draft this paper. The underlying method, the Fortran reference
implementation, and all methodological and design decisions are the
author's own work [@Arita2022]. Correctness of the AI-assisted port
does not rest on code review alone: the Python implementation is
verified bit for bit against the human-written Fortran reference on the
frozen golden-test suite described above, and the public test suite
runs in continuous integration. All repository commits were reviewed
and made by the author.

# Acknowledgements

TODO(user): optional — add acknowledgements here, or delete this section
before submission.

# References
