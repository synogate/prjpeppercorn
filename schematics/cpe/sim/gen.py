"""Generate a Verilog model of the CPE from cpe.kicad_sch.
Usage: python gen.py ../cpe.kicad_sch cpe.v
Config bits are module parameters (names as in the libgm bit database)."""
import sys, re, math, collections
sys.path.insert(0, '.')
import kisch, netlist

BS = chr(92)
NL = chr(10)
Q = chr(39)

# MUX invert/mask blocks: the schematic text "C = Lxx, X = Lyy" names the LUT whose INIT bits invert (C) and the one whose bits select (X) per input.
# nextpnr (pack_cpe.cc, bitstream.cc) has select(X) in L10 and invert(C) in L11 for the upper mux; hardware (S3, S7) confirms both muxes.
# The schematic texts now say so (upper "C = L11, X = L10", lower "C = L10, X = L11"), no swap is needed here.
SWAP_MASK_CX = False
OUTPUT_PORTS = {'OUT1', 'OUT2', 'RAM_O1', 'RAM_O2', 'COUTX', 'COUTY1', 'COUTY2', 'POUTX', 'POUTY1', 'POUTY2'}

TEXT_ALIAS = {'C_RAMI1': 'C_RAM_I1', 'C_RAMI2': 'C_RAM_I2'}
LUT1_NAME = {'C_EN': 'C_CPE_EN', 'C_CLK': 'C_CPE_CLK', 'C_R': 'C_CPE_RES', 'C_S': 'C_CPE_SET'}


def clean(t):
    return t.split(BS)[0].strip()


def vname(n):
    n = n.replace('[', '_').replace(']', '')
    n = re.sub('[^A-Za-z0-9_]', '_', n.replace('-', 'm'))
    if n[0].isdigit():
        n = 'n_' + n
    return n


root, libs, uf, insts, pins, names = netlist.build(sys.argv[1])
# some gate symbols in peppercorn.kicad_sym type their output pin as input: fix by geometry (rightmost pin)
for lname in ('OR', 'XOR', 'XNOR', 'NOR', 'AND', 'NAND', 'XOR3', 'AND3', 'NAND3', 'NOT'):
    L = libs.get('peppercorn:' + lname)
    if L:
        for k, pl in L['pins'].items():
            mx = max(p.x for p in pl)
            for p in pl:
                if p.x == mx:
                    p.etype = 'output'
texts = []
for t in kisch.find(root, 'text'):
    at = kisch.first(t, 'at')
    texts.append((clean(kisch.s(t[1])), float(at[1]), float(at[2]), kisch.s(t[1])))


def near(ins, pred, maxd):
    c = [(math.hypot(t[1] - ins['x'], t[2] - ins['y']), t) for t in texts if pred(t[0])]
    c.sort(key=lambda a: a[0])
    return c[0][1] if c and c[0][0] <= maxd else None


ipins = collections.defaultdict(list)
for i, p, pt in pins:
    ipins[i].append((p, uf.f(pt)))
netpins = collections.defaultdict(list)
for i, lst in ipins.items():
    for p, n in lst:
        netpins[n].append((i, p))


def is_legend(i):
    return all(len(netpins[n]) == 1 and not names.get(n) for p, n in ipins[i]) and insts[i]['lib'] != 'peppercorn:C_FUNCTION'


live = [i for i in range(len(insts)) if i in ipins and not is_legend(i)]
netpins = collections.defaultdict(list, {n: [(i, p) for (i, p) in lst if i in live] for n, lst in netpins.items()})
netpins = collections.defaultdict(list, {n: l for n, l in netpins.items() if l})

root_labels = []
for kind in ('label', 'global_label', 'hierarchical_label'):
    for l in kisch.find(root, kind):
        at = kisch.first(l, 'at')
        root_labels.append((kind, kisch.s(l[1]), (kisch.round2(float(at[1])), kisch.round2(float(at[2])))))
root_labels = [(k, netlist.ERRATA.get((k, nm, pt), nm), pt) for k, nm, pt in root_labels]
hier_names = collections.defaultdict(set)
for kind, nm, pt in root_labels:
    if kind == 'hierarchical_label' and not nm.startswith('C_'):          # blue hierarchical labels of hand-built blocks are config bits (parameters), not ports
        hier_names[uf.f(pt)].add(nm)

allnets = set(netpins)
netname = {}
for n in allnets:
    nms = names.get(n, set())
    if n in hier_names:
        pick = sorted(hier_names[n], key=lambda s: (s in OUTPUT_PORTS, s))[0]   # an input port name first: an output port on the same net becomes an assign
    elif nms:
        pick = sorted(nms, key=lambda s: (len(s), s))[0]
    else:
        pick = None
    netname[n] = pick
used = set()
cnt = 0
for n in sorted(allnets, key=lambda n: (netname[n] is None, str(netname[n]), n)):
    base = (netname[n] if re.match(r'^C_\w+\[\d+\]$', netname[n]) else vname(netname[n])) if netname[n] else None  # bit of a vector config parameter, e.g. C_O1[1]
    if base is None:
        cnt += 1
        base = 'n%03d' % cnt
    nm = base
    k = 1
    while nm in used:
        k += 1
        nm = '%s_%d' % (base, k)
    used.add(nm)
    netname[n] = nm


def etype_out(p):
    return p.etype.startswith('out')


drivers = collections.defaultdict(list)
for n, lst in netpins.items():
    for i, p in lst:
        if i in live and etype_out(p):
            drivers[n].append((i, p))
multi = {n: d for n, d in drivers.items() if len(d) > 1}

params = collections.OrderedDict()


def param(name, width=1):
    params[name] = max(params.get(name, 0), width)
    return name


def cfgbit(name):
    m = re.match(r'(.*)\[(\d+)\]$', name)
    if m:
        base = TEXT_ALIAS.get(m.group(1), m.group(1))
        param(base, int(m.group(2)) + 1)
        return '%s[%s]' % (base, m.group(2))
    nm = TEXT_ALIAS.get(name, name)
    param(nm, 1)
    return nm


for _kind, _nm, _pt in root_labels:                         # blue hierarchical labels of hand-built blocks are config bits
    if _kind == 'hierarchical_label' and _nm.startswith('C_'):
        cfgbit(_nm)


def byname(i, nm):
    r = [netname[n] for p, n in ipins[i] if p.name == nm]
    return r[0] if r else "1'bx"


def outs(i):
    return [(p, netname[n]) for p, n in ipins[i] if etype_out(p)]


def ins_(i):
    return [(p, netname[n]) for p, n in ipins[i] if p.etype.startswith('inp')]


notes = []
lines = []
for i in sorted(live, key=lambda i: (insts[i]['y'], insts[i]['x'])):
    ins = insts[i]
    lib = ins['lib'].split(':')[1]
    tag = '%s @(%.1f,%.1f)' % (lib, ins['x'], ins['y'])
    o = outs(i)
    if lib in ('AND', 'OR', 'XOR', 'XNOR', 'NAND', 'XOR3', 'NOR', 'AND3', 'NAND3'):
        op = {'AND': '&', 'OR': '|', 'XOR': '^', 'XNOR': '^', 'NAND': '&', 'XOR3': '^', 'NOR': '|', 'AND3': '&', 'NAND3': '&'}[lib]
        e = (' %s ' % op).join(n for p, n in ins_(i))
        if lib in ('XNOR', 'NAND', 'NOR', 'NAND3'):
            e = '~(' + e + ')'
        lines.append('  assign %s = %s; // %s' % (o[0][1], e, tag))
    elif lib == 'NOT':
        lines.append('  assign %s = ~%s; // %s' % (o[0][1], ins_(i)[0][1], tag))
    elif lib in ('AO21', 'OA21'):
        a = [netname[n] for p, n in ipins[i] if p.etype.startswith('inp') and p.x < -1]
        b = [netname[n] for p, n in ipins[i] if p.etype.startswith('inp') and p.x == 0.0]
        # by the symbol graphics: AO21 draws OR(pair) feeding AND(top), OA21 draws AND(pair) feeding OR(top)
        if lib == 'AO21':
            e = '(%s | %s) & %s' % (a[0], a[1], b[0])
        else:
            e = '(%s & %s) | %s' % (a[0], a[1], b[0])
        lines.append('  assign %s = %s; // %s' % (o[0][1], e, tag))
    elif lib in ('MUX2', 'MUX2 (conceptual)'):
        lines.append('  assign %s = %s ? %s : %s; // %s' % (o[0][1], byname(i, 'S'), byname(i, 'D1'), byname(i, 'D0'), tag))
    elif lib in ('MUX2B', 'MUX2B (conceptual)'):
        t = near(ins, lambda s: s.startswith('C_'), 1.0)
        if t is None and ins['props'].get('Value', '').startswith('C_'):          # hand-built blocks carry the select name in the Value field
            t = (ins['props']['Value'],)
        if t is None:
            notes.append('MUX2B without select name: ' + tag)
            sel = "1'bx"
        else:
            sel = cfgbit(t[0])
        lines.append('  assign %s = %s ? %s : %s; // %s select %s' % (o[0][1], sel, byname(i, 'D1'), byname(i, 'D0'), tag, sel))
    elif lib.startswith('MUX4'):
        d = [byname(i, 'D%d' % k) for k in range(4)]
        s0, s1 = byname(i, 'S0'), byname(i, 'S1')
        lines.append('  assign %s = %s ? (%s ? %s : %s) : (%s ? %s : %s); // %s' % (o[0][1], s1, s0, d[3], d[2], s0, d[1], d[0], tag))
    elif lib == 'MUX8':
        dd = ', '.join(byname(i, 'D%d' % k) for k in range(7, -1, -1))
        lines.append('  wire [7:0] mux8_d_%d = {%s};' % (i, dd))
        lines.append('  assign %s = mux8_d_%d[{%s, %s, %s}]; // %s' % (o[0][1], i, byname(i, 'S2'), byname(i, 'S1'), byname(i, 'S0'), tag))
    elif lib == 'FA':
        a, b, ci = byname(i, 'A'), byname(i, 'B'), byname(i, 'CI')
        so = [nm for p, nm in o if p.name == 'S']
        co = [nm for p, nm in o if p.name == 'CO']
        if so:
            lines.append('  assign %s = %s ^ %s ^ %s; // %s' % (so[0], a, b, ci, tag))
        if co:
            lines.append('  assign %s = (%s & %s) | (%s & %s) | (%s & %s); // %s' % (co[0], a, b, a, ci, b, ci, tag))
    elif lib == 'LUT1':
        t = near(ins, lambda s: s in LUT1_NAME, 5.0)
        pn = LUT1_NAME[t[0]] if t else None
        if not pn:
            notes.append('LUT1 unnamed: ' + tag)
            pn = 'INIT_LUT1_UNNAMED'
        param(pn, 2)
        lines.append('  assign %s = %s[%s]; // %s' % (o[0][1], pn, byname(i, 'D'), tag))
    elif lib in ('LUT2', 'LUT2 with C_I mux'):
        t = near(ins, lambda s: re.match(r'^L\d\d$', s) is not None, 5.0)
        pn = 'INIT_' + t[0] if t else None
        if lib == 'LUT2' and (pn is None or pn == 'INIT_L21'):
            notes.append('LUT2 unnamed -> INIT_L30 (guess): ' + tag)
            pn = 'INIT_L30'
        if pn is None:
            notes.append('LUT2 with C_I mux unnamed: ' + tag)
            pn = 'INIT_UNNAMED'
        param(pn, 4)
        if lib == 'LUT2':
            d0, d1 = byname(i, 'D0'), byname(i, 'D1')
        else:
            direct = [netname[n] for p, n in ipins[i] if p.x == -5.08][0]
            m0 = [netname[n] for p, n in ipins[i] if p.x == -10.16 and p.name == 'D0'][0]
            m1 = [netname[n] for p, n in ipins[i] if p.x == -10.16 and p.name == 'D1'][0]
            ct = near(ins, lambda s: re.match(r'^C_I\d$', s) is not None, 7.0)
            csel = cfgbit(ct[0]) if ct else "1'bx"
            d0, d1 = direct, '(%s ? %s : %s)' % (csel, m1, m0)
        lines.append('  assign %s = %s[{%s, %s}]; // %s' % (o[0][1], pn, d1, d0, tag))
    elif lib == 'CONFIG':
        t = near(ins, lambda s: s.startswith('C_'), 1.0)
        if t is None:
            notes.append('CONFIG without name: ' + tag)
            continue
        lines.append('  assign %s = %s; // %s' % (o[0][1], cfgbit(t[0]), tag))
    elif lib == 'C_FUNCTION':
        param('C_FUNCTION', 3)
        dec = {'C_MULT': '(C_FUNCTION == 3)', 'C_MX4': '(C_FUNCTION == 4)', 'C_EN_CIN': '(C_FUNCTION == 5)',
               'C_ADDF': '(C_FUNCTION == 1 || C_FUNCTION == 2 || C_FUNCTION == 3 || C_FUNCTION == 6)',
               'C_ADDF2': '(C_FUNCTION == 2 || C_FUNCTION == 3)',
               'C_ADDCIN': '(C_FUNCTION == 1 || C_FUNCTION == 2 || C_FUNCTION == 3 || C_FUNCTION == 7)'}
        for p, n in o:
            # C_MULT / C_ADDF outputs are not wired to their labels in the schematic: drive the labelled net by name
            tgt = n
            for net, nms in names.items():
                if p.name in nms and net in netname and net in netpins:
                    tgt = netname[net]
            lines.append('  assign %s = %s; // %s' % (tgt, dec[p.name], tag))
    elif lib == 'MUX invert/mask':
        t = near(ins, lambda s: s.startswith('C = '), 6.0)
        txt = t[3] if t else ''
        mm = re.search(r'C = (L\d\d)\D+X = (L\d\d)', txt)
        csrc, xsrc = (mm.group(1), mm.group(2)) if mm else ('L10', 'L11')
        if SWAP_MASK_CX:
            csrc, xsrc = xsrc, csrc
        param('INIT_' + csrc, 4)
        param('INIT_' + xsrc, 4)
        e = byname(i, 'E')
        for k in range(4):
            mk = byname(i, 'M%d' % (k + 1))
            on = [nm for p, nm in o if p.name == str(k + 1)]
            if on:
                lines.append('  assign %s = INIT_%s[%d] ^ (%s & INIT_%s[%d] & %s); // %s C(invert)=%s X(select)=%s' % (on[0], csrc, k, e, xsrc, k, mk, tag, csrc, xsrc))
    elif lib == 'DFF':
        lines.append('  cpe_dff u_dff_%d (.C(%s), .E(%s), .D(%s), .S(%s), .R(%s), .Q(%s)); // %s' % (i, byname(i, 'C'), byname(i, 'E'), byname(i, 'D'), byname(i, 'S'), byname(i, 'R'), o[0][1], tag))
    elif lib == 'DLT':
        lines.append('  cpe_dlt u_dlt_%d (.G(%s), .E(%s), .D(%s), .S(%s), .R(%s), .Q(%s)); // %s' % (i, byname(i, 'G'), byname(i, 'E'), byname(i, 'D'), byname(i, 'S'), byname(i, 'R'), o[0][1], tag))
    else:
        notes.append('UNHANDLED ' + tag)

port_in, port_out = [], []
alias_out = []
for n, nm in hier_names.items():
    pn = netname[n]
    (port_out if n in drivers else port_in).append(pn)
    for x in sorted(nm):
        if x != pn and x in OUTPUT_PORTS:                  # e.g. folded sheets: POUTY2 is PINY2
            alias_out.append((x, pn))
            port_out.append(x)
port_in.sort()
port_out.sort()
declared = set(port_in + port_out)
wire_list = sorted(set(netname[n] for n in allnets) - declared)

out = []
out.append('// Generated by schematics/cpe/sim/gen.py from cpe.kicad_sch -- do not edit.')
out.append('// Config bits and LUT INITs are module parameters (names as in the libgm bit database).')
out.append('// "conceptual" (dashed) schematic symbols are modelled functionally.')
out.append('`timescale 1ns/1ps')
out.append('module %s #(' % (sys.argv[3] if len(sys.argv) > 3 else 'cpe'))
pl = []
for k, w in params.items():
    if w > 1:
        pl.append('  parameter [%d:0] %s = %d' % (w - 1, k, 0))
    else:
        pl.append('  parameter %s = 1%sb0' % (k, Q))
out.append((',' + NL).join(pl))
out.append(') (')
plist = ['  input  wire %s' % p for p in port_in] + ['  output wire %s' % p for p in port_out]
out.append((',' + NL).join(plist))
out.append(');')
for w in wire_list:
    if w in params or re.match(r'^C_\w+\[\d+\]$', w):                       # config bits named by a hierarchical label are parameters already
        continue
    out.append('  wire %s;' % w)
out.append('')
for x, pn in alias_out:
    lines.append('  assign %s = %s; // output port on the same net as %s' % (x, pn, pn))
for _t in kisch.find(root, 'text'):                      # folded sheets: constants decoded from C_FUNCTION are listed in a note ("C_MX4 = 1")
    for _m in re.finditer(r'^(C_[A-Z0-9_]+) = ([01])$', kisch.s(_t[1]).replace(BS + 'n', NL), re.M):
        if _m.group(1) in [netname[n] for n in allnets] and not any(netname[n] == _m.group(1) and n in drivers for n in allnets):
            lines.append("  assign %s = 1'b%s; // constant from the sheet note" % (_m.group(1), _m.group(2)))
out += lines
out.append('endmodule')
open(sys.argv[2], 'w').write(NL.join(out) + NL)
print('instances', len(live), 'params', dict(params))
print('ports in', port_in)
print('ports out', port_out)
print('multi-driver nets', [(netname[n], [(insts[i]['lib'], insts[i]['x'], insts[i]['y']) for i, p in d]) for n, d in multi.items()])
print('notes', notes)
undr = [netname[n] for n in allnets if n not in drivers and netname[n] not in port_in and any(not etype_out(p) for i, p in netpins[n])]
print('undriven non-port nets', undr)
