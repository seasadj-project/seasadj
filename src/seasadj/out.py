"""Result output (port of 07_out.f90 / output_mod).

Numeric values are written with repr() (17 significant digits, round-trip
exact); the byte layout of the Fortran list-directed output is deliberately
not reproduced — the golden test comparison parses values, not bytes.
The o20/o21 label texts and field layout follow the Fortran formats so both
versions can be parsed by the same reader.
"""


def output_data(filename, x, num_x):
    """Write x[1..num_x], one value per line."""
    with open(filename, "w", encoding="ascii", newline="\n") as f:
        for i in range(1, num_x + 1):
            f.write(f" {x[i]!r}\n")


def output_summary(filename, A2_n, term, weekday, o, TC3, S2, I3, A2,
                   hol_eff, ao_eff, ls_eff):
    """Write the summary table o20_SUM (format '(i4, i4, F10.1, 7F14.5)')."""
    header = (" day week     O(t)        TC3(t)         S2(t)         I3(t)"
              "         A2(t)    hol_eff(t)     ao_eff(t)     ls_eff(t)")
    with open(filename, "w", encoding="ascii", newline="\n") as f:
        f.write(header + "\n")
        for i in range(1, A2_n + 1):
            f.write(f"{i:4d}{weekday[i]:4d}{o[i]:10.1f}"
                    f"{TC3[i]:14.5f}{S2[i]:14.5f}{I3[i]:14.5f}{A2[i]:14.5f}"
                    f"{hol_eff[i]:14.5f}{ao_eff[i]:14.5f}{ls_eff[i]:14.5f}\n")


def output_internal(filename,
                    ini_o_day, hol_reg_p, term, ih_term, fh_term, iwm_term,
                    swm_term, model, rep_si, sig_l, sig_u, bias_sig,
                    max_on, lead_on, hol_eff_n, ao_eff_n, ls_eff_n, adj_on,
                    TC1_n, SI1_n, S1p_n, S1_n, A1_n, TC2_n, SI2_n, S2p_n,
                    S2_n, A2_n, TC3_n, I3_n, w1_n, SI1r_n, w2_n, SI2r_n):
    """Write the internal data file o21_INT (same labels/format widths as the
    Fortran: a50 / a36+i5 / a36+f8.5 / a18+i5+a20+i5)."""

    def t(s):    # form_t '(a50)' : right-justified in width 50
        return f"{s:>50s}\n"

    def lidat(label, val):  # form_lidat '(a36, i5)'
        return f"{label:>36s}{val:5d}\n"

    def lrdat(label, val):  # form_lrdat '(a36, f8.5)'
        return f"{label:>36s}{val:8.5f}\n"

    def ndat2(l1, v1, l2, v2):  # form_ndat '(a18, i5, a20, i5)'
        return f"{l1:>18s}{v1:5d}{l2:>20s}{v2:5d}\n"

    def ndat1(l1, v1):  # form_ndat with a single pair
        return f"{l1:>18s}{v1:5d}\n"

    with open(filename, "w", encoding="ascii", newline="\n") as f:
        f.write(t("--------------------------------------------------"))
        f.write(t("internal of data                                  "))
        f.write(t("--------------------------------------------------"))
        f.write(lidat("weekday of initial original data ", ini_o_day))
        f.write(lrdat("parameter of holiday regression  ", hol_reg_p))
        f.write(lidat("number of weekdays  ", term))
        f.write(lidat("term of henderson (ih_term)", ih_term))
        f.write(lidat("term of henderson (fh_term)", fh_term))
        f.write(lidat("term of seasonal MA (iwm_term)", iwm_term))
        f.write(lidat("term of seasonal MA (swm_term)", swm_term))
        f.write(lidat("model (multi=0, additive=1)   ", model))
        f.write(lidat("replace extreme SI (rep_si)   ", rep_si))
        f.write(lrdat("lower sigma limit (sig_l)     ", sig_l))
        f.write(lrdat("upper sigma limit (sig_u)     ", sig_u))
        # the line below appears in the log model only : the output of the
        # other models stays identical to the former versions
        if model == 2:
            f.write(lrdat("trend bias correction (sig)   ", bias_sig))
        f.write(t(""))
        f.write(t("--------------------------------------------------"))
        f.write(t("number of data                                    "))
        f.write(t("--------------------------------------------------"))
        f.write(ndat2("num of o        = ", max_on, "  num of lead_o   = ", lead_on))
        f.write(ndat1("num of hol eff  = ", hol_eff_n))
        f.write(ndat2("num of ao eff   = ", ao_eff_n, "  num of ls  eff  = ", ls_eff_n))
        f.write(ndat2("num of adj_o    = ", adj_on, "  num of TC1      = ", TC1_n))
        f.write(ndat2("num of SI1      = ", SI1_n, "  num of S1p      = ", S1p_n))
        f.write(ndat2("num of S1       = ", S1_n, "  num of A1       = ", A1_n))
        f.write(ndat2("num of TC2      = ", TC2_n, "  num of SI2      = ", SI2_n))
        f.write(ndat2("num of S2p      = ", S2p_n, "  num of S2       = ", S2_n))
        f.write(ndat2("num of A2       = ", A2_n, "  num of TC3      = ", TC3_n))
        f.write(ndat1("num of I3       = ", I3_n))
        f.write(ndat2("num of w1       = ", w1_n, "  num of SI1r     = ", SI1r_n))
        f.write(ndat2("num of w2       = ", w2_n, "  num of SI2r     = ", SI2r_n))
