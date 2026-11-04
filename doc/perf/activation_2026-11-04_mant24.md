# 2026-11-04: the trained activation models with 24-bit requantization mantissas (after bug #38)

The four `trained_<activation>_img0` cases of `activation_2026-11-02.md`, measured again after the fix of bug #38
(`doc/experiments/2026-11-04_bug38_mantissa.md`): the toolchain now gives every Conv/Dense a 24-bit mantissa (was 8 bit),
the Leaky ReLU negative slope keeps 8 bits. Same platform (MNIST_REAL, 2x2 clusters, DMA 64 bit, QUANT_AMOUNT 64, ideal
memory), `test_real_model.py::test_real_model[0]` and `::test_real_model_activation[<activation>-0]` with
`OPENEYE_PROFILE=1`; all four PASS, every buffer check and the Dense psums bit-exact, DUT class 7.

| Model, image 0 | 8-bit mantissa (2026-11-02) | 24-bit mantissa | Change | Against ReLU (24 bit) |
|---|---:|---:|---:|---:|
| ReLU | 218,925 | 218,924 | -1 (Dense) | |
| Leaky ReLU | 238,049 | 238,049 | 0 | +19,125 (+8.74 %) |
| SiLU | 240,229 | 240,230 | +1 (Dense) | +21,306 (+9.73 %) |
| hard-swish | 240,293 | 240,287 | -6 (Dense) | +21,363 (+9.76 %) |

Only `compute` of the Dense layer moves: a few rounded outputs of Conv3 change (the multiplier is now exact to < 1e-7
instead of up to 0.2 %), a few of them cross zero, and the PEs skip zeros. Every other phase, every DMA word and the
96 cycles of `load_act` are identical. Report below:
`venv/bin/python -m open_eye.profile_report --clock-mhz 250 --compare <dir> doc/perf/activation_2026-11-04_mant24`, `<dir>` = a
copy of only the four `trained_*_img0.json` of `activation_2026-11-02`.

## trained_hardswish_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 123 | 0 | 108 | 108 | 0 | 10 -> 10 |  |
| load_iact | 196 | 196 | 0 | 196 | 196 | 0 | 0 -> 0 |  |
| load_wght | 39120 | 39120 | 0 | 39120 | 39120 | 0 | 0 -> 0 |  |
| load_bias | 23308 | 23308 | 0 | 23308 | 23308 | 0 | 0 -> 0 |  |
| load_quant | 240 | 240 | 0 | 160 | 160 | 0 | 0 -> 0 |  |
| load_act | 96 | 96 | 0 | 96 | 96 | 0 | 0 -> 0 |  |
| convert_iact | 10376 | 10376 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 146920 | 146914 | -6 (-0.0%) | 0 | 0 | 0 | 0 -> 0 |  |
| writeback | 11948 | 11948 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| pooling | 7952 | 7952 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 14 | 14 | 0 | 12 | 12 | 0 | 0 -> 0 |  |
| **TOTAL** | 240293 | 240287 | -6 (-0.0%) | 63000 | 63000 | 0 | 10 -> 10 |  |

| # | layer | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | 33011 | 33011 | 0 | 15102 | 15102 | 0 |
| 1 | Pool 28x28x32 | 5213 | 5213 | 0 | 18 | 18 | 0 |
| 2 | Conv 14x14x32->64 k3x3 | 120490 | 120490 | 0 | 22618 | 22618 | 0 |
| 3 | Pool 14x14x64 | 2861 | 2861 | 0 | 18 | 18 | 0 |
| 4 | Conv 7x7x64->64 k3x3 | 64730 | 64730 | 0 | 17242 | 17242 | 0 |
| 5 | Dense 3136->10 | 13988 | 13982 | -6 (-0.0%) | 8002 | 8002 | 0 |

## trained_leaky_relu_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 123 | 0 | 108 | 108 | 0 | 10 -> 10 |  |
| load_iact | 196 | 196 | 0 | 196 | 196 | 0 | 0 -> 0 |  |
| load_wght | 39120 | 39120 | 0 | 39120 | 39120 | 0 | 0 -> 0 |  |
| load_bias | 23308 | 23308 | 0 | 23308 | 23308 | 0 | 0 -> 0 |  |
| load_quant | 240 | 240 | 0 | 160 | 160 | 0 | 0 -> 0 |  |
| convert_iact | 10376 | 10376 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 144772 | 144772 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| writeback | 11948 | 11948 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| pooling | 7952 | 7952 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 14 | 14 | 0 | 12 | 12 | 0 | 0 -> 0 |  |
| **TOTAL** | 238049 | 238049 | 0 | 62904 | 62904 | 0 | 10 -> 10 |  |

| # | layer | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | 32979 | 32979 | 0 | 15070 | 15070 | 0 |
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
| load_iact | 196 | 196 | 0 | 196 | 196 | 0 | 0 -> 0 |  |
| load_wght | 39120 | 39120 | 0 | 39120 | 39120 | 0 | 0 -> 0 |  |
| load_bias | 23308 | 23308 | 0 | 23308 | 23308 | 0 | 0 -> 0 |  |
| load_quant | 240 | 240 | 0 | 160 | 160 | 0 | 0 -> 0 |  |
| convert_iact | 10376 | 10376 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 125648 | 125647 | -1 (-0.0%) | 0 | 0 | 0 | 0 -> 0 |  |
| writeback | 11948 | 11948 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| pooling | 7952 | 7952 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 14 | 14 | 0 | 12 | 12 | 0 | 0 -> 0 |  |
| **TOTAL** | 218925 | 218924 | -1 (-0.0%) | 62904 | 62904 | 0 | 10 -> 10 |  |

| # | layer | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | 32979 | 32979 | 0 | 15070 | 15070 | 0 |
| 1 | Pool 28x28x32 | 5213 | 5213 | 0 | 18 | 18 | 0 |
| 2 | Conv 14x14x32->64 k3x3 | 112010 | 112010 | 0 | 22586 | 22586 | 0 |
| 3 | Pool 14x14x64 | 2861 | 2861 | 0 | 18 | 18 | 0 |
| 4 | Conv 7x7x64->64 k3x3 | 52754 | 52754 | 0 | 17210 | 17210 | 0 |
| 5 | Dense 3136->10 | 13108 | 13107 | -1 (-0.0%) | 8002 | 8002 | 0 |

## trained_silu_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 123 | 0 | 108 | 108 | 0 | 10 -> 10 |  |
| load_iact | 196 | 196 | 0 | 196 | 196 | 0 | 0 -> 0 |  |
| load_wght | 39120 | 39120 | 0 | 39120 | 39120 | 0 | 0 -> 0 |  |
| load_bias | 23308 | 23308 | 0 | 23308 | 23308 | 0 | 0 -> 0 |  |
| load_quant | 240 | 240 | 0 | 160 | 160 | 0 | 0 -> 0 |  |
| load_act | 96 | 96 | 0 | 96 | 96 | 0 | 0 -> 0 |  |
| convert_iact | 10376 | 10376 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 146856 | 146857 | +1 (+0.0%) | 0 | 0 | 0 | 0 -> 0 |  |
| writeback | 11948 | 11948 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| pooling | 7952 | 7952 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 14 | 14 | 0 | 12 | 12 | 0 | 0 -> 0 |  |
| **TOTAL** | 240229 | 240230 | +1 (+0.0%) | 63000 | 63000 | 0 | 10 -> 10 |  |

| # | layer | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | 33011 | 33011 | 0 | 15102 | 15102 | 0 |
| 1 | Pool 28x28x32 | 5213 | 5213 | 0 | 18 | 18 | 0 |
| 2 | Conv 14x14x32->64 k3x3 | 120221 | 120221 | 0 | 22618 | 22618 | 0 |
| 3 | Pool 14x14x64 | 2861 | 2861 | 0 | 18 | 18 | 0 |
| 4 | Conv 7x7x64->64 k3x3 | 64906 | 64906 | 0 | 17242 | 17242 | 0 |
| 5 | Dense 3136->10 | 14017 | 14018 | +1 (+0.0%) | 8002 | 8002 | 0 |

## Summary

| case | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---|---:|---:|---:|---:|---:|---:|
| trained_hardswish_img0 | 240293 | 240287 | -6 (-0.0%) | 63000 | 63000 | 0 |
| trained_leaky_relu_img0 | 238049 | 238049 | 0 | 62904 | 62904 | 0 |
| trained_relu_img0 | 218925 | 218924 | -1 (-0.0%) | 62904 | 62904 | 0 |
| trained_silu_img0 | 240229 | 240230 | +1 (+0.0%) | 63000 | 63000 | 0 |
