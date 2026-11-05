"""Work package wp_gaps: open cases of the COUTX / POUTX validation (S17, S21, S22 leave these open).
  point 1  COUTX routing codes 01 / 10 / 11 (both C_Y12) for C_FUNCTION 1..7, C_CX_I = 1 (south helper 'default' / 'both' so that CINY1 != CINY2)
  point 2  POUTX routing codes 10 and 11 (both C_Y12) at f in {0,1,3}; codes 00 / 01 at f in {2,4,5,6,7}   (C_PX_I = 1)
  point 3  POUTX grid (C_HORIZ x C_COMP x C_PX_I x C_COMP_I x INIT_L30) at f in {2,4,5,6,7}, reduced: 5 PX_I = 0 cells per f + the routing cells of point 2
  point 4  does COUTX depend on C_COMP / C_COMP_I / INIT_L30?  (C_CX_I 0 / 1 x f 0,1,2 x C_COMP x C_COMP_I, asymmetric varying INIT_L30)
  point 5  COUTX at C_HORIZ = 1, C_CX_I = 0 with ADDF / ADDF2 (f 1, 2, 6), random LUT trees, helper variants sely1 / sely2 / both
  python wp_runner.py wp_gaps --dry      python wp_gaps.py --selftest   (analyze() against deliberately perturbed vectors)
"""
import sys, os, random, itertools
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_common import ENV, model_vectors, helper, x, NS, S

B = lambda v, n: format(v, "0%db" % n)
L30S = ["0110", "0100", "0010", "1011", "0111", "1000", "1101", "0001"]       # asymmetric / varying comparator LUTs
LUTS = ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20")
SIGS = ("COUTX", "POUTX", "OUT1", "OUT2", "comp_out", "carry_generate", "carry_propagate", "multo1", "multo2", "cx_route", "px_route")
READ = {"east_CINX": "COUTX", "east_PINX": "POUTX"}


def _cfg(name, reader, words, pt, var="default", **meta):
    c = {"name": name, "reader": reader, "words": words, "helper": var, "meta": dict(meta, pt=pt)}
    if var != "default":
        c["cpiny"] = helper(var)[0]
    return c


def configs():
    cfgs = []
    rnd = random.Random(2931)
    # ---- point 1: COUTX routing codes 01, 10, 11 (C_CX_I = 1)
    for f in range(1, 8):
        for code in ("01", "10", "11"):
            for y12 in ("0", "1") if code == "11" else ("0",):
                h = str((f + int(code, 2)) % 2)
                var = "default" if (f + int(y12)) % 2 == 0 else "both"       # alternate: CINY1 / CINY2 swap their bits
                l30 = L30S[(f + int(code, 2)) % len(L30S)] if code == "10" else "0110"
                w = dict(ENV, C_FUNCTION=B(f, 3), C_HORIZ=h, C_CX_I="1", C_SEL_C=code[0], C_SELX=code[1], C_Y12=y12, INIT_L30=l30)
                cfgs.append(_cfg("g1_f%d_c%s%s_h%s_%s" % (f, code, "_y" + y12 if code == "11" else "", h, var), "east_CINX", w, 1, var, code=code))
    # ---- point 2: POUTX routing codes ({C_SEL_P, C_SELX}: 00 OUT2, 01 OUT1, 10 ~comp, 11 PINY1 / PINY2), C_PX_I = 1
    for f in (0, 1, 3):
        for code, y12 in (("10", "0"), ("11", "0"), ("11", "1")):
            var = "default" if (f + int(y12)) % 2 == 0 else "both"
            l30 = L30S[(f * 3 + int(code, 2)) % len(L30S)]
            h = str((f + int(y12)) % 2)
            comp = str(int(code == "10"))
            w = dict(ENV, C_FUNCTION=B(f, 3), C_HORIZ=h, C_COMP=comp, C_COMP_I=str((f + int(code, 2)) % 2), C_PX_I="1", C_SEL_P=code[0], C_SELX=code[1], C_Y12=y12, INIT_L30=l30)
            cfgs.append(_cfg("g2_f%d_c%s%s_%s" % (f, code, "_y" + y12 if code == "11" else "", var), "east_PINX", w, 2, var, code=code))
    for i, f in enumerate((2, 4, 5, 6, 7)):                                  # codes 00 / 01 at the remaining functions (also the PX_I = 1 cells of point 3)
        for code in ("00", "01"):
            h, comp, ci = str((i + int(code)) % 2), str((i + 1) % 2), str((i + int(code) + 1) % 2)
            w = dict(ENV, C_FUNCTION=B(f, 3), C_HORIZ=h, C_COMP=comp, C_COMP_I=ci, C_PX_I="1", C_SEL_P=code[0], C_SELX=code[1], INIT_L30=L30S[(2 * i + int(code)) % len(L30S)])
            cfgs.append(_cfg("g2_f%d_c%s_h%s_cp%s_ci%s" % (f, code, h, comp, ci), "east_PINX", w, 2, code=code))
    # ---- point 3: POUTX grid, C_PX_I = 0 (comparator condition C_COMP & C_HORIZ & L30; C_COMP_I constant)
    for i, f in enumerate((2, 4, 5, 6, 7)):
        cells = [("1", "1", "0"), ("1", "1", "1"), ("0", "1", "1"), ("1", "0", "0"), ("1", "1", "0")]      # (C_HORIZ, C_COMP, C_COMP_I)
        for j, (h, comp, ci) in enumerate(cells):
            l30 = "0000" if j == 4 else L30S[(i + 2 * j) % len(L30S)]
            w = dict(ENV, C_FUNCTION=B(f, 3), C_HORIZ=h, C_COMP=comp, C_COMP_I=ci, C_PX_I="0", INIT_L30=l30)
            cfgs.append(_cfg("g3_f%d_h%s_cp%s_ci%s_l%s" % (f, h, comp, ci, l30), "east_PINX", w, 3))
    # ---- point 4: COUTX dependence on C_COMP / C_COMP_I / INIT_L30 (routing code 00 = OUT1 at C_CX_I = 1)
    n = 0
    for cx, f, comp, ci in itertools.product("01", (0, 1, 2), "01", "01"):
        l30 = L30S[n % len(L30S)]
        n += 1
        w = dict(ENV, C_FUNCTION=B(f, 3), C_HORIZ="1", C_CX_I=cx, C_COMP=comp, C_COMP_I=ci, INIT_L30=l30)
        cfgs.append(_cfg("g4_cx%s_f%d_cp%s_ci%s_l%s" % (cx, f, comp, ci, l30), "east_CINX", w, 4))
    # ---- point 5: COUTX with adders, C_HORIZ = 1, C_CX_I = 0, random LUT trees under the non-default helper variants
    for f in (1, 2, 6):
        for var in ("sely1", "sely2", "both"):
            for t in range(2):
                luts = {k: B(rnd.randrange(16), 4) for k in LUTS}
                w = dict(ENV, **dict(luts, C_FUNCTION=B(f, 3), C_HORIZ="1", C_CX_I="0"))
                cfgs.append(_cfg("g5_f%d_%s_%d" % (f, var, t), "east_CINX", w, 5, var))
    return cfgs


# ------------------------------------------------------------------------------------------------ model
_CACHE = {}


def _cp(cfg):
    return helper(cfg.get("helper", "default"))[1]


def _sigs(cfg):
    k = (cfg["name"], tuple(sorted(cfg["words"].items())), cfg.get("helper", "default"))
    if k not in _CACHE:
        _CACHE[k] = model_vectors(cfg["words"], SIGS, _cp(cfg))
    return _CACHE[k]


def model_F(cfg):
    return _sigs(cfg)[READ[cfg["reader"]]]


# ------------------------------------------------------------------------------------------------ analysis
def _candidates(cfg):
    """all candidate source vectors (merged by equal content, with complements): {label: array}"""
    sg, cp = _sigs(cfg), _cp(cfg)
    base = {"OUT1": sg["OUT1"], "OUT2": sg["OUT2"], "L30raw": sg["comp_out"], "G": sg["carry_generate"], "P": sg["carry_propagate"],
            "MULTO1": sg["multo1"], "MULTO2": sg["multo2"], "const0": np.zeros(NS, np.uint8), "const1": np.ones(NS, np.uint8)}
    for n in ("CINX", "PINX", "CINY1", "CINY2", "PINY1", "PINY2"):
        base["%s(x%d)" % (n, cp[n])] = x(cp[n])
    for b in range(11):
        base["x%d" % b] = x(b)
    for b in (15, 16):
        base["x%d" % b] = x(b)
    allc = {}
    for k, v in base.items():
        allc[k] = np.asarray(v, np.uint8)
        if not k.startswith("const"):
            allc["~" + k] = 1 - np.asarray(v, np.uint8)
    merged = {}
    for k, v in allc.items():
        key = v.tobytes()
        merged.setdefault(key, []).append(k)
    return {"/".join(ks): np.frombuffer(kb, np.uint8) for kb, ks in merged.items()}


def _dep(F, sel, maxsize=4):
    """smallest sets of counter bits that determine F inside the states `sel`: -> (size, [bit tuples])"""
    idx = np.flatnonzero(sel)
    if len(idx) == 0:
        return None
    Fs = F[idx].astype(np.float64)
    bits = [((idx >> b) & 1) for b in range(17)]
    for size in range(maxsize + 1):
        hits = []
        for comb in itertools.combinations(range(17), size):
            key = np.zeros(len(idx), np.int64)
            for b in comb:
                key = key * 2 + bits[b]
            cnt = np.bincount(key, minlength=1 << size)
            one = np.bincount(key, weights=Fs, minlength=1 << size)
            if np.all((one == 0) | (one == cnt)):
                hits.append(comb)
                if len(hits) >= 3:
                    break
        if hits:
            return size, hits
    return None


def _diagnose(cfg, F, m):
    sg = _sigs(cfg)
    cand = _candidates(cfg)
    D = F != m
    out = []
    ex = [k for k, c in cand.items() if int((c != F).sum()) == 0]
    if ex:
        out.append("whole vector equals: " + " ; ".join(ex))
    else:
        near = sorted(((int((c != F).sum()), k) for k, c in cand.items()))[:3]
        out.append("no single source; nearest: " + ", ".join("%s (%d diff)" % (k, d) for d, k in near))
        # split diagnosis: F = mux(splitter, candA, candB)
        spl = {"carry_propagate": sg["carry_propagate"], "L30 raw": sg["comp_out"]}
        for k, c in cand.items():
            if not k.startswith("const"):
                spl["split:" + k] = c
        res = []
        for sn, sv in spl.items():
            parts, tot = [], 0
            for v in (0, 1):
                sel = sv == v
                if not sel.any():
                    parts.append((v, "(empty)", 0))
                    continue
                best = min(((int((c[sel] != F[sel]).sum()), k) for k, c in cand.items()))
                names = [k for k, c in cand.items() if int((c[sel] != F[sel]).sum()) == best[0]]
                parts.append((v, "/".join(names[:4]) + (" ..." if len(names) > 4 else ""), best[0]))
                tot += best[0]
            res.append((tot, 0 if sn in ("carry_propagate", "L30 raw") else 1, sn, parts))
        res.sort(key=lambda r: (r[0], r[1]))
        for tot, _, sn, parts in res[:3]:
            out.append("split by %s: %s  [%d diff]" % (sn, "; ".join("=%d -> %s (%d)" % (v, nm, d) for v, nm, d in parts), tot))
    for nm, v in (("carry_propagate", sg["carry_propagate"]), ("L30 raw", sg["comp_out"])):
        out.append("differing states with %s=0 / 1: %d / %d" % (nm, int((D & (v == 0)).sum()), int((D & (v == 1)).sum())))
    d1 = _dep(F, np.ones(NS, bool))
    out.append("F depends only on bits %s" % ("x%s (%d bits)" % (d1[1][0], d1[0]) if d1 else "- (more than 4 bits)"))
    d2 = _dep(D.astype(np.uint8), np.ones(NS, bool))
    out.append("deviation set depends only on bits %s" % ("x%s (%d bits)" % (d2[1][0], d2[0]) if d2 else "- (more than 4 bits)"))
    return out


def analyze(records):
    bad, pts, tot = 0, {}, {}
    print("%-34s %-9s %-8s %s" % ("config", "reader", "pt", "differing states vs cpe.v (of %d)" % NS))
    for r in records:
        cfg, F = r["cfg"], np.asarray(r["F"], np.uint8)
        m = model_F(cfg)
        d = int((m != F).sum())
        pt = cfg.get("meta", {}).get("pt", 0)
        tot[pt] = tot.get(pt, 0) + 1
        uns = (r.get("info") or {}).get("unsure_states")
        print("%-34s %-9s %-8s %d%s" % (cfg["name"], cfg["reader"][5:], pt, d, "   [%s unsure states]" % uns if uns else ""))
        if d:
            bad += 1
            pts[pt] = pts.get(pt, 0) + 1
            for l in _diagnose(cfg, F, m):
                print("      " + l)
    print("configs with deviations:", bad, "of", len(records))
    for pt in sorted(tot):
        print("  point %s: %d of %d configs deviate" % (pt, pts.get(pt, 0), tot[pt]))
    return {"deviations": bad, "configs": len(records), "per_point": {p: (pts.get(p, 0), tot[p]) for p in tot}}


# ------------------------------------------------------------------------------------------------ self test of analyze() (no hardware)
def _selftest():
    cfgs = configs()
    pick = {c["name"]: c for c in cfgs}
    a = pick["g1_f2_c11_y0_h1_both" if "g1_f2_c11_y0_h1_both" in pick else [n for n in pick if n.startswith("g1_f2_c11_y0")][0]]
    b = [c for c in cfgs if c["name"].startswith("g3_f2_h1_cp1_ci0")][0]
    c = [c for c in cfgs if c["name"].startswith("g5_f1_")][0]
    recs = []
    cp = _cp(a)
    recs.append({"cfg": a, "F": x(cp["CINY2"]).copy()})                 # Y12 = 0 should give CINY1: pretend the hardware gave CINY2
    F = model_F(b).copy(); F[S % 1000 == 7] ^= 1                          # scattered flips
    recs.append({"cfg": b, "F": F})
    F = model_F(c).copy(); sg = _sigs(c); F[sg["carry_propagate"] == 1] = sg["carry_generate"][sg["carry_propagate"] == 1] ^ 1      # wrong generate term
    recs.append({"cfg": c, "F": F})
    recs.append({"cfg": c, "F": model_F(c)})
    recs[-1] = {"cfg": dict(c, name=c["name"] + "_ok"), "F": model_F(c)}
    s = analyze(recs)
    assert s["deviations"] == 3 and s["configs"] == 4, s
    print("selftest ok: 3 perturbed vectors noticed, 1 unperturbed accepted")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        c = configs()
        print(len(c), "configs, est. hardware time %.0f min at 6 s" % (len(c) * 6 / 60))
