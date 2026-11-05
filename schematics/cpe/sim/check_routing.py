#!/usr/bin/env python3
"""Compare the routing model (*.v, tested against gatemate/die.py by routing_tests.py) with the schematic.

  1. Tables: every mux of im, om11, om22, sb_big, sb_sml is read from the .kicad_sch (data pin Dk of a
     MUX4B/MUX8B -> net behind the NOT that follows it) and compared with the mux table of die.py.
  2. Verilog: the schematic table is turned into tb_modules_sch.v, which checks the module files against it.
  3. Wiring: which CPE output feeds which OM input / SB D0 (labels in om11 / om22) against Die.create_outmux
     and Die.create_sb.
  4. Top level: the nets between the sheets of prjpeppercorn.kicad_sch (the 4x4 tile) against the connection
     database of the same 4x4 window.

Needs kisch.py and netlist.py (same directory, or the directory in $GM_SIM_TOOLS).

    python check_routing.py
    iverilog -g2012 -o tb_modules_sch.vvp im.v om.v sb_big.v sb_sml.v sb_drive.v tb_modules_sch.v && vvp tb_modules_sch.vvp

What the schematic cannot tell: the MUX8B / MUX4B symbols have no select pins, so "select value k" is taken to
be "data pin Dk". The config bit assignment (3 bit pattern per mux) is only in die.py / libgm.
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for d in (HERE, os.environ.get("GM_SIM_TOOLS", "")):
    if d and os.path.exists(os.path.join(d, "kisch.py")):
        sys.path.insert(0, d)
        break
sys.path.insert(0, HERE)
import kisch
import netlist
import routing_tests as g
import die

PLANES = g.PLANES
SCH = os.path.join(HERE, "..")


def build(path):
    """netlist.build with one fix: im.kicad_sch caches its NOT symbols as NOT_12..NOT_23 while the instances
    say prjpeppercorn:NOT, so their pins would not resolve."""
    root, libs, uf, wires, juncs, labels, insts = kisch.load(path)
    for name in list(libs):
        if re.fullmatch(r"NOT_\d+", name) and "prjpeppercorn:NOT" not in libs:
            libs["prjpeppercorn:NOT"] = libs[name]
    pins = kisch.connect(root, libs, uf, wires, juncs, labels, insts)
    byname = {}
    for kind, nm, pt in labels:
        if nm in byname:
            uf.u(byname[nm], pt)
        else:
            byname[nm] = pt
    names = collections.defaultdict(set)
    for kind, nm, pt in labels:
        names[uf.f(pt)].add(nm)
    return root, libs, uf, insts, pins, names


class Sheet:
    """Muxes of one routing sheet: [(k, data nets, out label set, NOT-out net)]"""

    def __init__(self, name):
        root, libs, uf, insts, pins, names = build(os.path.join(SCH, name + ".kicad_sch"))
        self.names = names
        ip = collections.defaultdict(list)
        for i, p, pt in pins:
            ip[i].append((p, uf.f(pt)))
        nots = {}                      # NOT input net -> NOT output net
        muxes = []                     # (instance, {pin name: net}, Y net)
        for i, ins in enumerate(insts):
            lib = ins["lib"].split(":")[1]
            if lib == "NOT":
                a = [n for p, n in ip[i] if p.etype == "input"][0]
                b = [n for p, n in ip[i] if p.etype == "output"][0]
                nots[a] = b
            elif lib in ("MUX4B", "MUX8B"):
                d = {p.name: n for p, n in ip[i]}
                muxes.append((i, d, d["Y"]))
            else:
                raise SystemExit(f"{name}: unexpected symbol {lib}")
        self.muxes = muxes
        self.nots = nots
        self.mux_by_y = {y: m for m in muxes for y in [m[2]]}
        for _, _, y in muxes:
            assert y in nots, f"{name}: mux output without NOT"

    def labels(self, net):
        return sorted(self.names.get(net, ()))

    def resolve(self, net):
        """(labels, flag): the net carries the inverse of the labelled port if flag"""
        if net in self.mux_by_y:
            return self.labels(self.nots[net]), 1
        return self.labels(net), 0


def pick(labels, pattern):
    for l in labels:
        m = re.fullmatch(pattern, l)
        if m:
            return m
    return None


def sheet_tables():
    """Normalised tables from the schematic, plus the wiring of the OM sheets."""
    tables = {}
    wiring = {}
    # --- IM: 12 planes in one sheet
    sh = Sheet("im")
    ent = set()
    for _, d, y in sh.muxes:
        dst_l = sh.labels(sh.nots[y])
        dm = pick(dst_l, r"IM\.(P\d\d)\.Y")
        dst = f"IM.{dm.group(1)}.Y"
        for pin, net in d.items():
            if pin == "Y":
                continue
            labels, sf = sh.resolve(net)
            m = pick(labels, r"(?:IM\.)?(P\d\d)\.(D\d|Y)")
            ent.add((f"IM.{m.group(1)}.{m.group(2)}", dst, int(pin[1:]), 1 ^ sf))
    tables["IM"] = ent
    # --- OM: planes 9..12, two variants
    for variant in ("om11", "om22"):
        sh = Sheet(variant)
        ent = set()
        wire = {}
        for _, d, y in sh.muxes:
            dst_l = sh.labels(sh.nots[y])
            plane = pick(dst_l, r"SB\.P(\d\d)\.D0").group(1)
            dst = f"OM.P{plane}.Y"
            for pin, net in d.items():
                if pin == "Y":
                    continue
                labels, sf = sh.resolve(net)
                assert sf == 0
                ent.add((f"OM.P{plane}.D{pin[1:]}", dst, int(pin[1:]), 1))
                cpe = [l for l in labels if l.startswith("CPE")][0]
                wire[(int(plane), int(pin[1:]))] = cpe
                sbm = pick(labels, r"SB\.P(\d\d)\.D0")
                if sbm:
                    wire[("sb", int(sbm.group(1)))] = cpe
        tables[variant] = ent
        wiring[variant] = wire
    # --- SB: one plane per sheet, replicated
    for kind, fname in (("SB_BIG", "sb_big"), ("SB_SML", "sb_sml")):
        sh = Sheet(fname)
        ent = set()
        for _, d, y in sh.muxes:
            dst_l = sh.labels(sh.nots[y])
            dst = dst_l[0]
            for pin, net in d.items():
                if pin == "Y":
                    continue
                labels, sf = sh.resolve(net)
                assert len(labels) == 1, (fname, pin, labels)
                for p in PLANES:
                    ent.add((f"{kind}.P{p:02d}.{labels[0]}", f"{kind}.P{p:02d}.{dst}", int(pin[1:]), 1 ^ sf))
        tables[kind] = ent
    return tables, wiring


def diff(name, sch, mdl):
    only_s, only_d = sorted(sch - mdl), sorted(mdl - sch)
    print(f"  {name}: schematic {len(sch)} entries, die.py {len(mdl)}: "
          + ("identical" if not only_s and not only_d else f"{len(only_s)} only in schematic, {len(only_d)} only in die.py"))
    for e in only_s[:12]:
        print("      schematic only:", e)
    for e in only_d[:12]:
        print("      die.py only:   ", e)
    return not only_s and not only_d


def main():
    ok = True
    tables, wiring = sheet_tables()
    die_t = g.norm_die_all()
    print("1. mux tables, schematic vs die.py")
    ok &= diff("IM", tables["IM"], die_t["IM"])
    # OM: the two sheets differ only in the wiring of their inputs, the table is the same
    ok &= diff("OM (om11)", tables["om11"], die_t["OM"])
    ok &= diff("OM (om22)", tables["om22"], die_t["OM"])
    ok &= diff("SB_BIG", tables["SB_BIG"], die_t["SB_BIG"])
    ok &= diff("SB_SML", tables["SB_SML"], die_t["SB_SML"])

    print("2. single-plane modules vs schematic table -> tb_modules_sch.v")
    sch_t = {"IM": tables["IM"], "OM": tables["om11"], "SB_BIG": tables["SB_BIG"], "SB_SML": tables["SB_SML"]}
    mt = g.module_tb(sch_t)
    with open(os.path.join(HERE, "tb_modules_sch.v"), "w", newline="\n") as f:
        f.write(mt.text("tb_modules_sch", "the schematic (im, om11, sb_big, sb_sml)", g.ELEMENTS))
    print(f"  {mt.n} configurations, {mt.n_checks} checks (run with iverilog, see top of this file)")

    print("3. wiring inside the tile, schematic vs Die.create_outmux / create_sb / alt_plane")
    ok &= check_tile(tables, wiring)

    print("4. top level (prjpeppercorn.kicad_sch, 4x4 CPEs at x/y = 41..44), nets between sheets")
    ok &= check_top(wiring)

    sys.exit(0 if ok else 1)


def check_tile(tables, wiring):
    """CPE outputs -> OM inputs and SB D0 (labels in om11 / om22), IM planes 6 / 7 (nets in im)."""
    alt_s, alt_d = g.alt_from_table(tables["IM"]), g.tile_alt()
    bad = 0
    for key in sorted(set(alt_s) | set(alt_d)):
        if alt_s.get(key) != alt_d.get(key):
            bad += 1
            print(f"      IM plane {key[1]} D{key[0]}: schematic plane {alt_s.get(key)}, die.py plane {alt_d.get(key)}")
    print("  IM D6 / D7 sources (24): " + ("identical" if not bad else f"{bad} differences"))
    spec_s = {"sbd0": {}, "omd": {}}
    for s in ("11", "22"):
        w = wiring["om" + s]
        for p in g.PLANES:
            lab = w.get(("sb", p))
            spec_s["sbd0"][(s, p)] = ("om",) if p >= 9 else ("cpe", lab[3:5], int(lab[-1]))
        for q in range(9, 13):
            for k in range(4):
                lab = w[(q, k)]
                spec_s["omd"][(s, q, k)] = (lab[3:5], int(lab[-1]))
    n = 0
    for v in g.VARIANTS:
        spec_d = g.tile_spec(*g.REP[v])
        for part in ("sbd0", "omd"):
            for key in sorted(spec_d[part]):
                n += 1
                if spec_s[part].get(key) != spec_d[part][key]:
                    bad += 1
                    print(f"      {v} {part}{key}: schematic {spec_s[part].get(key)}, die.py {spec_d[part][key]}")
        name, text, t = g.tile_checks_text(v, spec_s, alt_s, "the schematic (om11, om22, im)", False)
        with open(os.path.join(HERE, name + ".v"), "w", newline="\n") as f:
            f.write(text)
        print(f"  {name}.v: {t.n} configurations, {t.n_checks} checks")
    print(f"  {n} OM input / SB D0 wires of the two tile kinds: " + ("identical" if not bad else f"{bad} differences"))
    return not bad


PITCH = 114.3


def check_top(wiring, x0=41, y0=41):
    """Plane 1 of the 4x4 tile. Only nets made of wires are compared: the CPE.OUT / OM pins are tied by
    label name, and the same names (CPE11.OUT1 ...) are used by all four 2x2 blocks."""
    root, libs, uf, wires, juncs, labels, insts = kisch.load(os.path.join(SCH, "prjpeppercorn.kicad_sch"))
    sheets = []
    for sh in kisch.find(root, "sheet"):
        props = {kisch.s(p[1]): kisch.s(p[2]) for p in kisch.find(sh, "property")}
        at = kisch.first(sh, "at")
        pl = [(kisch.s(p[1]), (kisch.round2(float(kisch.first(p, "at")[1])), kisch.round2(float(kisch.first(p, "at")[2]))))
              for p in kisch.find(sh, "pin")]
        sheets.append((props["Sheetfile"][:-10], float(at[1]), float(at[2]), pl))
    pts = {pt for *_, pl in sheets for _, pt in pl}
    for pt in pts:
        uf.f(pt)
        for a, b in wires:
            if kisch.on_seg(pt, a, b):
                uf.u(pt, a)
    grid = g.Window(x0, y0, 4)
    nets = collections.defaultdict(set)
    problems = 0
    for f, sx, sy, pl in sheets:
        if f in ("im", "cpe"):
            i = round((sx - (72.39 if f == "im" else 100.33)) / PITCH)
            j = round((444.5 - sy) / PITCH)
        elif f in ("sb_big", "sb_sml"):
            i, j = round((sx - 38.1) / PITCH), round((444.5 - 73.66 - sy) / PITCH)
        else:
            continue
        x, y = x0 + i, y0 + j
        if f.startswith("sb"):
            want = "sb_big" if die.get_sb_type(x, y) == "SB_BIG" else "sb_sml"
            if f != want:
                problems += 1
                print(f"      sheet {f} at ({x},{y}): die.py has {want} there")
        for name, pt in pl:
            if f == "im":
                node = (x, y, "IM.P01.Y" if name == "CPE.IN1" else "IM." + name)
            elif f == "cpe":
                if name != "IN1":
                    continue
                node = (x, y, "IM.P01.Y")
            else:
                node = (x, y, f"{die.get_sb_type(x, y)}.P01.{name}")
            nets[uf.f(pt)].add(node)
    exposed = {n for v in nets.values() for n in v}
    sch = {frozenset(v) for v in nets.values() if len(v) > 1}
    # components of the database; sources outside the exposed set still tie their loads together
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for dst, src in grid.driver.items():
        if dst in exposed:
            parent[find(dst)] = find(src)
    comp = collections.defaultdict(set)
    for n in exposed:
        comp[find(n)].add(n)
    where = {n: frozenset(comp[find(n)]) for n in exposed}
    conflicts = [e for e in sch if len({where[n] for n in e}) > 1]
    drawn = {where[next(iter(e))] for e in sch if e not in conflicts}
    missing = [c for c in {frozenset(v) for v in comp.values() if len(v) > 1}
               if not any(c <= set(e) for e in sch)]
    print(f"  {len(sch)} nets with several pins in the schematic: "
          f"{len(sch) - len(conflicts)} agree with die.py, {len(conflicts)} conflict")
    for e in sorted(conflicts, key=sorted)[:15]:
        print("      conflict:", sorted(e), "die.py:", [sorted(where[n]) for n in e][:2])
    kinds = collections.Counter()
    for c in missing:
        kinds["/".join(sorted({n[2].split(".")[0] + "." + n[2].split(".")[-1].split("_")[0][:2] for n in c}))] += 1
    print(f"  {len(missing)} connections of die.py between exposed pins are not drawn at top level (informational), by kind:")
    for k, n in kinds.most_common(8):
        print(f"      {n:3d}  {k}")
    only_s = conflicts
    only_m = []
    return not problems and not only_s and not only_m


if __name__ == "__main__":
    main()
