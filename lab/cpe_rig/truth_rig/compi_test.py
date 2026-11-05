"""Does C_COMP_I invert COMP_OUT in front of the routing multiplexers?  COUTX (read as CINX) and POUTX (read as PINX) with the routing mux on COMP_OUT (SEL = 10), C_COMP_I = 0 / 1.
    python compi_test.py -> hw_data/s22.jsonl"""
import sys, os, json
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from east import measure_east
from meas import internals, key15
from map_coutx import ENV, CPX, CPYP
from map_poutx import EAST_PINX
from east import EAST_CINX
from suites import OUT
NS = 1 << 17
keys = np.array([key15(s) for s in range(NS)])
out = open(os.path.join(OUT, "s22.jsonl"), "a")
cases = []
for ci in "01":
    cases.append(("coutx_route_comp_ci" + ci, dict(ENV, C_FUNCTION="000", C_CX_I="1", C_SEL_C="1", C_SELX="0", C_COMP_I=ci), EAST_CINX, "cx_route"))
    cases.append(("poutx_route_comp_ci" + ci, dict(ENV, C_FUNCTION="000", C_PX_I="1", C_SEL_P="1", C_SELX="0", C_COMP_I=ci), EAST_PINX, "px_route"))
for name, w, east, sig in cases:
    F, info = measure_east("s22_" + name, w, CPX, CPYP, east)
    Fv = np.array(F, dtype=np.uint8)
    d = internals(w, ("comp_out", sig))
    comp = np.array([int(d["comp_out"][k]) for k in keys], dtype=np.uint8)           # raw LUT output of the model
    res = {"F == ~raw": int((Fv == 1 - comp).all()), "F == raw": int((Fv == comp).all())}
    print(name, res, flush=True)
    out.write(json.dumps({"name": name, "words": w, "res": res, "F": format(sum(int(b) << i for i, b in enumerate(F)), "x")}) + chr(10))
