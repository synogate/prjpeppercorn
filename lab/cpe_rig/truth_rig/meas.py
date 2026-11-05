"""Measurement with the version-3 rig: patch the DUT (X146Y19) and the two CP helpers, pick OUT1 or OUT2 of the DUT with the selector MX8, load, capture
UART0_RX, compare with cpe.v.
    from meas import measure;  F, info, mism = measure('name', {'C_O2': '01', ...}, obs='OUT2')
Every word of the DUT and of the two helpers is removed first (nextpnr's own words for them are irrelevant, only their routing stays); the selector keeps its
routing words and gets C_BR = 1 and C_SN."""
import sys, os, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tt_rig
from tt_rig import load, capture, extract, N, DUT, REPO, BASE, PNR
import rig
sys.path.insert(0, os.path.join(REPO, "schematics", "cpe", "sim"))
from expect import expect

CPINX, CPINY = (145, 19), (146, 18)
SEL_SN = {"OUT1": "000", "OUT2": "001"}     # selector input of the DUT's OUT1 / OUT2 wire (checked by selftest)
# Pip polarity of the control pins CLK / EN / SR: depends on the routing of the build, measured by calibrate_pins() into calib.json (IN1..IN8 are direct by construction)
CALIB = os.path.join(os.path.dirname(BASE), "calib.json")
PIN_INV = json.load(open(CALIB)).get("PIN_INV", {"CLK": 0, "EN": 0, "SR": 0}) if os.path.exists(CALIB) else {"CLK": 0, "EN": 0, "SR": 0}
LOW = 11                                    # IN1..IN8 = x0..x7, CLK / EN / SR = x8..x10; the CP inputs are x11..x16


def sel_cell():
    m = json.load(open(PNR))["modules"]["top"]["cells"]["sel"]["attributes"]["NEXTPNR_BEL"]
    x, y = m.split("/")[0][1:].split("Y")
    return int(x), int(y)


def base_words(x, y):
    tile, cid = rig.tile_of(x, y)
    blocks = open(BASE, encoding="utf-8").read().split("\n.tile ")
    for blk in blocks[1:]:
        h, _, rest = blk.partition("\n")
        if h.strip() == tile:
            return [l.split(" ")[0][len("CPE%d." % cid):] for l in rest.split("\n") if l.startswith("CPE%d." % cid)]
    return []


def edits_for(dut_words, cpinx=None, cpiny=None, obs="OUT2", extra=None):
    """extra: {(x, y, word): value | None} additional edits for any other CPE (None deletes the word), applied last"""
    e = {}
    for cell, words in ((DUT, dut_words), (CPINX, cpinx), (CPINY, cpiny)):
        for w in base_words(*cell):
            e[(*cell, w)] = None
        for k, v in (words or {}).items():
            e[(*cell, k)] = v
    sx, sy = sel_cell()
    e[(sx, sy, "C_BR")] = "1"
    e[(sx, sy, "C_SN")] = SEL_SN[obs]
    e.update(extra or {})
    return e


def expected(words, out="OUT2", cp=None):
    """cp: {'CINX': 11, ...} = CP input follows counter bit k (all other CP inputs are held 0).  The result is indexed by cp_key(s, cp)."""
    cp = cp or {}
    names = list(cp)
    rows = []
    for key in range(1 << (LOW + len(names))):
        s = key & ((1 << LOW) - 1)
        r = {"IN%d" % (i + 1): (s >> i) & 1 for i in range(8)}
        r.update({"CLK": ((s >> 8) & 1) ^ PIN_INV["CLK"], "EN": ((s >> 9) & 1) ^ PIN_INV["EN"], "SR": ((s >> 10) & 1) ^ PIN_INV["SR"]})
        for j, n in enumerate(names):
            r[n] = (key >> (LOW + j)) & 1
        rows.append(r)
    w = {k: v for k, v in words.items() if v is not None}
    return [r[out] for r in expect(w, rows)]


def cp_key(s, cp):
    k = s & ((1 << LOW) - 1)
    for j, n in enumerate(cp or {}):
        k |= ((s >> cp[n]) & 1) << (LOW + j)
    return k


def measure(name, words, cpinx=None, cpiny=None, obs="OUT2", out=None, cp=None):
    load(name, edits_for(words, cpinx, cpiny, obs))
    r = capture()
    if not r:
        return None, {"error": "no capture"}, None
    F, info = extract(r[0], r[1], r[2])
    if F is None:
        return None, info, None
    E = expected(words, out or obs, cp)
    mism = 0
    for s in range(1 << N):
        e = E[cp_key(s, cp)]
        if e in "01" and int(e) != F[s]:
            mism += 1
    return F, info, mism


def calibrate_pins():
    """Polarity of CLK / EN / SR at the DUT: the LUT1 word 10 passes the pin; with C_BR = 0 and C_SN = 0 the mux8 selects IN(1 + weight * pin), weights 1 / 2 / 4."""
    global PIN_INV
    res = {}
    for pin, word, weight, bitpos in (("CLK", "C_CPE_CLK", 1, 8), ("EN", "C_CPE_EN", 2, 9), ("SR", "C_CPE_RES", 4, 10)):
        words = {"C_BR": "0", "C_SN": "000", "C_2D_IN": "0", "C_O2": "01", word: "10"}
        load("cal_" + pin, edits_for(words, None, None, "OUT2"))
        r = capture()
        F, info = extract(r[0], r[1], r[2])
        fit = {}
        for inv in (0, 1):
            fit[inv] = sum(1 for s in range(1 << N) if F[s] != ((s >> (weight * (((s >> bitpos) & 1) ^ inv))) & 1))
        res[pin] = 0 if fit[0] == 0 else (1 if fit[1] == 0 else None)
        print(pin, "direct" if res[pin] == 0 else "INVERTED" if res[pin] == 1 else "unclear %s" % fit)
    cal = json.load(open(CALIB)) if os.path.exists(CALIB) else {}
    cal["PIN_INV"] = res
    json.dump(cal, open(CALIB, "w"), indent=1)
    PIN_INV = res
    return res


def measure_raw(name, words, cpinx=None, cpiny=None, obs="OUT2", extra=None):
    """No expectation: -> F, info"""
    load(name, edits_for(words, cpinx, cpiny, obs, extra))
    r = capture()
    if not r:
        return None, {"error": "no capture"}
    return extract(r[0], r[1], r[2])


def identify(F):
    """Which signal does F follow?  -> (name, mismatching states) of the best of x0..x16, ~x0..~x16, 0, 1"""
    best = None
    for k in range(N):
        for inv in (0, 1):
            d = sum(1 for s in range(1 << N) if F[s] != (((s >> k) & 1) ^ inv))
            if best is None or d < best[1]:
                best = (("~" if inv else "") + "x%d" % k, d)
    for c in (0, 1):
        d = sum(1 for b in F if b != c)
        if d < best[1]:
            best = ("const%d" % c, d)
    return best


CPMAP = {"CINX": 11, "PINX": 12, "CINY1": 14, "CINY2": 13, "PINY1": 13, "PINY2": 14}     # which counter bit each CP input carries with the helpers as configured (CPX, CPY + C_PY1_I)


def internals(words, signals=("COUTX", "cx_route", "carry_generate", "carry_propagate", "multo2", "comp_out", "OUT1", "OUT2", "l10", "l11"), cp=CPMAP):
    """cpe.v evaluated over all 2^15 combinations of x0..x10 and the four CP bits x11..x14; returns {signal: list indexed by key = (s & 2047) | (((s >> 11) & 15) << 11)}"""
    import subprocess, tempfile
    from expect import INPUTS, _literal
    w = {k: v for k, v in words.items() if v is not None}
    for k in ("C_RAM_I1", "C_RAM_I2"):
        v = w.get(k, "0")
        w[k] = "0" if str(v) in ("1", "1'b1") else "1"
    params = ", ".join(".%s(%s)" % (k, _literal(k, v)) for k, v in w.items())
    outs = ["COUTX", "OUT1", "OUT2"]
    lines = ["module tb_int;", "  reg " + ", ".join(INPUTS) + ";", "  wire COUTX, OUT1, OUT2, RAM_O1, RAM_O2, COUTY1, COUTY2, POUTX, POUTY1, POUTY2;",
             "  cpe #(%s) u (%s);" % (params, ", ".join(".%s(%s)" % (p, p) for p in INPUTS + ["OUT1", "OUT2", "RAM_O1", "RAM_O2", "COUTX", "COUTY1", "COUTY2", "POUTX", "POUTY1", "POUTY2"])),
             "  integer key;", "  initial begin"]
    sig_exprs = {s: ("u." + s if s not in outs else s) for s in signals}
    lines.append("    for (key = 0; key < %d; key = key + 1) begin" % (1 << 15))
    for i in range(8):
        lines.append("      IN%d = key[%d];" % (i + 1, i))
    lines.append("      CLK = key[8] ^ %d; EN = key[9] ^ %d; SR = key[10] ^ %d;" % (PIN_INV["CLK"], PIN_INV["EN"], PIN_INV["SR"]))
    bitpos = {b: 11 + j for j, b in enumerate((11, 12, 13, 14))}
    for name in INPUTS:
        if name in cp:
            lines.append("      %s = key[%d];" % (name, bitpos[cp[name]]))
        elif name not in ("CLK", "EN", "SR") and not (name.startswith("IN") and name[2:].isdigit()):
            lines.append("      %s = 0;" % name)
    lines.append("      #1;")
    lines.append('      $display("ROW %s", {%s});' % ("%b" * len(signals), ", ".join(sig_exprs[s] for s in signals)))
    lines += ["    end", "    $finish;", "  end", "endmodule"]
    with tempfile.TemporaryDirectory() as tmp:
        tb, vv = os.path.join(tmp, "tb.v"), os.path.join(tmp, "tb.vvp")
        open(tb, "w").write(chr(10).join(lines))
        subprocess.run(["iverilog", "-g2012", "-o", vv, tb, os.path.join(REPO, "schematics", "cpe", "sim", "cpe.v")], check=True, capture_output=True)
        out = subprocess.run(["vvp", vv], check=True, capture_output=True, text=True).stdout
    rows = [l[4:].strip() for l in out.splitlines() if l.startswith("ROW ")]
    assert len(rows) == 1 << 15, len(rows)
    return {s: [r[i] for r in rows] for i, s in enumerate(signals)}


def key15(s):
    return (s & 2047) | (((s >> 11) & 15) << 11)
