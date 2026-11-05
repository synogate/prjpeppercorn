"""Rebuild the eight C_FUNCTION sub sheets of the CPE from cpe.kicad_sch.

Usage (from sim/):  python build_function_sheets.py [--dry]

For every C_FUNCTION 0..7 the sheet file below is replaced by a constant-folded copy of ../cpe.kicad_sch (fold_sheet.py).
Everything the old sheet file contained is dropped except its function description texts ("C_FUNCTION = n: ..." and the
multiplier note of the ADDF2 sheet); they are placed beside the diagram, to the right of it (outside the page, which keeps the A3 size of the top sheet).
The old files are overwritten: keep a copy of them (git has the committed versions) before running without --dry.
"""
import os, re, subprocess, sys, tempfile, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.join(HERE, '..', 'cpe.kicad_sch')
FILES = {0: 'cpe_comb', 1: 'cpe_comb_addf', 2: 'cpe_comb_addf2', 3: 'cpe_comb_mult',
         4: 'cpe_comb_mux4', 5: 'cpe_comb_en_cin', 6: 'cpe_comb_concat', 7: 'cpe_comb_addcin'}
DRY = '--dry' in sys.argv
TEXT_X = 424.0          # right of the A3 sheet (420 mm wide)


def end_of(t, i):
    depth = 0
    k = i
    while True:
        c = t[k]
        if c == '"':
            k += 1
            while t[k] != '"':
                if t[k] == chr(92):
                    k += 1
                k += 1
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return k + 1
        k += 1


def description_texts(path):
    """raw (text ...) blocks of the sheet that describe the function"""
    t = open(path, encoding='utf8', newline='').read().replace('\r\n', '\n')
    out = []
    for m in re.finditer(r'\n\t\(text "', t):
        a = m.start() + 2
        b = end_of(t, a)
        blk = t[a:b]
        s = re.match(r'\(text "((?:[^"\\]|\\.)*)"', blk).group(1)
        if s.startswith('C_FUNCTION = ') or s.startswith('In multiplier mode'):
            out.append((s, blk))
    return out


def place(blk, x, y):
    blk = re.sub(r'\(at [-\d.]+ [-\d.]+ [-\d.]+\)', '(at %s %s 0)' % (('%.2f' % x).rstrip('0').rstrip('.'), ('%.2f' % y).rstrip('0').rstrip('.')), blk, count=1)
    if '(justify' in blk:
        blk = re.sub(r'\(justify [^)]*\)', '(justify left top)', blk, count=1)
    else:
        blk = re.sub(r'(\(effects\s*\(font\s*\(size [\d. ]+\)\s*\))', r'\1\n\t\t\t(justify left top)', blk, count=1)
    return re.sub(r'\(uuid "[^"]*"\)', '(uuid "%s")' % uuid.uuid4(), blk)


for f, name in FILES.items():
    dst = os.path.join(HERE, '..', name + '.kicad_sch')
    if not os.path.exists(dst):
        print('missing', dst)
        continue
    texts = description_texts(dst)
    tmp = os.path.join(tempfile.mkdtemp(), 'f%d.kicad_sch' % f)
    r = subprocess.run([sys.executable, 'fold_sheet.py', str(f), TOP, tmp], cwd=HERE, capture_output=True, text=True)
    if r.returncode:
        print('fold failed for', f, r.stderr[-300:])
        sys.exit(1)
    s = open(tmp, encoding='utf8', newline='').read()
    texts = [(txt, blk) for txt, blk in texts if '(text "' + txt + '"' not in s]      # the folded sheet may already carry it (the multiplier note of the top sheet at C_FUNCTION=3)
    if texts:
        y = 12.0
        add = []
        width = 0.0
        for txt, blk in texts:
            size = float(re.search(r'\(size ([\d.]+) ', blk).group(1))
            lines = txt.replace(chr(92) + 'n', chr(10)).split(chr(10))
            width = max(width, max(len(l) for l in lines) * 0.9 * size)          # ~0.83 .. 0.9 mm per character and mm of font size
            add.append(chr(9) + place(blk, TEXT_X, y))
            y += len(lines) * 1.75 * size + 8.0
        k = s.index(chr(9) + '(sheet_instances')
        s = s[:k] + chr(10).join(add) + chr(10) + s[k:]
        # the page keeps the paper size of the top sheet (all sheets equally large for A/B comparison); the texts lie outside of it
    print('f%d -> %s: %d description text(s), %d bytes' % (f, name + '.kicad_sch', len(texts), len(s)))
    if not DRY:
        open(dst, 'w', encoding='utf8', newline='\n').write(s)
