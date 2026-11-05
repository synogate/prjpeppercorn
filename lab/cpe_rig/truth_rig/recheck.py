"""Recompute the mismatch of stored series (words + F) with the current expected(): python recheck.py s1 s1b ..."""
import sys, os, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import expected, LOW
from suites import OUT
for s in sys.argv[1:]:
    p = os.path.join(OUT, s + ".jsonl")
    rows = [json.loads(l) for l in open(p)]
    bad = []
    for r in rows:
        if "F" not in r:
            continue
        F = int(r["F"], 16)
        E = expected(r["words"])
        m = sum(1 for k in range(1 << 14) if E[k & ((1 << LOW) - 1)] in "01" and int(E[k & ((1 << LOW) - 1)]) != (F >> k) & 1)
        r["mismatch"] = m
        if m:
            bad.append((r["name"], m))
    open(p, "w").write("".join(json.dumps(r) + chr(10) for r in rows))
    print(s, len(rows), "configs, mismatching:", len(bad), bad[:10])
