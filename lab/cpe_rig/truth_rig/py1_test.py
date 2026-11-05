"""POUTY1 with C_COMP = 1, C_HORIZ = 0, C_PY1_I = 1: constant ~C_COMP_I or comparator result ^ C_COMP_I?  POUTY1 read through CPOUT1 (C_C_P = 0, C_O1 = 10);
C_SELY1 = 1 so that the routing mux shows OUT2 (= ~x7) and not OUT1 (the measured signal).   python py1_test.py -> hw_data/s23.jsonl"""
import sys, os, json
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import measure_raw, internals, key15
from map_coutx import ENV, CPX, CPYP
from suites import OUT
NS = 1 << 17
S = np.arange(NS)
keys = np.array([key15(int(s)) for s in S])
x = lambda b: ((S >> b) & 1).astype(np.uint8)
out = open(os.path.join(OUT, "s23.jsonl"), "a")
base = dict(ENV, C_FUNCTION="000", C_HORIZ="0", C_COMP="1", C_C_P="0", C_O1="10", C_SELY1="1")
cases = []
for pyi in "10":
    for l30 in ("0110", "0000", "1111"):
        for ci in "01":
            if pyi == "0" and l30 != "0110":
                continue
            cases.append(("py%s_l%s_ci%s" % (pyi, l30, ci), dict(base, C_PY1_I=pyi, INIT_L30=l30, C_COMP_I=ci)))
for name, w in cases:
    F, info = measure_raw("s23_" + name, w, CPX, CPYP, "OUT1")
    Fv = np.array(F, dtype=np.uint8)
    d = internals(w, ("comp_out",))
    raw = np.array([int(d["comp_out"][k]) for k in keys], dtype=np.uint8)           # raw L30 output of the model
    cand = {"const0": np.zeros(NS, np.uint8), "const1": np.ones(NS, np.uint8), "raw": raw, "~raw": 1 - raw, "route(~x7)": 1 - x(7), "PINY1(x13)": x(13)}
    fit = [n for n, c in cand.items() if (c == Fv).all()]
    print(name, "fits:", fit or "none", "(raw ones: %d)" % int(raw.sum()), flush=True)
    out.write(json.dumps({"name": name, "words": w, "fits": fit, "F": format(sum(int(b) << i for i, b in enumerate(F)), "x")}) + chr(10))
