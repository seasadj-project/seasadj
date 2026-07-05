"""Step1 of the decomposition (port of 05_st1.f90 / step1_mod)."""

from .ftn import idiv, imod, read_matrix
from .wma import wm_ave


def mov_ave(max_t, num_x, x, term, ave_x):
    """Centered term-moving average (2 x term terms when term is even).

    ave_x is written in place. Returns ave_xn.
    """
    # initialize
    for i in range(1, num_x + 1):
        ave_x[i] = 0.0

    ave_xn = 0

    # case of term is odd number
    if imod(term, 2) == 1:
        half = idiv(term - 1, 2)
        for i in range(half + 1, num_x - half + 1):
            for j in range(-half, half + 1):
                ave_x[i] = x[i + j] + ave_x[i]
            ave_x[i] = ave_x[i] / float(term)
            ave_xn += 1

    # case of term is even number
    if imod(term, 2) == 0:
        half = idiv(term, 2)
        for i in range(half + 1, num_x - half + 1):
            for j in range(-half, half + 1):
                if abs(j) == half:  # case of edge
                    ave_x[i] = x[i + j] + ave_x[i]
                else:
                    ave_x[i] = 2 * x[i + j] + ave_x[i]
            ave_x[i] = ave_x[i] / float(term * 2)
            ave_xn += 1

    return ave_xn


def Ini_SI(max_t, term, adj_on, adj_o, TC1, model, SI1):
    """Initial SI estimate. SI1 written in place. Returns SI1_n."""
    # initialize
    for i in range(1, max_t + 1):
        SI1[i] = 0.0

    SI1_n = 0

    # case of term is odd number
    if imod(term, 2) == 1:
        half = idiv(term - 1, 2)
        for i in range(half + 1, adj_on - half + 1):
            if model == 0:
                SI1[i] = adj_o[i] / TC1[i]
            else:
                SI1[i] = adj_o[i] - TC1[i]
            SI1_n += 1

    # case of term is even number
    if imod(term, 2) == 0:
        half = idiv(term, 2)
        for i in range(half + 1, adj_on - half + 1):
            if model == 0:
                SI1[i] = adj_o[i] / TC1[i]
            else:
                SI1[i] = adj_o[i] - TC1[i]
            SI1_n += 1

    return SI1_n


def Ini_S(max_t, term, SI1, SI1_n, iwm_term,
          wm3_w, wm5_w, wm9_w, pwm3_w, pwm5_w, pwm9_w, S1p):
    """Initial preliminary seasonal factor. S1p written in place. Returns S1p_n."""
    # read the file of 3x(iwm_term) weighted moving average weights to forecast
    # pw_wm[1][*]: backward, pw_wm[2][*]: forward
    if iwm_term == 3:
        fname = pwm3_w
    elif iwm_term == 5:
        fname = pwm5_w
    elif iwm_term == 9:
        fname = pwm9_w
    pw_wm = read_matrix(fname, 2, iwm_term + 2)

    # initialize S1p
    S1p_n = 0

    # case of term is odd number
    if imod(term, 2) == 1:
        half = idiv(term - 1, 2)

        for i in range(1, SI1_n + (term - 1) + 1):
            S1p[i] = 0.0

        # estimate S1p during the periods SI1 exists
        S1p_n = wm_ave(max_t, term, half + 1, SI1_n + half, SI1,
                       iwm_term, S1p, wm3_w, wm5_w, wm9_w)

        # estimate S1p during the periods SI1 doesn't exist
        for i in range(1, half + 1):
            for j in range(1, iwm_term + 2 + 1):
                S1p[i] = SI1[i + term * j] * pw_wm[1][j] + S1p[i]
            S1p_n += 1

        for i in range(SI1_n + half + 1, SI1_n + (term - 1) + 1):
            for j in range(0, iwm_term + 1 + 1):
                S1p[i] = SI1[i - term * (iwm_term + 2 - j)] * pw_wm[2][j + 1] + S1p[i]
            S1p_n += 1

    # case of term is even number
    if imod(term, 2) == 0:
        half = idiv(term, 2)

        for i in range(1, SI1_n + term + 1):
            S1p[i] = 0.0

        # estimate S1p during the periods SI1 exists
        S1p_n = wm_ave(max_t, term, half + 1, SI1_n + half, SI1,
                       iwm_term, S1p, wm3_w, wm5_w, wm9_w)

        # estimate S1p during the periods SI1 doesn't exist
        for i in range(1, half + 1):
            for j in range(1, iwm_term + 2 + 1):
                S1p[i] = SI1[i + term * j] * pw_wm[1][j] + S1p[i]
            S1p_n += 1

        for i in range(SI1_n + half + 1, SI1_n + term + 1):
            for j in range(0, iwm_term + 1 + 1):
                S1p[i] = SI1[i - term * (iwm_term + 2 - j)] * pw_wm[2][j + 1] + S1p[i]
            S1p_n += 1

    return S1p_n


def std_sf(max_t, num_ps, ps, term, model, sf):
    """Standardize the preliminary seasonal factor. sf written in place.

    Returns num_sf.
    """
    from .ftn import alloc

    ma_s = alloc(max_t)  # moving average of seasonal factor

    # initialize
    for i in range(1, num_ps + 1):
        ma_s[i] = 0.0
        sf[i] = 0.0

    num_sf = 0

    # calculate moving average of seasonal factor

    # case of period which has enough data to calculate moving average
    ma_sn = mov_ave(max_t, num_ps, ps, term, ma_s)

    # case of edge periods of which term is odd number
    if imod(term, 2) == 1:
        half = idiv(term - 1, 2)

        for i in range(1, half + 1):
            for j in range(1, term + 1):
                ma_s[i] = ps[j] + ma_s[i]
            ma_s[i] = ma_s[i] / float(term)
            ma_sn += 1

        for i in range(num_ps - half + 1, num_ps + 1):
            for j in range(num_ps - term + 1, num_ps + 1):
                ma_s[i] = ps[j] + ma_s[i]
            ma_s[i] = ma_s[i] / float(term)
            ma_sn += 1

    # case of edge periods of which term is even number
    if imod(term, 2) == 0:
        half = idiv(term, 2)

        for i in range(1, half + 1):
            for j in range(1, term + 1):
                ma_s[i] = ps[j] + ma_s[i]
            ma_s[i] = ma_s[i] / float(term)
            ma_sn += 1

        for i in range(num_ps - half + 1, num_ps + 1):
            for j in range(num_ps - term + 1, num_ps + 1):
                ma_s[i] = ps[j] + ma_s[i]
            ma_s[i] = ma_s[i] / float(term)
            ma_sn += 1

    # standardize seasonal factor
    for i in range(1, num_ps + 1):
        if model == 0:
            sf[i] = ps[i] / ma_s[i]
        else:
            sf[i] = ps[i] - ma_s[i]
        num_sf += 1

    return num_sf
