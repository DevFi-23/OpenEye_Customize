# 2026-11-02: activation functions in the RTL, step B (implemented, approved by the user)

Implementation of `2026-11-02_activation_rtl_design.md` (approved 2026-11-02): Leaky ReLU, SiLU and hard-swish computed
in the write-back quantizers, bit-exact with the reference of step A (`2026-11-02_activation.md`).

## 1. RTL changes

| File | Change |
|---|---|
| `hdl/quantization_unit.v` | inputs `leaky_en`, `neg_mant`, `neg_shift`, `round_en`. Stage 1 computes the sum as before, takes its sign and registers the chosen [mant, shift] (the negative slope when `leaky_en` and the sum is negative) and `round_en`; stage 2 multiplies and adds 2^(shift-1) when rounding (`mant * sum + round_const`, the DSP's post-adder); stage 3 unchanged. With both options 0 every register gets its old value |
| `hdl/activation_table.v` (new) | the 256-entry table: `TABLE_WORD_WIDTH / 8` banks of distributed RAM (8 banks of 32 at 64 bit), one table word per clock written (byte b to bank b at address w), read without a clock at index = value + 128 (sign bit flipped) |
| `hdl/psum_pipeline.v` | ports `act_mode`, `act_round`, `act_neg_mant`, `act_neg_shift`, `act_table_we`, `act_table_addr`; the options to every quantizer; an `activation_table` per write-back lane (`WRITEBACK_WORDS`) written from `data_dma_i_reg`, the lane output = the table in mode 2, else the quantizer as before |
| `hdl/OpenEye_FPGA.v` | the five status fields from `dma_storage`; state `GET_ACTIVATION` = 15 (`ACT_TABLE_WORDS` = 2048 / `DMA_BITWIDTH` words); `GET_QUANTIZE` goes there instead of `START_CONVERTER` for a non-pooling layer with `act_mode` 2 and not `act_keep_table`, keeping `ready_dma_o` high; `act_table_we` = state 15 and a DMA word, `act_table_addr` = `fsm_cycle`; trace wire `UNPACKED_TRACES.act_capture` (the write-back takes the lanes) for the profiler |
| `test/cocotb_fpga/regmap.yaml` | `act_mode` (2), `act_round` (1), `act_neg_mant` (8), `act_neg_shift` (7), `act_keep_table` (1) after `quant_clamp_low`: the last status word 40 -> 59 bits, still 14 words |

## 2. Python changes

* `layer_parameters.py`: `check_rtl_activation` now checks that the settings fit the RTL (slope 8 + 7 bits, table of
  256 int8, rounding shift <= 45); `activation_registers` (the five fields), `activation_table_words` (the table as
  DMA words, entry w * E + b in byte b of word w), `ACT_MODE_CODES`; `act_keep_table`; `activation_config` also takes
  `openeye_activation` (the test hook below).
* `conv_mapper.py`, `dense_mapper.py`: the fields in the status words, the table words after the quantization words
  (the host sends them in the same stream section; no testbench change for the stream).
* `onnx2model.py`: Leaky ReLU, SiLU and hard-swish round to nearest (`activation_round`), ReLU keeps the floor.
* `data_create.py`: test hook `OPENEYE_ACTIVATION` (`leaky:<mant>:<shift>`, `table:random`,
  `table:<f>:<s_in>:<s_out>`, extra items `round`, `keep`) on every Conv/Dense but the last of a random model.
* `OpenEye_FPGA_tb.py`: with `OPENEYE_MODEL_WEIGHTS` the model gets the activation stored in the checkpoint
  (`train_mnist.load_activation_model`; the original checkpoint is ReLU).

## 3. Verification

| Check | Result |
|---|---|
| `test/cocotb_quantization/test_quantization_unit.py` (extended: 10 blocks of act_min x leaky x round, random psums, every shift; rounding with shift <= 45) | **2/2 PASS** (psum 20 and 32 bit), 30,470 outputs each bit-exact with the Python model, about 6,100 on the negative slope |
| `test/cocotb_activation_table/test_activation_table.py` (new: load, read all 256, reload, writes with `we_i` = 0 ignored) | **3/3 PASS** at table word width 32 / 64 / 128 bit |
| `test/cocotb_fpga/test_activation_rtl.py` (new, random models through the hook): Leaky (floor, round), ReLU + round, random table (floor, round), SiLU table on Conv -> Pool -> Conv, hard-swish table on a Dense chain, Leaky on a Dense chain, table with `NUM_GLB_PSUM=2`, table at DMA 32 bit (64 words, 4 banks), `keep` on an MLP, SiLU table on the Table 2 network of the paper (7 layers) | **12/12 PASS**, every iact buffer check bit-exact |
| Negative controls (`sitecustomize` patch of the stream only, the reference unchanged): RTL told mode 0 (table, Leaky, Dense table), table one entry off (Conv, MLP with keep), rounding off | **6/6 FAIL** at the iact buffer check, as they must |
| `test_real_model.py::test_real_model_activation`: trained Leaky ReLU, SiLU, hard-swish models, MNIST test images 0 and 1, through `onnx2model` (rounded, two slopes / tables per layer) | **6/6 PASS**, the whole network bit-exact (every buffer check and the Dense psums), DUT class 7 and 2 = labels |
| RTL regression: the 162 tests + `test_activation_rtl` 12 + `test_real_model_activation` 6 = 180 | **175 PASS + 5 known xfail, 0 FAIL** (xfails: 3 channels x2 #7, Conv1 without padding #17, Conv3 x2 #9) |
| 12 baseline cases (`run_profile --compare doc/perf/baseline_2026-11-02`) | **12/12, 0 cycles, 0 DMA words of change** (incl. DMA 32 bit, see below) |
| Table 3 of the paper, 16 configurations | **13/16** as before; cycles identical to the `wghts_per_pe + 1` experiment in all 16 (0 change from step B); saved as the new Table 3 baseline `doc/perf/paper_table3_2026-11-02` |
| Python unit tests | 321 pass (290 + 31 of `test_activation.py`), the 11 old fails |
| Lint | `fpga` 461 -> **460** (0 new; `data_dma_i_reg` is now used in full), `parallel` 36; baseline lowered |
| Vivado 4 ns (`doc/synth/2026-11-02_route4ns_act_zu7ev/`) | **0 ERROR, 0 CRITICAL WARNING**; WNS +0.203 / **+0.045 ns** (250 MHz met; worst path the main FSM's compare chain to `router_configurator`, as before); LUT +778 after routing (+1.3 %; attributable about +550: 4 tables 354 LUT incl. 256 LUTRAM, the 4 quantizers +193), FF +59, BRAM / URAM / DSP unchanged |

**The status word layout.** With the five fields at the end of the register map the status stream kept 14 words at
DMA 64 bit and 7 at 128 bit but grew from 28 to 29 words at DMA 32 bit (+1 cycle and +1 word per layer in the case
`32x3_f4_q32_dma32`, found by the first profile run). `act_mode` (2 bit) and `act_keep_table` (1 bit) were then moved
into gaps further up (after `psum_pagu_cs_limit_1` and `iact_read_inc_3`), found by a search over the insertion
points: 28 / 14 / 7 words at 32 / 64 / 128 bit, as without the activation. Every test above ran again on this final
layout except the negative controls, which ran on the first one (they test the checks, not the field positions).

## 4. Cost

| | Modes 0 (none / ReLU) | Leaky | Table (SiLU, hard-swish) |
|---|---:|---:|---:|
| Cycles per value | 0 | 0 | 0 (the table is read without a clock) |
| Cycles per layer | 0 | 0 | 256 / E table words (32 at DMA 64 bit), 0 with `act_keep_table` |
| DMA words | 0 | 0 | the same 32 per layer |
| Status words | 0 at DMA 32 / 64 / 128 bit | | |

Resources: about +550 LUT (+0.9 %) and +60 FF attributable, 0 BRAM / URAM / DSP. The design estimated ~300 LUT; the
quantizers grew more than expected because the rounding constant 2^(shift-1) (shift up to 45) keeps every bit of the
46-bit product significant, where Vivado used to remove the upper bits of two quantizers. A narrower rounding range
(the toolchain's shifts are 13-20) would win part of it back; not done. Timing: 250 MHz met (+0.045 ns).
