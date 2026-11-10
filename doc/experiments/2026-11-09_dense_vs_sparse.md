# 2026-11-09: dense (`SPARSITY_EN=0`) against sparse on the same model

Question: is the fork's sparse direction worse than upstream's dense one? Measured on the trained MNIST net (Conv 32,
MaxPool, Conv 64, MaxPool, Conv 64, Dense 3136 -> 10, image 0) with `test/cocotb_fpga/test_real_model.py::test_real_model[0]`,
`OPENEYE_PROFILE=1`, the same tree (`dev` = `2c09f81` plus the Python fix below), `SPARSITY_EN=1` and `SPARSITY_EN=0`
(dense also with `OPENEYE_KEEP_GOING=1`, so the run continues past wrong buffers).

## 1. Dense mode had never run on the fork; what was fixed, what is still wrong

**Python (fixed, `src/open_eye/wght_stream_mapper.py`):** the conv weight stream applied the column encoding of bug #22
(`conv_wght_encoding.encode_columns`, which is the sparse PE's format) and dropped all-zero packed words also in dense mode.
With `SPARSITY_EN=0` the mapper now returns the plain layout (every weight in its slot) and keeps zero words. After that,
single convolutions with 16 filters pass in dense (8x4 with 2 / 4 / 8 channels, 8x8 with `NUM_GLB_IACT` 3, 28x28x1 -> 32).
Sparse is unchanged (the code is behind `SPARSITY_EN`; the MNIST run below passes bit-exact as before).

**Still wrong in dense (RTL, not changed):**

| Case | Dense result | Upstream `b1e02a0` dense |
|---|---|---|
| Conv 8x4x4 -> 4 or 8x4x8 -> 8 (`used_psum_per_PE` = 4) | every map wrong, filters 2-3 of row 0 X | the same (X) |
| Conv 8x4x16 -> 16 | odd filters right, **every even filter X** (MAC 0 of each PE) | PASS |
| any of the above with `PARALLEL_MACS=1` | still wrong | |
| Conv -> Conv chains of the 13-case set | wrong (their first layer has 4 or 8 filters, the case above) | wrong |
| trained MNIST: Conv1 + Pool | **bit-exact** (buffer check 784 / 784 words) | |
| trained MNIST: Conv2 + Pool | 294 / 392 words right, the other 98 are `0x80` bytes (pooling saw no value) | |
| trained MNIST: Conv3 | no word written into the iact buffer (392 / 392 unwritten) | |
| trained MNIST: Dense | X in the output | |

`used_psum_per_PE` 4 against 8 is the only difference between the failing 8x4x4 -> 4 and the passing 8x4x4 -> 16
(`lp_diff.py`). The even / odd split of the 16-channel case points at the MAC 0 lane of the dense PE FSM (`PE.v`
`gen_dense_fsm`) or of its psum path; upstream has a `wght_filter <= 0` in `SEND_PSUM` of the dense FSM that the fork
lacks (from the depthwise rework), not yet tried. These are RTL bugs of a mode the fork has not used; fixing them needs
approval.

**2026-11-10:** causes found and a fix proposed, `2026-11-10_bug46_47.md` (#47: all-zero weight words dropped outside raw
mode; #46: no psum forwarding in the dense FSM). With the proposed patch in a temporary copy the whole MNIST net is
bit-exact in dense with the same 225,221 cycles as in section 2. Applied the same day (approved); the fixed dense build is 43,523 LUT
(`doc/synth/2026-11-10_route4ns_dense4647_zu7ev`), -26.9 % against sparse, as measured before the fix.

## 2. Cycles on the same model

The dense FSM does not look at the values (it multiplies everything), so its cycle count does not depend on whether the
values are right; only Conv1 + Pool1 are verified in dense. Dense per layer from `layer_starts` of its `profile.json` (the
run stopped at the X readout, so the per-layer phases were not closed), per phase from `pending` (whole run). Sparse
from the normal report (bit-exact, PASS). 250 MHz.

| Layer | input zeros | sparse | dense | dense - sparse |
|---|---:|---:|---:|---:|
| Conv 28x28x1 -> 32 (verified in both) | 0 % | 32,619 | 32,246 | -373 (-1.1 %) |
| Pool | | 5,213 | 5,213 | 0 |
| Conv 14x14x32 -> 64 | 43.5 % | 112,010 | 114,380 | +2,370 (+2.1 %) |
| Pool | | 2,861 | 2,861 | 0 |
| Conv 7x7x64 -> 64 | 87.3 % | 52,754 | 59,788 | +7,034 (+13.3 %) |
| Dense 3136 -> 10 | 74.3 % | 13,107 | 10,733 | -2,374 (-18.1 %) |
| **total** | | **218,564 (874 us)** | **225,221 (901 us)** | **+6,657 (+3.0 %)** |

By phase (whole model):

| Phase | sparse | dense | dense - sparse |
|---|---:|---:|---:|
| `load_wght` | 38,880 | 23,328 | **-15,552 (-40 %)** |
| `compute` | 125,647 | 147,856 | **+22,209 (+17.7 %)** |
| `load_bias`, `convert_iact`, `writeback`, `pooling`, `load_config`, `load_iact`, `load_quant` | 54,023 | 54,023 | 0 |

Compute per layer (layer total minus its other phases, which equal sparse except `load_wght`): Conv1 9,305 against 9,582
(-2.9 %, no zeros: the sparse format only costs), Conv2 89,556 against 81,042 (+10.5 %), Conv3 44,756 against 31,578
(+41.7 %), Dense 4,239 against 3,445 (+23.1 %). The same pattern as losing the zeros with Leaky ReLU in sparse mode
(section 6.15 of README_FI: Conv2 +8.5 %, Conv3 +36 %, Dense +24 %).

Weight words per layer, dense / sparse: 144 / 240, 9,216 / 15,360, 9,216 / 15,360, 4,752 / 7,920, every layer 3 / 5.
One weight row carries one transfer for each of the 12 weight routers (4 clusters x `NUM_GLB_WGHT` 3): 12 x 16 bits = 192
bits = 3 DMA words dense, 12 x 24 bits = 288 bits -> 5 words sparse (12-bit weights, 32 bits of padding). The trained
weights have 1-5 % zeros, so the sparse weight format is overhead almost only.

## 3. Reading

* Neither mode wins everywhere: sparse wins compute by the zeros of the activations (+17.7 % for dense on this net), dense
  wins weight loading by the 4 overhead bits per weight (-40 %). Net on MNIST: sparse 3.0 % faster. On a net without
  activation zeros (SiLU / hard-swish / GELU, image input) dense would win by about the weight-loading share.
* The two effects come from different operands: activations are sparse (ReLU), trained weights are not. A **mixed mode**
  (zero-skipping CSC for iacts, plain 8-bit weights) would take both: about 218,564 - 15,552 = 203,000 cycles (-7.1 %
  against sparse, -9.9 % against dense), estimate only; it needs RTL work in the weight pipeline / PE (weight address
  SPad and overhead field off, iact side unchanged) and is not started.
* Area (Vivado, the stride1 baseline configuration with `SPARSITY_EN=0`): section 4.
* Independent of the mode: `load_bias` is 23,308 cycles (10.7 %), 14,336 words for the 32 biases of Conv1 (44 % of
  that layer): the bias is sent as a full initial psum map (32 bits per output position) instead of one value per
  filter. A larger saving than either mode, also RTL work.

## 4. Area

Vivado 2024.2, xczu7ev, 4 ns, place and route, the hardware baseline configuration with only `SPARSITY_EN=0`
(`doc/synth/2026-11-09_route4ns_dense_zu7ev/SUMMARY.md`, against `doc/synth/2026-11-09_route4ns_stride1_zu7ev`):

| | sparse (baseline) | dense | dense - sparse |
|---|---:|---:|---:|
| CLB LUT post-route | 59,548 | 43,554 | **-15,994 (-26.9 %)** |
| FF post-route | 39,449 | 28,797 | **-10,652 (-27.0 %)** |
| Block RAM tile / URAM / DSP | 188 / 12 / 4 | 184 / 10 / 4 | -4 / -2 / 0 |
| WNS post-route (fmax) | +0.042 ns (~252.7 MHz) | +0.062 ns (~253.9 MHz) | same |

Each PE goes from about 1,000 to 620 LUT (-38 %): the sparse mode costs about a quarter of the chip for its address
SPads, overhead pipelines and zero-skipping control. The dense RTL is not correct yet (#46, #47); the fixes may add a
little logic. Clock: unchanged (the worst paths are in the top level and in reset routing, not in the PE).

So, per unit of area, on this MNIST net: dense is 3.0 % slower with 27 % fewer LUTs. If the saved area were spent on more
PEs (a fifth cluster does not fit the 2 x 2 grid; the next size up, e.g. `CLUSTER_ROWS` 3, is about +50 % PEs), dense
would come out ahead in cycles per area; with the area unused, sparse is the faster design on ReLU nets. The mixed mode of
section 3 would sit in between in area (weight address SPad and weight overhead path dropped, iact side kept).

## Files

* `2026-11-09_dense_vs_sparse/dense_diag.py`: which filter / channel subset a wrong output map was computed with
  (needs `OPENEYE_DUMP_VERIFY=1`; with `OPENEYE_X_CONTINUE=1` the testbench writes X words to `output.txt` instead of
  stopping at the first one and logs the `[f, x, y]` of each X psum as `XPOS`).
* `2026-11-09_dense_vs_sparse/lp_diff.py`: the `LayerParameters` fields that differ between two configurations.
* Runs: `SPARSITY_EN=0 OPENEYE_PROFILE=1 OPENEYE_KEEP_GOING=1 venv/bin/python -m pytest -q "test/cocotb_fpga/test_real_model.py::test_real_model[0]"`
  and the same with `SPARSITY_EN=1`; the profiles are in `doc/perf/dense_vs_sparse_2026-11-09/`. Small cases:
  `2026-10-31_upstream_review/up_run.py` with `SPARSITY_EN=0`.
