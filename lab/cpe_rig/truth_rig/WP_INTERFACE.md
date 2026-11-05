# Measurement work packages (WP) - interface and rig facts

A work package is one Python module `wp_<name>.py` in this folder. The runner `wp_runner.py` measures / dry-runs it, `wp_common.py` has the model helpers, `wp_example.py` is a working template
(`python wp_runner.py wp_example --dry`). **Read `wp_example.py`, `wp_common.py`, `wp_runner.py` first.**

## Rules for the author of a package (no hardware!)
* **Never touch the hardware.** There is one scope and one board; only the lab owner measures. Do not call `load`, `capture`, `measure`, `measure_raw`, `measure_east`, `wp_runner.measure`, `openFPGALoader`,
  `gmpack`, or run `wp_runner.py` without `--dry` / `--list` / `--analyze`. Only `cpe.v` simulation (`iverilog`, via `wp_common.model_vectors`) is allowed.
* Create **only** your own `wp_<name>.py` (and, if needed, scratch files under your own name). Do not edit `cpe.v`, `meas.py`, `east.py`, `suites.py`, `map_*.py`, `wp_*.py` of others, `hw_measurements.md`, the schematic.
  No git commits. Use `python -I`-free normal python (`sys.dont_write_bytecode = True` is set by the helpers).
* Keep a package to **at most about 120 configurations** (one hardware measurement = 5-8 s). Prefer informative configurations (random LUT trees, asymmetric INITs, several helper variants) over exhaustive grids.
* Deliver: the module, a passing `python wp_runner.py wp_<name> --dry` (it must report 0 deviations), a test of `analyze()` against a *perturbed* model (it must notice a deliberately wrong vector), and a short report.

## The module
```python
def configs() -> list[dict]          # each: name (unique str), reader, words {str: str}, optional cpinx / cpiny {str: str}, optional extra {(x, y, word): str|None}, optional helper (key of wp_common.HELPER_VARIANTS), meta
def model_F(cfg) -> np.ndarray       # uint8, 2**17 states: what cpe.v predicts that the reader sees
def analyze(records) -> dict         # records: [{"cfg": cfg, "F": uint8 array, "info": ...}]; print a table: per config the differing states vs the model;
                                     # for deviating configs a *diagnosis* (which candidate source / which bits F depends on / how it differs); return a summary dict
```
* `reader` (what is observed): `sel_OUT1` / `sel_OUT2` = OUT1 / OUT2 wire of the DUT through the selector; `east_CINX` = COUTX of the DUT (selector patched into a reader of its CINX); `east_PINX` = POUTX of the DUT (read as PINX).
  The east readers use the selector, so OUT1 / OUT2 of the same configuration cannot be seen at the same time; each config has one reader.
* `words` = config words of the DUT (CPE X146Y19), bitfile names and bit-string values exactly as in `hw_measurements.md` (`'C_FUNCTION': '011'`, `'INIT_L30': '0110'`, `'C_CX_I': '1'`). Words not given are 0. nextpnr's own words of the DUT are deleted.
* `cpinx` / `cpiny` = words of the west / south helper CPE (default `CPX` / `CPYP`, see below). `extra` = words for any other CPE `(x, y, word)`; only CPEs that are not used by the design may be patched
  (find free ones by reading the base bitfile `<tmp>/cpe_rig_work/truth/bitfile.txt` read-only; `meas.base_words(x, y)` lists the words nextpnr wrote for a CPE: none = free, and the counter flops sit in some CPEs!).
* `model_F`: `wp_common.model_vectors(words, [signal], cp)[signal]`; `cp` maps the CP inputs to the counter bit they carry (`wp_common.helper(variant)[1]`).
  Any wire or output of `cpe.v` can be used as signal (`COUTX`, `COUTY1`, `POUTX`, `OUT1`, `comp_out`, `carry_generate`, `carry_propagate`, `multo1`, `multo2`, `cx_route`, `px_route`, `cy1_route`, ... see the file).
  Which signal the reader sees: `sel_OUT1` -> `OUT1`, `sel_OUT2` -> `OUT2`, `east_CINX` -> `COUTX`, `east_PINX` -> `POUTX`.

## Rig facts
* States: 17 orthogonal counter bits x0..x16, F[s] = value for state s = bit pattern (x_k = bit k of s), 2**17 entries. The DUT sees: IN1..IN8 = x0..x7, CLK = x8, EN = x9, SR = x10 (all direct), CINX = x11, PINX = x12 (west helper),
  CINY1, CINY2, PINY1, PINY2 = x13 / x14 (south helper, which one depends on its settings), x15, x16 = helper inputs only.
* `wp_common.ENV` (= `map_coutx.ENV`): pass-through LUTs `INIT_L00 = INIT_L01 = INIT_L02 = INIT_L03 = 1010` (pass D0), `INIT_L10 = INIT_L11 = INIT_L20 = 1100` (pass D1): l00 = x0, l01 = x2, l02 = x4, l03 = x6, l10 = x2, l11 = x6;
  `INIT_L30 = 0110`; OUT1 = x7 (`C_BR = 1`, `C_SN = 111`, `C_O1 = 01`: MUXOUT of IN8), OUT2 = ~x7 (`C_O2 = 00`, `C_L_D = 1`, `C_CPE_CLK = C_CPE_EN = C_CPE_RES = C_CPE_SET = 11`, `C_2D_IN = 1`: transparent latch on inverted MUXOUT).
  Override `C_O1` / `C_O2` if a package wants OUT1 / OUT2 to show something else (e.g. `10` = CPOUT).
* West helper `CPX` (X145Y19): COUTX = OUT1 = x11 (CINX of the DUT), POUTX = OUT2 = x12 (PINX of the DUT). South helper `CPYP` (X146Y18): `C_CY1_I = C_CY2_I = C_PY1_I = C_PY2_I = 1`, OUT1 = x13, OUT2 = x14; default
  CINY1 = x14 (COUTY1 = OUT2), CINY2 = x13 (COUTY2 = OUT1), PINY1 = x13 (POUTY1 = OUT1), PINY2 = x14 (POUTY2 = OUT2). `wp_common.HELPER_VARIANTS` has the four settings (`default`, `sely1`, `sely2`, `both`) with the matching model mapping.
* Observability: COUTX / POUTX through `east_CINX` / `east_PINX` for any `C_HORIZ`, `C_MULT`. COUTY1 / POUTY1 only through CPOUT (`cp_use_x = C_HORIZ | C_MULT`; with 0 CPOUT carry = COUTY1, prop = POUTY1;
  `cpout1 = C_C_P ? carry : prop`, `cpout2 = C_C_P ? prop : carry`; `C_O1 = 10` / `C_O2 = 10` puts CPOUT on OUT1 / OUT2, which is then read by `sel_OUT1` / `sel_OUT2`); not visible: COUTY1 / POUTY1 at `C_HORIZ = 1` or `C_MULT = 1`.
  COUTY2 / POUTY2 of the DUT are not visible; those of the south helper are visible at the DUT as CINY2 / PINY2 (DUT words as in S15: `C_HORIZ = 1`, `C_CX_I = 1`, `C_PX_I = 1`, `C_SEL_C = C_SEL_P = C_SELX = 1`, `C_Y12 = 1`, `C_O2 = 10`,
  `C_C_P = 0` reads CINY2 via COUTX, `1` reads PINY2 via POUTX, reader `sel_OUT2`).
* Which model signal is the "truth": `cpe.v` is the current best model, validated by the measurements in `schematics/cpe/sim/hw_measurements.md` (findings 1-33; read the sections S17 .. S23 and "Model and schematic status").
  A package tests the *open* cases listed in its brief; a deviation found later is a result, not an error.
* A measurement can show unreliable states only if the signal changes faster than the sampling allows; nothing to do for the author. Constant outputs are fine.
