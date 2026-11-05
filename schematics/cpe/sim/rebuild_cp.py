"""One-off rebuild of the CP output generators of ../cpe.kicad_sch (COUTY1, COUTY2, POUTX, POUTY1, POUTY2) in the style of the hand-built COUTX block:
discrete gates, no inverter in front of a multiplexer select (the data inputs are arranged instead), config bits as blue hierarchical labels.
Logic = cpe.v. COMP_OUT is the raw LUT output; the inverter behind the comparator LUT2 now only feeds the net COMP_OUT_N (D2 of the routing multiplexers).
    python rebuild_cp.py ../cpe.kicad_sch"""
import sys as _sys
if "--force" not in _sys.argv:
    _sys.exit("rebuild_cp.py regenerates the whole CP block area and OVERWRITES a hand-arranged layout (it did so once). It was only used for the first draft; "
              "the schematic is maintained by hand now. Run with --force only on a copy.")
_sys.argv = [a for a in _sys.argv if a != "--force"]
import re, sys, uuid

path = sys.argv[1]
raw = open(path, newline='').read()
t = raw.replace('\r\n', '\n')
U = lambda: str(uuid.uuid4())
f = lambda v: ("%.2f" % v).rstrip("0").rstrip(".")
r2 = lambda v: round(v + 1e-9, 2)


# ---------------------------------------------------------------- element writers
def w_wire(a, b):
    return '\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "%s")\n\t)\n' % (f(a[0]), f(a[1]), f(b[0]), f(b[1]), U())


def w_label(name, x, y):
    return '\t(label "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n' % (name, f(x), f(y), U())


def w_hin(name, x, y, blue):
    col = '\t\t\t\t(color 0 0 194 1)\n' if blue else ''
    return '\t(hierarchical_label "%s"\n\t\t(shape input)\n\t\t(at %s %s 180)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n%s\t\t\t)\n\t\t\t(justify right)\n\t\t)\n\t\t(uuid "%s")\n\t)\n' % (name, f(x), f(y), col, U())


def w_hout(name, x, y):
    return '\t(hierarchical_label "%s"\n\t\t(shape output)\n\t\t(at %s %s 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left)\n\t\t)\n\t\t(uuid "%s")\n\t)\n' % (name, f(x), f(y), U())


def w_sym(lib, x, y, npins, value=""):
    def prop(n, v, dy, hide):
        return '\t\t(property "%s" "%s"\n\t\t\t(at %s %s 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n%s\t\t\t)\n\t\t)\n' % (n, v, f(x), f(y + dy), '\t\t\t\t(hide yes)\n' if hide else '')
    s = '\t(symbol\n\t\t(lib_id "peppercorn:%s")\n\t\t(at %s %s 0)\n\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(fields_autoplaced yes)\n\t\t(uuid "%s")\n' % (lib, f(x), f(y), U())
    s += prop("Reference", "U?", -5.08, True) + prop("Value", value, -2.54, not value) + prop("Footprint", "", 0, True) + prop("Datasheet", "", 0, True) + prop("Description", "", 0, True)
    s += ''.join('\t\t(pin ""\n\t\t\t(uuid "%s")\n\t\t)\n' % U() for _ in range(npins))
    return s + '\t)\n'


class Blk:
    def __init__(s):
        s.o = []

    def wire(s, *pts):
        for a, b in zip(pts, pts[1:]):
            if a != b:
                s.o.append(w_wire(a, b))

    def mux4(s, x, y):
        s.o.append(w_sym("MUX4", x, y, 7))
        return dict(D=[(r2(x - 5.08), r2(y + d)) for d in (-3.81, -1.27, 1.27, 3.81)], S0=(x, r2(y - 7.62)), S1=(r2(x + 2.54), r2(y - 5.08)), Y=(r2(x + 5.08), y))

    def mux2(s, x, y):
        s.o.append(w_sym("MUX2", x, y, 4))
        return dict(D0=(r2(x - 5.08), r2(y - 1.27)), D1=(r2(x - 5.08), r2(y + 1.27)), S=(x, r2(y - 5.08)), Y=(r2(x + 5.08), y))

    def mux2b(s, x, y, sel):
        s.o.append(w_sym("MUX2B", x, y, 3, sel))
        return dict(D0=(r2(x - 7.62), r2(y - 1.27)), D1=(r2(x - 7.62), r2(y + 1.27)), Y=(r2(x + 7.62), y))

    def and2(s, x, y):
        s.o.append(w_sym("AND", x, y, 3))
        return dict(I=[(r2(x - 3.81), r2(y - 1.27)), (r2(x - 3.81), r2(y + 1.27))], O=(r2(x + 5.08), y))

    def and3(s, x, y):
        s.o.append(w_sym("AND3", x, y, 4))
        return dict(I=[(r2(x - 3.81), r2(y + d)) for d in (-2.54, 0, 2.54)], O=(r2(x + 5.08), y))

    def or2(s, x, y):
        s.o.append(w_sym("OR", x, y, 3))
        return dict(I=[(r2(x - 5.08), r2(y - 1.27)), (r2(x - 5.08), r2(y + 1.27))], O=(r2(x + 3.81), y))

    def not1(s, x, y):
        s.o.append(w_sym("NOT", x, y, 2))
        return dict(I=(r2(x - 3.81), y), O=(r2(x + 3.81), y))

    def src(s, kind, name, pin, dx):
        """kind lab (local label), cfg (blue hierarchical input), port (hierarchical input); the label sits dx to the left of the pin with a wire in between"""
        a = (r2(pin[0] - dx), pin[1])
        s.wire(a, pin)
        if kind == "lab":
            s.o.append(w_label(name, a[0], a[1]))
        else:
            s.o.append(w_hin(name, a[0], a[1], kind == "cfg"))

    def out_lab(s, name, pin, dx=3.81):
        b = (r2(pin[0] + dx), pin[1])
        s.wire(pin, b)
        s.o.append(w_label(name, b[0], b[1]))

    def out_port(s, name, pin, dx=2.54):
        b = (r2(pin[0] + dx), pin[1])
        s.wire(pin, b)
        s.o.append(w_hout(name, b[0], b[1]))


def routing_mux(B, ym, d, s0name, s1name, y12=None):
    R = B.mux4(349.25, ym)
    for i in range(3):
        B.src("lab", d[i], R["D"][i], 10.16)
    if y12:                                        # C_Y12 multiplexer in front of D3
        m = B.mux2b(328.93, R["D"][3][1], "C_Y12")
        B.src("port", y12[0], m["D0"], 0)
        B.src("port", y12[1], m["D1"], 0)
        B.wire(m["Y"], R["D"][3])
    else:
        B.src("port", d[3], R["D"][3], 10.16)
    B.src("cfg", s0name, R["S0"], 2.54)
    s1 = R["S1"]
    up = (s1[0], r2(s1[1] - 5.08))
    B.wire(s1, up)
    B.src("cfg", s1name, up, 5.08)
    return R


BL = {}

# ---------------------------------------------------------------- COUTY1:  (C_CY1_I | (CADD_S & C_ADDF & ~C_HORIZ)) ? ((C_ADDF & ~C_HORIZ) ? CADD_A : route) : CINY1
B = Blk(); ym = 100.0
R = routing_mux(B, ym, ("OUT2", "OUT1", "COMP_OUT_N", "CINX"), "C_SELY1", "C_SEL_C")
G = B.mux2(368.3, r2(ym + 1.27)); B.wire(R["Y"], G["D0"]); B.src("lab", "CADD_A", G["D1"], 8.89)
F = B.mux2(388.62, ym); B.src("port", "CINY1", F["D0"], 0); B.wire(G["Y"], F["D1"]); B.out_port("COUTY1", F["Y"])
yb = ym - 16.0                                               # inner select  C_ADDF & ~C_HORIZ  (AND2, wired straight to the select)
Nb = B.not1(347.98, r2(yb + 1.27)); B.src("cfg", "C_HORIZ", Nb["I"], 7.62)
Ab = B.and2(356.87, yb); B.src("lab", "C_ADDF", Ab["I"][0], 7.62); B.wire(Nb["O"], Ab["I"][1])
B.wire(Ab["O"], (G["S"][0], yb), G["S"])
yg = ym - 28.0                                               # outer select  C_CY1_I | AND3(CADD_S, C_ADDF, ~C_HORIZ)
Na = B.not1(347.98, yg); B.src("cfg", "C_HORIZ", Na["I"], 7.62)
A3 = B.and3(363.22, r2(yg - 2.54)); B.src("lab", "CADD_S", A3["I"][0], 7.62); B.src("lab", "C_ADDF", A3["I"][1], 7.62); B.wire(Na["O"], A3["I"][2])
O = B.or2(383.54, r2(A3["O"][1] + 1.27)); B.wire(A3["O"], O["I"][0]); B.src("cfg", "C_CY1_I", O["I"][1], 7.62)
B.wire(O["O"], (F["S"][0], O["O"][1]), F["S"])
BL["COUTY1"] = B.o

# ---------------------------------------------------------------- COUTY2:  (C_CY2_I | (C_MULT & COY2_S)) ? (C_MULT ? COY2_a : route) : CINY2,  COY2_S = NAND(mult_sum_hi, mult_sum_lo)
B = Blk(); ym = 144.0
R = routing_mux(B, ym, ("OUT1", "OUT2", "COMP_OUT_N", "CINX"), "C_SELY2", "C_SEL_C")
G = B.mux2(368.3, r2(ym + 1.27)); B.wire(R["Y"], G["D0"]); B.src("lab", "COY2_a", G["D1"], 8.89); B.src("lab", "C_MULT", G["S"], 7.62)
F = B.mux2(388.62, ym); B.src("port", "CINY2", F["D0"], 0); B.wire(G["Y"], F["D1"]); B.out_port("COUTY2", F["Y"])
ya = ym - 20.32
A2 = B.and2(370.84, ya); B.src("lab", "C_MULT", A2["I"][0], 7.62); B.src("lab", "COY2_S", A2["I"][1], 7.62)
O = B.or2(383.54, r2(ya + 3.81)); B.wire(A2["O"], O["I"][0]); B.src("cfg", "C_CY2_I", O["I"][1], 7.62)
B.wire(O["O"], (F["S"][0], O["O"][1]), F["S"])
BL["COUTY2"] = B.o

# ---------------------------------------------------------------- POUTX (same structure as the hand-built COUTX)
B = Blk(); ym = 188.0
R = routing_mux(B, ym, ("OUT2", "OUT1", "COMP_OUT_N", None), "C_SELX", "C_SEL_P", y12=("PINY1", "PINY2"))
F = B.mux4(388.62, r2(ym - 3.81))
yF = F["Y"][1]
B.src("port", "PINX", F["D"][0], 0)
B.src("lab", "MULTO1", F["D"][1], 7.62)
Nc = B.not1(372.11, F["D"][2][1]); B.src("cfg", "C_COMP_I", Nc["I"], 7.62); B.wire(Nc["O"], F["D"][2])
B.wire(R["Y"], F["D"][3]); B.out_port("POUTX", F["Y"], 5.08)
O1 = B.or2(384.81, r2(yF - 20.32))                     # S1 = C_PX_I | (COMP_OUT & C_COMP & C_HORIZ)
O0 = B.or2(384.81, r2(yF - 12.7))                      # S0 = C_MULT | C_PX_I
Ax = B.and3(361.95, r2(yF - 21.59))
B.src("lab", "COMP_OUT", Ax["I"][0], 7.62); B.src("cfg", "C_COMP", Ax["I"][1], 7.62); B.src("cfg", "C_HORIZ", Ax["I"][2], 7.62)
B.wire(Ax["O"], O1["I"][0])
B.wire(O1["I"][1], O0["I"][0])                         # C_PX_I net: vertical wire between the two OR gates, label in the middle
B.o.append(w_hin("C_PX_I", O1["I"][1][0], r2((O1["I"][1][1] + O0["I"][0][1]) / 2), True))
B.src("lab", "C_MULT", O0["I"][1], 7.62)
B.wire(O1["O"], (F["S1"][0], O1["O"][1]), F["S1"])
B.wire(O0["O"], (F["S0"][0], O0["O"][1]), F["S0"])
BL["POUTX"] = B.o

# ---------------------------------------------------------------- POUTY1 (by parallel with COUTY1 / POUTX):  (C_PY1_I | AND3(COMP_OUT, C_COMP, ~C_HORIZ)) ? ((C_COMP & ~C_HORIZ) ? ~C_COMP_I : route) : PINY1
B = Blk(); ym = 232.0
R = routing_mux(B, ym, ("OUT1", "OUT2", "COMP_OUT_N", "PINX"), "C_SELY1", "C_SEL_P")
G = B.mux2(368.3, r2(ym + 1.27)); B.wire(R["Y"], G["D0"])
Nc = B.not1(356.0, r2(ym + 6.35)); B.src("cfg", "C_COMP_I", Nc["I"], 7.62); B.wire(Nc["O"], (361.0, Nc["O"][1]), (361.0, G["D1"][1]), G["D1"])
F = B.mux2(388.62, ym); B.src("port", "PINY1", F["D0"], 0); B.wire(G["Y"], F["D1"]); B.out_port("POUTY1", F["Y"])
yb = ym - 16.0                                               # inner select  C_COMP & ~C_HORIZ
Nb = B.not1(347.98, r2(yb + 1.27)); B.src("cfg", "C_HORIZ", Nb["I"], 7.62)
Ab = B.and2(356.87, yb); B.src("cfg", "C_COMP", Ab["I"][0], 7.62); B.wire(Nb["O"], Ab["I"][1])
B.wire(Ab["O"], (G["S"][0], yb), G["S"])
yg = ym - 28.0                                               # outer select  C_PY1_I | AND3(COMP_OUT, C_COMP, ~C_HORIZ)
Na = B.not1(347.98, yg); B.src("cfg", "C_HORIZ", Na["I"], 7.62)
A3 = B.and3(363.22, r2(yg - 2.54)); B.src("lab", "COMP_OUT", A3["I"][0], 7.62); B.src("cfg", "C_COMP", A3["I"][1], 7.62); B.wire(Na["O"], A3["I"][2])
O = B.or2(383.54, r2(A3["O"][1] + 1.27)); B.wire(A3["O"], O["I"][0]); B.src("cfg", "C_PY1_I", O["I"][1], 7.62)
B.wire(O["O"], (F["S"][0], O["O"][1]), F["S"])
BL["POUTY1"] = B.o

# ---------------------------------------------------------------- POUTY2:  (C_PY2_I & ~C_MULT) ? route : PINY2
B = Blk(); ym = 276.0
R = routing_mux(B, ym, ("OUT2", "OUT1", "COMP_OUT_N", "PINX"), "C_SELY2", "C_SEL_P")
F = B.mux2(388.62, r2(ym - 1.27)); B.src("port", "PINY2", F["D0"], 0); B.wire(R["Y"], F["D1"]); B.out_port("POUTY2", F["Y"])
Nm = B.not1(369.57, r2(ym - 12.73)); B.src("lab", "C_MULT", Nm["I"], 7.62)
A = B.and2(383.54, r2(ym - 14.0)); B.src("cfg", "C_PY2_I", A["I"][0], 7.62); B.wire(Nm["O"], A["I"][1])
B.wire(A["O"], F["S"])
BL["POUTY2"] = B.o


# ---------------------------------------------------------------- remove the old blocks
def top_items(text):
    out = []
    i = 0
    while True:
        j = text.find('\n\t(', i)
        if j < 0:
            break
        j += 1
        d = 0
        k = j
        while True:
            c = text[k]
            if c == '"':
                k += 1
                while text[k] != '"':
                    k += 2 if text[k] == '\\' else 1
            elif c == '(':
                d += 1
            elif c == ')':
                d -= 1
                if d == 0:
                    break
            k += 1
        out.append((j, k + 1))
        i = k + 1
    return out


X0, X1, Y0, Y1 = 318.0, 398.0, 66.5, 222.5
inreg = lambda x, y: X0 <= x <= X1 and Y0 <= y <= Y1
drop = []
for a, b in top_items(t):
    blk = t[a:b]
    head = blk.split('\n', 1)[0].strip().split(' ')[0]
    if head == '(wire':
        xs = [(float(p), float(q)) for p, q in re.findall(r'\(xy ([\d.-]+) ([\d.-]+)\)', blk)]
        if all(inreg(p, q) for p, q in xs):
            drop.append((a, b))
    elif head in ('(symbol', '(label', '(hierarchical_label', '(text', '(junction'):
        m = re.search(r'\n\t\t\(at ([\d.-]+) ([\d.-]+)', blk) or re.search(r'\(at ([\d.-]+) ([\d.-]+)', blk)
        if m and inreg(float(m.group(1)), float(m.group(2))):
            drop.append((a, b))
print("removing", len(drop), "old elements")
for a, b in sorted(drop, reverse=True):
    t = t[:a - 1] + t[b:]


# ---------------------------------------------------------------- COY2_S: the OR of the two multiplier sums becomes a NAND (hardware, wp_y2): same output and input pins when moved 1.27 to the left
m = re.search(r'\t\(symbol\n\t\t\(lib_name "[^"]*"\)\n\t\t\(lib_id "peppercorn:OR"\)\n\t\t\(at 132.08 161.29 0\)', t)
assert m, "COY2_S OR gate not found"
e = t.index('\n\t)\n', m.start()) + 4
blk = t[m.start():e]
blk = re.sub(r'\t\t\(lib_name "[^"]*"\)\n', '', blk).replace('(lib_id "peppercorn:OR")', '(lib_id "peppercorn:NAND")').replace('(at 132.08 161.29 0)', '(at 130.81 161.29 0)')
t = t[:m.start()] + blk + t[e:]

# ---------------------------------------------------------------- COMP_OUT raw + inverted net; COUTX routing multiplexer D2
def relabel(text, old, new, x, y):
    pat = r'(\t\(label ")%s("\n\t\t\(at %s %s \d+\))' % (re.escape(old), re.escape(x), re.escape(y))
    assert len(re.findall(pat, text)) == 1, (old, x, y)
    return re.sub(pat, r'\g<1>%s\g<2>' % new, text)


t = relabel(t, "COMP_OUT", "COMP_OUT_N", "146.05", "105.41")                 # behind the inverter of the comparator LUT2
t = relabel(t, "COMP_OUT", "COMP_OUT_N", "334.01", "59.69")                  # COUTX routing multiplexer D2
a = t.index('\t(wire\n\t\t(pts\n\t\t\t(xy 134.62 105.41) (xy 137.16 105.41)')
t = t[:a] + w_label("COMP_OUT", 135.89, 105.41) + t[a:]
# ---------------------------------------------------------------- frame of the CP generator box
fr = '(end 393.7 229.87)'
assert t.count(fr) == 1
t = t.replace(fr, '(end 393.7 %s)' % f(276.0 + 14.0))
# ---------------------------------------------------------------- insert the new blocks
body = ''.join(''.join(v) for v in BL.values())
k = t.rstrip().rfind(')')
t = t[:k].rstrip('\n') + '\n' + body + t[k:]
open(path, 'w', newline='').write(t.replace('\n', '\r\n') if '\r\n' in raw else t)
print("rebuilt", path)
