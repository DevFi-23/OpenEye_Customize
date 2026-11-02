# 2026-11-02: plan for activation functions (ReLU, Leaky ReLU, SiLU, hard-swish) and their profiling

Plan only: nothing of the RTL or Python was changed for this note. "hard-switch" in the request is read as hard-swish
(h-swish of MobileNetV3, x * relu6(x + 3) / 6).

## 1. What exists today

* `hdl/quantization_unit.v`: q = clamp(floor(mant * (psum + offset) / 2^shift), act_min, 127), 3 pipeline stages
  (add, multiply, shift + clamp). `psum_pipeline.v` has `TRANS_WORDS` (8 in the baseline configuration) instances,
  fed in `SEND_PSUM_TO_IACT`: they requantize the psums of a layer while they are written back into the iact buffer
  (main FSM state `RECEIVE_PSUMS_TO_IACT`). The final readout to the DMA does not pass through them (raw psums).
* ReLU already exists as the lower clamp bound (`act_min = 0`, register `quant_clamp_low`, bug #30 fix). It costs
  0 cycles and 0 DMA words.
* `hdl/af_cluster.v`: a ReLU-only block, instantiated nowhere, with two bugs (#24). Not a good base: it works on
  int8 values after quantization and has no place in the datapath.
* The receiver in `OpenEye_FPGA.v` (`RECEIVE_PSUMS_TO_IACT`) keeps several delay chains of exactly 3 clocks
  (`psum_cycle_buffer_3`, `psum_cycle_inc_3`, `fsm_y_cl_psum_q3`, ...) aligned to the 3-stage quantizer. The
  write-back is where bugs #25 and #26 were; changing its latency is the riskiest part of any design.
* Free configuration space: the last status word of the register map uses 40 of 64 bits, so 24 bits of new
  per-layer fields cost no DMA word.
* Main FSM state codes are 4 bits, 0-14 used: one code (15) is free for a new load state.
* Toolchain (`onnx2model`, ONNX opset 18, ONNX Runtime 1.23 `quantize_static` in QOperator format):
  PyTorch exports LeakyReLU as `LeakyRelu`, SiLU as `Sigmoid` + `Mul`, Hardswish as `HardSwish`. ONNX Runtime has
  quantized versions of `Relu`, `LeakyRelu`, `Sigmoid`, `Mul`, but not of `HardSwish` (it stays float between
  dequantize and quantize nodes). `onnx2model` today only detects ReLU (`has_relu`).

## 2. Design: fuse the activation into the requantizer of the write-back

The decisive point for latency and bandwidth is to apply the activation **on chip, in the same pipeline as the
requantization, while the layer's results are written back**. No separate activation pass over the tensor, no
pre-activation values on the DMA, no host round-trip. (On the host, Conv2 of the MNIST model would need its 12,544
raw psums read out, about 6,272 words at 64 bit, and 1,568 words sent back; fused it is 0 words.)

| Function | Mechanism | Extra cycles per value | Extra DMA words | Extra hardware (estimate) |
|---|---|---:|---:|---|
| none (int8) | `act_min = -128` (today) | 0 | 0 | - |
| ReLU | `act_min = 0` (today) | 0 | 0 | - |
| Leaky ReLU | **two slopes in the quantizer**: a negative `psum + offset` uses a second mantissa/shift (`m_neg / 2^s_neg = alpha * m / 2^s`), the multiplier is shared | 0 | 0 (fields in the free bits of the last status word) | 8 lanes x (mux 8 + 7 bit) ~ 120 LUT |
| SiLU, hard-swish (and any int8 -> int8 function: hard-sigmoid, GELU, tanh, ...) | **256-entry lookup table** after the clamp: y = LUT[q], q = int8 pre-activation at a calibrated scale s_in; LUT[q] = clamp(round(f(q * s_in) / s_out)) computed by the toolchain | 0 (design A below) | 32 per layer that uses it (256 B at DMA 64 bit; 16 at 128 bit) | 8 copies (one per lane, one read per clock each) of 256 x 8 bit in LUTRAM ~ 8 x 32 = 256 LUT, 0 BRAM |

Total about 400 LUT (+0.7 %), about 25 FF, no BRAM/DSP.

Why two slopes for Leaky ReLU and not the table: the negative side keeps the precision of the full psum (a table
would see the already-rounded int8 value) and it needs no table load. Why a table for SiLU and hard-swish: one small
generic block covers both and later functions, the toolchain fills it bit-exactly, and an exact hard-swish would need
a second multiplier per lane.

Pipeline and latency:

* **Design A (preferred)**: keep the 3-clock latency. The stage-3 register holds the clamped index; the LUTRAM is read
  asynchronously from it and the receiver's existing register captures the result. None of the 3-clock delay chains
  of the write-back changes: 0 extra cycles. Risk: timing of index register -> LUTRAM -> receiver logic at 250 MHz
  (the design has WNS +0.020 ns today, although on another path). Checked with Vivado.
* **Design B (fallback)**: a 4th register stage; every 3-clock delay chain of `RECEIVE_PSUMS_TO_IACT` becomes 4 clocks.
  +1 clock per write-back burst (not per value), but it touches the code of bugs #25/#26.
* The table is loaded in a new main FSM state `GET_ACTIVATION` (code 15) right after `GET_QUANTIZE`, only when the
  layer uses the table (0 cycles otherwise), written to the 8 copies in parallel. A "keep table" bit skips the load
  when the next layer uses the same table.
* Rounding: the quantizer floors today. For Leaky ReLU and SiLU this turns every small negative value into -1 instead
  of 0, which destroys exact zeros and with them zero skipping in the next layer (section 4). A per-layer rounding
  bit (round half up: + 2^(shift-1) before the shift, one adder in stage 3) keeps zeros and also brings the result
  closer to ONNX Runtime. The old floor behaviour stays the default, so all existing tests stay bit-exact.
* Per-filter scales (#12, still open) do not change this: the per-filter mant/shift would bring every filter to the
  same table input scale s_in, so one table per layer suffices.
* The final layer: its readout bypasses the quantizer (raw psums). An activation there needs the planned INT8
  readout (roadmap 1.2) through the same pipeline, which also cuts the readout words about 4 times.

## 3. Changes

| Where | Change |
|---|---|
| `hdl/quantization_unit.v` (or a new `activation_unit.v` right after it) | modes 0 none / 1 ReLU / 2 Leaky / 3 table; negative mantissa and shift; rounding bit; table read |
| `hdl/psum_pipeline.v` | new per-layer inputs to the 8 lanes; 8 LUTRAM copies with a broadcast write port |
| `hdl/OpenEye_FPGA.v` | decode of the new fields; state `GET_ACTIVATION` (load the table from the DMA, skipped when not needed) |
| `test/cocotb_fpga/regmap.yaml` | `act_mode` (2 bit), `act_neg_mant` (8 bit), `act_neg_shift` (7 bit), `act_round`, `act_keep_lut` in the free bits of the last status word: 0 extra config words |
| `src/open_eye/onnx2model.py` | detect `LeakyRelu` (alpha), `Sigmoid` + `Mul` on the same tensor (SiLU), `HardSwish` after `QLinearConv` / `QGemm`; take s_in (the conv output scale) and s_out (the activation's output scale, from its quantized node or calibration); build the mode and parameters |
| `src/open_eye/layer_parameters.py`, mappers | act fields into the status word; table words into a new stream part after the quant stream |
| `src/open_eye/simple_layer_operations.py` (reference) | the same integer steps as the RTL (two slopes, rounding, table), bit-exact |
| `af_cluster.v` | not used; left as it is |
| Tests | unit testbench of the activation lanes (every mode, all 256 table inputs, random psums against the Python model); system tests like `test_int8_clamp.py` per mode (Conv -> Conv, Conv -> Pool -> Conv, Dense -> Dense, `NUM_GLB_PSUM` 2 and 4); three MNIST variants trained with LeakyReLU, SiLU, Hardswish, run end to end on the RTL; regression 162 + 12 baseline cases with 0 cycles of change in modes 0/1; Table 3; Vivado |

## 4. What it does to latency (to be measured)

* Directly: 0 cycles per value (design A), the table load (about 32 + a few cycles per layer that uses it; for a
  network like the MNIST model with 3 activated conv layers about 100 of 240,000 cycles, 0.04 %).
* Indirectly, and larger: the next layer's compute depends on the zeros the activation leaves (zero skipping). With
  ReLU the trained model's Conv3 input is 87 % zeros and Conv3 computes 27 % faster than with random data. Leaky ReLU
  has exact zeros only where alpha * x rounds to 0, SiLU only where its small negative outputs round to 0,
  hard-swish below x = -3. Expect the compute phase of the following layers to grow towards the random-data level.
  Rounding to nearest helps; the table can also map tiny outputs (|y| < 1 LSB or a chosen band) to 0, a knob that
  trades a little accuracy for zeros, chosen per layer by the toolchain from accuracy measurements.
* Zero point: the hardware keeps zero point 0 (needed for zero skipping and zero padding). SiLU and hard-swish outputs
  are almost all positive (minimum -0.28 and -0.375), so about one bit of the int8 range is unused on the negative
  side; acceptable for MNIST-size models, to be checked on accuracy.

## 5. Profiler: yes, the activation can be measured

The activation runs inside the write-back pipeline, so it has no FSM state of its own; its cycles overlap the
`writeback` phase. What the profiler (`rtl_test_utils.profile_dma_phases`, observation only, 0 cycles of influence)
can report:

1. **`load_act`**: a new phase for state 15 (`PROFILE_PHASES[15]`): cycles, DMA words, bus efficiency and memory
   stalls of the table load, like the other load phases. Also added to `profile_report`, `paper_table3` and
   `test_profile_phases`.
2. **Activation counters per layer**, from a valid signal and the outputs of the 8 lanes sampled every clock:
   mode, values processed, busy cycles (overlapped with `writeback`), extra pipeline cycles (0 in design A),
   outputs equal to 0 and negative. The zero fraction is the link to the next layer's compute.
3. **The cost in cycles** as a difference: the same model with the activation on and in mode 0, compared with
   `run_profile --compare` per phase and per layer (writeback, load_act, and the compute of the next layer).

## 6. Order of work

| Step | Content | RTL? |
|---|---|---|
| A | Python: toolchain detection, bit-exact reference with two slopes / table / rounding; three trained MNIST variants; int8 accuracy and zero fraction per layer from the reference (predicts the compute change before any RTL) | no |
| B | RTL: modes, table, load state, register fields; unit testbench, system tests, regression, 12 cases (0 change in modes 0/1), Vivado (design A timing) | yes, needs approval |
| C | Profiler: `load_act`, activation counters, report | Python only (reads RTL signals) |
| D | Measurement: ReLU / Leaky / SiLU / hard-swish variants of the MNIST model, cycles per layer and phase, accuracy; rounding and zero band | no |
