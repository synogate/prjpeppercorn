"""CPOUT through the Y1 lines (C_HORIZ = 0): cpout1 = C_C_P ? COUTY1 : POUTY1, cpout2 = C_C_P ? POUTY1 : COUTY1.  python cpout_y.py 1 | 2   -> hw_data/s13.jsonl"""
import sys, os, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import measure, measure_raw, identify
from suites import CPX, CPY, OUT
CPYP = dict(CPY, C_PY1_I="1")                      # south helper: POUTY1 = OUT1 = x13, COUTY1 = OUT2 = x14 (C_CY1_I = 1, C_SELY1 = 0)
zero = {k: "0000" for k in ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")}
out = open(os.path.join(OUT, "s13.jsonl"), "a")


def run(name, words, obs, cp=None):
    if cp is not None:
        F, info, m = measure("s13_" + name, words, CPX, CPYP, obs, None, cp)
    else:
        F, info = measure_raw("s13_" + name, words, CPX, CPYP, obs); m = None
    best = identify(F)
    print(name, "identify:", best, "mismatch vs cpe.v:", m, flush=True)
    out.write(json.dumps({"name": name, "words": words, "obs": obs, "best": best, "mismatch": m, "F": format(sum(b << i for i, b in enumerate(F)), "x")}) + chr(10))


if sys.argv[1] == "1":      # CPOUT1 on OUT1 (C_O1 = 10)
    base = dict(zero, C_FUNCTION="000", C_HORIZ="0", C_O1="10")
    run("cpout1_cp1_coutY1_pass", dict(base, C_C_P="1"), "OUT1", {"CINY1": 14})      # COUTY1 passes CINY1 (C_CY1_I = 0): model x14
    run("cpout1_cp0_poutY1", dict(base, C_C_P="0"), "OUT1")                          # POUTY1 (C_PY1_I = 0): hypothesis PINY1 = x13, model: py1_route (loop with OUT1, so no expectation)
else:                       # CPOUT2 on OUT2 (C_O2 = 10)
    base = dict(zero, C_FUNCTION="000", C_HORIZ="0", C_O2="10")
    run("cpout2_cp0_coutY1_pass", dict(base, C_C_P="0"), "OUT2", {"CINY1": 14})
    run("cpout2_cp1_poutY1", dict(base, C_C_P="1"), "OUT2")
