"""For a measured COUTX config: in the states of a subset, find the smallest set of counter bits x0..x16 that determines F, and print its truth table.
    python dep_coutx.py NAME  [subset]   subset = P1 (model carry_propagate = 1), P0, all"""
import sys, os, json, itertools
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import internals, key15
from suites import OUT
name = sys.argv[1]; sub = sys.argv[2] if len(sys.argv) > 2 else "all"
r = [json.loads(l) for l in open(os.path.join(OUT, "s17.jsonl")) if json.loads(l)["name"] == name][0]
NS = 1 << 17
F = np.array([(int(r["F"], 16) >> s) & 1 for s in range(NS)], dtype=np.uint8)
d = internals(r["words"], ("carry_propagate",))
P = np.array([int(d["carry_propagate"][key15(s)]) for s in range(NS)], dtype=np.uint8)
sel = np.arange(NS)
if sub == "P1": sel = sel[P == 1]
if sub == "P0": sel = sel[P == 0]
bits = [(sel >> b) & 1 for b in range(17)]
print(name, sub, len(sel), "states; F ones:", int(F[sel].sum()))
for size in range(0, 7):
    hits = []
    for comb in itertools.combinations(range(17), size):
        key = np.zeros(len(sel), dtype=np.int64)
        for b in comb: key = key * 2 + bits[b]
        # F is a function of key iff every key value has a constant F
        mx = np.zeros(1 << size, dtype=np.int64) - 1; mn = np.zeros(1 << size, dtype=np.int64) + 2
        np.maximum.at(mx, key, F[sel]); np.minimum.at(mn, key, F[sel])
        ok = all((mx[k] == mn[k]) or mx[k] == -1 for k in range(1 << size))
        if ok: hits.append((comb, mx.copy()))
    if hits:
        for comb, tt in hits[:3]:
            print("  F depends only on x%s ; truth table (index = bits in that order, first listed = MSB):" % list(comb), "".join(str(max(int(t), 0)) for t in tt))
        break
else:
    print("  no dependency on <= 6 bits")
