"""Work package wp_cpout: CPOUT1 / CPOUT2 (-> OUT1 / OUT2) with adder, comparator and multiplier active.

Open points (see brief): C_FUNCTION in {1, 2, 3, 6, 7} x C_HORIZ x C_C_P x C_COMP x C_xx_I (xx = CX/PX for the X pair, CY1/PY1 for the Y1 pair) x C_COMP_I / INIT_L30,
CPOUT observed on OUT1 (C_O1 = 10, reader sel_OUT1) and on OUT2 (C_O2 = 10, reader sel_OUT2).  cp_use_x = C_HORIZ | C_MULT.

Per (C_FUNCTION, C_HORIZ) group of 11 configurations (10 groups = 110) + 4 extras:
  a0..a3  C_xx_I = 0, C_COMP = 0:    (cp, obs) = (1,1) carry on OUT1, (0,1) prop on OUT1, (1,2) prop on OUT2, (0,2) carry on OUT2   [carry / prop through both OUTs and both C_C_P]
  b0..b3  C_xx_I = 1, C_COMP = 0:    routing mux of the observed line on OUT-other / COMP_OUT / CIN*/PIN* ('rc','rp','ex','cmp', rotated per group)
  c0..c2  C_COMP = 1:                POUTX / POUTY1 compare branch with C_COMP_I = 0 / 1 and three INIT_L30
  x0..x3  extras: C_COMP = 0 with C_COMP_I = 1 (must have no effect)
a/b/c use pass-through LUTs (ENV) or seeded random LUT trees, and the four south-helper settings (HELPER_VARIANTS) rotate over the configs so that CINY1 / CINY2 / PINY1 / PINY2
(and with them the multiplier inputs) carry different counter bits.
Routing multiplexer data: the observed OUT must never be read back by a routing mux (combinational loop in cpe.v): with C_O1 = 10 OUT2 (= ~x7) is the usable OUT, with C_O2 = 10 OUT1 (= x7).
C_SELX is shared by the X carry / propagate muxes with opposite meaning (carry: 0 -> OUT1, 1 -> OUT2; prop: 0 -> OUT2, 1 -> OUT1), so only one of the two lines can use the OUT of the
other output; the other gets code 10 / 11 (comp / CIN* / PIN*).  Same for C_SELY1.
Dry run: python wp_runner.py wp_cpout --dry          Perturbation test of analyze(): python wp_cpout.py selftest
"""
import sys, os, random
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_common import ENV, model_vectors, helper, NS, S, x
import meas

B = lambda v, n: format(v, "0%db" % n)
LUTS = ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")
FUNCS = (1, 2, 3, 6, 7)
VARIANTS = ("default", "sely1", "sely2", "both")
KINDS = ("rc", "rp", "ex", "cmp")


def _route(obs, kind, y12):
    """routing multiplexer words of the four lines (cx/px via C_SELX, cy1/py1 via C_SELY1, C_SEL_C / C_SEL_P shared); obs = which OUT carries CPOUT (that one must not be read back)."""
    w = {}
    if kind == "rc":      # carry lines on the other OUT (code 00 / 01), propagate lines on code 11 (PIN*): X: pin_y12, Y1: PINX
        w.update(C_SEL_C="0", C_SEL_P="1", C_SELX="1" if obs == 1 else "0", C_SELY1="0" if obs == 1 else "1")
        # obs 1 (other = OUT2): cx SELX=1 -> OUT2, cy1 SELY1=0 -> OUT2;  obs 2 (other = OUT1): cx SELX=0 -> OUT1, cy1 SELY1=1 -> OUT1
        w["C_SELX"] = "1" if obs == 1 else "0"
        # propagate lines then see code {1, SELX}: SELX=1 -> pin_y12, SELX=0 -> ~comp_out;  {1, SELY1}: SELY1=1 -> PINX, SELY1=0 -> ~comp_out
    elif kind == "rp":    # propagate lines on the other OUT, carry lines on code 1x
        w.update(C_SEL_C="1", C_SEL_P="0")
        # obs 1 (other = OUT2): px SELX=0 -> OUT2, py1 SELY1=1 -> OUT2;  obs 2 (other = OUT1): px SELX=1 -> OUT1, py1 SELY1=0 -> OUT1
        w["C_SELX"] = "0" if obs == 1 else "1"
        w["C_SELY1"] = "1" if obs == 1 else "0"
    elif kind == "ex":    # all four lines on CIN* / PIN*: cx = cin_y12, px = pin_y12, cy1 = CINX, py1 = PINX
        w.update(C_SEL_C="1", C_SEL_P="1", C_SELX="1", C_SELY1="1")
    else:                 # "cmp": all four lines on ~COMP_OUT
        w.update(C_SEL_C="1", C_SEL_P="1", C_SELX="0", C_SELY1="0")
    w["C_Y12"] = y12
    return w


def _luts(rng):
    return {k: B(rng.randrange(16), 4) for k in LUTS}


def _cfg(name, f, h, cp, obs, kind_meta, luts=None, variant="default", **extra_words):
    words = dict(ENV, C_FUNCTION=B(f, 3), C_HORIZ=str(h), C_C_P=str(cp))
    if luts:
        words.update(luts)
    words["C_O1" if obs == 1 else "C_O2"] = "10"
    words.update(extra_words)
    cfg = {"name": name, "reader": "sel_OUT%d" % obs, "words": words, "helper": variant,
           "meta": dict(f=f, h=h, cp=cp, obs=obs, variant=variant, **kind_meta)}
    if variant != "default":
        cfg["cpiny"] = helper(variant)[0]
    return cfg


def configs():
    rng = random.Random(2024)
    cfgs = []
    for g, (f, h) in enumerate((f, h) for f in FUNCS for h in (0, 1)):
        tag = "f%dh%d" % (f, h)
        # a: C_xx_I = 0, no comparator.  (cp, obs, random LUTs, helper variant offset)
        for j, (cp, obs, rnd) in enumerate(((1, 1, False), (0, 1, True), (1, 2, True), (0, 2, False))):
            var = VARIANTS[(g + j) % 4] if j in (1, 2) else "default"
            kind = KINDS[(g + j + 2) % 4]      # routing data must never be the observed OUT (f = 3 / adder with C_HORIZ = 1 takes the routing mux even at C_xx_I = 0)
            y12 = str((g + j) % 2)
            cfgs.append(_cfg("a%d_%s_cp%d_o%d" % (j, tag, cp, obs), f, h, cp, obs, {"set": "a", "I": "00", "kind": kind}, _luts(rng) if rnd else None, var, **_route(obs, kind, y12)))
        # b: C_xx_I = 1: (cp, obs, I = (cxi, pxi), random)
        for j, (cp, obs, (cxi, pxi), rnd) in enumerate(((1, 1, (1, 1), False), (1, 2, (1, 1), False), (0, 1, (0, 1), True), (0, 2, (1, 0), True))):
            kind = KINDS[(g + j) % 4]
            y12 = str((g + j) // 2 % 2) if kind == "ex" else "0"
            var = VARIANTS[(g + j + 1) % 4] if j >= 2 else "default"
            w = dict(_route(obs, kind, y12), C_CX_I=str(cxi), C_CY1_I=str(cxi), C_PX_I=str(pxi), C_PY1_I=str(pxi))
            cfgs.append(_cfg("b%d_%s_cp%d_o%d_%s_i%d%d" % (j, tag, cp, obs, kind, cxi, pxi), f, h, cp, obs,
                             {"set": "b", "I": "%d%d" % (cxi, pxi), "kind": kind}, _luts(rng) if rnd else None, var, **w))
        # c: comparator, propagate line observed (POUTX at h = 1, POUTY1 at h = 0), C_COMP_I 0 / 1, INIT_L30 variants
        for j, (cp, obs, ci, l30, pxi, kind, rnd) in enumerate(((0, 1, 0, "0110", 0, None, False), (1, 2, 1, "0001", 0, None, True), (0, 1, 1, "0111", 1, "cmp", False))):
            var = VARIANTS[(g + 1) % 4] if j == 1 else "default"
            w = {"C_COMP": "1", "C_COMP_I": str(ci), "INIT_L30": l30, "C_PX_I": str(pxi), "C_PY1_I": str(pxi)}
            kind = kind or KINDS[(g + j) % 4]
            w.update(_route(obs, kind, str(g % 2)))
            cfgs.append(_cfg("c%d_%s_cp%d_o%d_ci%d_l%s_pi%d" % (j, tag, cp, obs, ci, l30, pxi), f, h, cp, obs,
                             {"set": "c", "ci": ci, "l30": l30, "I": "0%d" % pxi, "kind": kind}, _luts(rng) if rnd else None, var, **w))
    # x: C_COMP = 0 with C_COMP_I = 1 (no effect expected), prop observed
    for f, h, cp, obs in ((1, 1, 0, 1), (1, 0, 1, 2), (3, 1, 1, 2), (3, 0, 0, 1)):
        cfgs.append(_cfg("x_f%dh%d_cp%d_o%d_ci1" % (f, h, cp, obs), f, h, cp, obs, {"set": "x", "I": "00", "ci": 1}, None, "default", C_COMP_I="1", **_route(obs, "ex", "0")))
    return cfgs


def _cp(cfg):
    return helper(cfg.get("helper", "default"))[1]


_CACHE = {}


def model_F(cfg):
    sig = "OUT%d" % cfg["meta"]["obs"]
    key = (sig, tuple(sorted(cfg["words"].items())), cfg.get("helper", "default"))
    if key not in _CACHE:
        _CACHE[key] = model_vectors(cfg["words"], [sig], _cp(cfg))[sig]
    return _CACHE[key].copy()


# ---------------------------------------------------------------- analysis
CAND = ("COUTX", "POUTX", "COUTY1", "POUTY1", "carry_generate", "carry_propagate", "multo1", "multo2", "cx_route", "px_route", "cy1_route", "py1_route",
        "comp_out", "cpout1", "cpout2", "comb1_out", "comb2_out")


def _candidates(cfg):
    """model vectors of the candidate sources for cfg (x values = unavailable) + inversions + the raw CP inputs + constants"""
    sigs = list(CAND)
    d = meas.internals(cfg["words"], tuple(sigs), _cp(cfg))
    from wp_common import _KEYS
    cand = {}
    for n in sigs:
        v = np.array([{"0": 0, "1": 1}.get(d[n][k], 2) for k in _KEYS], dtype=np.uint8)
        if (v == 2).any():
            continue
        cand[n] = v
        cand["~" + n] = 1 - v
    cp = _cp(cfg)
    for n, b in cp.items():
        cand[n + "(x%d)" % b] = x(b)
        cand["~" + n + "(x%d)" % b] = 1 - x(b)
    cand["x7"], cand["~x7"] = x(7), 1 - x(7)
    cand["const0"], cand["const1"] = np.zeros(NS, np.uint8), np.ones(NS, np.uint8)
    return cand


def _deps(F):
    """bits x0..x16 that F depends on"""
    out = []
    for k in range(17):
        a = F.reshape(1 << (16 - k), 2, 1 << k)
        if (a[:, 0, :] != a[:, 1, :]).any():
            out.append(k)
    return out


def _diagnose(cfg, F, m):
    diff = F != m
    print("      differs in %d states; F depends on x%s, model on x%s; difference depends on x%s" % (int(diff.sum()), _deps(F), _deps(m), _deps(diff.astype(np.uint8))))
    cand = _candidates(cfg)
    rank = sorted(((int((c != F).sum()), n) for n, c in cand.items()))
    exact = [n for k, n in rank if k == 0]
    print("      observed OUT%d equals candidate(s): %s" % (cfg["meta"]["obs"], ", ".join(exact) if exact else "none"))
    if not exact:
        print("      closest candidates (differing states): " + ", ".join("%s %d" % (n, k) for k, n in rank[:4]))
    # where it differs from the model: does F follow another source there?
    sub = [(int(((c != F) & diff).sum()), n) for n, c in cand.items()]
    sub.sort()
    print("      inside the deviating states F follows: " + ", ".join("%s (%d wrong of %d)" % (n, k, int(diff.sum())) for k, n in sub[:3]))
    return exact


def analyze(records):
    bad = 0
    byset = {}
    print("%-44s %-10s %s" % ("config", "OUT", "differing states vs cpe.v"))
    for r in records:
        cfg = r["cfg"]
        m = model_F(cfg)
        d = int((m != r["F"]).sum())
        mt = cfg["meta"]
        const = "const%d" % int(r["F"][0]) if (r["F"] == r["F"][0]).all() else ""
        print("%-44s OUT%d CPOUT%d %-7s %d" % (cfg["name"], mt["obs"], mt["obs"], const, d))
        s = byset.setdefault(mt["set"], [0, 0])
        s[0] += 1
        if d:
            bad += 1
            s[1] += 1
            _diagnose(cfg, np.asarray(r["F"], dtype=np.uint8), m)
    # open points summary: how the deviations distribute over the parameters
    print("per set (configs, deviating):", {k: tuple(v) for k, v in byset.items()})
    dev = [r["cfg"]["meta"] for r in records if int((model_F(r["cfg"]) != r["F"]).sum())]
    for key in ("f", "h", "cp", "obs"):
        vals = sorted({m[key] for m in (r["cfg"]["meta"] for r in records)})
        print("deviations by %s:" % key, {v: sum(1 for m in dev if m[key] == v) for v in vals})
    print("configs with deviations:", bad, "of", len(records))
    return {"deviations": bad, "configs": len(records)}


def selftest():
    """analyze() on model data with three deliberate perturbations: a flipped bit pattern, CPOUT swapped (C_C_P ignored), a wrong source"""
    cfgs = configs()
    pick = {"flip": next(c for c in cfgs if c["name"].startswith("a0_f1h1")), "swap": next(c for c in cfgs if c["name"].startswith("a0_f3h0")),
            "poutx": next(c for c in cfgs if c["name"].startswith("c0_f2h1"))}
    recs = []
    for c in cfgs[:3]:
        recs.append({"cfg": c, "F": model_F(c)})
    F = model_F(pick["flip"]).copy()
    F[(S & 0x80) != 0] ^= (x(2)[(S & 0x80) != 0] & x(6)[(S & 0x80) != 0])          # wrong in a quarter of the half space
    recs.append({"cfg": pick["flip"], "F": F})
    c = pick["swap"]
    c2 = dict(c, words=dict(c["words"], C_C_P=str(1 - int(c["words"]["C_C_P"]))))   # hardware would give the other CPOUT
    recs.append({"cfg": c, "F": model_F(c2)})
    c = pick["poutx"]
    recs.append({"cfg": c, "F": x(12)})                                              # POUTX showing plain PINX although the comparator should act
    res = analyze(recs)
    assert res["deviations"] >= 2, res
    print("selftest: perturbations noticed:", res)


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
