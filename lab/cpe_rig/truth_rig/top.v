// Truth-table rig, version 3: every input of the CPE under test has its own orthogonal square wave, including the six carry / propagate inputs.
// x[k] = registered copy of bit k of a free-running counter (f_k = 12 MHz / 2^(k+1)); UART0_TX = reference = bit 17 (rising edge starts a full enumeration
// of 2^17 states, falling edge ends it).  UART0_RX = what the selector sees.
//   DUT  X146Y19  CC_MX8, patched into the CPE under test.  IN1..IN8 = x0..x7 (fixed pins, never swapped or inverted), CLK / EN / SR = x8 / x9 / x10.
//   CPINX  X145Y19  CC_MX8 west of the DUT: IN1 = x11, IN2 = x12 (patched to drive CINX and PINX of the DUT through COUTX / POUTX).
//   CPINY  X146Y18  CC_MX8 south of the DUT: IN1..IN4 = x13..x16 (patched to drive CINY1, CINY2, PINY1, PINY2 through COUTY1/2, POUTY1/2).
//   dut_o1  an L2T4 on the upper half of the DUT CPE: only there so that nextpnr routes the OUT1 wire of the DUT (the MX8 cluster owns the whole CPE otherwise).
//   sel  CC_MX8 in front of the pad: IN1 = OUT2 wire of the DUT (MUXOUT net), IN2 = OUT1 wire (dut_o1).  C_SN in the bitfile picks which one reaches UART0_RX.
// place_mx8.py (--pre-place) binds the MX8 clusters and moves the dummy of the DUT's upper half out of the way.
module top(input CLK12M, output UART0_TX, output UART0_RX);
  reg [17:0] cnt = 0;
  reg [16:0] x = 0;
  reg ref = 0;
  always @(posedge CLK12M) begin
    cnt <= cnt + 1;
    x   <= cnt[16:0];
    ref <= cnt[17];
  end
  assign UART0_TX = ref;

  wire out2, out1;
  (* keep *) CC_MX8 dut (.D0(x[0]), .D1(x[1]), .D2(x[2]), .D3(x[3]), .D4(x[4]), .D5(x[5]), .D6(x[6]), .D7(x[7]), .S0(x[8]), .S1(x[9]), .S2(x[10]), .Y(out2));
  (* keep, BEL = "X146Y19/CPE_LT_U" *) CC_L2T4 dut_o1 (.I0(1'b0), .I1(1'b0), .I2(1'b0), .I3(1'b0), .O(out1));
  (* keep *) CC_MX8 cpinx (.D0(x[11]), .D1(x[12]), .D2(1'b0), .D3(1'b0), .D4(1'b0), .D5(1'b0), .D6(1'b0), .D7(1'b0), .S0(1'b0), .S1(1'b0), .S2(1'b0), .Y());
  (* keep *) CC_MX8 cpiny (.D0(x[13]), .D1(x[14]), .D2(x[15]), .D3(x[16]), .D4(1'b0), .D5(1'b0), .D6(1'b0), .D7(1'b0), .S0(1'b0), .S1(1'b0), .S2(1'b0), .Y());
  (* keep *) CC_MX8 sel (.D0(out2), .D1(out1), .D2(1'b0), .D3(1'b0), .D4(1'b0), .D5(1'b0), .D6(1'b0), .D7(1'b0), .S0(1'b0), .S1(1'b0), .S2(1'b0), .Y(UART0_RX));
endmodule
