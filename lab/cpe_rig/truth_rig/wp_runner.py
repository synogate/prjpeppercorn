"""Runner for measurement work packages (WP).  A work package is a module  wp_<name>.py  next to this file with
    configs()           -> list of config dicts (see WP_INTERFACE.md)
    model_F(cfg)        -> numpy uint8 array of 2**17 values: what cpe.v predicts for cfg (used by the dry run and by analyze())
    analyze(records)    -> prints a report and returns a dict; records = list of {"cfg": cfg, "F": numpy uint8 array}

    python wp_runner.py wp_name --dry            # no hardware: F := model_F(cfg); runs analyze() on it (must report 0 deviations)
    python wp_runner.py wp_name --list           # print the configs
    python wp_runner.py wp_name                  # MEASURE on the hardware (scope + board; only the owner of the lab does this)
    python wp_runner.py wp_name --analyze        # run analyze() on the stored measurement data  hw_data/wp_name.jsonl
"""
import sys, os, json, importlib
import numpy as np
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tt_rig import REPO, N
OUT = os.path.join(REPO, "schematics", "cpe", "sim", "hw_data")
NS = 1 << N
READERS = ("sel_OUT1", "sel_OUT2", "east_CINX", "east_PINX")


def check(cfgs):
    seen = set()
    for c in cfgs:
        assert isinstance(c["name"], str) and c["name"] not in seen, "name missing or duplicate: %r" % c.get("name")
        seen.add(c["name"])
        assert c["reader"] in READERS, "reader must be one of %s (%s)" % (READERS, c["name"])
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in c["words"].items()), "words must be {str: str} (%s)" % c["name"]
        for k in ("cpinx", "cpiny"):
            if c.get(k) is not None:
                assert all(isinstance(a, str) and isinstance(b, str) for a, b in c[k].items()), k
        for key in c.get("extra", {}):
            assert len(key) == 3 and isinstance(key[0], int) and isinstance(key[1], int), "extra keys are (x, y, word)"


def to_hex(F):
    return format(sum(int(b) << i for i, b in enumerate(F)), "x")


def from_hex(h):
    v = int(h, 16)
    return np.array([(v >> s) & 1 for s in range(NS)], dtype=np.uint8)


def measure(cfg):
    """one hardware measurement; -> F (list of 2**17 ints)"""
    from meas import measure_raw
    from east import measure_east, EAST_CINX
    from map_poutx import EAST_PINX
    from map_coutx import CPX, CPYP
    cpinx = cfg["cpinx"] if cfg.get("cpinx") is not None else CPX
    cpiny = cfg["cpiny"] if cfg.get("cpiny") is not None else CPYP
    extra = cfg.get("extra")
    r = cfg["reader"]
    if r.startswith("sel_"):
        F, info = measure_raw("wp_" + cfg["name"], cfg["words"], cpinx, cpiny, r[4:], extra)
    else:
        F, info = measure_east("wp_" + cfg["name"], cfg["words"], cpinx, cpiny, EAST_CINX if r == "east_CINX" else EAST_PINX, extra)
    return F, info


def jsonable(cfg):
    c = dict(cfg)
    if "extra" in c:
        c["extra"] = [[k[0], k[1], k[2], v] for k, v in c["extra"].items()]
    return c


def unjson(cfg):
    c = dict(cfg)
    if "extra" in c:
        c["extra"] = {(a, b, w): v for a, b, w, v in c["extra"]}
    return c


def main(argv):
    name = argv[0]
    mod = importlib.import_module(name)
    cfgs = mod.configs()
    check(cfgs)
    if "--list" in argv:
        for c in cfgs:
            print(c["name"], c["reader"], c["words"], "cpiny=%s" % c.get("cpiny"), "extra=%s" % c.get("extra"))
        print(len(cfgs), "configs")
        return
    if "--analyze" in argv:
        path = os.path.join(OUT, name + ".jsonl")
        recs = []
        for l in open(path):
            d = json.loads(l)
            recs.append({"cfg": unjson(d["cfg"]), "F": from_hex(d["F"]), "info": d.get("info")})
        mod.analyze(recs)
        return
    dry = "--dry" in argv
    path = os.path.join(OUT, name + ("_dry" if dry else "") + ".jsonl")
    if dry and os.path.exists(path):
        os.remove(path)
    done = {json.loads(l)["cfg"]["name"] for l in open(path)} if os.path.exists(path) else set()
    recs = []
    for c in cfgs:
        if c["name"] in done:
            continue
        if dry:
            F, info = np.asarray(mod.model_F(c), dtype=np.uint8), {"dry": True}
        else:
            F, info = measure(c)
            if F is None:
                print(c["name"], "NO CAPTURE", info, flush=True)
                continue
        open(path, "a").write(json.dumps({"cfg": jsonable(c), "F": to_hex(F), "info": info}) + chr(10))
        recs.append({"cfg": c, "F": np.asarray(F, dtype=np.uint8), "info": info})
        print(c["name"], "ok" if not dry else "dry", flush=True)
    if dry:
        mod.analyze(recs)


if __name__ == "__main__":
    main(sys.argv[1:])
