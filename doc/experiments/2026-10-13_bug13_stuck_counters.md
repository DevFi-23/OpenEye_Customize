# Experiment 2026-10-13: does bug #13 (multi-driven iact read-loop counters) break the hardware?

## Question

Vivado reports CRITICAL WARNING Synth 8-6858/8-6859 on `hdl/iact_stream_constructor.v:475-478`: the counters
`rd_cycle_loop_cnt_0..3` are reset in one `always` block (line 437) and counted in another (line 233). Vivado keeps the
constant driver (the reset value 0) and drops the counting logic, so in the synthesised hardware the four counters are always 0.
Simulators let the last write win and show the intended behaviour. Does the hardware therefore compute wrong results?

## Method (approved by the user; the project RTL was not touched)

- Two temporary git worktrees of `dev` at 2462665 in the session scratch directory, both removed afterwards:
  - `wt_stuck`: the four `rd_cycle_loop_cnt_N <= rd_cycle_loop_cnt_N + 1;` lines replaced by `rd_cycle_loop_cnt_N <= 8'd0;`.
    Since the reset value is 0 and every other assignment writes 0, the registers stay 0, which is exactly the netlist Vivado builds.
  - `wt_ctrl`: unmodified, as the control.
- Each worktree ran with `PYTHONPATH=<worktree>/src`, so `open_eye.hdl_dir` pointed at the worktree's `hdl/`
  (checked: the compiled `OpenEye_FPGA.vvp` references `wt_stuck/hdl/iact_stream_constructor.v`).
- `tools/run_profile.py` (9 baseline cases, ideal memory) in `wt_stuck`; the three `32x3` cases also in `wt_ctrl`.
- `tools/decode_iact_read_loops.py` decoded the loop registers each case sends to the DUT.

## Result

| Case | iact_read_limit_0..4 | iact_read_inc_0..4 | Stuck counters (hardware) | Control |
|---|---|---|---|---|
| 8x1_f4_q32_dma64 | 11, 0, 0, 0, 0 | 1, 12, 36, 12, 12 | **PASS** | (baseline PASS) |
| 8x1_f4_q1024_dma64 | 11, 0, 0, 0, 0 | 1, 12, 36, 12, 12 | **PASS** | (baseline PASS) |
| 16x3_f4_q32_dma64 | 11, 0, 0, 0, 2 | 1, 12, 60, 12, 12 | **PASS** | (baseline PASS) |
| 32x3_f4_q32_dma64 | 11, 0, 0, **1**, 2 | 1, 24, 120, 12, 24 | **FAIL**: 4/4 feature maps wrong | PASS, 1,672 cycles (= baseline) |
| 32x3_f4_q32_dma32 | 11, 0, 0, **1**, 2 | 1, 24, 120, 12, 24 | **FAIL**: 4/4 wrong | PASS, 2,236 cycles (= baseline) |
| 32x3_f16_q32_dma64 | 11, 0, 0, **1**, 2 | 1, 24, 120, 12, 24 | **FAIL**: 16/16 wrong | PASS, 3,652 cycles (= baseline) |
| mnist1_28x28_c4_f32 | 11, 0, **1**, **1**, 27 | 1, 24, 720, 12, 24 | **FAIL**: 32/32 wrong | (baseline PASS) |
| mnist2_14x14_c32_f32 | 11, **7**, **1**, 0, 13 | 1, 12, 192, 12, 12 | **FAIL**: 32/32 wrong | (baseline PASS) |
| mnist3_8x8_c32_f32 | 11, **7**, 0, 0, 7 | 1, 12, 120, 12, 12 | **FAIL**: 32/32 wrong | (baseline PASS) |

The failing runs did not hang: they finished, read out the same number of words as the baseline, and the result check found
wrong values (for example mnist1: reference 6073, 7261, 7393, ...; DUT 3645, 3645, 3645, ...; only 3 distinct output values in
2,048 compared positions, because the read address never moves on to the next input window). Compute took fewer cycles than the
baseline (mnist2 17,049 vs 66,681), which is a symptom of the wrong data (fewer non-zero products), not a speed-up.

## Why some cases pass

- Loop 1-3 (`rd_cycle_loop_cnt_1..3`): the wrap branch runs when `cnt == limit`. With the counter stuck at 0 it runs every time
  if the limit is 0 (correct by accident) and never if the limit is not 0 (the address never jumps to the next row/line, wrong).
- Loop 0: with the counter stuck it never wraps, so the address keeps advancing by `inc_0`. In all nine cases the wrap target
  `rd_addr_1 + inc_1` equals that sequential address (`inc_1 = (limit_0 + 1) * inc_0` with the bank skip), and the address is
  reloaded by loop 1 at the end of every compute step, so loop 0 caused no error here.
- Rule observed: the hardware is wrong whenever one of `iact_read_limit_1..3` is not 0, which is every layer wider than about 16
  pixels or with more than one row group, i.e. every realistic layer (all three MNIST-like layers).

## Conclusion

Bug #13 is real and severe: a bitstream built from the current RTL computes wrong convolution results for all realistic layers,
while every simulation passes. Before any measurement on a board, and before further RTL optimisation, the four reset
assignments have to move into the reset branch of the counting `always` block (no cycle or resource cost expected), followed by
the full regression and a new synthesis (the CRITICAL WARNING must disappear).
