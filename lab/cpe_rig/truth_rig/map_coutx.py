"""Map the COUTX generator: read COUTX of the DUT in the east neighbour (selector as reader) over config grids with distinguishable data sources.
Environment: l00 = x0, l01 = x2, l02 = x4, l03 = x6, l10 = x2, l11 = x6 (pass-through LUTs), comp_out = comb2 ^ comb1 (INIT_L30 = 0110),
OUT1 = x7 (MUXOUT of IN8 via the bridge), OUT2 = ~x7 (inverted MUXOUT through the transparent latch), CINX = x11, CINY2 = x13, CINY1 = x14.
    python map_coutx.py e1 e2   ->  hw_data/s17.jsonl"""
import sys, os, json, itertools
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from east import measure_east
from suites import CPX, CPY, OUT

CPYP = dict(CPY, C_PY1_I="1")
ENV = {"INIT_L00": "1010", "INIT_L01": "1010", "INIT_L02": "1010", "INIT_L03": "1010", "INIT_L10": "1100", "INIT_L11": "1100", "INIT_L20": "1100", "INIT_L30": "0110",
       "C_BR": "1", "C_SN": "111", "C_O1": "01", "C_O2": "00", "C_L_D": "1", "C_CPE_CLK": "11", "C_CPE_EN": "11", "C_CPE_RES": "11", "C_CPE_SET": "11", "C_2D_IN": "1"}
B = lambda v, n: format(v, "0%db" % n)


def configs(series):
    if series == "e1":
        for f, h, cx in itertools.product(range(8), "01", "01"):
            yield "e1_f%d_h%s_cx%s" % (f, h, cx), dict(ENV, C_FUNCTION=B(f, 3), C_HORIZ=h, C_CX_I=cx)
    elif series == "e3":      # random LUT trees: learn the propagate / generate functions (C_HORIZ = 1, C_CX_I = 0 so that COUTX = P ? G : CINX)
        import random
        r = random.Random(17)
        for f in (1, 2, 6):
            for i in range(12):
                luts = {k: B(r.randrange(16), 4) for k in ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")}
                yield "e3_f%d_%02d" % (f, i), dict(ENV, **dict(luts, C_FUNCTION=B(f, 3), C_HORIZ="1", C_CX_I="0"))
    else:
        for sc, sx, y12 in itertools.product("01", "01", "01"):
            yield "e2_sc%s_sx%s_y%s" % (sc, sx, y12), dict(ENV, C_FUNCTION="000", C_HORIZ="0", C_CX_I="1", C_SEL_C=sc, C_SELX=sx, C_Y12=y12)


if __name__ == "__main__":
    path = os.path.join(OUT, "s17.jsonl")
    done = {json.loads(l)["name"] for l in open(path)} if os.path.exists(path) else set()
    for s in sys.argv[1:]:
        for name, w in configs(s):
            if name in done:
                continue
            F, info = measure_east("s17_" + name, w, CPX, CPYP)
            open(path, "a").write(json.dumps({"name": name, "words": w, "info": info, "F": format(sum(b << i for i, b in enumerate(F)), "x")}) + chr(10))
            print(name, info.get("unsure_states"), flush=True)
