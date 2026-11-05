"""Work package wp_l30: the comparator LUT2 L30 (INIT_L30) - input order and all 16 INIT values, and its inputs with adder / multiplier terms.
cpe.v: comp_out = lut2(INIT_L30, comb2_out, comb1_out) = INIT_L30[{COMB2OUT, COMB1OUT}] (raw LUT output).  Observed through
  (a) COUTX routing mux D2 (C_CX_I=1, C_SEL_C=1, C_SELX=0; east_CINX; model: ~comp_out)
  (b) POUTX routing mux D2 (C_PX_I=1, C_SEL_P=1, C_SELX=0; east_PINX; model: ~comp_out)
  (c) POUTX select condition (C_PX_I=0, C_COMP=1, C_HORIZ=1, C_COMP_I=0; east_PINX; model: comp_out ? 1 : PINX)
Series:  p1a/p1b/p1c  all 16 INIT_L30 in the common ENV (comb1 = x6, comb2 = x2), paths a / b / c       (48)
         p2           C_FUNCTION in {1,2,3,5,6,7} x C_HORIZ {0,1} x INIT_L30 in {0010, 1011}, path a        (24)
         p3           random LUT trees (random INIT of all LUTs, random asymmetric INIT_L30, random function / C_HORIZ), paths a / b   (24)
Analysis: differing states vs cpe.v, and the *effective INIT_L30* learned from F (4-entry truth table over (COMB2OUT, COMB1OUT) of the model's own
comb vectors), printed next to the programmed one; a swapped input order / complemented LUT shows up directly.
    python wp_runner.py wp_l30 --dry"""
import sys, os, random
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_common import ENV, model_vectors, helper, x

B = lambda v, n: format(v, "0%db" % n)
LUTS = ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")
READER = {"a": "east_CINX", "b": "east_PINX", "c": "east_PINX"}
PATHWORDS = {"a": {"C_CX_I": "1", "C_SEL_C": "1", "C_SELX": "0"},
             "b": {"C_PX_I": "1", "C_SEL_P": "1", "C_SELX": "0"},
             "c": {"C_PX_I": "0", "C_COMP": "1", "C_HORIZ": "1", "C_COMP_I": "0"}}


def _cfg(name, path, l30, f="000", h="0", luts=None):
    w = dict(ENV, **(luts or {}))
    w.update(PATHWORDS[path])
    if path != "c":
        w["C_HORIZ"] = h
    w.update(C_FUNCTION=f, INIT_L30=l30)
    return {"name": name, "reader": READER[path], "words": w, "meta": {"path": path, "l30": l30, "f": f, "h": w["C_HORIZ"]}}


def configs():
    cfgs = []
    for path in "abc":
        for v in range(16):
            cfgs.append(_cfg("p1%s_l%s" % (path, B(v, 4)), path, B(v, 4)))
    for f in (1, 2, 3, 5, 6, 7):
        for h in "01":
            for l30 in ("0010", "1011"):
                cfgs.append(_cfg("p2_f%d_h%s_l%s" % (f, h, l30), "a", l30, B(f, 3), h))
    r = random.Random(30)
    asym = [B(v, 4) for v in range(16) if v not in (0, 6, 9, 15)]
    for i in range(24):
        for _try in range(50):      # redraw until all four (COMB2OUT, COMB1OUT) combinations occur often enough for the effective INIT to be learnable
            luts = {k: B(r.randrange(16), 4) for k in LUTS}
            f, h, l30 = r.choice((0, 1, 2, 4, 5, 6, 7)), r.choice("01"), r.choice(asym)
            c = _cfg("p3_%02d_f%d_h%s_l%s" % (i, f, h, l30), "ab"[i % 2], l30, B(f, 3), h, luts)
            c1, c2 = _combs(c)
            if min(int(((2 * c2.astype(int) + c1) == k).sum()) for k in range(4)) >= 4000:
                break
        cfgs.append(c)
    return cfgs


def _cp(cfg):
    return helper(cfg.get("helper", "default"))[1]


_SIG = {"a": "COUTX", "b": "POUTX", "c": "POUTX"}
_cache = {}


def _vec(cfg, sigs):
    key = (tuple(sorted(cfg["words"].items())), tuple(sigs))
    if key not in _cache:
        _cache[key] = model_vectors(cfg["words"], list(sigs), _cp(cfg))
    return _cache[key]


def model_F(cfg):
    return _vec(cfg, [_SIG[cfg["meta"]["path"]]])[_SIG[cfg["meta"]["path"]]]


def _combs(cfg):
    d = _vec(cfg, ["comb1_out", "comb2_out"])
    return d["comb1_out"], d["comb2_out"]


def predict(cfg, init):
    """F expected for any INIT_L30 value `init` (4-char bit string, bit3 first), from the model's comb vectors (no simulation of L30 itself)"""
    c1, c2 = _combs(cfg)
    tt = [int(init[3 - i]) for i in range(4)]          # tt[{D1, D0}] = tt[2 * comb2 + comb1]
    L = np.array(tt, dtype=np.uint8)[2 * c2.astype(int) + c1.astype(int)]
    if cfg["meta"]["path"] in "ab":
        return (1 - L).astype(np.uint8)
    pinx = x(_cp(cfg)["PINX"])
    return np.where(L == 1, 1 - int(cfg["words"]["C_COMP_I"]), pinx).astype(np.uint8)


def learn(cfg, F):
    """effective INIT_L30 from F: -> (bit string or '?' per position (bit3 first), per index [(ones, zeros)]).  In path c only states with PINX = 0 are informative."""
    c1, c2 = _combs(cfg)
    idx = 2 * c2.astype(int) + c1.astype(int)
    if cfg["meta"]["path"] in "ab":
        L, ok = 1 - F.astype(int), np.ones(len(F), bool)
    else:
        L, ok = F.astype(int), x(_cp(cfg)["PINX"]) == 0
    bits, stat = [], []
    for i in range(4):
        m = ok & (idx == i)
        n1, n0 = int((L[m] == 1).sum()), int((L[m] == 0).sum())
        stat.append((n1, n0))
        bits.append("?" if n1 + n0 == 0 else ("1" if n0 == 0 else "0" if n1 == 0 else "x"))     # x: mixed = F is not a function of (comb1, comb2)
    return "".join(bits[3 - k] for k in range(4)), stat


def _swap(init):      # exchange D1 / D0: entries 1 and 2 trade places
    return init[0] + init[2] + init[1] + init[3]


def _compl(init):
    return "".join("1" if c == "0" else "0" for c in init)


def analyze(records):
    bad, rows, seen = 0, [], {}
    print("%-30s %-3s %-5s %-5s %-6s  diff  diagnosis" % ("config", "pth", "prog", "eff", "func/H"))
    for r in records:
        cfg, F = r["cfg"], np.asarray(r["F"], dtype=np.uint8)
        m = model_F(cfg)
        d = int((m != F).sum())
        bad += d > 0
        prog = cfg["words"]["INIT_L30"]
        eff, stat = learn(cfg, F)
        diag = ""
        if d:
            fits = [B(v, 4) for v in range(16) if int((predict(cfg, B(v, 4)) != F).sum()) == 0]
            nm = {_swap(prog): "inputs swapped", _compl(prog): "complemented", _compl(_swap(prog)): "swapped + complemented"}
            diag = "fits INIT_L30 = %s" % (",".join("%s(%s)" % (f, nm.get(f, "other")) for f in fits) if fits else "no 4-entry L30 of comb1/comb2 explains F")
            if not fits:
                ds = [k for k in range(17) if k <= 16 and int((F[(np.arange(len(F)) ^ (1 << k))] != F).sum()) > 0]
                diag += "; F depends on x%s; differs from model in %d states, first at s=%d" % (",".join(map(str, ds)), d, int(np.nonzero(m != F)[0][0]))
        print("%-30s %-3s %-5s %-5s f%s h%s  %5d  %s" % (cfg["name"], cfg["meta"]["path"], prog, eff, cfg["meta"]["f"], cfg["meta"]["h"], d, diag))
        rows.append((cfg["name"], prog, eff, d))
        seen.setdefault(cfg["meta"]["path"], []).append((prog, eff, d))
    print("effective INIT_L30 == programmed, per path:")
    for p, v in sorted(seen.items()):
        print("  path %s: %d of %d configs; deviations vs cpe.v: %d" % (p, sum(a == b for a, b, _ in v), len(v), sum(dd > 0 for _, _, dd in v)))
    print("configs with deviations:", bad, "of", len(records))
    return {"deviations": bad, "configs": len(records), "effective": {n: (p, e) for n, p, e, _ in rows}}
