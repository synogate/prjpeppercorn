"""Analysis of s21 p1 (map_poutx.py): per config the model mismatch (cpe.v), the best single source / split by comp_out, and the mismatch of the hypothesis
   POUTX = mux4{S1, S0}(D0 = C_COMP_I, D1 = px_route, D2 = PINX, D3 = MULTO1),  S0 = C_MULT | C_PX_I,  S1 = ~(C_PX_I | (C_COMP & C_HORIZ & comp_out)).
    python an_poutx.py"""
import sys, os, json
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import internals, key15
from suites import OUT
rows = [json.loads(l) for l in open(os.path.join(OUT, "s21.jsonl"))]
rows = [r for r in rows if r["name"].startswith("p1_")]
NS = 1 << 17
S = np.arange(NS)
keys = np.array([key15(int(s)) for s in S])
PINX = ((S >> 12) & 1).astype(np.uint8)
res = {}
for r in rows:
    w = r["words"]
    d = internals(w, ("POUTX", "px_route", "multo1", "comp_out"))
    V = {n: np.array([int(d[n][k]) for k in keys], dtype=np.uint8) for n in d}
    F = np.array([(int(r["F"], 16) >> s) & 1 for s in range(NS)], dtype=np.uint8)
    f = int(w["C_FUNCTION"], 2); mult = int(f == 3); comp, h, pxi, ci = (int(w[k]) for k in ("C_COMP", "C_HORIZ", "C_PX_I", "C_COMP_I"))
    co = V["comp_out"]
    s0 = mult | pxi
    s1 = 1 - (pxi | (comp & h & (1 - co)))          # refined (S21): the comparator condition is the raw LUT output = ~comp_out
    hyp = np.where(s1 == 1, np.where(s0 == 1, V["multo1"], PINX), np.where(s0 == 1, V["px_route"], 1 - ci)).astype(np.uint8)         # D0 = ~C_COMP_I
    cand = {"C_COMP_I": np.full(NS, ci, np.uint8), "R": V["px_route"], "PINX": PINX, "MULTO1": V["multo1"]}
    desc = None
    for part in ("all", "split"):
        if part == "all":
            ok = [n for n, c in cand.items() if (c == F).all()]
            if ok: desc = "always " + "/".join(ok); break
        else:
            out = []
            for cv in (0, 1):
                sel = co == cv
                okn = [n for n, c in cand.items() if (c[sel] == F[sel]).all()]
                out.append("comp_out=%d -> %s" % (cv, "/".join(okn) if okn else "?"))
            desc = "; ".join(out)
    res[r["name"]] = (int((V["POUTX"] != F).sum()), int((hyp != F).sum()), desc)
    print("%-34s model %6d  hypothesis %6d | %s" % (r["name"][3:], res[r["name"]][0], res[r["name"]][1], desc), flush=True)
print("configs:", len(rows), " model mismatching:", sum(1 for v in res.values() if v[0]), " hypothesis mismatching:", sum(1 for v in res.values() if v[1]))
