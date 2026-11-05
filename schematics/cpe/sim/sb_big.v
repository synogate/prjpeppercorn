// GateMate large switch box (SB_BIG), one plane.  Schematic: sb_big.kicad_sch
//
// The switch boxes make up the routing grid. There is one at every CPE whose x and y have the same parity
// (every second CPE, as on a chessboard), 12 planes each, and the planes do not mix, except through
// the diagonal wires X14 and X23 and the diagonal outputs. Boxes alternate between large (this
// module) and small (sb_sml.v) in a pattern of period 4.
//
// Y1..Y4 are the four outputs, each an 8:1 multiplexer followed by an inverter. They run in the
// directions
//         Y1  towards +x (east)        Y2  towards +y (north)
//         Y3  towards -x (west)        Y4  towards -y (south)
// so an input that receives Yi comes from the opposite side: D2_1 is fed by the box to the west.
//
// Inputs, with n = 1..4 the direction of the wire and the distance counted in CPEs:
//   D0      own CPE output (planes 1..8) or the OM (planes 9..12)
//   D2_n    Yn of the box 2 CPEs away
//   D3_n    Yn of the box 4 CPEs away
//   D4_n .. D7_n   the long wires, 8, 12, 16 and 20 CPEs away, which come through the SB_DRIVE
//           repeater of the far box (sb_drive.v)
//   X12     YDIAG of the box at (-1,-1)           X34     YDIAG of the box at (+1,+1)
//   X14     YDIAG of the previous plane          X23     YDIAG of the next plane (same box)
//
// Yn          = ~mux(D0, YDIAG, D2_n, D3_n, D4_n, D5_n, D6_n, D7_n)     select value 0..7
// YDIAG       = ~mux(Y1, Y2, Y3, Y4, X34, X14, X12, X23)                select value 0..7
// Select value k connects the k-th input of that list (libgm: SB_BIG.Pnn.Yn, 3 bits each).
`timescale 1ns/1ps

module sb_big #(
    parameter [2:0] SEL_Y1 = 3'd0,
    parameter [2:0] SEL_Y2 = 3'd0,
    parameter [2:0] SEL_Y3 = 3'd0,
    parameter [2:0] SEL_Y4 = 3'd0,
    parameter [2:0] SEL_YDIAG = 3'd0
) (
    input  D0,
    input  D2_1, D2_2, D2_3, D2_4,
    input  D3_1, D3_2, D3_3, D3_4,
    input  D4_1, D4_2, D4_3, D4_4,
    input  D5_1, D5_2, D5_3, D5_4,
    input  D6_1, D6_2, D6_3, D6_4,
    input  D7_1, D7_2, D7_3, D7_4,
    input  X12, X14, X23, X34,
    output Y1, Y2, Y3, Y4,
    output YDIAG
);
    wire [7:0] y1_in = {D7_1, D6_1, D5_1, D4_1, D3_1, D2_1, YDIAG, D0};
    wire [7:0] y2_in = {D7_2, D6_2, D5_2, D4_2, D3_2, D2_2, YDIAG, D0};
    wire [7:0] y3_in = {D7_3, D6_3, D5_3, D4_3, D3_3, D2_3, YDIAG, D0};
    wire [7:0] y4_in = {D7_4, D6_4, D5_4, D4_4, D3_4, D2_4, YDIAG, D0};
    wire [7:0] ydiag_in = {X23, X12, X14, X34, Y4, Y3, Y2, Y1};

    assign Y1    = ~y1_in[SEL_Y1];
    assign Y2    = ~y2_in[SEL_Y2];
    assign Y3    = ~y3_in[SEL_Y3];
    assign Y4    = ~y4_in[SEL_Y4];
    assign YDIAG = ~ydiag_in[SEL_YDIAG];
endmodule
