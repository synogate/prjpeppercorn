// Simulation model of one Cologne Chip GateMate CPE, written by hand after cpe.kicad_sch.
// Plain Verilog-1995: no ANSI ports, no always @*, no declaration initialisers.
//
// All configuration bits and LUT truth tables are parameters, named like in the libgm bit
// database. C_FUNCTION is a 3-bit parameter; the individual signals the schematic decodes from it
// (C_MULT, C_MX4, C_EN_CIN, C_ADDF, C_ADDF2, C_ADDCIN) are derived wires, not parameters.
//
// Sections follow the schematic: combinational logic, sequential logic, carry/propagate lines.
// "NOTE" marks places where the schematic and nextpnr / die.py disagree.
`timescale 1ns/1ps

module cpe (
    IN1, IN2, IN3, IN4, IN5, IN6, IN7, IN8,
    CLK, EN, SR,
    CINX, CINY1, CINY2,
    PINX, PINY1, PINY2,
    RAM_I1, RAM_I2,
    OUT1, OUT2,
    RAM_O1, RAM_O2,
    COUTX, COUTY1, COUTY2,
    POUTX, POUTY1, POUTY2
);

    // ---- LUT truth tables; index = {D1, D0} ----
    parameter [3:0] INIT_L00 = 4'h0, INIT_L01 = 4'h0, INIT_L02 = 4'h0, INIT_L03 = 4'h0;  // level 0
    parameter [3:0] INIT_L10 = 4'h0, INIT_L11 = 4'h0;                                    // level 1
    parameter [3:0] INIT_L20 = 4'h0;                                                     // level 2
    parameter [3:0] INIT_L30 = 4'h0;                                                     // comparator

    // ---- Second input of L00..L03: 0 = IN2/IN4/IN6/IN8, 1 = PINY1/CINX/PINY1/PINX ----
    parameter [0:0] C_I1 = 1'b0, C_I2 = 1'b0, C_I3 = 1'b0, C_I4 = 1'b0;

    // ---- Function: the 3-bit C_FUNCTION field of the bitstream (decoded below) ----
    parameter [2:0] C_FUNCTION = 3'd0;
    parameter [0:0] C_HORIZ  = 1'b0;  // carry-in source: 0 = CINY1, 1 = CINX (also steers CPOUT and comparator)
    parameter [0:0] C_COMP   = 1'b0;
    parameter [0:0] C_COMP_I = 1'b0;   // constant that POUTX / POUTY1 pass while comparing

    // ---- Carry / propagate lines ----
    parameter [0:0] C_SELX = 1'b0, C_SELY1 = 1'b0, C_SELY2 = 1'b0;   // OUT1 / OUT2 pick, one per axis
    parameter [0:0] C_SEL_C = 1'b0;                                  // carry lines:     0 = OUT1/OUT2, 1 = COMP_OUT/CIN
    parameter [0:0] C_SEL_P = 1'b0;                                  // propagate lines: 0 = OUT1/OUT2, 1 = COMP_OUT/PIN
    parameter [0:0] C_Y12 = 1'b0;                                    // 0 = CINY1/PINY1, 1 = CINY2/PINY2 into the X lines
    parameter [0:0] C_CX_I = 1'b0, C_CY1_I = 1'b0, C_CY2_I = 1'b0;
    parameter [0:0] C_PX_I = 1'b0, C_PY1_I = 1'b0, C_PY2_I = 1'b0;
    parameter [0:0] C_C_P = 1'b0;                                    // CPOUT1/2: 1 = CPOUT1 from carry lines

    // ---- Register, latch, 8:1 mux / bridge ----
    parameter [1:0] C_CPE_CLK = 2'd0, C_CPE_EN = 2'd0, C_CPE_RES = 2'd0, C_CPE_SET = 2'd0;  // LUT1 truth tables
    parameter [0:0] C_CLKSEL = 1'b0;    // add CINY2 to the clock (the 8:1 mux select adder adds it too, finding 37)
    parameter [0:0] C_ENSEL  = 1'b0;    // add PINY2 to the enable (the 8:1 mux select adder adds it too, finding 37)
    parameter [0:0] C_EN_SR  = 1'b0;    // 1: SET LUT1 listens to SR, 0: to EN
    parameter [0:0] C_L_D    = 1'b0;    // 0: flip-flop, 1: latch
    parameter [0:0] C_BR     = 1'b0;    // 1: 8:1 mux select = C_SN (bridge); flop 2 takes MUXOUT
    parameter [0:0] C_2D_IN  = 1'b0;
    parameter [2:0] C_SN = 3'd0;

    // ---- Outputs ----
    parameter [1:0] C_O1 = 2'd0, C_O2 = 2'd0;       // 0 = register, 1 = MUXOUT, 2 = CPOUT, 3 = COMBOUT

    // ---- Start state of the registers. The bitstream loader brings them there by pulsing the reset or set input
    // ---- while it configures the CPE (libgm: FF_INIT, 2 bits per CPE in the last byte of the tile data), so the
    // ---- hardware has no such bits. A model cannot change a parameter later, hence it is one here.
    // ---- 2 = reset (Q = 0), 3 = set (Q = 1), 0 and 1 = not initialised: the start state of this model, Q = 1.
    parameter [1:0] FF_INIT = 2'd0;
    parameter [0:0] C_RAM_I1 = 1'b0, C_RAM_I2 = 1'b0;     // NOTE: schematic: 0 selects RAM_I; nextpnr sets C_RAM_I=1 only when RAM_I is used
    parameter [0:0] C_RAM_O1 = 1'b0, C_RAM_O2 = 1'b0;

    // ---- C_FUNCTION decode, as in the schematic's C_FUNCTION symbol (not separate bits in the bitstream) ----
    wire C_MULT   = (C_FUNCTION == 3'd3);
    wire C_MX4    = (C_FUNCTION == 3'd4);
    wire C_EN_CIN = (C_FUNCTION == 3'd5);
    wire C_ADDF   = (C_FUNCTION == 3'd1) | (C_FUNCTION == 3'd2) | (C_FUNCTION == 3'd3) | (C_FUNCTION == 3'd6);
    wire C_ADDF2  = (C_FUNCTION == 3'd2) | (C_FUNCTION == 3'd3);
    wire C_ADDCIN = (C_FUNCTION == 3'd1) | (C_FUNCTION == 3'd2) | (C_FUNCTION == 3'd3) | (C_FUNCTION == 3'd7);

    input  IN1, IN2, IN3, IN4, IN5, IN6, IN7, IN8;
    input  CLK, EN, SR;
    input  CINX, CINY1, CINY2;
    input  PINX, PINY1, PINY2;
    input  RAM_I1, RAM_I2;

    output OUT1, OUT2;
    output RAM_O1, RAM_O2;
    output COUTX, COUTY1, COUTY2;
    output POUTX, POUTY1, POUTY2;

    // ------------------------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------------------------
    function lut2;
        input [3:0] init;
        input d1;
        input d0;
        begin
            lut2 = init[{d1, d0}];
        end
    endfunction

    function lut1;
        input [1:0] init;
        input d;
        begin
            lut1 = init[d];
        end
    endfunction

    // ------------------------------------------------------------------------------------
    // Combinational logic
    // ------------------------------------------------------------------------------------

    // Level 0: four LUT2. The second input can come from a carry/propagate line instead of IN2/4/6/8.
    wire in2_or_piny1 = C_I1 ? PINY1 : IN2;
    wire in4_or_cinx  = C_I2 ? CINX  : IN4;
    wire in6_or_piny1 = C_I3 ? PINY1 : IN6;
    wire in8_or_pinx  = C_I4 ? PINX  : IN8;

    wire carry_in = C_HORIZ ? CINX : CINY1;

    wire l00     = lut2(INIT_L00, in2_or_piny1, IN1);
    wire l01     = lut2(INIT_L01, in4_or_cinx,  IN3);
    wire l02     = lut2(INIT_L02, in6_or_piny1, IN5);
    wire l03_lut = lut2(INIT_L03, in8_or_pinx,  IN7);
    wire l03     = l03_lut | (C_EN_CIN & carry_in);        // in EN_CIN mode the carry-in is ORed into L03

    // Level 1
    wire l10 = lut2(INIT_L10, l01, l00);
    wire l11 = lut2(INIT_L11, l03, l02);

    // 4:1 multiplexers (MX4): per input  out = invert ^ (mode & select & data).
    // The invert and select bits are the INIT bits of L10 / L11 of the *other* half, one bit per input.
    // NOTE: the schematic labels MX4a "C = L11, X = L10" and MX4b "C = L10, X = L11" (as nextpnr has it; hardware S3 / S7 confirms both).
    //       Hardware (M20): the upper mux (MX4a, data IN1..IN4, select l03/l02) feeds L20.D1 (level2_b),
    //       the other one (MX4b, data IN5..IN8, select l01/l00) feeds L20.D0 (level2_a = COMB2OUT).
    wire [3:0] mx4a_in   = {IN4, IN3, IN2, IN1};
    wire [3:0] mx4b_in   = {IN8, IN7, IN6, IN5};
    wire [3:0] mx4a_data = INIT_L11 ^ ({4{C_MX4}} & INIT_L10 & mx4a_in);
    wire [3:0] mx4b_data = INIT_L10 ^ ({4{C_MX4}} & INIT_L11 & mx4b_in);
    wire mx4a_out = mx4a_data[{l03, l02}];     // selected by the LUT outputs of the lower half
    wire mx4b_out = mx4b_data[{l01, l00}];     // selected by the LUT outputs of the upper half

    // Level 2: in MX4 mode the multiplexers replace L10 / L11
    wire level2_a = C_MX4 ? mx4b_out : l10;
    wire level2_b = C_MX4 ? mx4a_out : l11;
    wire l20      = lut2(INIT_L20, level2_b, level2_a);

    // Adder: COMB1OUT = sum bit 0, COMB2OUT = sum bit 1
    wire carry_into_bit1 = l11 ? carry_in : l02;                 // carry ripples through when L11 propagates
    wire add_cin         = C_ADDCIN & carry_in;
    wire add2_carry      = C_ADDF2  & carry_into_bit1;
    wire comb1_out       = l20 ^ add_cin;
    wire comb2_out       = level2_a ^ add2_carry;

    // Comparator
    // NOTE: COMP_OUT is the raw LUT output. The comparator conditions of the CP generators (POUTX, hw_measurements.md finding 30) see it as it is; the inversion measured on the
    //       COUTX routing multiplexer (finding 20) sits in front of that multiplexer's data input D2 (written ~comp_out below, for all six routing multiplexers: assumed to be alike).
    wire comp_out = lut2(INIT_L30, comb2_out, comb1_out);

    // Carry chain signals: propagate (CADD_S) and generate (CADD_A)
    wire propagate_addf  = ~(l10 ^ l11);
    wire propagate_addf2 = ~(l10 & l11);
    // NOTE: measured on hardware (hw_measurements.md finding 23, COUTX with random LUT trees): generate of ADDF is l00 | l01 | l02. With nextpnr's INIT_L02 = 0 this is l00 | l01
    //       (what an adder test with nextpnr's CC_ADDF can see). An earlier schematic had (l00 | l01) & l02.
    wire generate_addf   = l00 | l01 | l02;
    wire generate_addf2  = l10 ? l02 : (l00 | l01);
    wire carry_propagate = C_ADDF2 ? propagate_addf2 : propagate_addf;    // CADD_S
    wire carry_generate  = C_ADDF2 ? generate_addf2  : generate_addf;     // CADD_A

    // Multiplier: two partial products and their sums (schematic labels A_0, A_-1, B_1)
    wire pp_a0_b1       = IN5 & PINY2;
    wire pp_am1_b1      = IN8 & PINY2;
    wire mult_sum_hi    = add2_carry ^ l10 ^ pp_a0_b1;
    wire mult_sum_lo    = l11 ^ pp_am1_b1 ^ CINY1;
    // NOTE: hardware (hw_measurements.md findings 27, 28): the data inputs of this mux are swapped with respect to the schematic: mult_sum_lo ? CINY2 : pp_am1_b1
    //       (mult_sum_lo itself is not inverted: MULTO1 = mult_sum_lo ^ CINY2 matches).
    wire mult_carry_mid = mult_sum_lo ? CINY2 : pp_am1_b1;
    wire coy2_a         = mult_sum_hi ? pp_am1_b1 : pp_a0_b1;             // COY2_a
    // NOTE: hardware (hw_measurements.md finding 36, wp_y2 / wp_y2b): the select that COUTY2 uses is NAND(mult_sum_hi, mult_sum_lo); the schematic has OR here.
    wire coy2_s         = ~(mult_sum_hi & mult_sum_lo);                   // COY2_S
    wire multo1         = mult_sum_lo ^ CINY2;                            // MULTO1
    wire multo2         = mult_sum_hi ^ mult_carry_mid;                   // MULTO2

    // ------------------------------------------------------------------------------------
    // Clock, enable and set/reset terms of the registers. Each goes through its own LUT1
    // (invert / constant); clock and enable can be XORed with a carry/propagate line.
    // ------------------------------------------------------------------------------------
    wire ff_clk    = lut1(C_CPE_CLK, CLK) ^ (C_CLKSEL & CINY2);
    wire ff_en     = lut1(C_CPE_EN,  EN)  ^ (C_ENSEL  & PINY2);
    // NOTE: hardware (hw_measurements.md, finding 6): the reset / set request LUT1s are active low, word 11 = no request (what nextpnr writes for a plain
    //       flip-flop), 00 = permanent request. The schematic's S / R pins of the flip-flop symbols are active low too (bubble), the LUT1 output goes in directly;
    //       here the requests are modelled active high, hence the inversion.
    wire reset_req = ~lut1(C_CPE_RES, SR);
    wire set_req   = ~lut1(C_CPE_SET, C_EN_SR ? SR : EN);

    // ------------------------------------------------------------------------------------
    // 8:1 multiplexer (MUXOUT). Its select is a 3-bit adder:
    //   C_SN + {SR, EN, CLK terms} + C_2D_IN, or C_SN alone in bridge mode.
    // The terms are built like the register ones, with their own LUT1s and the same config bits.
    // NOTE: hardware (hw_measurements.md, S31, finding 37): the terms read CINY2 / PINY2 (C_CLKSEL / C_ENSEL), the same lines as the registers, added by XOR.
    //       The schematic still has CINY1 / PINY1 here (commit 5a43fa5 relabelled only the register side).
    // ------------------------------------------------------------------------------------
    wire mux8_term_clk = lut1(C_CPE_CLK, CLK) ^ (C_CLKSEL & CINY2);
    wire mux8_term_en  = lut1(C_CPE_EN,  EN)  ^ (C_ENSEL  & PINY2);
    wire mux8_term_sr  = lut1(C_CPE_RES, SR);

    wire [2:0] mux8_select_sum = C_SN + {mux8_term_sr, mux8_term_en, mux8_term_clk} + C_2D_IN;
    wire [2:0] mux8_select     = C_BR ? C_SN : mux8_select_sum;
    wire [7:0] mux8_in         = {IN8, IN7, IN6, IN5, IN4, IN3, IN2, IN1};
    wire       muxout          = mux8_in[mux8_select];

    // ------------------------------------------------------------------------------------
    // Sequential logic: two flip-flops or latches. They store the inverted data, and their set
    // and reset inputs are crossed, so the output (inverted again) behaves as expected.
    // ------------------------------------------------------------------------------------

    // Data of the second register: COMB1OUT, COMB2OUT, MUXOUT, or inverted MUXOUT
    reg ff2_source;
    always @(comb1_out or comb2_out or muxout) begin
        case ({C_BR, C_2D_IN})
            2'b00:   ff2_source = comb1_out;
            2'b01:   ff2_source = comb2_out;
            2'b10:   ff2_source = muxout;
            default: ff2_source = ~muxout;
        endcase
    end

    reg ff1_stored;       // inverted data
    reg ff2_stored;
    reg latch1_stored;
    reg latch2_stored;

    initial begin
        ff1_stored    = (FF_INIT == 2'd2);       // stores the inverse: FF_INIT = 2 starts with Q = 0
        ff2_stored    = (FF_INIT == 2'd2);
        latch1_stored = (FF_INIT == 2'd2);
        latch2_stored = (FF_INIT == 2'd2);
    end

    always @(posedge ff_clk or posedge reset_req or posedge set_req) begin
        if (set_req)        ff1_stored <= 1'b0;                // stores 0: output 1
        else if (reset_req) ff1_stored <= 1'b1;                // stores 1: output 0
        else if (ff_en)     ff1_stored <= ~comb1_out;
    end

    always @(posedge ff_clk or posedge reset_req or posedge set_req) begin
        if (set_req)        ff2_stored <= 1'b0;
        else if (reset_req) ff2_stored <= 1'b1;
        else if (ff_en)     ff2_stored <= ~ff2_source;
    end

    always @(set_req or reset_req or ff_clk or ff_en or comb1_out) begin
        if (set_req)             latch1_stored = 1'b0;
        else if (reset_req)      latch1_stored = 1'b1;
        else if (ff_clk & ff_en) latch1_stored = ~comb1_out;
    end

    always @(set_req or reset_req or ff_clk or ff_en or ff2_source) begin
        if (set_req)             latch2_stored = 1'b0;
        else if (reset_req)      latch2_stored = 1'b1;
        else if (ff_clk & ff_en) latch2_stored = ~ff2_source;
    end

    wire dout1 = ~(C_L_D ? latch1_stored : ff1_stored);
    wire dout2 = ~(C_L_D ? latch2_stored : ff2_stored);

    // ------------------------------------------------------------------------------------
    // Carry / propagate lines
    // ------------------------------------------------------------------------------------

    // CPOUT1/2: one of the carry or propagate outputs, X or Y1 axis
    wire cp_use_x      = C_HORIZ | C_MULT;
    wire cp_carry_out  = cp_use_x ? COUTX : COUTY1;
    wire cp_prop_out   = cp_use_x ? POUTX : POUTY1;
    wire cpout1        = C_C_P ? cp_carry_out : cp_prop_out;
    wire cpout2        = C_C_P ? cp_prop_out  : cp_carry_out;

    // Output multiplexers
    reg out1_mux, out2_mux;

    always @(dout1 or muxout or cpout1 or comb1_out) begin
        case (C_O1)
            2'd0:    out1_mux = dout1;
            2'd1:    out1_mux = muxout;
            2'd2:    out1_mux = cpout1;
            default: out1_mux = comb1_out;
        endcase
    end

    always @(dout2 or muxout or cpout2 or comb2_out) begin
        case (C_O2)
            2'd0:    out2_mux = dout2;
            2'd1:    out2_mux = muxout;
            2'd2:    out2_mux = cpout2;
            default: out2_mux = comb2_out;
        endcase
    end

    assign OUT1   = C_RAM_I1 ? out1_mux : RAM_I1;
    assign OUT2   = C_RAM_I2 ? out2_mux : RAM_I2;
    assign RAM_O1 = out1_mux & C_RAM_O1;
    assign RAM_O2 = out2_mux & C_RAM_O2;

    // Routing multiplexer in front of every carry / propagate output:
    // picks OUT1 / OUT2 (C_SELx), COMP_OUT, or an incoming carry / propagate line.
    wire cin_y12 = C_Y12 ? CINY2 : CINY1;
    wire pin_y12 = C_Y12 ? PINY2 : PINY1;

    reg cx_route, cy1_route, cy2_route;       // carry lines
    reg px_route, py1_route, py2_route;       // propagate lines

    always @(OUT1 or OUT2 or comp_out or cin_y12) begin
        case ({C_SEL_C, C_SELX})
            2'b00: cx_route = OUT1;
            2'b01: cx_route = OUT2;
            2'b10: cx_route = ~comp_out;                 // inverter in front of D2 (measured on COUTX)
            default: cx_route = cin_y12;
        endcase
    end

    always @(OUT1 or OUT2 or comp_out or CINX) begin
        case ({C_SEL_C, C_SELY1})
            2'b00: cy1_route = OUT2;
            2'b01: cy1_route = OUT1;
            2'b10: cy1_route = ~comp_out;                 // inverter in front of D2 (assumed like COUTX)
            default: cy1_route = CINX;
        endcase
    end

    always @(OUT1 or OUT2 or comp_out or CINX) begin
        case ({C_SEL_C, C_SELY2})
            2'b00: cy2_route = OUT1;
            2'b01: cy2_route = OUT2;
            2'b10: cy2_route = ~comp_out;                 // inverter in front of D2 (assumed like COUTX)
            default: cy2_route = CINX;
        endcase
    end

    always @(OUT1 or OUT2 or comp_out or pin_y12) begin
        case ({C_SEL_P, C_SELX})
            2'b00: px_route = OUT2;
            2'b01: px_route = OUT1;
            2'b10: px_route = ~comp_out;                 // inverter in front of D2 (assumed like COUTX)
            default: px_route = pin_y12;
        endcase
    end

    always @(OUT1 or OUT2 or comp_out or PINX) begin
        case ({C_SEL_P, C_SELY1})
            2'b00: py1_route = OUT1;
            2'b01: py1_route = OUT2;
            2'b10: py1_route = ~comp_out;                 // inverter in front of D2 (assumed like COUTX)
            default: py1_route = PINX;
        endcase
    end

    always @(OUT1 or OUT2 or comp_out or PINX) begin
        case ({C_SEL_P, C_SELY2})
            2'b00: py2_route = OUT2;
            2'b01: py2_route = OUT1;
            2'b10: py2_route = ~comp_out;                 // inverter in front of D2 (assumed like COUTX)
            default: py2_route = PINX;
        endcase
    end

    // ---- COUTX / POUTX: 4:1 final multiplexers ----
    // The selects are never inverted in front of the multiplexer: S1 is the OA21 / AO21-type output as it is, the data inputs are arranged accordingly.
    // COUTX (hw_measurements.md findings 20-24, 27): S1 = C_CX_I | ((C_ADDF & C_HORIZ) & carry_propagate), S0 = C_MULT | C_CX_I,
    //   {S1, S0}: 00 CINX, 01 MULTO2, 10 generate, 11 routing multiplexer. (The schematic has an OR / AND-with-~C_CX_I here: not what the hardware does.)
    wire coutx_s1 = C_CX_I | ((C_ADDF & C_HORIZ) & carry_propagate);
    wire coutx_s0 = C_MULT | C_CX_I;
    reg  coutx_value;

    always @(coutx_s1 or coutx_s0 or carry_generate or cx_route or CINX or multo2) begin
        case ({coutx_s1, coutx_s0})
            2'b00: coutx_value = CINX;
            2'b01: coutx_value = multo2;
            2'b10: coutx_value = carry_generate;
            default: coutx_value = cx_route;
        endcase
    end
    assign COUTX = coutx_value;

    // POUTX (hw_measurements.md finding 30), same structure with the comparator in place of the adder: S1 = C_PX_I | ((C_COMP & C_HORIZ) & comp_out), S0 = C_MULT | C_PX_I,
    //   {S1, S0}: 00 PINX, 01 MULTO1, 10 ~C_COMP_I, 11 routing multiplexer.
    wire poutx_s1 = C_PX_I | ((C_COMP & C_HORIZ) & comp_out);
    wire poutx_s0 = C_MULT | C_PX_I;
    reg  poutx_value;

    always @(poutx_s1 or poutx_s0 or px_route or PINX or multo1 or C_COMP_I) begin
        case ({poutx_s1, poutx_s0})
            2'b00: poutx_value = PINX;
            2'b01: poutx_value = multo1;
            2'b10: poutx_value = ~C_COMP_I;
            default: poutx_value = px_route;
        endcase
    end
    assign POUTX = poutx_value;

    // ---- COUTY1 / POUTY1 ----
    // NOTE: measured on hardware (lab adder_f1, C_FUNCTION=1, C_HORIZ=0): C_CY1_I = 0 passes CINY1 when the adder propagates
    //       (l10 ^ l11, i.e. ~carry_propagate), otherwise the generate term comes out; C_CY1_I = 1 always gives generate.
    //       Without an adder C_CY1_I = 0 passes CINY1 (as die.py has it). C_HORIZ = 1 was measured too (COUTY1 = CINY1 | (A & B)
    //       with B on CINX) and is not reproduced: it is modelled like a non-adder here.
    wire cy1_adder   = C_ADDF & ~C_HORIZ;
    wire cy1_sel     = C_CY1_I | (cy1_adder & carry_propagate);        // 0: pass CINY1 (the select takes the OA21 output as it is)
    assign COUTY1 = cy1_sel ? (cy1_adder ? carry_generate : cy1_route) : CINY1;

    // NOTE: POUTY1 follows POUTX (hw_measurements.md finding 30) and COUTY1 by parallel: only "C_PY1_I = 1 takes the routing multiplexer, 0 passes PINY1" is measured (finding 10);
    //       the comparator terms (C_COMP & ~C_HORIZ, raw comp_out, ~C_COMP_I) are assumed. The schematic had (comp_out | compare) & C_PY1_I -> PINY1 here.
    wire py1_compare = C_COMP & ~C_HORIZ;
    wire py1_sel     = C_PY1_I | (py1_compare & comp_out);                // 0: pass PINY1
    assign POUTY1 = py1_sel ? (py1_compare ? ~C_COMP_I : py1_route) : PINY1;

    // ---- COUTY2 / POUTY2 ----
    // COUTY2 (hw_measurements.md findings 35, 36; the south helper's COUTY2 read at the DUT): C_CY2_I = 0 passes CINY2, C_CY2_I = 1 gives the routing multiplexer, like COUTY1; in multiplier mode
    //   (C_MULT = 1) the generate-type term coy2_a replaces the route and CINY2 is passed only where mult_sum_hi & mult_sum_lo (independent of the comparator, checked with six INIT_L30 values):
    //   select = C_CY2_I | (C_MULT & coy2_s).  coy2_a itself was only seen as constant 0 (IN5 = IN8 = 0 on the helper): unvalidated.
    wire cy2_sel = C_CY2_I | (C_MULT & coy2_s);                           // 0: pass CINY2
    assign COUTY2 = cy2_sel ? (C_MULT ? coy2_a : cy2_route) : CINY2;

    // POUTY2 (finding 35): C_PY2_I = 1 takes the routing multiplexer, 0 passes PINY2; in multiplier mode (C_MULT = 1) PINY2 is always passed (B operand forwarded), also at C_PY2_I = 1.
    wire py2_sel = C_PY2_I & ~C_MULT;
    assign POUTY2 = py2_sel ? py2_route : PINY2;

endmodule
