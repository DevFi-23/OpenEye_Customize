# 2026-10-31: weight send phase ends one clock earlier (wghts_per_pe + 1, from upstream 3258813)

Experiment approved by the user on 2026-10-31. Upstream `3258813` ("Fix multi-channel and sparse conv weight tiling")
also changes one line of `hdl/OpenEye_FPGA.v`, Process 5:

```verilog
-          if (fsm_sending_cycle > wghts_per_pe + 2) begin
+          if (fsm_sending_cycle > wghts_per_pe + 1) begin
```

The rest of that commit is already in `dev` (#18, #22). The question was whether the line alone shortens the weight send
of every pass by one clock without breaking anything. The experiment ran in a separate worktree of `dev` (`5595d15`,
after taking `e78e5b7`) with only this line changed.

## 1. Timing of the weight send

Process 5 starts a send with `fsm_sending_cycle <= 1` and `wght_buffer_en_r <= 1` once every PE has weight ready; let
N = `wghts_per_pe` (packed weight words per PE) and v the value of `fsm_sending_cycle`:

* v = 1 ... N: `wght_buffer_rd_addr` advances, so the N addresses of the pass are presented at v = 1 ... N (the first
  one was set up before the send);
* the weight buffer has two read stages (this is the reading of the code; the regression below is the check), so its
  data arrive at v = 3 ... N + 2;
* from v = 2 on, `wght_enable_i_reg` is set (the register is high from v = 3);
* with `+ 2`, the end branch runs at v = N + 3: enable low, `wght_buffer_en_r` low, `compute_reg <= 1`. The enable
  is therefore high for v = 3 ... N + 3, N + 1 clocks: one word more than the PE needs, the word read at address N + 1
  (the first word of the next weight tile, or a word past the end). Since every test passes with `+ 2`, this word does
  not reach the computation (not traced further); but compute starts one clock later than necessary;
* with `+ 1`, the end branch runs at v = N + 2: the enable is high for exactly the N clocks of valid data, and compute
  starts one clock earlier.

Expected effect: one clock less per weight send on the critical path, nothing else.

## 2. Results

The change as a patch: `2026-10-31_wght_send_end/wght_send_end_plus1.patch`. Runs in the experiment worktree with
`PYTHONPATH=<worktree>/src` (the ignored model files `.tflite`, `.pth` and the MNIST data copied in).

### 2.1 Correctness

| Check | `dev` (`5595d15`) | with `+ 1` |
|---|---|---|
| RTL regression, 162 tests (`test_conv_const` 36, `test_mnist_layers` 26, `test_gemm_layer` 63 with `OPENEYE_SKIP_FC_WRITE_CHECK=1`, `test_dense_chain` 11, `test_glb_psum2` 7, `test_int8_clamp` 9, `test_pooling` 4, `test_nets` 1, `test_empty_pass` 3, `test_real_model` 2) | 157 PASS + 5 xfail, 0 FAIL | **157 PASS + 5 xfail, 0 FAIL** (same 5 known xfails: 3 channels x2 #7, Conv1 without padding #17, Conv3 x2 #9) |
| 12 baseline cases (`tools/run_profile.py`) | 12/12 PASS | **12/12 PASS** |
| Trained MNIST model, test images 0, 1, 2, 7 (`run35.py`, profiler on) | PASS, classes 7, 2, 1, 9 | **PASS**, bit-exact, classes 7, 2, 1, 9 |
| Lint (`tools/lint_check.py`) | fpga 461, parallel 36 | fpga 461, parallel 36: **0 new** |
| Table 3 of the paper, 16 configurations (`tools/paper_table3.py --run`) | 13/16 PASS (fails: CR 1 X 2 Y 3/4 #28, CR 1 X 4 Y 3 #19b); cycles identical to `paper_table3_2026-10-26_fix25` in all 16 | **13/16 PASS**, the same three configurations fail the same way |

### 2.2 Cycles (ideal memory, `--compare doc/perf/baseline_2026-10-24`; `dev` itself has 0 change against it)

| Case | `+ 2` (dev) | `+ 1` | change | where |
|---|---:|---:|---:|---|
| `8x1_f4_q32`, `8x1_f4_q1024`, `16x3_f4`, `32x3_f4` (DMA 64 and 32) | 568 ... 2,236 | same | 0 | - |
| `32x3_f16_q32_dma64` | 3,556 | 3,555 | -1 | compute |
| `mnist1_28x28_c4_f32` | 55,048 | 54,936 | -112 (-0.2 %) | compute |
| `mnist2_14x14_c32_f32` | 65,528 | 65,304 | -224 (-0.3 %) | compute |
| `mnist3_8x8_c32_f32` | 20,584 | 20,520 | -64 (-0.3 %) | compute |
| `model_mnist16_c2` | 50,007 | 49,930 | -77 (-0.2 %) | compute -74, writeback -3 |
| `model_mnist_real_c2` | 243,517 | 242,844 | -673 (-0.3 %) | compute -670, writeback -3 |
| `model_mnist_real_c1` | 240,671 | 239,998 | -673 (-0.3 %) | Conv1 -1, Conv2 -448, Conv3 -224, Dense 0 |
| Trained model, images 0 / 1 / 2 / 7 | 219,598 / 220,941 / 213,040 / 218,374 | 218,925 / 220,268 / 212,367 / 217,701 | -673 each (-0.3 %) | as above |

DMA words: 0 change everywhere (the change is on chip only).

* The saved clocks are in the **compute** phase, not in `load_wght`. `load_wght` is the DMA transfer of the weights
  from external memory into the on-chip weight buffer (39,120 words = 39,120 clocks for the MNIST model, bus bound) and
  does not change. The send from the weight buffer to the PEs, the part this line ends, happens in the compute phase.
* One clock per pass in which the end of the weight send is on the critical path: Conv2 448, Conv3 224 passes. Where
  the pass waits for something else (the small single-layer cases, Conv1, Dense) nothing changes; this was not traced
  further.
* The saving does not depend on the data (the same -673 with random data and with the four real images).

### 2.3 Table 3 of the paper (Table 2 network, 7 layers, 16 cluster/PE configurations, ideal memory)

Against `doc/perf/paper_table3_2026-10-26_fix25` (= `dev` on 2026-10-31: re-run, 0 cycles and 0 DMA words of change in
all 16 configurations):

| CR | X = 2, Y = 3 | X = 2, Y = 4 | X = 4, Y = 3 | X = 4, Y = 4 |
|---:|---:|---:|---:|---:|
| 1 | 211,402 -> 210,685 (-717) | 206,614 -> 205,908 (-706) | 133,574 -> 133,193 (-381) | 128,563 -> 128,193 (-370) |
| 2 | 137,594 -> 137,235 (-359) | 138,524 -> 138,170 (-354) | 89,694 -> 89,503 (-191) | 89,688 -> 89,502 (-186) |
| 4 | 98,638 -> 98,458 (-180) | 104,036 -> 103,858 (-178) | 68,198 -> 68,097 (-101) | 71,136 -> 71,037 (-99) |
| 8 | 79,901 -> 79,805 (-96) | 83,787 -> 83,691 (-96) | 62,635 -> 62,586 (-49) | 64,152 -> 64,103 (-49) |

-0.1 % to -0.3 % everywhere, DMA words unchanged. The saving halves with each doubling of the cluster rows or of the PE
X axis: fewer, larger passes, so fewer weight sends.

## 3. Assessment

* Correct: the same results as `dev` in every check (162 RTL tests, 12 baseline cases, 4 real images, 16 Table 3
  configurations), lint 0 new.
* Gain: -0.1 % to -0.3 % cycles (-673 on the MNIST model, about 2.7 us at 250 MHz), only in the compute phase; it
  needs no resources (one constant of a comparison). Small, but free.
* Not synthesised with Vivado: the change is the constant of one comparison, so no change in resources or timing is
  expected; a Vivado run belongs to taking it into `dev`.
* Taken into `dev` on 2026-11-01 (approved by the user) on the strength of these worktree results: the same line, plus a
  comment at it and two comments on the range of `fsm_sending_cycle` (`OpenEye_FPGA.v`, `dense_mapper.py`). On `dev`
  itself: lint 0 new, Python unit tests 290 pass / 11 old fails, quantizer testbench 2/2, the first 16 of the 162 RTL
  regression tests PASS/xfail (the run was stopped on request). Vivado and a new cycle baseline were not run.
