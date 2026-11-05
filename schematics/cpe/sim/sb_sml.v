// GateMate small switch box (SB_SML), one plane.  Schematic: sb_sml.kicad_sch
//
// Like the large box (sb_big.v, which explains directions and inputs) but with only the wires
// of 2 and 4 CPEs, and with the inverter behind a 4:1 multiplexer per output instead of an 8:1:
//
//   Yn_int      = mux(D0, YDIAG_int, D2_n, D3_n)                      select value 0..3
//   YDIAG_int   = mux(Y1_int, Y2_int, Y3_int, Y4_int, X34, X14, X12, X23)   select value 0..7
//   Yn = ~Yn_int,  YDIAG = ~YDIAG_int
//
// The diagonal multiplexer reads the outputs before their inverters, so Yn_int is the inverse of
// Yn. The output stage "Yn_INT" of die.py, a 1-bit configuration that is always set when the box
// is used, is modelled as always on.
// (libgm: SB_SML.Pnn.Yn, 2 bits each; SB_SML.Pnn.YDIAG, 3 bits).
`timescale 1ns/1ps

module sb_sml #(
    parameter [1:0] SEL_Y1 = 2'd0,
    parameter [1:0] SEL_Y2 = 2'd0,
    parameter [1:0] SEL_Y3 = 2'd0,
    parameter [1:0] SEL_Y4 = 2'd0,
    parameter [2:0] SEL_YDIAG = 3'd0
) (
    input  D0,
    input  D2_1, D2_2, D2_3, D2_4,
    input  D3_1, D3_2, D3_3, D3_4,
    input  X12, X14, X23, X34,
    output Y1, Y2, Y3, Y4,
    output YDIAG
);
    wire Y1_int, Y2_int, Y3_int, Y4_int, YDIAG_int;

    wire [3:0] y1_in = {D3_1, D2_1, YDIAG_int, D0};
    wire [3:0] y2_in = {D3_2, D2_2, YDIAG_int, D0};
    wire [3:0] y3_in = {D3_3, D2_3, YDIAG_int, D0};
    wire [3:0] y4_in = {D3_4, D2_4, YDIAG_int, D0};
    wire [7:0] ydiag_in = {X23, X12, X14, X34, Y4_int, Y3_int, Y2_int, Y1_int};

    assign Y1_int    = y1_in[SEL_Y1];
    assign Y2_int    = y2_in[SEL_Y2];
    assign Y3_int    = y3_in[SEL_Y3];
    assign Y4_int    = y4_in[SEL_Y4];
    assign YDIAG_int = ydiag_in[SEL_YDIAG];

    assign Y1    = ~Y1_int;
    assign Y2    = ~Y2_int;
    assign Y3    = ~Y3_int;
    assign Y4    = ~Y4_int;
    assign YDIAG = ~YDIAG_int;
endmodule
