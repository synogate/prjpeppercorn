"""Minimal KiCad (v7-v10) schematic reader: symbols, pins, wires, labels -> connectivity."""
import re, sys

def parse(text):
    tok = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+')
    stack = [[]]
    for m in tok.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append([])
        elif t == ')':
            l = stack.pop()
            stack[-1].append(l)
        elif t[0] == '"':
            stack[-1].append(('s', t[1:-1].replace('\"', '"')))
        else:
            stack[-1].append(t)
    return stack[0][0]

def s(x):  # atom or string -> python str
    return x[1] if isinstance(x, tuple) else x

def find(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]

def first(node, name):
    r = find(node, name)
    return r[0] if r else None

class Pin:
    def __init__(self, name, number, etype, x, y, angle):
        self.name, self.number, self.etype, self.x, self.y, self.angle = (name or number), number, etype, x, y, angle

def lib_symbols(root):
    libs = {}
    ls = first(root, 'lib_symbols')
    for sym in find(ls, 'symbol'):
        name = s(sym[1])
        props = {s(p[1]): s(p[2]) for p in find(sym, 'property')}
        pins = {}  # unit -> list
        for sub in find(sym, 'symbol'):
            m = re.match(r'.*_(\d+)_(\d+)$', s(sub[1]))
            unit, style = int(m.group(1)), int(m.group(2))
            for p in find(sub, 'pin'):
                at = first(p, 'at')
                nm = first(p, 'name'); nu = first(p, 'number')
                pins.setdefault((unit, style), []).append(
                    Pin(s(nm[1]), s(nu[1]), s(p[1]), float(at[1]), float(at[2]), float(at[3])))
        # direct pins (rare)
        for p in find(sym, 'pin'):
            at = first(p, 'at'); nm = first(p, 'name'); nu = first(p, 'number')
            pins.setdefault((0, 0), []).append(Pin(s(nm[1]), s(nu[1]), s(p[1]), float(at[1]), float(at[2]), float(at[3])))
        libs[name] = {'props': props, 'pins': pins}
    return libs

def xform(px, py, ang, mirror):
    # symbol coords are y-up; apply mirror then rotation (ccw), then y flip to sheet coords
    if mirror == 'x':
        py = -py
    elif mirror == 'y':
        px = -px
    import math
    a = math.radians(ang)
    rx = px * math.cos(a) - py * math.sin(a)
    ry = px * math.sin(a) + py * math.cos(a)
    return rx, -ry

def round2(v):
    return round(v * 100) / 100.0

class UF:
    def __init__(self): self.p = {}
    def f(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]; a = self.p[a]
        return a
    def u(self, a, b): self.p[self.f(a)] = self.f(b)

def load(path):
    root = parse(open(path, encoding='utf8').read())
    libs = lib_symbols(root)
    uf = UF()
    wires = []
    for w in find(root, 'wire'):
        pts = first(w, 'pts'); xy = find(pts, 'xy')
        a = (round2(float(xy[0][1])), round2(float(xy[0][2])))
        b = (round2(float(xy[1][1])), round2(float(xy[1][2])))
        wires.append((a, b)); uf.u(a, b)
    juncs = [(round2(float(first(j, 'at')[1])), round2(float(first(j, 'at')[2]))) for j in find(root, 'junction')]
    labels = []
    for kind in ('label', 'global_label', 'hierarchical_label'):
        for l in find(root, kind):
            at = first(l, 'at')
            labels.append((kind, s(l[1]), (round2(float(at[1])), round2(float(at[2])))))
    insts = []
    for sy in find(root, 'symbol'):
        lib = first(sy, 'lib_id'); at = first(sy, 'at')
        if not lib: continue
        mir = first(sy, 'mirror'); un = first(sy, 'unit'); bs = first(sy, 'body_style') or first(sy, 'convert')
        props = {s(p[1]): s(p[2]) for p in find(sy, 'property')}
        insts.append(dict(lib=s(lib[1]), x=float(at[1]), y=float(at[2]), ang=float(at[3]) if len(at) > 3 else 0.0,
                          mirror=mir[1] if mir else None, unit=int(un[1]) if un else 1,
                          style=int(bs[1]) if bs else 1, props=props,
                          uuid=s(first(sy, 'uuid')[1]) if first(sy, 'uuid') else ''))
    return root, libs, uf, wires, juncs, labels, insts

def on_seg(p, a, b):
    if a[0] == b[0]:
        return abs(p[0] - a[0]) < 0.011 and min(a[1], b[1]) - 0.011 <= p[1] <= max(a[1], b[1]) + 0.011
    if a[1] == b[1]:
        return abs(p[1] - a[1]) < 0.011 and min(a[0], b[0]) - 0.011 <= p[0] <= max(a[0], b[0]) + 0.011
    return False

def connect(root, libs, uf, wires, juncs, labels, insts):
    """returns pins: list of (inst_index, Pin, abs_point); nets via uf"""
    pins = []
    for i, ins in enumerate(insts):
        lib = libs.get(ins['lib'])
        if lib is None: continue
        lp = lib['pins']
        sel = []
        for (u, st), pl in lp.items():
            if u in (0, ins['unit']) and st in (0, 1, ins['style']):
                sel += pl
        for p in sel:
            dx, dy = xform(p.x, p.y, ins['ang'], ins['mirror'])
            pt = (round2(ins['x'] + dx), round2(ins['y'] + dy))
            pins.append((i, p, pt))
    pts = set()
    for _, _, pt in pins: pts.add(pt)
    for _, _, pt in labels: pts.add(pt)
    pts |= set(juncs)
    # pins/labels/junctions connect to any wire passing through (or ending at) their point
    for pt in pts:
        uf.f(pt)
        for a, b in wires:
            if on_seg(pt, a, b):
                uf.u(pt, a)
    return pins
