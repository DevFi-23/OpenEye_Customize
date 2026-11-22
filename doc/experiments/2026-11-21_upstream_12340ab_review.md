# 2026-11-21: upstream `12340ab` "Added fixes for FC Layers" (2026-11-18), take or not

`git fetch upstream`: `upstream/main` moved from `3e2e027` (reviewed 2026-11-17) to `12340ab`, one commit by DenLeb.
Other branches: only `dev_asic_sg13g2` moved (`d4b8afc`, 2026-11-13: status logs of the LibreLane run, which stops at the
KLayout filler on a 251 GB host, plus a `.gitignore` line; nothing for the FPGA fork). Nothing was taken into `dev`; this
note is the evidence. Analysis only; every run below used detached worktrees in a scratch directory.

## 1. The commit

| File | Change | What it does (algorithm) |
|---|---|---|
| `hdl/OpenEye_FPGA.v` | `fc_size_reg` 14 → 20 bit (with `regmap.yaml`) | FC input size K: the iact converter of an FC layer counts activations in `current_x` and stops at `current_x < fc_size_reg` |
| `hdl/OpenEye_FPGA.v` | the branch `if ((iact_converter_x + iact_x_per_cluster) >= iact_x_add_up) & (kernels_per_calc != 1) & (iact_x_per_cluster < iact_x_add_up)) iact_converter_x <= iact_x_per_cluster` commented out | Conv (not FC) path of the iact converter: when the x sweep of a row ends and there are several kernel groups per calculation, the next kernel group used to start at x = `iact_x_per_cluster` (second cluster column tile) instead of 0 |
| `hdl/iact_stream_constructor.v` | `iact_channels_per_pe_i` signed → unsigned; FC `iact_values_per_cluster_transmit = (iact_channels_per_pe_i / 2) * PE_Y` (was `iact_channels_per_pe_i * PE_Y`) | FC: activations per cluster transmission. One buffer word carries 2 activations, so the count is in pairs; a signed 4-bit port read 8 and 12 activations per PE as negative |
| `src/open_eye/layer_parameters.py` (`write_dense_layer`) | `iact_read_inc_2 = 0` (was `ceil(needed_Iact_writes * used_iact_per_PE / 2)`, equal to `iact_read_inc_1`) | FC read address generator: loops 1 and 2 both stepped by one K pass, so a layer with several K passes read twice too far |
| `src/open_eye/test_utils_main.py` (`fill_dram_with_ref`) | reference position of a written-back activation `(f % 2, x % 4)` instead of `(f % 4, x % 2)` | iact buffer check after Conv → Dense: 2-channel words of upstream's 2-channel rewrite (`9594bec` .. `3e2e027`) |
| `src/open_eye/data_create.py` | model `FC` = Conv → MaxPool → Flatten → Dense (was one Dense with input (1, 1, K)); `VGG-19` cut to alpha 0.25, 128 × 128, one conv per block | test models |
| `test/cocotb_fpga/test_single_layers.py` | sweep CR 1 / 2 / 4 / 6 / 8 × CC 1 / 2, dense (`SPARSITY_EN` 0), DMA 32 bit, default model `VGG-19`; fixed directory names, waves on | test |

## 2. Against `dev`, change by change (static)

| Change | In `dev` | Verdict |
|---|---|---|
| `fc_size_reg` 20 bit | 14 bit. In both trees `current_x` is `reg signed [11:0]`, stepped by 2 per FC word. Upstream still tests `(current_x >= 0)` in the FC path, so from activation 2048 on `current_x` reads negative and the rest of the input is dropped: bug #19 part 2, fixed in `dev` (`10bcaf7`: `fully_connected_layer \| (current_x >= 0)`). In `dev` the unsigned comparison with `fc_size_reg` holds up to K = 4094; at 4096 the 12-bit counter wraps. A 14-bit field (16,383) is therefore never the limit, in either tree; 20 bits change nothing until `current_x` grows | Not useful. Measured: section 3 (K at 2046 / 2050 upstream, 4096 / 4200 `dev`) |
| converter branch removed | present (`OpenEye_FPGA.v:972`, from `83a47b6`, 2026-09-11, "Fixed iact writing to clusters in all configurations") | Changes which cluster column handles which x tile in the next kernel group; upstream changed no Python with it. Tested on a copy of `dev` (section 4) |
| FC `/ 2`, unsigned port | already in `dev`: `iact_values_per_cluster_transmit <= (iact_channels_per_pe_i * PE_Y) / 2` since `23be043` (in the fork base), port unsigned. Upstream lost it with the revert `551cf85` and its FC rewrite, and now puts it back. `(c / 2) * PE_Y` = `(c * PE_Y) / 2` for even c, and the Python makes c even for FC | Already there |
| `iact_read_inc_2 = 0` | `dev` keeps the loop numbering from before upstream `7465852` (renumbered read loops, not taken): Dense sets `iact_read_limit_1 = diff_iact_layer - 1` and `iact_read_inc_2 = ceil(...)`, the step of that same loop in `dev`'s constructor. Dense with several K passes is right in `dev` (1568 and 3136 inputs in the regression) | Not applicable (different loop layout) |
| `fill_dram_with_ref` 2-channel | `dev` writes back in 4-channel words (`f % 4`, `x % 2`), checked after every layer in the regression | Would break `dev`'s buffer check |
| models, test sweep | `dev` has its own models for these paths (`Conv_Dense`, MNIST, paper network) | Test only. Their cut VGG-19 (3 input channels, Dense 2048 → 1024 → 1024) was not run: 3 channels are refused in `dev` (#7), and a Dense of 2M weights is far above the weight buffer (Dense 3136 → 64 is already refused, #29) |

Bug #21 (testbench decoder of multi-pass Dense output, fixed in `dev` 2026-11-21): upstream's `compare_stream_Dense`
has the same line `f = offset + (beat % columns) * per_column + beat // columns`, not touched by this commit.

## 3. Runs: upstream before / after, `dev`, `dev` + the converter change

Trees (detached worktrees of a scratch directory): `up_old` = `3e2e027`, `up_new` = `12340ab`, `dev_fc` = `dev` (`6a7a323`),
`dev_p1` = `dev` + only the converter change of `12340ab` (`OpenEye_FPGA.v`, three lines commented). All four got the same
two test models in `data_create.py` (test models only): `UP_FC` = upstream's new `FC` (Conv → MaxPool → Flatten → Dense),
and `Conv_Dense` of the fork in the upstream trees. Each case runs through the tree's own Python, RTL and testbench
(`2026-10-31_upstream_review/up_run.py` via `run1.sh`; Icarus, CR 2 × CC 2, `QUANT_AMOUNT` 1024, random data, seed 1),
sparse (`SPARSITY_EN` 1) and dense (0). Cells: simulated ns of a PASS, or the failure. `up_old sparse` of the 13 conv
cases was not rerun (0 / 13 on 2026-11-17). `d6_mlp` expects 3 layers, upstream's `MLP` has 2 (6 → 32 → 16), so the
upstream trees ran `d6b_mlp2` instead. Results: `matrix*.txt`, table by `table.py` (the CC 1 cases `h*` / `n*` and the
FC input sizes `k*` are in sections 3b and 4).

| Case | up_old dense | up_new dense | up_old sparse | up_new sparse | dev_fc dense | dev_fc sparse | dev_p1 dense | dev_p1 sparse |
| c1_8x4c4 | PASS 21,000 | PASS 21,000 |  | hang | PASS 18,480 | PASS 19,270 | PASS 18,480 | PASS 19,270 |
| c2_8x4c2 | PASS 17,380 | PASS 17,380 |  | FAIL (16 of 16 maps) | PASS 14,950 | PASS 15,440 | PASS 14,950 | PASS 15,440 |
| c3_8x4c3 | FAIL | FAIL |  | FAIL (16 of 16 maps) | FAIL | FAIL (16 of 16 maps) | FAIL | FAIL (16 of 16 maps) |
| c4_8x4c8 | PASS 28,960 | PASS 28,960 |  | FAIL (16 of 16 maps) | PASS 26,440 | PASS 28,040 | PASS 26,440 | PASS 28,040 |
| c5_8x4c16 | PASS 44,880 | PASS 44,880 |  | hang | PASS 42,360 | PASS 45,600 | PASS 42,360 | PASS 45,600 |
| c6_8x8c4_g3 | PASS 29,900 | PASS 29,900 |  | FAIL (16 of 16 maps) | PASS 24,820 | PASS 25,700 | PASS 24,820 | PASS 25,700 |
| c7_8x8c2_g3 | PASS 25,860 | PASS 25,860 |  | hang | PASS 20,860 | PASS 21,470 | PASS 20,860 | PASS 21,470 |
| c8_28x28c1 | PASS 376,210 | PASS 376,210 |  | FAIL (32 of 32 maps) | PASS 259,790 | PASS 263,520 | PASS 259,790 | PASS 263,520 |
| c9_stack_c4 | FAIL (4 of 4 maps) | FAIL (4 of 4 maps) |  | hang | PASS 32,040 | PASS 32,980 | PASS 32,040 | PASS 32,980 |
| c10_stack_c4_p2 | FAIL (iact buffer) | FAIL (iact buffer) |  | hang | PASS 27,560 | PASS 28,560 | PASS 27,560 | PASS 28,560 |
| c11_cpc | FAIL (8 of 8 maps) | FAIL (8 of 8 maps) |  | FAIL (iact buffer) | PASS 35,200 | PASS 36,290 | PASS 35,200 | PASS 36,290 |
| c12_stack_c8 | PASS 45,190 | PASS 45,190 |  | FAIL (iact buffer) | PASS 42,560 | PASS 44,510 | PASS 42,560 | PASS 44,510 |
| c13_16x4c6 | FAIL | FAIL |  | FAIL (16 of 16 maps) | FAIL | FAIL (16 of 16 maps) | FAIL | FAIL (16 of 16 maps) |
| d1_gemm64_10 | FAIL | PASS 10,750 | FAIL (10 of 10) | FAIL (10 of 10) | PASS 10,710 | PASS 11,460 | PASS 10,710 | PASS 11,460 |
| d2_gemm256_32 | FAIL | PASS 30,060 | FAIL (32 of 32) | FAIL (32 of 32) | PASS 30,020 | PASS 37,880 | PASS 30,020 | PASS 37,880 |
| d3_gemm1568_32 | FAIL | PASS 126,020 | FAIL (32 of 32) | FAIL | PASS 125,980 | PASS 169,300 | PASS 125,980 | PASS 169,300 |
| d4_gemm3136_10 | FAIL | FAIL (10 of 10) | FAIL (10 of 10) | FAIL (10 of 10) | PASS 117,320 | PASS 150,320 | PASS 117,320 | PASS 150,320 |
| d5_gemm64_40 | FAIL | FAIL (30 of 40) | FAIL (40 of 40) | FAIL (40 of 40) | PASS 15,440 | PASS 17,920 | PASS 15,440 | PASS 17,920 |
| d6_mlp | n/a | n/a | n/a | n/a | PASS 28,990 | PASS 29,870 | PASS 28,990 | PASS 29,870 |
| d7_upfc8 | FAIL (iact buffer) | PASS 45,540 | FAIL (iact buffer) | FAIL (iact buffer) | PASS 41,550 | PASS 43,750 | PASS 41,550 | PASS 43,750 |
| d8_upfc14 | FAIL (iact buffer) | PASS 431,380 | FAIL (iact buffer) | FAIL (iact buffer) | PASS 381,510 | PASS 413,560 | PASS 381,510 | PASS 413,560 |
| d9_convdense | FAIL (10 of 10) | PASS 42,710 | FAIL (iact buffer) | FAIL (iact buffer) | PASS 40,020 | PASS 43,650 | PASS 40,020 | PASS 43,650 |
| d10_mnist | FAIL (10 of 10) | PASS 548,010 | FAIL (iact buffer) | FAIL (iact buffer) | PASS 421,000 | PASS 442,720 | PASS 421,000 | PASS 442,720 |
| d5d_gemm64_40_dbg |  | FAIL (30 of 40) |  |  |  |  |  |  |
| d6b_mlp2 | FAIL (iact buffer) | FAIL (iact buffer) | FAIL (iact buffer) | FAIL (iact buffer) |  |  |  |  |

Per tree (cases that ran): `up_old` dense 8 / 23, `up_new` dense **16 / 26**, `up_old` sparse 0 / 10, `up_new` sparse
**0 / 23**, `dev` dense **21 / 23**, `dev` sparse **21 / 23** (+ the K cases), `dev_p1` 21 / 23 in both modes.

* **What `12340ab` fixes upstream:** in their dense mode every FC path that was wrong before now passes: GEMM 64 → 10,
  256 → 32, 1568 → 32 (before: X in the output), Conv → MaxPool → Flatten → Dense (8 × 8 and 14 × 14 × 16), Conv →
  Flatten → Dense, the 6-layer MNIST net. Conv results are unchanged (13 / 13 identical verdicts and ns).
* **What it does not fix upstream:** GEMM 3136 → 10 still fails: bug #19 part 2, measured at the boundary, K 2046 PASS,
  K 2050 FAIL (`k3`, `k4`); `fc_size_reg` at 20 bits does not help while `current_x` is 12-bit signed. GEMM 64 → 40 fails
  30 / 40, the #21 pattern: with `LOGGER_LEVEL=10` (`d5d`) the RTL stream is byte for byte upstream's reference stream
  (40 / 40 words, 40 / 40 right with the pass / address / column decoding), so upstream has the same testbench bug the
  fork fixed this morning. Dense → Dense (`MLP`) fails the iact buffer check after layer 0 in both upstream trees (bug
  #26, fixed in the fork 2026-10-24). Sparse: 0 / 23, as before.
* **`dev`:** every case that upstream now passes was already right in `dev`, in both modes, and faster wherever both
  pass (bias once per filter, 2026-11-17): MNIST 421,000 vs 548,010 ns (−23 %), Conv 28 × 28 × 1 → 32 259,790 vs 376,210
  (−31 %), Conv → MaxPool → Flatten → Dense 14 × 14 × 16 381,510 vs 431,380 (−12 %), GEMM equal within 0.4 %. The only
  `dev` failures are the known 3-channel (#7) and 6-channel (#45) cases.
* **`dev_p1` = `dev` in all 46 runs, to the ns.**

### 3b. Dense input size: a limit of `dev` found on the way (bug #50, new)

| Tree | K | Result |
|---|---:|---|
| `dev` sparse | 4000 | PASS 189,080 ns |
| `dev` sparse | 4088 | PASS 192,300 ns |
| `dev` sparse | 4094 | PASS 192,340 ns |
| `dev` sparse | 4096 | **FAIL, 10 of 10 outputs** |
| `dev` sparse | 4200 | **FAIL, 10 of 10 outputs** |
| `up_new` dense | 2046 / 2050 | PASS / FAIL (#19, upstream only) |

Dense K → 10 at CR 2 × CC 2. From K = 4096 every output of `dev` is wrong and no toolchain check fires: the FC sweep
counts activations in the 12-bit `current_x` (`OpenEye_FPGA.v:1420`, `+2` per word, compared unsigned with
`fc_size_reg`), which wraps at 4096. (The 12-bit `iact_size_c` also overflows from K 4033 on, since it carries K
rounded up to 72, but `dev`'s constructor does not read `fc_storage_valid`, and K 4088 / 4094 pass.) A Flatten of
8 × 8 × 64 is exactly 4096 inputs. Fix options (not done, need approval): a Python check refusing FC input ≥ 4096
(`check_dense_readout` style, immediate), or widen `current_x` to the 20 bits of the new upstream `fc_size_reg` (RTL).

## 4. The converter change on `dev`: dead at 2 cluster columns, a real fix at 1 column (bug #51, new)

The branch can only act when, at the end of a row sweep, `iact_converter_x + iact_x_per_cluster >= iact_x_add_up`, there
are several kernel groups and `iact_x_per_cluster < iact_x_add_up`. Static scan of dev's `LayerParameters`
(8,208 conv layers: widths 4–28, heights 2–14, 1–32 channels, 2–64 filters, CR 1 / 2 / 4 / 8, `NUM_GLB_PSUM` 2 / 4;
the converter x sequence simulated from the registers):

* **2 cluster columns** (every configuration of the fork): 2,328 layers have several kernel groups, 7,884 row ends, the
  two conditions are never true together (the sweep steps 2 tiles, so either a row ends on a full pair or one tile is the
  whole row): **0 layers**. Matches the 46 identical runs above.
* **1 cluster column**: the first condition is always true at a row end, so the branch fires in **1,104 layers** (CR 4
  and CR 8 with `NUM_GLB_PSUM` 4; e.g. 4 × 4 × 4 → 8: `iact_x_per_cluster` 4, `iact_x_add_up` 8, 2 kernel groups): the
  second kernel group starts at x = 4 instead of 0.

On the RTL (`up_run_cc.py`, CC 1, sparse, `run1_cc.sh`):

| Layer (CR 4, `NUM_GLB_PSUM` 4, CC 1) | `dev` | `dev_p1` |
|---|---|---|
| 4 × 4 × 4 → 8 | **FAIL, 4 of 8 feature maps** | PASS 15,850 ns |
| 6 × 2 × 1 → 16 | **FAIL, 8 of 16 feature maps** | PASS 11,490 ns |
| 4 × 8 × 16 → 8 | **FAIL, 4 of 8 feature maps** | PASS 58,200 ns |
| controls, CR 2, CC 1 (branch does not act): 8 × 4 × 4 → 16, 4 × 4 × 4 → 8 | PASS 21,650 / 14,250 ns | |

Half of the feature maps (the second kernel group) are wrong in `dev`; without the branch they are right, with the same
cycle count. So the change is the one useful part of `12340ab` for the fork: a correct fix for kernel groups at one
cluster column, a no-op at two. Conv-side RTL tests of `dev` on `dev_p1` (`dev_p1_subset.sh`: `test_conv_const` 36, `test_glb_psum2` 7, `test_pooling` 4,
`test_stride` 12, `test_bias_per_filter` 12, `test_bug49` 2, `test_int8_clamp` 9, `test_mnist_layers` mapping and random
data 20, `test_real_model[0]`): **103 = 101 PASS + 2 known xfail** (3 channels, #7), as on `dev`; the two trained-MNIST
tests were first skipped (the checkpoints are untracked), then PASS with `doc/demo_notebooks/*.pth` copied in
(`seeded.sh`). Simulated time against `dev`'s regression of 2026-11-21 (`compare_ns.py`): equal in 95 tests; the other
6 (`test_random_data` ×5, `test_conv_bias_order[2_kernels]`) use unseeded random data, and with `OPENEYE_SEED=1` on both
trees they are equal to the ns too (`seeded/`); the two trained-MNIST runs are equal to the ns.

## 5. Decision (nothing taken; proposals need approval)

**Do not merge or cherry-pick `12340ab` as a whole.** Most of it serves upstream's own 2-channel dense flow, which the
fork did not take (`9594bec` .. `3e2e027`, sparse 0 / 23): `fill_dram_with_ref` in 2-channel order would break `dev`'s
4-channel buffer check, `iact_read_inc_2 = 0` belongs to the renumbered read loops of `7465852`, the FC `/ 2` and the
unsigned port are already in `dev` (since the fork base), and `fc_size_reg` at 20 bits changes nothing while the FC
counter is 12 bits wide. Every FC case this commit fixes upstream was already right in `dev`, in both modes.

| Part | For `dev` | Proposal |
|---|---|---|
| Converter branch removed (`OpenEye_FPGA.v`, 3 lines) | **Fixes new bug #51**: conv with several kernel groups at `CLUSTER_COLUMNS = 1` (CR 4 / 8, `NUM_GLB_PSUM` 4: 1,104 of 8,208 scanned layers) computes the second kernel group from the wrong x, half the feature maps wrong. Dead code at 2 cluster columns (0 layers; 46 runs and the conv-side tests identical) | Take these 3 lines only (RTL, needs approval); add a CC 1 conv test (the 3 cases of section 4 + controls) to the regression; lint, regression, Vivado (a few LUT less expected) |
| `fc_size_reg` 20 bit | Useless alone | Instead fix **bug #50** (Dense K ≥ 4096 silently wrong): first a Python check refusing FC input ≥ 4096 (no RTL), later, if large FC layers are needed, widen `current_x` together with `fc_size_reg` (RTL) |
| FC `/ 2`, unsigned port | Already in `dev` | — |
| `iact_read_inc_2 = 0`, `fill_dram_with_ref` 2-channel | Other loop / buffer layout | Do not take |
| `FC` model, VGG-19 cut, `test_single_layers.py` sweep | Test only | Idea: the fork has no conv test at `CLUSTER_COLUMNS = 1` (#51 went unseen); a CC 1 / 2 × CR 1–8 sweep like theirs is worth adding |

Upstream still has #19 (K ≥ 2048), the #21 testbench decoder, the Dense → Dense write-back of #26, and no working sparse
mode. Next review: whether upstream widens `current_x` (their `fc_size_reg` change suggests large FC inputs are next).

## 6. How to rerun

Worktrees (scratch, removed after the review): `git worktree add --detach <dir>/up_old 3e2e027`, `up_new 12340ab`,
`dev_fc dev`, `dev_p1 dev`; in each, `UP_FC` (and `Conv_Dense` upstream) added before `case "MNIST":` of
`src/open_eye/data_create.py`; in `dev_p1` the three lines of the converter branch commented out. Then, from the
repository root: in `jobs*.txt` replace `<worktrees>` with the worktree directory (and `<repo>` in `seeded/` with the repository); `all.sh` (matrix, about 2.5 hours at 8 processes;
the subset step there had a path bug, rerun as below), `dev_p1_subset.sh <dev_p1> <out>` (103 tests, about 50 min),
`seeded.sh <dev_p1> <out>`, `run1_cc.sh` with `jobs_cc*.txt` (CC 1), `run1.sh` with `jobs_k*.txt` (FC input size),
`table.py`, `compare_ns.py`; the scan of section 4: `venv/bin/python branch_scan.py` and `SCAN_CC=1 venv/bin/python branch_scan.py`
(Python only, about 2 minutes each).
