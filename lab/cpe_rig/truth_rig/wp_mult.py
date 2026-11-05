"""Work package wp_mult: multiplier terms MULTO2 (read as COUTX) and MULTO1 (read as POUTX), C_FUNCTION = 3.
Open points covered (see configs()):
  1. C_HORIZ = 1 (carry-in of add2_carry = CINX = x11), MULTO2 at COUTX (S1 = C_CX_I | ((C_ADDF & C_HORIZ) & carry_propagate): MULTO2 where S1 = 0, routing mux where S1 = 1;
     the routing mux is chosen so that it differs from MULTO2) and MULTO1 at POUTX.
  2. 12 random LUT trees (random INIT of L00..L03, L10, L11, L20) x the four south-helper variants x C_HORIZ in {0, 1} x both readers.
  3. C_FUNCTION = 3 with C_COMP = 1 (COUTX and POUTX), and C_CX_I / C_PX_I = 1 (routing multiplexer wins).
    python wp_runner.py wp_mult --dry        python wp_mult.py   (self-test of analyze() against perturbed formulas)
"""
import sys, os, random, itertools
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_common import ENV, model_vectors, helper, x, NS, S

B = lambda v, n: format(v, "0%db" % n)
HELPERS = ("default", "sely1", "sely2", "both")
LUTS = ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")
# routing multiplexer settings (C_SEL_C / C_SEL_P, C_SELX, C_Y12) that differ from the multiplier terms
ROUTES = [("0", "0", "0"), ("0", "1", "0"), ("1", "0", "0"), ("1", "1", "0"), ("1", "1", "1")]
SIGNAL = {"east_CINX": "COUTX", "east_PINX": "POUTX"}


def _cfg(name, reader, words, hv, **meta):
    return {"name": name, "reader": reader, "words": words, "helper": hv, "cpiny": helper(hv)[0], "meta": dict(meta, helper=hv)}


def configs():
    r = random.Random(20260511)
    cfgs = []
    # ---- A: 12 random trees x 4 helper variants x {COUTX, POUTX}; C_HORIZ alternates so that every helper variant sees both values on both readers
    for t in range(12):
        luts = {k: B(r.randrange(16), 4) for k in LUTS}
        for hi, hv in enumerate(HELPERS):
            h = (t + hi) % 2
            sc, sx, y12 = ROUTES[(t // 2 + hi) % len(ROUTES)]
            w = dict(ENV, **luts)
            w.update(C_FUNCTION="011", C_HORIZ=str(h), C_CX_I="0", C_PX_I="0")
            if h:
                w.update(C_SEL_C=sc, C_SELX=sx, C_Y12=y12)           # route visible where S1 = 1 (only COUTX; harmless for MULTO1)
            cfgs.append(_cfg("a%02d_%s_co_h%d" % (t, hv, h), "east_CINX", w, hv, part="A", horiz=h, tree=t))
            w = dict(ENV, **luts)
            w.update(C_FUNCTION="011", C_HORIZ=str(1 - h), C_CX_I="0", C_PX_I="0")
            cfgs.append(_cfg("a%02d_%s_po_h%d" % (t, hv, 1 - h), "east_PINX", w, hv, part="A", horiz=1 - h, tree=t))
    # ---- C: C_CX_I / C_PX_I = 1 (routing mux wins), C_COMP = 1
    for i in range(6):                                   # COUTX, C_CX_I = 1, C_FUNCTION = 3: both C_HORIZ, several route settings
        luts = {k: B(r.randrange(16), 4) for k in LUTS}
        sc, sx, y12 = ROUTES[i % 5]
        h = i % 2
        w = dict(ENV, **luts)
        w.update(C_FUNCTION="011", C_HORIZ=str(h), C_CX_I="1", C_SEL_C=sc, C_SELX=sx, C_Y12=y12, INIT_L30=B(r.choice([6, 9, 1, 14, 2, 4]), 4))
        cfgs.append(_cfg("c_cxi_%d_h%d" % (i, h), "east_CINX", w, HELPERS[i % 4], part="C", horiz=h))
    for i in range(6):                                   # POUTX, C_PX_I = 1
        luts = {k: B(r.randrange(16), 4) for k in LUTS}
        sc, sx, y12 = ROUTES[(i + 1) % 5]
        h = (i // 2) % 2
        w = dict(ENV, **luts)
        w.update(C_FUNCTION="011", C_HORIZ=str(h), C_PX_I="1", C_SEL_P=sc, C_SELX=sx, C_Y12=y12, INIT_L30=B(r.choice([6, 9, 1, 14, 2, 4]), 4))
        cfgs.append(_cfg("c_pxi_%d_h%d" % (i, h), "east_PINX", w, HELPERS[(i + 1) % 4], part="C", horiz=h))
    for i in range(4):                                   # COUTX with C_COMP = 1 (random L30), C_HORIZ 0 / 1, route visible at S1 = 1
        luts = {k: B(r.randrange(16), 4) for k in LUTS}
        h = i % 2
        sc, sx, y12 = ROUTES[(i + 2) % 5]
        w = dict(ENV, **luts)
        w.update(C_FUNCTION="011", C_HORIZ=str(h), C_COMP="1", C_COMP_I=str(i // 2), C_SEL_C=sc, C_SELX=sx, C_Y12=y12, INIT_L30=B(r.choice([6, 9, 1, 14, 2, 4, 7, 8]), 4))
        cfgs.append(_cfg("c_comp_co_%d_h%d" % (i, h), "east_CINX", w, HELPERS[(i + 1) % 4], part="C", horiz=h))
    for i in range(6):                                   # POUTX with C_COMP = 1: C_HORIZ x C_COMP_I; the comparator branch (C_HORIZ = 1, L30 = 1) is where C_MULT = 1 meets D0 / the routing mux
        luts = {k: B(r.randrange(16), 4) for k in LUTS}
        h, ci = (1, 0), (1, 1)
        h = (0, 1, 1, 1, 0, 1)[i]
        ci = (0, 0, 1, 0, 1, 1)[i]
        sc, sx, y12 = ROUTES[(i + 3) % 5]
        w = dict(ENV, **luts)
        w.update(C_FUNCTION="011", C_HORIZ=str(h), C_COMP="1", C_COMP_I=str(ci), C_SEL_P=sc, C_SELX=sx, C_Y12=y12, INIT_L30=B(r.choice([6, 9, 1, 14, 2, 4, 7, 8]), 4))
        cfgs.append(_cfg("c_comp_po_%d_h%d_ci%d" % (i, h, ci), "east_PINX", w, HELPERS[(i + 2) % 4], part="C", horiz=h))
    return cfgs


def _cp(cfg):
    return helper(cfg.get("helper", "default"))[1]


def model_F(cfg):
    sig = SIGNAL[cfg["reader"]]
    return model_vectors(cfg["words"], [sig], _cp(cfg))[sig]


# ---------------------------------------------------------------------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------------------------------------------------------------------
_SIGS = ("l00", "l01", "l02", "l10", "l11", "carry_in", "carry_propagate", "carry_generate", "cx_route", "px_route", "comp_out",
         "multo1", "multo2", "OUT1", "OUT2", "coutx_s1", "poutx_s1")


def _signals(cfg):
    V = model_vectors(cfg["words"], list(_SIGS), _cp(cfg))
    cp = _cp(cfg)
    V = {k: v.astype(bool) for k, v in V.items()}
    for n in ("CINX", "PINX", "CINY1", "CINY2", "PINY1", "PINY2"):
        V[n] = x(cp[n]).astype(bool)
    V["IN5"], V["IN8"] = x(4).astype(bool), x(7).astype(bool)
    V["ONE"] = np.ones(NS, bool)
    V["ZERO"] = np.zeros(NS, bool)
    return V


def _multo2_variants(V):
    """MULTO2 formula variants: carry-in source of the l11 ? c : l02 term, carry-in of lo, partial products, mid mux, form of the add term"""
    out = {}
    P = V["PINY2"]
    pps = {"pp=std": (V["IN5"] & P, V["IN8"] & P), "pp=swap": (V["IN8"] & P, V["IN5"] & P), "pp=CINY1": (V["IN5"] & V["CINY1"], V["IN8"] & V["CINY1"])}
    for (an, c), (ln, cl), (pn, (a0, am1)), mux, form in itertools.product(
            (("carry_in", V["carry_in"]), ("CINY1", V["CINY1"]), ("CINX", V["CINX"]), ("0", V["ZERO"])),
            (("CINY1", V["CINY1"]), ("carry_in", V["carry_in"]), ("CINX", V["CINX"])), pps.items(), ("swap", "orig"), ("l11?c:l02", "l11?l02:c")):
        add2 = np.where(V["l11"], c, V["l02"]) if form == "l11?c:l02" else np.where(V["l11"], V["l02"], c)
        hi = add2 ^ V["l10"] ^ a0
        lo = V["l11"] ^ am1 ^ cl
        mid = np.where(lo, V["CINY2"], am1) if mux == "swap" else np.where(lo, am1, V["CINY2"])
        out["add[%s,%s] lo[cin=%s] %s mid[%s]" % (form, an, ln, pn, mux)] = hi ^ mid
    return out


def _multo1_variants(V):
    out = {}
    P = V["PINY2"]
    for (ln, cl), (pn, am1), inv, (yn, y) in itertools.product((("CINY1", V["CINY1"]), ("carry_in", V["carry_in"]), ("CINX", V["CINX"])),
                                                                (("std", V["IN8"] & P), ("IN5", V["IN5"] & P)), (False, True),
                                                                (("CINY2", V["CINY2"]), ("CINY1", V["CINY1"]), ("PINY2", V["PINY2"]))):
        lo = V["l11"] ^ am1 ^ cl
        out["lo[cin=%s,pp=%s%s] ^ %s" % (ln, pn, ",inverted" if inv else "", yn)] = (lo ^ inv) ^ y
    return out


def _depends(F, mask, maxk=5, nbits=15):
    """smallest sets of counter bits (x0..x14, <= maxk) that determine F inside the states of `mask`; -> (bits tuple list, truth table string) or None"""
    idx = np.nonzero(mask)[0]
    if len(idx) == 0:
        return None
    f = F[idx].astype(bool)
    if f.all() or (~f).all():
        return [()], "const %d" % int(f[0])
    bits = [((idx >> b) & 1) for b in range(nbits)]
    for k in range(1, maxk + 1):
        hits = []
        for comb in itertools.combinations(range(nbits), k):
            key = np.zeros(len(idx), dtype=np.int64)
            for b in comb:
                key = key * 2 + bits[b]
            c1 = np.bincount(key[f], minlength=1 << k)
            c0 = np.bincount(key[~f], minlength=1 << k)
            if not ((c1 > 0) & (c0 > 0)).any():
                tt = "".join("1" if c1[i] else ("0" if c0[i] else "-") for i in range(1 << k))
                hits.append((comb, tt))
        if hits:
            return hits[:2], None
    return None


def _fmt_dep(d):
    if d is None:
        return "no dependency on <= 5 of x0..x14"
    hits, const = d
    if const:
        return const
    return "; ".join("x%s tt(msb=first)=%s" % (list(c), tt) for c, tt in hits)


def _best(F, cands, n=3):
    sc = sorted(((int((np.asarray(c) != F).sum()), nm) for nm, c in cands.items()))
    return sc[:n]


def _fit_coutx(cfg, F, V):
    w = cfg["words"]
    H, CXI = int(w.get("C_HORIZ", "0")), int(w.get("C_CX_I", "0"))
    route = V["cx_route"]
    P2, P1 = V["carry_propagate"], None
    pv = {"P(model)": P2, "~P(model)": ~P2, "1": V["ONE"], "0": V["ZERO"]}
    cands = {}
    for mn, m in _multo2_variants(V).items():
        for pn, p in pv.items():
            s1 = bool(CXI) | (bool(H) & p)
            cands["%s | route when S1=%s%s" % (mn, "C_CX_I|H&", pn)] = np.where(s1, route, m).astype(np.uint8)
    return cands


def _fit_poutx(cfg, F, V):
    w = cfg["words"]
    H, PXI, COMP, CI = int(w.get("C_HORIZ", "0")), int(w.get("C_PX_I", "0")), int(w.get("C_COMP", "0")), int(w.get("C_COMP_I", "0"))
    cands = {}
    branch = {"route": V["px_route"], "~C_COMP_I": np.full(NS, not CI), "C_COMP_I": np.full(NS, bool(CI)), "PINX": V["PINX"], "multo1(var)": None}
    cv = {"comp_out": V["comp_out"], "~comp_out": ~V["comp_out"], "1": V["ONE"], "0": V["ZERO"]}
    for mn, m in _multo1_variants(V).items():
        for cn, c in cv.items():
            for bn, b in branch.items():
                if b is None:
                    continue
                s1 = bool(PXI) | (bool(COMP & H) & c)
                # S0 = 1 (C_MULT): s1 = 0 -> MULTO1, s1 = 1 -> branch (routing multiplexer for the model; other branches as alternatives)
                cands["%s | S1=C_PX_I|COMP&H&%s -> %s" % (mn, cn, bn)] = np.where(s1, b, m).astype(np.uint8)
    return cands


def _pool(cfg, V):
    p = {"route": V["cx_route"] if cfg["reader"] == "east_CINX" else V["px_route"], "MULTO2(model)": V["multo2"], "MULTO1(model)": V["multo1"],
         "CINX": V["CINX"], "PINX": V["PINX"], "generate": V["carry_generate"], "comp_out": V["comp_out"], "~comp_out": ~V["comp_out"],
         "OUT1": V["OUT1"], "OUT2": V["OUT2"], "0": V["ZERO"], "1": V["ONE"], "~C_COMP_I": np.full(NS, not int(cfg["words"].get("C_COMP_I", "0")))}
    p.update({"~" + k: ~v for k, v in list(p.items()) if k in ("route", "MULTO2(model)", "MULTO1(model)", "CINX", "PINX", "generate")})
    return p


def diagnose(cfg, F, M):
    """-> list of lines describing how F (measured) deviates from the model vector M"""
    lines = []
    D = (F != M)
    V = _signals(cfg)
    co = cfg["reader"] == "east_CINX"
    sel = V["coutx_s1"] if co else V["poutx_s1"]
    lines.append("differing states %d; of these with model S1=1 (routing / branch side): %d, with S1=0 (MULTO side): %d" % (int(D.sum()), int((D & sel).sum()), int((D & ~sel).sum())))
    lines.append("diff indicator depends on: " + _fmt_dep(_depends(D.astype(np.uint8), np.ones(NS, bool))))
    lines.append("F inside the differing states depends on: " + _fmt_dep(_depends(F, D)))
    pool = _pool(cfg, V)
    sc = sorted(((float((pool[k][D] == F[D].astype(bool)).mean()), k) for k in pool), reverse=True)[:3]
    lines.append("signals equal to F in the differing states: " + ", ".join("%s %.3f" % (k, s) for s, k in sc))
    cands = _fit_coutx(cfg, F, V) if co else _fit_poutx(cfg, F, V)
    b = _best(F, cands, 4)
    exact = [nm for d, nm in _best(F, cands, 400) if d == 0]
    lines.append("formula library: %d variants explain F exactly%s" % (len(exact), (": " + " || ".join(exact[:4])) if exact else ""))
    lines.append("  best fits (differing states / variant): " + " ; ".join("%d / %s" % t for t in b))
    return lines, exact


def analyze(records):
    bad, diags = 0, []
    cover = {}
    print("%-26s %-9s %-7s %-4s %-5s %s" % ("config", "reader", "helper", "H", "part", "differing states vs cpe.v"))
    for rec in records:
        cfg = rec["cfg"]
        M = model_F(cfg)
        F = np.asarray(rec["F"], dtype=np.uint8)
        d = int((M != F).sum())
        w = cfg["words"]
        key = (cfg["reader"], w.get("C_HORIZ", "0"), cfg.get("helper"))
        cover[key] = cover.get(key, 0) + 1
        print("%-26s %-9s %-7s %-4s %-5s %d" % (cfg["name"], cfg["reader"][5:], cfg.get("helper"), w.get("C_HORIZ", "0"), cfg["meta"].get("part"), d))
        if d:
            bad += 1
            lines, exact = diagnose(cfg, F, M)
            for l in lines:
                print("    " + l)
            diags.append({"name": cfg["name"], "differing": d, "exact_variants": exact, "reader": cfg["reader"]})
    print("configs with deviations:", bad, "of", len(records))
    for rd in ("east_CINX", "east_PINX"):
        ds = [d for d in diags if d["reader"] == rd]
        if ds:
            common = set(ds[0]["exact_variants"]).intersection(*[set(d["exact_variants"]) for d in ds[1:]])
            print("%s: %d deviating configs; %d formula variants explain ALL of them%s" % (rd, len(ds), len(common), (": " + " || ".join(sorted(common)[:5])) if common else " (no single variant: look at the per-config diagnoses)"))
    print("coverage (reader, C_HORIZ, helper): configs")
    for k in sorted(cover):
        print("   ", k, cover[k])
    return {"deviations": bad, "configs": len(records), "diagnoses": diags}


# ---------------------------------------------------------------------------------------------------------------------------------------
# self-test: analyze() must notice perturbed formulas (cpe.v's original, un-swapped mux; lo with CINX; inverted lo for MULTO1; the wrong route select)
# ---------------------------------------------------------------------------------------------------------------------------------------
def _selftest():
    cf = {c["name"]: c for c in configs()}
    recs = []
    c = cf["a00_default_co_h0"]; V = _signals(c)
    P = V["PINY2"]; lo = V["l11"] ^ (V["IN8"] & P) ^ V["CINY1"]
    hi = np.where(V["l11"], V["carry_in"], V["l02"]) ^ V["l10"] ^ (V["IN5"] & P)
    recs.append({"cfg": c, "F": (hi ^ np.where(lo, V["IN8"] & P, V["CINY2"])).astype(np.uint8)})      # original (un-swapped) mid mux
    c = next(c for c in configs() if c["name"].endswith("_co_h1") and c["name"].startswith("a01")); V = _signals(c)
    lo = V["l11"] ^ (V["IN8"] & V["PINY2"]) ^ V["CINX"]
    hi = np.where(V["l11"], V["carry_in"], V["l02"]) ^ V["l10"] ^ (V["IN5"] & V["PINY2"])
    s1 = V["coutx_s1"]
    recs.append({"cfg": c, "F": np.where(s1, V["cx_route"], hi ^ np.where(lo, V["CINY2"], V["IN8"] & V["PINY2"])).astype(np.uint8)})     # lo takes CINX
    c = cf["a02_sely1_po_h1"] if "a02_sely1_po_h1" in cf else next(c for c in configs() if c["name"].startswith("a02_sely1_po")); V = _signals(c)
    lo = V["l11"] ^ (V["IN8"] & V["PINY2"]) ^ V["CINY1"]
    recs.append({"cfg": c, "F": (~lo ^ V["CINY2"]).astype(np.uint8)})                                   # inverted lo
    c = next(c for c in configs() if c["name"].startswith("a03_") and c["name"].endswith("co_h1")); V = _signals(c)
    recs.append({"cfg": c, "F": V["multo2"].astype(np.uint8)})                                           # route select ignored
    ok = model_F(recs[0]["cfg"])
    recs.append({"cfg": cf["a00_default_po_h1"], "F": model_F(cf["a00_default_po_h1"])})                 # untouched: must stay at 0
    res = analyze(recs)
    assert res["deviations"] >= 4 and res["diagnoses"][0]["name"] == "a00_default_co_h0" and res["configs"] == 5
    assert any("mid[orig]" in v for v in res["diagnoses"][0]["exact_variants"]), res["diagnoses"][0]
    assert any("cin=CINX" in v for v in res["diagnoses"][1]["exact_variants"]), res["diagnoses"][1]
    assert any("inverted" in v for v in res["diagnoses"][2]["exact_variants"]), res["diagnoses"][2]
    print("SELFTEST OK: perturbed formulas noticed and identified")


if __name__ == "__main__":
    _selftest()
