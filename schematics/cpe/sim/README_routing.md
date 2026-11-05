# Routing fabric model (IM, OM, SB, 2x2 tile, 4x4 tile)

Verilog models of the GateMate routing next to `cpe.v`. They are meant to be read: the model is hand-written,
one module per file, with the chip's geometry in the comments. Only the testbenches are generated (from
`gatemate/die.py`, from `libgm` and from the schematic). Unlike `cpe.v` the files use SystemVerilog-style packed arrays
and `generate` (`iverilog -g2012`), because indexing by plane, direction and relative position is what makes
them readable.

## Hierarchy

| File | Content |
|------|---------|
| `im.v` | input mux, **one** 8:1 mux + NOT (`im.kicad_sch` has 12 of them, one per plane) |
| `om.v` | output mux, one 4:1 mux + NOT |
| `sb_big.v`, `sb_sml.v` | one plane of a large / small switch box; ports are named like the schematic pins (`D2_1`, `X14`, ...) |
| `sb_drive.v` | one long wire repeater of a large switch box (plane and direction) |
| `tile2x2.v` | 2x2 CPEs with their 12 planes: `generate for` over CPE (x, y), plane p = 1..12, direction i = 1..4. Parameter `BIG11` says which of the two switch boxes is the large one, parameter `CFG` is the configuration |
| `tile4x4.v` | **the unit the chip is built of**: 2x2 tiles of 2x2 CPEs. The wiring is written per CPE (cx, cy) with relative coordinates: `sb_y[cx - 2][cy]` is the box two CPEs to the west. Each 2x2 tile has its own configuration parameter |

Planes are numbered like in the schematics (1..12), CPEs by their relative position in the tile
(x, y in 0..1; the schematics call (0,0) CPE11, (0,1) CPE12, (1,0) CPE21, (1,1) CPE22).

What is wired where: `tile2x2` has what the schematic sheets `om11`/`om22` and `im` fix inside a 2x2 block (CPE outputs to
OM and switch box D0, IM planes 6 and 7, YDIAG of neighbouring planes). Everything that depends on the position on
the chip (switch box to IM, switch box to switch box, diagonals, carry chain) is in `tile4x4`. Wires from outside the unit are the
inputs `ext_*` of `tile4x4`; wires of 4 CPEs and more always are. Polarity: every mux in `im`, `om11/22`,
`sb_big`, `sb_sml` is followed by a NOT, so every IM, OM and SB on a path inverts, and `SB_DRIVE.OUT` once more.

## Configuration: the bitstream format

`tile2x2` has the parameter `CFG`: the configuration of a core tile exactly as the bitstream (and libgm) holds it, 113 bytes =
904 bits. Byte n is `CFG[8n+7:8n]`, the lowest bit of a byte comes first, a setting of w bits at bit b is `CFG[b +: w]`, lowest bit
first. `tile4x4` has one such parameter per 2x2 tile, `CFG_X0Y0`, `CFG_X1Y0`, `CFG_X0Y1`, `CFG_X1Y1` (tile x and y), because the
configuration stream sets the tiles one by one.

| Bytes | Content |
|-------|---------|
| 0..39 | the four CPEs, 10 bytes each (CPE c = 2x+y+1): all the settings of `cpe.v`, in the order of libgm's `add_cpe` |
| 40..63 | the four IMs, 6 bytes each; per byte plane 2j+1 in bits 2:0 and plane 2j+2 in bits 5:3 |
| 54..57, 60..63 | OM1 (`s`=0) and OM4 (`s`=1), planes 9..12, bits 7:6 of these bytes |
| 64..93 | SB_BIG, 5 bytes per two planes: YDIAG, Y1..Y4 (3 bits each), and between the planes one byte with the 4 SB_DRIVE bits of each |
| 94..111 | SB_SML, 3 bytes per two planes: YDIAG (3 bits), Y1..Y4 (2 bits each) |
| 112 | FF_INIT, 2 bits per CPE: 2 = registers start with Q = 0, 3 = with Q = 1, 0 and 1 = not initialised |

`tile2x2.v` has the positions as small functions (`im_bit`, `om_bit`, `sb_big_bit`, `sb_sml_bit`, `sb_drive_bit`, `cpe_bit`, `ff_init_bit`), with the layout in
the comments. The elements keep their select parameters (`SEL`, `SEL_Y1..4`, `SEL_YDIAG`, `EN`); the tile sets them from `CFG`. A tile has both
kinds of switch box configuration: the large box takes the SB_BIG bits and the small one the SB_SML bits, wherever they are.

`FF_INIT` is a parameter of `cpe.v` for the model only: on the chip the bitstream loader brings the registers into their start state by
pulsing the set or reset input while it configures the CPE, which a parameter cannot do afterwards. A model needs it as a
parameter. (With `C_CPE_SET` = `C_CPE_RES` = 0 set and reset are active all the time and override the start state.)

`libgm_layout.py` reads the offsets from `libgm/src/TileBitDatabase.cpp` (the `add_*` functions) and checks that the constructor
is still the one it knows, so the tests follow libgm and stop if the layout changes. With it a block can be put together by name:

    cfg = TileCfg(core_layout()); cfg.set("SB_BIG.P03.Y1", 2); cfg.set("IM2.P05", 7)
    tile2x2 #(.BIG11(1), .CFG(cfg.literal())) ...

Instance names, for looking at the elements (the select parameters then show what the tile decoded):

    dut.tile_x[tx].tile_y[ty].u_tile                      2x2 tile at CPE (2 tx, 2 ty) of a tile4x4
        .col[x].row[y].u_cpe                              the CPE
        .col[x].row[y].plane[p].u_im                      its IM plane p
        .om[s].plane[q].u_om                              OM at CPE (s, s), q = 9..12
        .sb[s].plane[p].big.u_sb | .sml.u_sb              switch box at CPE (s, s)
        .sb[s].plane[p].big.dir[i].u_drv                  its repeater

## Tests

`python routing_tests.py` writes the testbenches (it needs `libgm_layout.py`), `python check_routing.py` the ones made from the schematic
(and compares the schematic with die.py). All end with `PASS`.

    P="im.v om.v sb_big.v sb_sml.v sb_drive.v"; T="$P tile2x2.v"
    iverilog -g2012 -o t.vvp $P tb_modules.v && vvp t.vvp                              # also tb_modules_sch.v
    iverilog -g2012 -o t.vvp $T cpe_stub.v tb_tile2x2_big11.v && vvp t.vvp             # also big22, *_sch.v
    iverilog -g2012 -o t.vvp $T tile4x4.v cpe_stub.v tb_cfg.v && vvp t.vvp
    iverilog -g2012 -o t.vvp $T tile4x4.v cpe.v tb_tile4x4.v && vvp t.vvp
    iverilog -g2012 -o t.vvp $T tile4x4.v cpe_stub.v tb_wiring.v && vvp t.vvp
    iverilog -g2012 -o t.vvp cpe.v tb_ff_init.v && vvp t.vvp                           # hand-written

| Testbench | Checks |
|-----------|--------|
| `tb_modules.v`, `tb_modules_sch.v` | each single-plane module, every select value, against the mux table of die.py / the schematic |
| `tb_tile2x2_*.v`, `tb_tile2x2_*_sch.v` | wiring inside the tile for both values of `BIG11` (CPE outputs set through `cpe_stub.v`): every OM select value, switch box D0, IM planes 6/7, YDIAG of neighbouring planes; the `_sch` variants take the wiring from `om11`/`om22`/`im` (only die.py has X14/X23) |
| `tb_cfg.v` | the bit positions: random configuration blocks go into the tile (both values of `BIG11`), and every parameter of every CPE, IM, OM, switch box and repeater, `FF_INIT` included, has to equal the libgm word at the position `libgm_layout.py` has for it (about 2500 words); and every `CFG_XtxYty` of `tile4x4` has to reach its 2x2 tile |
| `tb_tile4x4.v` | routes through the unit at the same time, across tiles and through IM, SB_SML, SB_BIG, SB_DRIVE; configured from the mux table of die.py |
| `tb_wiring.v` | **every** connection of the unit, in six configurations: IM inputs D0..D5, switch box inputs D2..D7, X12 / X34 and the carry and propagate chain, all planes, all positions, against `Die.create_cpe / create_inmux / create_sb`. Also the `ext_*` port a wire from outside has to come in on |
| `tb_ff_init.v` | `FF_INIT` of `cpe.v` for the flip-flops and the latches (hand-written) |

## Comparison with the schematic (`check_routing.py`)

1. Mux tables of `im`, `om11`, `om22`, `sb_big`, `sb_sml` (data pin Dk of a MUX4B/MUX8B -> label behind the NOT)
   against die.py: 96 + 16 + 16 + 480 + 288 entries, identical.
2. The single-plane modules against the schematic table (`tb_modules_sch.v`).
3. The wiring of the tile against the labels of `om11`/`om22` and the nets of `im` (112 OM input / SB D0 wires of both
   tile kinds, 24 IM D6/D7 sources): identical, and `tb_tile2x2_*_sch.v` checks the Verilog against it.
4. Top level `prjpeppercorn.kicad_sch`: all 32 wire-made nets between sheets agree with the connection database
   of the same 4x4 window. That covers plane 1 only, and 54 connections of die.py are not drawn there
   (diagonal IM links, SB to SB wires, X12/X34).

Not covered by the schematic, so only checked against die.py: the select encoding (the MUX symbols have no select pin; value k is taken
as data pin Dk), `SB_DRIVE`, the always-on `Yn_INT` stage of `SB_SML`, X14/X23, everything of the unit beyond plane 1.
Not covered by the tests: wires between two 4x4 tiles are only checked as far as the `ext_*` port they have to use (the
wires of 4 CPEs and more all come in there); composing several units is left to the parent. Not modelled: LES/BES/RES/TES,
IOES/GPIO, RAM, PLL, SERDES, global mesh, D2D. `SB_DRIVE` with `EN` = 0 and the repeaters of small boxes drive `x`.
`RAM_I1/2` of the CPEs are tied low.

Notes on the schematic:

- `im.kicad_sch` caches its NOT symbols as `NOT_12` ... `NOT_23` while the instances say `prjpeppercorn:NOT`, so
  `netlist.build` finds no pins on them. `check_routing.py` aliases the symbol; the sheet itself was not changed.
- At the top level the OM and CPE pins are tied by label name only (`CPE11.OUT1` and so on), and the same names are
  used by all four 2x2 blocks, so the labels join the four blocks. Only the wires are compared (step 4).

`check_routing.py` needs `kisch.py` and `netlist.py` from this directory (or from `$GM_SIM_TOOLS`).
