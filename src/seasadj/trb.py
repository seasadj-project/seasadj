"""Trend bias correction of the log model and back-transform
(port of 09_trb.f90 / trb_mod)."""

import math

from .ftn import alloc


def hend_w(hw):
    """Symmetric henderson moving average weights of 2*hw+1 terms by the
    closed-form formula (Ladiray & Quenneville (2001), eq. 3.3):

      w(j) = 315 [(n-1)^2 - j^2] [n^2 - j^2] [(n+1)^2 - j^2] [3n^2 - 16 - 11j^2]
             / [ 8 n (n^2-1) (4n^2-1) (4n^2-9) (4n^2-25) ]      n = hw + 2

    Returns a list w of length 2*hw+1 where w[j + hw] is the Fortran w(j)
    for j = -hw..hw.
    """
    w = [0.0] * (2 * hw + 1)
    rn = float(hw + 2)

    for j in range(-hw, hw + 1):
        rj = float(j * j)
        w[j + hw] = (315.0 * ((rn - 1.0) ** 2 - rj) * (rn ** 2 - rj)
                     * ((rn + 1.0) ** 2 - rj) * (3.0 * rn ** 2 - 16.0 - 11.0 * rj)
                     / (8.0 * rn * (rn ** 2 - 1.0) * (4.0 * rn ** 2 - 1.0)
                        * (4.0 * rn ** 2 - 9.0) * (4.0 * rn ** 2 - 25.0)))
    return w


def trb_cor(max_t, term, max_on, S2_n, S2, I3_n, I3, TC3_n, TC3):
    """Thomson & Ozaki (2002) trend bias correction of the log model and
    back-transform of the final trend (same construction as trbias.f of
    X-13ARIMA-SEATS):

      sig   = exp( sum(I3_log^2) / (2 n) )  over the actual-data period
      hs(i) = smoothing of exp(S2_log) by the (2*term-1)-term henderson filter
      TC3   = exp(TC3_log) * sig * hs

    TC3 is updated in place (log domain in, original scale out).
    Returns sig.
    """
    # bias correction constant from the log-domain irregular
    n_act = min(max_on, I3_n)
    ss = 0.0
    for i in range(1, n_act + 1):
        ss = I3[i] ** 2 + ss
    sig = math.exp(ss / (2.0 * float(n_act)))

    # symmetric henderson weights of 2*term-1 terms
    hw = term - 1
    w = hend_w(hw)

    # seasonal factors back to the original scale before smoothing
    es2 = alloc(max_t)
    for i in range(1, S2_n + 1):
        es2[i] = math.exp(S2[i])

    # corrected trend ; at the series edges where the full window does not
    # fit, the weights are truncated and renormalized to sum 1 (the effect
    # is minor : hs is a level term near 1 and the correction itself is of
    # second order)
    for i in range(1, TC3_n + 1):
        hs = 0.0
        wsum = 0.0
        for j in range(-hw, hw + 1):
            if 1 <= i + j <= S2_n:
                hs = es2[i + j] * w[j + hw] + hs
                wsum = w[j + hw] + wsum
        hs = hs / wsum

        TC3[i] = math.exp(TC3[i]) * sig * hs

    print(f"{'trend bias corr : sig =':>28s}{sig:8.5f}")

    return sig


def exp_dat(max_t, num_x, x):
    """Transform a series back to the original scale (element-wise exp),
    in place."""
    for i in range(1, num_x + 1):
        x[i] = math.exp(x[i])
