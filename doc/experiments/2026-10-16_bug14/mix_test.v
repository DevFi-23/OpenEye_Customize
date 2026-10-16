// Minimal copy of the results_ready pattern of psum_pipeline.v (bug #14 analysis, not project RTL).
// state 0 = WAIT_TO_SEND_READY_SIGNAL (rr = 0), 1 = CALCULATE_PSUM, 2 = PSUM_GET_RESULTS, 3 = other.
module mix_test (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [1:0] state,
    input  wire       go,          // psum_ready_i_reg != 0
    input  wire [3:0] x,           // per-cluster ready / enable terms
    input  wire       exit_calc,   // CALCULATE_PSUM exit condition
    input  wire       clr,         // status_reg_enable_reg
    output reg        fire_calc,   // "if (results_ready & (psum_ready_i_reg != 0))" taken
    output reg        fire_get     // "if (results_ready)" taken in PSUM_GET_RESULTS
);
  reg rr;
  integer i;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rr        <= 0;
      fire_calc <= 0;
      fire_get  <= 0;
    end else begin
      fire_calc <= 0;
      fire_get  <= 0;
      case (state)
        2'd0: rr = 0;
        2'd1: begin
          if ((rr == 0) & go) begin
            rr = 1;
            for (i = 0; i < 4; i = i + 1) rr = rr & x[i];
          end
          if (rr & go) begin
            fire_calc <= 1;
            if (exit_calc) rr <= 1;
          end
        end
        2'd2: begin
          rr <= 1;
          for (i = 0; i < 4; i = i + 1) rr = rr & x[i];
          if (rr) fire_get <= 1;
        end
        default: ;
      endcase
      if (clr) rr <= 0;
    end
  end
endmodule
