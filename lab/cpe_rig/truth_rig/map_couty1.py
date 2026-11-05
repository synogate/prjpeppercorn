"""COUTY1 (C_HORIZ = 0, read through CPOUT1: C_C_P = 1, C_O1 = 10 on OUT1) over the same grid as COUTX in map_coutx.py (parallel check, C_MULT = 0).
Environment as in map_coutx.ENV, except C_O1 = 10 (OUT1 now shows CPOUT1); route data for COUTY1: {C_SEL_C, C_SELY1} = 00 -> OUT2 (= ~x7).  CINY1 = x14.
    python map_couty1.py y1 y3   ->  hw_data/s18.jsonl"""
import sys, os, json, itertools, random
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import measure_raw
from map_coutx import ENV, CPX, CPYP, B
from suites import OUT

YENV = dict(ENV, C_O1="10", C_C_P="1", C_HORIZ="0")


def configs(series):
    if series == "y1":
        for f, cy in itertools.product((0, 1, 2, 4, 5, 6, 7), "01"):
            yield "y1_f%d_cy%s" % (f, cy), dict(YENV, C_FUNCTION=B(f, 3), C_CY1_I=cy)
    else:
        r = random.Random(18)
        for f in (1, 2, 6):
            for i in range(12):
                luts = {k: B(r.randrange(16), 4) for k in ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")}
                yield "y3_f%d_%02d" % (f, i), dict(YENV, **dict(luts, C_FUNCTION=B(f, 3), C_CY1_I="0"))


if __name__ == "__main__":
    path = os.path.join(OUT, "s18.jsonl")
    done = {json.loads(l)["name"] for l in open(path)} if os.path.exists(path) else set()
    for s in sys.argv[1:]:
        for name, w in configs(s):
            if name in done:
                continue
            F, info = measure_raw("s18_" + name, w, CPX, CPYP, "OUT1")
            open(path, "a").write(json.dumps({"name": name, "words": w, "info": info, "F": format(sum(b << i for i, b in enumerate(F)), "x")}) + chr(10))
            print(name, info.get("unsure_states"), flush=True)
