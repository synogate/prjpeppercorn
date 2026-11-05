"""Follow-up to wp_y2 (group F, C_MULT = 1): does COUTY2 at C_MULT = 1, C_CY2_I = 0 depend on the comparator?
The four wp_y2 configs f1_mult_couty_i0_h*_* are repeated with several INIT_L30 values of the helper.  Hypothesis H1: through = ~C_CY2_I & (~C_MULT | (mult_sum_hi & mult_sum_lo))
(independent of INIT_L30); the alias H2 (mult_sum_lo & comp_out) would change with INIT_L30.  model_F = H1 (and the unchanged rest of cpe.v: COUTY2 / POUTY2 hypotheses of the analysis of wp_y2).
    python wp_runner.py wp_y2b --dry | --list | (measure) | --analyze"""
import sys, os
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wp_y2

BASE = ["f1_mult_couty_i0_h0_0", "f1_mult_couty_i0_h0_1", "f1_mult_couty_i0_h1_0", "f1_mult_couty_i0_h1_1"]
L30 = ("0000", "1111", "0110", "1001", "0010", "0111")


def configs():
    base = {c["name"]: c for c in wp_y2.configs()}
    out = []
    for b in BASE:
        for l in L30:
            c = dict(base[b])
            c["name"] = "%s_L%s" % (b, l)
            c["cpiny"] = dict(c["cpiny"], INIT_L30=l)
            c["meta"] = dict(c["meta"])
            out.append(c)
    return out


def hyp_F(cfg):
    """COUTY2 hypothesis H1 evaluated for the helper"""
    hw = cfg["cpiny"]
    d = wp_y2.helper_eval(cfg, ["coy2_a", "mult_sum_hi", "mult_sum_lo", "cy2_route"])
    src = wp_y2.lines_of(cfg)
    ciny2 = wp_y2.vec(src["CINY2"])
    mult = hw.get("C_FUNCTION", "000") == "011"
    cy2 = int(hw.get("C_CY2_I", "0"))
    through = ((1 - cy2) & (d["mult_sum_hi"] & d["mult_sum_lo"])) if mult else np.full(wp_y2.NS, 1 - cy2, np.uint8)
    return np.where(through == 1, ciny2, d["coy2_a"] if mult else d["cy2_route"]).astype(np.uint8)


def model_F(cfg):
    return hyp_F(cfg)


def analyze(records):
    bad = 0
    by = {}
    for r in records:
        h = hyp_F(r["cfg"])
        d = int((h != r["F"]).sum())
        old = int((wp_y2.model_F(r["cfg"]) != r["F"]).sum())
        bad += d > 0
        base = r["cfg"]["name"].rsplit("_L", 1)[0]
        by.setdefault(base, []).append((r["cfg"]["name"].rsplit("_L", 1)[1], d, old, int(r["F"].sum())))
        print("%-34s differing vs hypothesis H1: %6d   vs cpe.v: %6d   F ones: %d" % (r["cfg"]["name"], d, old, int(r["F"].sum())))
    print("configs deviating from H1:", bad, "of", len(records))
    for b, v in by.items():
        ones = {x[3] for x in v}
        print("  %s: F identical for all INIT_L30: %s" % (b, "yes" if len(ones) == 1 else "NO (ones: %s)" % sorted(ones)))
    return {"deviations": bad}
