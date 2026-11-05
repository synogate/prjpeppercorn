// GateMate 4x4 tile: 4x4 CPEs, made of 2x2 tiles of 2x2 CPEs (tile2x2.v). This is the unit the chip is built of.
//
//        tile (0,1)   tile (1,1)          CPE (cx, cy), cx and cy from 0 at the lower left corner;
//        tile (0,0)   tile (1,0)          tile (tx, ty) holds the CPEs (2tx..2tx+1, 2ty..2ty+1)
//
// This module shows how the chip is wired: which output goes to which input. The wiring is written
// per CPE (cx, cy) with the neighbours found by relative coordinates, so source and destination of
// every wire are next to each other in the text.
//
// The unit repeats over the chip. Wires that come from a neighbouring unit are taken from the ports ext_*,
// which have the shape of the inputs they feed; only the entries whose source lies outside are used. The
// wires of 4 CPEs and more (Dk_i with k >= 3) always come from outside, as do the long wires of 8 CPEs and more
// with the SB_DRIVE of the far box. All outputs are visible, so a parent can connect them.
//
// Chip coordinates: the unit starts at a CPE with x - 1 and y - 1 a multiple of 4 (the switch box pattern
// has period 4). ORIGIN_BIG11 says whether the 2x2 tile in its lower left corner has the large box at its
// CPE (0,0): 1 for the tile at x = y = 41, which is the model's reference, 0 for the cut shifted by 2 in x.
//
// Configuration: every 2x2 tile has its own parameter, CFG_XtxYty, the 113 bytes of the bitstream as
// described in tile2x2.v, because the configuration stream sets the tiles one by one.
//
// Switch box outputs Y1..Y4 flow towards +x, +y, -x, -y (sb_big.v). A box at (cx, cy) with
// (cx % 2) == (cy % 2) exists wherever a CPE has x and y of the same parity; the entries sb_*[cx][cy] of
// the other CPEs stay unused.
`timescale 1ns/1ps

module tile4x4 #(
    parameter ORIGIN_BIG11 = 1,
    parameter [903:0] CFG_X0Y0 = 904'd0,
    parameter [903:0] CFG_X1Y0 = 904'd0,
    parameter [903:0] CFG_X0Y1 = 904'd0,
    parameter [903:0] CFG_X1Y1 = 904'd0
) (
    // ---- from outside the unit; index [cx][cy], plane [12:1], direction [4:1], input number
    input  [3:0][3:0][12:1][5:0]      ext_im_d,              // IM D0..D5
    input  [3:0][3:0][12:1][4:1][7:2] ext_sb_d,              // switch box Dk_i, k = 2..7
    input  [3:0][3:0][12:1]           ext_sb_x12, ext_sb_x34,
    input  [3:0][3:0]                 ext_cinx, ext_ciny1, ext_ciny2, ext_pinx, ext_piny1, ext_piny2,
    // ---- everything inside
    output [3:0][3:0][12:1]           im_y,
    output [3:0][3:0][12:1][4:1]      sb_y, sb_drv, sb_drvn,
    output [3:0][3:0][12:1]           sb_ydiag,
    output [3:0][3:0]                 coutx, couty1, couty2, poutx, pouty1, pouty2
);
    localparam NX = 4, NY = 4, TX = 2, TY = 2;
    genvar tx, ty, cx, cy, p, i, k;

    // the configuration of the tiles in the order n = 2 tx + ty
    localparam [4*904-1:0] CFGS = {CFG_X1Y1, CFG_X1Y0, CFG_X0Y1, CFG_X0Y0};

    // ---------------------------------------------------------------------------------------------
    // Helpers, all evaluated while the unit is built
    // ---------------------------------------------------------------------------------------------

    function in_window(input integer x, input integer y);
        in_window = (x >= 0) && (x < NX) && (y >= 0) && (y < NY);
    endfunction

    // Position of the source of a wire relative to its destination: the wire flows in the direction
    // of Yi (+x, +y, -x, -y for i = 1..4), so the source lies in the opposite direction.
    function integer src_dx(input integer i);
        src_dx = (i == 1) ? -1 : (i == 3) ? 1 : 0;
    endfunction

    function integer src_dy(input integer i);
        src_dy = (i == 2) ? -1 : (i == 4) ? 1 : 0;
    endfunction

    // Length in CPEs of the switch box wire that arrives at input Dk (k = 2..7)
    function integer wire_length(input integer k);
        wire_length = (k == 2) ? 2 : (k == 3) ? 4 : 4 * (k - 2);   // 2, 4, 8, 12, 16, 20
    endfunction

    // ---------------------------------------------------------------------------------------------
    // The tiles. Their ports, collected over the unit, are indexed [tile x][tile y]
    // ---------------------------------------------------------------------------------------------

    wire [TX-1:0][TY-1:0][1:0][1:0][12:1][5:0] t_im_d;
    wire [TX-1:0][TY-1:0][1:0][1:0][12:1]      t_im_y;
    wire [TX-1:0][TY-1:0][1:0][1:0] t_cinx, t_ciny1, t_ciny2, t_pinx, t_piny1, t_piny2;
    wire [TX-1:0][TY-1:0][1:0][1:0] t_coutx, t_couty1, t_couty2, t_poutx, t_pouty1, t_pouty2;
    wire [TX-1:0][TY-1:0][1:0][12:1][4:1][7:2] t_sb_d;
    wire [TX-1:0][TY-1:0][1:0][12:1]           t_sb_x12, t_sb_x34, t_sb_ydiag;
    wire [TX-1:0][TY-1:0][1:0][12:1][4:1]      t_sb_y, t_sb_drv, t_sb_drvn;

    generate
        for (tx = 0; tx < TX; tx = tx + 1) begin : tile_x
            for (ty = 0; ty < TY; ty = ty + 1) begin : tile_y
                // the large box alternates from tile to tile, like on a chessboard
                tile2x2 #(
                    .BIG11(ORIGIN_BIG11 ^ ((tx + ty) % 2)),
                    .CFG(CFGS[(tx * TY + ty) * 904 +: 904])
                ) u_tile (
                    .im_d(t_im_d[tx][ty]),   .im_y(t_im_y[tx][ty]),
                    .cinx(t_cinx[tx][ty]),   .ciny1(t_ciny1[tx][ty]), .ciny2(t_ciny2[tx][ty]),
                    .pinx(t_pinx[tx][ty]),   .piny1(t_piny1[tx][ty]), .piny2(t_piny2[tx][ty]),
                    .coutx(t_coutx[tx][ty]), .couty1(t_couty1[tx][ty]), .couty2(t_couty2[tx][ty]),
                    .poutx(t_poutx[tx][ty]), .pouty1(t_pouty1[tx][ty]), .pouty2(t_pouty2[tx][ty]),
                    .sb_d(t_sb_d[tx][ty]),   .sb_x12(t_sb_x12[tx][ty]), .sb_x34(t_sb_x34[tx][ty]),
                    .sb_y(t_sb_y[tx][ty]),   .sb_ydiag(t_sb_ydiag[tx][ty]),
                    .sb_drv(t_sb_drv[tx][ty]), .sb_drvn(t_sb_drvn[tx][ty])
                );
            end
        end
    endgenerate

    // ---------------------------------------------------------------------------------------------
    // The wiring, CPE by CPE
    // ---------------------------------------------------------------------------------------------

    generate
        for (cx = 0; cx < NX; cx = cx + 1) begin : cpe_x
            for (cy = 0; cy < NY; cy = cy + 1) begin : cpe_y
                // where this CPE is in its tile
                localparam TXI = cx / 2, TYI = cy / 2;       // tile
                localparam X = cx % 2, Y = cy % 2;           // relative position in the tile
                localparam HAS_SB = (X == Y);                // has a switch box and an OM of its own
                localparam SB_DIST = HAS_SB ? 2 : 1;         // distance to the boxes that feed its IM

                // ---- the outputs of the tile, at the position of the CPE
                assign im_y[cx][cy]   = t_im_y[TXI][TYI][X][Y];
                assign coutx[cx][cy]  = t_coutx[TXI][TYI][X][Y];
                assign couty1[cx][cy] = t_couty1[TXI][TYI][X][Y];
                assign couty2[cx][cy] = t_couty2[TXI][TYI][X][Y];
                assign poutx[cx][cy]  = t_poutx[TXI][TYI][X][Y];
                assign pouty1[cx][cy] = t_pouty1[TXI][TYI][X][Y];
                assign pouty2[cx][cy] = t_pouty2[TXI][TYI][X][Y];

                // ---- carry (C) and propagate (P) chain: the X lines come from the CPE at (-1,0), the
                // ---- Y lines from the CPE at (0,-1)
                if (cx > 0) begin : chain_x
                    assign t_cinx[TXI][TYI][X][Y] = coutx[cx-1][cy];
                    assign t_pinx[TXI][TYI][X][Y] = poutx[cx-1][cy];
                end else begin : chain_x_ext
                    assign t_cinx[TXI][TYI][X][Y] = ext_cinx[cx][cy];
                    assign t_pinx[TXI][TYI][X][Y] = ext_pinx[cx][cy];
                end
                if (cy > 0) begin : chain_y
                    assign t_ciny1[TXI][TYI][X][Y] = couty1[cx][cy-1];
                    assign t_ciny2[TXI][TYI][X][Y] = couty2[cx][cy-1];
                    assign t_piny1[TXI][TYI][X][Y] = pouty1[cx][cy-1];
                    assign t_piny2[TXI][TYI][X][Y] = pouty2[cx][cy-1];
                end else begin : chain_y_ext
                    assign t_ciny1[TXI][TYI][X][Y] = ext_ciny1[cx][cy];
                    assign t_ciny2[TXI][TYI][X][Y] = ext_ciny2[cx][cy];
                    assign t_piny1[TXI][TYI][X][Y] = ext_piny1[cx][cy];
                    assign t_piny2[TXI][TYI][X][Y] = ext_piny2[cx][cy];
                end

                // ---- input multiplexer, plane by plane
                for (p = 1; p <= 12; p = p + 1) begin : im
                    // D0..D3 (input numbers 0..3): Y1..Y4 of the switch boxes next to the CPE
                    for (i = 1; i <= 4; i = i + 1) begin : from_sb
                        localparam SX = cx + SB_DIST * src_dx(i), SY = cy + SB_DIST * src_dy(i);
                        if (in_window(SX, SY)) begin : internal
                            assign t_im_d[TXI][TYI][X][Y][p][i-1] = sb_y[SX][SY][p][i];
                        end else begin : external
                            assign t_im_d[TXI][TYI][X][Y][p][i-1] = ext_im_d[cx][cy][p][i-1];
                        end
                    end

                    // D4, D5: the IM of the CPE at (-1,-1) and (+1,+1)
                    if (in_window(cx - 1, cy - 1)) begin : d4_internal
                        assign t_im_d[TXI][TYI][X][Y][p][4] = im_y[cx-1][cy-1][p];
                    end else begin : d4_external
                        assign t_im_d[TXI][TYI][X][Y][p][4] = ext_im_d[cx][cy][p][4];
                    end
                    if (in_window(cx + 1, cy + 1)) begin : d5_internal
                        assign t_im_d[TXI][TYI][X][Y][p][5] = im_y[cx+1][cy+1][p];
                    end else begin : d5_external
                        assign t_im_d[TXI][TYI][X][Y][p][5] = ext_im_d[cx][cy][p][5];
                    end
                end

                // ---- switch box
                if (HAS_SB) begin : sb
                    assign sb_y[cx][cy]     = t_sb_y[TXI][TYI][X];
                    assign sb_ydiag[cx][cy] = t_sb_ydiag[TXI][TYI][X];
                    assign sb_drv[cx][cy]   = t_sb_drv[TXI][TYI][X];
                    assign sb_drvn[cx][cy]  = t_sb_drvn[TXI][TYI][X];

                    for (p = 1; p <= 12; p = p + 1) begin : plane
                        // Dk_i: Yi of the box LEN CPEs away, against the direction of the wire
                        for (i = 1; i <= 4; i = i + 1) begin : dir
                            for (k = 2; k <= 7; k = k + 1) begin : kind
                                localparam LEN = wire_length(k);
                                localparam SX = cx + LEN * src_dx(i), SY = cy + LEN * src_dy(i);
                                // the wires of 8 CPEs and more come from the SB_DRIVE of the far box, and
                                // never from inside a unit of 4x4 CPEs
                                if (k <= 3 && in_window(SX, SY)) begin : internal
                                    assign t_sb_d[TXI][TYI][X][p][i][k] = sb_y[SX][SY][p][i];
                                end else begin : external
                                    assign t_sb_d[TXI][TYI][X][p][i][k] = ext_sb_d[cx][cy][p][i][k];
                                end
                            end
                        end

                        // X12, X34: YDIAG of the boxes at (-1,-1) and (+1,+1)
                        if (in_window(cx - 1, cy - 1)) begin : x12_internal
                            assign t_sb_x12[TXI][TYI][X][p] = sb_ydiag[cx-1][cy-1][p];
                        end else begin : x12_external
                            assign t_sb_x12[TXI][TYI][X][p] = ext_sb_x12[cx][cy][p];
                        end
                        if (in_window(cx + 1, cy + 1)) begin : x34_internal
                            assign t_sb_x34[TXI][TYI][X][p] = sb_ydiag[cx+1][cy+1][p];
                        end else begin : x34_external
                            assign t_sb_x34[TXI][TYI][X][p] = ext_sb_x34[cx][cy][p];
                        end
                    end
                end
            end
        end
    endgenerate
endmodule
