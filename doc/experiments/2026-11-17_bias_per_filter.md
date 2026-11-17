# 2026-11-17: send the bias once per filter instead of as a whole psum map (proposal, nothing changed)

Refresh of the design of README_FI section 8c "1.1 gửi bias theo filter" (2026-10-15, row C of the roadmap) against the
current code (`dev` = `f435068`) and the current measurements. No RTL or Python was changed.

## 1. How the bias is loaded today

* The psum buffer (`psum_pipeline.v`, one address = `CLUSTERS * NUM_GLB_PSUM` accumulators of `DATA_PSUM_BITWIDTH` =
  20 bits) is the accumulator of the whole layer. `CALCULATE_PSUM` feeds an address into the PE chain when the PEs report
  their pass done, `PSUM_GET_RESULTS` writes the sum back. Before the first pass the buffer must hold the bias.
* Python (`psum_stream_mapper.PsumStreamMapper.get_psum_stream`, serial branch) therefore sends the bias of **every
  output value**: for each x pass `k`, each row `j`, each filter (`bias_stream_filter_order`, bug #32), one 64-bit word
  with the bias twice, repeated `block_length = (NUM_GLB_PSUM / 2 * Clusters) / different_kernels_per_calculation`
  times. `trans_cycles_psum = filters * iact_size_y * iact_x_line_repetitions * ceil(NUM_GLB_PSUM * Clusters * 20 / 64)`
  (`layer_parameters.py:1459`).
* `GET_BIAS` of `psum_pipeline.v` shifts `CONV_BIAS_CYCLES = CLUSTERS * NUM_GLB_PSUM / 2` words into one address and writes
  it; `psum_cnt` (addresses of the layer, used by the main FSM) is set at the end. Dense / FC layers already send one
  word per filter and cluster column (32 and 12 words in the Table 2 network) and are not concerned.
* So the DMA moves a whole 20-bit map of the layer output for F distinct numbers: Conv1 of the trained MNIST net,
  32 biases, 14,336 words (115 KB in DRAM).

Measured share (`load_bias`, ideal memory):

| Run | load_bias | share of the network |
|---|---:|---:|
| Trained MNIST (CR 2, CC 2, X 4), 16 runs of `doc/perf/activation_2026-11-12_rounding` | 23,308 cycles | 9.7-10.7 % |
| Table 2 network, 16 configurations of Table 3 (`doc/perf/paper_table3_2026-11-04`) | 10,796-11,692 cycles | 5.1 % (CR 1 X 2) to 18.7 % (CR 8 X 4) |

## 2. Options

| | What | DMA words of a Conv layer | Cycles left |
|---|---|---:|---|
| today | whole map | F x rows x x-passes x `CLUSTERS * NUM_GLB_PSUM / 2` / groups | all of them |
| **A** | F biases into a table, a counter rewrites the same addresses with the same content as today, one address per cycle | ceil(F / 2) | one cycle per address (today's words / `CONV_BIAS_CYCLES`) |
| **A, background** | as A, but the rewrite runs in the PSUM FSM's idle time (it is idle from `GET_BIAS` until the PEs finish the first pass) while the main FSM goes on with `GET_QUANTIZE`, `GET_ACTIVATION`, `CONVERT_IACT` | ceil(F / 2) | only the part of the rewrite that is not done when the first `CALCULATE_PSUM` starts (expected about 0, to measure) |
| B | no write at all: in the first channel pass `CALCULATE_PSUM` feeds the bias of the address's filter instead of the buffer word | ceil(F / 2) | 0 |
| C (rejected) | psum starts at 0, the bias is added in the quantizer | ceil(F / 2) | 0, but needs bug #12 (`current_filter` never increments) fixed and a zeroed buffer (same work as A or B) |

Estimate from the saved profiles (Conv layers: old `load_bias` replaced by ceil(F / 2) words for B, plus one cycle per
address for A; Dense unchanged):

| Run | A (sequential) | A background / B |
|---|---:|---:|
| Trained MNIST, ReLU sparse (218,564) | −9.3 % | −10.6 % |
| Trained MNIST, SiLU dense (225,317) | −9.0 % | −10.3 % |
| Table 3, CR 1 X 2 | −2.5 % | −5.1 % |
| Table 3, CR 2 X 4 | −11.4 % | −13.0 % |
| Table 3, CR 8 X 4 | −17.5 to −18.0 % | −18.1 to −18.5 % |

With the `typical` memory model (about 1.44 cycles per DMA word) the gain is larger. It is the same in sparse and dense
builds and for every activation function. The bias traffic of a Conv layer falls by a factor of 56 (Table 2 Conv3, 896 -> 16 words) to 896 (MNIST Conv1, 14,336 -> 16).

## 3. What would change (option A, background; recommended)

RTL (needs approval):

| File | Change |
|---|---|
| `hdl/psum_pipeline.v` | bias table, depth `QUANT_AMOUNT` (the per-layer filter bound the quantization words already impose), 20 bits, written by `GET_BIAS` (2 biases per DMA word) when the layer's `bias_per_filter` bit is set; a rewrite block: loop filter group g -> x pass k -> row j, address `(k * rows + j) * groups + g`, word = the group's biases each replicated over `CLUSTERS * NUM_GLB_PSUM / groups` lanes in the order of `bias_stream_filter_order` (#32), one address per cycle on the existing write port; reading the table once per group avoids a multi-port table; `psum_cnt` set when the rewrite ends; the first `CALCULATE_PSUM` waits for the end of the rewrite (no other writer of the buffer before it); the old shift-register path kept for `bias_per_filter = 0` |
| `hdl/OpenEye_FPGA.v` | new fields from `dma_storage` to `psum_pipeline`; `GET_BIAS` leaves after `trans_cycles_psum` = ceil(F / 2) words as today; no new main-FSM state (the 4-bit state is full, 16 states) |
| `test/cocotb_fpga/regmap.yaml` (+ generated `dma_storage.v`) | `bias_per_filter` (1 bit), kernel groups (2-3 bits), rewrite address count or rows / x passes; the status word counts at DMA 32 / 64 / 128 checked as for the activation fields |
| parameters | build switch `BIAS_PER_FILTER_EN`, first default 0 (every baseline unchanged), then 1 after the checks |

Python:

| File | Change |
|---|---|
| `src/open_eye/psum_stream_mapper.py` | serial `get_psum_stream`: ceil(F / 2) words in per-filter mode; the old loop stays for the old mode and for depthwise |
| `src/open_eye/layer_parameters.py` | `trans_cycles_psum` (line 1459) per mode; the new fields (`different_kernels_per_calculation`, address count); a guard F <= `QUANT_AMOUNT` |
| `src/open_eye/conv_mapper.py` | pack the new fields like `skipPsum_reg` |
| `src/open_eye/open_eye_parameters.py`, `vh_file_creator.py` | the build switch |
| `src/open_eye/rtl_test_utils.py` (profiler) | `load_bias` gets small; a counter for the rewrite cycles that hold up `CALCULATE_PSUM` |

Added: the table, the rewrite counters, three register fields, a build switch, tests. Removed (per-filter mode only):
the per-output bias stream and almost all of its DMA words; nothing is deleted from the RTL while the old mode stays.

Tests: `test/cocotb_fpga/test_bias_per_filter.py` (Conv single and chains, two kernel groups (short lines, #32),
`NUM_GLB_PSUM` 2 / 4, CR 1 / 2 / 8, several x passes, stride 2, pooling, a layer with several iact transmissions
(`skipPsum`), trained MNIST with the four activations, sparse and dense); a testbench probe that compares the psum buffer
after the rewrite with the buffer after today's `GET_BIAS` (A is bit-exact by construction: same addresses, same words);
unit tests for the stream and the fields; `regression.sh`; then the 12 baseline cases (only `load_bias` may change),
Table 3 and Vivado (timing).

## 4. Pros and cons against today

Pros: −9 to −11 % on the trained MNIST net, −5 to −18 % on the Table 2 network (more with real memory); bias DMA traffic
and DRAM image of a Conv layer 56 to 896 times smaller; independent of sparse / dense and of the activation, so it
adds to every other optimization; option A can be verified word by word against today's buffer.

Cons: RTL in `psum_pipeline.v` on the psum-buffer write path, which is where the routed critical path is (wires to the
psum BRAMs, README section 6d): a mux there is a timing risk at 250 MHz; three new register fields; a small table
(`QUANT_AMOUNT` x 20 bits: LUTRAM, or about 640 FF at 32 entries); loses nothing as long as the old mode is kept, but the
old mode is the only way to start a layer from arbitrary psums from memory (a split layer, a residual add), so it should
stay; the profiler phase changes meaning.

B over A: no rewrite at all, but a mux on the buffer-to-PE read path, a "first channel pass" condition from the main FSM
and the filter of each lane in `CALCULATE_PSUM`; not verifiable at the buffer (the buffer is never initialised), only
on the outputs. Worth it only if the background rewrite of A turns out not to be hidden (CR 1 X 2: about 3,100 cycles per
Conv1).

## 5. Recommendation

Option A in the background, behind a per-layer bit with the old path kept, Conv only, after approval of the RTL change.
Order: Python stream and fields with the switch off (baselines unchanged), RTL with the switch, bit-exact buffer
comparison, regression, measurements, Vivado.

## 6. Implementation (2026-11-17, option A in the background, approved by the user)

| File | Change |
|---|---|
| `hdl/psum_pipeline.v` | parameter `BIAS_PER_FILTER_EN` (default 0: no table, the hardware of before); inputs `bias_per_filter`, `bias_groups`; `bias_table` (generate, `ceil(QUANT_AMOUNT / PSUM_OUTPUT_WORDS)` rows of one DMA payload, LUTRAM: one write port, read without a clock) written by `GET_BIAS` in bias mode instead of the shift into `psum_buffer_data_w`; at the last bias word the rewrite starts. Rewrite, in `PSUM_IDLE`: for group g, shift the group word together through the **same shift register** as the old `GET_BIAS` (the filters of the group last first, `CONV_BIAS_CYCLES / kernels_per_calc` payloads each, one per cycle), then write it to addresses g, g + groups, ... (rows x x passes of them, one per cycle); `psum_cnt` = last address as before. A `compute_reg` pulse during the rewrite is held in `compute_pending`; `PSUM_IDLE` leaves only when the rewrite is done. New registers reset, and cleared by a new layer configuration |
| `hdl/OpenEye_FPGA.v` | parameter `BIAS_PER_FILTER_EN`, the two fields from `dma_storage` to `psum_pipeline`; the main FSM is unchanged (`GET_BIAS` ends after `trans_cycles_psum` words as before) |
| `test/cocotb_fpga/regmap.yaml` | `bias_per_filter` (1 bit, after `skipPsum_reg`), `bias_groups` (11 bits, before `psum_size_y`): free bits, the status word counts are unchanged in all 96 configurations of `2026-11-17_bias_per_filter/regmap_fit.py` (DMA 32 / 64 / 128, CR 1-8, CC 1-4, BRANCHES 1-2) |
| `src/open_eye/open_eye_parameters.py`, `vh_file_creator.py` | `BIAS_PER_FILTER_EN` (environment, default 0) into `parameters_FPGA.vh` |
| `src/open_eye/layer_parameters.py` | `set_bias_per_filter` (Conv2D only): on when the hardware has the table, DMA 32 / 64, the filters split into whole kernel groups that fill a psum buffer address, filters <= `QUANT_AMOUNT`, groups <= 2047; otherwise the layer keeps the old stream (logged with the reason) |
| `src/open_eye/psum_stream_mapper.py` | per-filter stream: `ceil(filters / words_per_transmission)` words, filter f in slot f % 2 |
| `src/open_eye/conv_mapper.py` | packs the two fields |
| tests | `test/test_bias_per_filter.py` (19: a model of the old `GET_BIAS` and of the rewrite give the same buffer word for word in 9 configurations, the decision rules), `test/cocotb_fpga/test_bias_per_filter.py` (10 RTL cases, added to `regression.sh`) |

The main FSM's 16 states stay as they are (the 4-bit state is full); no mux on the buffer data path (the rewrite uses
the existing shift register and write port), only the address register gets one more source.

**Default since 2026-11-17:** `BIAS_PER_FILTER_EN = 1` (user decision, `open_eye_parameters.py`, `OpenEye_FPGA.v`,
`psum_pipeline.v`), committed together with the fix of bug #49 before the verification runs of that state; the
measurements above were made with the parameter set explicitly, before the #49 fix.
