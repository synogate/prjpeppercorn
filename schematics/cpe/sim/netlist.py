import sys, collections
sys.path.insert(0, '.')
import kisch

ERRATA = {}   # (kind, name, position) -> corrected name; empty: the schematic is modelled as drawn


def build(path):
    root, libs, uf, wires, juncs, labels, insts = kisch.load(path)
    # internal nets named like a port (post-LUT1 CLK/EN) are not the port: keep them apart
    labels = [(k, (nm + '_int' if (k == 'label' and nm in ('CLK', 'EN')) else nm), pt) for k, nm, pt in labels]
    # errata: the 8:1 mux side still reads CINY1 / PINY1; commit 5a43fa5 only relabelled the register side
    labels = [(k, ERRATA.get((k, nm, pt), nm), pt) for k, nm, pt in labels]
    pins = kisch.connect(root, libs, uf, wires, juncs, labels, insts)
    # label names per net
    names = collections.defaultdict(set)
    for kind, nm, pt in labels:
        names[uf.f(pt)].add(nm)
    # same-name labels join nets (local/global/hierarchical in a flat sheet)
    byname = {}
    for kind, nm, pt in labels:
        if nm in byname: uf.u(byname[nm], pt)
        else: byname[nm] = pt
    names = collections.defaultdict(set)
    for kind, nm, pt in labels:
        names[uf.f(pt)].add(nm)
    return root, libs, uf, insts, pins, names

if __name__ == '__main__':
    root, libs, uf, insts, pins, names = build('../cpe.kicad_sch')
    netpins = collections.defaultdict(list)
    for i, p, pt in pins:
        netpins[uf.f(pt)].append((i, p))
    # dangling pins (net with a single pin and no label)
    dang = [(i, p) for n, l in netpins.items() for (i, p) in l if len(l) == 1 and not names.get(n)]
    print('nets', len(netpins), 'dangling pins', len(dang))
    multi = {n: v for n, v in names.items() if len(v) > 1}
    print('nets with several label names:', [sorted(v) for v in multi.values()])
    for i, p in dang[:60]:
        ins = insts[i]
        print(' dangling', ins['lib'], ins['props'].get('Reference'), ins['props'].get('Value'), p.name, p.number, p.etype, (ins['x'], ins['y']))
