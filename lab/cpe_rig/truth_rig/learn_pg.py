"""Learn the propagate (P) and generate (G) functions of the COUTX generator from series with C_HORIZ = 1, C_CX_I = 0 (COUTX = P ? G : CINX):
per low-11-bit group P = 0 if COUTX follows CINX (x11), P = 1 if it is constant over x11 (then G = that constant).  P and G are tabulated against the LUT outputs of the (validated) model.
    python learn_pg.py e3 1     ->  functions for C_FUNCTION 1"""
import sys, os, json, itertools, collections
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import internals, key15
from suites import OUT
ser, f = sys.argv[1], int(sys.argv[2])      # ser = name prefix in the file, e.g. e3 / y3
SER_FILE = sys.argv[3] if len(sys.argv) > 3 else "s17"
CBIT = int(sys.argv[4]) if len(sys.argv) > 4 else 0          # counter bit of the carry in minus 11 (CINX = x11 -> 0, CINY1 = x14 -> 3)
rows = [json.loads(l) for l in open(os.path.join(OUT, SER_FILE + ".jsonl"))]
rows = [r for r in rows if r["name"].startswith("%s_f%d_" % (ser, f))]
LV = ("l00", "l01", "l02", "l03", "l10", "l11")
table = collections.defaultdict(collections.Counter)      # l-vector -> counter of observed (P, G)
bad = 0
for r in rows:
    F = np.array([(int(r["F"], 16) >> s) & 1 for s in range(1 << 17)], dtype=np.uint8).reshape(64, 2048)
    cons = all((F[h] == F[h & (1 << CBIT)]).all() for h in range(64))                     # F must depend on x11 only (not on x12..x16)
    bad += 0 if cons else 1
    A0, A1 = F[0], F[1 << CBIT]
    d = internals(r["words"], LV)
    for low in range(2048):
        k = key15(low)
        lv = tuple(int(d[n][k]) for n in LV)
        if A0[low] == 0 and A1[low] == 1: obs = (0, None)           # follows CINX
        elif A0[low] == A1[low]: obs = (1, int(A0[low]))             # constant: generate
        else: obs = ("inv", None)
        table[lv][obs] += 1
print("%s f=%d: %d configs, %d inconsistent in x12..x16, %d distinct LUT-output vectors seen" % (ser, f, len(rows), bad, len(table)))
conf = {lv: c for lv, c in table.items() if len(c) > 1}
print("vectors with conflicting observations (P/G depend on more than l00..l11):", len(conf))
for lv, c in list(conf.items())[:6]:
    print("   ", dict(zip(LV, lv)), dict(c))
# P as function of (l10, l11)
pt = collections.defaultdict(set)
for lv, c in table.items():
    for (p, g) in c: pt[(lv[4], lv[5])].add(p)
print("P(l10,l11):", {k: sorted(map(str, v)) for k, v in sorted(pt.items())})
# G as function of the l-vector (only where P = 1)
g = {lv: {gg for (p, gg) in c if p == 1} for lv, c in table.items()}
g = {lv: s for lv, s in g.items() if s}
print("G known for", len(g), "vectors; conflicts:", sum(1 for s in g.values() if len(s) > 1))
# test hypotheses
hyp = {"l00|l01": lambda v: v[0] | v[1], "l00|l01|l02": lambda v: v[0] | v[1] | v[2], "l10 ? l02 : (l00|l01)": lambda v: v[2] if v[4] else (v[0] | v[1]),
       "l10 ? l02 : (l00|l01|l02)": lambda v: v[2] if v[4] else (v[0] | v[1] | v[2]), "l00|l01|l02|l03": lambda v: v[0] | v[1] | v[2] | v[3], "(l00|l01)&l02": lambda v: (v[0] | v[1]) & v[2],
       "l10|l11": lambda v: v[4] | v[5], "l00|l10": lambda v: v[0] | v[4], "l01|l02": lambda v: v[1] | v[2], "l00|l01|l11": lambda v: v[0] | v[1] | v[5], "l00|l01|l03": lambda v: v[0] | v[1] | v[3],
       "l00|l10|l02": lambda v: v[0] | v[4] | v[2], "l10 ? l11 : (l00|l01|l02)": lambda v: v[5] if v[4] else (v[0] | v[1] | v[2])}
for name, fn in hyp.items():
    mis = sum(1 for lv, s in g.items() for gg in s if fn(lv) != gg)
    print("   G = %-28s mismatches over %d vectors: %d" % (name, len(g), mis))
print("G truth table (l00 l01 l02 l03 l10 l11 -> G):")
for lv in sorted(g): print("   ", "".join(map(str, lv)), sorted(g[lv]))
