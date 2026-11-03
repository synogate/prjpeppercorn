// Lab validation design: sends "Hello GateMate #n\r\n" on UART0_TX at 115200 8N1, 12 MHz clock.
// Also echoes UART0_RX level on LED-less internal reg (RX unused except to keep it in the design).
module top(input CLK12M, output UART0_TX, input UART0_RX);
  localparam DIV = 104;  // 12e6/115200 = 104.17
  reg [6:0] div = 0;
  reg [9:0] sh = 10'h3FF;
  reg [3:0] bitn = 0;
  reg busy = 0;
  reg [5:0] idx = 0;
  reg [3:0] cnt = 0;
  reg [23:0] gap = 0;
  wire [7:0] ch =
    idx==0?"H": idx==1?"e": idx==2?"l": idx==3?"l": idx==4?"o": idx==5?" ":
    idx==6?"G": idx==7?"M": idx==8?"#": idx==9? (cnt<10 ? "0"+cnt : "A"+cnt-10) :
    idx==10?8'h0D : 8'h0A;
  reg tx = 1;
  assign UART0_TX = tx;
  always @(posedge CLK12M) begin
    if (!busy) begin
      if (gap != 0) gap <= gap - 1;
      else begin
        sh <= {1'b1, ch, 1'b0}; busy <= 1; bitn <= 0; div <= 0;
      end
    end else begin
      tx <= sh[0];
      if (div == DIV-1) begin
        div <= 0; sh <= {1'b1, sh[9:1]};
        if (bitn == 9) begin
          busy <= 0; tx <= 1;
          if (idx == 11) begin idx <= 0; cnt <= cnt + 1; gap <= 24'd600000; end  // ~50ms pause
          else idx <= idx + 1;
        end else bitn <= bitn + 1;
      end else div <= div + 1;
    end
  end
endmodule
