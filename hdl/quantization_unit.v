// This file is part of the OpenEye project.
// © Fachhochschule Dortmund – University of Applied Sciences and Arts (until 2025), Universität Duisburg-Essen (since 2025).
// SPDX-License-Identifier: SHL-2.1
// For more details, see the LICENSE file in the root directory of this project.

`timescale 1ns / 1ps

// -----------------------------------------------------------------------
// quantization_unit_pipelined
//
// Pipelined version of quantization_unit. Computes:
//
//   quantized_value = clamp((quant_mant * (psum_data + quant_offset)) >>> shift,
//                           act_min, 2^(OUT_WIDTH-1)-1)
//
// over 3 clock cycles instead of one big combinational path:
//
//   Stage 1 (S1): register inputs, compute (psum_data + quant_offset)
//   Stage 2 (S2): register sum, compute multiplication with quant_mant
//   Stage 3 (S3): register product, apply arithmetic right-shift, saturate
//                 to [act_min, 2^(OUT_WIDTH-1)-1] -> output
//
// Splitting add / multiply / shift into separate stages shortens the
// critical path (helpful once TRANS_WORDS instances run in parallel)
// at the cost of a fixed 3-cycle latency and a valid_out handshake.
//
// Intermediate widths are widened by one bit for the add stage and by
// MANT_WIDTH bits for the multiply stage to avoid overflow.
//
// Saturation: a value outside the output range is clamped to the nearest
// bound instead of keeping its low OUT_WIDTH bits (which turned 130 into
// -126 and -129 into 127). act_min is the lower bound: -2^(OUT_WIDTH-1) for
// plain int8 saturation, the output zero point for a fused ReLU (0 when the
// activations are quantized with zero point 0). It is a per-layer setting
// that stays constant while the layer runs.
//
// Activations (doc/experiments/2026-11-02_activation_rtl_design.md), per-layer
// settings as well:
//   leaky_en  Leaky ReLU: a negative sum (psum_data + quant_offset < 0) uses
//             neg_mant / neg_shift instead of quant_mant / current_shift.
//             Stage 1 chooses the pair by the sign of the sum it computes.
//   round_en  round half up instead of the floor: stage 2 adds 2^(shift-1) to
//             the product (the multiplier's post-adder), so
//             (mant * sum + 2^(shift-1)) >>> shift. Needs shift <= PROD_WIDTH-1.
// With leaky_en = 0 and round_en = 0 every register gets the value it had
// before these options. A table activation (SiLU, hard-swish) follows the
// quantizer in psum_pipeline.v (activation_table.v).
// -----------------------------------------------------------------------
module quantization_unit #(
    parameter PSUM_WIDTH   = 32,   // width of one PSUM word (psum_buffer_data_r slice)
    parameter MANT_WIDTH   = 8,    // width of quant_mant
    parameter OFFSET_WIDTH = 16,   // width of quant_offset
    parameter SHIFT_WIDTH  = 5,    // width of current_shift
    parameter OUT_WIDTH    = 8    // width of quantized_value
) (
    input  wire                           clk_i,
    input  wire                           rst_n,          // asynchronous, active-low reset

    input  wire signed [MANT_WIDTH-1:0]   quant_mant,      // quantization multiplier (per filter)
    input  wire signed [PSUM_WIDTH-1:0]   psum_data,       // raw accumulated PSUM word
    input  wire signed [OFFSET_WIDTH-1:0] quant_offset,    // quantization offset (per filter)
    input  wire        [SHIFT_WIDTH-1:0]  current_shift,   // arithmetic right-shift amount
    input  wire signed [OUT_WIDTH-1:0]    act_min,         // lower saturation bound (per layer)
    input  wire                           leaky_en,        // negative sums use neg_mant / neg_shift (per layer)
    input  wire        [7:0]              neg_mant,        // Leaky ReLU: mantissa of the negative slope
    input  wire        [SHIFT_WIDTH-1:0]  neg_shift,       // Leaky ReLU: shift of the negative slope
    input  wire                           round_en,        // round half up instead of the floor (per layer)

    output reg  signed [OUT_WIDTH-1:0]    quantized_value // quantized result, valid when valid_out = 1
);

    // Internal widths sized to avoid overflow in the intermediate steps.
    localparam SUM_WIDTH  = ((PSUM_WIDTH > OFFSET_WIDTH) ? PSUM_WIDTH : OFFSET_WIDTH) + 1;
    localparam PROD_WIDTH = SUM_WIDTH + MANT_WIDTH;

    // ---------------------------------------------------------------
    // Stage 1: sum = psum_data + quant_offset; the slope of the sum's sign
    // ---------------------------------------------------------------
    reg signed [SUM_WIDTH-1:0]   sum_s1;
    reg signed [MANT_WIDTH-1:0]  mant_s1;
    reg        [SHIFT_WIDTH-1:0] shift_s1;
    reg                          round_s1;
    reg                          valid_s1;
    wire signed [SUM_WIDTH-1:0]  sum_w   = psum_data + quant_offset;
    wire                         use_neg = leaky_en & sum_w[SUM_WIDTH-1];

    always @(posedge clk_i or negedge rst_n) begin
        if (!rst_n) begin
            sum_s1   <= {SUM_WIDTH{1'b0}};
            mant_s1  <= {MANT_WIDTH{1'b0}};
            shift_s1 <= {SHIFT_WIDTH{1'b0}};
            round_s1 <= 1'b0;
        end else begin
            sum_s1   <= sum_w;
            mant_s1  <= use_neg ? {{(MANT_WIDTH-8){1'b0}}, neg_mant} : quant_mant;
            shift_s1 <= use_neg ? neg_shift : current_shift;
            round_s1 <= round_en;
        end
    end

    // ---------------------------------------------------------------
    // Stage 2: prod = mant_s1 * sum_s1 (+ 2^(shift_s1-1) when rounding)
    // ---------------------------------------------------------------
    reg signed [PROD_WIDTH-1:0]  prod_s2;
    reg        [SHIFT_WIDTH-1:0] shift_s2;
    reg                          valid_s2;
    wire signed [PROD_WIDTH-1:0] round_const = (round_s1 && (shift_s1 != 0)) ?
        ({{(PROD_WIDTH-1){1'b0}}, 1'b1} << (shift_s1 - 1'b1)) : {PROD_WIDTH{1'b0}};

    always @(posedge clk_i or negedge rst_n) begin
        if (!rst_n) begin
            prod_s2  <= {PROD_WIDTH{1'b0}};
            shift_s2 <= {SHIFT_WIDTH{1'b0}};
            valid_s2 <= 1'b0;
        end else begin
            prod_s2  <= mant_s1 * sum_s1 + round_const;
            shift_s2 <= shift_s1;
        end
    end

    // ---------------------------------------------------------------
    // Stage 3: quantized_value = clamp(prod_s2 >>> shift_s2, act_min, OUT_MAX)
    // ---------------------------------------------------------------
    localparam signed [PROD_WIDTH-1:0] OUT_MAX = (1 << (OUT_WIDTH-1)) - 1;
    wire signed [PROD_WIDTH-1:0] shifted_s2  = prod_s2 >>> shift_s2;
    wire signed [PROD_WIDTH-1:0] act_min_ext = {{(PROD_WIDTH-OUT_WIDTH){act_min[OUT_WIDTH-1]}}, act_min};

    always @(posedge clk_i or negedge rst_n) begin
        if (!rst_n) begin
            quantized_value <= {OUT_WIDTH{1'b0}};
        end else if (shifted_s2 > OUT_MAX) begin
            quantized_value <= OUT_MAX[OUT_WIDTH-1:0];
        end else if (shifted_s2 < act_min_ext) begin
            quantized_value <= act_min;
        end else begin
            quantized_value <= shifted_s2[OUT_WIDTH-1:0];
        end
    end

endmodule