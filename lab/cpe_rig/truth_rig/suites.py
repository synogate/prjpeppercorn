"""Measurement series of the helper-free rig (OUT2 only, no latch).  python suites.py s1 s2 ...  -> appends to <sim>/hw_data/<series>.jsonl
s1  OUT2 = MUXOUT: bridge, mux8 with selects, LUT1 words      s2  OUT2 = COMBOUT, C_FUNCTION = 0: LUT tree (L00, L01, L10 visible)
s3  OUT2 = COMBOUT, C_FUNCTION = 4: MX4b path               s4  OUT2 = CPOUT, C_FUNCTION = 0/4     s5  OUT2 = COMBOUT, other C_FUNCTION"""
import sys, os, json, random
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meas import measure, measure_raw, identify
from tt_rig import REPO

OUT = os.path.join(REPO, "schematics", "cpe", "sim", "hw_data")
B = lambda v, n: format(v, "0%db" % n)
PASS = {"INIT_L00": "1100", "INIT_L01": "1100", "INIT_L10": "1100", "INIT_L11": "1100", "INIT_L02": "1100", "INIT_L03": "1100", "INIT_L20": "1100"}


def rnd_lut(r):
    return {k: B(r.randrange(16), 4) for k in ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")}


def s1():
    r = random.Random(1)
    for k in range(8):
        yield "br_sn%d" % k, {"C_BR": "1", "C_SN": B(k, 3), "C_O2": "01"}
    for i in range(24):
        yield "br_inv%02d" % i, {"C_BR": "1", "C_SN": B(r.randrange(8), 3), "C_O2": "01", "INIT_L10": B(r.randrange(16), 4), "INIT_L11": B(r.randrange(16), 4)}
    for i in range(40):
        w = {"C_BR": "0", "C_SN": B(r.randrange(8), 3), "C_O2": "01", "C_2D_IN": str(r.randrange(2)), "INIT_L10": B(r.randrange(16), 4), "INIT_L11": B(r.randrange(16), 4)}
        for c in ("C_CPE_CLK", "C_CPE_EN", "C_CPE_RES"):
            w[c] = B(r.randrange(4), 2)
        yield "mx8_%02d" % i, w


def s1b():
    """mux8 (C_BR = 0), one parameter at a time"""
    base = {"C_BR": "0", "C_O2": "01", "C_SN": "000", "C_2D_IN": "0", "C_CPE_CLK": "00", "C_CPE_EN": "00", "C_CPE_RES": "00"}
    for c2 in "01":
        for k in range(8):
            yield "sel_c2d%s_sn%d" % (c2, k), dict(base, C_SN=B(k, 3), C_2D_IN=c2)
    for word in ("C_CPE_CLK", "C_CPE_EN", "C_CPE_RES"):
        for v in ("01", "10", "11"):
            for k in (0, 3):
                yield "lut1_%s_%s_sn%d" % (word[6:], v, k), dict(base, C_SN=B(k, 3), **{word: v})
    for name, v in (("L10_1111", {"INIT_L10": "1111"}), ("L11_1111", {"INIT_L11": "1111"}), ("L10_0101", {"INIT_L10": "0101"}), ("L11_1010", {"INIT_L11": "1010"})):
        yield "inv_" + name, dict(base, **v)


def s2():
    r = random.Random(2)
    for lut in ("INIT_L00", "INIT_L01", "INIT_L10"):
        for v in range(16):
            w = dict(PASS)
            w[lut] = B(v, 4)
            yield "per_%s_%s" % (lut[5:], B(v, 4)), dict(w, C_FUNCTION="000", C_O2="11")
    for i in range(24):
        yield "rnd%02d" % i, dict(rnd_lut(r), C_FUNCTION="000", C_O2="11")


def s3():
    r = random.Random(3)
    for i in range(40):
        yield "mx4_%02d" % i, dict(rnd_lut(r), C_FUNCTION="100", C_O2="11")


def s4():
    r = random.Random(4)
    for f in ("000", "100"):
        for i in range(12):
            w = dict(rnd_lut(r), C_FUNCTION=f, C_O2="10", C_HORIZ=str(r.randrange(2)))
            yield "cp_f%s_%02d" % (f, i), w


def s5():
    r = random.Random(5)
    for f in ("001", "010", "011", "101", "110", "111"):
        for i in range(6):
            yield "f%s_%02d" % (f, i), dict(rnd_lut(r), C_FUNCTION=f, C_O2="11", C_HORIZ=str(r.randrange(2)))


LATCH = {"C_O2": "00", "C_L_D": "1", "C_CPE_CLK": "11", "C_CPE_EN": "11", "C_CPE_RES": "11", "C_CPE_SET": "11"}      # transparent latch (RES/SET words 11 = no request, measured s6e/s6f) on OUT2 (pass-through only)


def s6():
    """latch as pass-through: MUXOUT (C_BR = 1, C_2D_IN = 0), inverted MUXOUT (C_BR = 1, C_2D_IN = 1), COMB2OUT (C_BR = 0, C_2D_IN = 1)"""
    r = random.Random(6)
    for k in range(8):
        yield "mux_sn%d" % k, dict(LATCH, C_BR="1", C_2D_IN="0", C_SN=B(k, 3))
    for k in range(8):
        yield "muxinv_sn%d" % k, dict(LATCH, C_BR="1", C_2D_IN="1", C_SN=B(k, 3))
    for i in range(16):
        yield "comb2_%02d" % i, dict({**rnd_lut(r), **LATCH}, C_BR="0", C_2D_IN="1", C_FUNCTION="000")


def s7():
    """latch, COMB1OUT (C_BR = 0, C_2D_IN = 0): L20 (^ carry)"""
    r = random.Random(7)
    for lut in ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20"):
        for v in range(16):
            w = dict(PASS)
            w[lut] = B(v, 4)
            yield "per_%s_%s" % (lut[5:], B(v, 4)), dict({**w, **LATCH}, C_BR="0", C_2D_IN="0", C_FUNCTION="000")
    for i in range(24):
        yield "rnd%02d" % i, dict({**rnd_lut(r), **LATCH}, C_BR="0", C_2D_IN="0", C_FUNCTION="000")
    for i in range(24):
        yield "mx4_%02d" % i, dict({**rnd_lut(r), **LATCH}, C_BR="0", C_2D_IN="0", C_FUNCTION="100")


def s6d():
    """latch diagnosis: which CLK / EN LUT1 words open the latch (MUXOUT = IN1 as source)"""
    for c in range(4):
        for e in range(4):
            yield "clk%s_en%s" % (B(c, 2), B(e, 2)), dict(LATCH, C_BR="1", C_2D_IN="0", C_SN="000", C_CPE_CLK=B(c, 2), C_CPE_EN=B(e, 2))


def s6e():
    """does the OUT2 register path reach the pad at all?  forced set / reset, flip-flop, latch, C_O2 variants (source MUXOUT = IN1)"""
    src = {"C_BR": "1", "C_2D_IN": "0", "C_SN": "000"}
    base = dict(src, C_O2="00", C_CPE_CLK="11", C_CPE_EN="11")
    yield "latch_set11", dict(base, C_L_D="1", C_CPE_SET="11")
    yield "latch_res11", dict(base, C_L_D="1", C_CPE_RES="11")
    yield "ff_set11", dict(base, C_L_D="0", C_CPE_SET="11")
    yield "ff_res11", dict(base, C_L_D="0", C_CPE_RES="11")
    yield "ff_clkpass", dict(src, C_O2="00", C_L_D="0", C_CPE_CLK="10", C_CPE_EN="11")
    yield "latch_clkpass", dict(src, C_O2="00", C_L_D="1", C_CPE_CLK="10", C_CPE_EN="11")
    yield "latch_clkpass_inv", dict(src, C_O2="00", C_L_D="1", C_CPE_CLK="01", C_CPE_EN="11")
    yield "latch_ensr", dict(base, C_L_D="1", C_EN_SR="1")
    yield "muxout_ref", dict(src, C_O2="01")


def s6f():
    """latch with set and reset LUT1 = 11 (what nextpnr writes for a plain flip-flop): CLK x EN words, source MUXOUT = IN1"""
    for l in "10":
        for c in range(4):
            for e in range(4):
                yield "ld%s_clk%s_en%s" % (l, B(c, 2), B(e, 2)), {"C_O2": "00", "C_L_D": l, "C_CPE_RES": "11", "C_CPE_SET": "11", "C_BR": "1", "C_2D_IN": "0", "C_SN": "000", "C_CPE_CLK": B(c, 2), "C_CPE_EN": B(e, 2)}


# ---- carry / propagate inputs of the DUT, read through the validated LUT paths (identification, no expectation) ----
CPX = {"C_BR": "1", "C_SN": "000", "C_O1": "01", "C_O2": "11", "INIT_L00": "1100", "INIT_L10": "1010", "C_CX_I": "1", "C_PX_I": "1"}   # COUTX = OUT1 = IN1, POUTX = OUT2 = IN2
CPY = {"C_BR": "1", "C_SN": "000", "C_O1": "01", "C_O2": "11", "INIT_L00": "1100", "INIT_L10": "1010", "C_CY1_I": "1", "C_CY2_I": "1", "C_PY2_I": "1"}  # OUT1 = IN1, OUT2 = IN2
READ = {   # DUT word sets reading one CP input into COMB2OUT (OUT2) or COMB1OUT (OUT1)
    "CINX":  ({"C_I2": "1", "INIT_L01": "1100", "INIT_L10": "1100", "C_O2": "11"}, "OUT2"),
    "PINY1_L00": ({"C_I1": "1", "INIT_L00": "1100", "INIT_L10": "1010", "C_O2": "11"}, "OUT2"),
    "PINX":  ({"C_I4": "1", "INIT_L03": "1100", "INIT_L11": "1100", "INIT_L20": "1100", "C_O1": "11"}, "OUT1"),
    "PINY1_L02": ({"C_I3": "1", "INIT_L02": "1100", "INIT_L11": "1010", "INIT_L20": "1100", "C_O1": "11"}, "OUT1"),
}


def s8():
    """which counter bit and polarity arrive at CINX / PINX / PINY1, for several settings of the two helpers"""
    for inp, (w, obs) in READ.items():
        for hn, hx, hy in (("default", {}, {}), ("selx1", {"C_SELX": "1"}, {"C_SELY1": "1", "C_SELY2": "1"}), ("hx_off", {"C_CX_I": "0", "C_PX_I": "0"}, {"C_CY1_I": "0", "C_CY2_I": "0", "C_PY2_I": "0"})):
            yield "%s_%s" % (inp, hn), w, dict(CPX, **hx), dict(CPY, **hy), obs


def s9():
    """carry in through CINX (C_HORIZ = 1): comb1_out = l20 ^ CINX (C_FUNCTION 1, 2, 7), comb2_out = l10 ^ (l11 ? CINX : l02) (C_FUNCTION 2); CINX = x11 from the west helper.
    yields (name, words, cp) ; observed COMB1OUT on OUT1 and COMB2OUT on OUT2"""
    r = random.Random(9)
    for f in ("001", "010", "111"):
        zero = {k: "0000" for k in ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")}
        cfgs = [("zero", zero)] + [("rnd%d" % i, rnd_lut(r)) for i in range(8)]
        for n, luts in cfgs:
            for obs, cw in (("OUT1", {"C_O1": "11"}), ("OUT2", {"C_O2": "11"})):
                yield "f%s_%s_%s" % (f, n, obs), dict(luts, C_FUNCTION=f, C_HORIZ="1", **cw), obs


def s10():
    """C_EN_CIN (C_FUNCTION = 101): l03 = l03_lut | (C_EN_CIN & carry_in), carry_in = CINX (C_HORIZ = 1) = x11.
    pass: L11 and L20 pass D1, so COMB1OUT (OUT1) = l03; every INIT_L03; controls with C_FUNCTION 000; random trees on OUT1 and OUT2"""
    r = random.Random(10)
    passw = {"INIT_L00": "0000", "INIT_L01": "0000", "INIT_L02": "0000", "INIT_L10": "0000", "INIT_L11": "1100", "INIT_L20": "1100"}
    for v in range(16):
        yield "pass_f101_L03_%s" % B(v, 4), dict(passw, INIT_L03=B(v, 4), C_FUNCTION="101", C_HORIZ="1", C_O1="11"), "OUT1"
    for v in (1, 6, 9, 14):
        yield "pass_f000_L03_%s" % B(v, 4), dict(passw, INIT_L03=B(v, 4), C_FUNCTION="000", C_HORIZ="1", C_O1="11"), "OUT1"
    for i in range(8):
        luts = rnd_lut(r)
        yield "rnd%d_OUT1" % i, dict(luts, C_FUNCTION="101", C_HORIZ="1", C_O1="11"), "OUT1"
        yield "rnd%d_OUT2" % i, dict(luts, C_FUNCTION="101", C_HORIZ="1", C_O2="11"), "OUT2"


if __name__ == "__main__":
    tag, stride, names = "", 1, []
    for a in sys.argv[1:]:
        if a.startswith("--tag="):
            tag = a[6:] + "_"
        elif a.startswith("--stride="):
            stride = int(a[9:])
        else:
            names.append(a)
    for s in names:
        path = os.path.join(OUT, tag + s + ".jsonl")
        done = {json.loads(l)["name"] for l in open(path)} if os.path.exists(path) else set()
        for i, item in enumerate(globals()[s]()):
            name = item[0]
            if name in done or i % stride:
                continue
            if len(item) == 5:                       # identification series: (name, dut, cpinx, cpiny, obs)
                F, info = measure_raw(tag + s + "_" + name, item[1], item[2], item[3], item[4])
                rec = {"name": name, "words": item[1], "cpinx": item[2], "cpiny": item[3], "obs": item[4], "info": info}
                if F is not None:
                    rec["F"] = format(sum(b << i for i, b in enumerate(F)), "x")
                    rec["best"] = identify(F)
                open(path, "a").write(json.dumps(rec) + chr(10))
                print(tag + s, name, rec.get("best"), flush=True)
                continue
            w = item[1]
            F, info, m = measure(tag + s + "_" + name, w, CPX if s in ("s9", "s10") else None, None, item[2] if len(item) == 3 else "OUT2", None, {"CINX": 11} if s in ("s9", "s10") else None)
            retried = 0
            if m:
                F2, info2, m2 = measure(tag + s + "_" + name + "_retry", w, CPX if s in ("s9", "s10") else None, None, item[2] if len(item) == 3 else "OUT2", None, {"CINX": 11} if s in ("s9", "s10") else None)
                retried = 1
                if m2 is not None and m2 < m:
                    F, info, m = F2, info2, m2
            rec = {"name": name, "words": w, "info": info, "mismatch": m, "retried": retried}
            if F is not None:
                rec["F"] = format(sum(b << i for i, b in enumerate(F)), "x")
            open(path, "a").write(json.dumps(rec) + chr(10))
            print(tag + s, name, "mismatch", m, "(retried)" if retried else "", flush=True)
