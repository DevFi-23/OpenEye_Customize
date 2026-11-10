# 2026-11-09: upstream commits `302d330` ... `9a742fb` (2026-11-06), take or not

`git fetch upstream`: `upstream/main` moved from `b1e02a0` to `9a742fb` (five commits by DenLeb, 17 files, +326 / -217),
and a new branch `dev_asic_sg13g2` appeared. Nothing was taken; this note is the evidence. Method as in
`2026-11-06_upstream_dw_review.md`: worktrees of `9a742fb` ("new") and `b1e02a0` ("old"), the same 13 cases through each
tree's own Python, RTL and testbench (`2026-10-31_upstream_review/up_run.py`, Icarus, CR 2 x CC 2, NUM_GLB_PSUM 4 unless
stated, QUANT_AMOUNT 1024, random data) in sparse (`SPARSITY_EN=1`, the fork's mode) and dense (`SPARSITY_EN=0`,
upstream's mode), against `dev` = `2c09f81` with the same runner; and upstream's own Makefile test (Verilator 5.044,
`2026-11-06_upstream_dw_review/mkv.sh`).

## 1. The commits

| Commit | Change |
|---|---|
| `302d330` | PE cluster testbench sets `dw_mode` |
| `21bc1b6` | `hdl/debug/PE_IO_debug.v` test fix |
| `9594bec` "Changed data flow for iact stream constructors" | (a) the iact layer buffer holds **2 consecutive channels per group** (`MAX_CHANNELS_IACT_GLB = 2`, `cont_iact_channels_glb = min(used_channels, 2)`; was 4), `channel_div_trans = ceil(used_channels / 2)` widened to 3 bits; (b) with `NUM_GLB_IACT > 1` the banks are **interleaved**: the converter -> constructor bus is 16 bits (was 16 x NUM_GLB_IACT), `NUM_GLB_IACT` transfers are collected and written to the banks at one address, every bank reads the same address (was: every bank a full copy of the window, read at offsets `r * channel_div_trans`); the write-side delay register `ram_wr_en_q` is gone; (c) a fourth write address loop (`wr_addr_inc_3`, new regmap field) writes a channel-pair-major input stream into a pixel-major buffer: limits `words/ch_div/diff - 1`, `ch_div - 1`, `diff - 1`, increments `ch_div`, `1`, `words/diff`; (d) `used_channels = 4` no longer forced for 1 x 1 kernels; (e) ports `padding_x/y` removed; constructor FST dump for its unit test; Makefile defaults changed |
| `c288541` | `padding_x`, `padding_y` declared `wire` |
| `9a742fb` "Fixed Interlayer_operability" | write-back (`RECEIVE_PSUMS_TO_IACT`) in groups of **2** channels, hard-coded (`iact_to_psum_trans_counter == 2`, shift registers `32 * IACT_RAM_CELLS` bits), psum PAGU limits 4 -> 2, `diff_iact_layer_next_layer = 2` forced; Makefile default `Convolution_Stack`, `NUM_GLB_IACT=1`, `CLUSTER_COLUMNS=1`, 4 channels |

Upstream's test configuration (Makefile): **dense** (`SPARSITY_EN=0`), `PARALLEL_MACS=1`, 32-bit psums, 1 x 1 cluster,
`NUM_GLB_IACT=1`. `dev_asic_sg13g2` (Alexander Utz, based on `e78e5b7` of 2026-10-21): an ASIC flow for IHP SG13G2
(LibreLane / OpenROAD), RTL edits for latch / SRAM macros; its log of 2026-11-06 stops at the KLayout filler step, which
needs about 247 GiB of RAM on a 110 mm2 die. Not related to the FPGA fork.

Still in the code: the duplicate `assign rd_addr_inc_4_next` (lines 263, 266) and `rd_cycle_loop_cnt_4 <=
rd_cycle_loop_cnt_4` (480) of `7465852`; `iact_channel_sending_cycle2 ... //Remove?`. New inconsistency: Python
`IACT_RAM_CELLS_WORD_BITWIDTH = 4 * IACT_Trans_Bitwidth` is 64 in dense but **96 in sparse** (12-bit values with overhead),
while the RTL keeps `DATA_IACT_BITWIDTH * 8 = 64`.

## 2. Results

Simulated ns (same clock), 13 cases; FAIL = values differ, "hang" = no FSM progress for 200,000 cycles.

| Case | dev sparse | new sparse | old sparse | dev dense | new dense | old dense |
|---|---|---|---|---|---|---|
| Conv 8x4, 4 ch -> 16 | PASS 21,750 | hang | PASS 21,780 | FAIL | PASS 21,000 | PASS 20,990 |
| Conv 8x4, 2 ch | PASS 17,920 | FAIL | PASS 17,950 | FAIL | PASS 17,470 | PASS 17,460 |
| Conv 8x4, 3 ch | FAIL (#7) | FAIL | FAIL | FAIL | FAIL | FAIL |
| Conv 8x4, 8 ch | PASS 30,520 | FAIL | PASS 30,550 | FAIL | PASS 28,960 | PASS 28,950 |
| Conv 8x4, 16 ch | PASS 48,080 | FAIL | PASS 48,090 | FAIL | PASS 44,880 | PASS 44,870 |
| Conv 8x8, 4 ch, NUM_GLB_IACT 3 | PASS 30,740 | FAIL | FAIL | FAIL | **PASS 29,900** | FAIL |
| Conv 8x8, 2 ch, NUM_GLB_IACT 3 | PASS 26,510 | hang | FAIL | FAIL | **PASS 25,940** | FAIL |
| Conv 28x28x1 -> 32 | PASS 403,820 | FAIL | PASS 378,200 | FAIL | PASS 376,210 | PASS 376,200 |
| Conv -> Conv 8x4x4 | PASS 35,500 | hang | PASS 35,560 | FAIL | FAIL (buffer) | FAIL (buffer) |
| Conv -> Conv, NUM_GLB_PSUM 2 | PASS 29,800 | hang | FAIL (#25) | FAIL | FAIL (buffer) | FAIL (buffer) |
| Conv -> Pool -> Conv 8x4x2 | PASS 38,130 | FAIL (buffer) | FAIL | FAIL | FAIL (buffer) | FAIL (buffer) |
| Conv -> Conv 8x4x8 | PASS 46,990 | FAIL (buffer) | PASS 47,020 | FAIL | FAIL (buffer) | FAIL (buffer) |
| Conv 16x4, 6 ch | **FAIL** | hang | hang | FAIL | FAIL | FAIL |

Upstream's own Makefile test (dense, 1 x 1 cluster): `Convolution_Stack` PASS on new (FAIL on old: "Fixed
Interlayer_operability" works in that configuration), `Convolution_Single` PASS on both.

Also found for `dev` (sparse): Conv with more than 4 input channels that are not a multiple of 4 is wrong (6, 10: every
map; 12 passes) without any check refusing it: new bug **#45**. Upstream has it too (6 channels hang). And `dev` in dense
mode fails every case: the fork never ran dense; its fixes (weight encoding #22, empty pass #31, ...) are on the sparse
path.

## 3. Whose approach is better, algorithm by algorithm

* **Several iact banks (`NUM_GLB_IACT > 1`).** Upstream now interleaves the banks: one copy of the data, a 16-bit bus into
  each constructor, every bank at one address; the fork writes the whole window into every bank (N copies, an N x wider
  bus, N x the buffer words per pass, so `check_iact_buffer` refuses layers earlier) and reads at offsets. Same cycles
  (29,900 dense against 30,740 sparse, the sparse overhead included), so the interleaving is the better algorithm on
  memory and wiring, and it works in dense mode. For the fork it does not matter today: every configuration it measures
  (baseline, MNIST, Table 3, the Vivado baseline) has `NUM_GLB_IACT = 1`.
* **Channel granularity of the iact buffer (2 against 4).** Two-channel groups would let channel counts that are not a
  multiple of 4 map without padding, but upstream still fails 3 and 6 channels. The fork's 4-channel groups match the
  4 channels a PE takes per pass with 3 x 3 kernels and its write-back (#25); 6 / 10 channels (#45) and 3 channels (#7)
  are cheaper to handle on the host by padding to a multiple of 4 with zero channels, which the sparse PE skips.
* **Write-back.** The fork's groups of 4 channels per pixel for any number of lanes (#25), output-size geometry (#41c), are
  verified with NUM_GLB_PSUM 2 and 4, strides, pooling and Dense; upstream's is hard-coded to 2 and passes only its
  1 x 1 cluster test (every chain fails at 2 x 2).
* **Sparse against dense.** Upstream works dense (smaller PE, ASIC); its new Python breaks sparse (13 of 13). The fork's
  latency work rests on zero skipping (63-83 % zeros after ReLU in the trained MNIST net); with the random non-zero test
  data dense is about 3-7 % faster than sparse (no overhead), with real activations sparse is far ahead.
* **One upstream feature worth measuring separately:** on 28 x 28 x 1 -> 32 both upstream trees take 376,000-378,000 ns
  against the fork's 403,820 (6-7 % fewer); `b10db82` raised the psums per PE from 16 to 32 (one weight pass instead of two).
  The fork did not take `b10db82` (#39, the #22-type hang); the 32-psum idea alone could be tried.

## 4. Decision

Not taken. The commits sit on `b10db82` (not in the fork), rewrite the same constructor and write-back code as the fork's
fixes #6/#7, #13, #17, #25, #37, #41c, break sparse mode and fail every layer chain on 2 x 2 clusters, and keep two
known code errors. Ideas for later, implemented on the fork's own code: interleaved banks if `NUM_GLB_IACT > 1` is
adopted; 32 psums per PE (measure); fix #45 / #7 by host-side channel padding.
