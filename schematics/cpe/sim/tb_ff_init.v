// FF_INIT of cpe.v: the registers start with Q = 0 (2), Q = 1 (3) or, not initialised (0, 1), with Q = 1.
// OUT1 and OUT2 are the registers (C_O1 = C_O2 = 0, C_RAM_I = 1; set and reset are off with C_CPE_SET = C_CPE_RES = 3, with 0 they would hold the registers set), as a flip-flop and as a latch.
//   iverilog -g2012 -o tb_ff_init.vvp cpe.v tb_ff_init.v && vvp tb_ff_init.vvp
`timescale 1ns/1ps

module tb_ff_init;
    integer errors;

    wire [3:0] ff1, ff2, la1, la2;

    genvar i;
    generate
        for (i = 0; i < 4; i = i + 1) begin : init
            cpe #(.FF_INIT(i), .C_L_D(1'b0), .C_RAM_I1(1'b1), .C_RAM_I2(1'b1), .C_CPE_RES(2'b11), .C_CPE_SET(2'b11)) u_ff (
                .IN1(1'b0), .IN2(1'b0), .IN3(1'b0), .IN4(1'b0), .IN5(1'b0), .IN6(1'b0), .IN7(1'b0), .IN8(1'b0),
                .CLK(1'b0), .EN(1'b0), .SR(1'b0), .CINX(1'b0), .CINY1(1'b0), .CINY2(1'b0),
                .PINX(1'b0), .PINY1(1'b0), .PINY2(1'b0), .RAM_I1(1'b0), .RAM_I2(1'b0),
                .OUT1(ff1[i]), .OUT2(ff2[i]), .RAM_O1(), .RAM_O2(),
                .COUTX(), .COUTY1(), .COUTY2(), .POUTX(), .POUTY1(), .POUTY2()
            );
            cpe #(.FF_INIT(i), .C_L_D(1'b1), .C_RAM_I1(1'b1), .C_RAM_I2(1'b1), .C_CPE_RES(2'b11), .C_CPE_SET(2'b11)) u_latch (
                .IN1(1'b0), .IN2(1'b0), .IN3(1'b0), .IN4(1'b0), .IN5(1'b0), .IN6(1'b0), .IN7(1'b0), .IN8(1'b0),
                .CLK(1'b0), .EN(1'b0), .SR(1'b0), .CINX(1'b0), .CINY1(1'b0), .CINY2(1'b0),
                .PINX(1'b0), .PINY1(1'b0), .PINY2(1'b0), .RAM_I1(1'b0), .RAM_I2(1'b0),
                .OUT1(la1[i]), .OUT2(la2[i]), .RAM_O1(), .RAM_O2(),
                .COUTX(), .COUTY1(), .COUTY2(), .POUTX(), .POUTY1(), .POUTY2()
            );
        end
    endgenerate

    // expected Q for FF_INIT = 0, 1, 2, 3
    wire [3:0] q = 4'b1011;

    initial begin
        errors = 0;
        #1;
        if (ff1 !== q || ff2 !== q || la1 !== q || la2 !== q) begin
            errors = 1;
            $display("FAIL ff1=%b ff2=%b latch1=%b latch2=%b, expected %b", ff1, ff2, la1, la2, q);
        end
        if (errors == 0) $display("PASS FF_INIT");
        $finish;
    end
endmodule
