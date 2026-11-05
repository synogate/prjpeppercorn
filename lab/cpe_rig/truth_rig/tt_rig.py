"""Truth-table rig (method B): every internal input pin of the CPE under test gets its own orthogonal 50 % square wave, UART0_TX carries the
reference clock, UART0_RX is the pin under test. One capture of the pin gives the output function over all 2^14 input combinations.

    python tt_rig.py build                    # build the rig in the work directory (once; deterministic)
    python tt_rig.py calibrate                # reader polarity and polarity of IN1..IN8 (about 9 captures)
    python tt_rig.py run NAME X:Y:WORD=VALUE ...   # patch, load, capture, compare with cpe.v (DUT words only, X:Y = 146:19)

Library: from tt_rig import build, calibrate, measure, expected, compare, bit, N
Everything is written to the work directory outside lab/ (CPE_RIG_WORK, default <tmp>/cpe_rig_work/truth).  See README.md here and ../README.md.
"""
import sys, os, re, json, math, subprocess, shutil
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
CPE_RIG = os.path.dirname(HERE)
LAB = os.path.dirname(CPE_RIG)
REPO = os.path.dirname(LAB)
sys.path.insert(0, CPE_RIG)
sys.path.insert(0, os.path.join(REPO, "schematics", "cpe", "sim"))      # expect.py
import rig
from expect import expect

N = 17                                    # number of orthogonal signals x[0..16]; the reference is bit 17 of the counter
TT = os.path.join(rig.WORK, "truth")
BASE = os.path.join(TT, "bitfile.txt")
PNR = os.path.join(TT, "pnr.json")
CALIB = os.path.join(TT, "calib.json")
rig.BASE = BASE
DUT, W, S = (146, 19), (145, 19), (146, 18)
# Reader at X147Y19: IN4 is replaced by CINX (C_I2), output of the L2T4 half goes to UART0_RX. Fixed words, whatever nextpnr wrote.
# The base DUT is an MX8; its select LUT1 words are removed so that the patched CPE starts from an empty configuration
DUT_BASE = {("C_CPE_CLK"): None, ("C_CPE_EN"): None, ("C_CPE_RES"): None}
READER = {(147, 19, "INIT_L00"): "0000", (147, 19, "INIT_L01"): "1100", (147, 19, "INIT_L10"): "1100", (147, 19, "C_I2"): "1"}
# West neighbour: COUTX = OUT1 = MUXOUT = its IN1 (= x[8], arrives as CINX at the DUT)
W_SOURCE = {(*W, "C_BR"): "1", (*W, "C_SN"): "000", (*W, "C_O1"): "01", (*W, "C_CX_I"): "1"}


def build(force=False):
    if os.path.exists(BASE) and os.path.exists(PNR) and not force:
        return BASE
    os.makedirs(TT, exist_ok=True)
    for f in ("top.v", "Makefile", "pins.ccf", "top.sdc", "place_mx8.py"):
        shutil.copy(os.path.join(HERE, f), TT)
    for f in ("bitfile.txt", "pnr.json", "synth.json"):
        p = os.path.join(TT, f)
        if os.path.exists(p):
            os.remove(p)
    subprocess.run(["make", "bitfile.txt"], cwd=TT, check=True)
    return BASE


def mapping():
    """Pin -> x index from pnr.json (the DUT is an MX8, so IN k = x[k-1]; W and S are LUT cells whose inputs nextpnr may swap). -> {'DUT': {1..8: k}, 'W': {1..4: k}, 'S': {1..4: k}}"""
    build()
    m = json.load(open(PNR))["modules"]["top"]
    names = {}
    for n, v in m["netnames"].items():
        for b in v["bits"]:
            names.setdefault(b, []).append(n)

    def pins(cell):
        out = {}
        for port, bits in m["cells"][cell]["connections"].items():
            if port.startswith("IN") and bits:
                nm = [re.match(r"x\[(\d+)\]", n) for n in names.get(bits[0], [])]
                nm = [g for g in nm if g]                # also x[k]$bridgeN$muxout (the signal went through a bridge CPE)
                if nm:
                    out[int(port[2:])] = int(nm[0].group(1))
        return out
    return {"DUT": pins("dut"), "W": pins("w_u"), "S": pins("s_u")}      # DUT: CC_MX8, IN1..IN8 = D0..D7, never swapped or inverted


_scope = None


def load(name, edits):
    build()
    work = os.path.join(TT, "runs")
    os.makedirs(work, exist_ok=True)
    txt, bit_ = os.path.join(work, name + ".txt"), os.path.join(work, name + ".bit")
    rig.patch(txt, edits)
    subprocess.run(["gmpack", txt, bit_, "--reconfig"], check=True, capture_output=True)
    r = subprocess.run(["openFPGALoader", "-c", "gatemate_pgm", bit_], capture_output=True, text=True)
    assert "DONE" in r.stdout + r.stderr, r.stdout + r.stderr


def capture(tscale=7e-4, tries=3, offset=6.0e-3):
    """Single-shot on the rising edge of UART0_TX (CH1); returns t, CH1, CH2 (trigger at t = 0, window +-4 ms).
    Never abort a run in the middle of a waveform readout (kill the process): the scope keeps the unread data in its output queue and the answers
    of every later session come one position late (symptom: `:ACQ:MDEP?` returns `STOP`). A power cycle of the scope clears that."""
    global _scope
    for _ in range(tries):
        try:
            if _scope is None:
                _scope = rig.Scope()
            _scope.setup_uart(tscale=tscale, edge="POS", level=1.65, src="CHAN1")
            _scope.w(":TIM:MAIN:OFFS %g" % offset)       # the window is 22 divisions wide and centred on the offset: about -1.8 ms .. +13.8 ms around the trigger (an enumeration takes 10.9 ms)
            if _scope.single(10):
                t1, v1 = _scope.waveform("CHAN1")
                t2, v2 = _scope.waveform("CHAN2")
                if len(t1) == len(v1) == len(v2) >= 900000:
                    return t1, v1, v2
                print("capture retry: short read", len(t1), len(v1), len(v2))
        except Exception as ex:
            print("capture retry:", type(ex).__name__, str(ex)[:60])
        if _scope is not None:
            try:
                _scope.s.close()
            except Exception:
                pass
        _scope = None
    return None


def crossings(t, v, lo=1.0, hi=2.0):
    out, state = [], v[0] > hi
    for i in range(1, len(v)):
        if (not state and v[i] > hi) or (state and v[i] < lo):
            j = i
            while j > 0 and ((v[j - 1] > 1.65) if not state else (v[j - 1] < 1.65)):
                j -= 1
            tt = t[j - 1] + (1.65 - v[j - 1]) / (v[j] - v[j - 1]) * (t[j] - t[j - 1]) if j > 0 else t[i]
            out.append((tt, -1 if state else +1))
            state = not state
    return out


def extract(t, v_ref, v_out):
    """-> (F, info); F[s] = level of the pin in state s (x[k] = bit k of s), sampled late in each state. None if the reference is missing."""
    ce = crossings(t, v_ref)
    rises = [c for c, d in ce if d > 0 and abs(c) < 3e-5]
    falls = [c for c, d in ce if d < 0 and c > 0]
    if not rises or not falls:
        return None, {"error": "no reference edges"}
    t0, tick = min(rises, key=abs), (falls[0] - min(rises, key=abs)) / (1 << N)
    oc = [c for c, d in crossings(t, v_out) if t0 <= c <= t0 + (1 << N) * tick]
    info = {"tick_ns": tick * 1e9, "out_edges": len(oc)}
    if len(oc) >= 8:
        sx = sum(math.cos(2 * math.pi * ((c - t0) / tick % 1.0)) for c in oc)
        sy = sum(math.sin(2 * math.pi * ((c - t0) / tick % 1.0)) for c in oc)
        d = (math.atan2(sy, sx) / (2 * math.pi)) % 1.0
        if d > 0.7:
            d -= 1.0                       # the delay of the output is small; keep the phase around 0 so that the sampling window never slips by a tick
    else:
        d = 0.0
    info["delay_ticks"] = d
    dt = t[1] - t[0]
    F, unsure = [], 0
    for s in range(1 << N):
        i0, i1 = max(0, int((t0 + (s + d + 0.4) * tick - t[0]) / dt)), int((t0 + (s + d + 0.8) * tick - t[0]) / dt)
        seg = v_out[i0:i1 + 1]
        m = sum(seg) / len(seg) if seg else 0.0
        F.append(1 if m > 1.65 else 0)
        unsure += 0.9 < m < 2.4
    info["unsure_states"] = unsure
    return F, info


def bit(k):
    return [(s >> k) & 1 for s in range(1 << N)]


def compare(F, G):
    return sum(1 for a, b in zip(F, G) if a != b)


def _calib():
    return json.load(open(CALIB)) if os.path.exists(CALIB) else None


def measure(name, dut_words, w_source=True, extra=None):
    """Patch DUT words (X146Y19; None deletes a word), load, capture. Reader polarity is applied. -> (F, info)"""
    e = dict(READER)
    if w_source:
        e.update(W_SOURCE)
    e.update({(*DUT, k): v for k, v in DUT_BASE.items()})
    e.update({(*DUT, k): v for k, v in dut_words.items()})
    e.update(extra or {})
    load(name, e)
    r = capture()
    if not r:
        return None, {"error": "no capture"}
    F, info = extract(*r[:1], r[1], r[2])
    c = _calib()
    if F is not None and c and c["reader_inverted"]:
        F = [1 - b for b in F]
    return F, info


def calibrate():
    """Reader polarity (DUT as plain bridge, non-inverting) and polarity of IN1..IN8 (identity through the 8:1 mux, SN = 0..7)."""
    mp = mapping()["DUT"]
    os.makedirs(TT, exist_ok=True)
    json.dump({"reader_inverted": False, "pin_inverted": {}}, open(CALIB, "w"))
    F, info = measure("cal_reader", {"C_BR": "1", "C_O1": "01", "C_SN": "000", "C_CX_I": "1"})
    x = bit(mp[1])
    inv = compare(F, x) != 0
    cal = {"reader_inverted": bool(inv), "pin_inverted": {}, "pin_to_x": mp}
    json.dump(cal, open(CALIB, "w"))
    for k in range(8):
        F, info = measure("cal_in%d" % (k + 1), {"C_BR": "1", "C_O1": "01", "C_SN": format(k, "03b"), "C_CX_I": "1"})
        x = bit(mp[k + 1])
        d0, d1 = compare(F, x), compare(F, [1 - b for b in x])
        cal["pin_inverted"][str(k + 1)] = 0 if d0 == 0 else (1 if d1 == 0 else None)
        print("IN%d <- x%d: %s" % (k + 1, mp[k + 1], {0: "direct", 1: "INVERTED", None: "unclear"}[cal["pin_inverted"][str(k + 1)]]))
    json.dump(cal, open(CALIB, "w"), indent=1)
    return cal


def expected(dut_words, out="COUTX"):
    """cpe.v output over all 2^14 states: IN1..IN8 = the signals the pins really see (x index and polarity from mapping()/calibrate()),
    CINX = x[8] (west neighbour, W_SOURCE), all other inputs 0."""
    cal = _calib()
    mp = mapping()["DUT"]
    words = {k: v for k, v in dut_words.items() if v is not None}
    rows = []
    for s in range(1 << N):
        row = {"IN%d" % i: ((s >> mp[i]) & 1) ^ int(cal["pin_inverted"].get(str(i)) or 0) for i in range(1, 9)}
        row["CINX"] = (s >> 8) & 1
        rows.append(row)
    return [int(r[out]) for r in expect(words, rows)]


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        print(build(force=True))
    elif cmd == "calibrate":
        calibrate()
    elif cmd == "run":
        name = sys.argv[2]
        words = {}
        for a in sys.argv[3:]:
            k, v = a.split("=")
            x, y, w = k.split(":")
            words[w] = None if v == "-" else v
        F, info = measure(name, words)
        E = expected(words)
        print(name, info, "| mismatch vs cpe.v (COUTX): %d of %d" % (compare(F, E), len(F)))
