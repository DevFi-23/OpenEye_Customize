# 2026-11-17: the Table 2 network of the OpenEye paper, sparse against dense hardware

Question: run the network of Table 2 of the paper (arXiv 2606.01450: 28 x 28 x 1, Conv 16, MaxPool, Conv 32, MaxPool,
Conv 32, Dense 1568 -> 32, Dense 32 -> 10) on the 16 configurations of its Table 3 in both hardware modes and see the
difference. No RTL or toolchain Python changed; only runs (`dev` = `f435068`, the sparse Table 3 baseline was checked
identical on this RTL on 2026-11-10).

## Runs

| Run | Data | Mode | Result | Profiles |
|---|---|---|---|---|
| Table 3 (existing baseline) | `PAPER_MNIST`, no activation, random weights with real zeros, random input | sparse | 16 / 16 PASS | `doc/perf/paper_table3_2026-11-04` |
| Table 3 dense | same | dense (`SPARSITY_EN=0`) | **16 / 16 PASS** | `doc/perf/paper_table3_2026-11-17_dense` (+ `.md`) |
| ReLU sparse | `PAPER_MNIST_RELU`: ReLU after every layer but the last, otherwise as Table 3 | sparse | **14 / 16 PASS**, CR 2 X 2 Y 3 / Y 4 FAIL (new bug #49) | `doc/perf/paper_table3_2026-11-17_relu_sparse` (+ `.md`) |
| ReLU dense | same | dense | **16 / 16 PASS** | `doc/perf/paper_table3_2026-11-17_relu_dense` (+ `.md`) |

Commands (repository root):

```bash
SPARSITY_EN=0 venv/bin/python tools/paper_table3.py --run --jobs 6 --save doc/perf/paper_table3_2026-11-17_dense --report doc/perf/paper_table3_2026-11-17_dense.md
venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/run_relu.py doc/perf/paper_table3_2026-11-17_relu_sparse 6
SPARSITY_EN=0 venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/run_relu.py doc/perf/paper_table3_2026-11-17_relu_dense 6
venv/bin/python tools/paper_table3.py doc/perf/paper_table3_2026-11-17_relu_sparse --report doc/perf/paper_table3_2026-11-17_relu_sparse.md
venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/compare.py doc/perf/paper_table3_2026-11-04 doc/perf/paper_table3_2026-11-17_dense
venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/compare.py doc/perf/paper_table3_2026-11-17_relu_sparse doc/perf/paper_table3_2026-11-17_relu_dense
```

`test_paper_relu.py` is `test_profile.py::test_profile_paper` with the layer taken from `P_LAYER` (default
`PAPER_MNIST_RELU`); `run_relu.py` runs it like `paper_table3.py --run` (about 45 min for 16 cases, 6 in parallel).
Wall time per case: 4-25 min.

## Summary

| | sparse | dense | dense − sparse |
|---|---:|---:|---:|
| No activation (Table 3 data), sum of 16 configurations (ns) | 8,807,505 | 8,245,555 | **−6.4 %** (−2.3 to −11.5 % per configuration) |
| ReLU, sum of 16 configurations | 8,475,300 | 8,245,555 | **−2.7 %** (+3.5 to −10.3 %) |
| ReLU, the 14 configurations both pass | 7,153,905 | 6,952,565 | −2.8 % |
| Ratio to the paper's Total, no activation | 1.97-3.52 | 1.75-3.42 | |
| Ratio to the paper's Total, ReLU | 1.95-3.31 | 1.75-3.42 | |

* Dense is data-independent: the ReLU and the plain dense runs have the same cycle count in every configuration.
* Dense always loads weights faster: `load_wght` −33 to −35 % (16-bit instead of 24-bit weight transfers), most of it
  in the Dense 1568 -> 32 layer (164,736 -> 108,416 cycles summed over the configurations).
* Sparse computes faster where the layer input has zeros. With ReLU, summed over the configurations: Conv3 (53 % input
  zeros) compute 212,153 sparse against 261,568 dense (−19 %), Dense 1568 -> 32 (85 %) 40,358 against 59,108 (−32 %);
  Conv2 (11 %: max pooling keeps few zeros) is equal; Conv1 (image, 0 %) dense −3 %. Without an activation the inputs
  have 4-11 % zeros (quantized small values) and the compute of both modes is within ±3 %.
* Which wins depends on the share of compute: CR 1 X 2 (compute about 75 % of the time) sparse is 3.4-3.5 % faster with
  ReLU; CR 1 X 4 equal (+0.7 %); from CR 2 on dense wins (−2 to −10 %), because more clusters shorten the compute and
  the weight load stays.
* Neither mode closes the gap to the paper (1.75-3.42 x): at CR 1 the compute dominates, at CR 8 the weight load and the
  bias load (5-19 %, see `2026-11-17_bias_per_filter.md`).
* Area (Vivado, baseline configuration, 2026-11-10): dense 43,5k LUT against sparse 59,5k (−26.9 %).

## New bug #49 (sparse, found here, not investigated)

`PAPER_MNIST_RELU` on sparse hardware at CLUSTER_ROWS 2, NUM_GLB_PSUM 2 (Y 3 and Y 4): Conv2 (14 x 14 x 16 -> 32, ReLU)
writes the iact buffer correctly, the max pooling after it (14 x 14 x 32 -> 7 x 7 x 32) does not: 188 of 196 buffer
words match, the other 8 have single bytes wrong (reference 5, chip 7; 0 and 4; 5 and 4), so the next layers and the
result are wrong. The same configurations pass without the ReLU and in dense mode; every other configuration passes
with the ReLU. The first pooling (28 x 28 x 16) passes. Log of CR 2 X 2 Y 4:
`2026-11-17_paper_dense_sparse/fail_logs_sparse_relu/` (the CR 2 X 2 Y 3 log was overwritten by the dense run).
Reproduce: `venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/run_relu.py <dir> 1 -k paper_cr2_x2_y4`.

## Tables

### No activation (Table 3 data): sparse `paper_table3_2026-11-04`, dense `paper_table3_2026-11-17_dense`

ns at 200 MHz. Phase columns: dense minus sparse, ns.

| CR | X | Y | status sparse / dense | sparse | dense | dense − sparse | paper Total | sparse / paper | dense / paper | load_iact | load_wght | load_bias | convert_iact | compute | writeback | pooling | readout |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 3 | PASS / PASS | 1.052.385 | 1.024.050 | -2,7 % | 299.315 | 3,52 | 3,42 | 0 | -32.940 | 0 | 0 | 4.605 | 0 | 0 | 0 |
| 2 | 2 | 3 | PASS / PASS | 684.975 | 641.765 | -6,3 % | 231.265 | 2,96 | 2,78 | 0 | -44.580 | 0 | 0 | 1.370 | 0 | 0 | 0 |
| 4 | 2 | 3 | PASS / PASS | 490.610 | 451.695 | -7,9 % | 202.710 | 2,42 | 2,23 | 0 | -39.420 | 0 | 0 | 505 | 0 | 0 | 0 |
| 8 | 2 | 3 | PASS / PASS | 399.025 | 357.495 | -10,4 % | 177.520 | 2,25 | 2,01 | 0 | -41.220 | 0 | 0 | -310 | 0 | 0 | 0 |
| 1 | 4 | 3 | PASS / PASS | 664.990 | 633.630 | -4,7 % | 199.230 | 3,34 | 3,18 | 0 | -32.940 | 0 | 0 | 1.580 | 0 | 0 | 0 |
| 2 | 4 | 3 | PASS / PASS | 446.315 | 409.885 | -8,2 % | 154.005 | 2,90 | 2,66 | 0 | -36.900 | 0 | 0 | 470 | 0 | 0 | 0 |
| 4 | 4 | 3 | PASS / PASS | 340.485 | 312.065 | -8,3 % | 128.010 | 2,66 | 2,44 | 0 | -27.900 | 0 | 0 | -520 | 0 | 0 | 0 |
| 8 | 4 | 3 | PASS / PASS | 312.930 | 282.020 | -9,9 % | 115.340 | 2,71 | 2,45 | 0 | -29.340 | 0 | 0 | -1.570 | 0 | 0 | 0 |
| 1 | 2 | 4 | PASS / PASS | 1.028.660 | 1.005.340 | -2,3 % | 306.095 | 3,36 | 3,28 | 0 | -27.600 | 0 | 0 | 4.280 | 0 | 0 | 0 |
| 2 | 2 | 4 | PASS / PASS | 689.530 | 651.225 | -5,6 % | 252.680 | 2,73 | 2,58 | 0 | -39.720 | 0 | 0 | 1.415 | 0 | 0 | 0 |
| 4 | 2 | 4 | PASS / PASS | 517.250 | 469.365 | -9,3 % | 232.535 | 2,22 | 2,02 | 0 | -48.600 | 0 | 0 | 715 | 0 | 0 | 0 |
| 8 | 2 | 4 | PASS / PASS | 418.455 | 370.210 | -11,5 % | 211.880 | 1,97 | 1,75 | 0 | -47.920 | 0 | 0 | -325 | 0 | 0 | 0 |
| 1 | 4 | 4 | PASS / PASS | 640.005 | 613.660 | -4,1 % | 205.105 | 3,12 | 2,99 | 0 | -27.600 | 0 | 0 | 1.255 | 0 | 0 | 0 |
| 2 | 4 | 4 | PASS / PASS | 446.190 | 414.665 | -7,1 % | 167.460 | 2,66 | 2,48 | 0 | -32.040 | 0 | 0 | 515 | 0 | 0 | 0 |
| 4 | 4 | 4 | PASS / PASS | 355.185 | 321.635 | -9,4 % | 142.365 | 2,49 | 2,26 | 0 | -33.240 | 0 | 0 | -310 | 0 | 0 | 0 |
| 8 | 4 | 4 | PASS / PASS | 320.515 | 286.850 | -10,5 % | 129.165 | 2,48 | 2,22 | 0 | -32.080 | 0 | 0 | -1.585 | 0 | 0 | 0 |
| | | | sum | 8.807.505 | 8.245.555 | -6,4 % | | | |  |  |  |  |  |  |  |  |

#### Per layer, summed over the configurations (cycles)

| # | layer | input zeros (sparse run) | sparse | dense | dense − sparse | load_wght s / d | compute s / d |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Convolution2D 28x28x1 -> 16 | 0,0 % | 326.827 | 322.619 | -1,3 % | 3.336 / 2.208 | 106.248 / 103.168 |
| 1 | Pooling 28x28x16 | 6,9 % | 41.891 | 41.891 | +0,0 % | 0 / 0 | 0 / 0 |
| 2 | Convolution2D 14x14x16 -> 32 | 4,5 % | 721.639 | 696.587 | -3,5 % | 74.496 / 49.152 | 506.356 / 506.648 |
| 3 | Pooling 14x14x32 | 7,3 % | 23.075 | 23.075 | +0,0 % | 0 / 0 | 0 / 0 |
| 4 | Convolution2D 7x7x32 -> 32 | 8,7 % | 399.379 | 373.699 | -6,4 % | 92.160 / 60.672 | 255.760 / 261.568 |
| 5 | Dense 1568x1x1 -> 32 | 10,7 % | 242.081 | 185.159 | -23,5 % | 164.736 / 108.416 | 59.710 / 59.108 |
| 6 | Dense 32x1x1 -> 10 | 6,2 % | 6.609 | 6.081 | -8,0 % | 1.548 / 1.020 | 2.506 / 2.506 |

### ReLU: sparse `paper_table3_2026-11-17_relu_sparse`, dense `paper_table3_2026-11-17_relu_dense`

ns at 200 MHz. Phase columns: dense minus sparse, ns.

| CR | X | Y | status sparse / dense | sparse | dense | dense − sparse | paper Total | sparse / paper | dense / paper | load_iact | load_wght | load_bias | convert_iact | compute | writeback | pooling | readout |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 3 | PASS / PASS | 990.405 | 1.024.050 | +3,4 % | 299.315 | 3,31 | 3,42 | 0 | -32.940 | 0 | 0 | 66.585 | 0 | 0 | 0 |
| 2 | 2 | 3 | FAIL (iact after L3,4,5; result) / PASS | 657.220 | 641.765 | -2,4 % | 231.265 | 2,84 | 2,78 | 0 | -44.580 | 0 | 0 | 29.125 | 0 | 0 | 0 |
| 4 | 2 | 3 | PASS / PASS | 477.195 | 451.695 | -5,3 % | 202.710 | 2,35 | 2,23 | 0 | -39.420 | 0 | 0 | 13.920 | 0 | 0 | 0 |
| 8 | 2 | 3 | PASS / PASS | 392.435 | 357.495 | -8,9 % | 177.520 | 2,21 | 2,01 | 0 | -41.220 | 0 | 0 | 6.280 | 0 | 0 | 0 |
| 1 | 4 | 3 | PASS / PASS | 629.295 | 633.630 | +0,7 % | 199.230 | 3,16 | 3,18 | 0 | -32.940 | 0 | 0 | 37.275 | 0 | 0 | 0 |
| 2 | 4 | 3 | PASS / PASS | 428.925 | 409.885 | -4,4 % | 154.005 | 2,79 | 2,66 | 0 | -36.900 | 0 | 0 | 17.860 | 0 | 0 | 0 |
| 4 | 4 | 3 | PASS / PASS | 332.055 | 312.065 | -6,0 % | 128.010 | 2,59 | 2,44 | 0 | -27.900 | 0 | 0 | 7.910 | 0 | 0 | 0 |
| 8 | 4 | 3 | PASS / PASS | 309.035 | 282.020 | -8,7 % | 115.340 | 2,68 | 2,45 | 0 | -29.340 | 0 | 0 | 2.325 | 0 | 0 | 0 |
| 1 | 2 | 4 | PASS / PASS | 971.360 | 1.005.340 | +3,5 % | 306.095 | 3,17 | 3,28 | 0 | -27.600 | 0 | 0 | 61.580 | 0 | 0 | 0 |
| 2 | 2 | 4 | FAIL (iact after L3,4,5; result) / PASS | 664.175 | 651.225 | -1,9 % | 252.680 | 2,63 | 2,58 | 0 | -39.720 | 0 | 0 | 26.770 | 0 | 0 | 0 |
| 4 | 2 | 4 | PASS / PASS | 504.980 | 469.365 | -7,1 % | 232.535 | 2,17 | 2,02 | 0 | -48.600 | 0 | 0 | 12.985 | 0 | 0 | 0 |
| 8 | 2 | 4 | PASS / PASS | 412.695 | 370.210 | -10,3 % | 211.880 | 1,95 | 1,75 | 0 | -47.920 | 0 | 0 | 5.435 | 0 | 0 | 0 |
| 1 | 4 | 4 | PASS / PASS | 608.990 | 613.660 | +0,8 % | 205.105 | 2,97 | 2,99 | 0 | -27.600 | 0 | 0 | 32.270 | 0 | 0 | 0 |
| 2 | 4 | 4 | PASS / PASS | 431.200 | 414.665 | -3,8 % | 167.460 | 2,57 | 2,48 | 0 | -32.040 | 0 | 0 | 15.505 | 0 | 0 | 0 |
| 4 | 4 | 4 | PASS / PASS | 347.900 | 321.635 | -7,5 % | 142.365 | 2,44 | 2,26 | 0 | -33.240 | 0 | 0 | 6.975 | 0 | 0 | 0 |
| 8 | 4 | 4 | PASS / PASS | 317.435 | 286.850 | -9,6 % | 129.165 | 2,46 | 2,22 | 0 | -32.080 | 0 | 0 | 1.495 | 0 | 0 | 0 |
| | | | sum | 8.475.300 | 8.245.555 | -2,7 % | | | |  |  |  |  |  |  |  |  |

#### Per layer, summed over the configurations (cycles)

| # | layer | input zeros (sparse run) | sparse | dense | dense − sparse | load_wght s / d | compute s / d |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Convolution2D 28x28x1 -> 16 | 0,0 % | 326.827 | 322.619 | -1,3 % | 3.336 / 2.208 | 106.248 / 103.168 |
| 1 | Pooling 28x28x16 | 57,1 % | 41.891 | 41.891 | +0,0 % | 0 / 0 | 0 / 0 |
| 2 | Convolution2D 14x14x16 -> 32 | 10,7 % | 718.165 | 696.587 | -3,0 % | 74.496 / 49.152 | 502.882 / 506.648 |
| 3 | Pooling 14x14x32 | 75,5 % | 23.075 | 23.075 | +0,0 % | 0 / 0 | 0 / 0 |
| 4 | Convolution2D 7x7x32 -> 32 | 53,3 % | 355.772 | 373.699 | +5,0 % | 92.160 / 60.672 | 212.153 / 261.568 |
| 5 | Dense 1568x1x1 -> 32 | 85,4 % | 222.729 | 185.159 | -16,9 % | 164.736 / 108.416 | 40.358 / 59.108 |
| 6 | Dense 32x1x1 -> 10 | 68,8 % | 6.601 | 6.081 | -7,9 % | 1.548 / 1.020 | 2.498 / 2.506 |
