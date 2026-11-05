"""Put one hierarchical-sheet reference per C_FUNCTION 0..7 into ../cpe.kicad_sch (idempotent).

Usage (from sim/):  python place_function_sheets.py

The sheets that already exist keep their uuid and their page numbers in the project hierarchy, they are only renamed ("C_FUNCTION=n")
and moved into a grid (3 rows x 3 columns, left of the big group boxes). The missing ones are copies of the C_FUNCTION=0 symbol with a
new uuid and unused page numbers (129 and up).  The sheet files are the ones written by build_function_sheets.py.
"""
import os, re, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, '..', 'cpe.kicad_sch')
FILES = {0: 'cpe_comb', 1: 'cpe_comb_addf', 2: 'cpe_comb_addf2', 3: 'cpe_comb_mult',
         4: 'cpe_comb_mux4', 5: 'cpe_comb_en_cin', 6: 'cpe_comb_concat', 7: 'cpe_comb_addcin'}
COL = [107.95, 149.86, 191.77]
ROW = [21.59, 31.75, 41.91]
POS = {f: (COL[f % 3], ROW[f // 3]) for f in range(8)}          # row by row: 0 1 2 / 3 4 5 / 6 7
FIRST_NEW_PAGE = 129
BS = chr(92)


def end_of(t, i):
    depth = 0
    k = i
    while True:
        c = t[k]
        if c == '"':
            k += 1
            while t[k] != '"':
                if t[k] == BS:
                    k += 1
                k += 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return k + 1
        k += 1


def fmt(v):
    return ('%.2f' % v).rstrip('0').rstrip('.')


def shift(blk, dx, dy):
    return re.sub(r'\(at ([-\d.]+) ([-\d.]+)', lambda m: '(at %s %s' % (fmt(float(m.group(1)) + dx), fmt(float(m.group(2)) + dy)), blk)


t = open(TOP, encoding='utf8', newline='').read()
nl = '\r\n' if '\r\n' in t else '\n'
blocks = []                                    # (start, end, text) of the sheet symbols
for m in re.finditer(r'\n\t\(sheet' + nl.replace('\r\n', '\r\n') + r'|\n\t\(sheet\b', t):
    pass
k = 0
while True:
    m = re.compile(r'\t\(sheet\s').search(t, k)
    if not m:
        break
    a = m.start()
    b = end_of(t, a + 1)
    blocks.append((a, b, t[a:b]))
    k = b
by_file = {}
for a, b, s in blocks:
    by_file[re.search(r'\(property "Sheetfile" "([^"]*)"', s).group(1)] = s
assert by_file, 'no sheet symbols found'

new_blocks = {}
n_new = 0
template = by_file['cpe_comb.kicad_sch']
tx, ty = [float(v) for v in re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', template).groups()]
for f, name in FILES.items():
    x, y = POS[f]
    if name + '.kicad_sch' in by_file:
        s = by_file[name + '.kicad_sch']
        ox, oy = [float(v) for v in re.search(r'\(at ([-\d.]+) ([-\d.]+)\)', s).groups()]
        s = shift(s, x - ox, y - oy)
    else:
        s = shift(template, x - tx, y - ty)
        s = s.replace('"cpe_comb.kicad_sch"', '"%s.kicad_sch"' % name, 1)
        s = re.sub(r'\(uuid "[^"]*"\)', '(uuid "%s")' % uuid.uuid4(), s, count=1)
        pages = iter(range(1, 1000))
        j = [0]

        def newpage(m, n_new=n_new):
            j[0] += 1
            return '(page "%d")' % (FIRST_NEW_PAGE + (j[0] - 1) * 3 + n_new if j[0] <= 16 else 7 + n_new)
        s = re.sub(r'\(page "\d+"\)', newpage, s)
        n_new += 1
    s = re.sub(r'(\(property "Sheetname" )"[^"]*"', r'\1"C_FUNCTION=%d"' % f, s, count=1)
    new_blocks[f] = s

# page numbers in function order: per hierarchy path the eight pages (already unique in the project) are sorted and handed out by function
PG = re.compile(r'\(page "(\d+)"\)')
cols = [[int(v) for v in PG.findall(new_blocks[f])] for f in range(8)]
assert len({len(c) for c in cols}) == 1, 'sheet symbols with different numbers of instances'
for i in range(len(cols[0])):
    vals = sorted(cols[f][i] for f in range(8))
    for f in range(8):
        cols[f][i] = vals[f]
for f in range(8):
    it = iter(cols[f])
    new_blocks[f] = PG.sub(lambda m: '(page "%d")' % next(it), new_blocks[f])

# replace the old blocks by the new ones, in function order, at the place of the first old block
first = blocks[0][0]
out = t
for a, b, s in sorted(blocks, reverse=True):
    cut_a = a - len(nl) if out[a - len(nl):a] == nl else a
    out = out[:cut_a] + out[b:]
ins = ''.join(nl + new_blocks[f] for f in sorted(new_blocks))
pos = first - len(nl) if t[first - len(nl):first] == nl else first
# position in the shortened text: everything before `first` that was removed is nothing (first is the earliest old block)
out = out[:pos] + ins + out[pos:]
assert out.count('(') == out.count(')')
open(TOP, 'w', encoding='utf8', newline='').write(out)
print('sheet symbols now:', re.findall(r'\(property "Sheetname" "([^"]*)"', out))
