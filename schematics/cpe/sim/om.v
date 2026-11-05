// GateMate output multiplexer (OM), one plane.  Schematics: om11.kicad_sch, om22.kicad_sch
//
// A 2x2 block of CPEs has two OMs, one at CPE (0,0) and one at CPE (1,1), each with the planes 9..12.
// A plane is one 4:1 multiplexer followed by an inverter. Its output is D0 of the switch box of the
// same plane at the same CPE. Planes 1..8 of that box take D0 directly from a CPE output instead.
//
// Inputs: one output (OUT1 or OUT2) of each CPE of the 2x2 block, in the order
//   D0 = CPE (0,0)   D1 = CPE (0,1)   D2 = CPE (1,0)   D3 = CPE (1,1)
// Which of the two outputs it is depends on the plane, see tile2x2.v.
//
// Select value k connects input Dk (libgm: OM.Pnn, 2 bits).
`timescale 1ns/1ps

module om #(
    parameter [1:0] SEL = 2'd0
) (
    input  D0, D1, D2, D3,
    output Y
);
    wire [3:0] d = {D3, D2, D1, D0};

    assign Y = ~d[SEL];
endmodule
