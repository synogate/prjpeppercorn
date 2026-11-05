"""Example work package (template): COUTX routing multiplexer on COMP_OUT with two INIT_L30 values, read in the east neighbour.
A real package copies this structure.  Dry run:  python wp_runner.py wp_example --dry"""
import sys, os
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_common import ENV, EAST_CINX, model_vectors, explain, helper

SIGNAL = "COUTX"       # the output of cpe.v that the reader sees


def configs():
    cfgs = []
    for l30 in ("0110", "0100"):
        cfgs.append({"name": "ex_route_comp_l%s" % l30, "reader": "east_CINX",
                     "words": dict(ENV, C_FUNCTION="000", C_CX_I="1", C_SEL_C="1", C_SELX="0", INIT_L30=l30),
                     "meta": {"l30": l30}})
    return cfgs


def _cp(cfg):
    return helper(cfg.get("helper", "default"))[1]


def model_F(cfg):
    return model_vectors(cfg["words"], [SIGNAL], _cp(cfg))[SIGNAL]


def analyze(records):
    bad = 0
    for r in records:
        m = model_F(r["cfg"])
        d = int((m != r["F"]).sum())
        bad += d > 0
        print("%-28s differing states vs cpe.v: %d" % (r["cfg"]["name"], d))
    print("configs with deviations:", bad, "of", len(records))
    return {"deviations": bad, "configs": len(records)}
