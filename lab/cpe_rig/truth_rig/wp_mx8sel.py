"""Work package wp_mx8sel: which lines feed the 8:1 multiplexer's select terms when C_CLKSEL / C_ENSEL = 1?

cpe.v (as drawn in the schematic): term_clk = lut1(C_CPE_CLK, CLK) ^ (C_CLKSEL & CINY1), term_en = lut1(C_CPE_EN, EN) ^ (C_ENSEL & PINY1)   (flip-flops: CINY2 / PINY2).
gatemate/die.py (pip model, flip-flops): C_CLKSEL is a routing mux  CLK_int = C_CLKSEL ? CINY2 : CLK,  C_ENSEL:  EN_int = C_ENSEL ? PINY2 : EN  (the LUT1 sees the replaced signal).
Nothing of this is measured.  Per term four hypotheses: line = Y1 / Y2  x  mode = 'xor' (add to the LUT1 output) / 'repl' (replace the LUT1 input).
  A = (Y2, xor) = cpe.v after the measurement (S31: all 60 configurations fit, nothing else does; cpe.v had (Y1, xor) before).

Observation: MUXOUT on OUT1 (C_O1 = 01, reader sel_OUT1), IN1..IN8 = x0..x7, so F = x[select], select = (C_SN + t_clk + 2 t_en + 4 t_sr + C_2D_IN) mod 8 (C_BR = 0).
The LUT1 words of the three terms are chosen per group (00 / 11 constant, 10 pass, 01 invert):
  a  baseline, C_CLKSEL = C_ENSEL = 0 (the CP lines must have no effect)
  b  C_CLKSEL = 1 only, four CLK words x two C_SN x helper variants
  c  C_ENSEL = 1 only, four EN words x two C_SN x helper variants
  d  both, random words / C_SN / C_2D_IN / SR word, all four helper variants
Constant words separate the modes: with 'repl' a constant LUT1 hides the CP line completely, with 'xor' the line is seen.  The helper variants decide Y1 against Y2:
  default: CINY1 = x14, CINY2 = x13, PINY1 = x13, PINY2 = x14;  both: CINY1 = x13, CINY2 = x14, PINY1 = x14, PINY2 = x13;  sely1 / sely2 swap one pair (control).
Not covered: the flip-flop / latch side (state dependent, needs another package).
Dry run: python wp_runner.py wp_mx8sel --dry          Perturbation test of analyze(): python wp_mx8sel.py selftest
"""
import sys, os, random, itertools
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_common import ENV, model_vectors, helper, NS, S, x
from meas import PIN_INV

B = lambda v, n: format(v, "0%db" % n)
WORDS = ("00", "11", "10", "01")
VARIANTS = ("default", "both", "sely1", "sely2")
HYP = [(y, m) for y in (1, 2) for m in ("xor", "repl")]          # per term; A = (1, "xor")
A = ((2, "xor"), (2, "xor"))                                      # cpe.v since the measurement (finding 37); before: ((1, "xor"), (1, "xor"))


def _cfg(name, group, sn, wclk, wen, wres, clksel, ensel, c2d, variant):
    words = dict(ENV, C_BR="0", C_2D_IN=str(c2d), C_SN=B(sn, 3), C_O1="01", C_FUNCTION="000",
                 C_CPE_CLK=wclk, C_CPE_EN=wen, C_CPE_RES=wres, C_CLKSEL=str(clksel), C_ENSEL=str(ensel))
    cfg = {"name": name, "reader": "sel_OUT1", "words": words, "helper": variant,
           "meta": dict(group=group, sn=sn, wclk=wclk, wen=wen, wres=wres, clksel=clksel, ensel=ensel, c2d=c2d, variant=variant)}
    if variant != "default":
        cfg["cpiny"] = helper(variant)[0]
    return cfg


def configs():
    rng = random.Random(30)
    out = []
    n = 0
    for sn, variant in ((0, "default"), (3, "default"), (5, "both"), (6, "both")):                       # a
        out.append(_cfg("a%d" % n, "a", sn, "00", "00", "00", 0, 0, 0, variant))
        n += 1
    for wclk, (sn, variant) in itertools.product(WORDS, ((1, "default"), (4, "both"), (2, "sely1"), (6, "sely2"))):    # b
        out.append(_cfg("b%d" % n, "b", sn, wclk, "00", "00", 1, 0, 0, variant))
        n += 1
    for wen, (sn, variant) in itertools.product(WORDS, ((1, "default"), (4, "both"), (2, "sely1"), (6, "sely2"))):     # c
        out.append(_cfg("c%d" % n, "c", sn, "00", wen, "00", 0, 1, 0, variant))
        n += 1
    for i in range(24):                                                                                     # d
        out.append(_cfg("d%d" % n, "d", rng.randrange(8), rng.choice(WORDS), rng.choice(WORDS), rng.choice(WORDS), 1, 1, rng.randrange(2),
                        VARIANTS[i % 2 if i < 16 else i % 4]))
        n += 1
    return out


def _lut1(word, d):
    """LUT1 word (string, MSB first): '10' passes, '01' inverts, '00' / '11' constant"""
    d = np.asarray(d, dtype=np.uint8)
    return np.array([int(word[1 - b]) for b in (0, 1)], dtype=np.uint8)[d]


def hyp_F(cfg, hclk=(2, "xor"), hen=(2, "xor")):
    """expected F of cfg for the select-term hypotheses (hclk, hen)"""
    w = cfg["words"]
    cp = helper(cfg.get("helper", "default"))[1]
    clk, en, sr = x(8) ^ PIN_INV["CLK"], x(9) ^ PIN_INV["EN"], x(10) ^ PIN_INV["SR"]
    ciny = {1: x(cp["CINY1"]), 2: x(cp["CINY2"])}
    piny = {1: x(cp["PINY1"]), 2: x(cp["PINY2"])}
    clksel, ensel = int(w["C_CLKSEL"]), int(w["C_ENSEL"])

    def term(word, pin, sel, line, hyp):
        y, mode = hyp
        if mode == "xor":
            return _lut1(word, pin) ^ (line[y] & sel)
        return _lut1(word, line[y] if sel else pin)

    tclk = term(w["C_CPE_CLK"], clk, clksel, ciny, hclk).astype(np.int64)
    ten = term(w["C_CPE_EN"], en, ensel, piny, hen).astype(np.int64)
    tsr = _lut1(w["C_CPE_RES"], sr).astype(np.int64)
    sel = (int(w["C_SN"], 2) + tclk + 2 * ten + 4 * tsr + int(w["C_2D_IN"])) % 8
    return ((S >> sel) & 1).astype(np.uint8)


def model_F(cfg):
    """what cpe.v predicts (= hypothesis A)"""
    return model_vectors(cfg["words"], ["OUT1"], helper(cfg.get("helper", "default"))[1])["OUT1"]


def _name(h):
    return "%s%d" % ("x" if h[1] == "xor" else "r", h[0])


def analyze(records):
    bad = 0
    alive = {g: {(hc, he) for hc in HYP for he in HYP} for g in "abcd"}
    print("%-6s %-5s %-4s %-4s %-4s %-3s %-3s %-4s %-7s %s" % ("cfg", "SN", "clk", "en", "res", "cs", "es", "c2d", "variant", "differing vs cpe.v (A)  | matching hypotheses (clk,en)"))
    for r in records:
        cfg, F, m = r["cfg"], r["F"], r["cfg"]["meta"]
        d = int((hyp_F(cfg, *A) != F).sum())
        bad += d > 0
        ok = {(hc, he) for hc in HYP for he in HYP if int((hyp_F(cfg, hc, he) != F).sum()) == 0}
        alive[m["group"]] &= ok
        shown = sorted("%s/%s" % (_name(a), _name(b)) for a, b in ok)
        print("%-6s %-5d %-4s %-4s %-4s %-3d %-3d %-4d %-7s %6d  | %s" % (cfg["name"], m["sn"], m["wclk"], m["wen"], m["wres"], m["clksel"], m["ensel"], m["c2d"], m["variant"], d,
                                                                         "all %d" % len(ok) if len(ok) > 8 else (" ".join(shown) if shown else "NONE")))
        if not ok:
            dep = [b for b in range(8, 15) if int((F != F[S ^ (1 << b)]).sum()) > 0]
            print("       no hypothesis fits; F depends on x%s (of x8..x14); ones: %d" % (dep, int(F.sum())))
    print("configs deviating from cpe.v (A):", bad, "of", len(records))
    for g, name in (("a", "baseline"), ("b", "C_CLKSEL only"), ("c", "C_ENSEL only"), ("d", "both")):
        s = alive[g]
        if g == "b":
            print("group b (%s): clk hypotheses alive: %s" % (name, sorted({_name(a) for a, b in s})))
        elif g == "c":
            print("group c (%s): en hypotheses alive: %s" % (name, sorted({_name(b) for a, b in s})))
        else:
            print("group %s (%s): (clk, en) combinations alive: %d%s" % (g, name, len(s), "" if len(s) > 4 else "  " + " ".join(sorted("%s/%s" % (_name(a), _name(b)) for a, b in s))))
    return {"deviations": bad, "configs": len(records)}


def selftest():
    cfgs = configs()
    recs = [{"cfg": c, "F": hyp_F(c, *A).copy()} for c in cfgs]
    assert all(int((hyp_F(c, *A) != model_F(c)).sum()) == 0 for c in cfgs[:8]), "analytic hypothesis A differs from cpe.v"
    print("analytic A equals cpe.v on 8 configs: ok")
    ref = analyze(recs)
    assert ref["deviations"] == 0
    # perturbation 1: flip one state of one config -> must be noticed
    recs2 = [dict(r) for r in recs]
    f = recs2[10]["F"].copy()
    f[12345] ^= 1
    recs2[10]["F"] = f
    assert analyze(recs2)["deviations"] == 1
    # perturbation 2: hardware that uses Y1 / xor for the clock term (the old model) -> must be noticed and identified
    recs3 = [{"cfg": c, "F": hyp_F(c, (1, "xor"), (2, "xor"))} for c in cfgs]
    res = analyze(recs3)
    assert res["deviations"] > 0
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
