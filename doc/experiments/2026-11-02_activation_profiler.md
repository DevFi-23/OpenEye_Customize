# 2026-11-02: profiler of the activation functions, step C

Step C of `2026-11-02_activation_plan.md`: the profiler measures what the activation hardware of step B
(`2026-11-02_activation_rtl.md`) costs. Python only (testbench and reports); the RTL is the one of step B, whose trace
wire `UNPACKED_TRACES.act_capture` was added for this.

## 1. What is measured

| Quantity | Where it comes from | Where it is reported |
|---|---|---|
| Phase `load_act`: cycles and DMA words of the table load | main FSM state 15 `GET_ACTIVATION` (`PROFILE_PHASES[15]`), the same six counters as every phase | phase table, layer table (in the `load` column), `--compare`, Table 3 (a column only when a configuration has a table) |
| Activation clocks of a layer (`activation_cycles`) | `act_capture` sampled every clock: the write-back takes the activated lane values (`quantized_value_reg`, table output in mode 2) into `iact_to_psum_mux_reg` | activation table of `profile_report`; they lie **inside** `writeback`, they are not extra cycles |
| Activation of a layer (`info.activation`: mode none / relu / leaky / table, round, keep_table) | `LayerParameters` (`profile_set_layer_info`) | activation table |
| Zeros and negatives of a layer's input (`info.input`: values, zeros, negatives) | the testbench reference after `batchnorm_output` (`profile_set_layer_input`): the activated output of the layer before, after pooling; layer 0 = the model input | activation table |
| Minimal payload of the table | 256 bytes per layer with a table that is not kept (`layer_payload_bytes`) | bus efficiency of the layer table |

The input zeros are what zero skipping skips, so together with `compute` they show the indirect cost of an activation.
They are taken from the reference instead of sampling the four write-back lanes as the design suggested
(`2026-11-02_activation_rtl_design.md`, section 8): the reference is exactly what the RTL computes (every buffer check
of these runs is bit-exact), counts the next layer's real input (after pooling, without the row padding and the
pipeline flush the lanes also carry) and needs no extra signal.

The cost of an activation is measured as a difference: the same model with ReLU and with the activation, per phase
and per layer (`profile_report --compare`, or the table of `doc/perf/activation_2026-11-02.md`).

## 2. Changes

| File | Change |
|---|---|
| `src/open_eye/rtl_test_utils.py` | `PROFILE_PHASES[15] = "load_act"`; `profile_set_layer_info` writes `activation`; new `profile_set_layer_input(index, values)`; `profile_dma_phases` counts `activation_cycles` per layer from `act_capture` (absent in older RTL: not counted) |
| `test/cocotb_fpga/OpenEye_FPGA_tb.py` | with `OPENEYE_PROFILE` only: `profile_set_layer_input` for the model input (after the channel padding of bug #17) and after every layer's reference (`batchnorm_output`) for the next layer |
| `src/open_eye/profile_report.py` | `load_act` in `PHASE_ORDER` and in the layer table's `load` column; payload 256 bytes per table layer; `summarise_activations`, `print_activation_table` (printed when a profile has the new fields) |
| `tools/paper_table3.py` | `load_act` among the load phases; the whole-network table shows the `load_act` column only when a configuration has it (the tables of earlier runs are unchanged) |
| `test/test_profile_phases.py`, `test/test_profile_report.py`, `test/test_paper_table3.py` | state 15, the activation info, the layer input, the activation table, the table payload, the `load` column, the Table 3 columns |

## 3. Verification

| Check | Result |
|---|---|
| Unit tests of the profiler (`test_profile_phases`, `test_profile_report`, `test_paper_table3`) | **41/41 PASS** |
| `act_table_keep_mlp` (random table, `keep` on the next layers) | `load_act` 32 cycles / 32 words in layer 0, **0** in layer 1 (table kept) and in the last layer (mode none) |
| `act_table_conv_stack_dma32` (DMA 32 bit) | `load_act` **64** cycles / 64 words (2048 / 32) |
| `act_table_paper_network` (SiLU table, 7 layers) | 32 / 32 in each of the 4 Conv/Dense layers with a table, 0 in pooling and the last layer |
| Trained models, image 0 (`doc/perf/activation_2026-11-02.md`) | `writeback` and the activation clocks identical in all four functions (11,948 cycles; 7,174 / 3,590 / 902 clocks); every phase but `compute` and `load_act` 0 cycles of difference; `load_act` 96 for SiLU and hard-swish (3 x 32), 0 for ReLU and Leaky |
| ReLU input zeros against the earlier measurement (`doc/perf/trained_mnist_2026-10-31.md`) | Conv2 / Conv3 / Dense 43.5 / 87.3 / 74.3 % (then 44 / 87 / 74 %); the ReLU run is 673 cycles shorter than on 2026-10-31, exactly the change of the `wghts_per_pe + 1` line (`baseline_2026-11-02`) |
| Zero fractions against step A (10,000 images, `2026-11-02_activation/eval_10000.md`) | within 2 points for every function and layer |
| All 7 runs | PASS, every buffer check bit-exact |
| 12 baseline cases (`run_profile --compare doc/perf/baseline_2026-11-02`) | **12/12 PASS, 0 cycles and 0 DMA words of change** (section 5) |

## 4. Results: the cost of each activation (trained MNIST model, image 0, 250 MHz)

| | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Total cycles | 218,925 | 238,049 | 240,229 | 240,293 |
| vs ReLU | | +19,124 (+8.7 %) | +21,304 (+9.7 %) | +21,368 (+9.8 %) |
| of which `load_act` (table loads) | 0 | 0 | +96 | +96 |
| of which `compute` (lost zeros) | | +19,124 | +21,208 | +21,272 |
| other phases (incl. `writeback`) | | 0 | 0 | 0 |
| DMA words | 62,904 | +0 | +96 | +96 |
| Zeros in the input of Conv2 / Conv3 / Dense | 43.5 / 87.3 / 74.3 % | 24.3 / 14.7 / 18.1 % | 11.0 / 7.2 / 6.6 % | 5.9 / 14.3 / 13.2 % |
| Compute of Conv2 / Conv3 / Dense vs ReLU | | +8.5 / +36.1 / +23.9 % | +10.1 / +38.4 / +26.4 % | +10.4 / +37.8 / +25.5 % |
| Time at 250 MHz | 875.7 us | 952.2 us | 960.9 us | 961.2 us |

1. **The activation unit itself is free in time**: 0 cycles per value (the write-back is the same clock for clock),
   32 cycles and 32 DMA words per table layer (0.04 % of the model for three layers), 0 for Leaky ReLU. Step B's
   design target is met on the real model.
2. **The cost is the zeros**: 99.5-100 % of the extra cycles are compute, because zero skipping skips fewer values.
   Conv3 is hit hardest (+36-38 %): ReLU leaves 87 % zeros in its input, the others 7-15 %. Step A predicted +7.4 /
   +9.2 / +9.0 % (average over 10,000 images, linear in the zero fractions); image 0 measures +8.7 / +9.7 / +9.8 %.
3. **Latency knobs from here** (not done): the table's +-1 entries set to 0 (`band1`, step A: zeros 20-27 %, about
   2 points of the model back, no accuracy loss); fewer passes whose fixed cost does not depend on the zeros.

## 5. The 12 baseline cases

`venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-11-02 --clock-mhz 250` with the profiler of step C:
12/12 PASS, every case 0 cycles and 0 DMA words of change (the profiler only observes). The three model cases now print the
activation table too (mode none; random data: 6.1 / 11.0 / 9.5 % zeros in the inputs of Conv2 / Conv3 / Dense of
`model_mnist_real_c1`, as in `doc/perf/trained_mnist_2026-10-31.md`).

## 6. Usage

```bash
# a profiled run of a trained model with an activation (10-25 minutes, depending on the load of the machine)
OPENEYE_PROFILE=1 venv/bin/python -m pytest -q "test/cocotb_fpga/test_real_model.py::test_real_model_activation[silu-0]"
venv/bin/python -m open_eye.profile_report --clock-mhz 250 "test/.temp/test_cocotb_fpga_test_real_model.py_test_real_model_activation_silu-0_/profile.json"
# the cost against ReLU: both profiles under the same case name in two directories
venv/bin/python -m open_eye.profile_report --clock-mhz 250 --compare <dir with relu as X.json> <dir with silu>/X.json
# a random model with an activation (test hook OPENEYE_ACTIVATION, step B)
OPENEYE_PROFILE=1 venv/bin/python -m pytest -q "test/cocotb_fpga/test_activation_rtl.py::test_activation_rtl[table_paper_network]"
```
