"""Extreme SI ratio replacement, X-11 extreme value replacement
(port of 08_rep.f90 / rep_mod).

1) estimate a preliminary seasonal factor by a 3x(pwm_term) weighted
   moving average of the SI ratios and normalize it by a centered
   term-moving average
2) compute a moving standard deviation of the preliminary irregular
   over 5-cycle windows (each window is assigned to its central cycle;
   the first/last two cycles use the nearest window), and recompute it
   once after excluding the values beyond sig_u standard deviations
3) assign a weight to each SI ratio : 1 within sig_l standard deviations,
   0 beyond sig_u standard deviations, linearly graduated between them
4) replace each SI ratio with weight < 1 by the weighted average of the
   ratio itself (with its weight) and the nearest full-weight ratios of
   the same cycle position (2 preceding and 2 following ones; when one
   side has fewer than 2, the missing ones are taken from the other side)
"""

import math

from .ftn import alloc, idiv, imod
from .wma import wm_ave


def rep_ext(max_t, term, ft_x, fn_x, x, rep_si, sig_l, sig_u, pwm_term, model,
            wm3_w, wm5_w, wm9_w, w, xr):
    """Replace extreme SI ratios. w and xr written in place.

    Returns (w_n, xr_n, cnt_rep, cnt_checked, printed) where printed tells
    whether the Fortran writes the "SI replaced" line (it returns before the
    print when rep_si = 0 or the series is too short).
    """
    # initialize : weights are 1 and SI ratios are unchanged
    for i in range(1, max_t + 1):
        w[i] = 1.0
        xr[i] = 0.0

    for i in range(1, fn_x + 1):
        xr[i] = x[i]

    w_n = fn_x
    xr_n = fn_x

    # case of the replacement is not used
    if rep_si == 0:
        return (w_n, xr_n, 0, 0, False)

    # case of the series is too short to estimate the preliminary seasonal factor
    # (prevented beforehand by check_inputs; defensive guard)
    if fn_x - ft_x + 1 < term * (pwm_term + 2):
        return (w_n, xr_n, 0, 0, False)

    ps = alloc(max_t)      # preliminary seasonal factor
    ma_ps = alloc(max_t)   # centered term-moving average of ps (for normalization)
    irr = alloc(max_t)     # preliminary irregular
    sig = alloc(max_t)     # moving standard deviation assigned to each cycle
    bck = alloc(4)         # nearest full-weight SI ratios backward
    fwd = alloc(4)         # nearest full-weight SI ratios forward

    # -----------------------------------
    # 1) preliminary seasonal factor and preliminary irregular

    # estimate the preliminary seasonal factor
    wm_ave(max_t, term, ft_x, fn_x, x, pwm_term, ps, wm3_w, wm5_w, wm9_w)

    # initialize ma_ps
    for i in range(ft_x, fn_x + 1):
        ma_ps[i] = 0.0

    # centered term-moving average of ps (same convention as std_sf)
    if imod(term, 2) == 1:
        half = idiv(term - 1, 2)
        for i in range(ft_x + half, fn_x - half + 1):
            for j in range(-half, half + 1):
                ma_ps[i] = ps[i + j] + ma_ps[i]
            ma_ps[i] = ma_ps[i] / float(term)
    else:
        half = idiv(term, 2)
        for i in range(ft_x + half, fn_x - half + 1):
            for j in range(-half, half + 1):
                if abs(j) == half:  # case of edge
                    ma_ps[i] = ps[i + j] + ma_ps[i]
                else:
                    ma_ps[i] = 2 * ps[i + j] + ma_ps[i]
            ma_ps[i] = ma_ps[i] / float(term * 2)

    # edge periods : average of the first / last term values
    for i in range(ft_x, ft_x + half - 1 + 1):
        for j in range(ft_x, ft_x + term - 1 + 1):
            ma_ps[i] = ps[j] + ma_ps[i]
        ma_ps[i] = ma_ps[i] / float(term)

    for i in range(fn_x - half + 1, fn_x + 1):
        for j in range(fn_x - term + 1, fn_x + 1):
            ma_ps[i] = ps[j] + ma_ps[i]
        ma_ps[i] = ma_ps[i] / float(term)

    # estimate the preliminary irregular
    # (the deviation of irr is measured from cen : 1 in the multiplicative
    #  model since irr is a ratio, 0 in the additive model since irr is a
    #  difference)
    if model == 0:
        cen = 1.0
        for i in range(ft_x, fn_x + 1):
            irr[i] = x[i] * ma_ps[i] / ps[i]
    else:
        cen = 0.0
        for i in range(ft_x, fn_x + 1):
            irr[i] = x[i] - (ps[i] - ma_ps[i])

    # -----------------------------------
    # 2) moving standard deviation of the preliminary irregular per cycle

    n_c = idiv(fn_x - ft_x, term) + 1

    for c in range(1, n_c + 1):

        # determine the 5-cycle window assigned to cycle c
        if n_c < 5:
            wlo = 1
            whi = n_c
        else:
            cw = c
            if cw < 3:
                cw = 3
            if cw > n_c - 2:
                cw = n_c - 2
            wlo = cw - 2
            whi = cw + 2

        jlo = ft_x + (wlo - 1) * term
        jhi = ft_x + whi * term - 1
        if jhi > fn_x:
            jhi = fn_x

        # first pass : standard deviation of irr around cen
        ss = 0.0
        cnt = 0
        for j in range(jlo, jhi + 1):
            ss = (irr[j] - cen) ** 2 + ss
            cnt += 1
        sig1 = math.sqrt(ss / float(cnt))

        # second pass : recompute excluding the values beyond sig_u * sig1
        ss = 0.0
        cnt = 0
        for j in range(jlo, jhi + 1):
            if abs(irr[j] - cen) <= sig_u * sig1:
                ss = (irr[j] - cen) ** 2 + ss
                cnt += 1

        if cnt > 0:
            sig[c] = math.sqrt(ss / float(cnt))
        else:
            sig[c] = sig1

    # -----------------------------------
    # 3) assign a weight to each SI ratio

    for i in range(ft_x, fn_x + 1):
        c = idiv(i - ft_x, term) + 1
        dev = abs(irr[i] - cen)

        if sig[c] <= 0:
            w[i] = 1.0
        elif dev <= sig_l * sig[c]:
            w[i] = 1.0
        elif dev >= sig_u * sig[c]:
            w[i] = 0.0
        else:
            w[i] = (sig_u * sig[c] - dev) / ((sig_u - sig_l) * sig[c])

    # -----------------------------------
    # 4) replace the SI ratios with weight < 1

    cnt_rep = 0

    for i in range(ft_x, fn_x + 1):
        if w[i] >= 1.0:
            continue

        # collect the nearest full-weight SI ratios of the same cycle position
        n_bck = 0
        j = i - term
        while j >= ft_x and n_bck < 4:
            if w[j] >= 1.0:
                n_bck += 1
                bck[n_bck] = x[j]
            j -= term

        n_fwd = 0
        j = i + term
        while j <= fn_x and n_fwd < 4:
            if w[j] >= 1.0:
                n_fwd += 1
                fwd[n_fwd] = x[j]
            j += term

        # use 2 ratios of each side; borrow from the other side when short
        use_b = min(n_bck, 2)
        use_f = min(n_fwd, 2)
        short = 4 - use_b - use_f
        if short > 0:
            use_f = use_f + min(n_fwd - use_f, short)
            short = 4 - use_b - use_f
        if short > 0:
            use_b = use_b + min(n_bck - use_b, short)

        # replace the SI ratio by the weighted average
        if use_b + use_f > 0:
            rep_sum = 0.0
            for j in range(1, use_b + 1):
                rep_sum = bck[j] + rep_sum
            for j in range(1, use_f + 1):
                rep_sum = fwd[j] + rep_sum
            xr[i] = (w[i] * x[i] + rep_sum) / (w[i] + float(use_b + use_f))
            cnt_rep += 1

    cnt_checked = fn_x - ft_x + 1
    print(f"{'SI replaced =':>14s}{cnt_rep:5d}{'SI checked =':>21s}{cnt_checked:5d}")

    return (w_n, xr_n, cnt_rep, cnt_checked, True)
