"""The configuration bits of a core tile (4 CPEs, 2 switch boxes), as libgm stores them.

The offsets of the settings are read from libgm/src/TileBitDatabase.cpp (the add_* functions); only the loops
of the TileBitDatabase constructor are written out here, and an exact copy of that part of the C++ text is
compared with the file, so a change of the layout in libgm stops the tests instead of passing silently.

    layout = core_layout()          # {"IM1.P01": (start, length), ...}, bit numbers in the tile block
    cfg = TileCfg(layout); cfg.set("SB_BIG.P03.Y1", 2); cfg.v   # the block as an integer, bit n = bit n of the data

Bit n of the block is bit n % 8 (lowest first) of byte n // 8; a setting is stored lowest bit first.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LIBGM = os.path.join(HERE, "..", "..", "..", "libgm")

# Constructor of TileBitDatabase for a core tile, as in the C++ file (white space and comments ignored)
CORE_PART = """is_core = true;
for (int i = 0; i < 4; i++) {
    add_cpe(i + 1, 10 * i * 8);
    add_ff_init(i + 1, (Die::LATCH_BLOCK_SIZE - 1) * 8 + i * 2);
}
int pos = 40;
for (int i = 0; i < 4; i++) {
    for (int j = 0; j < 6; j++) {
        add_inmux(i + 1, j * 2 + 1, pos * 8);
        add_inmux(i + 1, j * 2 + 2, pos * 8 + 3);
        pos++;
    }
}
for (int i = 0; i < 2; i++) {
    pos = 54 + i * 6;
    for (int j = 9; j <= 12; j++) {
        add_outmux(i ? 4 : 1, j, pos * 8 + 6);
        pos++;
    }
}
}"""

ALL_TILES_PART = """int pos = 64;
for (int i = 0; i < 6; i++) {
    add_sb_big(i * 2 + 1, pos * 8);
    add_sb_drive(i * 2 + 1, (pos + 2) * 8);
    add_sb_drive(i * 2 + 2, (pos + 2) * 8 + 4);
    add_sb_big(i * 2 + 2, (pos + 3) * 8);
    pos += 5;
}
for (int i = 0; i < 6; i++) {
    add_sb_sml(i * 2 + 1, pos * 8);
    add_sb_sml(i * 2 + 2, (pos + 1) * 8 + 4);
    pos += 3;
}
add_unknowns();"""


def _norm(text):
    text = re.sub(r"//[^\n]*", "", text)
    return re.sub(r"\s+", "", text)


class Layout:
    def __init__(self):
        self.words = {}
        self.bits = 0

    def add(self, name, start, length):
        assert name not in self.words, name
        for n, (s, l) in self.words.items():
            assert start + length <= s or s + l <= start, f"{name} overlaps {n}"
        self.words[name] = (start, length)


def core_layout():
    cpp = open(os.path.join(LIBGM, "src", "TileBitDatabase.cpp"), encoding="utf-8").read()
    hpp = open(os.path.join(LIBGM, "include", "Die.hpp"), encoding="utf-8").read()
    latch = eval(re.search(r"LATCH_BLOCK_SIZE\s*=\s*([^;/]+)", hpp).group(1))

    # the constructor must still be the one written above
    ctor = cpp[cpp.index("TileBitDatabase::TileBitDatabase"):]
    a = ctor.index("is_core = true;")
    part1 = ctor[a:ctor.index("if (!is_core)")]
    b = ctor.index("int pos = 64;")
    part2 = ctor[b:ctor.index("add_unknowns();") + len("add_unknowns();")]
    if _norm(part1) != _norm(CORE_PART) or _norm(part2) != _norm(ALL_TILES_PART):
        raise SystemExit("libgm/src/TileBitDatabase.cpp: the constructor changed, update CORE_PART in libgm_layout.py "
                         "and the offsets in gm_tile2x2.v")

    # the add_* functions: name -> [(format, argument expressions, offset expression, length)]
    funcs = {}
    for m in re.finditer(r"void TileBitDatabase::(add_\w+)\(([^)]*)\)\s*\{(.*?)\n\}", cpp, re.S):
        body = m.group(3)
        calls = re.findall(r'add_word_settings\(stringf\("([^"]+)",\s*([^)]*)\),\s*([^;]+?),\s*(\d+)\);', body)
        loop = re.search(r"for \(int i = 0; i < (\d+); i\+\+\)", body)
        funcs[m.group(1)] = (calls, int(loop.group(1)) if loop else 1, [a.split()[-1] for a in m.group(2).split(",")])

    lay = Layout()

    def call(fname, *args):
        calls, reps, argnames = funcs[fname]
        env = dict(zip(argnames, args))
        for i in range(reps):
            env["i"] = i
            for fmt, fargs, off, length in calls:
                name = fmt % tuple(eval(a, {}, env) for a in fargs.split(","))
                lay.add(name, eval(off, {}, env), int(length))

    for i in range(4):
        call("add_cpe", i + 1, 10 * i * 8)
        call("add_ff_init", i + 1, (latch - 1) * 8 + i * 2)
    pos = 40
    for i in range(4):
        for j in range(6):
            call("add_inmux", i + 1, j * 2 + 1, pos * 8)
            call("add_inmux", i + 1, j * 2 + 2, pos * 8 + 3)
            pos += 1
    for i in range(2):
        pos = 54 + i * 6
        for j in range(9, 13):
            call("add_outmux", 4 if i else 1, j, pos * 8 + 6)
            pos += 1
    pos = 64
    for i in range(6):
        call("add_sb_big", i * 2 + 1, pos * 8)
        call("add_sb_drive", i * 2 + 1, (pos + 2) * 8)
        call("add_sb_drive", i * 2 + 2, (pos + 2) * 8 + 4)
        call("add_sb_big", i * 2 + 2, (pos + 3) * 8)
        pos += 5
    for i in range(6):
        call("add_sb_sml", i * 2 + 1, pos * 8)
        call("add_sb_sml", i * 2 + 2, (pos + 1) * 8 + 4)
        pos += 3
    lay.bits = latch * 8
    return lay


class TileCfg:
    """The 8 * LATCH_BLOCK_SIZE bits of one tile."""

    def __init__(self, layout, v=0):
        self.layout = layout
        self.v = v

    def set(self, name, value):
        start, length = self.layout.words[name]
        assert 0 <= value < (1 << length), (name, value)
        self.v = (self.v & ~(((1 << length) - 1) << start)) | (value << start)

    def get(self, name):
        start, length = self.layout.words[name]
        return (self.v >> start) & ((1 << length) - 1)

    def literal(self):
        return f"{self.layout.bits}'h{self.v:x}"
