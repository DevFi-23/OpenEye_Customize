# 2026-11-04: the trained activation models after row O (bugs #37, #17, #39)

The four `trained_<activation>_img0` cases of `activation_2026-11-04_mant24.md` again, after the RTL fix of #17 (Conv1
runs with its one input channel, no longer padded to two) and the weight-set fix #39 it needed. Same platform and
tests (`test_real_model.py`, `OPENEYE_PROFILE=1`); all four PASS, bit-exact, DUT class 7.

| Model, image 0 | before (`activation_2026-11-04_mant24`) | after | change | against ReLU |
|---|---:|---:|---:|---:|
| ReLU | 218,924 | 218,564 (874.3 us) | -360 | |
| Leaky ReLU | 238,049 | 237,689 (950.8 us) | -360 | +19,125 (+8.75 %) |
| SiLU | 240,230 | 239,870 (959.5 us) | -360 | +21,306 (+9.75 %) |
| hard-swish | 240,287 | 239,927 (959.7 us) | -360 | +21,363 (+9.77 %) |

All of it in Conv1: `load_iact` -96 (the padding channel is no longer sent), `load_wght` -240 (one channel of weights),
`writeback` -24; `compute` unchanged (the PEs skipped the zero padding channel anyway). The zero share of the Conv1
input is 0 % now (it was 50 %: the padding channel). Every other layer is identical cycle for cycle. Report below:
`venv/bin/python -m open_eye.profile_report --clock-mhz 250 --compare doc/perf/activation_2026-11-04_mant24 doc/perf/activation_2026-11-04_rowO`.


## trained_hardswish_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 123 | 0 | 108 | 108 | 0 | 10 -> 10 |  |
| load_iact | 196 | 100 | -96 (-49.0%) | 196 | 100 | -96 (-49.0%) | 0 -> 0 |  |
| load_wght | 39120 | 38880 | -240 (-0.6%) | 39120 | 38880 | -240 (-0.6%) | 0 -> 0 |  |
| load_bias | 23308 | 23308 | 0 | 23308 | 23308 | 0 | 0 -> 0 |  |
| load_quant | 240 | 240 | 0 | 160 | 160 | 0 | 0 -> 0 |  |
| load_act | 96 | 96 | 0 | 96 | 96 | 0 | 0 -> 0 |  |
| convert_iact | 10376 | 10376 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 146914 | 146914 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| writeback | 11948 | 11924 | -24 (-0.2%) | 0 | 0 | 0 | 0 -> 0 |  |
| pooling | 7952 | 7952 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 14 | 14 | 0 | 12 | 12 | 0 | 0 -> 0 |  |
| **TOTAL** | 240287 | 239927 | -360 (-0.1%) | 63000 | 62664 | -336 (-0.5%) | 10 -> 10 |  |

| # | layer | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1->32 k3x3 | 33011 | 32651 | -360 (-1.1%) | 15102 | 14766 | -336 (-2.2%) |
| 1 | Pool 28x28x32 | 5213 | 5213 | 0 | 18 | 18 | 0 |
| 2 | Conv 14x14x32->64 k3x3 | 120490 | 120490 | 0 | 22618 | 22618 | 0 |
| 3 | Pool 14x14x64 | 2861 | 2861 | 0 | 18 | 18 | 0 |
| 4 | Conv 7x7x64->64 k3x3 | 64730 | 64730 | 0 | 17242 | 17242 | 0 |
| 5 | Dense 3136->10 | 13982 | 13982 | 0 | 8002 | 8002 | 0 |

## trained_leaky_relu_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 123 | 0 | 108 | 108 | 0 | 10 -> 10 |  |
| load_iact | 196 | 100 | -96 (-49.0%) | 196 | 100 | -96 (-49.0%) | 0 -> 0 |  |
| load_wght | 39120 | 38880 | -240 (-0.6%) | 39120 | 38880 | -240 (-0.6%) | 0 -> 0 |  |
| load_bias | 23308 | 23308 | 0 | 23308 | 23308 | 0 | 0 -> 0 |  |
| load_quant | 240 | 240 | 0 | 160 | 160 | 0 | 0 -> 0 |  |
| convert_iact | 10376 | 10376 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 144772 | 144772 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| writeback | 11948 | 11924 | -24 (-0.2%) | 0 | 0 | 0 | 0 -> 0 |  |
| pooling | 7952 | 7952 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 14 | 14 | 0 | 12 | 12 | 0 | 0 -> 0 |  |
| **TOTAL** | 238049 | 237689 | -360 (-0.2%) | 62904 | 62568 | -336 (-0.5%) | 10 -> 10 |  |

| # | layer | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1->32 k3x3 | 32979 | 32619 | -360 (-1.1%) | 15070 | 14734 | -336 (-2.2%) |
| 1 | Pool 28x28x32 | 5213 | 5213 | 0 | 18 | 18 | 0 |
| 2 | Conv 14x14x32->64 k3x3 | 118928 | 118928 | 0 | 22586 | 22586 | 0 |
| 3 | Pool 14x14x64 | 2861 | 2861 | 0 | 18 | 18 | 0 |
| 4 | Conv 7x7x64->64 k3x3 | 64138 | 64138 | 0 | 17210 | 17210 | 0 |
| 5 | Dense 3136->10 | 13930 | 13930 | 0 | 8002 | 8002 | 0 |

## trained_relu_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 123 | 0 | 108 | 108 | 0 | 10 -> 10 |  |
| load_iact | 196 | 100 | -96 (-49.0%) | 196 | 100 | -96 (-49.0%) | 0 -> 0 |  |
| load_wght | 39120 | 38880 | -240 (-0.6%) | 39120 | 38880 | -240 (-0.6%) | 0 -> 0 |  |
| load_bias | 23308 | 23308 | 0 | 23308 | 23308 | 0 | 0 -> 0 |  |
| load_quant | 240 | 240 | 0 | 160 | 160 | 0 | 0 -> 0 |  |
| convert_iact | 10376 | 10376 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 125647 | 125647 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| writeback | 11948 | 11924 | -24 (-0.2%) | 0 | 0 | 0 | 0 -> 0 |  |
| pooling | 7952 | 7952 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 14 | 14 | 0 | 12 | 12 | 0 | 0 -> 0 |  |
| **TOTAL** | 218924 | 218564 | -360 (-0.2%) | 62904 | 62568 | -336 (-0.5%) | 10 -> 10 |  |

| # | layer | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1->32 k3x3 | 32979 | 32619 | -360 (-1.1%) | 15070 | 14734 | -336 (-2.2%) |
| 1 | Pool 28x28x32 | 5213 | 5213 | 0 | 18 | 18 | 0 |
| 2 | Conv 14x14x32->64 k3x3 | 112010 | 112010 | 0 | 22586 | 22586 | 0 |
| 3 | Pool 14x14x64 | 2861 | 2861 | 0 | 18 | 18 | 0 |
| 4 | Conv 7x7x64->64 k3x3 | 52754 | 52754 | 0 | 17210 | 17210 | 0 |
| 5 | Dense 3136->10 | 13107 | 13107 | 0 | 8002 | 8002 | 0 |

## trained_silu_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 123 | 0 | 108 | 108 | 0 | 10 -> 10 |  |
| load_iact | 196 | 100 | -96 (-49.0%) | 196 | 100 | -96 (-49.0%) | 0 -> 0 |  |
| load_wght | 39120 | 38880 | -240 (-0.6%) | 39120 | 38880 | -240 (-0.6%) | 0 -> 0 |  |
| load_bias | 23308 | 23308 | 0 | 23308 | 23308 | 0 | 0 -> 0 |  |
| load_quant | 240 | 240 | 0 | 160 | 160 | 0 | 0 -> 0 |  |
| load_act | 96 | 96 | 0 | 96 | 96 | 0 | 0 -> 0 |  |
| convert_iact | 10376 | 10376 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 146857 | 146857 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| writeback | 11948 | 11924 | -24 (-0.2%) | 0 | 0 | 0 | 0 -> 0 |  |
| pooling | 7952 | 7952 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 14 | 14 | 0 | 12 | 12 | 0 | 0 -> 0 |  |
| **TOTAL** | 240230 | 239870 | -360 (-0.1%) | 63000 | 62664 | -336 (-0.5%) | 10 -> 10 |  |

| # | layer | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1->32 k3x3 | 33011 | 32651 | -360 (-1.1%) | 15102 | 14766 | -336 (-2.2%) |
| 1 | Pool 28x28x32 | 5213 | 5213 | 0 | 18 | 18 | 0 |
| 2 | Conv 14x14x32->64 k3x3 | 120221 | 120221 | 0 | 22618 | 22618 | 0 |
| 3 | Pool 14x14x64 | 2861 | 2861 | 0 | 18 | 18 | 0 |
| 4 | Conv 7x7x64->64 k3x3 | 64906 | 64906 | 0 | 17242 | 17242 | 0 |
| 5 | Dense 3136->10 | 14018 | 14018 | 0 | 8002 | 8002 | 0 |

## Summary

| case | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---|---:|---:|---:|---:|---:|---:|
| trained_hardswish_img0 | 240287 | 239927 | -360 (-0.1%) | 63000 | 62664 | -336 (-0.5%) |
| trained_leaky_relu_img0 | 238049 | 237689 | -360 (-0.2%) | 62904 | 62568 | -336 (-0.5%) |
| trained_relu_img0 | 218924 | 218564 | -360 (-0.2%) | 62904 | 62568 | -336 (-0.5%) |
| trained_silu_img0 | 240230 | 239870 | -360 (-0.1%) | 63000 | 62664 | -336 (-0.5%) |
