# 2026-11-02: RTL design of the activation functions (step B), for review

Design only; no RTL was changed. Step A (`2026-11-02_activation.md`) fixed the arithmetic: the reference
(`simple_layer_operations.batchnorm_output`) is the specification, and the RTL must match it bit for bit:

* requantize(v) = (mant * v + r) >> shift, r = 0 (floor) or 2^(shift-1) (round half up, `act_round`)
* mode clamp (none / ReLU): clamp(requantize(v), act_min, 127), as today
* mode leaky: [mant, shift] for v >= 0, [mant_n, shift_n] for v < 0, clamp to [-128, 127]
* mode table: T[clamp(requantize(v), -128, 127) + 128], T loaded per layer

v is the psum plus the quantizer offset (always 0 in this flow). Requirements: modes clamp/ReLU bit-exact and
cycle-exact as today (0 cycles of change in the 12 baseline cases); 0 extra cycles per value in every mode; the
quantizer's 3-clock latency unchanged, so none of the 3-clock delay chains of `RECEIVE_PSUMS_TO_IACT` changes.

## 1. Facts of the present RTL the design builds on

* `psum_pipeline.v` instantiates `TRANS_WORDS` quantizers, but only lanes 0 ... `WRITEBACK_WORDS` - 1
  (`min(TRANS_WORDS, NUM_GLB_PSUM)`, 4 in the baseline configuration) feed the write-back; Vivado keeps 4 instances.
  Each takes 166-169 LUT, 75 FF and **1 DSP48E2** (the multiplication; lane 3 678 LUT / 109 FF with shared logic).
* The receiver in `OpenEye_FPGA.v` (`RECEIVE_PSUMS_TO_IACT`) copies `quantized_value_reg[a]` (a wire of
  `quantized_value_flat`) straight into the register `iact_to_psum_mux_reg`, no logic in between.
* The quantizer is not among the 80 paths of the post-route timing report (worst +0.020 ns ... +0.332 ns): it has more
  than about 0.3 ns of slack.
* Main FSM state register `reg [3:0] fsm_current_state`, codes 0-14 used, 15 free. `fsm_last_state` is only compared
  with `GET_PARAMETERS`, so a state after `GET_QUANTIZE` does not disturb it.
* The per-layer configuration comes from the status words (`test/cocotb_fpga/regmap.yaml` -> generated
  `dma_storage.v`); the last status word uses 40 of 64 bits.
* The quantization stream is one section (`stream_parallel_dict["quantize"]`), `QUANT_TRANS_CYCLES` words consumed in
  `GET_QUANTIZE`; the host sends sections back to back.

## 2. Configuration: 19 new bits in the last status word (0 extra DMA words)

| Field | Width | Meaning |
|---|---:|---|
| `act_mode` | 2 | 0 clamp only (none / ReLU through `quant_clamp_low`, as today), 1 Leaky (two slopes), 2 table, 3 reserved (= 0) |
| `act_round` | 1 | 0 floor (today), 1 round half up, every mode |
| `act_neg_mant` | 8 | mantissa of the negative slope (Leaky) |
| `act_neg_shift` | 7 | shift of the negative slope (Leaky) |
| `act_keep_table` | 1 | table mode: keep the table of the previous layer, no load |

40 + 19 = 59 bits: the word count of the status stream does not change. All fields 0 = today's behaviour.

## 3. `quantization_unit.v`: slope and rounding chosen in stage 1, the DSP adds the rounding constant

New inputs (constant while a layer runs): `neg_mant`, `neg_shift`, `leaky_en` (= mode 1), `round_en`. The stages keep
their structure:

| Stage | Today | New |
|---|---|---|
| 1 | sum = psum + offset; register sum, mant, shift | the same, plus: neg = sum < 0 (the adder's sign bit, same stage); choose mant / shift = (leaky_en & neg) ? (neg_mant, neg_shift) : (mant, shift); register the chosen pair and round_en |
| 2 | prod = mant * sum (DSP) | prod = mant * sum + rc, rc = round_en & shift != 0 ? 1 << (shift - 1) : 0 (the DSP48E2 computes A * B + C in the same stage: the rounding needs no adder in the fabric; rc is decoded from the registered shift) |
| 3 | clamp(prod >>> shift, act_min, 127) | unchanged |

```verilog
// stage 1 (sketch)
wire signed [SUM_WIDTH-1:0] sum = psum_data + quant_offset;
wire use_neg = leaky_en & sum[SUM_WIDTH-1];
always @(posedge clk_i or negedge rst_n)
  if (!rst_n) begin ... end else begin
    sum_s1   <= sum;
    mant_s1  <= use_neg ? {{(MANT_WIDTH-8){1'b0}}, neg_mant} : quant_mant;
    shift_s1 <= use_neg ? neg_shift : current_shift;
    round_s1 <= round_en;
  end
// stage 2: the DSP's post-adder takes the rounding constant
wire signed [PROD_WIDTH-1:0] rc = (round_s1 && shift_s1 != 0) ? ({{(PROD_WIDTH-1){1'b0}}, 1'b1} << (shift_s1 - 1)) : 0;
always @(posedge clk_i ...) prod_s2 <= mant_s1 * sum_s1 + rc;
```

Exactness: (mant * v + 2^(s-1)) >> s is round half up of mant * v / 2^s for negative values too (arithmetic shift =
floor), the reference's formula. With leaky_en = 0 and round_en = 0 every register gets today's value: modes 0 is the
old datapath. The constant needs shift <= PROD_WIDTH - 1 (46): `onnx2model.hardware_multiplier` gives shifts of
about 13-20, and the toolchain refuses a larger one. Cost per lane: about 15 LUT (two muxes, the decoder), 9 FF.

## 4. Table: banked LUTRAM after the quantizer, read without a clock (design A)

New module `activation_table.v`, one instance per write-back lane (`gen_quant_unit[gi]` with gi < `WRITEBACK_WORDS`):

* **Banks so a DMA word is written in one clock.** E = `DMA_BITWIDTH` / 8 entries per DMA word (8 at 64 bit). Bank b
  (0 ... E-1) holds the entries i with i mod E = b at address i / E (32 deep at 64 bit). DMA word w carries entries
  w * E ... w * E + E - 1, byte b to bank b at address w: all E banks are written at once, so the table loads at DMA
  speed, 256 / E words (32 at 64 bit, 16 at 128 bit, 64 at 32 bit).
* **Read**: index = quantized_value + 128 = {~q[7], q[6:0]}; every bank is read asynchronously at index / E, an E:1
  mux takes bank index mod E. In LUTRAM a 32 x 8 bank is 4 LUT6, so 8 banks are 32 LUT, the 8:1 mux of 8 bits about
  16 LUT.
* **Output**: `quantized_value_flat` lane = (act_mode == 2) ? table output : quantized_value. Modes 0 and 1 take the
  quantizer's register directly (the path of today).
* The write port (`act_table_we`, `act_table_addr`, `act_table_data` = the DMA word) is broadcast to the copies of all
  lanes.

```verilog
// activation_table.v (sketch), ENTRIES = DMA_BITWIDTH / 8, DEPTH = 256 / ENTRIES
reg [7:0] bank [0:ENTRIES-1][0:DEPTH-1];          // inferred as distributed RAM
always @(posedge clk_i)
  if (we) for (b = 0; b < ENTRIES; b = b + 1) bank[b][waddr] <= wdata[8*b +: 8];
wire [7:0] index = {~q[7], q[6:0]};
assign table_o = bank[index[LOG_E-1:0]][index[7:LOG_E]];
```

Timing of design A: quantizer stage-3 register -> LUTRAM read (index fans out to 8 banks) -> E:1 mux -> mode mux ->
`iact_to_psum_mux_reg` in `OpenEye_FPGA.v`. Today this path is a register-to-register wire (not in the timing
report); the table adds about 1 ns of logic plus routing to it, well inside 4 ns, but the design's margin is only
+0.020 ns elsewhere, so Vivado has to confirm it. Fallback (design B): register the table
output and make every 3-clock delay chain of `RECEIVE_PSUMS_TO_IACT` 4 clocks (`fsm_psum_cycle >= 7` -> 8 and the
`_3` registers); +1 clock per write-back burst, and it touches the code of bugs #25/#26, so only if A fails timing.

## 5. `psum_pipeline.v`

* New ports: `act_mode[1:0]`, `act_round`, `act_neg_mant[7:0]`, `act_neg_shift[6:0]`, `act_table_we`,
  `act_table_addr`, `act_table_data[DMA_BITWIDTH-1:0]`.
* To every quantizer: `leaky_en = (act_mode == 1)`, `round_en = act_round`, `neg_mant`, `neg_shift`.
* `activation_table` instances for lanes 0 ... `WRITEBACK_WORDS` - 1 and the output mux; lanes from
  `WRITEBACK_WORDS` on stay as today (no table).

## 6. `OpenEye_FPGA.v`

* Wires of the 5 new status fields from `dma_storage`, to `psum_pipeline`.
* `localparam GET_ACTIVATION = 4'd15`, `ACT_TABLE_WORDS = 2048 / DMA_BITWIDTH`.
* Exit of `GET_QUANTIZE` (last quant word accepted): as today, except that a non-pooling layer with
  `act_mode == 2 && !act_keep_table` goes to `GET_ACTIVATION` instead of `START_CONVERTER` and keeps `ready_dma_o`
  high (no bubble in the stream).
* `GET_ACTIVATION`: `ready_dma_o` high; every accepted word (`enable_dma_i_reg`) is written to the table copies at
  address `fsm_cycle` (registered write enable / address / data from `data_dma_i_reg`); after `ACT_TABLE_WORDS` words
  `ready_dma_o` low, `fsm_cycle` 0, `START_CONVERTER`. Nothing else of the layer depends on it.
* A trace wire for the profiler, next to the existing `quant_stage_traces`: `act_capture` = the condition under which
  `RECEIVE_PSUMS_TO_IACT` takes `quantized_value_reg` into `iact_to_psum_mux_reg` (unused by the logic, removed by
  synthesis).
* Pooling layers, the final readout (raw psums, no quantizer) and layers in mode 0 do not change.

## 7. Python side of step B

* Mappers (`conv_mapper`, `dense_mapper`, `pooling_mapper` = 0): the 5 fields in `pack_registers` from
  `act_mode` / `act_round` / `act_negative` (and keep-table when the previous layer has the same table).
* `write_quant_and_offset` appends the `ACT_TABLE_WORDS` table words after the quantization words when the layer is in
  table mode and does not keep the table: byte b of word w = T[w * E + b]. The host sends them in the same section, so
  the testbench needs no change.
* `check_rtl_activation` then refuses only what the RTL cannot do: an activation on the last layer (its results go out
  as raw psums), a Leaky slope that does not fit 8 + 7 bits.
* The reference is unchanged (it already computes the modes).

## 8. Profiler (step C, Python only, uses the trace wire)

* `PROFILE_PHASES[15] = "load_act"`: cycles, DMA words, memory stalls and bus efficiency of the table load like every
  load phase; in `profile_report`, `paper_table3` and `test_profile_phases`.
* Per layer, in `profile.json`: `activation = {mode, capture_cycles, lane_values, zeros, negatives}` from
  `act_capture` and the write-back lanes of `quantized_value_flat` sampled every clock (observation only, 0 cycles
  of influence); the zero fraction of the next layer's input after pooling from the testbench's iact buffer check.
* The cost of an activation is measured as a difference: the same model with the activation and in mode 0,
  `run_profile --compare` per phase and layer (`load_act`, `writeback`, and the next layers' `compute`).

## 9. Cost

| | Modes 0 (none / ReLU) | Leaky | Table (SiLU, hard-swish) |
|---|---:|---:|---:|
| Cycles per value | 0 | 0 | 0 (design A) |
| Cycles per layer | 0 | 0 | 256 / E words (32 at DMA 64 bit), 0 with `act_keep_table` |
| DMA words per layer | 0 | 0 | 32 at 64 bit |
| LUT (4 lanes) | | ~60 (mux, rounding decoder) | ~220 (4 x 8 banks of LUTRAM + muxes) |
| FF | 19 (status fields, shared) | ~40 | ~10 (write address/enable) |
| BRAM / DSP | 0 / 0 | 0 / 0 (the DSP's post-adder) | 0 / 0 |

In total about 300 LUT (+0.5 % of 60.6k), 70 FF; the estimate is replaced by the Vivado run.

## 10. Verification

| Check | Expected |
|---|---|
| `test/cocotb_quantization/test_quantization_unit.py` extended: leaky (random psums, both signs, several slopes), round on/off, every shift, against the Python model | bit-exact |
| Unit testbench of `activation_table`: all 256 indices after a load at DMA 32/64/128 bit, reload, keep | bit-exact |
| New system tests like `test_int8_clamp.py`: every mode x round on Conv -> Conv, Conv -> Pool -> Conv, Dense -> Dense, MLP, `NUM_GLB_PSUM` 2 and 4 (random models, activation set through test hooks in the integer domain) | PASS, iact buffer checks bit-exact |
| `test_real_model.py` for the trained Leaky ReLU, SiLU, hard-swish models (test images 0, 1; floor and round) | the whole network bit-exact, class = label |
| RTL regression 162 tests | 157 PASS + 5 known xfail |
| 12 baseline cases (mode 0) | 0 cycles, 0 DMA words of change |
| Table 3 (16 configurations) | 13/16 as today, 0 cycles of change |
| Lint | 0 new warnings |
| Vivado 4 ns | 0 critical, 250 MHz met, resources as section 9 (and design A's table path) |

## 11. Decisions for the user

1. Design A (table read without a clock, 0 cycles) first, design B only if Vivado fails timing. Recommended.
2. `act_round` per layer, default 0 (floor): the toolchain sets 1 for Leaky ReLU, SiLU, hard-swish (step A), keeps 0
   for ReLU.
3. Tables only for the write-back lanes (`WRITEBACK_WORDS`), not for all `TRANS_WORDS`.
4. Step C (profiler) right after B, then D (measurements of the four trained variants on the RTL).
