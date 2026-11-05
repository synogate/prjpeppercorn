"""check_fold.py <F> <folded.kicad_sch> <seed> <N>: simulate the folded sheet's model against cpe_ref (cpe_generated.v, the full schematic) with C_FUNCTION=F.
Run gen.py on ../cpe.kicad_sch first.  Example:  python check_fold.py 2 ../cpe_comb_addf2.kicad_sch 1 100"""
import sys, re, subprocess, os
F, SHEET, SEED, N = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
import tempfile
tmpv = os.path.join(tempfile.mkdtemp(), 'f%d_model.v' % F)
r = subprocess.run([sys.executable, 'gen.py', SHEET, tmpv, 'cpe_fold'], capture_output=True, text=True)
info = [l for l in r.stdout.splitlines() if l.startswith(('multi-driver', 'undriven', 'UNHANDLED', 'notes'))]
src = open(tmpv).read()
params = set(re.findall(r'parameter\s+(?:\[[^\]]*\]\s*)?(\w+)\s*=', src))
code = open('make_equiv_tb.py').read()
code = code.replace('fn = random.randrange(8)', 'fn = %d' % F)
code = code.replace('    new = ref\n', "    new = ', '.join('.%s(%d)' % (a, v) for a, v in p.items() if a in NEWP)\n")
code = code.replace("o.append('  cpe     #(%s) new%d (%s);' % (new, k, pins('n')))", "o.append('  cpe_fold #(%s) new%d (%s);' % (new, k, pins('n')))")
sys.argv = ['x', SEED, N]
NEWP = params
exec(compile(code, 'make_fold_tb', 'exec'))
subprocess.run(['iverilog', '-g2012', '-o', 'fold.vvp', 'tb_equiv.v', 'cpe_generated.v', tmpv, 'cpe_prims.v'], check=False, capture_output=True)
ve = subprocess.run(['iverilog', '-g2012', '-o', 'fold.vvp', 'tb_equiv.v', 'cpe_generated.v', tmpv, 'cpe_prims.v'], capture_output=True, text=True)
if ve.returncode: print(ve.stderr[:400]); sys.exit(1)
out = subprocess.run(['vvp', 'fold.vvp'], capture_output=True, text=True).stdout
res = [l for l in out.splitlines() if l.startswith('equivalence')]
print('f%d: C_FUNCTION param kept: %s; %s | %s' % (F, 'C_FUNCTION' in params, res[0] if res else out[-300:], ' '.join(i[:80] for i in info)))
