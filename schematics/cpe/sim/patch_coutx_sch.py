"""One-off patch of ../cpe.kicad_sch after the COUTX mapping (hw_measurements.md findings 20-24):
 1. COUTX select S1: AO21 -> OA21 + NOT after it (same structure as COUTY1), the NOT on C_CX_I goes away
 2. COMP_OUT inverter directly behind the comparator LUT2 (L30)
 3. generate term of the ADDF adder = l00 | l01 | l02: second OR (placed in free space, connected by labels G01 / G_ADDF)
Run once:  python patch_coutx_sch.py ../cpe.kicad_sch"""
import re, sys, uuid

path = sys.argv[1]
raw = open(path, newline='').read()
t = raw.replace('\r\n', '\n')
U = lambda: str(uuid.uuid4())


def wire(a, b):
    return '\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n\t\t(uuid "%s")\n\t)\n' % (a[0], a[1], b[0], b[1], U())


def label(name, x, y, ang, just):
    return '\t(label "%s"\n\t\t(at %s %s %d)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify %s)\n\t\t)\n\t\t(uuid "%s")\n\t)\n' % (name, x, y, ang, just, U())


def gate(lib, x, y, ang, npins):
    x, y = float(x), float(y)
    fmt = lambda v: ("%.2f" % v).rstrip("0").rstrip(".")
    prop = lambda name, val, dy, hide: '\t\t(property "%s" "%s"\n\t\t\t(at %s %s 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n%s\t\t\t)\n\t\t)\n' % (name, val, fmt(x), fmt(y + dy), '\t\t\t\t(hide yes)\n' if hide else '')
    s = '\t(symbol\n\t\t(lib_id "peppercorn:%s")\n\t\t(at %s %s %d)\n\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(fields_autoplaced yes)\n\t\t(uuid "%s")\n' % (lib, fmt(x), fmt(y), ang, U())
    s += prop("Reference", "U?", -5.08, True) + prop("Value", "~", -2.54, False) + prop("Footprint", "", 0, True) + prop("Datasheet", "", 0, True) + prop("Description", "", 0, True)
    s += ''.join('\t\t(pin ""\n\t\t\t(uuid "%s")\n\t\t)\n' % U() for _ in range(npins))
    return s + '\t)\n'


def cut(text, pat, what):
    m = re.search(pat, text, re.S)
    assert m, "not found: " + what
    assert len(re.findall(pat, text, re.S)) == 1, "ambiguous: " + what
    return text[:m.start()], text[m.end():]


def symbol_block(text, lib, x, y, ang):
    """span of the top-level (symbol ...) instance with this lib_id and position"""
    for m in re.finditer(r'\t\(symbol\n', text):
        end = text.index('\n\t)\n', m.start()) + 4
        blk = text[m.start():end]
        if re.search(r'\(lib_id "peppercorn:%s"\)' % lib, blk) and ('(at %s %s %s)' % (x, y, ang)) in blk.split('(unit')[0]:
            return m.start(), end
    raise AssertionError("symbol not found %s %s %s" % (lib, x, y))


def wire_span(text, a, b):
    pat = r'\t\(wire\n\t\t\(pts\n\t\t\t\(xy %s %s\) \(xy %s %s\)\n.*?\n\t\)\n' % (a[0], a[1], b[0], b[1])
    m = list(re.finditer(pat, text, re.S))
    assert len(m) == 1, "wire %s %s: %d" % (a, b, len(m))
    return m[0].start(), m[0].end()


# ---- 1. COUTX select S1 --------------------------------------------------------------------------------------------------------------------------------------------------------
s0, e0 = symbol_block(t, "AO21", "379.73", "57.15", "0")
blk = t[s0:e0]
blk = re.sub(r'\t\t\(lib_name "[^"]*"\)\n', '', blk).replace('(lib_id "peppercorn:AO21")', '(lib_id "peppercorn:OA21")')
t = t[:s0] + blk + t[e0:]
s1, e1 = symbol_block(t, "NOT", "355.6", "60.96", "0")                                   # NOT(C_CX_I): the OA21 takes C_CX_I directly
t = t[:s1] + wire(("351.79", "60.96"), ("359.41", "60.96")) + t[e1:]
a, b = wire_span(t, ("388.62", "59.69"), ("388.62", "74.93"))                              # S1 line: OA21 output -> NOT -> mux
t = t[:a] + wire(("388.62", "59.69"), ("388.62", "63.5")) + gate("NOT", "388.62", "67.31", 270, 2) + wire(("388.62", "71.12"), ("388.62", "74.93")) + t[b:]

# ---- 2. COMP_OUT inverter behind the LUT2 ---------------------------------------------------------------------------------------------------------------------------------------
a, b = wire_span(t, ("134.62", "105.41"), ("149.86", "105.41"))
t = t[:a] + wire(("134.62", "105.41"), ("137.16", "105.41")) + gate("NOT", "140.97", "105.41", 0, 2) + wire(("144.78", "105.41"), ("149.86", "105.41")) + t[b:]

# ---- 3. generate of ADDF: l00 | l01 | l02 ------------------------------------------------------------------------------------------------------------------------------------------
a, b = wire_span(t, ("67.31", "114.3"), ("90.17", "114.3"))                               # OR(L01, L00) output -> MUX2: cut, join by labels
new = wire(("87.63", "114.3"), ("90.17", "114.3")) + label("G_ADDF", "87.63", "114.3", 180, "right bottom") + label("G01", "67.31", "114.3", 0, "left bottom")
new += gate("OR", "125.73", "120.65", 0, 3)
new += wire(("116.84", "119.38"), ("120.65", "119.38")) + label("G01", "116.84", "119.38", 180, "right bottom")
new += wire(("116.84", "121.92"), ("120.65", "121.92")) + label("L02", "116.84", "121.92", 180, "right bottom")
new += wire(("129.54", "120.65"), ("133.35", "120.65")) + label("G_ADDF", "133.35", "120.65", 0, "left bottom")
t = t[:a] + new + t[b:]

open(path, 'w', newline='').write(t.replace('\n', '\r\n') if '\r\n' in raw else t)
print("patched", path)
