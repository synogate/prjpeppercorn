// GateMate input multiplexer (IM), one plane.  Schematic: im.kicad_sch
//
// Every CPE has an IM with 12 planes. A plane is one 8:1 multiplexer followed by an inverter, so
// the signal that reaches the CPE is inverted (the LUT contents take care of that).
//
//   plane   1  2  3  4  5  6  7  8   9    10  11   12
//   Y to    IN1 IN2 IN3 IN4 IN5 IN6 IN7 IN8 CLK EN  SR  (none, only read by other IM planes)
//
// Inputs, with (dx, dy) the position relative to the CPE this IM belongs to:
//   D0..D3  Y1..Y4 of the switch box next to the CPE (the same plane), see sb_big.v for the
//           directions. The box sits 1 CPE away, or 2 CPEs if this CPE has a box of its own.
//           D0 comes from the west (-1,0), D1 from the south (0,-1), D2 from the east (+1,0),
//           D3 from the north (0,+1).
//   D4, D5  Y of the same plane of the IM of the CPE at (-1,-1) and (+1,+1)
//   D6, D7  Y of two other planes of this very IM, see tile2x2.v
//
// Select value k connects input Dk (libgm: IM.Pnn, 3 bits).
`timescale 1ns/1ps

module im #(
    parameter [2:0] SEL = 3'd0
) (
    input  D0, D1, D2, D3,
    input  D4, D5,
    input  D6, D7,
    output Y
);
    wire [7:0] d = {D7, D6, D5, D4, D3, D2, D1, D0};

    assign Y = ~d[SEL];
endmodule
