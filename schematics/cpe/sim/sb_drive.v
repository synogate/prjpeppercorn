// GateMate long wire repeater (SB_DRIVE), one per plane and direction of a large switch box.
//
// IN is the output Yn of the box. The repeater feeds the long wires D4_n .. D7_n of the boxes 8, 12, 16
// and 20 CPEs away in direction n. On its way the signal passes an inverter in every 8x8 tile
// border; die.py models that by picking OUT (inverted) or OUT_NOINV (plain) at the receiving
// end, depending on whether the number of tiles crossed is odd or even.
//
// EN is the configuration bit (libgm: SB_DRIVE.Pnn.Dn). Without it nothing drives the wire,
// modelled as x.
`timescale 1ns/1ps

module sb_drive #(
    parameter EN = 1'b0
) (
    input  IN,
    output OUT,
    output OUT_NOINV
);
    assign OUT       = EN ? ~IN : 1'bx;
    assign OUT_NOINV = EN ?  IN : 1'bx;
endmodule
