"""Step2/3 of the decomposition (port of 06_st2.f90 / step2_mod)."""

from .ftn import alloc, ialloc, idiv, read_matrix
from .wma import wm_ave


def hmv_ave(max_t, num_x, x, h_term, hmv_x, h5_w, h7_w, h9_w, h13_w, h23_w):
    """Henderson moving average. hmv_x written in place. Returns hmv_xn."""
    # initialize of hmv_x and hmv_xn
    for i in range(1, num_x + 1):
        hmv_x[i] = 0.0

    hmv_xn = 0

    # read the file of h_term henderson moving average weight
    if h_term == 5:
        fname = h5_w
    elif h_term == 7:
        fname = h7_w
    elif h_term == 9:
        fname = h9_w
    elif h_term == 13:
        fname = h13_w
    elif h_term == 23:
        fname = h23_w
    w_hmv = read_matrix(fname, h_term, h_term)

    # estimate henderson moving average
    for i in range(1, num_x + 1):

        # initial edge period where is not enough data
        if i <= idiv(h_term + 1, 2):
            for j in range(1, h_term + 1):
                hmv_x[i] = x[j] * w_hmv[i][j] + hmv_x[i]
            hmv_xn += 1

        # end edge period where is not enough data
        elif i >= num_x - idiv(h_term + 1, 2) + 1:
            for j in range(1, h_term + 1):
                hmv_x[i] = x[num_x - h_term + j] * w_hmv[i - num_x + h_term][j] + hmv_x[i]
            hmv_xn += 1

        # period where is enough data to estimate normal weight
        else:
            row = idiv(h_term + 1, 2)
            for j in range(1, h_term + 1):
                hmv_x[i] = x[i - row + j] * w_hmv[row][j] + hmv_x[i]
            hmv_xn += 1

    return hmv_xn


def dev_dat(max_t, num_x, x, num_y, y, model, z):
    """Remove y from x (multiplicative: division, additive: subtraction).

    z written in place. Returns num_z.
    """
    num_z = 0

    num_l = min(num_x, num_y)

    if model == 0:
        for i in range(1, num_l + 1):
            z[i] = x[i] / y[i]
            num_z += 1
    else:
        for i in range(1, num_l + 1):
            z[i] = x[i] - y[i]
            num_z += 1

    return num_z


def det_het(max_t, max_on, A_n, A, h5_w, h7_w, h9_w, h13_w, h23_w, model):
    """Determine the term of the henderson moving average.

    Returns (h_term, sum_ratio) and prints the Fortran console line.
    """
    c9_13 = 1.0   # criteria dividing  9-term and 13-term
    c13_23 = 3.5  # criteria dividing 13-term and 23-term

    pr_T = alloc(max_t)  # preliminary trend estimated
    pr_I = alloc(max_t)  # preliminary irregular estimated

    # initialize h_term
    h_term = 13
    sum_T = 0.0
    sum_I = 0.0

    # estimate preliminary trend by using 13-term henderson moving average
    pr_T_n = hmv_ave(max_t, A_n, A, h_term, pr_T, h5_w, h7_w, h9_w, h13_w, h23_w)

    # estimate preliminary irregular estimated data
    pr_I_n = dev_dat(max_t, A_n, A, pr_T_n, pr_T, model, pr_I)

    # estimate sum of month-to-month percent change (multiplicative model) or
    # month-to-month difference (additive model) of pr_T and pr_I without sign
    # by using the data which isn't extended
    half = idiv(h_term - 1, 2)
    if model == 0:
        for i in range(half + 2, max_on - half + 1):
            sum_T = sum_T + abs(pr_T[i] / pr_T[i - 1] - 1)
            sum_I = sum_I + abs(pr_I[i] / pr_I[i - 1] - 1)
    else:
        for i in range(half + 2, max_on - half + 1):
            sum_T = sum_T + abs(pr_T[i] - pr_T[i - 1])
            sum_I = sum_I + abs(pr_I[i] - pr_I[i - 1])

    # determine h_term by the ratio of sum_I/sum_T
    ratio = sum_I / sum_T

    if ratio < c9_13:
        h_term = 9
    elif ratio > c13_23:
        h_term = 23
    elif c9_13 <= ratio <= c13_23:
        h_term = 13
    else:
        print("error in subroutine det_het")

    print(f"{'h_term =':>11s}{h_term:3d}{'sum_I/sum_T =':>20s}{ratio:5.2f}")

    return (h_term, ratio)


def det_swm(max_t, term, ft_o, SI_n, SI, max_on, weekday, model,
            wm3_w, wm5_w, wm9_w):
    """Determine the term of the weighted moving average in the Preliminary
    Seasonal Factor estimate (global MSR).

    Returns (swm_term, msr_ratio, count) and prints the Fortran console line.
    """
    c_AB = 2.5  # criteria separating A and B (under c_AB: 3x3)
    c_BC = 3.5  # criteria separating B and C (under c_BC: buffer zone)
    c_CD = 5.5  # criteria separating C and D (under c_CD: 3x5)
    c_DE = 6.5  # criteria separating D and E (under c_DE: buffer zone)
                #                             (over  c_DE: 3x9)

    max_loop = 5  # maximum loop times to estimate MSR

    pr_S = alloc(max_t)  # preliminary seasonal factor estimated
    pr_I = alloc(max_t)  # preliminary irregular estimated

    sum_S = alloc(term)      # sum of absolute cycle-to-cycle changes of pr_S per weekday
    sum_I = alloc(term)      # sum of absolute cycle-to-cycle changes of pr_I per weekday
    pr_S_nt = ialloc(term)   # number of weeks to estimate G_MSR_S
    pr_I_nt = ialloc(term)   # number of weeks to estimate G_MSR_I

    # initialize
    ft_SI = ft_o  # first day of SI equals first day of original series
    fn_SI = SI_n  # final day of SI equals final day of SI

    swm_term = 3  # a 3x3 moving average is used to estimate MSR
    count = 0
    G_MSR_S = 0.0
    G_MSR_I = 0.0

    for i in range(1, term + 1):
        sum_S[i] = 0.0
        sum_I[i] = 0.0
        pr_S_nt[i] = 0
        pr_I_nt[i] = 0

    # estimate preliminary seasonal factor
    pr_S_n = wm_ave(max_t, term, ft_SI, fn_SI, SI, swm_term, pr_S,
                    wm3_w, wm5_w, wm9_w)

    # estimate preliminary irregular estimated data
    pr_I_n = dev_dat(max_t, SI_n, SI, pr_S_n, pr_S, model, pr_I)

    # determine the edge date
    edge = max_on - weekday[max_on + 1] + 1

    # estimate global moving seasonality ratio (MSR)
    for i in range(0, max_loop + 1):

        G_MSR_S = 0.0
        G_MSR_I = 0.0

        # reset accumulators: they would carry over between retries otherwise
        for j in range(1, term + 1):
            sum_S[j] = 0.0
            sum_I[j] = 0.0
            pr_S_nt[j] = 0
            pr_I_nt[j] = 0

        for j in range(1, term + 1):
            for k in range(1, (edge - term) - i * term + 1):
                if weekday[k] == j:
                    # cycle-to-cycle percent change (multiplicative model)
                    # or cycle-to-cycle difference (additive model)
                    if model == 0:
                        sum_S[j] = abs(pr_S[k + term] / pr_S[k] - 1) + sum_S[j]
                        sum_I[j] = abs(pr_I[k + term] / pr_I[k] - 1) + sum_I[j]
                    else:
                        sum_S[j] = abs(pr_S[k + term] - pr_S[k]) + sum_S[j]
                        sum_I[j] = abs(pr_I[k + term] - pr_I[k]) + sum_I[j]

                    pr_S_nt[j] += 1
                    pr_I_nt[j] += 1

            # mean absolute change (divided by the number of changes) weighted
            # by the number of observations, following the standard X-11 MSR
            if pr_S_nt[j] > 0:
                G_MSR_S = (pr_S_nt[j] + 1) * (sum_S[j] / pr_S_nt[j]) + G_MSR_S
                G_MSR_I = (pr_I_nt[j] + 1) * (sum_I[j] / pr_I_nt[j]) + G_MSR_I

        # MSR cannot be estimated if the seasonal factor shows no variation
        if G_MSR_S <= 0.0:
            count += 1
            continue

        if G_MSR_I / G_MSR_S < c_AB:
            swm_term = 3
            break
        elif c_BC < G_MSR_I / G_MSR_S < c_CD:
            swm_term = 5
            break
        elif G_MSR_I / G_MSR_S > c_DE:
            swm_term = 9
            break
        else:
            count += 1

    if count == max_loop + 1:
        swm_term = 5

    msr_ratio = G_MSR_I / G_MSR_S if G_MSR_S != 0.0 else float("inf")

    print(f"{'swm_term =':>11s}{swm_term:3d}{'G_MSR_I/G_MSR_S =':>20s}{msr_ratio:5.2f}"
          f"{'count    =':>12s}{count:3d}")

    return (swm_term, msr_ratio, count)
