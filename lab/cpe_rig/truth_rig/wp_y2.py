"""Work package wp_y2: COUTY2 / POUTY2 as outputs of a CPE (the south helper X146Y18), read at the DUT as CINY2 / PINY2.

Open points (S15 only measured the routing codes 00 / 01 with C_CY2_I = 1 / C_PY2_I = 1 and C_SELY2 = 0 / 1):
  (1) pass-through at C_CY2_I = 0 (COUTY2 = CINY2) and C_PY2_I = 0 (POUTY2 = PINY2)   groups A, B
  (2) routing multiplexer codes 10 (~comp_out of the helper) and 11 (CINX / PINX of the helper)   groups C, D (all four codes, two or three helper variants)
  (3) C_MULT = 1 (helper C_FUNCTION = 3): COUTY2 = coy2_a?, POUTY2 behaviour, coy2_s role   group F;   POUTY2 compare branch (C_COMP)   group E

Rig (all of it is made visible by patches of CPEs that nextpnr does not use for anything the CP lines touch, see the comment block KNOWN SOURCES):
  reader  R_C: DUT words of S15 with C_C_P = 0 -> OUT2 = CPOUT2 = COUTX = CINY2 (= COUTY2 of the helper);  R_P: C_C_P = 1 -> POUTX = PINY2 (= POUTY2 of the helper).  Reader sel_OUT2.
  model   F = COUTY2 / POUTY2 of cpe.v evaluated for the *helper* with its own inputs (IN1..IN4 = x13..x16, IN5..IN8 = GND, CP inputs as the sources below).

KNOWN SOURCES (the helper's CP inputs are not driven by the design; they come from two neighbours that are used as counter flops, and from a free CPE):
  X146Y17 (south of the helper) holds the counter flop x0 in its upper half (OUT2 = x0); its lower half is unused, nothing reads its OUT1, L20, L30 or any CP word.  Only CP words are added to it:
          COUTY1, COUTY2, POUTY1, POUTY2 of X146Y17 = CINY1, CINY2, PINY1, PINY2 of the helper.  Per line the routing multiplexer gives x0 (OUT2), a constant through ~comp_out
          (INIT_L30 = 0000 -> 1, 1111 -> 0, the comparator inputs do not matter) or a constant on OUT1 (C_O1 = 11, INIT_L20 = 0000 / 1111).  The words that nextpnr wrote for the flop stay.
  X145Y18 (west of the helper) holds the counter flop x3 in its upper half (OUT2 = x3) and the GND driver of the design in its lower half (OUT1 = 0, must stay untouched).  Only CP words are added:
          COUTX / POUTX of X145Y18 = CINX / PINX of the helper = x3, 0 (OUT1 = GND) or the constant ~comp_out.
  X146Y16 (south of X146Y17): free (no word of nextpnr, no cell in pnr.json).  Used as a source of a constant 1 (~comp_out, INIT_L30 = 0000) that reaches the helper through X146Y17 and the helper
          (two pass-throughs with nothing patched in X146Y17): configs a4_*, b4_*.
  Unspecified lines of the helper are 0 in the model (S11: an undriven CINY1 is 0); `python wp_y2.py check` proves that the helper's output of every config does not depend on them.
  IN5..IN8 of the helper are wired to the design's GND net in pnr.json (not 'unconnected'); the model takes 0 (UNC).  They only matter through the multiplier terms IN5 & PINY2, IN8 & PINY2
  (coy2_a = hi ? IN8 & PINY2 : IN5 & PINY2 is 0 when both are 0).  analyze() scans the 16 values of IN5..IN8 for a deviating config.

Dry run:  python wp_runner.py wp_y2 --dry      Checks:  python wp_y2.py check | selftest
"""
import sys, os, random, json, itertools
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_common import ENV, CPYP, model_eval, explain, x, NS, S

B = lambda v, n: format(v, "0%db" % n)
UNC = {"IN5": 0, "IN6": 0, "IN7": 0, "IN8": 0}          # helper's IN5..IN8: the GND net of the design
HELPER = (146, 18)
Y17, X145, Y16 = (146, 17), (145, 18), (146, 16)
LINE_PORT = {"CY1": "CINY1", "CY2": "CINY2", "PY1": "PINY1", "PY2": "PINY2", "CX": "CINX", "PX": "PINX"}
VALS_Y = ("x0", "0", "1")
VALS_X = ("x3", "0", "1")

# ---------------------------------------------------------------- the DUT readers (S15)
DUT_R = dict(ENV, C_FUNCTION="000", C_HORIZ="1", C_CX_I="1", C_PX_I="1", C_SEL_C="1", C_SEL_P="1", C_SELX="1", C_Y12="1", C_O2="10")
DUT_WORDS = {"C": dict(DUT_R, C_C_P="0"), "P": dict(DUT_R, C_C_P="1")}
TARGET = {"C": "COUTY2", "P": "POUTY2"}


# ---------------------------------------------------------------- source patches
def solve_y17(spec):
    """spec {line: 'x0'|'0'|'1'} for lines CY1 CY2 PY1 PY2 -> words to add to X146Y17 (fewest words)"""
    best = None
    for sc, sp, s1, s2, k1, kc in itertools.product((0, 1), repeat=6):
        table = {"CY1": {(0, 0): "x0", (0, 1): "o1", (1, 0): "nc"}.get((sc, s1)), "CY2": {(0, 0): "o1", (0, 1): "x0", (1, 0): "nc"}.get((sc, s2)),
                 "PY1": {(0, 0): "o1", (0, 1): "x0", (1, 0): "nc"}.get((sp, s1)), "PY2": {(0, 0): "x0", (0, 1): "o1", (1, 0): "nc"}.get((sp, s2))}
        ok, o1, nc = True, False, False
        for ln, v in spec.items():
            t = table[ln]
            if t is None:
                ok = False
                break
            if t == "o1":
                o1, t = True, str(k1)
            elif t == "nc":
                nc, t = True, str(1 - kc)
            if t != v:
                ok = False
                break
        if not ok:
            continue
        w = {"C_%s_I" % ln: "1" for ln in spec}
        for k, v in (("C_SEL_C", sc), ("C_SEL_P", sp), ("C_SELY1", s1), ("C_SELY2", s2)):
            if v:
                w[k] = "1"
        if o1:
            w.update(C_O1="11", INIT_L20=B(15 * k1, 4))
        if nc:
            w["INIT_L30"] = B(15 * kc, 4)
        score = len(w) + 2 * o1
        if best is None or score < best[0]:
            best = (score, w)
    if best is None:
        raise ValueError("no X146Y17 setting for %s" % (spec,))
    return best[1]


def solve_x145(spec):
    """spec {'CX': 'x3'|'0'|'1', 'PX': ...} -> words to add to X145Y18 (OUT1 = GND = 0, OUT2 = x3)"""
    best = None
    for sc, sp, sx, kc in itertools.product((0, 1), repeat=4):
        table = {"CX": {(0, 0): "g", (0, 1): "x3", (1, 0): "nc"}.get((sc, sx)), "PX": {(0, 0): "x3", (0, 1): "g", (1, 0): "nc"}.get((sp, sx))}
        ok, nc = True, False
        for ln, v in spec.items():
            t = table[ln]
            if t is None:
                ok = False
                break
            if t == "g":
                t = "0"
            elif t == "nc":
                nc, t = True, str(1 - kc)
            if t != v:
                ok = False
                break
        if not ok:
            continue
        w = {"C_%s_I" % ln: "1" for ln in spec}
        if "CX" in spec and sc:
            w["C_SEL_C"] = "1"
        if "PX" in spec and sp:
            w["C_SEL_P"] = "1"
        if sx and spec:
            w["C_SELX"] = "1"
        if nc:
            w["INIT_L30"] = B(15 * kc, 4)
        if best is None or len(w) < best[0]:
            best = (len(w), w)
    if best is None:
        raise ValueError("no X145Y18 setting for %s" % (spec,))
    return best[1]


def y16_words(lines, v):
    """X146Y16 (free CPE): the given lines (CY1 CY2 PY1 PY2) carry the constant v through the routing multiplexer code 10 (~comp_out)"""
    w = {"INIT_L30": B(0 if v == "1" else 15, 4)}
    for ln in lines:
        w["C_%s_I" % ln] = "1"
        w["C_SEL_C" if ln[0] == "C" else "C_SEL_P"] = "1"
    return w


# ---------------------------------------------------------------- config construction
def make(name, grp, rd, hw, y17=None, x145=None, y16=None, desc=""):
    """rd 'C' (read COUTY2 as CINY2) or 'P' (read POUTY2 as PINY2); hw = words of the helper; y17 / x145 / y16 = source specs (see solve_*, y16 = (lines, const))"""
    extra = {}
    if y17:
        extra.update({(Y17[0], Y17[1], k): v for k, v in solve_y17(y17).items()})
    if x145:
        extra.update({(X145[0], X145[1], k): v for k, v in solve_x145(x145).items()})
    if y16:
        extra.update({(Y16[0], Y16[1], k): v for k, v in y16_words(*y16).items()})
    cfg = {"name": name, "reader": "sel_OUT2", "words": dict(DUT_WORDS[rd]), "cpiny": dict(hw),
           "meta": {"grp": grp, "rd": rd, "y17": dict(y17 or {}), "x145": dict(x145 or {}), "y16": [list(y16[0]), y16[1]] if y16 else None, "desc": desc}}
    if extra:
        cfg["extra"] = extra
    return cfg


def h0(**kw):
    """south helper of S15: OUT1 = x13, OUT2 = x14 (the CPYP words), plus overrides"""
    return dict(CPYP, **kw)


def h1(**kw):
    """other helper variant: OUT1 = IN3 = x15 (C_SN = 010), OUT2 = IN4 = x16 (L01 -> L10 pass D1)"""
    return dict(CPYP, C_SN="010", INIT_L00="0000", INIT_L01="1100", INIT_L10="1100", **kw)


def rand_hw(rng, f, h, **kw):
    """random helper: LUT tree (L02 / L03 depend only on PINY1 / PINX, so IN5..IN8 never matter), C_O1 in {MUXOUT, COMB1OUT}, C_O2 = COMB2OUT"""
    hw = {"C_BR": "1", "C_SN": B(rng.randrange(4), 3), "C_O1": rng.choice(["01", "11"]), "C_O2": "11", "C_FUNCTION": B(f, 3), "C_HORIZ": str(h),
          "INIT_L02": rng.choice(["1100", "0011"]), "INIT_L03": rng.choice(["1100", "0011"]), "C_I1": rng.choice("01"), "C_I2": rng.choice("01"), "C_I3": "1", "C_I4": "1"}
    for k in ("INIT_L00", "INIT_L01", "INIT_L10", "INIT_L11", "INIT_L20", "INIT_L30"):
        hw[k] = B(rng.randrange(16), 4)
    hw.update(kw)
    return hw


def rand_srcs(rng, y17_fixed=None, x145_fixed=None):
    """random feasible values for all four Y lines and both X lines (fixed ones kept)"""
    for _ in range(500):
        y = {ln: (y17_fixed or {}).get(ln) or rng.choice(VALS_Y) for ln in ("CY1", "CY2", "PY1", "PY2")}
        xx = {ln: (x145_fixed or {}).get(ln) or rng.choice(VALS_X) for ln in ("CX", "PX")}
        try:
            solve_y17(y)
            solve_x145(xx)
            return y, xx
        except ValueError:
            continue
    raise ValueError("no feasible source assignment for %s %s" % (y17_fixed, x145_fixed))


def varying(build, tries=40):
    """call build() (draws from rng) until the model output is not constant (a constant output cannot tell routes apart)"""
    for _ in range(tries):
        cfg = build()
        F = model_F(cfg)
        if 0 < int(F.sum()) < NS:
            return cfg
    return cfg


def configs():
    rng = random.Random(20250611)
    C = []
    add = C.append

    # ---- A: COUTY2 pass-through (C_CY2_I = 0), reader R_C; source X146Y17.COUTY2 (leak detector: x0 is not one of the helper's own signals)
    for v in ("0", "1"):
        add(make("a1_pass_src%s" % v, "A", "C", h0(C_CY2_I="0"), y17={"CY2": v}, desc="C_CY2_I=0, CINY2 = const %s" % v))
    for sc, s2 in itertools.product("01", repeat=2):
        add(make("a2_pass_x0_sc%s_sy%s" % (sc, s2), "A", "C", h0(C_CY2_I="0", C_SEL_C=sc, C_SELY2=s2), y17={"CY2": "x0"}, desc="C_CY2_I=0 CINY2 = x0, C_SEL_C=%s C_SELY2=%s (must not matter)" % (sc, s2)))
    add(make("a2_pass_x0_h1", "A", "C", h1(C_CY2_I="0"), y17={"CY2": "x0"}, desc="C_CY2_I=0, helper variant h1 (OUT = x15 / x16)"))
    for f, h in ((1, 0), (1, 1), (2, 0), (2, 1), (6, 0), (6, 1), (4, 0), (5, 0), (7, 0)):
        def b(f=f, h=h):
            y, xx = rand_srcs(rng, {"CY2": "x0"})
            return make("a3_pass_f%d_h%d" % (f, h), "A", "C", rand_hw(rng, f, h, C_CY2_I="0", C_PY2_I="1", C_CY1_I="1"), y17=y, x145=xx,
                        desc="C_CY2_I=0 with C_FUNCTION=%d, C_HORIZ=%d, random LUTs (adder?) y17=%s" % (f, h, y))
        add(varying(b))
    for nm, hw in (("h0", h0(C_CY2_I="0")), ("h1", h1(C_CY2_I="0"))):
        add(make("a4_pass2hop_%s" % nm, "A", "C", hw, y16=(["CY2"], "1"), desc="X146Y16 COUTY2 = 1 -> X146Y17 (nothing patched) passes -> helper passes: expect 1"))

    # ---- B: POUTY2 pass-through (C_PY2_I = 0, C_MULT = 0), reader R_P
    for v in ("0", "1"):
        add(make("b1_pass_src%s" % v, "B", "P", h0(C_PY2_I="0"), y17={"PY2": v}, desc="C_PY2_I=0, PINY2 = const %s" % v))
    for sp, s2 in itertools.product("01", repeat=2):
        add(make("b2_pass_x0_sp%s_sy%s" % (sp, s2), "B", "P", h0(C_PY2_I="0", C_SEL_P=sp, C_SELY2=s2), y17={"PY2": "x0"}, desc="C_PY2_I=0 PINY2 = x0, C_SEL_P=%s C_SELY2=%s (must not matter)" % (sp, s2)))
    add(make("b2_pass_x0_h1", "B", "P", h1(C_PY2_I="0"), y17={"PY2": "x0"}, desc="C_PY2_I=0, helper variant h1"))
    for f, h in ((1, 0), (2, 1), (6, 0), (4, 0), (5, 1), (7, 0)):
        def b(f=f, h=h):
            y, xx = rand_srcs(rng, {"PY2": "x0"})
            return make("b3_pass_f%d_h%d" % (f, h), "B", "P", rand_hw(rng, f, h, C_PY2_I="0", C_CY2_I="1", C_PY1_I="1"), y17=y, x145=xx,
                        desc="C_PY2_I=0 with C_FUNCTION=%d, C_HORIZ=%d, random LUTs y17=%s" % (f, h, y))
        add(varying(b))
    for nm, hw in (("h0", h0(C_PY2_I="0")), ("h1", h1(C_PY2_I="0"))):
        add(make("b4_pass2hop_%s" % nm, "B", "P", hw, y16=(["PY2"], "1"), desc="X146Y16 POUTY2 = 1 -> X146Y17 passes -> helper passes: expect 1"))

    # ---- C: COUTY2 routing multiplexer {C_SEL_C, C_SELY2}: 00 OUT1, 01 OUT2, 10 ~comp_out, 11 CINX (C_CY2_I = 1); CINY2 = x0 is the leak detector
    for hn, hf in (("h0", h0), ("h1", h1)):
        for code in ("00", "01", "10", "11"):
            xx = {"CX": "x3" if hn == "h0" else "1"} if code == "11" else None
            hw = hf(C_CY2_I="1", C_SEL_C=code[0], C_SELY2=code[1], **({"INIT_L30": "0110"} if code == "10" else {}))
            add(make("c1_route_%s_%s" % (hn, code), "C", "C", hw, y17={"CY2": "x0"}, x145=xx, desc="COUTY2 routing code %s (%s)" % (code, {"00": "OUT1", "01": "OUT2", "10": "~comp_out", "11": "CINX"}[code])))
    for code in ("00", "01", "10", "11"):
        for k in range(2):
            def b(code=code, k=k):
                f = rng.choice((0, 5, 7))
                hw = rand_hw(rng, f, rng.choice((0, 1)), C_CY2_I="1", C_SEL_C=code[0], C_SELY2=code[1])
                y, xx = rand_srcs(rng, {"CY2": "x0"}, {"CX": "x3"} if code == "11" else None)
                return make("c2_route_%s_%d" % (code, k), "C", "C", hw, y17=y, x145=xx, desc="random helper f=%d code %s y17=%s x145=%s" % (f, code, y, xx))
            add(varying(b))
    add(make("c3_route_11_cinx0", "C", "C", h0(C_CY2_I="1", C_SEL_C="1", C_SELY2="1"), y17={"CY2": "x0"}, x145={"CX": "0", "PX": "x3"}, desc="code 11 with CINX = 0 (X145Y18 OUT1 = GND)"))
    for f, h in ((1, 0), (2, 0), (6, 0), (1, 1), (2, 1), (6, 1)):
        def b(f=f, h=h):
            code = rng.choice(("00", "01", "10"))
            y, xx = rand_srcs(rng, {"CY2": "x0"})
            return make("c4_route_f%d_h%d" % (f, h), "C", "C", rand_hw(rng, f, h, C_CY2_I="1", C_SEL_C=code[0], C_SELY2=code[1]), y17=y, x145=xx,
                        desc="adder f=%d C_HORIZ=%d, C_CY2_I=1 code %s: route or generate (COUTY1 gives generate)? y17=%s" % (f, h, code, y))
        add(varying(b))

    # ---- D: POUTY2 routing multiplexer {C_SEL_P, C_SELY2}: 00 OUT2, 01 OUT1, 10 ~comp_out, 11 PINX (C_PY2_I = 1); PINY2 = x0 leak detector
    for hn, hf in (("h0", h0), ("h1", h1)):
        for code in ("00", "01", "10", "11"):
            xx = {"PX": "x3" if hn == "h0" else "1"} if code == "11" else None
            hw = hf(C_PY2_I="1", C_SEL_P=code[0], C_SELY2=code[1], **({"INIT_L30": "0110"} if code == "10" else {}))
            add(make("d1_route_%s_%s" % (hn, code), "D", "P", hw, y17={"PY2": "x0"}, x145=xx, desc="POUTY2 routing code %s (%s)" % (code, {"00": "OUT2", "01": "OUT1", "10": "~comp_out", "11": "PINX"}[code])))
    for code in ("00", "01", "10", "11"):
        for k in range(2):
            def b(code=code, k=k):
                f = rng.choice((0, 5, 7))
                hw = rand_hw(rng, f, rng.choice((0, 1)), C_PY2_I="1", C_SEL_P=code[0], C_SELY2=code[1])
                y, xx = rand_srcs(rng, {"PY2": "x0"}, {"PX": "x3"} if code == "11" else None)
                return make("d2_route_%s_%d" % (code, k), "D", "P", hw, y17=y, x145=xx, desc="random helper f=%d code %s y17=%s x145=%s" % (f, code, y, xx))
            add(varying(b))
    add(make("d3_route_11_pinx0", "D", "P", h0(C_PY2_I="1", C_SEL_P="1", C_SELY2="1"), y17={"PY2": "x0"}, x145={"CX": "x3", "PX": "0"}, desc="code 11 with PINX = 0 (X145Y18 OUT1 = GND)"))

    # ---- E: POUTY2 with the comparator active (POUTY1 has the compare branch: select = C_PY1_I | (C_COMP & ~C_HORIZ & L30), value ~C_COMP_I)
    for pi, ci, h in ((0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0), (0, 0, 1), (0, 1, 1)):
        def b(pi=pi, ci=ci, h=h):
            y, xx = rand_srcs(rng, {"PY2": "x0"})
            hw = rand_hw(rng, 0, h, C_PY2_I=str(pi), C_COMP="1", C_COMP_I=str(ci), C_SEL_P="0", C_SELY2="1")
            hw["INIT_L30"] = "0110"
            return make("e1_cmp_py%d_ci%d_h%d" % (pi, ci, h), "E", "P", hw, y17=y, x145=xx, desc="C_COMP=1 C_COMP_I=%d C_PY2_I=%d C_HORIZ=%d: model has no compare branch for POUTY2" % (ci, pi, h))
        add(varying(b))

    # ---- F: multiplier (C_FUNCTION = 3); model: COUTY2 = C_CY2_I ? coy2_a : CINY2, POUTY2 = py2_route whenever C_MULT (C_PY2_I irrelevant)
    for rd in ("C", "P"):
        for cyi in (0, 1):
            for h in (0, 1):
                for k in range(2):
                    def b(rd=rd, cyi=cyi, h=h, k=k):
                        code = rng.choice(("00", "01", "10"))
                        fixed = {"PY2": "0"}
                        if rd == "C" and cyi == 0:
                            fixed["CY2"] = "x0"
                        if rd == "P":
                            fixed = {"PY2": "x0"}
                        y, xx = rand_srcs(rng, fixed)
                        hw = rand_hw(rng, 3, h, C_CY2_I=str(cyi) if rd == "C" else "1", C_PY2_I=str(cyi) if rd == "P" else "1", C_SEL_C=code[0], C_SEL_P=code[0], C_SELY2=code[1])
                        return make("f1_mult_%s_i%d_h%d_%d" % (TARGET[rd][:5].lower(), cyi, h, k), "F", rd, hw, y17=y, x145=xx,
                                    desc="C_MULT=1 %s: %s_I=%d C_HORIZ=%d code %s y17=%s" % (TARGET[rd], "C_CY2" if rd == "C" else "C_PY2", cyi, h, code, y))
                    add(varying(b) if (rd == "P" or cyi == 0) else b())
    for k in range(4):     # PINY2 = x0 makes the partial products visible if IN5 / IN8 are not 0
        y, xx = rand_srcs(rng, {"PY2": "x0", "CY1": "x0", "CY2": rng.choice(("0", "1"))})
        hw = rand_hw(rng, 3, k % 2, C_CY2_I="1", C_PY2_I="1", C_SEL_C="0", C_SELY2="0")
        add(make("f2_mult_pp_%d" % k, "F", "C", hw, y17=y, x145=xx, desc="C_MULT=1 COUTY2 with PINY2 = x0 (IN5 & PINY2, IN8 & PINY2 terms) y17=%s" % y))
    for k in range(2):     # multiplier + the structure of the schematic's pass-through: C_CY2_I = 0, C_MULT = 1, PINY2 = x0
        y, xx = rand_srcs(rng, {"PY2": "x0", "CY2": rng.choice(("0", "1"))})
        hw = rand_hw(rng, 3, k, C_CY2_I="0", C_PY2_I="1")
        add(make("f3_mult_pass_pp_%d" % k, "F", "C", hw, y17=y, x145=xx, desc="C_MULT=1, C_CY2_I=0, PINY2 = x0, y17=%s" % y))
    return C


# ---------------------------------------------------------------- model
_cache = {}


def lines_of(cfg):
    """{helper port: source label} from the specs (Y17 patch wins over the Y16 chain; everything else 0)"""
    m = cfg["meta"]
    src = {p: "0" for p in LINE_PORT.values()}
    if m.get("y16"):
        for ln in m["y16"][0]:
            src[LINE_PORT[ln]] = m["y16"][1]
    for ln, v in m["y17"].items():
        src[LINE_PORT[ln]] = v
    for ln, v in m["x145"].items():
        src[LINE_PORT[ln]] = v
    return src


def vec(label):
    return {"x0": x(0), "x3": x(3), "0": np.zeros(NS, np.uint8), "1": np.ones(NS, np.uint8)}[label]


def helper_eval(cfg, signals, unc=None, override=None):
    unc = unc or UNC
    src = dict(lines_of(cfg), **(override or {}))
    key = json.dumps([sorted(cfg["cpiny"].items()), sorted(src.items()), sorted(unc.items()), list(signals)])
    if key not in _cache:
        inp = {"IN%d" % (i + 1): x(b) for i, b in enumerate((13, 14, 15, 16))}
        inp.update({k: np.full(NS, v, np.uint8) for k, v in unc.items()})
        inp.update({p: vec(v) for p, v in src.items()})
        _cache[key] = model_eval(cfg["cpiny"], list(signals), inp)
    return _cache[key]


def model_F(cfg):
    t = TARGET[cfg["meta"]["rd"]]
    F = helper_eval(cfg, [t])[t]
    assert F.max() <= 1, "unknown (x) in the model for %s" % cfg["name"]
    return F


# ---------------------------------------------------------------- analysis
SIGS = ["OUT1", "OUT2", "comp_out", "coy2_a", "coy2_s", "multo1", "multo2", "carry_generate", "carry_propagate", "mult_sum_hi", "mult_sum_lo", "cy2_route", "py2_route", "COUTY2", "POUTY2"]


def candidates(cfg, unc=None):
    d = helper_eval(cfg, SIGS, unc)
    c = {n: d[n] for n in SIGS}
    c["~comp_out"] = 1 - d["comp_out"]
    c["~carry_generate"] = 1 - d["carry_generate"]
    for p, v in lines_of(cfg).items():
        c["in:" + p] = vec(v)
    c["const0"], c["const1"] = vec("0"), vec("1")
    for b in (13, 14, 15, 16):
        c["x%d" % b] = x(b)
    return c


def mux_search(F, c, limit=4):
    pool = ["in:CINY2", "in:PINY2", "in:CINX", "in:PINX", "in:CINY1", "OUT1", "OUT2", "~comp_out", "coy2_a", "cy2_route", "py2_route", "const0", "const1"]
    sels = {"coy2_s": c["coy2_s"], "~coy2_s": 1 - c["coy2_s"], "mult_sum_hi": c["mult_sum_hi"], "mult_sum_lo": c["mult_sum_lo"], "~mult_sum_hi": 1 - c["mult_sum_hi"], "~mult_sum_lo": 1 - c["mult_sum_lo"]}
    hits = []
    for sn, sv in sels.items():
        for a, b in itertools.permutations(pool, 2):
            if not np.any(c[a] != c[b]) or np.all(F == c[a]) or np.all(F == c[b]):
                continue
            if not np.any(np.where(sv == 1, c[a], c[b]) != F):
                hits.append("%s ? %s : %s" % (sn, a, b))
                if len(hits) >= limit:
                    return hits
    return hits


def sensitivity(F):
    out = []
    for b in range(17):
        fr = float(np.mean(F != F[S ^ (1 << b)]))
        if fr > 0:
            out.append("x%d:%.2f" % (b, fr))
    return " ".join(out) or "none (constant)"


def diagnose(cfg, F, m):
    """print what a deviating configuration looks like"""
    c = candidates(cfg)
    ex = explain(F, c)
    print("    differing: %d states; F depends on bits %s" % (int((F != m).sum()), sensitivity(F)))
    print("    exact candidate(s): %s" % (", ".join(ex) if ex else "none"))
    if not ex:
        near = sorted(((int((F != v).sum()), n) for n, v in c.items()))[:4]
        print("    nearest: %s" % ", ".join("%s (%d)" % (n, d) for d, n in near))
        hits = mux_search(F, c)
        print("    2-input mux forms with 0 differing states: %s" % (hits if hits else "none"))
    t = TARGET[cfg["meta"]["rd"]]
    ok = []
    for bits in itertools.product((0, 1), repeat=4):
        u = dict(zip(("IN5", "IN6", "IN7", "IN8"), bits))
        if not np.any(helper_eval(cfg, [t], u)[t] != F):
            ok.append("".join(map(str, bits)))
    print("    IN5..IN8 values (IN5 IN6 IN7 IN8) under which cpe.v reproduces F: %s" % (ok if ok else "none"))


def analyze(records):
    bad, groups, names = 0, {}, []
    print("%-26s %-3s %-10s %8s  %s" % ("config", "grp", "reads", "differ", "what"))
    for r in records:
        cfg, F = r["cfg"], np.asarray(r["F"], dtype=np.uint8)
        m = model_F(cfg)
        d = int((m != F).sum())
        g = cfg["meta"]["grp"]
        s = groups.setdefault(g, [0, 0])
        s[0] += 1
        s[1] += d > 0
        bad += d > 0
        print("%-26s %-3s %-10s %8d  %s" % (cfg["name"], g, TARGET[cfg["meta"]["rd"]], d, cfg["meta"]["desc"][:70]))
        if d:
            names.append(cfg["name"])
            diagnose(cfg, F, m)
    print("per group (configs, deviating):", {g: tuple(v) for g, v in sorted(groups.items())})
    print("configs with deviations:", bad, "of", len(records))
    if bad:
        print("deviating:", names)
    return {"deviations": bad, "configs": len(records), "groups": groups, "deviating": names}


# ---------------------------------------------------------------- offline checks (no hardware)
def check():
    """(1) independence: the model output does not change if the unspecified helper inputs are 1 instead of 0; (2) every patch is on one of the three CPEs; (3) no word of nextpnr is deleted in X146Y17 / X145Y18"""
    cfgs = configs()
    bad = 0
    for c in cfgs:
        t = TARGET[c["meta"]["rd"]]
        base = helper_eval(c, [t])[t]
        src = lines_of(c)
        spec = set(c["meta"]["y17"]) | set(c["meta"]["x145"]) | (set(c["meta"]["y16"][0]) if c["meta"]["y16"] else set())
        free = [p for p in LINE_PORT.values() if p not in {LINE_PORT[k] for k in spec}]
        for p in free:
            for alt in ("1", "x0", "x3"):
                alt_v = helper_eval(c, [t], override={p: alt})[t]
                if np.any(alt_v != base):
                    print("DEPENDS on unspecified %s: %s (alt %s)" % (p, c["name"], alt))
                    bad += 1
                    break
        for (x_, y_, w) in c.get("extra", {}):
            assert (x_, y_) in (Y17, X145, Y16), (c["name"], x_, y_)
    print("configs:", len(cfgs), "independence violations:", bad)
    return bad


def selftest():
    """analyze() must notice a deliberately wrong vector"""
    from wp_runner import check as runner_check
    cfgs = configs()
    runner_check(cfgs)
    recs = [{"cfg": c, "F": model_F(c)} for c in cfgs]
    print("--- unperturbed")
    ok = analyze(recs)["deviations"]
    assert ok == 0
    rng = np.random.default_rng(1)
    pr = [dict(r) for r in recs]
    i = [k for k, c in enumerate(cfgs) if c["name"] == "a1_pass_src1"][0]
    F = pr[i]["F"].copy()
    F[rng.choice(NS, 300, replace=False)] ^= 1
    pr[i]["F"] = F
    j = [k for k, c in enumerate(cfgs) if c["name"] == "d1_route_h0_00"][0]
    pr[j]["F"] = x(0)
    print("--- perturbed (300 states of a1_pass_src1, d1_route_h0_00 replaced by x0)")
    res = analyze(pr)
    assert res["deviations"] == 2, res
    print("selftest ok: perturbed vectors noticed", res["deviating"])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check()
    elif len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    else:
        cs = configs()
        print(len(cs), "configs")
