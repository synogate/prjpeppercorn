"""Analysis of s17 (map_coutx.py): for every config find which source reaches COUTX, possibly split by a selecting signal.
    python an_coutx.py  ->  prints a table and writes hw_data/s17_summary.json"""
import sys, os, json, itertools
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import internals, key15, CPMAP
from suites import OUT

SIGS = ("COUTX", "COUTY1", "cx_route", "cy1_route", "carry_generate", "carry_propagate", "multo2", "comp_out", "OUT1", "OUT2", "l00", "l01", "l02", "l10", "l11")
FILE, MODEL, ROUTE, CIN = (sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])) if len(sys.argv) > 4 else ("s17", "COUTX", "cx_route", 11)
rows = [json.loads(l) for l in open(os.path.join(OUT, FILE + ".jsonl"))]
NS = 1 << 17
keys = [key15(s) for s in range(NS)]
summary = {}


def vec(d, name):
    return [int(d[name][k]) for k in keys]


for r in rows:
    w = r["words"]; F = int(r["F"], 16); Fv = [(F >> s) & 1 for s in range(NS)]
    d = internals(w, SIGS)
    V = {n: vec(d, n) for n in SIGS}
    x = lambda b: [(s >> b) & 1 for s in range(NS)]
    cand = {"G": V["carry_generate"], "R": V[ROUTE], "CINX": x(CIN), "MULTO2": V["multo2"], "OUT1": V["OUT1"], "OUT2": V["OUT2"], "COMP": V["comp_out"],
            "CINY1": x(14), "CINY2": x(13), "0": [0] * NS, "1": [1] * NS}
    if MODEL == "COUTY1":
        cand.pop("OUT1")                      # OUT1 is the measured signal itself (CPOUT1 = COUTY1)
    l10, l11, l00, l01, l02 = V["l10"], V["l11"], V["l00"], V["l01"], V["l02"]
    split = {"none": [0] * NS, "S(model)": V["carry_propagate"], "~(l10^l11)": [1 - (a ^ b) for a, b in zip(l10, l11)], "~(l10&l11)": [1 - (a & b) for a, b in zip(l10, l11)],
             "l10": l10, "l11": l11, "l10&l11": [a & b for a, b in zip(l10, l11)], "l10|l11": [a | b for a, b in zip(l10, l11)], "COMP": V["comp_out"]}
    model_mis = sum(1 for a, b in zip(Fv, V[MODEL]) if a != b)
    found = None
    for sname, sv in split.items():
        parts = []
        for val in (0, 1):
            idx = [s for s in range(NS) if sv[s] == val]
            if not idx:
                parts.append(("-", None)); continue
            best = max(((cn, sum(1 for s in idx if cv[s] == Fv[s])) for cn, cv in cand.items()), key=lambda t: t[1])
            parts.append((best[0], best[1] == len(idx), best[1] / len(idx)))
        if all(p[1] is None or p[1] is True for p in parts):
            found = (sname, parts); break
    if not found:      # report the best split that comes closest
        bestsplit = None
        for sname, sv in split.items():
            tot = 0
            lab = []
            for val in (0, 1):
                idx = [s for s in range(NS) if sv[s] == val]
                if not idx:
                    continue
                bc = max(((cn, sum(1 for s in idx if cv[s] == Fv[s])) for cn, cv in cand.items()), key=lambda t: t[1])
                tot += bc[1]; lab.append("%s=%d -> %s (%.3f)" % (sname, val, bc[0], bc[1] / len(idx)))
            if bestsplit is None or tot > bestsplit[0]:
                bestsplit = (tot, "; ".join(lab))
        found = None
        nofit = "no exact fit; closest: " + bestsplit[1]
    desc = nofit if not found else "split by %s: %s=0 -> %s, %s=1 -> %s" % (found[0], found[0], found[1][0][0], found[0], found[1][1][0]) if found[0] != "none" else "always %s" % (found[1][0][0] if found[1][0][1] is not None else found[1][1][0])
    print("%-18s model mismatch %6d | %s" % (r["name"], model_mis, desc), flush=True)
    summary[r["name"]] = {"model_mismatch": model_mis, "fit": desc}
json.dump(summary, open(os.path.join(OUT, FILE + "_summary.json"), "w"), indent=1)
