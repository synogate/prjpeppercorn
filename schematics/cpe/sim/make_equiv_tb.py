"""Random equivalence test: hand-written cpe.v against the generated cpe_generated.v (module cpe_ref)."""
import random, sys
random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
N = int(sys.argv[2]) if len(sys.argv) > 2 else 400
bit1 = ['C_I1','C_I2','C_I3','C_I4','C_HORIZ','C_COMP','C_COMP_I','C_SELX','C_SELY1','C_SELY2','C_SEL_C','C_SEL_P','C_Y12',
        'C_CX_I','C_CY1_I','C_CY2_I','C_PX_I','C_PY1_I','C_PY2_I','C_C_P','C_CLKSEL','C_ENSEL','C_EN_SR','C_L_D','C_BR','C_2D_IN',
        'C_RAM_I1','C_RAM_I2','C_RAM_O1','C_RAM_O2']
init4 = ['INIT_L00','INIT_L01','INIT_L02','INIT_L03','INIT_L10','INIT_L11','INIT_L20','INIT_L30']
vec2 = ['C_CPE_CLK','C_CPE_EN','C_CPE_RES','C_CPE_SET','C_O1','C_O2']
ins = ['IN1','IN2','IN3','IN4','IN5','IN6','IN7','IN8','CLK','EN','SR','CINX','CINY1','CINY2','PINX','PINY1','PINY2','RAM_I1','RAM_I2']
outs = ['OUT1','OUT2','RAM_O1','RAM_O2','COUTX','COUTY1','COUTY2','POUTX','POUTY1','POUTY2']
o = []
o.append('module tb_equiv;')
o.append('  reg [%d:0] stim;' % (len(ins) - 1))
for k in range(N):
    fn = random.randrange(8)
    # avoid combinational CPOUT feedback loops dominating: allow, but rarely
    p = {}
    for b in bit1: p[b] = random.randrange(2)
    for b in init4: p[b] = random.randrange(16)
    for b in vec2: p[b] = random.randrange(4)
    if True:
        p['C_O1'] = random.choice([0, 1, 3]); p['C_O2'] = random.choice([0, 1, 3])
    p['C_SN'] = random.randrange(8)
    if p['C_L_D'] and p['C_BR']: p['C_BR'] = 0   # latch D from MUXOUT would race with EN/SR closing it
    if p['C_L_D']: p['C_EN_SR'] = 1              # latch set from EN would race with the latch enable (both change with EN)
    ref = ', '.join('.%s(%d)' % (a, v) for a, v in p.items()) + ', .C_FUNCTION(%d)' % fn
    new = ref
    pins = lambda tag: ', '.join('.%s(%s)' % (i, 'stim[%d]' % j) for j, i in enumerate(ins)) + ', ' + ', '.join('.%s(%s_%s%d)' % (x, 'r' if tag == 'r' else 'n', x, k) for x in outs)
    for x in outs:
        o.append('  wire r_%s%d, n_%s%d;' % (x, k, x, k))
    o.append('  cpe_ref #(%s) ref%d (%s);' % (ref, k, pins('r')))
    o.append('  cpe     #(%s) new%d (%s);' % (new, k, pins('n')))
o.append('  integer step, errors = 0, xdiff = 0; reg clkq = 0; reg [31:0] rnd;')
o.append('  task check(input integer k, input [255:0] name, input a, input b);')
o.append('    if (step >= 3 && a !== b) begin')
o.append('      if ((^{a, b}) === 1'+"'"+'bx) xdiff = xdiff + 1;  // power-up state of a register is undefined; counted separately')
o.append('      else begin errors = errors + 1; $display("MISMATCH cfg %0d %0s ref=%b new=%b stim=%b", k, name, a, b, stim); end')
o.append('    end')
o.append('  endtask')
o.append('  initial begin')
o.append('    stim = 0; #5;')
o.append('    for (step = 0; step < 80; step = step + 1) begin')
o.append('      rnd = $random; stim[7:0] = rnd[7:0]; stim[12:11] = rnd[12:11]; stim[15:14] = rnd[15:14]; stim[18:17] = rnd[18:17]; #2; stim[9] = rnd[9]; #2; stim[10] = rnd[10]; #2; stim[16] = rnd[16]; #2; stim[13] = rnd[13]; #2; clkq = ~clkq; stim[8] = clkq; #3;')
for k in range(N):
    for x in outs:
        o.append('      check(%d, "%s", r_%s%d, n_%s%d);' % (k, x, x, k, x, k))
o.append('    end')
o.append('    $display("equivalence: %0d configs, %0d mismatches, %0d X-only differences", ' + str(N) + ', errors, xdiff);')
o.append('    $finish;')
o.append('  end')
o.append('endmodule')
NL = chr(10)
open('tb_equiv.v', 'w').write(NL.join(o) + NL)
