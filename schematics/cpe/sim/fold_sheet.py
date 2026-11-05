"""Constant-fold cpe.kicad_sch for a fixed C_FUNCTION and write a reduced KiCad sheet.

Usage: python fold_sheet.py <C_FUNCTION 0..7> ../cpe.kicad_sch ../cpe_f6.kicad_sch

* C_MULT, C_MX4, C_EN_CIN, C_ADDF, C_ADDF2, C_ADDCIN become constants (decoded from C_FUNCTION as in the schematic).
* Gates with a constant output are removed; gates that only pass one input on (AND with 1, OR with 0, XOR with 0,
  MUX2/MUX4 with constant select, ...) are removed and their input net is wired to their output net.
* Gates that keep fewer inputs are replaced by the smaller symbol (AO21 -> AND, XOR3 -> XOR, AND3 -> AND, NAND3 -> NAND).
* Everything that no longer reaches a port (hierarchical label) is removed, together with the wires, labels and
  C_* texts that belonged to it.  Free configuration bits are left alone.
The result keeps the original block text, so it opens like the source sheet.
"""
import sys, re, math, uuid, collections
sys.path.insert(0, '.')
import kisch, netlist

F = int(sys.argv[1])
SRC, DST = sys.argv[2], sys.argv[3]
DEC = {'C_MULT': F == 3, 'C_MX4': F == 4, 'C_EN_CIN': F == 5,
       'C_ADDF': F in (1, 2, 3, 6), 'C_ADDF2': F in (2, 3), 'C_ADDCIN': F in (1, 2, 3, 7)}
r2 = kisch.round2


def P(x, y):
    return (r2(x), r2(y))


# ---------------------------------------------------------------- raw file: top level blocks
text = open(SRC, encoding='utf8').read()


def top_blocks(t):
    blocks, depth, k, start, n = [], 0, 0, None, len(t)
    while k < n:
        ch = t[k]
        if ch == '"':
            k += 1
            while t[k] != '"':
                if t[k] == '\\':
                    k += 1
                k += 1
        elif ch == '(':
            depth += 1
            if depth == 2:
                start = k
        elif ch == ')':
            if depth == 2:
                blocks.append((start, k + 1))
            depth -= 1
        k += 1
    return blocks


spans = top_blocks(text)
header = text[:spans[0][0]]
footer = text[spans[-1][1]:]
blocks = []
for a, b in spans:
    s = text[a:b]
    kind = re.match(r'\((\w+)', s).group(1)
    blocks.append(dict(kind=kind, text=s, sx=None))
for blk in blocks:
    blk['sx'] = kisch.parse(blk['text']) if blk['kind'] in ('wire', 'junction', 'label', 'global_label', 'hierarchical_label',
                                                           'text', 'no_connect', 'symbol', 'sheet', 'rectangle') else None


def strip_child(s, name):
    """remove the depth-1 child '(name ...)' from block text s"""
    out, depth, k, n = [], 0, 0, len(s)
    last = 0
    while k < n:
        ch = s[k]
        if ch == '"':
            k += 1
            while s[k] != '"':
                if s[k] == '\\':
                    k += 1
                k += 1
        elif ch == '(':
            depth += 1
            if depth == 2 and re.match(r'\(' + name + r'\b', s[k:k + len(name) + 2]):
                st = k
                d2 = 0
                while True:
                    c2 = s[k]
                    if c2 == '"':
                        k += 1
                        while s[k] != '"':
                            if s[k] == '\\':
                                k += 1
                            k += 1
                    elif c2 == '(':
                        d2 += 1
                    elif c2 == ')':
                        d2 -= 1
                        if d2 == 0:
                            break
                    k += 1
                # also eat the preceding whitespace/newline
                a = st
                while a > 0 and s[a - 1] in ' \t':
                    a -= 1
                if a > 0 and s[a - 1] == '\n':
                    a -= 1
                out.append(s[last:a])
                last = k + 1
                depth -= 1
        elif ch == ')':
            depth -= 1
        k += 1
    out.append(s[last:])
    return ''.join(out)


# ---------------------------------------------------------------- connectivity (as gen.py)
root, libs, uf, insts, pins, names = netlist.build(SRC)
for lname in ('OR', 'XOR', 'XNOR', 'NOR', 'AND', 'NAND', 'XOR3', 'AND3', 'NAND3', 'NOT'):
    L = libs.get('peppercorn:' + lname)
    if L:
        for k, pl in L['pins'].items():
            mx = max(p.x for p in pl)
            for p in pl:
                p.etype = 'output' if p.x == mx else 'input'
ip = collections.defaultdict(list)           # inst -> [(pin, net, point)]
for i, p, pt in pins:
    ip[i].append((p, uf.f(pt), pt))
inst_blocks = [b for b in blocks if b['kind'] == 'symbol' and kisch.first(b['sx'], 'lib_id')]
assert len(inst_blocks) == len(insts), (len(inst_blocks), len(insts))


def isout(p):
    return p.etype.startswith('out')


def libname(i):
    return insts[i]['lib'].split(':')[1]


netpin_count = collections.Counter(n for i in ip for p, n, pt in ip[i])
legend = set()
for i in ip:
    if libname(i) != 'C_FUNCTION' and all(netpin_count[n] == 1 and not names.get(n) for p, n, pt in ip[i]):
        legend.add(i)

# ---------------------------------------------------------------- constant propagation
val, alias = {}, {}
for k, v in DEC.items():
    for n, nms in names.items():
        if k in nms:
            val[n] = int(v)


def get(n):
    inv = 0
    while n in alias:
        n, i = alias[n]
        inv ^= i
    if n in val:
        return ('c', val[n] ^ inv)
    return ('n', n, inv)


def cv(v):
    return v[1] if v[0] == 'c' else None


plan = {}   # inst -> ('const', v) | ('alias', via_pt, target_value) | ('reduce', new_lib, kept_input_pts)

unreach = {}   # MUX4 inst -> data indices that can never be selected (found by reachability of the selects)
drivers0 = collections.defaultdict(list)
for i in ip:
    for p, n, pt in ip[i]:
        if isout(p):
            drivers0[n].append(i)
EVAL_LIBS = ('AND', 'AND3', 'NAND', 'NAND3', 'OR', 'NOR', 'XOR', 'XOR3', 'XNOR', 'NOT', 'AO21', 'OA21',
             'MUX2', 'MUX2 (conceptual)', 'MUX4', 'MUX4 (conceptual)', 'MUX4 (conceptual) (upside down)')
MAX_VARS = 18


def support(n, visiting, sup, cache):
    g = get(n)
    if g[0] == 'c':
        return
    m = g[1]
    if m in cache:
        sup |= cache[m]
        return
    drv = drivers0.get(m, [])
    if len(drv) != 1 or libname(drv[0]) not in EVAL_LIBS or m in visiting:
        s_ = {m}
    else:
        visiting.add(m)
        s_ = set()
        for p, nn, pt in ip[drv[0]]:
            if not isout(p):
                support(nn, visiting, s_, cache)
        visiting.discard(m)
    cache[m] = s_
    sup |= s_


def ev(n, asg, memo, V):
    g = get(n)
    if g[0] == 'c':
        return g[1]
    m = g[1]
    if m in V:
        return asg[m]
    if m in memo:
        return memo[m]
    i = drivers0[m][0]
    lib = libname(i)
    inp = [(p, nn) for p, nn, pt in ip[i] if not isout(p)]
    if lib in ('AND', 'AND3', 'NAND', 'NAND3'):
        r_ = int(all(ev(nn, asg, memo, V) for p, nn in inp))
        r_ ^= lib.startswith('NAND')
    elif lib in ('OR', 'NOR'):
        r_ = int(any(ev(nn, asg, memo, V) for p, nn in inp))
        r_ ^= lib == 'NOR'
    elif lib in ('XOR', 'XOR3', 'XNOR'):
        r_ = 0
        for p, nn in inp:
            r_ ^= ev(nn, asg, memo, V)
        r_ ^= lib == 'XNOR'
    elif lib == 'NOT':
        r_ = 1 - ev(inp[0][1], asg, memo, V)
    elif lib in ('AO21', 'OA21'):
        a = [ev(nn, asg, memo, V) for p, nn in inp if p.x < -1]
        bb = [ev(nn, asg, memo, V) for p, nn in inp if p.x == 0.0][0]
        r_ = ((a[0] | a[1]) & bb) if lib == 'AO21' else ((a[0] & a[1]) | bb)
    elif lib.startswith('MUX2'):
        d = {p.name: nn for p, nn in inp}
        r_ = ev(d['D1' if ev(d['S'], asg, memo, V) else 'D0'], asg, memo, V)
    else:
        d = {p.name: nn for p, nn in inp}
        k = ev(d['S1'], asg, memo, V) * 2 + ev(d['S0'], asg, memo, V)
        r_ = ev(d['D%d' % k], asg, memo, V)
    memo[m] = int(r_)
    return int(r_)


def reach_pass():
    """Find selects that are constant in every reachable state, or mux4 data inputs that can never be selected."""
    found = False
    cache = {}
    for i in sorted(ip):
        lib = libname(i)
        if i in plan or i in legend or not (lib.startswith('MUX2') or lib.startswith('MUX4')) or lib == 'MUX2B':
            continue
        sels = [nn for p, nn, pt in ip[i] if p.name in ('S', 'S0', 'S1')]
        if not sels or any(get(nn)[0] == 'c' for nn in sels):
            continue
        sup = set()
        for nn in sels:
            support(nn, set(), sup, cache)
        if len(sup) > MAX_VARS:
            continue
        V = sorted(sup)
        combos = set()
        for bits in range(1 << len(V)):
            asg = {v: (bits >> k) & 1 for k, v in enumerate(V)}
            memo = {}
            combos.add(tuple(ev(nn, asg, memo, set(V)) for nn in sels))
        if lib.startswith('MUX2'):
            vs = {c[0] for c in combos}
            if len(vs) == 1:
                val[get(sels[0])[1]] = vs.pop()
                found = True
        else:
            names_ = [p.name for p, nn, pt in ip[i] if p.name in ('S', 'S0', 'S1')]
            ix = {nm_: k for k, nm_ in enumerate(names_)}
            for nm_, nn in zip(names_, sels):
                vs = {c[ix[nm_]] for c in combos}
                if len(vs) == 1:
                    val[get(nn)[1]] = vs.pop()
                    found = True
            if not found:
                un = {k for k in range(4) if not any(c[ix['S1']] * 2 + c[ix['S0']] == k for c in combos)}
                if un and unreach.get(i) != un:
                    unreach[i] = un
    return found


outer = True
while outer:
    outer = False
    changed = True
    while changed:
        changed = False
        for i in sorted(ip):
            if i in plan or i in legend:
                continue
            lib = libname(i)
            outs = [(p, n, pt) for p, n, pt in ip[i] if isout(p)]
            inp = [(p, n, pt) for p, n, pt in ip[i] if not isout(p)]
            if not outs or lib in ('CONFIG', 'C_FUNCTION'):
                continue
            r = None
            if lib in ('AND', 'AND3', 'NAND', 'NAND3', 'OR', 'NOR'):
                isand = lib.startswith('AND') or lib.startswith('NAND')
                neg = 1 if lib.startswith('N') else 0
                dom = 0 if isand else 1
                vs = [(get(n), pt) for p, n, pt in inp]
                if any(cv(v) == dom for v, pt in vs):
                    r = ('const', dom ^ neg)
                else:
                    rest = [(v, pt) for v, pt in vs if v[0] != 'c']
                    if not rest:
                        r = ('const', (1 - dom) ^ neg)
                    elif len(rest) < len(vs):
                        if len(rest) == 1 and not neg:
                            r = ('alias', rest[0][1], rest[0][0])
                        elif len(rest) == 1:
                            raise SystemExit('inverting reduction not implemented: %s @%s' % (lib, insts[i]))
                        elif lib in ('AND3', 'NAND3') and len(rest) == 2:
                            r = ('reduce', 'AND' if lib == 'AND3' else 'NAND', [pt for v, pt in rest])
                        else:
                            raise SystemExit('reduction of %s not implemented' % lib)
            elif lib in ('XOR', 'XOR3', 'XNOR'):
                neg = 1 if lib == 'XNOR' else 0
                vs = [(get(n), pt) for p, n, pt in inp]
                c = sum(v[1] for v, pt in vs if v[0] == 'c') & 1
                rest = [(v, pt) for v, pt in vs if v[0] != 'c']
                if not rest:
                    r = ('const', c ^ neg)
                elif len(rest) < len(vs):
                    if len(rest) == 1:
                        if c ^ neg:
                            raise SystemExit('XOR with 1 -> inverter not implemented')
                        r = ('alias', rest[0][1], rest[0][0])
                    elif lib == 'XOR3' and len(rest) == 2 and not (c ^ neg):
                        r = ('reduce', 'XOR', [pt for v, pt in rest])
                    else:
                        raise SystemExit('reduction of %s not implemented' % lib)
            elif lib == 'NOT':
                v = get(inp[0][1])
                if v[0] == 'c':
                    r = ('const', 1 - v[1])
            elif lib in ('AO21', 'OA21'):
                a = [(get(n), pt) for p, n, pt in inp if p.x < -1]
                b = [(get(n), pt) for p, n, pt in inp if p.x == 0.0]
                ao = lib == 'AO21'
                bv = cv(b[0][0])
                av = [cv(v) for v, pt in a]
                dom_b, dom_a = (0, 1) if ao else (1, 0)      # AO21=(a0|a1)&b, OA21=(a0&a1)|b
                if bv == dom_b or all(x == 1 - dom_a for x in av):
                    r = ('const', dom_b)
                elif any(x == dom_a for x in av):            # pair is constant, output follows b
                    r = ('const', bv) if bv is not None else ('alias', b[0][1], b[0][0])
                elif bv is not None:
                    raise SystemExit('pair-only reduction of %s not implemented' % lib)
                elif any(x == 1 - dom_a for x in av):        # one input of the pair is neutral -> 2-input gate
                    rest = [pt for (v, pt) in a if v[0] != 'c']
                    r = ('reduce', 'AND' if ao else 'OR', [rest[0], b[0][1]])
            elif lib in ('MUX2', 'MUX2 (conceptual)'):
                d = {p.name: (get(n), pt) for p, n, pt in inp}
                s = d['S'][0]
                if s[0] == 'c':
                    sel = d['D1' if s[1] else 'D0']
                    r = ('const', sel[0][1]) if sel[0][0] == 'c' else ('alias', sel[1], sel[0])
            elif lib.startswith('MUX4'):
                d = {p.name: (get(n), pt) for p, n, pt in inp}
                s0, s1 = d['S0'][0], d['S1'][0]
                if s0[0] == 'c' and s1[0] == 'c':
                    sel = d['D%d' % (s1[1] * 2 + s0[1])]
                    r = ('const', sel[0][1]) if sel[0][0] == 'c' else ('alias', sel[1], sel[0])
                elif s0[0] == 'c':
                    lo, hi = d['D%d' % s0[1]], d['D%d' % (2 + s0[1])]
                    r = ('reduce', 'MUX2', {'S': d['S1'][1], 'D0': lo[1], 'D1': hi[1]})
                elif s1[0] == 'c':
                    lo, hi = d['D%d' % (2 * s1[1])], d['D%d' % (2 * s1[1] + 1)]
                    r = ('reduce', 'MUX2', {'S': d['S0'][1], 'D0': lo[1], 'D1': hi[1]})
            if r is None:
                continue
            plan[i] = r
            changed = True
            for p, n, pt in outs:
                if r[0] == 'const':
                    val[n] = r[1]
                elif r[0] == 'alias':
                    tgt = r[2]
                    if tgt[2]:
                        raise SystemExit('inverted alias not implemented')
                    alias[n] = (tgt[1], 0)
    outer = reach_pass()

# ---------------------------------------------------------------- liveness (cone of influence of the ports)
hier = []
for blk in blocks:
    if blk['kind'] == 'hierarchical_label':
        at = kisch.first(blk['sx'], 'at')
        hier.append(uf.f(P(float(at[1]), float(at[2]))))
drivers = collections.defaultdict(list)
for i in ip:
    for p, n, pt in ip[i]:
        if isout(p):
            drivers[n].append(i)
needed, live, work = set(), set(), []


def need(n):
    g = get(n)
    if g[0] == 'c' or g[1] in needed:
        return
    needed.add(g[1])
    work.append(g[1])


for n in hier:
    need(n)
while work:
    n = work.pop()
    for i in drivers.get(n, []):
        if i in live or i in legend:
            continue
        if i in plan and plan[i][0] in ('const', 'alias'):
            continue
        live.add(i)
        if i in plan and plan[i][0] == 'reduce':
            keep = set(plan[i][2].values() if isinstance(plan[i][2], dict) else plan[i][2])
            for p, nn, pt in ip[i]:
                if not isout(p) and pt in keep:
                    need(nn)
        else:
            for p, nn, pt in ip[i]:
                if not isout(p) and not (i in unreach and p.name in ['D%d' % k for k in unreach[i]]):
                    need(nn)
keep_inst = (live | legend | {i for i in range(len(insts)) if i not in ip}) - {i for i in range(len(insts)) if libname(i) == 'C_FUNCTION'}
removed_inst = set(range(len(insts))) - keep_inst
for i in keep_inst:
    if i in ip and i not in legend:
        for p, n, pt in ip[i]:
            if not isout(p) and i not in plan and get(n)[0] == 'c' and libname(i) != 'MUX invert/mask':
                raise SystemExit('live gate with constant input: %s @%s' % (insts[i]['lib'], (insts[i]['x'], insts[i]['y'])))

# ---------------------------------------------------------------- geometry of the kept wires
wires = []   # dict(a, b, block, new)
for blk in blocks:
    if blk['kind'] == 'wire':
        xy = kisch.find(kisch.first(blk['sx'], 'pts'), 'xy')
        wires.append(dict(a=P(float(xy[0][1]), float(xy[0][2])), b=P(float(xy[1][1]), float(xy[1][2])), blk=blk, new=False))

all_pin_pts = {pt for i in ip for p, n, pt in ip[i]}
all_label_pts = set()
for blk in blocks:
    if blk['kind'] in ('label', 'global_label', 'hierarchical_label'):
        at = kisch.first(blk['sx'], 'at')
        all_label_pts.add(P(float(at[1]), float(at[2])))
free_ends = set()      # wire ends that already dangle in the source sheet: not our business
for k0, w0 in enumerate(wires):
    for e in (w0['a'], w0['b']):
        others = sum(1 for k1, w1 in enumerate(wires) if k1 != k0 and (w1['a'] == e or w1['b'] == e or kisch.on_seg(e, w1['a'], w1['b'])))
        if others == 0 and e not in all_pin_pts and e not in all_label_pts:
            free_ends.add((k0, e))
pin_pts = set()
open_pins = set()
for i in keep_inst:
    for p, n, pt in ip.get(i, []):
        if i in unreach and p.name in ['D%d' % k for k in unreach[i]]:
            open_pins.add(pt)
            continue
        pin_pts.add(pt)
label_blocks = [b for b in blocks if b['kind'] in ('label', 'global_label', 'hierarchical_label')]
label_pt = {}
for b in label_blocks:
    at = kisch.first(b['sx'], 'at')
    label_pt[id(b)] = P(float(at[1]), float(at[2]))

drop = set()    # ids of dropped blocks
for i in removed_inst:
    drop.add(id(inst_blocks[i]))
for b in blocks:
    if b['kind'] == 'sheet':
        drop.add(id(b))


def seg_has(pt, w):
    return kisch.on_seg(pt, w['a'], w['b'])


def vertical(w):
    return w['a'][0] == w['b'][0]


# replaced symbols (AO21 -> AND, XOR3 -> XOR): new pin positions, rewire stubs
new_wires = []
replaced = {}
replaced_off = {}


def pins_of(lib_key, ins):
    L = libs[lib_key]
    out = []
    for (u, st), pl in L['pins'].items():
        if u in (0, ins['unit']) and st in (0, 1, ins['style']):
            for p in pl:
                dx, dy = kisch.xform(p.x, p.y, ins['ang'], ins['mirror'])
                out.append((p, P(ins['x'] + dx, ins['y'] + dy)))
    return out


for i, r in plan.items():
    if r[0] != 'reduce' or i not in keep_inst:
        continue
    ins = insts[i]
    newlib = 'peppercorn:' + r[1]
    named = isinstance(r[2], dict)
    old_in = sorted(r[2].values() if named else r[2], key=lambda q: (q[1], q[0]))
    old_out = [pt for p, n, pt in ip[i] if isout(p)]
    occupied = set(all_pin_pts)

    def clash(q):
        return q in occupied or any(kisch.on_seg(q, w['a'], w['b']) for w in wires)

    best = None
    best_key = None
    cand_off = sorted(((dx * 1.27, dy * 1.27) for dx in range(-8, 9) for dy in range(-8, 9)), key=lambda d: (abs(d[0]) + abs(d[1]), d))
    for dx, dy in cand_off:
        moved = dict(ins, x=ins['x'] + dx, y=ins['y'] + dy)
        np_ = pins_of(newlib, moved)
        new_in = sorted([pt for p, pt in np_ if not p.etype.startswith('out')], key=lambda q: (q[1], q[0]))
        new_out = [pt for p, pt in np_ if p.etype.startswith('out')]
        if named:
            by_name = {p.name: pt for p, pt in np_ if not p.etype.startswith('out')}
            if set(by_name) != set(r[2]):
                continue
            new_in = [by_name[k] for k in r[2]]
        if len(new_in) != len(old_in) or len(new_out) != 1:
            continue
        if any(clash(q) for q in new_in + new_out):
            continue
        # prefer the place where the most of the reconnecting wires come out straight (no jog), then the smallest move
        olds = (list(r[2].values()) if named else old_in) + [old_out[0]]
        jogs = sum(1 for a_, b_ in zip(olds, new_in + [new_out[0]]) if a_ != b_ and a_[0] != b_[0] and a_[1] != b_[1])
        key = (jogs, abs(dx) + abs(dy))
        if best_key is None or key < best_key:
            best_key = key
            best = (dx, dy, new_in, new_out)
        if jogs == 0:
            break
    assert best, 'no free place for the replacement of %s' % libname(i)
    dx, dy, new_in, new_out = best
    pairs = list(zip(list(r[2].values()) if named else old_in, new_in)) + [(old_out[0], new_out[0])]
    replaced_off[i] = (dx, dy)
    replaced[i] = (newlib, [q for _, q in pairs])
    for a, b in pairs:
        if a != b:
            new_wires.append((a, b))
    for p, n, pt in ip[i]:
        if not any(pt == pt2 for j in ip if j != i and j in keep_inst for p2, n2, pt2 in ip[j]):   # a pin of another gate may sit on the same point
            pin_pts.discard(pt)
    for _, q in pairs:
        pin_pts.add(q)

# alias gates: connect the passed-through input to the output
for i, r in plan.items():
    if r[0] == 'alias':
        for p, n, pt in ip[i]:
            if isout(p) and pt != r[1]:
                new_wires.append((r[1], pt))


def route(a, b, others):
    """orthogonal route a->b avoiding collinear overlaps with existing wires; returns list of segments"""
    cands = []
    if a[0] == b[0] or a[1] == b[1]:
        cands.append([(a, b)])
    else:
        c1, c2 = P(b[0], a[1]), P(a[0], b[1])
        cands += [[(a, c1), (c1, b)], [(a, c2), (c2, b)]]
        mx = r2(round((a[0] + b[0]) / 2 / 1.27) * 1.27)
        my = r2(round((a[1] + b[1]) / 2 / 1.27) * 1.27)
        cands.append([(a, P(mx, a[1])), (P(mx, a[1]), P(mx, b[1])), (P(mx, b[1]), b)])
        cands.append([(a, P(a[0], my)), (P(a[0], my), P(b[0], my)), (P(b[0], my), b)])
    # detours: step aside, run parallel, step back
    for k in range(1, 13):
        for sg in (1, -1):
            d = 1.27 * k * sg
            p1, p2 = P(a[0] + d, a[1]), P(a[0] + d, b[1])
            cands.append([(a, p1), (p1, p2), (p2, b)])
            q1, q2 = P(a[0], a[1] + d), P(b[0], a[1] + d)
            cands.append([(a, q1), (q1, q2), (q2, b)])
            p1, p2 = P(b[0] + d, a[1]), P(b[0] + d, b[1])
            cands.append([(a, p1), (p1, p2), (p2, b)])

    def ok(segs):
        for s0, s1 in segs:
            for w in others:
                ws = (w['a'], w['b'])
                # collinear overlap
                if (s0[0] == s1[0] == ws[0][0] == ws[1][0]) or (s0[1] == s1[1] == ws[0][1] == ws[1][1]):
                    lo = max(min(s0[0], s1[0]), min(ws[0][0], ws[1][0])) if s0[1] == s1[1] else max(min(s0[1], s1[1]), min(ws[0][1], ws[1][1]))
                    hi = min(max(s0[0], s1[0]), max(ws[0][0], ws[1][0])) if s0[1] == s1[1] else min(max(s0[1], s1[1]), max(ws[0][1], ws[1][1]))
                    if hi - lo > 0.01:
                        return False
                # foreign endpoint lying inside the segment
                for e in ws:
                    if e not in (a, b) and kisch.on_seg(e, s0, s1):
                        return False
                # a bend of the new route must not land on an existing wire
                for e in (s0, s1):
                    if e not in (a, b) and kisch.on_seg(e, ws[0], ws[1]):
                        return False
            for q in pin_pts:
                if q not in (a, b) and kisch.on_seg(q, s0, s1):
                    return False
        return True

    for c in cands:
        if ok(c):
            return c, True
    return cands[0], False


bad_routes = 0
if __import__('os').environ.get('FOLD_DEBUG'):
    for i, r in plan.items():
        print('PLAN', libname(i), (insts[i]['x'], insts[i]['y']), r[0], r[1:] if r[0] != 'const' else r[1])
    for a, b in new_wires:
        print('NEWWIRE', a, b)
for a, b in new_wires:
    segs, good = route(a, b, wires)
    bad_routes += 0 if good else 1
    for s0, s1 in segs:
        wires.append(dict(a=s0, b=s1, blk=None, new=True))

# ---------------------------------------------------------------- prune: dangling wire ends and pin-less nets
label_keep = {id(b): True for b in label_blocks}
nc_blocks = [b for b in blocks if b['kind'] == 'no_connect']
nc_pt = {id(b): P(float(kisch.first(b['sx'], 'at')[1]), float(kisch.first(b['sx'], 'at')[2])) for b in nc_blocks}
alive = [True] * len(wires)


def support(pt, skip):
    n = 0
    for k, w in enumerate(wires):
        if k != skip and alive[k] and (w['a'] == pt or w['b'] == pt or seg_has(pt, w)):
            n += 1
    if pt in pin_pts:
        n += 1
    for b in label_blocks:
        if label_keep[id(b)] and label_pt[id(b)] == pt:
            n += 1
    return n


def components():
    idx = [k for k in range(len(wires)) if alive[k]]
    par = {k: k for k in idx}

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for x in idx:
        for y in idx:
            if x < y:
                wx, wy = wires[x], wires[y]
                if (seg_has(wx['a'], wy) or seg_has(wx['b'], wy) or seg_has(wy['a'], wx) or seg_has(wy['b'], wx)):
                    par[f(x)] = f(y)
    comp = collections.defaultdict(list)
    for k in idx:
        comp[f(k)].append(k)
    return list(comp.values())


hier_pts = {label_pt[id(b)] for b in label_blocks if b['kind'] == 'hierarchical_label'}
while True:
    ch = False
    for k, w in enumerate(wires):
        if not alive[k]:
            continue
        for e in (w['a'], w['b']):
            if support(e, k) != 0 or (k, e) in free_ends:
                continue
            # dangling end: shorten the wire to the nearest point that still carries something (pin, label, other wire), else drop it
            other = w['b'] if e == w['a'] else w['a']
            cands = set()
            for pt in pin_pts | hier_pts:
                if seg_has(pt, w):
                    cands.add(pt)
            for b in label_blocks:
                if label_keep[id(b)] and seg_has(label_pt[id(b)], w):
                    cands.add(label_pt[id(b)])
            for j, w2 in enumerate(wires):
                if j != k and alive[j]:
                    for e2 in (w2['a'], w2['b']):
                        if seg_has(e2, w):
                            cands.add(e2)
            cands -= {e, other}
            if cands:
                p = min(cands, key=lambda q: abs(q[0] - e[0]) + abs(q[1] - e[1]))
                if e == w['a']:
                    w['a'] = p
                else:
                    w['b'] = p
                if w['blk'] is not None:                       # the source block has the old ends: write a new wire instead
                    drop.add(id(w['blk']))
                    w['blk'] = None
                w['new'] = True
            else:
                alive[k] = False
            ch = True
            break
    for comp in components():
        has_pin = any(pt in pin_pts for k in comp for pt in (wires[k]['a'], wires[k]['b']))
        if not has_pin:
            # interior pin points (pin inside a wire) also count
            has_pin = any(any(seg_has(q, wires[k]) for q in pin_pts) for k in comp)
        if not has_pin:
            # no pin: only a through connection between two port labels (e.g. POUTY2 = PINY2 at C_FUNCTION=3) is of use
            has_pin = len({q for q in hier_pts if any(seg_has(q, wires[k]) for k in comp)}) >= 2
        if not has_pin:
            for k in comp:
                alive[k] = False
            ch = True
    # a net label that only ends a stub (one wire ends there, no pin) and that names nothing else is a left-over: drop it, the stub is trimmed afterwards
    comps_now = components()
    comp_of = {k: ci for ci, c in enumerate(comps_now) for k in c}
    names_in = collections.defaultdict(set)
    for b in label_blocks:
        if label_keep[id(b)]:
            pt = label_pt[id(b)]
            for k in range(len(wires)):
                if alive[k] and seg_has(pt, wires[k]):
                    names_in[kisch.s(b['sx'][1])].add(comp_of[k])
    for b in label_blocks:
        if label_keep[id(b)] and b['kind'] == 'label':
            pt = label_pt[id(b)]
            ends = [k for k in range(len(wires)) if alive[k] and (wires[k]['a'] == pt or wires[k]['b'] == pt)]
            thru = [k for k in range(len(wires)) if alive[k] and k not in ends and seg_has(pt, wires[k])]
            others = names_in[kisch.s(b['sx'][1])] - {comp_of[ends[0]]} if len(ends) == 1 else set()
            if len(ends) == 1 and not thru and not others and pt not in pin_pts and pt not in hier_pts:
                label_keep[id(b)] = False
                ch = True
    # a label that is no longer on any wire or pin is dropped (hierarchical labels stay: they are the ports)
    for b in label_blocks:
        if label_keep[id(b)] and b['kind'] != 'hierarchical_label':
            pt = label_pt[id(b)]
            if not any(alive[k] and seg_has(pt, wires[k]) for k in range(len(wires))) and pt not in pin_pts:
                label_keep[id(b)] = False
                ch = True
    if not ch:
        break
def label_connected(b):
    pt = label_pt[id(b)]
    return pt in pin_pts or any(alive[k] and seg_has(pt, wires[k]) for k in range(len(wires)))


byname_h = collections.defaultdict(list)
for b in label_blocks:
    if b['kind'] == 'hierarchical_label' and label_keep[id(b)]:
        byname_h[kisch.s(b['sx'][1])].append(b)
for nm_, lst in byname_h.items():
    conn = [b for b in lst if label_connected(b)]
    for b in lst:
        if not label_connected(b):                    # a port label that hangs in the air is of no use on a folded sheet
            label_keep[id(b)] = False
for b in label_blocks:
    if not label_keep[id(b)]:
        drop.add(id(b))
for k, w in enumerate(wires):
    if not alive[k] and w['blk'] is not None:
        drop.add(id(w['blk']))
for b in nc_blocks:
    if not any(alive[k] and seg_has(nc_pt[id(b)], wires[k]) for k in range(len(wires))) and nc_pt[id(b)] not in pin_pts:
        drop.add(id(b))

# ---------------------------------------------------------------- texts
texts = []
for b in blocks:
    if b['kind'] == 'text':
        at = kisch.first(b['sx'], 'at')
        texts.append((b, kisch.s(b['sx'][1]), float(at[1]), float(at[2])))
inst_pos = [(i, insts[i]['x'], insts[i]['y']) for i in range(len(insts))]
legend_rects = []
for b in blocks:
    if b['kind'] == 'rectangle':
        st, en = kisch.first(b['sx'], 'start'), kisch.first(b['sx'], 'end')
        legend_rects.append((float(st[1]), float(st[2]), float(en[1]), float(en[2])))
note_block = None
for b, s, x, y in texts:
    if s.startswith('C_FUNCTION='):
        note_block = b
        continue
    if 'multiplier mode' in s and F != 3:
        drop.add(id(b))
        continue
    ours = re.match(r'^(C_|L\d\d$|C = |MUX4[ab]$|LUT2$)', s.replace('\\n', '\n')) is not None
    if not ours:
        continue
    if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in legend_rects if x0 >= 200):
        continue
    d, owner = min((math.hypot(x - ix, y - iy), i) for i, ix, iy in inst_pos if i in ip)
    if d <= 8.0 and owner in removed_inst:
        drop.add(id(b))

# ---------------------------------------------------------------- group boxes that lost all their content
def inside(x, y, r):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


for b in blocks:
    if b['kind'] != 'rectangle':
        continue
    st, en = kisch.first(b['sx'], 'start'), kisch.first(b['sx'], 'end')
    x0, x1 = sorted((float(st[1]), float(en[1])))
    y0, y1 = sorted((float(st[2]), float(en[2])))
    r = (x0, y0, x1, y1)
    has = any(inside(insts[i]['x'], insts[i]['y'], r) for i in keep_inst) or \
        any(alive[k] and (inside(wires[k]['a'][0], wires[k]['a'][1], r) or inside(wires[k]['b'][0], wires[k]['b'][1], r)) for k in range(len(wires)))
    if has:
        continue
    drop.add(id(b))                                   # empty box: its title, texts and labels go with it
    for tb, s_, x, y in texts:
        if tb is not note_block and inside(x, y, r):
            drop.add(id(tb))
    for lb in label_blocks:
        if inside(label_pt[id(lb)][0], label_pt[id(lb)][1], r):
            drop.add(id(lb))
            label_keep[id(lb)] = False


# ---------------------------------------------------------------- junctions
def arms_at(pt):
    n = 0
    for k, w in enumerate(wires):
        if alive[k]:
            if w['a'] == pt or w['b'] == pt:
                n += 1
            elif seg_has(pt, w):
                n += 2
    return n + (1 if pt in pin_pts else 0)


junc_blocks = [b for b in blocks if b['kind'] == 'junction']
junc_pts = set()
for b in junc_blocks:
    pt = P(float(kisch.first(b['sx'], 'at')[1]), float(kisch.first(b['sx'], 'at')[2]))
    if arms_at(pt) < 3:
        drop.add(id(b))
    else:
        junc_pts.add(pt)

# ---------------------------------------------------------------- write
def num(v):
    s = ('%.4f' % v).rstrip('0').rstrip('.')
    return s if s != '-0' else '0'


wire_tpl = next(b['text'] for b in blocks if b['kind'] == 'wire')
junc_tpl = junc_blocks[0]['text']


def new_wire_text(a, b):
    t = re.sub(r'\(xy [-\d.]+ [-\d.]+\)\s*\(xy [-\d.]+ [-\d.]+\)',
               lambda m: '(xy %s %s)\n\t\t\t(xy %s %s)' % (num(a[0]), num(a[1]), num(b[0]), num(b[1])), wire_tpl, count=1)
    return re.sub(r'\(uuid "[^"]*"\)', '(uuid "%s")' % uuid.uuid4(), t)


def new_junc_text(pt):
    t = re.sub(r'\(at [-\d.]+ [-\d.]+\)', '(at %s %s)' % (num(pt[0]), num(pt[1])), junc_tpl, count=1)
    return re.sub(r'\(uuid "[^"]*"\)', '(uuid "%s")' % uuid.uuid4(), t)


out = []
for b in blocks:
    if id(b) in drop:
        continue
    t = b['text']
    if b['kind'] == 'symbol' and kisch.first(b['sx'], 'lib_id'):
        i = inst_blocks.index(b)
        t = strip_child(t, 'instances')
        if i in replaced:
            newlib, _ = replaced[i]
            t = re.sub(r'\(lib_id "[^"]*"\)', '(lib_id "%s")' % newlib, t, count=1)
            ddx, ddy = replaced_off[i]
            t = re.sub(r'\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', lambda m: '(at %s %s %s)' % (num(float(m.group(1)) + ddx), num(float(m.group(2)) + ddy), m.group(3)), t, count=1)
            t = re.sub(r'\n\t\t\(lib_name "[^"]*"\)', '', t, count=1)
            npins = len([1 for p, pt in pins_of(newlib, insts[i])])
            pin_re = re.compile(r'\n\t\t\(pin ""\n\t\t\t\(uuid "[^"]*"\)\n\t\t\)')
            found = pin_re.findall(t)
            for extra in found[npins:]:
                t = t.replace(extra, '', 1)
    elif b['kind'] == 'uuid':
        t = '(uuid "%s")' % uuid.uuid4()
    elif b['kind'] == 'title_block':
        t = re.sub(r'\(title "([^"]*)"\)', lambda m: '(title "%s, C_FUNCTION=%d")' % (m.group(1), F), t, count=1)
    elif b is note_block:
        lines = ['C_FUNCTION=%d' % F] + ['%s = %d' % (k, int(v)) for k, v in DEC.items()] + \
                ['constants folded, unused logic removed', 'generated by sim/fold_sheet.py']
        t = re.sub(r'^\(text "(?:[^"\\]|\\.)*"', lambda m: '(text "' + '\\n'.join(lines) + '"', t, count=1)
    out.append(t)

alive_wires = [w for k, w in enumerate(wires) if alive[k]]
for k, w in enumerate(wires):
    if alive[k] and w['new']:
        out.append(new_wire_text(w['a'], w['b']))
# junctions at new T / cross points
cand = set()
for k, w in enumerate(wires):
    if alive[k] and w['new']:
        cand |= {w['a'], w['b']}
for pt in sorted(cand):
    if pt not in junc_pts and arms_at(pt) >= 3:
        out.append(new_junc_text(pt))
        junc_pts.add(pt)

if nc_blocks:
    for pt in sorted(open_pins):
        t_ = re.sub(r'\(at [-\d.]+ [-\d.]+\)', '(at %s %s)' % (num(pt[0]), num(pt[1])), nc_blocks[0]['text'], count=1)
        out.append(re.sub(r'\(uuid "[^"]*"\)', '(uuid "%s")' % uuid.uuid4(), t_))

body = '\n\t'.join(out)
hdr = header
open(DST, 'w', encoding='utf8', newline='\n').write(hdr + body + footer)

cnt = collections.Counter(libname(i) for i in removed_inst)
print('F=%d: kept %d of %d symbols, removed %s' % (F, len(keep_inst), len(insts), dict(cnt)))
print('unreachable mux4 data inputs:', {'%s@(%.1f,%.1f)' % (libname(i), insts[i]['x'], insts[i]['y']): sorted(v) for i, v in unreach.items() if i in keep_inst})
print('plan:', collections.Counter(r[0] for r in plan.values()), 'replaced', {libname(i): v[0] for i, v in replaced.items()})
print('wires kept %d of %d (new %d, routes not clean: %d)' % (sum(alive), len(wires), sum(1 for k, w in enumerate(wires) if alive[k] and w['new']), bad_routes))
print('labels dropped %d, texts/others dropped %d' % (sum(1 for b in label_blocks if id(b) in drop), len(drop)))
