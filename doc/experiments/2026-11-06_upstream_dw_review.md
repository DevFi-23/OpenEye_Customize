# 2026-11-06: upstream commits `e8b3c3e` … `b1e02a0` (2026-11-05, depthwise reimplementation), take or not

`git fetch upstream`: `upstream/main` moved from `b10db82` (2026-11-04) to `b1e02a0`; five new commits by DenLeb, all
2026-11-05, 13 files, +290 / −189 lines against `b10db82`. **Nothing was taken, no file of `dev` was changed.** This note
is the evidence. Method: both upstream trees in scratch worktrees (`b1e02a0` "new", `b10db82` "old"); (a) the fork's
runner `2026-10-31_upstream_review/up_run.py` (each tree's own `test_conv_const._run_conv_const`, Icarus, sparse PE,
CR 2 × CC 2) and (b) upstream's own Makefile flow (`test/cocotb_fpga/Makefile`, dense PE `SPARSITY_EN=0`, Verilator,
script `2026-11-06_upstream_dw_review/mkv.sh`). Lint with `tools/lint_check.py` (Verilator 5.020), Yosys 0.69 for driver
checks. In both scratch trees `rtl_test_utils.py` decoded X/Z output bits as 0 (logged) instead of raising, so a run with
undriven outputs still reaches the comparison.

## 1. What the five commits change

| Commit | Files | Change |
|---|---|---|
| `e8b3c3e` "Reimplemented Depthwise Convolution" | `OpenEye_FPGA.v`, `OpenEye_Parallel.v`, `PE.v`, `iact_stream_constructor.v`, `psum_pipeline.v`, `router_configurator.v`, `dw_mapper.py`, `layer_parameters.py` (221 lines), `open_eye_parameters.py`, `test_utils_main.py`, Makefile, `regmap.yaml` | Depthwise (DW) moves into the **dense** PE FSM as a `dw_mode` (one channel per filter); `layer_parameters.get_pagu_values` / `calculate_pe_transmissions` rewritten (the `single_cluster_computation` branch is gone; it only applied to `SERIAL = 0`, so no effect on the fork); `CHANNEL_CYCLE_WIDTH` (new parameter: RTL default 12, `OpenEyeParameters` default 16, Makefile 12) widens `iact_channel_max_cycles` and its regmap field (8 → `CHANNEL_CYCLE_WIDTH` bit); DW reference in `test_utils_main.py` indexes x / y the right way round; Makefile switch `WAVES` |
| `2abe8d4` "Probably fixed one wrong wire" | `OpenEye_FPGA.v` | `iact_buffer_addr` declared `wire` instead of `reg` (it is driven by `assign`) |
| `0d5a0e3` "The next wire/reg bug" | `OpenEye_FPGA.v` | `quantized_value_reg` declared `wire` instead of `reg` (same pattern) |
| `7465852` "Chnages to Iact PAGU" | `iact_stream_constructor.v`, `layer_parameters.py` | iact read address generator renumbered: one more loop level, `rd_addr_inc_0` becomes the step inside a word group, the others shift by one |
| `b1e02a0` "Added reset to dw_mode" | `test/cocotb_PE/PE_tb.py` | PE unit testbench drives `dw_mode` to 0 |

All five sit on `b10db82` ("Re-Enabled python interface for DW Conv", 20 files, +1149 / −784), which the fork never took
(it carries bug #39 for more than 32 filters per calculation and the #22-type hang, `2026-11-05_b10db82_hang.md`).

## 2. Code review findings

* **`7465852`, read loop 4 never counts:** `iact_stream_constructor.v:453` `rd_cycle_loop_cnt_4 <= rd_cycle_loop_cnt_4;`
  (the other four levels say `+ 1`). With `rd_loop_limit_4 = 0` the wrap happens anyway; with a non-zero limit the
  outermost loop never wraps to address 0.
* **`7465852`, two drivers:** `assign rd_addr_inc_4_next = rd_addr_4 + rd_addr_inc_4;` appears at lines 236 and 239
  (the second under the old single-channel comment). Same expression, so simulators agree, but Yosys reports
  "multiple conflicting drivers" and it is a lint error class (`MULTIDRIVEN`) the fork removed for #13.
* **`7465852`, Python only half adapted:** the conv branch of `get_pagu_values` follows the new numbering, the DW branch
  still writes the old meaning (`inc_0 = 1`).
* **`7465852` vs the fork:** the fork keeps the `NUM_GLB_IACT − 1` skip term in `rd_addr_inc_0_next` (from `6d513f6`,
  needed for `NUM_GLB_IACT = 3`, removed upstream in `36395dd`) and the old `iact_read_inc_2`; the renumbering conflicts
  with both.
* **`CHANNEL_CYCLE_WIDTH` incomplete:** `psum_pipeline.v` `iact_channel_counter_reg` and `router_configurator.v`
  `iact_channels_counter_psum_router_o` stay 8 bit while the limit they are compared with is 12 / 16 bit (lint
  `WIDTHEXPAND`); RTL and Python defaults differ (12 vs 16); the regmap field changes width, so the packed status
  layout moves.
* **`2abe8d4`, `0d5a0e3`:** correct Verilog (a `reg` must not be driven by `assign`). The fork has the same two
  declarations (`OpenEye_FPGA.v:1381` with the assign at :2842, `:1455` with :2698); Icarus, Verilator 5.020 and Vivado
  accept them today, so the change is cosmetic for the fork.
* **Lint** (`fpga` top, new against old): 458 vs 464 warnings; 5 new (`UNUSEDSIGNAL dw_mode_w`, `WIDTHEXPAND`
  `OpenEye_FPGA.v:3094` 16 vs 12, `psum_pipeline.v:566` and `router_configurator.v:320` 8-bit counters, `WIDTHTRUNC`
  `DEPTHWISE_ENABLED` as a condition), 11 old truncation warnings gone.

## 3. Simulation

**(a) Fork runner, sparse PE, Icarus, CR 2 × CC 2** (random data):

| Case | old `b10db82` | new `b1e02a0` |
|---|---|---|
| Conv 8×4×1 → 64 | not rerun | PASS |
| Conv 28×28×2 → 64 | not rerun | PASS |
| Conv 28×28×1 → 32 | not rerun | PASS |
| Conv 8×8×2 → 16, `NUM_GLB_IACT = 3` | FAIL | FAIL (channel mapping bug the fork fixed, #6 / #7) |
| DW | hangs | hangs (sparse PE has no DW path; not the authors' configuration) |

(`b10db82` results for one channel and many filters: `2026-11-05_bug39_detail.md` section 8.)

**(b) Upstream's Makefile flow, dense PE, Verilator 5.044, original buffer widths** (random data, not seeded:
upstream's testbench does not read `OPENEYE_SEED`; about 1 minute and 2 GB per case):

| Case | old `b10db82` | new `b1e02a0` |
|---|---|---|
| Conv 8×8×4 → 16 | PASS, 78 190 ns | PASS, 78 190 ns |
| Conv 12×6×1 → 8 | PASS, 34 710 ns | PASS, 34 710 ns |
| DW 12×2×8 (new Makefile default) | FAIL, 8 / 8 maps, 88 / 192 words differ | FAIL, 8 / 8 maps, 192 / 192 words differ (128 are 0) |
| DW 4×1×4 (old Makefile default) | FAIL, 4 / 4 maps, 16 / 16 words | FAIL, 4 / 4 maps, 16 / 16 words (all 0) |
| DW 8×8×4 | FAIL, 4 / 4 maps, 256 / 256 words, 28 130 ns | FAIL, 4 / 4 maps, 256 / 256 words, 31 070 ns |

Icarus with the Makefile's 23 / 24-bit buffers needs 5.8 GB per run (out of memory on this machine); with buffer widths
12 / 13 / 13 the new DW default case gives 192 / 192 wrong words (at least 100 undriven, decoded as 0), the old default
4 / 4 maps wrong. Verilator ≥ 5.036 is required by cocotb 2.0.1; installed next to the lint version:
`~/tools/bin/micromamba create -p ~/tools/verilator-5.044 -c conda-forge verilator=5.044`. `b10db82`'s Makefile always
adds `--trace --trace-fst`, which needs `zlib.h`; pass `EXTRA_ARGS=`.

Conclusions: depthwise does **not** produce correct results in upstream's own configuration before or after these
commits (the new code mostly outputs 0); dense convolution is cycle-identical, so the PAGU rework brings no speed-up.

## 4. Decision

Not taken (2026-11-06):
1. depends on `b10db82` (not in the fork, carries #39 and the #22 hang);
2. DW is unfinished upstream and lives only in the dense PE FSM, while the fork runs the sparse PE (`SPARSITY_EN = 1`);
3. the PAGU rework has a counting typo and a double driver, gives no conv benefit and conflicts with fork fixes;
4. the `CHANNEL_CYCLE_WIDTH` widening is incomplete and changes the regmap layout.

Possible small pieces, only with approval (RTL): the two `reg` → `wire` declarations (no behaviour change), the
Makefile `WAVES` switch (testbench only). DW stays on the watch list (MobileNet-type networks, latency goal): re-test
when upstream's own DW test passes.
