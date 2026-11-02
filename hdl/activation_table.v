// This file is part of the OpenEye project.
// SPDX-License-Identifier: SHL-2.1
// For more details, see the LICENSE file in the root directory of this project.
`timescale 1ns / 1ps
// -----------------------------------------------------------------------
// activation_table
//
// 256-entry int8 -> int8 lookup table of a table activation (SiLU,
// hard-swish, or any other function of an int8 value), one instance per
// write-back lane of psum_pipeline.v, right after the lane's quantizer:
//
//   value_o = T[value_i + 128]
//
// value_i is the quantizer's clamped int8 output (the pre-activation at the
// layer's output scale); the toolchain computes T so that value_o is the
// activation at the next layer's input scale (onnx2model.activation_table,
// doc/experiments/2026-11-02_activation_rtl_design.md).
//
// The table is loaded from the DMA in the main FSM state GET_ACTIVATION, one
// DMA word per clock: word w carries the entries w*ENTRIES ... w*ENTRIES +
// ENTRIES - 1, entry w*ENTRIES + b in byte b. So that a whole word is written
// in one clock the table is split into ENTRIES banks: bank b holds the entries
// i with i mod ENTRIES = b, at address i / ENTRIES, and every bank takes its
// byte of the word at address w. The banks are read without a clock
// (distributed RAM): the lane's output keeps the quantizer's 3-clock latency.
// -----------------------------------------------------------------------
module activation_table #(
    parameter  TABLE_WORD_WIDTH = 64,                     // width of one table word (the DMA word)
    localparam ENTRIES      = TABLE_WORD_WIDTH / 8,       // entries per table word = banks
    localparam LOG_ENTRIES  = $clog2(ENTRIES),
    localparam DEPTH        = 256 / ENTRIES,              // entries per bank = table words
    localparam ADDR_WIDTH   = (DEPTH > 1) ? $clog2(DEPTH) : 1
) (
    input  wire                     clk_i,
    input  wire                     we_i,      // write table word waddr_i
    input  wire [ADDR_WIDTH-1:0]    waddr_i,   // table word number 0 ... DEPTH-1
    input  wire [TABLE_WORD_WIDTH-1:0] wdata_i, // entry waddr_i*ENTRIES + b in byte b
    input  wire signed [7:0]        value_i,   // table input (int8)
    output wire signed [7:0]        value_o    // T[value_i + 128]
);
    // value_i + 128 for an int8 value: flip the sign bit
    wire [7:0] index = {~value_i[7], value_i[6:0]};
    wire [7:0] bank_out [0:ENTRIES-1];

    genvar b;
    generate
        for (b = 0; b < ENTRIES; b = b + 1) begin : gen_bank
            (* ram_style = "distributed" *) reg [7:0] mem [0:DEPTH-1];
            always @(posedge clk_i) begin
                if (we_i) mem[waddr_i] <= wdata_i[8*b+:8];
            end
            assign bank_out[b] = mem[index[7:LOG_ENTRIES]];
        end
    endgenerate

    assign value_o = bank_out[index[LOG_ENTRIES-1:0]];
endmodule
