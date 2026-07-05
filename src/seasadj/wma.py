"""Seasonal weighted moving average (port of 04_wma.f90 / wma_mod)."""

from .ftn import idiv, imod, read_matrix


def wm_ave(max_t, term, ft_x, fn_x, x, wm_term, wm_x, wm3_w, wm5_w, wm9_w):
    """3x(wm_term) seasonal weighted moving average of x[ft_x..fn_x].

    wm_x is written in place (the whole array is zeroed first, as in the
    Fortran). Returns wm_xn.
    """
    # initialize of wm_x and wm_xn
    for i in range(1, max_t + 1):
        wm_x[i] = 0.0

    wm_xn = 0

    # read the file of 3x(wm_term) weighted moving average weights
    if wm_term == 3:
        fname = wm3_w
    elif wm_term == 5:
        fname = wm5_w
    elif wm_term == 9:
        fname = wm9_w
    w_wm = read_matrix(fname, wm_term + 2, wm_term + 2)

    # -----------------------------------
    # estimate weighted moving average
    for i in range(ft_x, fn_x + 1):

        # initial edge period where is not enough data
        if i <= idiv(term * (wm_term + 1), 2) + ft_x - 1:

            # determine x(i) position in the first term
            initial_xn = ft_x + imod(i - ft_x, term)

            row = idiv(i - ft_x, term) + 1
            for j in range(1, wm_term + 2 + 1):
                wm_x[i] = x[initial_xn + (j - 1) * term] * w_wm[row][j] + wm_x[i]
            wm_xn += 1

        # end edge period where is not enough data
        elif i >= fn_x - term * idiv(wm_term + 1, 2) + 1:

            # term_xn shows the term including x(i)
            term_xn = idiv(i - (fn_x - (wm_term + 2) * term) - 1, term) + 1

            for j in range(1, wm_term + 2 + 1):
                wm_x[i] = x[i + (j - term_xn) * term] * w_wm[term_xn][j] + wm_x[i]
            wm_xn += 1

        # period where is enough data to estimate normal weight
        else:
            row = idiv(wm_term + 1, 2) + 1
            for j in range(1, wm_term + 2 + 1):
                wm_x[i] = x[i - (idiv(wm_term + 1, 2) - j + 1) * term] * w_wm[row][j] + wm_x[i]
            wm_xn += 1

    return wm_xn
