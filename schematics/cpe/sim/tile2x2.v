// GateMate 2x2 tile: four CPEs with their input multiplexers, output multiplexers and switch boxes.
//
// The fabric is built of these. Coordinates inside the tile are relative: a CPE is (x, y) with
// x, y in 0..1. In the schematics (0,0) is called CPE11, (0,1) CPE12, (1,0) CPE21, (1,1) CPE22.
//
//        y=1   CPE (0,1)     CPE (1,1) + SB + OM
//        y=0   CPE (0,0) + SB + OM     CPE (1,0)
//                  x=0           x=1
//
// A switch box (SB) and an output multiplexer (OM) sit at every CPE with x == y (mod 2), so the tile has
// two of each: s = 0 at CPE (0,0) and s = 1 at CPE (1,1). One is a large box (sb_big), one a small
// box (sb_sml), and which is which alternates over the chip:
//     BIG11 = 1   the large box is at CPE (0,0), the small one at CPE (1,1)
//     BIG11 = 0   the other way round
//
// Everything is replicated over the 12 planes of the routing. Planes are numbered like in the
// schematics, 1..12; plane p of any element only talks to plane p of its neighbours, except where noted.
//
// What is wired here is what the schematics fix inside a 2x2 block:
//   - CPE outputs OUT1, OUT2  ->  OM inputs and, for the planes 1..8, D0 of the switch box
//   - OM outputs              ->  D0 of the switch box for the planes 9..12
//   - IM outputs              ->  IN1..IN8, CLK, EN, SR of the CPE (planes 1..11)
//   - IM planes               ->  D6, D7 of IM planes (see below)
//   - switch box YDIAG        ->  X14, X23 of the neighbouring planes
//   - switch box Y            ->  SB_DRIVE
// Everything that reaches over the tile border is a port; tile4x4.v wires them.
//
// Port indices: [x][y] a CPE, [s] a switch box or OM, [p] a plane 1..12, [i] the direction 1..4 of
// a switch box wire (see sb_big.v), [k] the input number Dk.
//
// Configuration: the parameter CFG is the configuration of the tile exactly as the bitstream holds it,
// the 113 bytes of a core tile (libgm: TileBitDatabase, Die::LATCH_BLOCK_SIZE). Byte n is CFG[8n+7:8n] and
// the lowest bit of a byte comes first; a setting of w bits at bit b is CFG[b +: w], lowest bit first.
//
//    byte    0..39     the four CPEs, 10 bytes each: CPE c = 2x+y+1 at byte 10(c-1)
//           40..63     the four IMs, 6 bytes each: IM c at byte 40 + 6(c-1); in a byte plane 2j+1 is in
//                      bits 2:0 and plane 2j+2 in bits 5:3 (3 bits: the select value)
//           54..57     OM1 (s=0), planes 9..12, bits 7:6 of these bytes (2 bits), they share the
//           60..63     OM4 (s=1)   bytes with the IMs of CPE3 and CPE4
//           64..93     SB_BIG, 5 bytes per two planes, see sb_big_bit()
//           94..111    SB_SML, 3 bytes per two planes, see sb_sml_bit()
//          112         FF_INIT, 2 bits per CPE c at bits 2(c-1)+1:2(c-1) of this byte (start state of the registers)
//
// Every tile has both kinds of switch box configuration; the large box of this tile takes the SB_BIG
// bits and the small one the SB_SML bits, whatever their position.
//
// Instance names: col[x].row[y].u_cpe / .plane[p].u_im, sb[s].plane[p].big|sml.u_sb (+ .dir[i].u_drv),
// om[s].plane[q].u_om
`timescale 1ns/1ps

module tile2x2 #(
    parameter BIG11 = 1,
    parameter [903:0] CFG = 904'd0
) (
    // ---- CPEs
    input  [1:0][1:0][12:1][5:0] im_d,                 // IM inputs D0..D5 (D6, D7 are internal)
    output [1:0][1:0][12:1]      im_y,                 // IM outputs
    input  [1:0][1:0] cinx, ciny1, ciny2, pinx, piny1, piny2,        // carry and propagate in
    output [1:0][1:0] coutx, couty1, couty2, poutx, pouty1, pouty2,  // and out
    // ---- switch boxes; the large one has the inputs D4..D7 and the SB_DRIVE outputs, the small one ignores
    // ---- the first and leaves the second at x
    input  [1:0][12:1][4:1][7:2] sb_d,                 // Dk_i, k = 2..7
    input  [1:0][12:1]           sb_x12, sb_x34,       // YDIAG of the boxes at (-1,-1) and (+1,+1)
    output [1:0][12:1][4:1]      sb_y,
    output [1:0][12:1]           sb_ydiag,
    output [1:0][12:1][4:1]      sb_drv, sb_drvn       // SB_DRIVE OUT and OUT_NOINV
);
    genvar x, y, s, p, q, i;

    // ---------------------------------------------------------------------------------------------
    // Where the settings are in CFG
    // ---------------------------------------------------------------------------------------------

    // CPE (x, y): 80 bits from byte 10(2x+y); the setting names are those of cpe.v (libgm: CPEc.name)
    function integer cpe_bit(input integer x, input integer y);
        cpe_bit = 80 * (2 * x + y);
    endfunction

    // FF_INIT of CPE (x, y): 2 bits in the last byte
    function integer ff_init_bit(input integer x, input integer y);
        ff_init_bit = 8 * 112 + 2 * (2 * x + y);
    endfunction

    // IM plane p of CPE (x, y): 3 bits
    function integer im_bit(input integer x, input integer y, input integer p);
        im_bit = 8 * (40 + 6 * (2 * x + y) + (p - 1) / 2) + 3 * ((p - 1) % 2);
    endfunction

    // OM s, plane q = 9..12: 2 bits
    function integer om_bit(input integer s, input integer q);
        om_bit = 8 * (54 + 6 * s + (q - 9)) + 6;
    endfunction

    // Large switch box, plane p: from byte 64, two planes per 5 bytes. The odd plane takes the first two bytes
    // and the even plane the last two, the byte between them has the 4 SB_DRIVE bits of both:
    //    +0 YDIAG (3 bits)  +3 Y1  +6 Y2  +9 Y3  +12 Y4 (3 bits each)
    function integer sb_big_bit(input integer p);
        sb_big_bit = 8 * (64 + 5 * ((p - 1) / 2)) + 24 * ((p - 1) % 2);
    endfunction

    // SB_DRIVE direction i = 1..4 of plane p: one bit
    function integer sb_drive_bit(input integer p, input integer i);
        sb_drive_bit = 8 * (64 + 5 * ((p - 1) / 2) + 2) + 4 * ((p - 1) % 2) + (i - 1);
    endfunction

    // Small switch box, plane p: from byte 94, two planes per 3 bytes (the even plane starts in the middle of the
    // second byte):
    //    +0 YDIAG (3 bits)  +3 Y1  +5 Y2  +7 Y3  +9 Y4 (2 bits each)
    function integer sb_sml_bit(input integer p);
        sb_sml_bit = 8 * (94 + 3 * ((p - 1) / 2)) + (8 + 4) * ((p - 1) % 2);
    endfunction

    // ---------------------------------------------------------------------------------------------
    // Helpers for the wiring, all evaluated while the tile is built
    // ---------------------------------------------------------------------------------------------

    // IM plane p reads the output of two other planes of the same IM on D6 and D7 (im.kicad_sch):
    //    plane   1  2  3  4  5  6  7  8   9 10 11 12
    //    D6      5  6  7  8  1  2  3  4  11 12  9 10
    //    D7      9 10 11 12  9 10 11 12  12 11 10  9
    function integer im_d6(input integer p);
        im_d6 = (p <= 4) ? p + 4 : (p <= 8) ? p - 4 : (p <= 10) ? p + 2 : p - 2;
    endfunction

    function integer im_d7(input integer p);
        im_d7 = (p <= 8) ? 9 + (p - 1) % 4 : 21 - p;
    endfunction

    // The planes 1..8 of the switch box s take D0 from the CPE at (x, y) = (bit 1, bit 0) of p-1,
    // and from its output OUT1 or OUT2 (om11.kicad_sch / om22.kicad_sch list the nets):
    //    plane            1     2     3     4     5     6     7     8
    //    box s=0 gets   (0,0)  (0,1)  (1,0)  (1,1)  (0,0)  (0,1)  (1,0)  (1,1)
    //                   OUT2   OUT1   OUT2   OUT1   OUT1   OUT2   OUT1   OUT2
    //    box s=1 gets the same CPEs with the other output.
    function integer sb_cpe_out(input integer s, input integer p);
        reg flip;
        begin
            flip = ((p - 1) ^ ((p - 1) >> 2)) & 1;
            sb_cpe_out = (flip == s) ? 2 : 1;
        end
    endfunction

    // The OM s, plane q = 9..12, input k takes the output of CPE (x, y) = (k >> 1, k & 1), OUT1 or OUT2:
    //    OM s=0, planes 9 and 11:  OUT2 OUT2 OUT1 OUT1  for k = 0..3,  planes 10 and 12: OUT1 OUT1 OUT2 OUT2
    //    OM s=1 is the other way round.
    function integer om_cpe_out(input integer s, input integer q, input integer k);
        reg lower_is_out2;                         // inputs 0 and 1 (CPE column 0) take OUT2
        begin
            lower_is_out2 = ((q + s) % 2) == 1;
            om_cpe_out = ((k < 2) == lower_is_out2) ? 2 : 1;
        end
    endfunction

    // ---------------------------------------------------------------------------------------------
    // CPEs, each with its input multiplexer
    // ---------------------------------------------------------------------------------------------

    wire [2:1][1:0][1:0] cpe_out;          // cpe_out[n][x][y] is OUTn of CPE (x, y)

    generate
        for (x = 0; x < 2; x = x + 1) begin : col
            for (y = 0; y < 2; y = y + 1) begin : row
                localparam B = cpe_bit(x, y);       // first bit of this CPE in CFG

                cpe #(
                    .INIT_L00(CFG[B +  0 +: 4]), .INIT_L01(CFG[B +  4 +: 4]),
                    .INIT_L02(CFG[B +  8 +: 4]), .INIT_L03(CFG[B + 12 +: 4]),
                    .INIT_L10(CFG[B + 16 +: 4]), .INIT_L11(CFG[B + 20 +: 4]),
                    .INIT_L20(CFG[B + 24 +: 4]), .INIT_L30(CFG[B + 28 +: 4]),
                    .C_I1(CFG[B + 32]), .C_I2(CFG[B + 33]), .C_I3(CFG[B + 34]), .C_I4(CFG[B + 35]),
                    .C_FUNCTION(CFG[B + 36 +: 3]),
                    .C_COMP(CFG[B + 39]), .C_COMP_I(CFG[B + 40]), .C_HORIZ(CFG[B + 41]),
                    .C_SELX(CFG[B + 42]), .C_SELY1(CFG[B + 43]), .C_SELY2(CFG[B + 44]),
                    .C_SEL_C(CFG[B + 45]), .C_SEL_P(CFG[B + 46]), .C_Y12(CFG[B + 47]),
                    .C_CX_I(CFG[B + 48]), .C_CY1_I(CFG[B + 49]), .C_CY2_I(CFG[B + 50]),
                    .C_PX_I(CFG[B + 51]), .C_PY1_I(CFG[B + 52]), .C_PY2_I(CFG[B + 53]),
                    .C_C_P(CFG[B + 54]), .C_2D_IN(CFG[B + 55]),
                    .C_SN(CFG[B + 56 +: 3]), .C_O1(CFG[B + 59 +: 2]), .C_O2(CFG[B + 61 +: 2]), .C_BR(CFG[B + 63]),
                    .C_CPE_CLK(CFG[B + 64 +: 2]), .C_CPE_EN(CFG[B + 66 +: 2]),
                    .C_CPE_RES(CFG[B + 68 +: 2]), .C_CPE_SET(CFG[B + 70 +: 2]),
                    .C_RAM_I1(CFG[B + 72]), .C_RAM_I2(CFG[B + 73]), .C_RAM_O1(CFG[B + 74]), .C_RAM_O2(CFG[B + 75]),
                    .C_L_D(CFG[B + 76]), .C_EN_SR(CFG[B + 77]), .C_CLKSEL(CFG[B + 78]), .C_ENSEL(CFG[B + 79]),
                    .FF_INIT(CFG[ff_init_bit(x, y) +: 2])
                ) u_cpe (
                    .IN1(im_y[x][y][1]), .IN2(im_y[x][y][2]), .IN3(im_y[x][y][3]), .IN4(im_y[x][y][4]),
                    .IN5(im_y[x][y][5]), .IN6(im_y[x][y][6]), .IN7(im_y[x][y][7]), .IN8(im_y[x][y][8]),
                    .CLK(im_y[x][y][9]), .EN(im_y[x][y][10]), .SR(im_y[x][y][11]),
                    .CINX(cinx[x][y]), .CINY1(ciny1[x][y]), .CINY2(ciny2[x][y]),
                    .PINX(pinx[x][y]), .PINY1(piny1[x][y]), .PINY2(piny2[x][y]),
                    .RAM_I1(1'b0), .RAM_I2(1'b0), .RAM_O1(), .RAM_O2(),
                    .OUT1(cpe_out[1][x][y]), .OUT2(cpe_out[2][x][y]),
                    .COUTX(coutx[x][y]), .COUTY1(couty1[x][y]), .COUTY2(couty2[x][y]),
                    .POUTX(poutx[x][y]), .POUTY1(pouty1[x][y]), .POUTY2(pouty2[x][y])
                );

                for (p = 1; p <= 12; p = p + 1) begin : plane
                    im #(.SEL(CFG[im_bit(x, y, p) +: 3])) u_im (
                        .D0(im_d[x][y][p][0]), .D1(im_d[x][y][p][1]), .D2(im_d[x][y][p][2]),
                        .D3(im_d[x][y][p][3]), .D4(im_d[x][y][p][4]), .D5(im_d[x][y][p][5]),
                        .D6(im_y[x][y][im_d6(p)]), .D7(im_y[x][y][im_d7(p)]),
                        .Y(im_y[x][y][p])
                    );
                end
            end
        end
    endgenerate

    // ---------------------------------------------------------------------------------------------
    // Output multiplexers, planes 9..12
    // ---------------------------------------------------------------------------------------------

    wire [1:0][12:9] om_y;                 // om_y[s][q]

    generate
        for (s = 0; s < 2; s = s + 1) begin : om
            for (q = 9; q <= 12; q = q + 1) begin : plane
                om #(.SEL(CFG[om_bit(s, q) +: 2])) u_om (
                    .D0(cpe_out[om_cpe_out(s, q, 0)][0][0]), .D1(cpe_out[om_cpe_out(s, q, 1)][0][1]),
                    .D2(cpe_out[om_cpe_out(s, q, 2)][1][0]), .D3(cpe_out[om_cpe_out(s, q, 3)][1][1]),
                    .Y(om_y[s][q])
                );
            end
        end
    endgenerate

    // ---------------------------------------------------------------------------------------------
    // Switch boxes; box s sits at the CPE (s, s)
    // ---------------------------------------------------------------------------------------------

    generate
        for (s = 0; s < 2; s = s + 1) begin : sb
            localparam IS_BIG = (s == 0) ? (BIG11 != 0) : (BIG11 == 0);

            for (p = 1; p <= 12; p = p + 1) begin : plane
                localparam P_PREV = (p == 1) ? 12 : p - 1;
                localparam P_NEXT = (p == 12) ? 1 : p + 1;

                wire d0;
                if (p <= 8) begin : d0_from_cpe
                    assign d0 = cpe_out[sb_cpe_out(s, p)][((p - 1) >> 1) & 1][(p - 1) & 1];
                end else begin : d0_from_om
                    assign d0 = om_y[s][p];
                end

                if (IS_BIG) begin : big
                    localparam B = sb_big_bit(p);
                    sb_big #(
                        .SEL_YDIAG(CFG[B +  0 +: 3]), .SEL_Y1(CFG[B + 3 +: 3]), .SEL_Y2(CFG[B + 6 +: 3]),
                        .SEL_Y3(CFG[B + 9 +: 3]), .SEL_Y4(CFG[B + 12 +: 3])
                    ) u_sb (
                        .D0(d0),
                        .D2_1(sb_d[s][p][1][2]), .D2_2(sb_d[s][p][2][2]), .D2_3(sb_d[s][p][3][2]), .D2_4(sb_d[s][p][4][2]),
                        .D3_1(sb_d[s][p][1][3]), .D3_2(sb_d[s][p][2][3]), .D3_3(sb_d[s][p][3][3]), .D3_4(sb_d[s][p][4][3]),
                        .D4_1(sb_d[s][p][1][4]), .D4_2(sb_d[s][p][2][4]), .D4_3(sb_d[s][p][3][4]), .D4_4(sb_d[s][p][4][4]),
                        .D5_1(sb_d[s][p][1][5]), .D5_2(sb_d[s][p][2][5]), .D5_3(sb_d[s][p][3][5]), .D5_4(sb_d[s][p][4][5]),
                        .D6_1(sb_d[s][p][1][6]), .D6_2(sb_d[s][p][2][6]), .D6_3(sb_d[s][p][3][6]), .D6_4(sb_d[s][p][4][6]),
                        .D7_1(sb_d[s][p][1][7]), .D7_2(sb_d[s][p][2][7]), .D7_3(sb_d[s][p][3][7]), .D7_4(sb_d[s][p][4][7]),
                        .X12(sb_x12[s][p]), .X34(sb_x34[s][p]),
                        .X14(sb_ydiag[s][P_PREV]), .X23(sb_ydiag[s][P_NEXT]),
                        .Y1(sb_y[s][p][1]), .Y2(sb_y[s][p][2]), .Y3(sb_y[s][p][3]), .Y4(sb_y[s][p][4]),
                        .YDIAG(sb_ydiag[s][p])
                    );
                    for (i = 1; i <= 4; i = i + 1) begin : dir
                        sb_drive #(.EN(CFG[sb_drive_bit(p, i)])) u_drv (
                            .IN(sb_y[s][p][i]), .OUT(sb_drv[s][p][i]), .OUT_NOINV(sb_drvn[s][p][i])
                        );
                    end
                end else begin : sml
                    localparam B = sb_sml_bit(p);
                    sb_sml #(
                        .SEL_YDIAG(CFG[B + 0 +: 3]), .SEL_Y1(CFG[B + 3 +: 2]), .SEL_Y2(CFG[B + 5 +: 2]),
                        .SEL_Y3(CFG[B + 7 +: 2]), .SEL_Y4(CFG[B + 9 +: 2])
                    ) u_sb (
                        .D0(d0),
                        .D2_1(sb_d[s][p][1][2]), .D2_2(sb_d[s][p][2][2]), .D2_3(sb_d[s][p][3][2]), .D2_4(sb_d[s][p][4][2]),
                        .D3_1(sb_d[s][p][1][3]), .D3_2(sb_d[s][p][2][3]), .D3_3(sb_d[s][p][3][3]), .D3_4(sb_d[s][p][4][3]),
                        .X12(sb_x12[s][p]), .X34(sb_x34[s][p]),
                        .X14(sb_ydiag[s][P_PREV]), .X23(sb_ydiag[s][P_NEXT]),
                        .Y1(sb_y[s][p][1]), .Y2(sb_y[s][p][2]), .Y3(sb_y[s][p][3]), .Y4(sb_y[s][p][4]),
                        .YDIAG(sb_ydiag[s][p])
                    );
                    for (i = 1; i <= 4; i = i + 1) begin : dir
                        assign sb_drv[s][p][i]  = 1'bx;        // no repeater in a small box
                        assign sb_drvn[s][p][i] = 1'bx;
                    end
                end
            end
        end
    endgenerate
endmodule
