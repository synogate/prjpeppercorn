"""CPE validation rig (patch rig): change config words of single CPEs in a nextpnr-built bitstream, load it, read the result.

Everything this module writes goes to a work directory OUTSIDE lab/ (env CPE_RIG_WORK, default <tmp>/cpe_rig_work).
See README.md in this folder for the method, the coordinate mapping and the fixed positions of the baseline design.

    python rig.py setup                       # build the baseline design in the work directory (once)
    python rig.py NAME X:Y:WORD=VALUE ...     # patch, pack, load, read; VALUE '-' deletes the word
    e.g.  python rig.py t1 146:19:C_CX_I=-    -> B'(B) as seen at the reader

As a library:  from rig import run, bprime, decode, tile_of, patch, WORK
"""
import sys, os, re, subprocess, shutil, tempfile
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
sys.path.insert(0, LAB)
from scope import *                       # lab/scope.py (read only)

WORK = os.environ.get("CPE_RIG_WORK") or os.path.join(tempfile.gettempdir(), "cpe_rig_work")
BASE_DIR = os.path.join(WORK, "base")
BASE = os.path.join(BASE_DIR, "bitfile.txt")
os.makedirs(WORK, exist_ok=True)


def setup(force=False):
    """Copy base/ to the work directory and build bitfile.txt there (deterministic: yosys + nextpnr --seed 25)."""
    if os.path.exists(BASE) and not force:
        return BASE
    shutil.copytree(os.path.join(HERE, "base"), BASE_DIR, dirs_exist_ok=True)
    subprocess.run(["make", "bitfile.txt"], cwd=BASE_DIR, check=True)
    return BASE


def tile_of(x, y):
    """Die CPE (x, y) -> (bitstream tile name, CPE index in the tile)."""
    return "0 %d %d" % ((x - 1) // 2, (y - 1) // 2), 1 + (1 if y % 2 == 0 else 0) + (2 if x % 2 == 0 else 0)


def patch(dst, edits):
    """edits: {(x, y, word): value | None}; None deletes the word. New tiles are created when needed."""
    setup()
    blocks = open(BASE, encoding="utf-8").read().split("\n.tile ")
    head, tiles, order = blocks[0], {}, []
    for blk in blocks[1:]:
        h, _, rest = blk.partition("\n")
        tiles[h.strip()] = [l for l in rest.split("\n") if l.strip()]
        order.append(h.strip())
    for (x, y, word), value in edits.items():
        t, cid = tile_of(x, y)
        if t not in tiles:
            tiles[t] = []
            order.append(t)
        key = "CPE%d.%s " % (cid, word)
        lines = tiles[t]
        hit = [k for k, l in enumerate(lines) if l.startswith(key)]
        if value is None:
            for k in reversed(hit):
                del lines[k]
        elif hit:
            lines[hit[0]] = key + value
        else:
            lines.append(key + value)
    out = [head] + [h + "\n" + "\n".join(tiles[h]) + "\n" for h in order]
    open(dst, "w", encoding="utf-8", newline="\n").write("\n.tile ".join(out))


_scope = None


def capture():
    global _scope
    for _ in range(2):
        try:
            if _scope is None:
                _scope = Scope()
                _scope.setup_uart(tscale=1e-3)
            if not _scope.single(10):
                return None
            t, v = _scope.waveform("CHAN1")
            return bytes(b for _, b in decode_uart(t, v, 115200)).decode("ascii", "replace")
        except Exception:
            _scope = None
    return None


def run(name, edits):
    """Patch, pack, load, read one UART line of the baseline test (`i:cs` pairs)."""
    txt, bit = os.path.join(WORK, name + ".txt"), os.path.join(WORK, name + ".bit")
    patch(txt, edits)
    subprocess.run(["gmpack", txt, bit, "--reconfig"], check=True, capture_output=True)
    r = subprocess.run(["openFPGALoader", "-c", "gatemate_pgm", bit], capture_output=True, text=True)
    assert "DONE" in r.stdout + r.stderr, r.stdout + r.stderr
    return capture()


def decode(line):
    """-> {i: (carry, sum)} for i = {CI,B,A}"""
    if not line:
        return None
    try:
        return {int(t[0]): (int(t[2]), int(t[3])) for t in line.split() if len(t) == 4 and t[1] == ":"}
    except ValueError:
        return None


def bprime(line):
    """B' = what arrives on the reader's CINX, for B = 0 and 1 (sum = A ^ B' ^ CI); 'x' if the rows disagree."""
    d = decode(line)
    if not d or len(d) != 8:
        return "?"
    res = {0: set(), 1: set()}
    for i, (c, s) in d.items():
        res[(i >> 1) & 1].add(s ^ (i & 1) ^ (i >> 2))
    return {b: (v.pop() if len(v) == 1 else "x") for b, v in res.items()}


if __name__ == "__main__":
    if sys.argv[1] == "setup":
        print(setup(force=True))
        sys.exit(0)
    name = sys.argv[1]
    edits = {}
    for a in sys.argv[2:]:
        k, v = a.split("=")
        x, y, w = k.split(":")
        edits[(int(x), int(y), w)] = None if v == "-" else v
    line = run(name, edits)
    print(name, edits, "->", line, "| B'(B)=", bprime(line))
