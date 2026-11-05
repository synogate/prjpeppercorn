// Stand-in for cpe.v in the routing testbenches (tb_*.v): same ports, but
//   - OUT1 and OUT2 are plain registers the testbench writes through the hierarchy (u_cpe.out1 = ...)
//   - the carry and propagate lines pass through, some of them inverted, so that a chain of CPEs shows
//     which line is wired to which:   COUTX = ~CINX     COUTY1 = ~CINY1     COUTY2 = CINY2
//                                      POUTX = PINX      POUTY1 = PINY1      POUTY2 = ~PINY2
// Compile it instead of cpe.v.
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
    // the configuration of cpe.v, unused here (tile2x2 sets them from its CFG)
    parameter [3:0] INIT_L00 = 4'h0, INIT_L01 = 4'h0, INIT_L02 = 4'h0, INIT_L03 = 4'h0;
    parameter [3:0] INIT_L10 = 4'h0, INIT_L11 = 4'h0;
    parameter [3:0] INIT_L20 = 4'h0;
    parameter [3:0] INIT_L30 = 4'h0;
    parameter [0:0] C_I1 = 1'b0, C_I2 = 1'b0, C_I3 = 1'b0, C_I4 = 1'b0;
    parameter [2:0] C_FUNCTION = 3'd0;
    parameter [0:0] C_HORIZ  = 1'b0;
    parameter [0:0] C_COMP   = 1'b0;
    parameter [0:0] C_COMP_I = 1'b0;
    parameter [0:0] C_SELX = 1'b0, C_SELY1 = 1'b0, C_SELY2 = 1'b0;
    parameter [0:0] C_SEL_C = 1'b0;
    parameter [0:0] C_SEL_P = 1'b0;
    parameter [0:0] C_Y12 = 1'b0;
    parameter [0:0] C_CX_I = 1'b0, C_CY1_I = 1'b0, C_CY2_I = 1'b0;
    parameter [0:0] C_PX_I = 1'b0, C_PY1_I = 1'b0, C_PY2_I = 1'b0;
    parameter [0:0] C_C_P = 1'b0;
    parameter [1:0] C_CPE_CLK = 2'd0, C_CPE_EN = 2'd0, C_CPE_RES = 2'd0, C_CPE_SET = 2'd0;
    parameter [0:0] C_CLKSEL = 1'b0;
    parameter [0:0] C_ENSEL  = 1'b0;
    parameter [0:0] C_EN_SR  = 1'b0;
    parameter [0:0] C_L_D    = 1'b0;
    parameter [0:0] C_BR     = 1'b0;
    parameter [0:0] C_2D_IN  = 1'b0;
    parameter [2:0] C_SN = 3'd0;
    parameter [1:0] C_O1 = 2'd0, C_O2 = 2'd0;
    parameter [0:0] C_RAM_I1 = 1'b0, C_RAM_I2 = 1'b0;
    parameter [0:0] C_RAM_O1 = 1'b0, C_RAM_O2 = 1'b0;
    parameter [1:0] FF_INIT = 2'd0;

    input  IN1, IN2, IN3, IN4, IN5, IN6, IN7, IN8;
    input  CLK, EN, SR;
    input  CINX, CINY1, CINY2;
    input  PINX, PINY1, PINY2;
    input  RAM_I1, RAM_I2;
    output OUT1, OUT2;
    output RAM_O1, RAM_O2;
    output COUTX, COUTY1, COUTY2;
    output POUTX, POUTY1, POUTY2;

    reg out1, out2;
    assign OUT1 = out1;
    assign OUT2 = out2;
    assign RAM_O1 = 1'b0;
    assign RAM_O2 = 1'b0;

    assign COUTX  = ~CINX;
    assign COUTY1 = ~CINY1;
    assign COUTY2 = CINY2;
    assign POUTX  = PINX;
    assign POUTY1 = PINY1;
    assign POUTY2 = ~PINY2;
endmodule
