"""Input reading, validation and prior adjustment (port of 03_reg.f90 / reg_mod)."""

import math

from .ftn import imod


class SeasadjError(Exception):
    """Raised where the Fortran calls abort_run (error message + stop 1), and
    for equivalent argument validation in api.decompose()."""


AbortRun = SeasadjError  # former name, kept as an alias for compatibility


def abort_run(msg: str):
    print(f"ERROR: {msg}")
    raise SeasadjError(msg)


def _to_int(tok: str) -> int:
    return int(tok)


def _to_float(tok: str) -> float:
    # Fortran list-directed input accepts d/D exponents
    return float(tok.replace("d", "e").replace("D", "E"))


def read_para(filename):
    """Read the 13 parameters (blocks A-M) from i00_inp.dat.

    Returns (ini_o_day, forecasting, reg_hol, hol_reg_p, reg_ao, reg_ls,
             term, iwm_term, ft_o, rep_si, sig_l, sig_u, model).
    """
    # set default parameters (kept for fidelity; every value is overwritten
    # below or the run aborts, as in the Fortran)
    ini_o_day = 1
    forecasting = 1
    reg_hol = 1
    hol_reg_p = 0.00
    reg_ao = 1
    reg_ls = 1
    term = 7
    iwm_term = 3
    ft_o = 1
    rep_si = 1
    sig_l = 1.5
    sig_u = 2.5
    model = 0

    try:
        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        abort_run(f"cannot open parameter file: {filename}")

    pos = 0

    def next_line():
        nonlocal pos
        if pos >= len(lines):
            return None
        line = lines[pos]
        pos += 1
        return line

    # skip header lines
    for _ in range(2):
        if next_line() is None:
            abort_run(f"unexpected end of {filename}")

    for j in range(1, 14):
        for _ in range(2):  # skip comments lines
            if next_line() is None:
                abort_run(f"unexpected end of {filename}"
                          " : 13 parameter blocks (A-M) are required")
        line = next_line()
        toks = line.split() if line is not None else []
        try:
            if not toks:
                raise ValueError
            if j == 1:
                ini_o_day = _to_int(toks[0])
            elif j == 2:
                forecasting = _to_int(toks[0])
            elif j == 3:
                reg_hol = _to_int(toks[0])
            elif j == 4:
                hol_reg_p = _to_float(toks[0])
            elif j == 5:
                reg_ao = _to_int(toks[0])
            elif j == 6:
                reg_ls = _to_int(toks[0])
            elif j == 7:
                term = _to_int(toks[0])
            elif j == 8:
                iwm_term = _to_int(toks[0])
            elif j == 9:
                ft_o = _to_int(toks[0])
            elif j == 10:
                rep_si = _to_int(toks[0])
            elif j == 11:
                sig_l = _to_float(toks[0])
            elif j == 12:
                sig_u = _to_float(toks[0])
            elif j == 13:
                model = _to_int(toks[0])
        except ValueError:
            abort_run(f"cannot read a parameter value in {filename}"
                      " : 13 parameter blocks (A-M) are required")

    # check the range of parameters
    if term < 2:
        abort_run("parameter G (term) must be 2 or larger")
    if ini_o_day < 1 or ini_o_day > term:
        abort_run("parameter A (ini_o_day) must be between 1 and term")
    if forecasting != 0 and forecasting != 1:
        abort_run("parameter B (forecasting) must be 0 or 1")
    if reg_hol != 0 and reg_hol != 1:
        abort_run("parameter C (reg_hol) must be 0 or 1")
    if reg_ao != 0 and reg_ao != 1:
        abort_run("parameter E (reg_ao) must be 0 or 1")
    if reg_ls != 0 and reg_ls != 1:
        abort_run("parameter F (reg_ls) must be 0 or 1")
    if iwm_term != 3 and iwm_term != 5 and iwm_term != 9:
        abort_run("parameter H (iwm_term) must be 3, 5 or 9")
    if ft_o < 1:
        abort_run("parameter I (ft_o) must be 1 or larger")
    if rep_si != 0 and rep_si != 1:
        abort_run("parameter J (rep_si) must be 0 or 1")
    if rep_si == 1:
        if sig_l <= 0.0:
            abort_run("parameter K (sig_l) must be positive")
        if sig_u <= sig_l:
            abort_run("parameter L (sig_u) must be larger than sig_l")
    if model != 0 and model != 1 and model != 2:
        abort_run("parameter M (model) must be 0 (multiplicative), 1 (additive) or 2 (log)")

    return (ini_o_day, forecasting, reg_hol, hol_reg_p, reg_ao, reg_ls,
            term, iwm_term, ft_o, rep_si, sig_l, sig_u, model)


def read_data(filename, max_t, x):
    """Read one value per record into x[1..] and return the record count."""
    num_x = 0

    try:
        f = open(filename, "r", encoding="utf-8", errors="replace")
    except OSError:
        abort_run(f"cannot open data file: {filename}")

    with f:
        for line in f:
            toks = line.split()
            if not toks:  # list-directed read skips empty records
                continue
            if num_x >= max_t:
                abort_run(f"too many records in {filename}"
                          " : raise max_t in 02_var.f90 and recompile")
            try:
                x[num_x + 1] = _to_float(toks[0])
            except ValueError:
                abort_run(f"invalid numeric data in {filename}")
            num_x += 1

    return num_x


def det_hol_core(reg_hol, hol_eff, hol_eff_n, hol_regdat, hol_regdat_n,
                  hol_reg_p, max_on, lead_on, model):
    """Compute holiday effects (hol_eff written in place). Returns hol_eff_n.

    hol_eff/hol_eff_n already hold the i04 data (and hol_regdat/hol_regdat_n
    the i03 data) when reg_hol == 1; both are unused when reg_hol == 0.
    """
    neu = 1.0
    if model == 1:
        neu = 0.0

    if reg_hol == 1:  # the regression variable of holiday is used
        if lead_on > 0:  # the case of forecasting data
            if hol_regdat_n < max_on + lead_on:
                abort_run("holiday regressor file is too short:"
                          " it must cover the forecast period as well")
            for i in range(max_on + 1, max_on + lead_on + 1):
                # the log model (2) takes the multiplicative factor : the
                # whole prior adjustment is done in the original scale and
                # log-transformed afterwards (adj_org)
                if model != 1:
                    hol_eff[i] = math.exp(hol_reg_p * hol_regdat[i])
                else:
                    hol_eff[i] = hol_reg_p * hol_regdat[i]
                hol_eff_n += 1

    else:  # the regression variable of holiday is not used
        for i in range(1, max_on + lead_on + 1):
            hol_eff[i] = neu
            hol_eff_n += 1

    return hol_eff_n


def det_hol(reg_hol, f_eff_hol, f_reg_hol, max_t, hol_reg_p, max_on, lead_on,
            model, hol_eff):
    """Determine holiday effects (file layer). Returns hol_eff_n (hol_eff
    written in place)."""
    from .ftn import alloc

    hol_regdat = None
    hol_regdat_n = 0
    hol_eff_n = 0

    if reg_hol == 1:  # the regression variable of holiday is used
        hol_regdat = alloc(max_t)
        hol_eff_n = read_data(f_eff_hol, max_t, hol_eff)
        hol_regdat_n = read_data(f_reg_hol, max_t, hol_regdat)

    return det_hol_core(reg_hol, hol_eff, hol_eff_n, hol_regdat, hol_regdat_n,
                         hol_reg_p, max_on, lead_on, model)


def det_ao_core(reg_ao, ao_eff, ao_eff_n, max_on, lead_on, model):
    """Compute additive outlier effects (ao_eff written in place). Returns
    ao_eff_n. ao_eff/ao_eff_n already hold the i05 data when reg_ao == 1."""
    neu = 1.0
    if model == 1:
        neu = 0.0

    if reg_ao == 1:
        if lead_on > 0:
            for i in range(max_on + 1, max_on + lead_on + 1):
                ao_eff[i] = neu  # outlier effects are neutral during t > max_on
                ao_eff_n += 1

    else:
        for i in range(1, max_on + lead_on + 1):
            ao_eff[i] = neu
            ao_eff_n += 1

    return ao_eff_n


def det_ao(reg_ao, f_eff_ao, max_t, max_on, lead_on, model, ao_eff):
    """Determine additive outlier effects (file layer). Returns ao_eff_n."""
    ao_eff_n = 0

    if reg_ao == 1:
        ao_eff_n = read_data(f_eff_ao, max_t, ao_eff)

    return det_ao_core(reg_ao, ao_eff, ao_eff_n, max_on, lead_on, model)


def det_ls_core(reg_ls, ls_eff, ls_eff_n, max_on, lead_on, model):
    """Compute levelshift effects (ls_eff written in place). Returns
    ls_eff_n. ls_eff/ls_eff_n already hold the i06 data when reg_ls == 1."""
    neu = 1.0
    if model == 1:
        neu = 0.0

    if reg_ls == 1:
        if lead_on > 0:
            for i in range(max_on + 1, max_on + lead_on + 1):
                ls_eff[i] = neu  # levelshift effects are neutral during t > max_on
                ls_eff_n += 1

    else:
        for i in range(1, max_on + lead_on + 1):
            ls_eff[i] = neu
            ls_eff_n += 1

    return ls_eff_n


def det_ls(reg_ls, f_eff_ls, max_t, max_on, lead_on, model, ls_eff):
    """Determine levelshift effects (file layer). Returns ls_eff_n."""
    ls_eff_n = 0

    if reg_ls == 1:
        ls_eff_n = read_data(f_eff_ls, max_t, ls_eff)

    return det_ls_core(reg_ls, ls_eff, ls_eff_n, max_on, lead_on, model)


def adj_org(max_t, o, lead_o, max_on, lead_on, hol_eff, ao_eff, ls_eff, model,
            adj_o):
    """Adjust original data. Returns adj_on (adj_o written in place)."""
    adj_on = 0

    # adjusting original data during t <= max_on
    # (the log model (2) adjusts in the original scale with the same
    #  multiplicative factors as model 0, then log-transforms : the
    #  decomposition pipeline runs on log(adjusted data))
    for i in range(1, max_on + 1):
        if model == 0:
            adj_o[i] = o[i] / (hol_eff[i] * ao_eff[i] * ls_eff[i])
        elif model == 1:
            adj_o[i] = o[i] - (hol_eff[i] + ao_eff[i] + ls_eff[i])
        else:
            adj_o[i] = math.log(o[i] / (hol_eff[i] * ao_eff[i] * ls_eff[i]))
        adj_on += 1

    # adjusting forecast data
    if lead_on > 0:
        for i in range(max_on + 1, max_on + lead_on + 1):
            if model == 0:
                adj_o[i] = lead_o[i - max_on] / (hol_eff[i] * ao_eff[i] * ls_eff[i])
            elif model == 1:
                adj_o[i] = lead_o[i - max_on] - (hol_eff[i] + ao_eff[i] + ls_eff[i])
            else:
                adj_o[i] = math.log(lead_o[i - max_on] / (hol_eff[i] * ao_eff[i] * ls_eff[i]))
            adj_on += 1

    return adj_on


def week(max_t, weekday, term, ini_o_day, max_on, lead_on):
    """Determine the weekday of each day (weekday written in place).

    Fills one extra slot: weekday[max_on + lead_on + 1] is referenced in det_swm.
    """
    for i in range(1, min(max_on + lead_on + 1, max_t) + 1):
        weekday[i] = imod((ini_o_day - 1) + (i - 1), term) + 1


def check_inputs(max_t, term, iwm_term, forecasting, max_on, lead_on, o, lead_o,
                 hol_eff, hol_eff_n, ao_eff, ao_eff_n, ls_eff, ls_eff_n,
                 rep_si, rwm_term, model):
    """Check consistency of input data (aborts on the first violation)."""
    # check the length of data
    if max_on < 1:
        abort_run("original data file is empty")
    if forecasting == 1 and lead_on < 1:
        abort_run("forecasting = 1 but the forecast data file is empty")
    if max_on + lead_on > max_t:
        abort_run("data length exceeds max_t : raise max_t in 02_var.f90 and recompile")
    if max_on < 20:
        abort_run("original data is too short (at least 20 observations are needed)")
    if max_on + lead_on < term * (iwm_term + 3):
        abort_run("time series is too short for the seasonal filters"
                  " (term * (iwm_term + 3) observations are needed)")
    if rep_si == 1 and max_on + lead_on < term * (rwm_term + 3):
        abort_run("time series is too short for the extreme SI replacement"
                  " (term * 8 observations are needed when rep_si = 1)")

    # the multiplicative and log models require positive data
    # (the additive model accepts zero and negative values)
    if model != 1:
        for i in range(1, max_on + 1):
            if o[i] <= 0.0:
                abort_run("original data must be positive (multiplicative/log model)")
        for i in range(1, lead_on + 1):
            if lead_o[i] <= 0.0:
                abort_run("forecast data must be positive (multiplicative/log model)")

    # effects must cover the whole period and be positive (they are used as divisors)
    if hol_eff_n < max_on + lead_on:
        abort_run("holiday effect file must have the same number of records as the original data")
    if ao_eff_n < max_on + lead_on:
        abort_run("additive outlier effect file must have the same number of records as the original data")
    if ls_eff_n < max_on + lead_on:
        abort_run("levelshift effect file must have the same number of records as the original data")

    # effects are used as divisors in the multiplicative and log models
    if model != 1:
        for i in range(1, max_on + lead_on + 1):
            if hol_eff[i] <= 0.0 or ao_eff[i] <= 0.0 or ls_eff[i] <= 0.0:
                abort_run("effect data must be positive (they are used as divisors)")
