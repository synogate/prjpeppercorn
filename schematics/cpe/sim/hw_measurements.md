# CPE hardware measurements (helper-free rig)

New log. The previous log and all its data were deleted because the old rig misled the interpretation (inverting pips at IN1/IN4/IN6 of an L2T4 DUT looked
like an inverted reader and inverted LUT inputs). Nothing from it is carried over; `cpe.v` changes that were derived from it are unconfirmed until
re-measured here.

## Method

* Rig: `lab/cpe_rig/truth_rig/` (`top.v`, `place_mx8.py`, `meas.py`, `suites.py`, `tt_rig.py`). Board: GateMate, scope Rigol MHO984.
* DUT = `CC_MX8` placed at X146Y19 by the `--pre-place` hook and patched in the bitfile into the CPE under test. nextpnr must route its data inputs
  without inversion and cannot swap them: **IN1..IN8 = x0..x7 exactly**, `CLK/EN/SR` = x8/x9/x10 (selects S0/S1/S2).
* Signals: x[k] = registered counter bit k (12 MHz / 2^(k+1)), UART0_TX = reference (counter bit 14). One capture of UART0_RX gives the output over all
  2^14 states (only the low 11 bits reach the DUT, x11..x13 are unused).
* **No helper CPEs.** UART0_RX = what nextpnr routes from the DUT to the pad: OUT2 of the DUT (nextpnr writes `C_O2 = 01`, MUXOUT) through its own
  pad CPE. Verified: MX8 mux over IN1..IN8 gives exactly `x[sel]`, no inversion (0 of 16384 states differ).
* Carry/propagate inputs (CINX, CINY1/2, PINX, PINY1/2) are **not driven** by any helper: their value is an unknown constant. Series that depend on
  them are marked and their mismatches are not evidence against `cpe.v`.
* Base DUT words from nextpnr (`C_CPE_CLK`, `C_CPE_EN`, `C_CPE_RES`, `C_O2`) are deleted before each patch; every configuration is explicit.
* Expected values: `expect.py` (cpe.v) with IN1..IN8 = x0..x7, CLK = x8, EN = ~x9, SR = ~x10 (see pin polarity), everything else 0. "mismatch" = number of the 16384 states that differ.
* Raw data: `hw_data/<series>.jsonl` (words, F as hex over states s = 0..16383 with bit s, mismatch).

## Pin polarity (what the DUT pins really see)

| Pin | Polarity | Source |
|---|---|---|
| IN1..IN8 | direct (= x0..x7) | MX8 data inputs: nextpnr aborts on an inverted route and cannot swap them; S0 with `C_BR` bridge identity IN1..IN8 (S1) |
| CLK | direct (= x8) | S1b: LUT1 word `10` passes it |
| EN | **inverted** (= ~x9) | S1b: pass is word `01`; nextpnr writes `C_CPE_EN = 01` itself for the same reason (inverting pip compensated by `update_cpe_inv`) |
| SR | **inverted** (= ~x10) | S1b: pass is word `01`, nextpnr writes `C_CPE_RES = 01` |

`meas.py` (`PIN_INV`) applies this when computing the expectation. The first evaluation of S1 without it showed 33 of 40 mux8 configurations 8192 states off;
after the correction all 222 configurations of S1, S1b, S2, S3 match (`recheck.py` recomputes stored data).

## Series

Result column: configurations measured / with mismatch against `cpe.v` (16384 states each). CP inputs (CINX, CINY1/2, PINX, PINY1/2) are not driven.

| Series | OUT2 source | What | Result |
|---|---|---|---|
| S0 | MUXOUT | selftest, IN1 and IN5 through the bridge | 2 / 0 |
| S1 | MUXOUT (`C_O2 = 01`) | bridge `C_SN` 0..7 (8), bridge with random `INIT_L10/L11` (24), mux8 with random selects, LUT1 words and `C_2D_IN` (40) | 72 / 0 |
| S1b | MUXOUT | mux8, one parameter at a time: `C_SN` x `C_2D_IN` (16), each LUT1 word `01/10/11` (18), `INIT_L10/L11` (4) | 38 / 0 |
| S2 | COMBOUT, `C_FUNCTION = 0` | all 16 INITs of L00, L01, L10 with the others as pass-through (48), random full LUT trees (24); only L00, L01, L10 reach COMB2OUT | 72 / 0 |
| S3 | COMBOUT, `C_FUNCTION = 4` | MX4 path, random LUT words (40) | 40 / 0 |
| S4 | CPOUT (`C_O2 = 10`), `C_FUNCTION` 0 / 4 | random LUT words, random `C_HORIZ` (24); CP inputs undriven | 24 / 0 |
| S5 | COMBOUT, `C_FUNCTION` 1, 2, 3, 5, 6, 7 | random LUT words, random `C_HORIZ` (36); carry in undriven | 36 / 0 |
| S6d, S6e, S6f | latch / flip-flop diagnosis | CLK x EN LUT1 words, forced set / reset, latch vs flip-flop, source MUXOUT = IN1 (57 configurations, see below) | diagnostics, no pass/fail |
| S6 | latch as pass-through (`C_O2 = 00`, `C_L_D = 1`, `C_CPE_CLK = C_CPE_EN = C_CPE_RES = C_CPE_SET = 11`) | MUXOUT (`C_BR = 1`, `C_2D_IN = 0`) for `C_SN` 0..7, inverted MUXOUT (`C_2D_IN = 1`) for `C_SN` 0..7, COMB2OUT (`C_BR = 0`, `C_2D_IN = 1`, 16 random LUT trees) | 32 / 0 |
| S7 | latch, COMB1OUT (`C_BR = 0`, `C_2D_IN = 0`, `C_FUNCTION` 0 / 4) | all 16 INITs of each of the seven LUTs L00..L03, L10, L11, L20 with the others as pass-through (112), random full LUT trees (24), MX4 (24) | 160 / 0 |

## Findings (confirmed by hardware)

1. **8:1 mux:** `muxout = IN[(C_SN + clk_term + 2*en_term + 4*res_term + C_2D_IN) mod 8]` with `term = lut1(word, pin)`, `lut1(w, d) = w[d]`; in bridge mode (`C_BR = 1`)
   the select is `C_SN` alone. The invert bits `INIT_L10/L11` have no effect on the mux8 or the bridge (S1, S1b), as modelled in `cpe.v`.
2. **LUT tree, `C_FUNCTION = 0`:** L00, L01, L10 behave exactly as `lut2(init, D1, D0)` with the pin polarity above, no inversion anywhere (S2). COMB2OUT = L10.
3. **MX4, `C_FUNCTION = 4`:** with the lower mux (`mx4b`: data IN5..IN8, selected by L01/L00) feeding level2_a = COMB2OUT, `cpe.v` as edited today matches (S3).
   (This confirms the MX4 to L20 assignment of the edit, now without a polarity correction.)
4. **COMB2OUT and COMB1OUT, `C_FUNCTION = 0`:** the whole LUT tree is validated: all 16 INITs of every LUT L00..L03, L10, L11, L20 and random trees match `cpe.v`
   (COMB1OUT = L20, COMB2OUT = L10), no inversion anywhere (S2, S7). With `C_FUNCTION = 4` COMB1OUT = L20(mx4a, mx4b) matches as well (S7).
5. **Latch as pass-through:** `C_O2 = 0`, `C_L_D = 1`, `C_CPE_CLK = C_CPE_EN = 11`, `C_CPE_RES = C_CPE_SET = 11` makes OUT2 follow `ff2_source` unchanged:
   `C_BR = 0, C_2D_IN = 0` -> COMB1OUT, `C_BR = 0, C_2D_IN = 1` -> COMB2OUT, `C_BR = 1, C_2D_IN = 0` -> MUXOUT, `C_BR = 1, C_2D_IN = 1` -> ~MUXOUT
   (S6, S7; matches the data selection of `cpe.v`). The latch is transparent when `lut1(CLK word, CLK) & lut1(EN word, EN)` is 1 and holds otherwise (S6f).
6. **Set / reset LUT1 words are active low:** word `00` for `C_CPE_RES` / `C_CPE_SET` (the default if the word is absent) requests reset / set permanently,
   `11` requests nothing (nextpnr writes `11` for both on a plain flip-flop). Measured at the pad (S6e, latch and flip-flop alike): both words `00` -> constant 1;
   `C_CPE_SET = 00`, `C_CPE_RES = 11` -> 1 (set); `C_CPE_SET = 11`, `C_CPE_RES = 00` -> 0 (reset). The result of the set / reset is the same as in `cpe.v`
   (set -> 1, reset -> 0, set wins); only the polarity of the two request words was reversed. **Applied to `cpe.v`** (`reset_req = ~lut1(...)`,
   `set_req = ~lut1(...)`); `meas.py` uses the model unchanged. All stored series S1..S7 (454 configurations) still match after the change.
7. **Flip-flop mode (`C_L_D = 0`) not examined.** Observed constant 1 in S6e / S6f; not needed for the combinational validation.

## Caveats

* S4 and S5 (CPOUT, other `C_FUNCTION`) pass with the CP inputs undriven. This only shows that the configurations tested do not depend on them (or that they
  happen to be 0). It does not validate CINX, CINY1/2, PINX, PINY1/2 and the carry chain from a neighbour; that needs helper CPEs.
* OUT1 and the OUT1 muxes (`C_O1`) were not observed. COMB1OUT is covered through the latch on OUT2.
* `cpe.v` changes in this round: MX4 to L20 (finding 3) and the set / reset request polarity (finding 6). No other deviation is known for the paths measured here.
* S6f against the model: 16 of 32 configurations differ, all in the diagnostic with a partly closed latch or in flip-flop mode. The partly closed latch differs only in the held
  value (the hardware holds the last value seen while open, 1; the simulation sees IN1 change before CLK/EN in the same time step and holds 0, an artefact of the input order in
  `expect.py`); the flip-flop mode (`C_L_D = 0`) was not examined.


## Rig with CP helpers and OUT1 / OUT2 selector

Extension of the method above (the series S1..S7 above were measured without the helpers and the selector; the results on IN1..IN8 and OUT2 are identical, see the regression below):

* 17 orthogonal signals x0..x16, reference = counter bit 17; one enumeration takes 2^17 ticks = 10.9 ms. Scope window about -1.8 ms .. +13.8 ms (`TIM:MAIN:SCAL 0.7 ms`, `TIM:MAIN:OFFS +6 ms`, 1 M points, about 15 ns per sample).
* Cells (all `CC_MX8` unless noted, placed by `place_mx8.py` in `--pre-place`, nextpnr runs once):
  * DUT X146Y19: IN1..IN8 = x0..x7, CLK / EN / SR = x8 / x9 / x10.
  * CPINX X145Y19 (west): IN1 = x11, IN2 = x12; patched to drive CINX and PINX of the DUT.
  * CPINY X146Y18 (south): IN1..IN4 = x13..x16; patched to drive the Y lines. (The Y lines run from south to north.)
  * `dut_o1`: an L2T4 on the upper half of the DUT CPE, only so that nextpnr routes the DUT's OUT1 wire. The dummy of the MX8 cluster for that half is parked at X100Y10.
  * Selector X147Y19: IN1 = OUT1 wire of the DUT, IN2 = OUT2 wire; `C_BR = 1`, `C_SN = 000` / `001` in the bitfile picks which one reaches UART0_RX. Both wires checked with bridge selftests (IN1 on OUT2, IN3 on OUT1: 0 mismatches).
* Words of the DUT and the helpers from nextpnr are deleted before patching; the selector keeps its routing words.
* Pin polarity of CLK / EN / SR is a property of the **route** of a build, only visible when the LUT1 passes the pin (word 10 / 01): earlier build EN and SR inverted, this build all three direct (`calibrate_pins()`, `calib.json`). IN1..IN8 are direct by construction.

### Corrections of the extraction

* `extract()` kept the phase of the output edges modulo 1. A small negative delay (about -0.03 tick) became 0.97 and the sampling window slipped by one tick; this showed up as mismatches in states with x0 = x1 = 1 when the sampling got coarse (5 samples per tick). Now the phase is kept in (-0.3, 0.7) and the sampling window is 0.4 .. 0.8 tick.
* Series runner repeats a mismatching measurement once (one unreproducible bad capture was seen right after a rebuild).

### Regression of S1..S7 on the rig with the helpers (every 4th configuration)

| Series | configurations | with mismatch |
|---|---|---|
| S1, S1b, S2, S3 | 18 + 10 + 18 + 10 | 0 |
| S4, S5, S6, S7 | 6 + 9 + 8 + 40 | 0 |

119 configurations, no retries, results identical to the earlier runs. The helpers are present and driving their CP lines in this regression (their words are cleared, so the CP inputs of the DUT see whatever an empty CPE emits); S4 and S5 are unchanged.

### S8: carry / propagate inputs of the DUT (identification, `hw_data/s8.jsonl`)

The DUT reads one CP input through a validated path (L01 -> L10 -> COMB2OUT, or L03 / L02 -> L11 -> L20 -> COMB1OUT on OUT1); `identify()` compares the result with x0..x16, ~x0..~x16 and the constants (no expectation assumed). Helper words: `CPX` in `suites.py` (OUT1 = IN1 = x11 via MUXOUT, OUT2 = COMB2OUT = IN2 = x12, `C_CX_I = 1`, `C_PX_I = 1`).

| Input | Read with | Helper setting | Result |
|---|---|---|---|
| CINX | `C_I2 = 1`, L01 / L10 pass D1, OUT2 | default (`C_SELX = 0`) | x11, 0 of 131072 states differ |
| CINX | same | `C_SELX = 1` | x12 |
| CINX | same | `C_CX_I = 0` | constant 0 |
| PINX | `C_I4 = 1`, L03 / L11 / L20 pass D1, OUT1 | default | x12 |
| PINX | same | `C_SELX = 1` | x11 |
| PINX | same | `C_PX_I = 0` | constant 0 |
| PINY1 | `C_I1` (L00) or `C_I3` (L02) | south helper with `C_PY1_I = 0`, `C_SELY1` = 0 / 1 | constant 0 in all runs: **unresolved** (see below) |

Findings:

8. **CINX (via `C_I2`) and the path OUT1 -> COUTX work as in `cpe.v`:** with `C_CX_I = 1` COUTX takes the routing mux, `C_SELX = 0` -> OUT1, `C_SELX = 1` -> OUT2; with `C_CX_I = 0` the generate term (constant 0 here). No inversion. `C_I2` and the COUTX route are validated together, not separately.
9. **OUT2 -> POUTX and `C_I4` work as expected:** with `C_PX_I = 1` and `C_SELX = 0` POUTX carries OUT2 of the helper (x12), with `C_SELX = 1` OUT1 (x11); with `C_PX_I = 0`
   (together with `C_CX_I = 0`) the line is constant 0 (`C_COMP_I`). At the DUT `C_I4 = 1` puts PINX in place of IN8 as D1 of L03 (read through L03 -> L11 -> L20 -> COMB1OUT
   on OUT1, `C_O1 = 11`). No inversion. As with finding 8, the POUTX route and `C_I4` are validated together; the read path with `C_O1 = 11` was not measured on its own before
   (the OUT1 selftest used MUXOUT, `C_O1 = 01`; L03 / L11 / L20 themselves are covered by S7 through the latch).
10. **POUTY1 -> PINY1: `C_PY1_I = 1` selects the routing mux, `C_SELY1` picks OUT1 / OUT2.** Measured with the south helper (the Y lines run one to one from south to north: POUTY1 of
    (x, y-1) -> PINY1 of (x, y)), PINY1 read at the DUT through `C_I1` (L00 -> L10 -> COMB2OUT, OUT2): `C_PY1_I = 1`, `C_SEL_P = 0`: `C_SELY1 = 0` -> x13 (OUT1 of the helper),
    `C_SELY1 = 1` -> x14 (OUT2), no inversion, 0 of 131072 states differ. A search over the other single config bits of the helper (`C_Y12`, `C_HORIZ`, `C_COMP_I`, `C_COMP`, `C_SELX`,
    `C_SELY1`, `C_SEL_P`) with `C_PY1_I = 0` gave constant 0 in every case (`hw_data/find_piny1.jsonl`); an earlier search over 11 helper positions was unnecessary and was stopped.
    `cpe.v` has `py1_through = (comp_out | py1_compare) & C_PY1_I`, i.e. `C_PY1_I` has no effect unless the comparator is active: **deviates from the hardware**, not yet changed in `cpe.v`.

    **Assumption (not measured):** `C_PY1_I = 0` simply passes PINY1 of the helper through, like `C_CX_I = 0` does for CINX (finding 8) and `C_CY1_I = 0` / `C_CY2_I = 0` are
    modelled for CINY1 / CINY2. The constant 0 at `C_PY1_I = 0` fits this because the helper's own PINY1 input is not driven in this rig. Working hypothesis behind it: the six CP
    output lines share the same logic at their core. Both are to be checked, e.g. by a second helper one row further south (X146Y17) driving the PINY1 of the south helper.

### S9: carry in through CINX with `C_HORIZ = 1` (`hw_data/s9.jsonl`)

CINX = x11 from the west helper (`CPX`: `C_CX_I = 1`, `C_SELX = 0`). DUT: `C_HORIZ = 1`, `C_FUNCTION` = 001, 010, 111; per function one configuration with all INITs 0 and eight random LUT trees,
each read twice: COMB1OUT on OUT1 (`C_O1 = 11`) and COMB2OUT on OUT2 (`C_O2 = 11`). Expectation: `cpe.v` with CINX = x11 (`meas.expected(..., cp={'CINX': 11})`).

| `C_FUNCTION` | COMB1OUT (OUT1) | COMB2OUT (OUT2) |
|---|---|---|
| 001 (ADDF, ADDCIN) | 9 / 0 mismatches | 9 / 0 |
| 010 (ADDF2, ADDCIN) | 9 / 0 | 9 / 0 |
| 111 (ADDCIN) | 9 / 0 | 9 / 0 |

54 configurations, no retries, 0 of 131072 states differ in every one.

11. **CINX is XORed into COMB1OUT (`C_ADDCIN`: `C_FUNCTION` 001, 010, 111) and, for `C_ADDF2` (010), into COMB2OUT with `l11 ? CINX : l02`, as in `cpe.v`.** With `C_FUNCTION` 001 and 111
    COMB2OUT has no carry term. `C_HORIZ = 1` selects CINX as the carry in.
12. **The combination with CINX is an XOR (checked for COMB1OUT, `C_FUNCTION` 001):** the nine measured functions were compared offline with `l20` (the model with CINX held 0) combined with CINX by
    XOR, XNOR, OR, AND, `l20` alone and CINX alone. Only XOR matches (0 differing states); the others differ in 274 432 (OR), 548 864 (CINX alone), 589 824 (`l20` alone),
    864 256 (AND) and 1 179 648 (XNOR) states over the nine configurations. The all-zero configuration does not tell XOR from OR (both give CINX); the random trees do.
    The same comparison was **not** done for COMB2OUT (`l10 ^ add2_carry`) and for `C_FUNCTION` 010 / 111; there the full match with the XOR model is the only evidence.

### S10: `C_EN_CIN` (`C_FUNCTION = 101`) with `C_HORIZ = 1` (`hw_data/s10.jsonl`)

CINX = x11 from the west helper. Read-out: `INIT_L11 = INIT_L20 = 1100` (both pass D1), all other INITs 0 except `INIT_L03`; COMB1OUT (OUT1, `C_O1 = 11`) then shows `l03` directly.

| Configurations | Count | Mismatches vs `cpe.v` |
|---|---|---|
| `C_FUNCTION = 101`, all 16 values of `INIT_L03`, L11 / L20 pass | 16 | 0 |
| control `C_FUNCTION = 000`, `INIT_L03` = 0001, 0110, 1001, 1110 | 4 | 0 |
| `C_FUNCTION = 101`, 8 random LUT trees, COMB1OUT (OUT1) and COMB2OUT (OUT2) | 16 | 0 |

36 configurations, no retries.

13. **`C_EN_CIN` (`C_FUNCTION = 101`) ORs the carry in into L03: `l03 = l03_lut | CINX` (with `C_HORIZ = 1`), as in `cpe.v`.** Offline comparison of the 16 measured `l03` functions (`INIT_L03` = 0000..1111) with
    `l03_lut` combined with CINX: OR matches in all 16 (0 differing states); XOR, AND, NOR, `l03_lut` alone and CINX alone differ in 524 288, 1 048 576, 2 097 152, 524 288 and 524 288 states over the 16 configurations.
    With `INIT_L03 = 0000` OR and XOR cannot be told apart (both give CINX); the other 15 values do. Controls with `C_FUNCTION = 000` show no CINX (0 differing states): the term is brought in by `C_EN_CIN`.
    The carry in only reaches L03 (and through it L11 and L20): the random trees on COMB2OUT, which does not see `l03`, match as well.
    Limits: only `C_HORIZ = 1` (CINX) was tested; `C_HORIZ = 0` (CINY1) and `C_I4 = 1` (PINX in place of IN8 in the same L03) in combination with `C_EN_CIN` were not.

### S11: CINY1 through `C_EN_CIN` with `C_HORIZ = 0` (`hw_data/s11.jsonl`)

DUT: `C_FUNCTION = 101`, `C_HORIZ = 0` (carry in = CINY1), all INITs 0 except `INIT_L11 = INIT_L20 = 1100`, `C_O1 = 11`: COMB1OUT = `l03 = l03_lut | CINY1` = CINY1. Identification without an expectation; helper = south CPE (X146Y18, `CPY`: OUT1 = IN1 = x13, OUT2 = IN2 = x14).

| South helper | CINY1 at the DUT |
|---|---|
| `C_CY1_I = 1`, `C_SELY1 = 0` | x14 (OUT2 of the helper), 0 of 131072 states differ |
| `C_CY1_I = 1`, `C_SELY1 = 1` | x13 (OUT1 of the helper) |
| `C_CY1_I = 0` | constant 0 (the helper's own CINY1 is not driven in this rig) |

14. **COUTY1 -> CINY1 (south to north) works, `C_CY1_I = 1` takes the routing mux (`C_SELY1`: 0 -> OUT2, 1 -> OUT1) as in `cpe.v`, no inversion, and CINY1 enters L03 through the OR of `C_EN_CIN` when `C_HORIZ = 0`.**
    `C_CY1_I = 0` gives constant 0; consistent with a pass-through of the helper's unconnected CINY1 (assumption, see finding 10), not tested separately.

### S12: COUTX -> CPOUT1 -> OUT1 in the DUT (`hw_data/s12.jsonl`)

DUT: all LUT INITs 0, `C_FUNCTION = 000`, `C_HORIZ = 1`, `C_CX_I = 0` (COUTX passes CINX), `C_O1 = 10` (OUT1 = CPOUT1), CINX = x11 from the west helper; OUT1 read through the selector. Expectation: `cpe.v` with CINX = x11.

| `C_C_P` | OUT1 measured | `cpe.v` | mismatching states |
|---|---|---|---|
| 1 | x11 | CINX through COUTX | 0 of 131072 |
| 0 (control) | x12 (= PINX) | constant 0 | 65536 |

15. **COUTX -> CPOUT1 -> OUT1 works:** with `C_HORIZ = 1`, `C_C_P = 1`, `C_CX_I = 0` the carry in CINX passes COUTX (no adder) into CPOUT1 and OUT1 (`C_O1 = 10`). No inversion.
16. **POUTX passes PINX at `C_PX_I = 0` (deviates from `cpe.v`):** with `C_C_P = 0` CPOUT1 = POUTX (carry-or-propagate select for `C_HORIZ = 1`) and OUT1 shows x12, which is PINX (helper: `C_PX_I = 1`,
    `C_SELX = 0`: POUTX = OUT2 = x12). `cpe.v` gives the constant `C_COMP_I` here (`poutx_chain = (comp_out | (C_COMP & C_HORIZ)) & ~C_PX_I` is 0 in this configuration). So POUTX behaves like COUTX: `C_PX_I = 0` passes
    the input, `C_PX_I = 1` takes the routing mux. This also fits the constant 0 at the DUT's PINX when the helper had `C_PX_I = 0` (the helper's own PINX is not driven). Which further bits
    (`C_COMP`, `INIT_L30`) change this is not measured; `cpe.v` not changed yet.

### S13: CPOUT1 / CPOUT2 through the Y1 lines (`hw_data/s13.jsonl`, `cpout_y.py`)

DUT: all LUT INITs 0, `C_FUNCTION = 000`, `C_HORIZ = 0` (`cp_carry_out = COUTY1`, `cp_prop_out = POUTY1`), `C_CY1_I = 0`, `C_PY1_I = 0`; OUT1 / OUT2 shown with `C_O1 = 10` / `C_O2 = 10` through the selector.
South helper (X146Y18): `C_CY1_I = 1`, `C_PY1_I = 1`, `C_SELY1 = 0`: CINY1 = OUT2 = x14, PINY1 = OUT1 = x13.

| Output | `C_C_P` | CPOUT = | measured | `cpe.v` |
|---|---|---|---|---|
| CPOUT1 (OUT1) | 1 | COUTY1 | x14 | CINY1 passes COUTY1 = x14, 0 of 131072 states differ |
| CPOUT1 (OUT1) | 0 | POUTY1 | x13 | `py1_route` (not comparable: it would loop through OUT1) |
| CPOUT2 (OUT2) | 0 | COUTY1 | x14 | x14, 0 of 131072 states differ |
| CPOUT2 (OUT2) | 1 | POUTY1 | x13 | `py1_route` (not comparable) |

17. **CPOUT1 and CPOUT2 work through the Y1 lines as in `cpe.v`:** `C_C_P = 1`: CPOUT1 = COUTY1, CPOUT2 = POUTY1; `C_C_P = 0`: CPOUT1 = POUTY1, CPOUT2 = COUTY1; `C_HORIZ = 0` selects the Y1 pair.
    COUTY1 passes CINY1 at `C_CY1_I = 0`. POUTY1 shows PINY1 at `C_PY1_I = 0` (the pass-through hypothesis of finding 10 / 16; `cpe.v` has `py1_route` there). No inversion anywhere.
    Not yet tested: CPOUT2 through the X pair (`C_HORIZ = 1`), `C_MULT`, and CPOUT with an adder or comparator active.

### S14: CPOUT2 through the X pair (`hw_data/s14.jsonl`)

DUT: all LUT INITs 0, `C_FUNCTION = 000`, `C_HORIZ = 1` (`cp_carry_out = COUTX`, `cp_prop_out = POUTX`), `C_CX_I = 0`, `C_PX_I = 0`, `C_O2 = 10` (OUT2 = CPOUT2) through the selector. West helper as before: CINX = x11, PINX = x12.

| `C_C_P` | CPOUT2 = | measured | `cpe.v` |
|---|---|---|---|
| 0 | COUTX | x11 | CINX passes COUTX = x11, 0 of 131072 states differ |
| 1 | POUTX | x12 | `C_COMP_I` = constant 0 (known deviation, finding 16) |

18. **CPOUT2 works through the X pair as in `cpe.v`:** `C_C_P = 0`: CPOUT2 = COUTX (CINX passed through), `C_C_P = 1`: CPOUT2 = POUTX, which carries PINX at `C_PX_I = 0` (deviation from `cpe.v` as in finding 16, not a new one).
    Together with findings 15 and 17: CPOUT1 and CPOUT2 are verified for both pairs (X and Y1) and both values of `C_C_P`, without an adder or comparator. Still open: `C_MULT`, CPOUT with an adder (`C_FUNCTION` 1, 2, 3, 6) or comparator active.

### S15: Y2 lines from the south helper (CINY2, PINY2) read through CPOUT2 (`hw_data/s15.jsonl`)

DUT: all LUT INITs 0, `C_FUNCTION = 000`, `C_HORIZ = 1`, `C_CX_I = 1`, `C_PX_I = 1`, `C_SEL_C = 1`, `C_SEL_P = 1`, `C_SELX = 1`, `C_Y12 = 1` (the X routing muxes take CINY2 / PINY2), `C_O2 = 10`; `C_C_P = 0` reads COUTX = CINY2, `C_C_P = 1` reads POUTX = PINY2.
South helper (X146Y18): `C_CY2_I = 1`, `C_PY2_I = 1`, `C_SELY2` = 0 / 1 (COUTY2 = OUT1 / OUT2, POUTY2 = OUT2 / OUT1; OUT1 = x13, OUT2 = x14). Expectation: `cpe.v`.

| DUT reads | helper `C_SELY2` | measured | `cpe.v` | mismatching states |
|---|---|---|---|---|
| CINY2 (via COUTX, `C_C_P = 0`) | 0 | x13 | x13 | 0 of 131072 |
| CINY2 | 1 | x14 | x14 | 0 |
| PINY2 (via POUTX, `C_C_P = 1`) | 0 | x14 | x14 | 0 |
| PINY2 | 1 | x13 | x13 | 0 |

19. **The Y2 lines work from the south helper as in `cpe.v`:** COUTY2 -> CINY2 and POUTY2 -> PINY2 (south to north); `C_CY2_I = 1` / `C_PY2_I = 1` take the routing mux, `C_SELY2` swaps OUT1 / OUT2 (COUTY2: 0 -> OUT1, 1 -> OUT2;
    POUTY2: 0 -> OUT2, 1 -> OUT1). At the DUT CINY2 / PINY2 reach COUTX / POUTX through `C_Y12 = 1` with `{C_SEL_C, C_SELX} = 11` / `{C_SEL_P, C_SELX} = 11` and `C_CX_I = 1` / `C_PX_I = 1`, and then CPOUT2.
    No inversion. Not tested: the pass-through at `C_CY2_I = 0` / `C_PY2_I = 0`, `C_Y12 = 0` for the X lines (CINY1 / PINY1 in place of CINY2 / PINY2), and the other routing mux choices (`comp_out`, CINX / PINX as source of COUTY1/2, POUTY1/2).

## Mapping of the COUTX generator (S17, `hw_data/s17.jsonl`; `map_coutx.py`, `an_coutx.py`, `learn_pg.py`, `dep_coutx.py`)

Schematic (as read from the picture): `S1 = (CADD_S | (C_ADDF & C_HORIZ)) & ~C_CX_I`, `S0 = C_MULT | C_CX_I`, final mux 4:1 `{S1, S0}`: D0 = CADD_A, D1 = routing mux, D2 = CINX, D3 = MULTO2;
routing mux `{C_SEL_C, C_SELX}`: D0 = OUT1, D1 = OUT2, D2 = COMP_OUT, D3 = `C_Y12` mux (CINY1 / CINY2).

Method: COUTX of the DUT is read in the east neighbour (the selector, patched into a reader: `C_I2 = 1`, `INIT_L01 = INIT_L10 = 1100`, `C_O2 = 11`, `east.py`), independent of `C_HORIZ` / `C_MULT`.
Data sources are made distinguishable: CINX = x11, CINY2 = x13, CINY1 = x14 (south helper), OUT1 = x7 (bridge MUXOUT of IN8), OUT2 = ~x7 (inverted MUXOUT through the transparent latch),
LUTs as pass-throughs (l00 = x0, l01 = x2, l02 = x4, l03 = x6, l10 = x2, l11 = x6), `INIT_L30 = 0110` (comp_out = comb2 ^ comb1).

### E2: routing mux (`C_FUNCTION = 000`, `C_HORIZ = 0`, `C_CX_I = 1`; all 8 combinations of `C_SEL_C`, `C_SELX`, `C_Y12`)

20. **The routing mux of COUTX works as in `cpe.v`:** 8 of 8 combinations match (0 differing states). `{C_SEL_C, C_SELX}` = 00 -> OUT1, 01 -> OUT2, 10 -> ~COMP_OUT (inverted, as `cpe.v` has it), 11 -> `C_Y12` mux
    (0 -> CINY1, 1 -> CINY2); with `C_CX_I = 1`, `S1 = 0` and `S0 = 1` the final mux takes this input (D1).

### E1: final mux (`C_FUNCTION` 0..7 x `C_HORIZ` x `C_CX_I`, routing mux at 00; 32 configurations, no addition of the multiplier inputs)

21. **`C_CX_I = 1`: COUTX = routing mux for every `C_FUNCTION` and `C_HORIZ`** (16 of 16, including `C_MULT` = `C_FUNCTION` 3).
22. **`C_CX_I = 0`, no adder (`C_FUNCTION` 0, 4, 5, 7), and `C_FUNCTION` 1, 2, 6 with `C_HORIZ = 0`: COUTX = CINX** (always).
23. **`C_CX_I = 0`, `C_HORIZ = 1`, adder (`C_FUNCTION` 1, 2, 6): COUTX = CINX when the propagate condition is false, else the generate term `G`** (learned from 12 random LUT trees per function, `learn_pg.py`;
    P = 1 means G, P = 0 means CINX; no conflicting observations, COUTX independent of x12..x16):

    | `C_FUNCTION` | CINX passes when | otherwise `G` = | `cpe.v` |
    |---|---|---|---|
    | 1, 6 (ADDF, no ADDF2) | `l10 ^ l11 = 1` | **`l00 \| l01 \| l02`** | G = `l00 \| l01`: **deviates** (4 of 31 / 4 of 28 vectors); P as in `cpe.v` |
    | 2 (ADDF2) | `l10 & l11 = 1` | `l10 ? l02 : (l00 \| l01)` | matches (0 of 46 vectors) |

    So the schematic's `S1 = (CADD_S | (C_ADDF & C_HORIZ)) & ~C_CX_I` is **not** what the hardware does: with `C_ADDF & C_HORIZ = 1` the OR would force `S1 = 1` (CINX) regardless of `CADD_S`; measured is `CADD_S` selecting between CINX and `CADD_A`.
    The `l00 | l01 | l02` for ADDF replaces the earlier `l00 | l01` in `cpe.v`; the data are consistent with 12 + 12 random trees (no counter-example). Hypotheses that differ: `l00|l01` (4 vectors wrong), `l00|l01|l02|l03` (2 wrong).
24. **With `C_HORIZ = 0` the adder does not touch COUTX (CINX passes at `C_CX_I = 0`):** the term `C_ADDF & C_HORIZ` is really part of the select, as in the schematic.
    **Open: `C_FUNCTION = 3` (multiplier) with `C_CX_I = 0`** - COUTX is neither CINX nor `cpe.v`'s `MULTO2` / route selection: `C_HORIZ = 0`: no exact fit (closest `S=0 -> G`, `S=1 -> COMP_OUT`, 62 / 67 %);
    `C_HORIZ = 1`: route (OUT1 = x7) in 87.5 % of the states, model differs in 16384 states. To be analysed next.

### S18: COUTY1 (`C_HORIZ = 0`) against COUTX (`C_HORIZ = 1`) with `C_MULT = 0` (`hw_data/s18.jsonl`, `map_couty1.py`, `an_coutx.py s18 COUTY1 cy1_route 14`, `learn_pg.py y3 <f> s18 3`)

Same environment as S17 (pass-through LUTs, CINY1 = x14 from the south helper, OUT2 = ~x7 as data of the Y1 routing mux `{C_SEL_C, C_SELY1}` = 00), but OUT1 now shows CPOUT1 = COUTY1 (`C_HORIZ = 0`, `C_C_P = 1`, `C_O1 = 10`).
`C_FUNCTION` 0, 1, 2, 4, 5, 6, 7 x `C_CY1_I` (14 configurations) and 12 random LUT trees each for 1, 2, 6 with `C_CY1_I = 0` (36 configurations). **All 50 match `cpe.v` (0 differing states).**
(COUTY1 can only be read through CPOUT with `C_HORIZ = 0`; the mirror case `C_HORIZ = 1` for COUTY1 has no reader, so it is not measured.)

| Case | COUTX (`C_HORIZ = 1`) | COUTY1 (`C_HORIZ = 0`) | identical? |
|---|---|---|---|
| no adder (`C_FUNCTION` 0, 4, 5, 7), `C_xx_I = 0` | CINX | CINY1 | yes |
| no adder, `C_xx_I = 1` | routing mux | routing mux | yes |
| adder (1, 2, 6), `C_xx_I = 0` | `P ? G : CINX` | `P ? G : CINY1` (same `P`, same `G`, 36 random trees) | yes |
| adder (1, 2, 6), `C_xx_I = 1` | **routing mux** | **G** | **no** |

25. **COUTX and COUTY1 share the through / generate part:** the same propagate condition (ADDF: `l10 ^ l11`, ADDF2: `l10 & l11`), the same generate term (ADDF: `l00 | l01 | l02`, ADDF2: `l10 ? l02 : (l00 | l01)`; for COUTY1 confirmed by the 36 random trees,
    which also confirms the corrected ADDF generate), CINX / CINY1 passed when `C_xx_I = 0` and the carry does not propagate.
26. **They differ when `C_xx_I = 1` and the adder works on this axis:** COUTX takes the routing mux (S0 = `C_MULT | C_CX_I`), COUTY1 takes the generate term. For COUTY1 the choice between routing mux and generate is made by "adder on this axis"
    (`C_ADDF & ~C_HORIZ`), not by `C_CY1_I`. `cpe.v` already models exactly this (`cy1_through = ~(C_CY1_I | (cy1_adder & carry_propagate))`, then `cy1_adder ? carry_generate : cy1_route`); the schematic's COUTY1 has the same structure
    (OA21 + NOT as through select, then a MUX2 with the adder bit as select), so for COUTX the schematic form is now the odd one out. `C_MULT = 1` was not part of this comparison.

### S19: MULTO2 (`C_FUNCTION = 3`, `C_HORIZ = 0`, `C_CX_I = 0`) read as COUTX in the east neighbour (`hw_data/s19.jsonl`, `mult_test.py`)

With `C_MULT = 1` the final mux takes MULTO2 (D3) here (`S0 = 1`, `S1 = ~(C_CX_I | (C_ADDF & C_HORIZ & CADD_S)) = 1`). In the S17 data (`e1_f3_h0_cx0`) COUTX depends on exactly the six bits MULTO2 depends on in `cpe.v`
(x2 = `l10`, x4 = IN5 / `l02`, x6 = `l11`, x7 = IN8, x13 = CINY2, x14 = CINY1 / PINY2) and not on x0 (`l00`) or x11 (CINX). In S17 CINY1 and PINY2 both carried x14, so S19 repeats the measurement with four settings of the south helper
(`C_SELY1`, `C_SELY2`) that give (CINY1, CINY2, PINY2) the counter bits (x14, x13, x14), (x13, x13, x14), (x14, x14, x13), (x13, x14, x13).

| Hypothesis (pieces shared by both: `add2 = l11 ? CINY1 : l02`, `hi = add2 ^ l10 ^ (IN5 & PINY2)`, `lo = l11 ^ (IN8 & PINY2) ^ CINY1`) | differing states, 4 x 131072 |
|---|---|
| `cpe.v`: `MULTO2 = hi ^ (lo ? IN8 & PINY2 : CINY2)` | 262 144 (65 536 per variant) |
| **`MULTO2 = hi ^ (lo ? CINY2 : IN8 & PINY2)`** | **0** |

27. **MULTO2 differs from `cpe.v` in one place: the data inputs of the `mult_carry_mid` mux are swapped** (`lo ? CINY2 : pp_am1` instead of `lo ? pp_am1 : CINY2`). Everything else in the formula is confirmed: the sum `l10 ^ add2_carry ^ (IN5 & PINY2)` including
    `add2_carry = l11 ? CINY1 : l02` at `C_HORIZ = 0`, `lo = l11 ^ (IN8 & PINY2) ^ CINY1`, and the independent roles of CINY1, CINY2 and PINY2 (four variants, all exact).
    **Not decided:** the same data are also explained if `lo` (`mult_sum_lo`) is inverted. That would change `MULTO1 = lo ^ CINY2` and `COY2_S` as well; to be separated by reading MULTO1 (POUTX with `C_MULT`).
    Not tested: `C_HORIZ = 1` (carry in = CINX), the selection between routing mux and MULTO2 for `C_FUNCTION = 3` at `C_HORIZ = 1` and `C_CX_I = 1` (S17: route in 87.5 % of the states for `C_HORIZ = 1`, `C_CX_I = 0`, not explained yet).
    `cpe.v` not changed yet.

### S20: MULTO1 / POUTX with `C_MULT = 1` (`hw_data/s20.jsonl`, `mult1_test.py`)

DUT `C_FUNCTION = 3`, `C_HORIZ = 0`, `C_PX_I = 0`; POUTX read through CPOUT1 (`C_C_P = 0`, `C_O1 = 10`; `C_MULT` makes `cp_use_x = 1`). The four south-helper variants of S19 x `INIT_L30` = 0110 / 1001 (flips `comp_out`): 8 measurements.
Candidates per state group (`comp_out` of the model = 0 / 1): `MULTO1 = lo ^ CINY2` with `lo = l11 ^ (IN8 & PINY2) ^ CINY1` (as in `cpe.v`), its inverse, `px_route`, PINX, constants.

| Group | best candidate (share of states matched), all 8 measurements alike |
|---|---|
| `comp_out` = 0 | **MULTO1** 1.000 (`px_route` 0.500) |
| `comp_out` = 1 | **MULTO1** 1.000 |

`cpe.v`'s POUTX matches in 75 % of the states (it takes `px_route` where `comp_out = 0`).

28. **`mult_sum_lo` is not inverted:** MULTO1 = `lo ^ CINY2` matches exactly (uninverted) in all 8 measurements, so the S19 result is the second explanation: the **data inputs of the `mult_carry_mid` mux are swapped** (finding 27), `lo` itself is as in `cpe.v`.
    (Assumes no two compensating inversions; `COY2_S`, which also uses `lo`, was not read.)
29. **POUTX = MULTO1 whenever `C_MULT = 1` and `C_PX_I = 0`, independent of `comp_out`** (at `C_HORIZ = 0`; `comp_out` flipped by `INIT_L30`, no change). `cpe.v` (`poutx_chain = (comp_out | (C_COMP & C_HORIZ)) & ~C_PX_I`, then `multo1` only when the chain is set)
    deviates: for `C_MULT = 1` the choice is not made by `comp_out`. Parallel to COUTX, where `C_MULT = 1` forces `S0 = 1`. `C_HORIZ = 1`, `C_COMP` and `C_PX_I = 1` with `C_MULT = 1` were not measured. `cpe.v` not changed yet.

### S21: POUTX generator (`hw_data/s21.jsonl`, `map_poutx.py`, `an_poutx.py`)

POUTX of the DUT is read as PINX in the east neighbour (selector as reader through the latch path: `C_I4 = 1`, L03 / L11 / L20 pass D1, `C_BR = 0`, `C_2D_IN = 0`, transparent latch on OUT2). Selftest: POUTX = ~x7 (OUT2, `C_SELX = 0`), x7 (OUT1, `C_SELX = 1`), x12 (PINX of the west helper, `C_PX_I = 0`), all exact.
Grid: `C_FUNCTION` 0 / 1 / 3 x `C_HORIZ` x `C_COMP` x `C_PX_I` x `C_COMP_I` x `INIT_L30` (0110: `comp_out` varies, 0000: constant 1, 1111: constant 0) = 144 configurations; routing mux at `{C_SEL_P, C_SELX}` = 00 (OUT2).

30. **POUTX generator** (all 144 configurations, 0 differing states; `cpe.v` differs in 48):
    `POUTX = mux4{S1, S0}` with D0 = **`~C_COMP_I`**, D1 = routing mux, D2 = PINX, D3 = MULTO1, `S0 = C_MULT | C_PX_I`, **`S1 = ~(C_PX_I | (C_COMP & C_HORIZ & L30))`** where `L30` is the *raw* output of the comparator LUT2 (= `~comp_out` of the model, i.e. before the inverter).
    - `C_PX_I = 1`: routing mux (all 48 configurations match `cpe.v`).
    - `C_PX_I = 0` and not (`C_COMP` and `C_HORIZ`): PINX (`C_MULT = 0`) or MULTO1 (`C_MULT = 1`), independent of the comparator output. `cpe.v` (and the schematic) use `comp_out` as select here.
    - `C_PX_I = 0`, `C_COMP = 1`, `C_HORIZ = 1`: PINX / MULTO1 where `L30 = 0`, **`~C_COMP_I`** where `L30 = 1` (`C_COMP_I = 0` gives constant 1, `C_COMP_I = 1` constant 0).
    Same structure as COUTX (`S1 = ~(C_CX_I | (C_ADDF & C_HORIZ & P))`, D0 = generate): the comparator takes the place of the adder, `L30` the place of the propagate condition, `~C_COMP_I` the place of the generate term.
31. **Where the `COMP_OUT` inverter belongs is open.** The comparator condition of POUTX sees the raw LUT output, so with the inverter directly behind the LUT2 (as in `cpe.v` / the schematic now) POUTX would need a second inversion (`~comp_out`) *and* the inverted `C_COMP_I`.
    With the inverter only in front of the COUTX routing-mux input D2 (the only place where the inversion was measured) POUTX needs only the inverted `C_COMP_I`. To be decided by measuring routing-mux input D2 (`COMP_OUT`) of the other lines (POUTX, COUTY1/2, POUTY1/2).
    `cpe.v` and the schematic not changed yet.

### Model and schematic status after S17 .. S21

* `cpe.v`: COUTX (findings 20-24), POUTX (finding 30), MULTO2 mux (finding 27) and the comparator / `COMP_OUT` handling follow the hardware. Selects are never inverted in front of a multiplexer (the data inputs are arranged instead);
  `comp_out` is the raw LUT output, the inversion measured on the COUTX routing multiplexer sits in front of its data input D2 (`~comp_out`, assumed alike for the other five routing multiplexers).
  Checked against the stored measurements: S21 144 / 144, S17 76 / 76 (COUTX), S18 50 / 50 (COUTY1) configurations match.
* `cpe.kicad_sch`: COUTX (hand-built) and COUTY1, COUTY2, POUTX, POUTY1, POUTY2 (`sim/rebuild_cp.py`) have the same structure as `cpe.v`; `COMP_OUT` = raw LUT output, `COMP_OUT_N` = inverted net for the routing multiplexers' D2.
  The generated model of the schematic is equivalent to `cpe.v` (600 random configurations, 0 mismatches) when three model-only deviations are taken out of `cpe.v`: set / reset request polarity (finding 6), MX4 to L20 (finding 3), `mult_carry_mid` data inputs (finding 27).
* POUTY1 is built like COUTY1 and POUTX (`S = C_PY1_I | (comp_out & C_COMP & ~C_HORIZ)`, data `~C_COMP_I` / routing multiplexer / PINY1); the compare branch (`C_COMP = 1`, `C_HORIZ = 0`) is measured in S23 (finding 33), `C_PY1_I = 1` with the routing multiplexer in finding 10; other combinations follow by parallel.
  COUTY2 / POUTY2 follow older measurements that were deleted.

### S22: does `C_COMP_I` invert `COMP_OUT` in front of the routing multiplexers? (`hw_data/s22.jsonl`, `compi_test.py`)

COUTX (read as CINX in the east neighbour, `C_CX_I = 1`) and POUTX (read as PINX, `C_PX_I = 1`) with the routing multiplexer on `COMP_OUT` (`{C_SEL_x, C_SELX} = 10`), `C_COMP_I` = 0 / 1, `INIT_L30 = 0110`. Compared with the raw LUT output of the model:

| Line | `C_COMP_I = 0` | `C_COMP_I = 1` |
|---|---|---|
| COUTX routing mux D2 | = ~raw (131072 of 131072 states) | = ~raw |
| POUTX routing mux D2 | = ~raw | = ~raw |

32. **`C_COMP_I` does not invert `COMP_OUT` at the routing multiplexer input:** D2 is `~L30` for both values. The inversion in front of D2 is now measured for COUTX and POUTX (assumed for the other four routing multiplexers).
    `C_COMP_I` acts only on D0 of POUTX (finding 30), where it cannot be told apart from "comparator result (`L30 = 1` in that branch) XOR `C_COMP_I`". It has no effect on the select condition of POUTX (S21) or on the routing multiplexer input.

### S23: POUTY1 with `C_COMP = 1`, `C_HORIZ = 0` (`hw_data/s23.jsonl`, `py1_test.py`)

POUTY1 read through CPOUT1 (`C_HORIZ = 0`, `C_C_P = 0`, `C_O1 = 10`), `C_SELY1 = 1` (routing multiplexer on OUT2 = ~x7), PINY1 = x13 from the south helper, `INIT_L30` = 0110 (L30 varies) / 0000 / 1111, `C_COMP_I` = 0 / 1.

| `C_PY1_I` | `INIT_L30` | `C_COMP_I = 0` | `C_COMP_I = 1` |
|---|---|---|---|
| 1 | 0110 (L30 varies in 65 536 of 131 072 states) | constant 1 | constant 0 |
| 1 | 0000 / 1111 (L30 constant) | constant 1 | constant 0 |
| 0 | 0110 | `L30 ? 1 : PINY1` (0 differing states) | `L30 ? 0 : PINY1` (0 differing states) |

33. **POUTY1 has the same structure as POUTX / COUTY1** (`C_COMP = 1`, `C_HORIZ = 0`): the select is `C_PY1_I | (C_COMP & ~C_HORIZ & L30)` (`L30` = raw comparator LUT output); select 1 gives `~C_COMP_I`, select 0 gives PINY1.
    - `C_PY1_I = 1`: the output is `~C_COMP_I` **independent of `L30`** (constant although `L30` varies): as COUTY1 with `C_CY1_I = 1` and an adder (finding 26) the "function on this axis" selects the compare value, not the routing multiplexer.
    - `C_PY1_I = 0`: `~C_COMP_I` where `L30 = 1`, PINY1 where `L30 = 0`. This also measures the assumption of finding 10 (`C_PY1_I = 0` passes PINY1 when the compare condition is false).
    - **`C_COMP_I` is a constant, not a comparator inversion:** `D0 = ~C_COMP_I` does not depend on `L30` even where `L30` varies (the "`L30 ^ C_COMP_I`" reading of finding 32 is refuted).
    Not covered: `C_PY1_I = 1` with `C_COMP = 0` or `C_HORIZ = 1` (routing multiplexer expected), POUTY2.

## Work packages S24 .. S30 (`wp_*.py`, `wp_runner.py`; data `hw_data/wp_*.jsonl`)

The remaining open cases of the CP line generator were designed as measurement packages (one module each: configurations, model prediction, analysis; interface in `lab/cpe_rig/truth_rig/WP_INTERFACE.md`),
measured serially on the rig (one measurement = all 2^17 states) and compared with `cpe.v`. A rig check (`wp_example`, 2 configurations) before and after the package that patches neighbouring CPEs (`wp_y2`) was identical, 0 differing states.

| Series | Package | Configurations | Differing from `cpe.v` |
|---|---|---|---|
| S24 | `wp_l30`: comparator LUT2 (all 16 `INIT_L30`, input order, adder / multiplier terms, random trees) | 96 | 0 |
| S25 | `wp_yroute`: COUTY1 / POUTY1 routing codes, POUTY1 grid at `C_HORIZ = 0`, COUTY1 with adders under other helpers (read through CPOUT) | 119 | 0 |
| S26 | `wp_gaps`: COUTX / POUTX routing codes at `C_FUNCTION` 1..7, POUTX grid for 2, 4, 5, 6, 7, COUTX independence from `C_COMP` / `C_COMP_I` / `INIT_L30`, adders under other helpers | 114 | 0 |
| S27 | `wp_mult`: MULTO1 / MULTO2 on 12 random trees x 4 helper variants x `C_HORIZ` 0 / 1, `C_COMP`, `C_CX_I` / `C_PX_I` | 118 | 0 |
| S28 | `wp_cpout`: CPOUT1 / CPOUT2 with adder, comparator, multiplier active (`C_FUNCTION` 1, 2, 3, 6, 7 x `C_HORIZ` x `C_C_P` x `C_COMP` x OUT1 / OUT2) | 114 | 0 |
| S29 | `wp_y2`: COUTY2 / POUTY2 of the south helper (read at the DUT as CINY2 / PINY2), sources via the neighbours X146Y17 / X145Y18 / X146Y16 | 101 | 13 (all in group F, `C_MULT = 1`) |
| S30 | `wp_y2b`: group F repeated with six `INIT_L30` values of the helper | 24 | 0 against the hypothesis of finding 36 |
| S31 | `wp_mx8sel`: select terms of the 8:1 multiplexer with `C_CLKSEL` / `C_ENSEL` (MUXOUT on OUT1, bridge off) | 60 | 0 against Y2 + XOR (cpe.v had Y1 + XOR: 36 of 60 deviated) |

34. **Closed by S24 .. S28 (447 + 114 configurations, no deviation):**
    - The comparator LUT2 is a plain LUT2: `comp_out = INIT_L30[{COMB2OUT, COMB1OUT}]`; the effective `INIT_L30` learned from the measured truth table equals the programmed one for all 16 values (no input swap, no complement),
      through COUTX route D2 (inverted), POUTX route D2 (inverted) and the POUTX compare condition; also with the adder / multiplier terms in COMB1OUT / COMB2OUT (`C_FUNCTION` 1, 2, 3, 5, 6, 7, `C_HORIZ` 0 / 1) and in random trees.
    - The Y1 routing multiplexers follow the order of `cpe.v`: COUTY1 `{C_SEL_C, C_SELY1}` 00 / 01 / 10 / 11 = OUT2 / OUT1 / ~COMP_OUT / CINX; POUTY1 `{C_SEL_P, C_SELY1}` = OUT1 / OUT2 / ~COMP_OUT / PINX. **The inverter in front of D2 is measured on COUTX, POUTX, COUTY1 and POUTY1** (assumed only for COUTY2 / POUTY2: confirmed too by S29 group C / D code 10).
    - POUTY1 at `C_HORIZ = 0` for `C_FUNCTION` 0, 1, 2, 4, 5, 6, 7 x `C_COMP` x `C_PY1_I` x `C_COMP_I`: select 0 passes PINY1 (finding 10 / 33 now measured), select 1 gives `~C_COMP_I` while comparing, else the route; COUTY1 with an adder: generate wins over the route for all four codes.
    - COUTX / POUTX routing codes 01 / 10 / 11 (both `C_Y12` values) for `C_FUNCTION` 1..7, POUTX grid at `C_FUNCTION` 2, 4, 5, 6, 7, no dependence of COUTX on `C_COMP`, `C_COMP_I`, `INIT_L30` (finding 30 confirmed on the remaining functions).
    - MULTO2 at `C_HORIZ = 1` (carry-in of `l11 ? c : l02` = CINX; `S1 = C_CX_I | ((C_ADDF & C_HORIZ) & carry_propagate)` selects it) and MULTO1 = `lo ^ CINY2` on random trees, all four helper variants, both `C_HORIZ` values; `C_FUNCTION = 3` with `C_CX_I` / `C_PX_I = 1` (route wins) and with `C_COMP = 1`. Findings 27 and 28 hold in general.
    - CPOUT1 / CPOUT2 with active adder, comparator and multiplier, both line pairs, both `C_C_P`, OUT1 and OUT2; at `C_FUNCTION = 3` CPOUT shows the X pair even at `C_HORIZ = 0`.
35. **POUTY2 (S29 groups B, D, E, F):** `C_PY2_I = 0` passes PINY2 (known sources 0, 1, x0, also two hops through an untouched CPE), `C_PY2_I = 1` gives the routing multiplexer at all four codes ({`C_SEL_P`, `C_SELY2`}: OUT2 / OUT1 / ~comp / PINX); no compare branch exists for POUTY2 (`C_COMP`, `C_COMP_I` have no effect).
    **In multiplier mode (`C_MULT = 1`) PINY2 is always passed**, also at `C_PY2_I = 1` (8 of 8 configurations; `cpe.v` had `C_PY2_I | C_MULT` selecting the route). Model: `py2_sel = C_PY2_I & ~C_MULT`.
    Plausibility from nextpnr (`pack_mult.cc`): POUTY2 is not a carry line of the multiplier. The `MultCell` (C_MULT) sets only `C_PY1_I` (0 = pass, 1 only in the MSB row) and never `C_PY2_I`, and `pack_mult` chains `POUTY1` / `POUTY2` of each row to `PINY1` / `PINY2` of the next row (the B operand bits are handed north through the pass-through); the carries run over `COUTY1` / `COUTY2` (`CINY1` / `CINY2`). So the pass-through at `C_MULT = 1` is exactly what the multiplier needs.
36. **COUTY2 (S29 groups A, C, F, S30):** without multiplier `C_CY2_I = 0` passes CINY2 (sources 0, 1, x0, two hops), `C_CY2_I = 1` gives the routing multiplexer at all four codes ({`C_SEL_C`, `C_SELY2`}: OUT1 / OUT2 / ~comp / CINX), and with an adder the route is also taken (no generate term on this line).
    **In multiplier mode:** `C_CY2_I = 1` gives the generate-type term `coy2_a` (constant 0 here: see below), `C_CY2_I = 0` passes CINY2 only where `mult_sum_hi & mult_sum_lo`, else `coy2_a`:
    `COUTY2 = (C_CY2_I | (C_MULT & coy2_s)) ? (C_MULT ? coy2_a : route) : CINY2` with **`coy2_s = ~(mult_sum_hi & mult_sum_lo)`** (a NAND; the schematic had `mult_sum_hi | mult_sum_lo`). It fits 13 deviating configurations of S29 and all 24 of S30, and COUTY2 does not change with `INIT_L30`
    (six values, four configurations): the alias `mult_sum_lo & comp_out` is excluded. Same shape as COUTY1 (select = `C_xx_I | (function on this axis & propagate-type term)`).
    **Limit:** the south helper's IN5 .. IN8 sit on the design's GND net, so `coy2_a = hi ? IN8&PINY2 : IN5&PINY2` was only ever 0: the data fix the *select*, not `coy2_a` itself.

37. **8:1 multiplexer select terms (S31, `wp_mx8sel`):** with `C_CLKSEL = 1` / `C_ENSEL = 1` the select adder adds **CINY2 / PINY2** (not CINY1 / PINY1 as drawn in the schematic and modelled before), by XOR with the LUT1 output:
    `term_clk = lut1(C_CPE_CLK, CLK) ^ (C_CLKSEL & CINY2)`, `term_en = lut1(C_CPE_EN, EN) ^ (C_ENSEL & PINY2)`, `term_sr = lut1(C_CPE_RES, SR)`; `select = C_SN + term_clk + 2 term_en + 4 term_sr + C_2D_IN` (mod 8, bridge off). These are the same lines the flip-flops use (as suspected).
    Of four hypotheses per term (Y1 / Y2 x XOR / replace the LUT1 input, the latter as `gatemate/die.py` has it for the flip-flop clock) only Y2 + XOR fits, in groups b (CLKSEL only), c (ENSEL only) and d (both, random words) separately; all 60 configurations, 0 states differing.
    Constant LUT1 words (00 / 11) still show the line, so it is an addition and not a replacement. Baseline (`C_CLKSEL = C_ENSEL = 0`): the CP lines have no effect. Not measured: the flip-flop / latch side itself (same bits, assumed CINY2 / PINY2 as in `cpe.v`; state dependent).
    Model: `cpe.v` changed (`mux8_term_clk` / `mux8_term_en`). Schematic: rewired accordingly (the flip-flops and the MX8 select adders share `CLK_int` / `EN_int`).

### Status after S24 .. S30
* `cpe.v`: COUTY2 / POUTY2 changed as in findings 35 and 36 (`coy2_s` NAND). Everything else of the CP section is unchanged and matches all stored measurements (S17 .. S30).
* `cpe.kicad_sch` (hand-arranged layout, maintained by hand; `sim/rebuild_cp.py` was only the first draft and is locked): `COY2_S` of the multiplier is a NAND (finding 36), POUTY2 selects the route with `C_PY2_I & ~C_MULT` (AND with a NOT on `C_MULT`; finding 35).
  The two gates of finding 36 (`C_CY2_I | (C_MULT & COY2_S)`, AND + OR, net `CY2_SEL`) are drawn. The MX8 select terms and the flip-flops share `CLK_int` / `EN_int` (`LUT1 ^ (C_CLKSEL & CINY2)`, `LUT1 ^ (C_ENSEL & PINY2)`), as measured for MX8 in finding 37.
  The generated model of the schematic (`sim/gen.py`) is now equivalent to the unmodified `cpe.v`: 800 random configurations (8 seeds x 100), 0 mismatches, no X-only differences, nothing taken out of the model.
  Resolved in the schematic over the last rounds: the `mult_carry_mid` mux (`lo ? CINY2 : pp_am1`, finding 27); the MX4 outputs go to L20 as measured (MX4b, data IN5..IN8, select L01 / L00, to level2_a / COMB2OUT; MX4a to level2_b) and the `C = ... X = ...` texts of the two MX4 blocks are right (MX4a C = L11, X = L10; MX4b C = L10, X = L11; `gen.py` no longer swaps them);
  the MX8 select terms share `CLK_int` / `EN_int` with the flip-flops (CINY2 / PINY2, finding 37). The S / R pins of the flip-flop symbols are active low like the hardware (`sim/cpe_prims.v`), so the set / reset polarity of finding 6 was never a deviation.
* Not validated, with reason: `coy2_a` (needs a non-GND IN5 / IN8 on the helper, not possible without re-running nextpnr); COUTY1 / POUTY1 at `C_HORIZ = 1` or `C_FUNCTION = 3` (CPOUT shows the X pair then; needs a reader north of the DUT, where a counter flop sits);
  `coy2_s` is identified only through its effect on COUTY2; CPOUT with `C_COMP = 1` on the carry line was not measured separately.
* Finding 10 (POUTY1: `cpe.v` deviates) is superseded: the model was changed (`py1_sel`), and S25 / finding 33 confirm it.
