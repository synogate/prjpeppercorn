// Behavioural models for the sequential symbols used by the generated cpe.v
module cpe_dff(input C, input E, input D, input S, input R, output reg Q);
  initial Q = 1'b0;
  always @(posedge C or negedge S or negedge R)
    if (!R) Q <= 1'b0;
    else if (!S) Q <= 1'b1;
    else if (E) Q <= D;
endmodule

module cpe_dlt(input G, input E, input D, input S, input R, output reg Q);
  initial Q = 1'b0;
  always @* begin
    if (!R) Q = 1'b0;
    else if (!S) Q = 1'b1;
    else if (G & E) Q = D;
  end
endmodule
