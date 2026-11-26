// tb_requant.v: cycle behaviour of hdl/quantization_unit.v and hdl/activation_table.v in RTL simulation (Icarus).
// 1. Quantizer latency: a new psum every clock (pipelined). The edge that samples input k loads S1, the next one S2, the
//    third one S3 = the output register: the result is there after the 3rd rising edge counting the sampling edge, not
//    after the 2nd (one register per stage, 3 clocks of latency, one result per clock).
// 2. Leaky ReLU: the sign of the sum picks [neg_mant, neg_shift] in stage 1 (MNIST Conv1 numbers of onnx2model:
//    mant 8817157 / 2^31, neg 215 / 2^19, round half up).
// 3. Activation table: written at clock edges (we), read without a clock: value_o follows value_i within the same
//    simulation time step, with no clock edge in between.
`timescale 1ns / 1ps
module tb_requant;
  reg clk = 0;
  reg rst_n = 0;
  always #2 clk = ~clk;                                  // 4 ns period, posedge at 2, 6, 10, ... ns
  reg  signed [19:0] psum = 0;
  reg  leaky = 1;
  wire signed [7:0] q;
  quantization_unit #(.PSUM_WIDTH(20), .MANT_WIDTH(25), .OFFSET_WIDTH(8), .SHIFT_WIDTH(7), .OUT_WIDTH(8)) uq (
    .clk_i(clk), .rst_n(rst_n), .quant_mant(25'd8817157), .psum_data(psum), .quant_offset(8'sd0),
    .current_shift(7'd31), .act_min(-8'sd128), .leaky_en(leaky), .neg_mant(8'd215), .neg_shift(7'd19),
    .round_en(1'b1), .quantized_value(q));
  reg we = 0;
  reg [4:0] waddr = 0;
  reg [63:0] wdata = 0;
  reg signed [7:0] vin = 0;
  wire signed [7:0] vout;
  activation_table #(.TABLE_WORD_WIDTH(64)) ut (.clk_i(clk), .we_i(we), .waddr_i(waddr), .wdata_i(wdata),
                                                .value_i(vin), .value_o(vout));
  reg signed [19:0] stim [0:7];
  reg signed [7:0]  want [0:7];
  integer i, j, b, errors;
  reg signed [7:0] early;

  initial begin
    errors = 0;
    stim[0] =  20'sd2000;  want[0] =   8;   // 2000 * 0.0041058 = 8.21
    stim[1] = -20'sd2000;  want[1] =  -1;   // Leaky: 0.1 * -8.21 = -0.82 (without Leaky: -8)
    stim[2] =  20'sd10000; want[2] =  41;   // 41.06
    stim[3] = -20'sd10000; want[3] =  -4;   // -4.11
    stim[4] =  20'sd0;     want[4] =   0;
    stim[5] = -20'sd1;     want[5] =   0;   // -0.00041
    stim[6] =  20'sd30000; want[6] = 123;   // 123.17
    stim[7] = -20'sd30000; want[7] = -12;   // -12.32
    #1 rst_n = 1;
    // part 1 and 2: one input per clock, set just after an edge, sampled by the next edge E_k
    for (i = 0; i < 8; i = i + 1) begin
      @(posedge clk); #0.5 psum = stim[i];
    end
  end

  // checker for parts 1 and 2: input k is set after edge k+1 and sampled (S1) at edge k+2; S2 at edge k+3, S3 at edge
  // k+4: the result must be at q after edge k+4 and not yet after edge k+3
  integer edge_count = 0;
  always @(posedge clk) edge_count <= edge_count + 1;
  initial begin
    @(posedge rst_n);
    for (j = 0; j < 8; j = j + 1) begin
      wait (edge_count == j + 3); #0.3; early = q;          // 2nd edge (S1, S2 loaded)
      wait (edge_count == j + 4); #0.3;                     // 3rd edge (S3 loaded)
      $display("input %0d psum %6d: q %4d after the 3rd edge (want %4d) %s; after the 2nd edge q was %4d (previous input)",
               j, stim[j], q, want[j], (q == want[j]) ? "OK" : "WRONG", early);
      if (q != want[j]) errors = errors + 1;
      if (j > 0 && early != want[j-1]) errors = errors + 1;
    end
    // part 3: table entry e = 255 - e, written word by word (8 entries per 64-bit word, byte b = entry 8w + b)
    @(negedge clk);
    for (j = 0; j < 32; j = j + 1) begin
      we = 1; waddr = j;
      for (b = 0; b < 8; b = b + 1) wdata[8*b +: 8] = 255 - (8*j + b);
      @(negedge clk);
    end
    we = 0;
    @(posedge clk); #0.5;
    vin =  8'sd5;  #0.1;
    $display("t=%0.1f ns: value_i = %4d -> value_o = %4d (entry %0d holds %0d)", $realtime, vin, $unsigned(vout), 133, 255 - 133);
    if ($unsigned(vout) != 255 - 133) errors = errors + 1;
    vin = -8'sd3;  #0.1;
    $display("t=%0.1f ns: value_i = %4d -> value_o = %4d (entry %0d holds %0d)", $realtime, vin, $unsigned(vout), 125, 255 - 125);
    if ($unsigned(vout) != 255 - 125) errors = errors + 1;
    vin = -8'sd128; #0.1;
    $display("t=%0.1f ns: value_i = %4d -> value_o = %4d (entry %0d holds %0d)", $realtime, vin, $unsigned(vout), 0, 255);
    if ($unsigned(vout) != 255) errors = errors + 1;
    $display("the three reads lie between the posedges at %0.0f and %0.0f ns: the table needs no clock to read",
             $realtime - 0.8, $realtime + 3.2);
    $display("RESULT %s (%0d errors)", (errors == 0) ? "PASS" : "FAIL", errors);
    $finish;
  end
endmodule
