// MX8 as routing resource in an otherwise unused CPE: C_FUNCTION=0, all other bits 0,
// C_SN=k selects IN(k+1), C_O1=1 / C_O2=1 route MUXOUT to OUT1 / OUT2.
module tb_bridge;
  reg [7:0] in;
  reg clk, en, sr;
  integer errors = 0, n;
  genvar k;
  generate
    for (k = 0; k < 8; k = k + 1) begin : g
      wire out1, out2;
      cpe #(.C_SN(k), .C_O1(2'd1), .C_O2(2'd1), .C_RAM_I1(1'b1), .C_RAM_I2(1'b1)) dut (
        .IN1(in[0]), .IN2(in[1]), .IN3(in[2]), .IN4(in[3]), .IN5(in[4]), .IN6(in[5]), .IN7(in[6]), .IN8(in[7]),
        .CLK(clk), .EN(en), .SR(sr),
        .CINX(1'b0), .CINY1(1'b0), .CINY2(1'b0), .PINX(1'b0), .PINY1(1'b0), .PINY2(1'b0),
        .RAM_I1(1'b0), .RAM_I2(1'b0), .OUT1(out1), .OUT2(out2));
    end
  endgenerate
  integer kk;
  initial begin
    clk = 0; en = 0; sr = 0;
    for (n = 0; n < 64; n = n + 1) begin
      in = $random; clk = $random; en = $random; sr = $random;
      #2;
      // C_SN=k expected: OUT = in[k]
      if (g[0].out1 !== in[0] || g[1].out1 !== in[1] || g[2].out1 !== in[2] || g[3].out1 !== in[3] ||
          g[4].out1 !== in[4] || g[5].out1 !== in[5] || g[6].out1 !== in[6] || g[7].out1 !== in[7] ||
          g[0].out2 !== in[0] || g[7].out2 !== in[7]) begin
        errors = errors + 1;
        $display("mismatch in=%b out1=%b%b%b%b%b%b%b%b", in, g[7].out1, g[6].out1, g[5].out1, g[4].out1, g[3].out1, g[2].out1, g[1].out1, g[0].out1);
      end
    end
    $display("bridge test: %0d errors", errors);
    $finish;
  end
endmodule
