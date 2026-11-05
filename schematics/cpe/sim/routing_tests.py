#!/usr/bin/env python3
#
#  prjpeppercorn -- GateMate FPGAs Bitstream Documentation and Tools
#
#  Copyright (C) 2024  The Project Peppercorn Authors.
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

"""Testbenches for the routing model (*.v), generated from gatemate/die.py. The model itself is hand-written.

  tb_modules.v     every mux entry of die.py against the single-plane modules
  tb_tile2x2_*.v      the wiring inside tile2x2 (BIG11 = 1 and 0) against die.py
  tb_tile4x4.v     routes through tile4x4, configured from the mux table of die.py
  tb_cfg.v         the bit positions of CFG against libgm_layout.py
  tb_wiring.v      every connection of tile4x4 against the connection database of die.py

check_routing.py makes the first two from the schematic; check_netlist.py compares the netlist of
tile4x4 with the connection database.

    python routing_tests.py
"""

import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "gatemate"))
import die
import libgm_layout as lg

PLANES = range(1, 13)
VARIANTS = ("big11", "big22")      # which switch box of the tile is the large one
REP = {"big11": (41, 41), "big22": (43, 41)}   # a tile of each kind (CPE11 position)
ELEMENTS = "im.v om.v sb_big.v sb_sml.v sb_drive.v"
MODEL = ELEMENTS + " tile2x2.v"
N = 4                                   # CPEs per side of the unit
CPE_IDS = ("11", "12", "21", "22")
CARRY = ("cinx", "ciny1", "ciny2", "pinx", "piny1", "piny2")
CARRY_OUT = ("coutx", "couty1", "couty2", "poutx", "pouty1", "pouty2")


# ---------------------------------------------------------------------------------------------
# Ports with packed dimensions, as declared in the Verilog: flat bit index of [a][b]...
# ---------------------------------------------------------------------------------------------

class Bus:
    def __init__(self, dims=""):
        self.dims = [(int(a), int(b)) for a, b in re.findall(r"\[(\d+):(\d+)\]", dims)]
        self.width = 1
        for hi, lo in self.dims:
            self.width *= hi - lo + 1

    def flat(self, *idx):
        assert len(idx) == len(self.dims), (idx, self.dims)
        v = 0
        for (hi, lo), i in zip(self.dims, idx):
            assert lo <= i <= hi, (idx, self.dims)
            v = v * (hi - lo + 1) + (i - lo)
        return v


def tile_ports():
    d = {"im_d": ("in", "[1:0][1:0][12:1][5:0]"), "im_y": ("out", "[1:0][1:0][12:1]"),
         "sb_d": ("in", "[1:0][12:1][4:1][7:2]"), "sb_x12": ("in", "[1:0][12:1]"), "sb_x34": ("in", "[1:0][12:1]"),
         "sb_y": ("out", "[1:0][12:1][4:1]"), "sb_ydiag": ("out", "[1:0][12:1]"),
         "sb_drv": ("out", "[1:0][12:1][4:1]"), "sb_drvn": ("out", "[1:0][12:1][4:1]")}
    d.update({n: ("in", "[1:0][1:0]") for n in CARRY})
    d.update({n: ("out", "[1:0][1:0]") for n in CARRY_OUT})
    return {n: (dr, Bus(dm)) for n, (dr, dm) in d.items()}


def unit_ports():
    c = "[%d:0][%d:0]" % (N - 1, N - 1)
    d = {"ext_im_d": ("in", c + "[12:1][5:0]"), "ext_sb_d": ("in", c + "[12:1][4:1][7:2]"),
         "ext_sb_x12": ("in", c + "[12:1]"), "ext_sb_x34": ("in", c + "[12:1]"),
         "im_y": ("out", c + "[12:1]"), "sb_y": ("out", c + "[12:1][4:1]"), "sb_drv": ("out", c + "[12:1][4:1]"),
         "sb_drvn": ("out", c + "[12:1][4:1]"), "sb_ydiag": ("out", c + "[12:1]")}
    d.update({"ext_" + n: ("in", c) for n in CARRY})
    d.update({n: ("out", c) for n in CARRY_OUT})
    return {n: (dr, Bus(dm)) for n, (dr, dm) in d.items()}


# ---------------------------------------------------------------------------------------------
# Tables: entries (src, dst, value, inv), die.py style names, inv = inversion between the ports
# ---------------------------------------------------------------------------------------------

def split_int(node):
    """'SB_SML.P01.Y1_int' -> ('SB_SML.P01.Y1', 1): an internal node is the inverse of the port."""
    return (node[:-4], 1) if node.endswith("_int") else (node, 0)


def norm_die(kind):
    prefix = {"IM": "IM.P", "OM": "OM.P", "SB_BIG": "SB_BIG.P", "SB_SML": "SB_SML.P"}[kind]
    table = die.get_mux_connections_for_type({"IM": "CPE_IM", "OM": "CPE_IM_OM"}.get(kind, kind))
    direct = {m.dst: m.src for m in table if m.bits == 0}
    res = set()
    for m in table:
        if m.bits == 0 or not m.visible or not m.dst.startswith(prefix):
            continue
        src, sf = split_int(direct.get(m.src, m.src) if kind == "IM" else m.src)
        dst, df = split_int(m.dst)
        res.add((src, dst, m.value, int(m.invert) ^ sf ^ df))
    return res


def norm_die_all():
    return {k: norm_die(k) for k in ("IM", "OM", "SB_BIG", "SB_SML")}


def plane_less(tables):
    """{kind: sorted [(src port, dst port, value, inv)]} for the single-plane modules. All planes must agree;
    the sources of IM D6/D7 (another plane) become the ports D6/D7."""
    out = {}
    for kind, ent in tables.items():
        per = collections.defaultdict(set)
        for src, dst, val, inv in ent:
            p = int(dst.split(".")[1][1:])
            s, d = src.split(".", 2)[2], dst.split(".", 2)[2]
            if kind == "IM" and s == "Y":
                s = f"D{val}"
            per[p].add((s, d, val, inv))
        sets = list(per.values())
        assert all(x == sets[0] for x in sets), f"{kind}: planes differ"
        out[kind] = sorted(sets[0])
    return out


def alt_from_table(im_entries):
    """{(k, plane): source plane} for IM D6 / D7 from a normalised IM table."""
    alt = {}
    for src, dst, val, inv in im_entries:
        if src.endswith(".Y"):
            alt[(val, int(dst[4:6]))] = int(src[4:6])
    return alt


LAYOUT = lg.core_layout()          # the bits of a core tile, from libgm
TILE_BITS = LAYOUT.bits
SB_WORDS = {"SB_BIG": "SB_BIG", "SB_SML": "SB_SML"}


def cfg_word(win, x, y, name):
    """Tile (tx, ty) of the window and libgm word of the mux `name` (die.py) at the CPE (x, y)."""
    parts = name.split(".")
    bx, by = die.base_loc(x, y)
    X, Y = x - bx, y - by
    tile = ((bx - win.x0) // 2, (by - win.y0) // 2)
    if parts[0] == "IM":
        return tile, f"IM{2*X+Y+1}.{parts[1]}"
    if parts[0] == "OM":
        return tile, f"OM{1 if X == 0 else 4}.{parts[1]}"
    return tile, name           # SB_BIG.Pnn.Yn, SB_SML.Pnn.YDIAG, SB_DRIVE.Pnn.Dn


class GridCfg:
    """The configuration of a window: one block of bits per tile."""

    def __init__(self, win):
        self.win = win
        self.tiles = collections.defaultdict(lambda: lg.TileCfg(LAYOUT))

    def set(self, x, y, name, value):
        tile, word = cfg_word(self.win, x, y, name)
        self.tiles[tile].set(word, value)

    def params(self):
        """The parameters CFG_XtxYty of tile4x4, one per 2x2 tile."""
        n = self.win.n // 2
        return [(f"CFG_X{tx}Y{ty}", self.tiles[(tx, ty)].literal() if (tx, ty) in self.tiles else f"{TILE_BITS}'d0")
                for tx in range(n) for ty in range(n)]


def tile_spec(bx, by):
    """Fixed wiring inside the tile whose CPE11 is at (bx, by), from Die.create_outmux / create_sb:
       sbd0    {(s, p): ('cpe', ab, n) | ('om',)}   D0 of plane p of switch box s ('11' or '22')
       omd     {(s, q, k): (ab, n)}                 OM s, plane 9..12, data input k; ab = CPE as in the schematics"""
    d = die.Die("tile", 0, 0)
    d.conn = {}
    pos = {"11": (bx, by), "22": (bx + 1, by + 1)}
    for x, y in pos.values():
        d.create_outmux(x, y)
        d.create_sb(x, y)
    drv = {}
    for lst in d.conn.values():
        for c in lst[1:]:
            drv[(c.x, c.y, c.name)] = (lst[0].x, lst[0].y, lst[0].name)

    def src(node):
        sx, sy, nm = node
        return f"{sx-bx+1}{sy-by+1}", int(nm[-1])

    spec = {"sbd0": {}, "omd": {}}
    for s, (x, y) in pos.items():
        t = die.get_sb_type(x, y)
        for p in PLANES:
            s0 = drv[(x, y, f"{t}.P{p:02d}.D0")]
            spec["sbd0"][(s, p)] = ("om",) if s0[2].startswith("OM.") else ("cpe",) + src(s0)
        for q in range(9, 13):
            for k in range(4):
                spec["omd"][(s, q, k)] = src(drv[(x, y, f"OM.P{q:02d}.D{k}")])
    return spec


def tile_alt():
    """IM planes 6 and 7 inputs: {(k, plane): source plane}"""
    return {(6 + a, p): die.alt_plane(a, p) for a in (0, 1) for p in PLANES}


# ---------------------------------------------------------------------------------------------
# Testbench text
# ---------------------------------------------------------------------------------------------

class Tb:
    """Instances with flat input regs / output wires, stimulus and checks."""

    def __init__(self):
        self.decl, self.code, self.stim, self.checks, self.extra, self.init = [], [], [], [], [], []
        self.ports = []
        self.n = 0
        self.n_checks = 0

    def new(self, module, params, ports, randomize=True):
        """ports: {name: (dir, Bus)}; returns the instance number"""
        k = self.n
        self.n += 1
        self.ports.append(ports)
        conns = []
        for name, (d, bus) in ports.items():
            pre = "i" if d == "in" else "o"
            rng = f"[{bus.width-1}:0] " if bus.width > 1 else ""
            self.decl.append(f"    {'reg' if d == 'in' else 'wire'} {rng}{pre}{k}_{name};")
            conns.append(f".{name}({pre}{k}_{name})")
            if d == "in" and not randomize:
                self.init.append(f"        {pre}{k}_{name} = 0;")
            elif d == "in":
                self.stim.append(f"        for (j = 0; j < {bus.width}; j = j + 32) {pre}{k}_{name}[j +: 32] = $random;"
                                 if bus.width > 32 else f"        {pre}{k}_{name} = $random;")
        pstr = (" #(" + ", ".join(f".{n}({v})" for n, v in params) + ")") if params else ""
        self.code.append(f"    {module}{pstr} u{k} ({', '.join(conns)});")
        return k

    def bit(self, k, port, *idx):
        d, bus = self.ports[k][port]
        pre = "i" if d == "in" else "o"
        return f"{pre}{k}_{port}" + (f"[{bus.flat(*idx)}]" if bus.width > 1 else "")

    def check(self, lhs, rhs, inv, label):
        self.checks.append(f"        if ({lhs} !== ({rhs} ^ 1'b{inv})) begin "
                           f"errors = errors + 1; $display(\"FAIL {label}\"); end")
        self.n_checks += 1

    def text(self, name, source, files, loops=8):
        out = [f"// Generated by routing_tests.py: checks {files} against {source}.",
               f"// Run:  iverilog -g2012 -o {name}.vvp {files} {name}.v && vvp {name}.vvp",
               f"// {self.n} configurations, {self.n_checks} checks x {loops} random vectors.",
               "`timescale 1ns/1ps", "", f"module {name};", "    integer errors, n, j;"]
        out += self.decl + self.code + self.extra + [""]
        out += ["    initial begin", "        errors = 0;"] + self.init + [f"        for (n = 0; n < {loops}; n = n + 1) begin"]
        out += self.stim + ["        #1;"] + self.checks + ["        end",
               "        if (errors == 0) $display(\"PASS %0d configurations\", " + str(self.n) + ");",
               "        else $display(\"FAILED with %0d errors\", errors);",
               "        $finish;", "    end", "endmodule", ""]
        return "\n".join(out)


# ---------------------------------------------------------------------------------------------
# Testbench 1: the single-plane modules against a table
# ---------------------------------------------------------------------------------------------

def module_tb(tables):
    pl = plane_less(tables)
    tb = Tb()
    scalar = Bus()

    def ports(ins, outs):
        d = {n: ("in", scalar) for n in ins}
        d.update({n: ("out", scalar) for n in outs})
        return d

    def checks(k, kind, v, pred=lambda d: True):
        for s, d, val, inv in pl[kind]:
            if val == v and pred(d):
                tb.check(tb.bit(k, d), tb.bit(k, s), inv, f"{kind} {s} -> {d} sel {v}")

    for v in range(8):
        k = tb.new("im", [("SEL", f"3'd{v}")], ports([f"D{n}" for n in range(8)], ["Y"]))
        checks(k, "IM", v)
    for v in range(4):
        k = tb.new("om", [("SEL", f"2'd{v}")], ports([f"D{n}" for n in range(4)], ["Y"]))
        checks(k, "OM", v)
    for kind, mod, big in (("SB_BIG", "sb_big", True), ("SB_SML", "sb_sml", False)):
        ins = ["D0"] + [f"D{k}_{i}" for k in range(2, 8 if big else 4) for i in range(1, 5)]
        ins += ["X12", "X14", "X23", "X34"]
        outs = ["Y1", "Y2", "Y3", "Y4", "YDIAG"]
        w = 3 if big else 2
        for v in range(8 if big else 4):
            # YDIAG fixed to X34 so that selecting YDIAG creates no loop
            params = [(f"SEL_Y{i}", f"{w}'d{v}") for i in range(1, 5)] + [("SEL_YDIAG", "3'd4")]
            checks(tb.new(mod, params, ports(ins, outs)), kind, v, lambda d: d != "YDIAG")
        for v in range(8):
            params = [(f"SEL_Y{i}", f"{w}'d0") for i in range(1, 5)] + [("SEL_YDIAG", f"3'd{v}")]
            checks(tb.new(mod, params, ports(ins, outs)), kind, v, lambda d: d == "YDIAG")
    return tb


# ---------------------------------------------------------------------------------------------
# Testbench 2: the wiring inside a tile
# ---------------------------------------------------------------------------------------------

def tile_tb(variant, spec, alt, with_x=True):
    """Checks the fixed wiring of a tile against spec (tile_spec form) and alt (tile_alt form), with the
    CPEs replaced by cpe_stub.v: every OM select value, SB D0 of all planes, IM planes 6 and 7, and, if
    with_x, YDIAG of neighbouring planes -> X14 / X23."""
    big11 = 1 if variant == "big11" else 0
    tb = Tb()
    ports = tile_ports()
    slot = {"11": 0, "22": 1}

    def cpe_out(k, ab, n):
        return f"u{k}.col[{int(ab[0]) - 1}].row[{int(ab[1]) - 1}].u_cpe.out{n}"

    def sb_type(s):
        return "SB_BIG" if (s == 0) == bool(big11) else "SB_SML"

    def instance(settings):
        """settings: [(libgm word, value)]"""
        cfg = lg.TileCfg(LAYOUT)
        for word, value in settings:
            cfg.set(word, value)
        k = tb.new("tile2x2", [("BIG11", str(big11)), ("CFG", cfg.literal())], ports)
        for x in (0, 1):
            for y in (0, 1):
                for n in (1, 2):
                    tb.stim.append(f"        u{k}.col[{x}].row[{y}].u_cpe.out{n} = $random;")
        return k

    # OM select values 0..3 (0 is the default); SB planes 1..8 take the CPE output directly
    for v in range(4):
        k = instance([(f"OM{1 if slot[s] == 0 else 4}.P{q:02d}", v) for s in slot for q in range(9, 13)])
        for s in slot:
            for p in PLANES:
                w0 = spec["sbd0"][(s, p)]
                y1 = tb.bit(k, "sb_y", slot[s], p, 1)
                if w0[0] == "cpe":
                    if v == 0:
                        tb.check(y1, cpe_out(k, w0[1], w0[2]), 1, f"SB{s} p{p} D0 <- CPE{w0[1]}.OUT{w0[2]}")
                else:
                    ab, n = spec["omd"][(s, p, v)]
                    tb.check(y1, cpe_out(k, ab, n), 0, f"OM{s} p{p} D{v} <- CPE{ab}.OUT{n}")
    # IM planes 6 and 7: Y of another plane
    for v in (6, 7):
        for p in PLANES:
            k = instance([(f"IM{2*x+y+1}.P{p:02d}", v) for x in (0, 1) for y in (0, 1)])
            a = alt[(v, p)]
            for x in (0, 1):
                for y in (0, 1):
                    tb.check(tb.bit(k, "im_y", x, y, p), tb.bit(k, "im_y", x, y, a), 1,
                             f"IM({x},{y}) p{p} D{v} <- p{a}")
    if with_x:
        for v, nb in ((5, die.prev_plane), (7, die.next_plane)):
            k = instance([(f"{sb_type(slot[s])}.P{p:02d}.YDIAG", v) for s in slot for p in PLANES if p % 2])
            for s in slot:
                for p in PLANES:
                    if p % 2:
                        tb.check(tb.bit(k, "sb_ydiag", slot[s], p), tb.bit(k, "sb_ydiag", slot[s], nb(p)), 1,
                                 f"SB{s} p{p} YDIAG <- p{nb(p)} (X{'14' if v == 5 else '23'})")
    return tb


def tile_checks_text(variant, spec, alt, source, with_x):
    tb = tile_tb(variant, spec, alt, with_x)
    name = f"tb_tile2x2_{variant}" + ("" if source.startswith("gatemate") else "_sch")
    return name, tb.text(name, source, f"{MODEL} cpe_stub.v", loops=4), tb


# ---------------------------------------------------------------------------------------------
# Testbench 3: route signals through the grid
# ---------------------------------------------------------------------------------------------

class Window:
    """The connection database of die.py around an NxN window at (x0, y0)."""

    def __init__(self, x0, y0, n=N):
        assert x0 % 2 == 1 and y0 % 2 == 1 and n % 2 == 0
        self.x0, self.y0, self.n = x0, y0, n
        margin = 22  # the longest SB wire spans 20
        self.d = die.Die("grid", 0, 0)
        self.d.conn = {}
        for y in range(y0 - margin, y0 + n + margin):
            for x in range(x0 - margin, x0 + n + margin):
                if die.is_cpe(x, y):
                    self.d.create_cpe(x, y)
                    self.d.create_inmux(x, y)
                    if die.is_outmux(x, y):
                        self.d.create_outmux(x, y)
                if die.is_sb(x, y):
                    self.d.create_sb(x, y)
        self.driver = {}      # dst node -> src node; node = (x, y, wire)
        self.loads = {}       # src node -> [dst node]
        for lst in self.d.conn.values():
            s = lst[0]
            src = (s.x, s.y, s.name)
            for c in lst[1:]:
                dst = (c.x, c.y, c.name)
                assert dst not in self.driver, f"{dst} has two drivers"
                self.driver[dst] = src
                self.loads.setdefault(src, []).append(dst)

    @property
    def origin_big11(self):
        return 1 if die.get_sb_type(self.x0, self.y0) == "SB_BIG" else 0

    def inside(self, x, y):
        return self.x0 <= x < self.x0 + self.n and self.y0 <= y < self.y0 + self.n

    def cpes(self):
        for y in range(self.y0, self.y0 + self.n):
            for x in range(self.x0, self.x0 + self.n):
                yield x, y

    def ext_port(self, dst):
        """(port, indices) of the ext_* input of the grid that feeds an input node of the window."""
        x, y, w = dst
        cx, cy = x - self.x0, y - self.y0
        parts = w.split(".")
        if parts[0] == "IM":
            return "ext_im_d", (cx, cy, int(parts[1][1:]), int(parts[2][1:]))
        if parts[0] == "CPE":
            return "ext_" + parts[1].lower(), (cx, cy)
        p = int(parts[1][1:])
        if parts[2] in ("X12", "X34"):
            return "ext_sb_" + parts[2].lower(), (cx, cy, p)
        return "ext_sb_d", (cx, cy, p, int(parts[2][3]), int(parts[2][1]))


def build_graph(win):
    """Signal graph of the window: node -> [(node, inverting, config)] with config
    (x, y, mux name, value) for edges that need a select setting."""
    adj = {}
    for dst, src in win.driver.items():
        if win.inside(dst[0], dst[1]):
            adj.setdefault(src, []).append((dst, False, None))
    cache = {}
    for x, y in win.cpes():
        t = die.get_tile_type(x, y)
        if t not in cache:
            cache[t] = die.get_mux_connections_for_type(t)
        for m in cache[t]:
            if m.src.startswith("CPE.") or m.dst.startswith("CPE."):
                continue
            cfg = (x, y, m.name, m.value) if m.bits and m.visible else None
            adj.setdefault((x, y, m.src), []).append(((x, y, m.dst), bool(m.invert), cfg))
    return adj


def find_path(win, adj, src, targets):
    """Longest shortest-path from src to any of targets; returns [(node, inv, cfg)] or None."""
    parent = {src: None}
    order = [src]
    for node in order:
        for dst, inv, cfg in adj.get(node, ()):
            if dst not in parent and win.inside(dst[0], dst[1]):
                parent[dst] = (node, inv, cfg)
                order.append(dst)
    reach = [n for n in order if n in targets]
    if not reach:
        return None
    node = reach[-1]
    path = []
    while parent[node] is not None:
        prev, inv, cfg = parent[node]
        path.append((node, inv, cfg))
        node = prev
    return path[::-1]


def grid_tb(win, count):
    """One grid with `count` routes configured at the same time. The routes share no node, so every target
    depends on its own source only."""
    adj = build_graph(win)
    targets = {(x, y, f"IM.P{p:02d}.Y") for x, y in win.cpes() for p in PLANES}
    sources = sorted(s for s, lst in adj.items() if not win.inside(s[0], s[1]))
    step = max(1, len(sources) // (4 * count))
    tests, used = [], set()
    for src in sources[::step]:
        path = find_path(win, adj, src, targets)
        if path and len(path) > 2 and not any(node in used for node, _, _ in path):
            used.update(node for node, _, _ in path)
            tests.append((src, path))
        if len(tests) == count:
            break
    tb = Tb()
    wanted = {n: v for n, v in unit_ports().items() if v[0] == "in" or n == "im_y"}
    cfg = GridCfg(win)
    for src, path in tests:
        for x, y, name, v in [c for _, _, c in path if c]:
            cfg.set(x, y, name, v)
    k = tb.new("tile4x4", [("ORIGIN_BIG11", str(win.origin_big11))] + cfg.params(), wanted, randomize=False)
    for t, (src, path) in enumerate(tests):
        port, idx = win.ext_port(path[0][0])
        tx, ty, tw = path[-1][0]
        parity = sum(1 for _, inv, _ in path if inv) & 1
        label = f"({src[0]},{src[1]}) {src[2]} -> ({tx},{ty}) {tw} via {len(path)} nodes, parity {parity}"
        tb.extra.append(f"    // route {t}: {label}")
        tb.stim.append(f"        {tb.bit(k, port, *idx)} = n[0] ^ 1'b{t & 1};")
        tb.check(tb.bit(k, "im_y", tx - win.x0, ty - win.y0, int(tw[4:6])),
                 f"({tb.bit(k, port, *idx)})", parity, f"route {t}: {label}")
    return tb, len(tests)


def obs(win, node):
    """(port, indices) of the grid output that shows a node inside the window."""
    x, y, w = node
    cx, cy = x - win.x0, y - win.y0
    parts = w.split(".")
    if parts[0] == "CPE":
        return parts[1].lower(), (cx, cy)
    p = int(parts[1][1:])
    if parts[0] == "IM":
        return "im_y", (cx, cy, p)
    if parts[0] == "SB_DRIVE":
        return ("sb_drv" if parts[3] == "OUT" else "sb_drvn"), (cx, cy, p, int(parts[2][1:]))
    if parts[2] == "YDIAG":
        return "sb_ydiag", (cx, cy, p)
    return "sb_y", (cx, cy, p, int(parts[2][1]))


# inversion of the carry and propagate lines in cpe_stub.v: output <- input
STUB_CHAIN = (("COUTX", "CINX", 1), ("COUTY1", "CINY1", 1), ("COUTY2", "CINY2", 0),
              ("POUTX", "PINX", 0), ("POUTY1", "PINY1", 0), ("POUTY2", "PINY2", 1))


def wiring_tb(win):
    """Every connection of the grid, against the database. Six configurations; in configuration j every IM
    selects input Dj, every switch box selects Dk_i with k = j + 2 (the small ones only up to k = 3) and
    its YDIAG selects X34 (j even) or X12 (j odd). Each output must then be the inverse of the signal
    that die.py wires to that input: an output of the grid if the source is inside the window, an ext_*
    bit if it is outside. The carry chain is checked through cpe_stub.v."""
    tb = Tb()
    ports = unit_ports()
    for j in range(6):
        cfg = GridCfg(win)
        k = tb.new("tile4x4", [("ORIGIN_BIG11", str(win.origin_big11)), ("CFG_X0Y0", "0")], ports)
        cfg_at = len(tb.code) - 1
        kk = j + 2
        xsel = 4 if j % 2 == 0 else 6
        xname = "X34" if xsel == 4 else "X12"

        def src_expr(dst):
            src = win.driver[dst]
            if win.inside(src[0], src[1]):
                port, idx = obs(win, src)
            else:
                port, idx = win.ext_port(dst)
            return tb.bit(k, port, *idx)

        for x, y in win.cpes():
            cx, cy = x - win.x0, y - win.y0
            for p in PLANES:
                cfg.set(x, y, f"IM.P{p:02d}", j)
                dst = (x, y, f"IM.P{p:02d}.D{j}")
                tb.check(tb.bit(k, "im_y", cx, cy, p), f"({src_expr(dst)})", 1, f"cfg{j} IM({cx},{cy}) p{p} D{j}")
            if not die.is_sb(x, y):
                continue
            t = die.get_sb_type(x, y)
            big = t == "SB_BIG"
            for p in PLANES:
                ysel = kk if (big or kk <= 3) else 0
                for i in range(1, 5):
                    cfg.set(x, y, f"{t}.P{p:02d}.Y{i}", ysel)
                    if ysel:
                        dst = (x, y, f"{t}.P{p:02d}.D{kk}_{i}")
                        tb.check(tb.bit(k, "sb_y", cx, cy, p, i), f"({src_expr(dst)})", 1,
                                 f"cfg{j} {t}({cx},{cy}) p{p} Y{i} <- D{kk}_{i}")
                cfg.set(x, y, f"{t}.P{p:02d}.YDIAG", xsel)
                dst = (x, y, f"{t}.P{p:02d}.{xname}")
                tb.check(tb.bit(k, "sb_ydiag", cx, cy, p), f"({src_expr(dst)})", 1,
                         f"cfg{j} {t}({cx},{cy}) p{p} YDIAG <- {xname}")
        tb.code[cfg_at] = tb.code[cfg_at].replace(".CFG_X0Y0(0)", ", ".join(f".{n}({v})" for n, v in cfg.params()))
        if j == 0:
            for x, y in win.cpes():
                for out_name, in_name, inv in STUB_CHAIN:
                    # follow the chain back to the first CPE of the window
                    node, par = (x, y), inv
                    while True:
                        dst = (node[0], node[1], "CPE." + in_name)
                        src = win.driver[dst]
                        if not win.inside(src[0], src[1]):
                            break
                        node, par = (src[0], src[1]), par ^ inv
                    port, idx = win.ext_port(dst)
                    tb.check(tb.bit(k, out_name.lower(), x - win.x0, y - win.y0), tb.bit(k, port, *idx), par,
                             f"chain {out_name} ({x - win.x0},{y - win.y0})")
    return tb


def cfg_tb(count=3, seed=1):
    """Testbench for the bit positions: random configuration blocks go into the tile (both values of BIG11,
    cpe_stub.v keeps the CPE parameters), and every parameter of every element must equal the libgm word at
    the position libgm_layout.py has for it."""
    import random
    rng = random.Random(seed)
    tb = Tb()
    ports = tile_ports()
    n_words = 0
    for big11 in (1, 0):
        slot_big = 0 if big11 else 1            # which switch box slot holds the large box
        for _ in range(count):
            cfg = lg.TileCfg(LAYOUT, rng.getrandbits(TILE_BITS))
            k = tb.new("tile2x2", [("BIG11", str(big11)), ("CFG", cfg.literal())], ports, randomize=False)

            def expect(path, word):
                nonlocal n_words
                start, length = LAYOUT.words[word]
                tb.check(f"u{k}.{path}", f"{length}'d{cfg.get(word)}", 0, f"{word} -> {path}")
                n_words += 1

            for word in LAYOUT.words:
                m = re.fullmatch(r"CPE(\d)\.(\w+)", word)
                if m:
                    c = int(m.group(1)) - 1
                    expect(f"col[{c // 2}].row[{c % 2}].u_cpe.{m.group(2)}", word)
                    continue
                m = re.fullmatch(r"IM(\d)\.P(\d\d)", word)
                if m:
                    c = int(m.group(1)) - 1
                    expect(f"col[{c // 2}].row[{c % 2}].plane[{int(m.group(2))}].u_im.SEL", word)
                    continue
                m = re.fullmatch(r"OM(\d)\.P(\d\d)", word)
                if m:
                    expect(f"om[{0 if m.group(1) == '1' else 1}].plane[{int(m.group(2))}].u_om.SEL", word)
                    continue
                m = re.fullmatch(r"(SB_BIG|SB_SML)\.P(\d\d)\.(\w+)", word)
                if m:
                    sl = slot_big if m.group(1) == "SB_BIG" else 1 - slot_big
                    kind = "big" if m.group(1) == "SB_BIG" else "sml"
                    expect(f"sb[{sl}].plane[{int(m.group(2))}].{kind}.u_sb.SEL_{m.group(3)}", word)
                    continue
                m = re.fullmatch(r"SB_DRIVE\.P(\d\d)\.D(\d)", word)
                if m:
                    expect(f"sb[{slot_big}].plane[{int(m.group(1))}].big.dir[{m.group(2)}].u_drv.EN", word)
    # tile4x4: every CFG_XtxYty reaches the 2x2 tile at that place
    cfgs = {(tx, ty): lg.TileCfg(LAYOUT, rng.getrandbits(TILE_BITS)) for tx in (0, 1) for ty in (0, 1)}
    ports4 = unit_ports()
    k = tb.new("tile4x4", [("ORIGIN_BIG11", "1")] + [(f"CFG_X{tx}Y{ty}", c.literal()) for (tx, ty), c in cfgs.items()],
               ports4, randomize=False)
    for (tx, ty), c in cfgs.items():
        tb.check(f"u{k}.tile_x[{tx}].tile_y[{ty}].u_tile.CFG", c.literal(), 0, f"tile4x4 CFG_X{tx}Y{ty}")
        n_words += 1
    return tb, n_words


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=HERE, help="output directory (default: next to this file)")
    ap.add_argument("--routes", type=int, default=24, help="routes in the grid testbench")
    args = ap.parse_args()

    def write(fn, text):
        with open(os.path.join(args.out, fn), "w", newline="\n") as f:
            f.write(text)

    mt = module_tb(norm_die_all())
    write("tb_modules.v", mt.text("tb_modules", "the mux table of gatemate/die.py", ELEMENTS, loops=64))
    nchk = mt.n_checks
    for v in VARIANTS:
        bx, by = REP[v]
        fname, text, t = tile_checks_text(v, tile_spec(bx, by), tile_alt(), "gatemate/die.py (create_outmux, create_sb)", True)
        write(fname + ".v", text)
        nchk += t.n_checks
    ct, nw = cfg_tb()
    write("tb_cfg.v", ct.text("tb_cfg", "libgm/src/TileBitDatabase.cpp", MODEL + " tile4x4.v cpe_stub.v", loops=1))
    nchk += ct.n_checks
    win = Window(41, 41)
    wt = wiring_tb(win)
    write("tb_wiring.v", wt.text("tb_wiring", "the connection database of gatemate/die.py",
                                    MODEL + " tile4x4.v cpe_stub.v", loops=2))
    nchk += wt.n_checks
    gt, n = grid_tb(win, args.routes)
    write("tb_tile4x4.v", gt.text("tb_tile4x4", "the mux table and connections of gatemate/die.py",
                                     MODEL + " tile4x4.v cpe.v", loops=2))
    print(f"{mt.n} module configurations, {n} grid routes, {nchk} checks")


if __name__ == "__main__":
    main()
