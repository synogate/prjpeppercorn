"""MULTO2 (C_FUNCTION = 3, C_HORIZ = 0, C_CX_I = 0: COUTX = MULTO2 by the S17 result) with four settings of the south helper that give CINY1 / CINY2 / PINY2 different counter bits.
    python mult_test.py   ->  hw_data/s19.jsonl"""
import sys, os, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from east import measure_east
from map_coutx import ENV, CPX, CPYP
from suites import OUT
out = open(os.path.join(OUT, "s19.jsonl"), "a")
words = dict(ENV, C_FUNCTION="011", C_HORIZ="0", C_CX_I="0")
# helper variants: (CINY1, CINY2, PINY2) = default (x14, x13, x14), sely1 (x13, x13, x14), sely2 (x14, x14, x13), both (x13, x14, x13)
for name, hx in (("v_default", {}), ("v_sely1", {"C_SELY1": "1"}), ("v_sely2", {"C_SELY2": "1"}), ("v_both", {"C_SELY1": "1", "C_SELY2": "1"})):
    F, info = measure_east("s19_" + name, words, CPX, dict(CPYP, **hx))
    out.write(json.dumps({"name": name, "helper": hx, "words": words, "F": format(sum(b << i for i, b in enumerate(F)), "x")}) + chr(10))
    print(name, info.get("unsure_states"), flush=True)
