"""Constants and file names (port of 02_var.f90 / var_mod)."""

from importlib import resources


def bundled_para_dir() -> str:
    """Path of the para/ weight files bundled inside the installed package
    (src/seasadj/para/, copied verbatim from 01_プログラム/para/).

    Used by api.decompose() so it needs no working directory. run() and the
    CLI keep reading the working directory's own para/, unaffected by this.
    Not supported when the package is loaded from a zip (zipimport); a
    regular pip install (wheel or editable) always yields a real path.
    """
    return str(resources.files("seasadj").joinpath("para"))

# compile-time limit of data length in the Fortran version (kept as-is so the
# "too many records" behaviour matches)
max_t = 7300

# term of weighted moving average to estimate the preliminary seasonal factor
# in the Step2 extreme SI replacement (3x5)
rwm_term = 5

# padding value of the series edges (where no valid data exists) of
# TC1/SI1/SI1r outputs in the additive model
pad_val = -999.0

# filenames to read (relative to the working directory, as in the Fortran)
f_inp = "in_data/i00_inp.dat"
f_org = "in_data/i01_org_ser.dat"
f_fct = "in_data/i02_fct_ser.dat"
f_reg_hol = "in_data/i03_hol_reg.dat"
f_eff_hol = "in_data/i04_hol_eff.dat"
f_eff_ao = "in_data/i05_aol_eff.dat"
f_eff_ls = "in_data/i06_lvs_eff.dat"

h5_w = "para/5_henderson.dat"
h7_w = "para/7_henderson.dat"
h9_w = "para/9_henderson.dat"
h13_w = "para/13_henderson.dat"
h23_w = "para/23_henderson.dat"

wm3_w = "para/3x3_mov_ave.dat"
wm5_w = "para/3x5_mov_ave.dat"
wm9_w = "para/3x9_mov_ave.dat"
pwm3_w = "para/fc_3x3_mov_ave.dat"
pwm5_w = "para/fc_3x5_mov_ave.dat"
pwm9_w = "para/fc_3x9_mov_ave.dat"

# filenames to write
o_org = "out_data/o01_org.dat"
o_adj = "out_data/o07_adj.dat"
o_tc1 = "out_data/o08_TC1.dat"
o_SI1 = "out_data/o09_SI1.dat"
o_S1p = "out_data/o10_S1p.dat"
o_S1 = "out_data/o11__S1.dat"
o_A1 = "out_data/o12__A1.dat"
o_TC2 = "out_data/o13_TC2.dat"
o_SI2 = "out_data/o14_SI2.dat"
o_S2p = "out_data/o15_S2p.dat"
o_S2 = "out_data/o16__S2.dat"
o_A2 = "out_data/o17__A2.dat"
o_TC3 = "out_data/o18_TC3.dat"
o_I3 = "out_data/o19__I3.dat"
o_sum = "out_data/o20_SUM.dat"
o_int = "out_data/o21_INT.dat"
o_w1 = "out_data/o22_SI1w.dat"
o_SI1r = "out_data/o23_SI1r.dat"
o_w2 = "out_data/o24_SI2w.dat"
o_SI2r = "out_data/o25_SI2r.dat"
