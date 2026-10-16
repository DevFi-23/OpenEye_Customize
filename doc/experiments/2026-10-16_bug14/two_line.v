module two_line (input clk, input a, output reg q);
  reg r;
  initial r = 0;
  always @(posedge clk) begin
    r <= 1;          // non-blocking, written first
    r = r & a;       // blocking, written second (same pattern as PSUM_GET_RESULTS)
    q <= r;
  end
endmodule
