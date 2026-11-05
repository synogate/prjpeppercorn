"""Map the POUTX generator: POUTX of the DUT is read as PINX in the east neighbour (selector as reader): C_I4 = 1 -> L03 -> L11 -> L20 (pass D1) -> COMB1OUT -> transparent latch on OUT2.
Environment as map_coutx.ENV (OUT1 = x7, OUT2 = ~x7, CINX = x11, PINX = x12, helper variants for PINY1 / PINY2).
    python map_poutx.py p0 p1   ->  hw_data/s21.jsonl      p0: selftest of the reader, p1: grid of C_FUNCTION (0, 1, 3), C_HORIZ, C_COMP, C_PX_I, C_COMP_I, INIT_L30"""
import sys, os, json, itertools
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from east import measure_east
from meas import identify
from map_coutx import ENV, CPX, CPYP, B
from suites import OUT

EAST_PINX = {"C_I4": "1", "INIT_L03": "1100", "INIT_L11": "1100", "INIT_L20": "1100", "C_O2": "00", "C_L_D": "1", "C_CPE_CLK": "11", "C_CPE_EN": "11", "C_CPE_RES": "11", "C_CPE_SET": "11", "C_2D_IN": "0"}


def configs(series):
    if series == "p0":
        yield "p0_route_out2", dict(ENV, C_FUNCTION="000", C_PX_I="1", C_SELX="0")          # POUTX = OUT2 = ~x7
        yield "p0_route_out1", dict(ENV, C_FUNCTION="000", C_PX_I="1", C_SELX="1")          # POUTX = OUT1 = x7
        yield "p0_pass_pinx", dict(ENV, C_FUNCTION="000", C_PX_I="0")                       # POUTX = PINX = x12 (west helper)
    else:
        for f, h, comp, pxi, compi, l30 in itertools.product((0, 1, 3), "01", "01", "01", "01", ("0110", "0000", "1111")):
            yield "p1_f%d_h%s_comp%s_px%s_ci%s_l%s" % (f, h, comp, pxi, compi, l30), dict(ENV, C_FUNCTION=B(f, 3), C_HORIZ=h, C_COMP=comp, C_PX_I=pxi, C_COMP_I=compi, INIT_L30=l30)


if __name__ == "__main__":
    path = os.path.join(OUT, "s21.jsonl")
    done = {json.loads(l)["name"] for l in open(path)} if os.path.exists(path) else set()
    for s in sys.argv[1:]:
        for name, w in configs(s):
            if name in done:
                continue
            F, info = measure_east("s21_" + name, w, CPX, CPYP, EAST_PINX)
            rec = {"name": name, "words": w, "info": info, "F": format(sum(b << i for i, b in enumerate(F)), "x")}
            if s == "p0":
                rec["best"] = identify(F)
            open(path, "a").write(json.dumps(rec) + chr(10))
            print(name, rec.get("best", info.get("unsure_states")), flush=True)
