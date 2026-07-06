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
monthly and quarterly data. The X-11 core of X-13ARIMA-SEATS accepts only
periods 12 and 4, and JDemetra+, the tool recommended for official
statistics in the European Statistical System, likewise targets monthly
and quarterly series. Yet series observed at higher frequencies are
increasingly common in official statistics, epidemiology, and business
monitoring, and they carry seasonality at other periods — most typically a
day-of-week cycle in daily data. The COVID-19 pandemic made this need
concrete: daily case counts in many countries showed strong day-of-week
reporting patterns that had to be removed before the epidemic's momentum
could be assessed, which is precisely the analysis in @Arita2022 using the
method implemented in this package.

Existing open tools cover adjacent needs but not this one. STL
[@Cleveland1990] and its multi-seasonal extension MSTL, as implemented in
`statsmodels`, accept an arbitrary period, but they are loess-based
smoothers and do not provide the X-11 framework — moving-seasonality-ratio
based automatic filter selection, extreme SI-ratio replacement, and
Henderson trend filters — on which long-standing official-statistics
practice and its diagnostics are built. The R package `dsa` [@Ollech2021]
targets daily data specifically, but it approaches the problem by
combining STL with regression models rather than by generalizing X-11
itself. To the author's knowledge, no other publicly installable
implementation of the X-11 methodology for arbitrary periods exists;
providing one is the purpose of `seasadj`. This matters for practitioners
who need methodological continuity with X-11-based practice — the same
filter logic, the same diagnostics, the same interpretation — when their
data move from monthly to daily or hourly frequency.

The intended users are analysts of official statistics, epidemiological
surveillance series, and operational business time series who already
work with X-13ARIMA-SEATS or JDemetra+ and need the same style of
adjustment at other frequencies, as well as researchers who want a
dependency-free, scriptable X-11 building block.

`seasadj` is the first openly available, installable implementation of
the method used in @Arita2022, which until now existed only as an
unpublished Fortran research program. Reliability rests on that lineage:
the Python implementation is verified against the Fortran reference
implementation on a frozen suite of golden tests spanning all three
decomposition modes, even and odd periods, extreme-value replacement on
and off, and holiday regression, with all numeric outputs matching
bit-for-bit. The distributed test suite additionally checks the
decomposition identity and the equivalence of the API and file modes on
artificial data, and runs in continuous integration on Linux and Windows
across supported Python versions.

# Acknowledgements

TODO(user): optional — add acknowledgements here, or delete this section
before submission.

# References
