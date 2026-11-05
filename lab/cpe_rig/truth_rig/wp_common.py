"""Shared helpers for work packages: model vectors over the 2**17 counter states, helper variants, the common environment.  Read-only; no hardware access."""
import sys, os
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tt_rig import N
from meas import internals, key15, CPMAP
from map_coutx import ENV, CPX, CPYP, B
from east import EAST_CINX
from map_poutx import EAST_PINX

NS = 1 << N
S = np.arange(NS)
_KEYS = np.array([key15(int(s)) for s in S])


def x(b):
    """counter bit b over all states (state s = bit pattern x0..x16)"""
    return ((S >> b) & 1).astype(np.uint8)


# the four south-helper settings of S19 / S20: bits carried by (CINY1, CINY2, PINY2, PINY1) and the helper words to add to CPYP
HELPER_VARIANTS = {
    "default": ({}, {"CINY1": 14, "CINY2": 13, "PINY2": 14, "PINY1": 13}),
    "sely1": ({"C_SELY1": "1"}, {"CINY1": 13, "CINY2": 13, "PINY2": 14, "PINY1": 14}),
    "sely2": ({"C_SELY2": "1"}, {"CINY1": 14, "CINY2": 14, "PINY2": 13, "PINY1": 13}),
    "both": ({"C_SELY1": "1", "C_SELY2": "1"}, {"CINY1": 13, "CINY2": 14, "PINY2": 13, "PINY1": 14}),
}


def helper(variant="default"):
    """-> (cpiny words, cp mapping for the model) of a south-helper variant"""
    hw, cp = HELPER_VARIANTS[variant]
    return dict(CPYP, **hw), dict(CPMAP, **cp)


def model_vectors(words, signals, cp=None):
    """cpe.v evaluated over all 2**17 states: {signal: uint8 array}.  signals: any wire / output of cpe.v (COUTX, COUTY1, POUTX, OUT1, comp_out, multo2, carry_generate, ...).
    cp: which counter bit each CP input carries (default CPMAP: CINX x11, PINX x12, CINY1 x14, CINY2 x13, PINY1 x13, PINY2 x14); only x11..x14 are modelled."""
    d = internals(words, tuple(signals), cp if cp is not None else CPMAP)
    return {n: np.array([int(d[n][k]) for k in _KEYS], dtype=np.uint8) for n in signals}


def explain(F, cand, tol=0):
    """which candidate vectors (dict name -> uint8 array) equal F (<= tol differing states)"""
    return [n for n, c in cand.items() if int((np.asarray(c) != F).sum()) <= tol]


def model_eval(words, signals, inputs, default_in=1):
    """cpe.v evaluated for arbitrary input vectors.  inputs: {port: array of 2**17 values (0/1)} for any ports of cpe.v (IN1..IN8, CLK, EN, SR, CINX, CINY1, CINY2, PINX, PINY1, PINY2, RAM_I1, RAM_I2);
    ports not given are 0, except IN1..IN8 which default to `default_in` (unconnected data pins read 1 on the hardware).  -> {signal: uint8 array of 2**17}.
    Use this for a CPE that sees other signals than the DUT (e.g. the south helper, whose IN1..IN4 carry x13..x16)."""
    import subprocess, tempfile
    from expect import INPUTS, _literal
    from meas import REPO
    w = {k: v for k, v in words.items() if v is not None}
    for k in ("C_RAM_I1", "C_RAM_I2"):
        v = w.get(k, "0")
        w[k] = "0" if str(v) in ("1", "1'b1") else "1"
    cols = []
    for p in INPUTS:
        if p in inputs:
            cols.append(np.asarray(inputs[p], dtype=np.uint8))
        else:
            cols.append(np.full(NS, default_in if (p.startswith("IN") and p[2:].isdigit()) else 0, dtype=np.uint8))
    M = np.stack(cols, axis=1)
    uniq, inv = np.unique(M, axis=0, return_inverse=True)
    inv = np.asarray(inv).reshape(-1)
    outs = ["OUT1", "OUT2", "COUTX", "COUTY1", "COUTY2", "POUTX", "POUTY1", "POUTY2", "RAM_O1", "RAM_O2"]
    params = ", ".join(".%s(%s)" % (k, _literal(k, v)) for k, v in w.items())
    lines = ["module tb_eval;", "  reg " + ", ".join(INPUTS) + ";", "  wire " + ", ".join(outs) + ";",
             "  cpe #(%s) u (%s);" % (params, ", ".join(".%s(%s)" % (p, p) for p in INPUTS + outs)), "  initial begin"]
    ex = {s: (s if s in outs else "u." + s) for s in signals}
    for row in uniq:
        lines.append("    " + " ".join("%s = %d;" % (p, int(v)) for p, v in zip(INPUTS, row)) + " #1;")
        lines.append('    $display("ROW %s", {%s});' % ("%b" * len(signals), ", ".join(ex[s] for s in signals)))
    lines += ["    $finish;", "  end", "endmodule"]
    with tempfile.TemporaryDirectory() as tmp:
        tb, vv = os.path.join(tmp, "tb.v"), os.path.join(tmp, "tb.vvp")
        open(tb, "w").write(chr(10).join(lines))
        subprocess.run(["iverilog", "-g2012", "-o", vv, tb, os.path.join(REPO, "schematics", "cpe", "sim", "cpe.v")], check=True, capture_output=True)
        out = subprocess.run(["vvp", vv], check=True, capture_output=True, text=True).stdout
    rows = [l[4:].strip() for l in out.splitlines() if l.startswith("ROW ")]
    assert len(rows) == len(uniq), (len(rows), len(uniq))
    return {s: np.array([int(r[i]) if r[i] in "01" else 2 for r in rows], dtype=np.uint8)[inv] for i, s in enumerate(signals)}      # 2 = unknown (x)


def dut_inputs():
    """the inputs the DUT sees (IN1..IN8 = x0..x7, CLK/EN/SR = x8..x10, CP inputs as in CPMAP); a starting point for model_eval"""
    d = {"IN%d" % (i + 1): x(i) for i in range(8)}
    d.update({"CLK": x(8), "EN": x(9), "SR": x(10)})
    d.update({k: x(b) for k, b in CPMAP.items()})
    return d
