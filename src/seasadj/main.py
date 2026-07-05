"""Processing flow (port of 01_main.f90 / program seasonal_adj_main,
version 16.0)."""

from pathlib import Path
from types import SimpleNamespace

from . import var
from .ftn import alloc, ialloc, idiv, imod
from .reg import (read_para, read_data, det_hol, det_ao, det_ls,
                  check_inputs, adj_org, week)
from .wma import wm_ave
from .st1 import mov_ave, Ini_SI, Ini_S, std_sf
from .st2 import hmv_ave, dev_dat, det_het, det_swm
from .rep import rep_ext
from .trb import trb_cor, exp_dat
from .out import output_data, output_summary, output_internal


def _pipeline(max_t, term, iwm_term, ft_o, rep_si, sig_l, sig_u, model,
              forecasting, ini_o_day, max_on, lead_on, o, lead_o,
              hol_eff, hol_eff_n, ao_eff, ao_eff_n, ls_eff, ls_eff_n,
              weights):
    """The decomposition core (check_inputs onward), on already-determined
    1-based input series. Shared verbatim by run() (file mode) and
    api.decompose() (in-memory mode) so both modes execute the exact same
    numeric code; only the surrounding I/O differs.

    hol_eff/ao_eff/ls_eff must already be fully determined (by det_hol/
    det_ao/det_ls or their *_core equivalents) before calling this, i.e. they
    must cover the forecast period (max_on + lead_on) as well.

    weights is a dict of the 11 weight file paths: wm3/wm5/wm9 (3x3/3x5/3x9
    moving average), pwm3/pwm5/pwm9 (their forecast-region variants),
    h5/h7/h9/h13/h23 (Henderson moving average).

    Returns a SimpleNamespace with every output series (1-based, as computed)
    and every diagnostic value, for the caller to write out and/or convert.
    """
    rwm_term = var.rwm_term
    pad_val = var.pad_val

    # the log model (2) log-transforms the adjusted data (adj_org) and runs
    # the additive pipeline on it ; the results are transformed back to the
    # original scale with the trend bias correction before the output
    wk_model = model
    if model == 2:
        wk_model = 1

    bias_sig = 0.0  # estimated in trb_cor (log model only)

    weekday = ialloc(max_t)
    adj_o = alloc(max_t)
    TC1 = alloc(max_t)
    SI1 = alloc(max_t)
    w1 = alloc(max_t)
    SI1r = alloc(max_t)
    S1p = alloc(max_t)
    S1 = alloc(max_t)
    A1 = alloc(max_t)
    TC2 = alloc(max_t)
    SI2 = alloc(max_t)
    w2 = alloc(max_t)
    SI2r = alloc(max_t)
    S2p = alloc(max_t)
    S2 = alloc(max_t)
    A2 = alloc(max_t)
    TC3 = alloc(max_t)
    I3 = alloc(max_t)

    # check consistency of input data
    check_inputs(max_t, term, iwm_term, forecasting, max_on, lead_on, o, lead_o,
                 hol_eff, hol_eff_n, ao_eff, ao_eff_n, ls_eff, ls_eff_n,
                 rep_si, rwm_term, model)

    # adjust original data
    adj_on = adj_org(max_t, o, lead_o, max_on, lead_on, hol_eff, ao_eff,
                     ls_eff, model, adj_o)

    # determine weekday of each days
    week(max_t, weekday, term, ini_o_day, max_on, lead_on)

    # paths of the weight files
    wm3 = weights["wm3"]
    wm5 = weights["wm5"]
    wm9 = weights["wm9"]
    pwm3 = weights["pwm3"]
    pwm5 = weights["pwm5"]
    pwm9 = weights["pwm9"]
    h5 = weights["h5"]
    h7 = weights["h7"]
    h9 = weights["h9"]
    h13 = weights["h13"]
    h23 = weights["h23"]

    # ----------------------------------------------------------------------
    # Step 1

    # estimate Initial Trend
    TC1_n = mov_ave(max_t, adj_on, adj_o, term, TC1)

    # estimate Initial SI
    SI1_n = Ini_SI(max_t, term, adj_on, adj_o, TC1, wk_model, SI1)

    # replace extreme SI1 ratios (X-11 extreme value replacement)
    if imod(term, 2) == 1:
        ft_SI1 = idiv(term - 1, 2) + 1
    else:
        ft_SI1 = idiv(term, 2) + 1

    (w1_n, SI1r_n, rep1_cnt, rep1_checked, rep1_printed) = rep_ext(
        max_t, term, ft_SI1, ft_SI1 + SI1_n - 1, SI1, rep_si, sig_l, sig_u,
        iwm_term, wk_model, wm3, wm5, wm9, w1, SI1r)

    # estimate Initial Preliminary Seasonal factor
    S1p_n = Ini_S(max_t, term, SI1r, SI1_n, iwm_term,
                  wm3, wm5, wm9, pwm3, pwm5, pwm9, S1p)

    # estimate Initial Seasonal factor
    S1_n = std_sf(max_t, S1p_n, S1p, term, wk_model, S1)

    # estimate Initial Seasonal Adjustment
    A1_n = dev_dat(max_t, adj_on, adj_o, S1_n, S1, wk_model, A1)

    # ----------------------------------------------------------------------
    # Step 2

    # determine the term of henderson moving average
    (ih_term, ih_ratio) = det_het(max_t, max_on, A1_n, A1,
                                  h5, h7, h9, h13, h23, wk_model)

    # estimate Intermediate Trend
    TC2_n = hmv_ave(max_t, A1_n, A1, ih_term, TC2, h5, h7, h9, h13, h23)

    # estimate Intermediate SI
    SI2_n = dev_dat(max_t, adj_on, adj_o, TC2_n, TC2, wk_model, SI2)

    # replace extreme SI2 ratios (X-11 extreme value replacement)
    (w2_n, SI2r_n, rep2_cnt, rep2_checked, rep2_printed) = rep_ext(
        max_t, term, ft_o, SI2_n, SI2, rep_si, sig_l, sig_u,
        rwm_term, wk_model, wm3, wm5, wm9, w2, SI2r)

    # estimate Preliminary Seasonal Factor
    (swm_term, msr_ratio, msr_count) = det_swm(max_t, term, ft_o, SI2_n, SI2r,
                                               max_on, weekday, wk_model,
                                               wm3, wm5, wm9)
    S2p_n = wm_ave(max_t, term, ft_o, SI2_n, SI2r, swm_term, S2p, wm3, wm5, wm9)

    # standardize Preliminary Seasonal Factor
    S2_n = std_sf(max_t, S2p_n, S2p, term, wk_model, S2)

    # estimate Seasonal Adjustment
    A2_n = dev_dat(max_t, adj_on, adj_o, S2_n, S2, wk_model, A2)

    # ----------------------------------------------------------------------
    # Step 3

    # determine the term of henderson moving average
    (fh_term, fh_ratio) = det_het(max_t, max_on, A2_n, A2,
                                  h5, h7, h9, h13, h23, wk_model)

    # estimate Final Trend
    TC3_n = hmv_ave(max_t, A2_n, A2, fh_term, TC3, h5, h7, h9, h13, h23)

    # estimate Final Irregular
    I3_n = dev_dat(max_t, A2_n, A2, TC3_n, TC3, wk_model, I3)

    # ----------------------------------------------------------------------
    # post-processing

    # in the additive model, pad the series edges (where no valid data exists)
    # of TC1/SI1/SI1r with pad_val : 0 cannot mark "no data" there since a
    # valid additive SI is itself around 0 (the multiplicative model keeps
    # the 0-padding)
    if model == 1:
        for i in range(1, ft_SI1 - 1 + 1):
            TC1[i] = pad_val
            SI1[i] = pad_val
            SI1r[i] = pad_val
        for i in range(ft_SI1 + SI1_n, adj_on + 1):
            TC1[i] = pad_val
            SI1[i] = pad_val
            SI1r[i] = pad_val

    # in the log model, transform the results back to the original scale
    if model == 2:

        # trend bias correction (Thomson & Ozaki 2002) : it needs the
        # log-domain S2 / I3 / TC3, so it runs before the back-transform ;
        # TC3 leaves trb_cor bias-corrected and in the original scale
        bias_sig = trb_cor(max_t, term, max_on, S2_n, S2, I3_n, I3, TC3_n, TC3)

        # back-transform of the other series (element-wise exp)
        exp_dat(max_t, adj_on, adj_o)
        exp_dat(max_t, adj_on, TC1)
        exp_dat(max_t, adj_on, SI1)
        exp_dat(max_t, adj_on, SI1r)
        exp_dat(max_t, S1p_n, S1p)
        exp_dat(max_t, S1_n, S1)
        exp_dat(max_t, A1_n, A1)
        exp_dat(max_t, TC2_n, TC2)
        exp_dat(max_t, SI2_n, SI2)
        exp_dat(max_t, SI2r_n, SI2r)
        exp_dat(max_t, S2p_n, S2p)
        exp_dat(max_t, S2_n, S2)
        exp_dat(max_t, A2_n, A2)

        # the series edges of TC1/SI1/SI1r (where no valid data exists) keep
        # the multiplicative-style 0-padding (exp turned the edge 0s into 1s)
        for i in range(1, ft_SI1 - 1 + 1):
            TC1[i] = 0.0
            SI1[i] = 0.0
            SI1r[i] = 0.0
        for i in range(ft_SI1 + SI1_n, adj_on + 1):
            TC1[i] = 0.0
            SI1[i] = 0.0
            SI1r[i] = 0.0

        # the final irregular is redefined as A2 / TC3 (as the X-13 table D13
        # = D11/D12) so that the identity adj_o = TC3 * S2 * I3 still holds
        # after the trend bias correction
        for i in range(1, I3_n + 1):
            I3[i] = A2[i] / TC3[i]

    return SimpleNamespace(
        adj_on=adj_on, adj_o=adj_o,
        weekday=weekday,
        TC1=TC1, TC1_n=TC1_n,
        SI1=SI1, SI1_n=SI1_n,
        w1=w1, w1_n=w1_n,
        SI1r=SI1r, SI1r_n=SI1r_n,
        S1p=S1p, S1p_n=S1p_n,
        S1=S1, S1_n=S1_n,
        A1=A1, A1_n=A1_n,
        TC2=TC2, TC2_n=TC2_n,
        SI2=SI2, SI2_n=SI2_n,
        w2=w2, w2_n=w2_n,
        SI2r=SI2r, SI2r_n=SI2r_n,
        S2p=S2p, S2p_n=S2p_n,
        S2=S2, S2_n=S2_n,
        A2=A2, A2_n=A2_n,
        TC3=TC3, TC3_n=TC3_n,
        I3=I3, I3_n=I3_n,
        ft_SI1=ft_SI1,
        ih_term=ih_term, ih_ratio=ih_ratio,
        fh_term=fh_term, fh_ratio=fh_ratio,
        swm_term=swm_term, msr_ratio=msr_ratio, msr_count=msr_count,
        rep1_cnt=rep1_cnt, rep1_checked=rep1_checked, rep1_printed=rep1_printed,
        rep2_cnt=rep2_cnt, rep2_checked=rep2_checked, rep2_printed=rep2_printed,
        bias_sig=bias_sig,
    )


def run(workdir="."):
    """Run the whole decomposition in the given working directory (which must
    hold in_data/ and para/, as for the Fortran executable). Writes out_data/
    and returns a dict of the internal values (for tests and callers)."""
    wd = Path(workdir)

    def p(rel):
        return str(wd / rel)

    (wd / "out_data").mkdir(parents=True, exist_ok=True)

    max_t = var.max_t

    # ----------------------------------------------------------------------
    # read 13 parameters from i00_inp.dat
    (ini_o_day, forecasting, reg_hol, hol_reg_p, reg_ao, reg_ls,
     term, iwm_term, ft_o, rep_si, sig_l, sig_u, model) = read_para(p(var.f_inp))

    # ----------------------------------------------------------------------
    # Preparing data for applying to X-11 methodology

    o = alloc(max_t)
    lead_o = alloc(max_t)
    hol_eff = alloc(max_t)
    ao_eff = alloc(max_t)
    ls_eff = alloc(max_t)

    # read original data
    max_on = read_data(p(var.f_org), max_t, o)

    # extend original data by X-13 forecasting data
    if forecasting == 1:
        lead_on = read_data(p(var.f_fct), max_t, lead_o)
    else:
        lead_on = 0

    # determine holiday, outlier and levelshift effects
    hol_eff_n = det_hol(reg_hol, p(var.f_eff_hol), p(var.f_reg_hol), max_t,
                        hol_reg_p, max_on, lead_on, model, hol_eff)
    ao_eff_n = det_ao(reg_ao, p(var.f_eff_ao), max_t, max_on, lead_on, model, ao_eff)
    ls_eff_n = det_ls(reg_ls, p(var.f_eff_ls), max_t, max_on, lead_on, model, ls_eff)

    # paths of the weight files
    weights = {
        "wm3": p(var.wm3_w), "wm5": p(var.wm5_w), "wm9": p(var.wm9_w),
        "pwm3": p(var.pwm3_w), "pwm5": p(var.pwm5_w), "pwm9": p(var.pwm9_w),
        "h5": p(var.h5_w), "h7": p(var.h7_w), "h9": p(var.h9_w),
        "h13": p(var.h13_w), "h23": p(var.h23_w),
    }

    r = _pipeline(max_t, term, iwm_term, ft_o, rep_si, sig_l, sig_u, model,
                  forecasting, ini_o_day, max_on, lead_on, o, lead_o,
                  hol_eff, hol_eff_n, ao_eff, ao_eff_n, ls_eff, ls_eff_n,
                  weights)

    # ----------------------------------------------------------------------
    # output files
    output_summary(p(var.o_sum), r.A2_n, term, r.weekday, o, r.TC3, r.S2, r.I3,
                   r.A2, hol_eff, ao_eff, ls_eff)
    output_data(p(var.o_org), o, max_on)
    output_data(p(var.o_adj), r.adj_o, r.adj_on)
    output_data(p(var.o_tc1), r.TC1, r.adj_on)     # there are no edge data in TC1
    output_data(p(var.o_SI1), r.SI1, r.adj_on)     # there are no edge data in SI1
    output_data(p(var.o_w1), r.w1, r.adj_on)       # weights are 1 where no SI1 data exists
    output_data(p(var.o_SI1r), r.SI1r, r.adj_on)   # there are no edge data in SI1r
    output_data(p(var.o_S1p), r.S1p, r.S1p_n)
    output_data(p(var.o_S1), r.S1, r.S1_n)
    output_data(p(var.o_A1), r.A1, r.A1_n)
    output_data(p(var.o_TC2), r.TC2, r.TC2_n)
    output_data(p(var.o_SI2), r.SI2, r.SI2_n)
    output_data(p(var.o_w2), r.w2, r.w2_n)
    output_data(p(var.o_SI2r), r.SI2r, r.SI2r_n)
    output_data(p(var.o_S2p), r.S2p, r.S2p_n)
    output_data(p(var.o_S2), r.S2, r.S2_n)
    output_data(p(var.o_A2), r.A2, r.A2_n)
    output_data(p(var.o_TC3), r.TC3, r.TC3_n)
    output_data(p(var.o_I3), r.I3, r.I3_n)

    output_internal(p(var.o_int),
                    ini_o_day, hol_reg_p, term, r.ih_term, r.fh_term, iwm_term,
                    r.swm_term, model, rep_si, sig_l, sig_u, r.bias_sig,
                    max_on, lead_on, hol_eff_n, ao_eff_n, ls_eff_n, r.adj_on,
                    r.TC1_n, r.SI1_n, r.S1p_n, r.S1_n, r.A1_n, r.TC2_n, r.SI2_n,
                    r.S2p_n, r.S2_n, r.A2_n, r.TC3_n, r.I3_n, r.w1_n, r.SI1r_n,
                    r.w2_n, r.SI2r_n)

    return {
        "params": {
            "ini_o_day": ini_o_day, "forecasting": forecasting,
            "reg_hol": reg_hol, "hol_reg_p": hol_reg_p, "reg_ao": reg_ao,
            "reg_ls": reg_ls, "term": term, "iwm_term": iwm_term,
            "ft_o": ft_o, "rep_si": rep_si, "sig_l": sig_l, "sig_u": sig_u,
            "model": model,
        },
        # console-level discrete decisions (exact-match targets)
        "si_replaced": ([(r.rep1_cnt, r.rep1_checked), (r.rep2_cnt, r.rep2_checked)]
                        if r.rep1_printed or r.rep2_printed else []),
        "h_terms": [r.ih_term, r.fh_term],
        "sum_ratios": [r.ih_ratio, r.fh_ratio],
        "swm_term": r.swm_term,
        "msr_ratio": r.msr_ratio,
        "msr_count": r.msr_count,
        "bias_sig": r.bias_sig,
        # series lengths
        "n": {
            "max_on": max_on, "lead_on": lead_on, "hol_eff_n": hol_eff_n,
            "ao_eff_n": ao_eff_n, "ls_eff_n": ls_eff_n, "adj_on": r.adj_on,
            "TC1_n": r.TC1_n, "SI1_n": r.SI1_n, "S1p_n": r.S1p_n, "S1_n": r.S1_n,
            "A1_n": r.A1_n, "TC2_n": r.TC2_n, "SI2_n": r.SI2_n, "S2p_n": r.S2p_n,
            "S2_n": r.S2_n, "A2_n": r.A2_n, "TC3_n": r.TC3_n, "I3_n": r.I3_n,
            "w1_n": r.w1_n, "SI1r_n": r.SI1r_n, "w2_n": r.w2_n, "SI2r_n": r.SI2r_n,
        },
        "ft_SI1": r.ft_SI1,
    }
