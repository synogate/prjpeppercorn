"""The selector (east neighbour of the DUT, X147Y19) as a reader of the DUT's COUTX: its CINX is read through C_I2 -> L01 -> L10 -> COMB2OUT -> OUT2 (the wire nextpnr routed to the pad).
    from east import measure_east"""
import sys, os, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import edits_for, sel_cell, load, capture, extract, identify
from suites import CPX, OUT

EAST_CINX = {"C_I2": "1", "INIT_L01": "1100", "INIT_L10": "1100", "C_O2": "11"}      # selector words: CINX (= COUTX of the DUT) on OUT2


def measure_east(name, dut_words, cpinx=CPX, cpiny=None, east=EAST_CINX, extra=None):
    e = edits_for(dut_words, cpinx, cpiny, "OUT2", extra)
    sx, sy = sel_cell()
    e[(sx, sy, "C_BR")] = None
    e[(sx, sy, "C_SN")] = None
    for k, v in east.items():
        e[(sx, sy, k)] = v
    load(name, e)
    r = capture()
    F, info = extract(r[0], r[1], r[2])
    return F, info


if __name__ == "__main__":
    zero = {k: "0000" for k in ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")}
    out = open(os.path.join(OUT, "s16.jsonl"), "a")
    cases = (("coutx_passes_cinx", dict(zero, C_FUNCTION="000", C_HORIZ="0", C_CX_I="0")),
             ("coutx_route_out1_x0", dict(zero, C_FUNCTION="000", C_HORIZ="0", C_CX_I="1", C_SELX="0", C_BR="1", C_SN="000", C_O1="01")))
    for name, w in cases:
        F, info = measure_east("s16_" + name, w)
        best = identify(F)
        print(name, "identify:", best, flush=True)
        out.write(json.dumps({"name": name, "words": w, "best": best, "F": format(sum(b << i for i, b in enumerate(F)), "x")}) + chr(10))
