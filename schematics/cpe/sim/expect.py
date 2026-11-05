"""Expected CPE outputs from cpe.v for a given configuration and input vector (runs iverilog).

For test plans (hw_test_plan.md): configuration words are given the way the hardware rig patches them (bitfile.txt names and values),
so that the expected value of a measurement can be computed with the same dictionary.

    python expect.py C_FUNCTION=001 C_HORIZ=1 INIT_L10=1111 -- IN7=1 CINX=1      # one row
    python expect.py C_CX_I=1 -- IN7=0,1 CINX=0,1                                 # all combinations of the listed values

Library:  from expect import expect;  rows = expect({'C_CX_I': '1', 'C_SELX': '1'}, [{'IN7': 0}, {'IN7': 1}])

Conventions
* Words are bitstring values as in bitfile.txt ('001', '0110') or integers. Words not given are 0, like in an unpatched bitstream.
* Hardware polarity of C_RAM_I1/2: in the hardware (nextpnr configuration) 0 selects the output multiplexer, cpe.v has it the other way round
  (schematic). expect() inverts these two words (absent -> 1 in the model), so a hardware word set can be passed unchanged.
* Unconnected IN1..IN8 read 1 on the hardware (measured for IN1); inputs that are not given default to `default_in` (1 for IN1..IN8, 0 for the carry /
  propagate / RAM inputs and CLK, EN, SR).
* Registers start in an undefined state; outputs that depend on them (C_O1/C_O2 = 0) are returned as 'x'.
"""
import os, re, subprocess, sys, itertools, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = ["IN1", "IN2", "IN3", "IN4", "IN5", "IN6", "IN7", "IN8", "CLK", "EN", "SR", "CINX", "CINY1", "CINY2", "PINX", "PINY1", "PINY2", "RAM_I1", "RAM_I2"]
OUTPUTS = ["OUT1", "OUT2", "RAM_O1", "RAM_O2", "COUTX", "COUTY1", "COUTY2", "POUTX", "POUTY1", "POUTY2"]
WIDTH = {"C_FUNCTION": 3, "C_SN": 3, "C_O1": 2, "C_O2": 2, "C_CPE_CLK": 2, "C_CPE_EN": 2, "C_CPE_RES": 2, "C_CPE_SET": 2}
for _w in ("INIT_L00", "INIT_L01", "INIT_L02", "INIT_L03", "INIT_L10", "INIT_L11", "INIT_L20", "INIT_L30"):
    WIDTH[_w] = 4


def _literal(word, value):
    w = WIDTH.get(word, 1)
    if isinstance(value, str):
        return "%d'b%s" % (len(value), value)
    return "%d'd%d" % (w, value)


def expect(words, rows, default_in=1, iverilog="iverilog", vvp="vvp"):
    """words: {name: '0110' | int}; rows: list of {input: 0|1}; returns a list of {output: '0' | '1' | 'x'} (same order)."""
    words = dict(words)
    for k in ("C_RAM_I1", "C_RAM_I2"):
        v = words.get(k, "0")
        words[k] = "0" if str(v) in ("1", "1'b1") else "1"
    params = ", ".join(".%s(%s)" % (k, _literal(k, v)) for k, v in words.items())
    lines = ["module tb_expect;", "  reg " + ", ".join(INPUTS) + ";", "  wire " + ", ".join(OUTPUTS) + ";",
             "  cpe #(%s) u (%s);" % (params, ", ".join(".%s(%s)" % (p, p) for p in INPUTS + OUTPUTS)), "  initial begin"]
    for row in rows:
        for p in INPUTS:
            default = default_in if p.startswith("IN") and p[2:].isdigit() else 0
            lines.append("    %s = %d;" % (p, row.get(p, default)))
        lines.append("    #1;")
        lines.append('    $display("ROW %s", {%s});' % ("%b" * len(OUTPUTS), ", ".join(OUTPUTS)))
    lines += ["    $finish;", "  end", "endmodule"]
    with tempfile.TemporaryDirectory() as tmp:
        tb, vvp_file = os.path.join(tmp, "tb.v"), os.path.join(tmp, "tb.vvp")
        open(tb, "w").write("\n".join(lines))
        subprocess.run([iverilog, "-g2012", "-o", vvp_file, tb, os.path.join(HERE, "cpe.v")], check=True, capture_output=True)
        out = subprocess.run([vvp, vvp_file], check=True, capture_output=True, text=True).stdout
    result = []
    for l in out.splitlines():
        if l.startswith("ROW "):
            bits = l[4:].strip()
            result.append(dict(zip(OUTPUTS, bits)))
    assert len(result) == len(rows), out
    return result


def main(argv):
    if "--" in argv:
        i = argv.index("--")
        wargs, iargs = argv[:i], argv[i + 1:]
    else:
        wargs, iargs = argv, []
    words = dict(a.split("=") for a in wargs)
    vary = {}
    for a in iargs:
        k, v = a.split("=")
        vary[k] = [int(x) for x in v.split(",")]
    keys = list(vary)
    rows = [dict(zip(keys, c)) for c in itertools.product(*[vary[k] for k in keys])] or [{}]
    res = expect(words, rows)
    print(" ".join(keys), "->", " ".join(OUTPUTS))
    for r, o in zip(rows, res):
        print(" ".join(str(r[k]) for k in keys), "->", " ".join("%s=%s" % (n, o[n]) for n in OUTPUTS))


if __name__ == "__main__":
    main(sys.argv[1:])
