# CPE simulation model

`cpe.v` is a hand-written Verilog model of one CPE, after `../cpe.kicad_sch`. All config bits and LUT
truth tables are module parameters named like in the libgm bit database. `C_FUNCTION` is a 3-bit parameter; the
signals the schematic decodes from it (`C_MULT`, `C_MX4`, `C_EN_CIN`, `C_ADDF`, `C_ADDF2`,
`C_ADDCIN`) are derived wires, not separate bits. `NOTE` comments in the file mark places where the schematic and nextpnr / `die.py` disagree.

`cpe.v` is plain Verilog-1995 (checked with `iverilog -g1995 -t null cpe.v`): no ANSI ports, no `always @*`
(sensitivity lists are written out and must stay complete when the file is edited), no declaration initialisers.

    iverilog -g2012 -o bridge.vvp tb_bridge.v cpe.v && vvp bridge.vvp

## Cross-check against the schematic

`gen.py` (with `kisch.py`, `netlist.py`) extracts the connectivity directly from `cpe.kicad_sch` and
writes a flat, unreadable but mechanical model `cpe_generated.v` (module `cpe_ref`, with `C_FUNCTION`):

    python gen.py ../cpe.kicad_sch cpe_generated.v cpe_ref

`make_equiv_tb.py` writes `tb_equiv.v`, which simulates `cpe` and `cpe_ref` side by side with random
configurations and stimulus and compares all outputs. Run it after every change to `cpe.v` or the schematic. Last run: 15 seeds x 100 random configurations, no mismatch.
Register power-up state is undefined, so differences that are X on one side are only counted, not reported as errors.
The random stimulus changes inputs in separate steps (data, EN, SR, PINY2, CINY2, then CLK) and avoids a few
configurations whose result depends on delta-cycle order (latch with set from EN, latch fed by the 8:1 mux,
`C_O1/C_O2` = CPOUT, which closes a combinational loop through the carry/propagate lines):

    python make_equiv_tb.py <seed> <configs>
    iverilog -g2012 -o equiv.vvp tb_equiv.v cpe.v cpe_generated.v cpe_prims.v && vvp equiv.vvp

(`kicad-cli ... export netlist` is not usable: it drops the pins of gate symbols.)

## Reading the schematic (assumptions)

- Config bit names are the texts next to the symbols (nearest `C_*` text), not symbol fields.
- `MUX2`/`MUX2B` Y = S ? D1 : D0; `MUX4` index {S1,S0}; `MUX8` index {S2,S1,S0}; `LUT2` INIT[{D1,D0}]; `LUT1` INIT[D].
- `AO21` is drawn as OR(pair) into AND(top), `OA21` as AND(pair) into OR(top): the names are the wrong way round.
- `C_MULT` and `C_ADDF` outputs of the `C_FUNCTION` symbol are not wired to their labels in the schematic.
- Labels `CLK` and `EN` after the LUT1s are internal nets, not the ports.
- The unlabelled `LUT2` at (129.5, 105.4) is `INIT_L30` (guess, matches libgm).
- The flops' S / R pins are active low (bubble on the symbols); the rest of the set / reset behaviour (reset wins) is a guess, see hw_measurements.md finding 6.

## Findings so far (schematic vs. nextpnr / die.py)

The schematic changed after the first `die.py` versions (5a43fa5, ba1eca1 "fix C/P line errata caused by misunderstanding
inversion", Jan 2026). The polarity findings below compare the schematic at HEAD with `die.py` / nextpnr at HEAD; they
still need a check on real hardware.


- `C_RAMI1/2`: schematic selects `RAM_I` at 0; nextpnr sets `C_RAM_I`=1 only when `RAM_I` is used.
- `C_CY2_I`, `C_PY1_I`, `C_PY2_I`: schematic passes `CINY*/PINY*` at 1 (`PY2`: `C_PY2_I OR C_MULT`);
  `die.py` has the pass-through at 0. Not measured yet. (`C_CY1_I` is corrected, see "Hardware measurements".)
- MUX invert/mask: schematic text says `C = L10, X = L11` for MX4a; nextpnr has invert in `INIT_L11`, select in `INIT_L10`.
- 8:1 mux select terms: as drawn, they read `CINY1` / `PINY1`, the registers `CINY2` / `PINY2`. Commit 5a43fa5
  ("fix C_CLKSEL/C_ENSEL input") relabelled only the register side. `cpe.v` models it as drawn. Untested on hardware;
  nextpnr's MX8 was derived from the schematic, so it is no reference for this.
- `CPOUT1/2` are muxes of `COUT*`/`POUT*` (`C_C_P`, `C_HORIZ`, `C_MULT`) in the schematic; the router has no pips for that.
- The register input mux has a fourth input, inverted `MUXOUT` (`C_BR`=1, `C_2D_IN`=1), which `die.py` does not have.

## Hardware measurements

`COUTY1` of an adder CPE (`C_FUNCTION=1`, `C_HORIZ=0`), measured with `CC_ADDF` as nextpnr packs it and with single LUT words
changed in the bitstream (11 variants, plus `C_CY1_I=1`; lab test `lab/adder_f1`, 2026-11-03):

    COUTY1 = (~C_CY1_I & (L10 ^ L11)) ? CINY1 : (L00 | L01)

`cpe.kicad_sch` and `cpe.v` now follow this: generate is `L00 | L01` (was `(L00|L01) & L02`, constant 0 with nextpnr's `INIT_L02=0`), the
`COUTY1` select is `~(C_CY1_I | (cy1_adder & CADD_S))` (it was `(CADD_S | cy1_adder) & C_CY1_I`). `CADD_S` itself is still drawn as XNOR / NAND:
it also drives `COUTX`, which is not measured, and a plain XOR there would break the pass-through of routing CPEs (all LUTs 0).
In the schematic the select is `NOT(OA21(CADD_S, cy1_adder | C_CY1_I))`; the final `MUX2` keeps `D1 = CINY1`.

`cpe.v` (but not yet the schematic) also follows the `COUTX` measurements of `hw_measurements.md` (M10 ... M14): `coutx_chain = ~(C_CX_I | (C_ADDF & C_HORIZ & CADD_S))`
and `COMP_OUT` inverted on `COUTX`. `tb_coutx.v` checks 142 measured configurations (`iverilog -g2012 -o coutx.vvp tb_coutx.v cpe.v && vvp coutx.vvp`). Until the schematic is
updated, `make_equiv_tb.py` reports differences on `COUTX` between `cpe.v` and `cpe_generated.v`.

Not reproduced: `C_HORIZ=1` (measured `COUTY1 = CINY1 | (A & B)` with B on `CINX`), `C_FUNCTION=2` (`ADDF2`), and everything on `COUTX`.

## Tests

- `tb_adder.v`: 12 cases of the adder CPE with the results measured on hardware (baseline, 10 changed LUT words, `C_CY1_I=1`).
  `iverilog -g2012 -o adder.vvp tb_adder.v cpe.v && vvp adder.vvp` -> `adder test: all 12 hardware cases match`.
- `tb_bridge.v`: the 8:1 mux as routing resource in an otherwise unused CPE (`C_SN=k`, `C_O1=1`,
  `C_RAM_I1=1`, everything else 0): `OUT1 = IN(k+1)` for k = 0..7, independent of CLK/EN/SR.

## Folded sheets for one C_FUNCTION

`fold_sheet.py` copies `cpe.kicad_sch` and folds the constants a fixed `C_FUNCTION` implies (`C_MULT`, `C_MX4`, `C_EN_CIN`,
`C_ADDF`, `C_ADDF2`, `C_ADDCIN`): constant gates and pass-through gates (AND with 1, OR with 0, MUX with constant select, ...)
are removed, `AO21`/`XOR3` that lose an input become `AND`/`XOR`, and everything that no longer reaches a port is dropped.
Free config bits and LUT contents stay.
Group boxes (blue frames) that no longer contain a symbol or a wire are dropped with their title and texts, and port labels that are connected to nothing (and their wire
stubs) are dropped too; only through connections between two ports remain (e.g. `POUTY2 = PINY2` at `C_FUNCTION=3`).

After the constants, a reachability pass looks at every remaining `MUX2`/`MUX4`: it enumerates all values of the free signals
in the cone of the selects (config bits, ports, register/LUT outputs count as independent variables) and drops a data input that
can never be selected (marked with a no-connect flag, everything that only fed it disappears too), or turns a select that is
constant in every reachable state into a constant. This is what removes the multiplier outputs for `C_FUNCTION=6`: `D3` of the
`COUTX`/`POUTX` multiplexers is selected by `{S1,S0} = {chain & ~C_CX_I, C_MULT | C_CX_I}`, which is never `11` when `C_MULT=0`.

    python fold_sheet.py 6 ../cpe.kicad_sch folded6.kicad_sch

`build_function_sheets.py` does this for all eight functions and writes them as the sub sheets of the CPE (`../cpe_comb.kicad_sch` = 0, `cpe_comb_addf` = 1,
`cpe_comb_addf2` = 2, `cpe_comb_mult` = 3, `cpe_comb_mux4` = 4, `cpe_comb_en_cin` = 5, `cpe_comb_concat` = 6, `cpe_comb_addcin` = 7). The old content of those files is dropped
except the function description texts, which are placed to the right of the diagram (the page is widened for them). Re-run it after every change of `cpe.kicad_sch`.
`place_function_sheets.py` keeps one hierarchical-sheet symbol per function in `../cpe.kicad_sch` (3 x 3 grid at the top; the existing symbols keep uuid and page numbers, the missing ones get new page numbers from 129 on).

Check (`check_fold.py`, after `python gen.py ../cpe.kicad_sch cpe_generated.v cpe_ref`): `gen.py` on the folded sheet gives a model without `C_FUNCTION` (the constants it still
needs are read from the note text of the sheet, e.g. `C_MX4 = 1`; an output port on the same net as an input becomes an `assign`, e.g. `POUTY2 = PINY2` at `C_FUNCTION=3`);
it simulates identically to `cpe_ref` with `C_FUNCTION=n` (random configurations as in `make_equiv_tb.py`, only the parameters the folded model still has):

    python check_fold.py 2 ../cpe_comb_addf2.kicad_sch 1 100

`FF_INIT` (2 bits, 2 = Q starts 0, 3 = Q starts 1, 0 / 1 = not initialised, Q = 1) is a parameter of `cpe.v` only; the chip has no such configuration bit, the bitstream loader pulses reset / set. Taken over from commit 532a8b9 (`tb_ff_init.v` there checks it). `cpe_ref` (from the schematic) always starts with Q = 0 in `cpe_prims.v`, so `make_equiv_tb.py` compares with the default `FF_INIT = 0` only.
