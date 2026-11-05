"""MULTO1 / POUTX with C_MULT = 1: POUTX read through CPOUT1 (C_C_P = 0, C_O1 = 10; C_MULT makes cp_use_x = 1), C_PX_I = 0, C_HORIZ = 0.  python mult1_test.py -> hw_data/s20.jsonl"""
import sys, os, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import measure_raw
from map_coutx import ENV, CPX, CPYP
from suites import OUT
out = open(os.path.join(OUT, "s20.jsonl"), "a")
base = dict(ENV, C_FUNCTION="011", C_HORIZ="0", C_PX_I="0", C_C_P="0", C_O1="10")
for l30 in ("0110", "1001"):
    for name, hx in (("v_default", {}), ("v_sely1", {"C_SELY1": "1"}), ("v_sely2", {"C_SELY2": "1"}), ("v_both", {"C_SELY1": "1", "C_SELY2": "1"})):
        w = dict(base, INIT_L30=l30)
        F, info = measure_raw("s20_%s_%s" % (l30, name), w, CPX, dict(CPYP, **hx), "OUT1")
        out.write(json.dumps({"name": "%s_%s" % (l30, name), "helper": hx, "words": w, "F": format(sum(b << i for i, b in enumerate(F)), "x")}) + chr(10))
        print(l30, name, info.get("unsure_states"), flush=True)
