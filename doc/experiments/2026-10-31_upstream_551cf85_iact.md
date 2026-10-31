# 2026-10-31: upstream 551cf85 (iact_stream_constructor before 23be043) compared with dev

Upstream `551cf85` (2026-10-27, "Restore iact_stream_constructor pre-23be043; fixes 3x3 conv regression") changes only
`hdl/iact_stream_constructor.v`. The question: how does it differ from the module in `dev`, what is its separate FC
path, and which of the two is the better design. Nothing of `dev` was changed for this note: upstream was run unmodified
in worktrees, and the module versions were only read and synthesised on their own with Yosys.

## 1. What the commit is

The file after `551cf85` is **byte-identical** to the file of `f84f064`, the last upstream commit before `23be043`
("Fixed many bugs for Dense Layer", 2026-10-01). So `551cf85` is a plain revert of this one file, with no new code. It
undoes `23be043` and `c4bd562` in this file only; the other parts of `23be043` (`OpenEye_FPGA.v` 67 lines,
`OpenEye_Parallel.v`, `layer_parameters.py`, `dense_mapper.py`, `psum_stream_mapper.py`, `wght_stream_mapper.py`, ...)
stay as they were.

History of the module:

| Version | Content |
|---|---|
| `f84f064` = `551cf85` (829 lines) | Convolution FSM plus a **separate FC path** (section 2) |
| `23be043` + `c4bd562` (730 lines) | FC merged into the convolution writer: bank rotation (`router_cycle`, `switching_cycle`), FC pair count `(channels*PE_Y)/2`; regressions #6 (one channel) and #7 (`NUM_GLB_IACT=3`) |
| `dev` (746 lines) | `c4bd562` + four small fixes, about 40 changed lines: #13 (read-loop counters reset in the block that counts them), #6 (one-channel write address `ram_wr_addr_q`), #7 (`rotate_banks` only for FC with more than one bank), #19 (12-bit pair counter `x_pos_in_w_cycle`) |
| upstream HEAD `93f0e82` (830 lines) | `551cf85` + the widened limits of `655a2ae` |

The port lists of `dev` and `551cf85` are the same except for two signed inputs (`iact_x_add_up`,
`iact_channels_per_pe_i` are `signed` in the old version).

## 2. The separate FC path of the old version

The old version splits both always blocks with `if (fully_connected_i) ... else <convolution FSM>`:

* **Write side.** The FPGA top asserts `fc_storage_valid_i` for each activation pair. Counters `fc_store_pe_row`
  (0 to PE_Y-1), `fc_store_pair` (0 to channels/2-1) and `fc_store_row` (cluster row) walk the Dense input in the order
  of `DenseWghtStreamMapper`. Only the cluster row equal to the parameter `CLUSTER_ROW_ID` stores the pair, in the
  physical bank `pe_row % NUM_GLB_IACT`. With fewer banks than PE rows each bank keeps its own address counter
  (`fc_bank_addr[]`).
* **Read side.** It has its own two-state FSM. Per PE row it reads `channels` words, prefetching each pair because
  `RAM_SP` has two read stages, and drives `iact_choose_o` per PE row. With `NUM_GLB_IACT < PE_Y` it serves the PE rows one
  after the other (`fc_output_row`, base address `fc_output_base_addr`); with `NUM_GLB_IACT >= PE_Y` all rows go at once.

`23be043` removed this path and let FC go through the convolution writer, with bank rotation. `dev` kept that structure
and fixed the four bugs listed above. In `dev` the port `fc_storage_valid_i` is still there but no longer read.

## 3. Bug #13 comes back with 551cf85

In the old version the read-loop counters `rd_cycle_loop_cnt_0..3` are counted in the encoder block (lines 421-453) but
reset in the storage block (lines 550-553). That is bug #13 (`2026-10-13_bug13_stuck_counters.md`): two always blocks
drive the same registers. Simulators let the last write win, so simulations pass. Vivado keeps the constant reset
driver and removes the counting logic (Synth 8-6858/8-6859), so on the FPGA the counters stay 0. In the 2026-10-13
experiment 6 of the 9 baseline cases, including the three MNIST layers, then read wrong iact addresses. `dev` fixed it
in `5f1e66e`, which also removed the CRITICAL WARNINGs. Yosys on the `551cf85` file reports
`multiple conflicting drivers for iact_stream_constructor.\rd_cycle_loop_cnt_0..3` (83 warnings; 2 for `dev`, both
harmless memory-to-register notes). Upstream HEAD `93f0e82` still has it (lines 425-465 against 551-554).

## 4. Measurements

### 4.1 Correctness and cycles in simulation

Same runner on every tree, the tree's own RTL, testbench and Python (`2026-10-31_upstream_review/up_run.py`, random data,
`OPENEYE_SEED=1`, 2x2 clusters, `NUM_GLB_PSUM` 4). Cycles = simulated time / 10 ns, same testbench clock on all trees; for
the two upstream trees they come from the same testbench, so their difference is the effect of the module alone.

| Case (`up_run.py` arguments) | `f84f064` tree (before `23be043`) | `2dde2db` (parent of `551cf85`) | `551cf85` | `dev` |
|---|---|---|---|---|
| Conv 8x4, 1 channel (`c1ch`, #6) | PASS 1,410 | FAIL (4/4 maps) | PASS 1,410 | PASS 1,410 |
| Conv 8x4, 4 channels (`c4g1`) | - | PASS 1,811 | PASS 1,811 | PASS 1,811 |
| Conv 8x4, 4 channels, `NUM_GLB_IACT=3` (`c4g3`, #7) | PASS 1,696 | FAIL (4/4) | PASS 1,696 | PASS **1,673** |
| Conv 14x4, 8 channels, `NUM_GLB_IACT=3` (`c8g3`) | **FAIL** (8/8) | FAIL (8/8) | **FAIL** (8/8) | PASS 3,083 |
| FC 256 -> 10 | FAIL (iact buffer, word 0) | PASS 2,112 | PASS 2,112 | PASS 2,112 |
| FC 512 -> 16, `NUM_GLB_IACT=3` | - | PASS 3,967 | PASS 3,967 | PASS 3,967 |
| FC 1024 -> 10 (#19, part 1) | FAIL (iact buffer, word 0) | FAIL (10/10) | PASS 5,644 | PASS 5,644 |
| FC 2032 -> 10 | - | - | PASS 10,164 | - |
| FC 2064 -> 10 (#19, part 2) | - | - | **FAIL** (10/10) | - |
| FC 3136 -> 10 (Dense of the trained MNIST model) | - | FAIL (10/10) | **FAIL** (10/10) | PASS 15,032 |

* `551cf85` does fix what it says: the one-channel and `NUM_GLB_IACT=3` regressions of `23be043` (#6, #7), and its FC
  path has no 8-bit pair counter, so K = 1024 is right where `2dde2db` drops every activation from index 512 on
  (#19 part 1, fixed in `dev` by the 12-bit `x_pos_in_w_cycle`).
* It does not fix FC with K > 2048: K = 2032 passes, K = 2064 fails. That is #19 part 2, the signed 12-bit `current_x`
  in the FC store condition of `OpenEye_FPGA.v` (fixed in `dev` in `10bcaf7`), which no upstream commit touches. This is
  why upstream fails the Dense 3136 -> 10 / 16 of the trained model (`2026-10-31_upstream_review.md`).
* Conv 14x4x8 -> 8 with `NUM_GLB_IACT=3` fails with the old module on its own tree before `23be043` too, so it is an old
  bug of that convolution path, not a mismatch with the rest of `23be043`. `dev` passes it.
* On its own tree before `23be043` the old module's FC fails already at the first iact buffer word (the old tree builds
  the FC model with a Flatten layer, run with 2 expected layers): FC was broken in the rest of that tree, which is what
  `23be043` fixed. Inside the later tree (`551cf85`) the old FC path works up to K = 2048.
* Cycles: the same in every passing case except `c4g3`, where `dev` is 23 cycles (1.4 %) faster. The separate FC path is
  not faster than the merged writer of `dev` (FC 256, 512, 1024: identical totals).

### 4.2 Resources (Yosys 0.69, `synth_xilinx`, module alone, RAM_SP as a black box)

Parameters of the Vivado baseline (2x2 clusters, PE 4x3, `ADDRWIDTH` 13), `NUM_GLB_IACT` 1 and 3:

| `NUM_GLB_IACT` | `dev` LUT / FF / CARRY4 | `551cf85` LUT / FF / CARRY4 |
|---|---:|---:|
| 1 | 891 / 375 / 130 | 992 / 363 / 136 |
| 3 | 1,074 / 474 / 146 | 1,127 / 444 / 150 |

The old version has 5-11 % more LUT and 3-6 % fewer FF, but its netlist is not valid (the multi-driven counters of
section 3), so its numbers are only indicative. Vivado on `dev` (baseline `doc/synth/2026-10-30_route4ns_fix31_zu7ev`):
537-564 LUT and 367-374 FF per instance, four instances, about 3.7 % of the design.

## 5. Which is better

`dev`. It is correct in every case above, the old module is not (Conv 8 channels with three banks, and it brings back
bug #13, which breaks the hardware without showing in simulation); `dev` is as fast or faster and about as large; and its
change against upstream is about 40 lines on the structure upstream used from `23be043` to `2dde2db`, each tied to a
tested bug fix, while taking `551cf85` replaces the module and would need #13 and #19 fixed again in another code
base. The separate FC path is a reasonable idea in itself (FC and convolution logic do not interfere, one bank per PE
row), but it gives no cycle advantage here and does not by itself fix the FC limits of the top level. Not taken.
