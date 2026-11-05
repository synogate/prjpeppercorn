# COUTX truth table

Source: `cpe.v` lines 353-365 and the COUTX section of `../cpe.kicad_sch`.

```
S1 (chain) = (CADD_S | (C_ADDF & C_HORIZ)) & ~C_CX_I
S0 (alt)   =  C_MULT | C_CX_I
COUTX      = mux4(S1,S0):  00 -> CADD_A,  01 -> cx_route,  10 -> CINX,  11 -> MULTO2

cx_route   = mux4(C_SEL_C, C_SELX):  00 -> OUT1,  01 -> OUT2,  10 -> COMP_OUT,  11 -> (C_Y12 ? CINY2 : CINY1)
```

`-` = don't care. `C_MULT` / `C_ADDF` are not bits, they come from `C_FUNCTION`:

| C_FUNCTION | C_MULT | C_ADDF |
|---|---|---|
| 3 | 1 | 1 |
| 1, 2, 6 | 0 | 1 |
| 0, 4, 5, 7 | 0 | 0 |

`CADD_S` is not a configuration bit but the propagate signal of the LUTs (`carry_propagate` in `cpe.v`). It is
not gated by `C_ADDF` in the schematic, so it also matters for `C_FUNCTION` = 0, 4, 5, 7.
`CADD_A` is `carry_generate`, `MULTO2` the multiplier carry (`multo2`).

| C_FUNCTION | C_HORIZ | C_CX_I | C_SEL_C | C_SELX | C_Y12 | CADD_S | COUTX |
|---|---|---|---|---|---|---|---|
| - | - | 1 | 0 | 0 | - | - | OUT1 |
| - | - | 1 | 0 | 1 | - | - | OUT2 |
| - | - | 1 | 1 | 0 | - | - | COMP_OUT |
| - | - | 1 | 1 | 1 | 0 | - | CINY1 |
| - | - | 1 | 1 | 1 | 1 | - | CINY2 |
| 3 | 1 | 0 | - | - | - | - | MULTO2 |
| 3 | 0 | 0 | - | - | - | 1 | MULTO2 |
| 3 | 0 | 0 | 0 | 0 | - | 0 | OUT1 |
| 3 | 0 | 0 | 0 | 1 | - | 0 | OUT2 |
| 3 | 0 | 0 | 1 | 0 | - | 0 | COMP_OUT |
| 3 | 0 | 0 | 1 | 1 | 0 | 0 | CINY1 |
| 3 | 0 | 0 | 1 | 1 | 1 | 0 | CINY2 |
| 1, 2, 6 | 1 | 0 | - | - | - | - | CINX |
| 1, 2, 6 | 0 | 0 | - | - | - | 1 | CINX |
| 1, 2, 6 | 0 | 0 | - | - | - | 0 | CADD_A |
| 0, 4, 5, 7 | - | 0 | - | - | - | 1 | CINX |
| 0, 4, 5, 7 | - | 0 | - | - | - | 0 | CADD_A |

Reading hints:
- `C_CX_I = 1` always forces the `cx_route` branch (first five rows), independent of `C_FUNCTION`.
- `C_FUNCTION = 3` (multiplier) has `C_ADDF = 1`, so `C_HORIZ = 1` selects `MULTO2` as well.
- `C_Y12` only matters when `C_CX_I = 1` (or the multiplier case with `CADD_S = 0`) and `C_SEL_C = C_SELX = 1`.
- `C_SEL_C`, `C_SELX`, `C_Y12` have no effect on `COUTX` when `C_CX_I = 0` and `C_FUNCTION != 3`.
