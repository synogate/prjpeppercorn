"""Work package wp_yroute: the Y1 lines of the DUT (COUTY1 and POUTY1, C_HORIZ = 0) through CPOUT.

Open points covered (see the report / hw_measurements.md S18, S23):
  A   COUTY1 routing multiplexer codes 01 / 10 / 11 (OUT1 / ~COMP_OUT / CINX) with non-adder functions 0, 4, 5, 7 at C_CY1_I = 1, and the pass-through (C_CY1_I = 0) for the same codes
  B   POUTY1 routing multiplexer codes 00 / 01 / 10 / 11 (OUT1 / OUT2 / ~COMP_OUT / PINX) with non-adder functions 0, 4, 5, 7 at C_PY1_I = 1, C_COMP = 0, and the pass-through
  G   POUTY1 grid at C_HORIZ = 0: C_FUNCTION 0, 1, 2, 4, 5, 6, 7 x C_COMP x C_PY1_I x C_COMP_I x INIT_L30
  C   COUTY1 with an adder (C_FUNCTION 1, 2, 6), C_CY1_I = 1, all four routing codes (model: the generate term regardless of the route), random LUT trees
  D   COUTY1 with an adder, C_CY1_I = 0, random LUT trees, south-helper variants other than the default (sely1, both: CINY1 = x13)
Not visible: COUTY1 / POUTY1 at C_HORIZ = 1 or C_MULT = 1 (CPOUT then reads COUTX / POUTX).

Observation: COUTY1 / POUTY1 on OUT1 or OUT2 through CPOUT (C_O1 / C_O2 = 10, C_C_P chooses carry or propagate).  The observed OUT is never the OUT wire that the routing multiplexer reads
(COUTY1: code 00 reads OUT2, 01 reads OUT1; POUTY1: code 00 reads OUT1, 01 reads OUT2), so there is no combinational loop.  The other OUT keeps its ENV value (OUT1 = x7, OUT2 = ~x7 via the latch).

    python wp_runner.py wp_yroute --dry"""
import sys, os, json, random
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_common import ENV, model_vectors, helper, x, NS

LUTS = ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")
ROUTE_NAME = {"C": {"00": "OUT2", "01": "OUT1", "10": "~comp", "11": "CINX"}, "P": {"00": "OUT1", "01": "OUT2", "10": "~comp", "11": "PINX"}}
SIG = {"C": "COUTY1", "P": "POUTY1"}


def B(v, n):
    return format(v, "0%db" % n)


def _mk(line, code, obs, hv="default", **kw):
    """line 'C' (COUTY1) or 'P' (POUTY1), routing code = {C_SEL_C or C_SEL_P, C_SELY1}, obs = 1 / 2: which OUT shows CPOUT."""
    assert line in "CP" and obs in (1, 2)
    if line == "C":
        assert not (code == "00" and obs == 2) and not (code == "01" and obs == 1), "combinational loop"
    else:
        assert not (code == "00" and obs == 1) and not (code == "01" and obs == 2), "combinational loop"
    w = dict(ENV, C_HORIZ="0")
    w.update({k: v for k, v in kw.items()})
    w["C_SEL_C" if line == "C" else "C_SEL_P"] = code[0]
    w["C_SELY1"] = code[1]
    carry_on_cpout1 = obs == 1
    w["C_C_P"] = ("1" if carry_on_cpout1 else "0") if line == "C" else ("0" if obs == 1 else "1")
    w["C_O%d" % obs] = "10"
    return w


def _cfg(name, line, code, obs, hv="default", meta=None, **kw):
    c = {"name": name, "reader": "sel_OUT%d" % obs, "words": _mk(line, code, obs, **kw),
         "meta": dict(line=line, code=code, obs=obs, helper=hv, **(meta or {}))}
    if hv != "default":
        c["helper"] = hv
        c["cpiny"] = helper(hv)[0]
    return c


def _free_obs(i):
    return 1 + (i % 2)


def _obs_for(line, code, i):
    if line == "C":
        return 1 if code == "00" else 2 if code == "01" else _free_obs(i)
    return 2 if code == "00" else 1 if code == "01" else _free_obs(i)


def _good(f, luts):
    """random tree usable for an adder test: generate and propagate condition both vary clearly over IN1..IN8 (x0..x7)"""
    lut = {k: int(v, 2) for k, v in luts.items()}
    g = p = 0
    for s in range(256):
        i = [(s >> b) & 1 for b in range(8)]
        l00 = (lut["INIT_L00"] >> (2 * i[1] + i[0])) & 1
        l01 = (lut["INIT_L01"] >> (2 * i[3] + i[2])) & 1
        l02 = (lut["INIT_L02"] >> (2 * i[5] + i[4])) & 1
        l03 = (lut["INIT_L03"] >> (2 * i[7] + i[6])) & 1
        l10 = (lut["INIT_L10"] >> (2 * l01 + l00)) & 1
        l11 = (lut["INIT_L11"] >> (2 * l03 + l02)) & 1
        if f == 2:
            g += (l02 if l10 else (l00 | l01))
            p += 1 - (l10 & l11)
        else:
            g += l00 | l01 | l02
            p += l10 ^ l11
    return 64 <= g <= 192 and 64 <= p <= 192


def _rand_luts(r, f):
    while True:
        luts = {k: B(r.randrange(16), 4) for k in LUTS}
        if _good(f, luts):
            return luts


def configs():
    cfgs = []
    # ---- A: COUTY1 routing codes with non-adder functions
    i = 0
    for code in ("01", "10", "11"):
        for f in (0, 4, 5, 7):
            cfgs.append(_cfg("A_cy_f%d_r%s_cyi1" % (f, code), "C", code, _obs_for("C", code, i), C_FUNCTION=B(f, 3), C_CY1_I="1"))
            i += 1
    for code, f in (("01", 0), ("10", 5), ("11", 4)):          # pass-through: CINY1 whatever the route says
        cfgs.append(_cfg("A_cy_f%d_r%s_cyi0" % (f, code), "C", code, _obs_for("C", code, 1), C_FUNCTION=B(f, 3), C_CY1_I="0"))
    # ---- B: POUTY1 routing codes with non-adder functions (C_COMP = 0)
    i = 0
    for code in ("00", "01", "10", "11"):
        for f in (0, 4, 5, 7):
            cfgs.append(_cfg("B_py_f%d_r%s_pyi1" % (f, code), "P", code, _obs_for("P", code, i), C_FUNCTION=B(f, 3), C_PY1_I="1"))
            i += 1
    for code, f in (("10", 4), ("11", 7)):
        cfgs.append(_cfg("B_py_f%d_r%s_pyi0" % (f, code), "P", code, _obs_for("P", code, 0), C_FUNCTION=B(f, 3), C_PY1_I="0"))
    # ---- G: POUTY1 grid at C_HORIZ = 0
    for f in (0, 1, 2, 4, 5, 6, 7):                           # C_COMP = 0: route (PY1_I = 1) or PINY1 (PY1_I = 0); comparator and C_COMP_I must not matter
        code = "01" if f % 2 == 0 else "00"
        for pyi in "01":
            hv = "sely1" if (f in (2, 5) and pyi == "0") else "default"           # PINY1 = x14 instead of x13
            cfgs.append(_cfg("G_c0_f%d_pyi%s" % (f, pyi), "P", code, _obs_for("P", code, 0), hv, C_FUNCTION=B(f, 3), C_COMP="0", C_PY1_I=pyi,
                             C_COMP_I="1" if f in (1, 5) else "0"))
    for f in (0, 1, 2, 4, 5, 6, 7):                           # C_COMP = 1
        code = "01" if f % 2 == 0 else "00"
        for pyi in "01":
            l30s = ("0100",) if pyi == "1" else ("0110", "0100")
            for l30 in l30s:
                for ci in "01":
                    hv = "sely1" if (pyi == "0" and f in (1, 4, 6) and ci == "1") else "default"
                    cfgs.append(_cfg("G_c1_f%d_pyi%s_l%s_ci%s" % (f, pyi, l30, ci), "P", code, _obs_for("P", code, 0), hv,
                                     C_FUNCTION=B(f, 3), C_COMP="1", C_PY1_I=pyi, INIT_L30=l30, C_COMP_I=ci))
    # ---- C: COUTY1, adder, C_CY1_I = 1, all routes (random trees)
    r = random.Random(2701)
    for f in (1, 2, 6):
        for code in ("00", "01", "10", "11"):
            luts = _rand_luts(r, f)
            luts["INIT_L30"] = B(r.randrange(1, 15), 4)
            cfgs.append(_cfg("C_cy_f%d_r%s_cyi1" % (f, code), "C", code, _obs_for("C", code, f), C_FUNCTION=B(f, 3), C_CY1_I="1", **luts))
    # ---- D: COUTY1, adder, C_CY1_I = 0, random trees, helper variants (CINY1 = x13)
    r = random.Random(2702)
    for f in (1, 2, 6):
        for hv in ("sely1", "both"):
            for k in range(3):
                luts = _rand_luts(r, f)
                cfgs.append(_cfg("D_cy_f%d_%s_%d" % (f, hv, k), "C", "00", 1, hv, C_FUNCTION=B(f, 3), C_CY1_I="0", **luts))
    return cfgs


_CACHE = {}


def _cp(cfg):
    return helper(cfg.get("helper", "default"))[1]


_EXTRA = ["comp_out", "carry_generate", "carry_propagate", "cy1_sel", "cy1_adder", "py1_sel", "py1_compare"]


def _model(cfg, sigs):
    key = (json.dumps(cfg["words"], sort_keys=True), cfg.get("helper", "default"), tuple(sigs))
    if key not in _CACHE:
        _CACHE[key] = model_vectors(cfg["words"], list(sigs), _cp(cfg))
    return _CACHE[key]


def model_F(cfg):
    obs = int(cfg["reader"][-1])
    return _model(cfg, ["OUT%d" % obs])["OUT%d" % obs]


def _depends(F):
    """counter bits F depends on"""
    return [b for b in range(17) if (F != F[np.arange(NS) ^ (1 << b)]).any()]


def _cands(cfg, m):
    cp = _cp(cfg)
    one = np.ones(NS, np.uint8)
    comp = m["comp_out"]
    gen = m["carry_generate"]
    return {"x7(OUT1)": x(7), "~x7(OUT2)": 1 - x(7), "~comp": 1 - comp, "comp": comp, "CINX": x(cp["CINX"]), "PINX": x(cp["PINX"]),
            "CINY1": x(cp["CINY1"]), "PINY1": x(cp["PINY1"]), "generate": gen, "~generate": 1 - gen, "const0": 0 * one, "const1": one}


def _diagnose(cfg, F, mF):
    m = _model(cfg, _EXTRA)
    cand = _cands(cfg, m)
    line = cfg["meta"]["line"]
    if line == "C":
        sel, ad = m["cy1_sel"], m["cy1_adder"]
        groups = {"through(sel=0, model CINY1)": sel == 0, "generate(sel=1, adder)": (sel == 1) & (ad == 1), "route(sel=1, no adder)": (sel == 1) & (ad == 0)}
    else:
        sel, cm = m["py1_sel"], m["py1_compare"]
        groups = {"through(sel=0, model PINY1)": sel == 0, "compare(sel=1, model ~C_COMP_I)": (sel == 1) & (cm == 1), "route(sel=1, no compare)": (sel == 1) & (cm == 0)}
    print("    model depends on bits %s, measurement on %s" % (_depends(mF), _depends(F)))
    for g, mask in groups.items():
        n = int(mask.sum())
        if n == 0:
            continue
        bad = int((F[mask] != mF[mask]).sum())
        sc = sorted(((float((F[mask] == c[mask]).mean()), nme) for nme, c in cand.items()), reverse=True)
        exact = [nme for p, nme in sc if p == 1.0]
        print("    group %-34s %6d states, %6d differ from cpe.v; exact candidates: %s; best: %s" % (g, n, bad, exact or "none", ", ".join("%s %.3f" % (nme, p) for p, nme in sc[:3])))
    ex = [n for n, c in cand.items() if (c == F).all()]
    print("    whole vector equals candidate(s): %s" % (ex or "none"))
    ds = np.flatnonzero(F != mF)
    print("    first differing states: %s" % [int(s) for s in ds[:6]])


def analyze(records):
    bad, rows = [], []
    print("%-32s %-6s %-8s %-6s %s" % ("config", "line", "route", "obs", "differing states vs cpe.v"))
    for rec in records:
        cfg, F = rec["cfg"], np.asarray(rec["F"], dtype=np.uint8)
        mF = model_F(cfg)
        d = int((mF != F).sum())
        mt = cfg["meta"]
        print("%-32s %-6s %-8s OUT%d   %d" % (cfg["name"], SIG[mt["line"]], ROUTE_NAME[mt["line"]][mt["code"]], mt["obs"], d))
        rows.append((cfg["name"], d))
        if d:
            bad.append(cfg["name"])
            _diagnose(cfg, F, mF)
    print("configs with deviations: %d of %d" % (len(bad), len(records)))
    return {"deviations": len(bad), "configs": len(records), "deviating": bad, "differing": dict(rows)}
