"""Search the config bits of the south helper (X146Y18) for a setting that puts a signal on its POUTY1 (PINY1 of the DUT, read through C_I1 -> L00 -> L10 -> COMB2OUT).
Stops at the first non-constant result.  python find_piny1.py   ->  hw_data/find_piny1.jsonl"""
import sys, os, json, itertools
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import measure_raw, identify
from suites import CPX, CPY, READ, OUT

BITS = ["C_PY1_I", "C_SEL_P", "C_SELY1", "C_SELX", "C_COMP", "C_COMP_I", "C_HORIZ", "C_Y12"]
dut, obs = READ["PINY1_L00"]
path = os.path.join(OUT, "find_piny1.jsonl")
done = {json.loads(l)["name"] for l in open(path)} if os.path.exists(path) else set()
combos = sorted(itertools.product("01", repeat=len(BITS)), key=lambda c: (c.count("1"), c))
for c in combos:
    name = "".join(c)
    if name in done:
        continue
    extra = {b: v for b, v in zip(BITS, c) if v == "1"}
    F, info = measure_raw("fp_" + name, dut, CPX, dict(CPY, **extra), obs)
    best = identify(F) if F is not None else None
    open(path, "a").write(json.dumps({"name": name, "bits": extra, "best": best}) + chr(10))
    print(name, extra, best, flush=True)
    if best and not best[0].startswith("const"):
        print("SIGNAL", name, extra, best, flush=True)
        break
