# 2026-11-02: profiles of the activation functions on the RTL (step C)

Profiler of step C (`doc/experiments/2026-11-02_activation_profiler.md`) on the RTL of step B (`f853b61`). Files
`activation_2026-11-02/*.json`, reports below from
`venv/bin/python -m open_eye.profile_report --clock-mhz 250 doc/perf/activation_2026-11-02/*.json`.

* `trained_<activation>_img0`: the trained MNIST models (ReLU = the original checkpoint, Leaky ReLU 0.1, SiLU,
  hard-swish; `doc/demo_notebooks/mnist_<activation>_model.pth`) on MNIST test image 0 through the toolchain, platform
  MNIST_REAL (2x2 clusters, DMA 64 bit, QUANT_AMOUNT 64), ideal memory; `test_real_model.py::test_real_model[0]` and
  `::test_real_model_activation[<activation>-0]` with `OPENEYE_PROFILE=1`. Every buffer check and the Dense psums
  bit-exact, DUT class 7 on all four.
* `act_table_*`: cases of `test_activation_rtl.py` (random models, `OPENEYE_SEED=1`) with `OPENEYE_PROFILE=1`: SiLU
  table on the Table 2 network of the paper, random table kept from layer to layer on an MLP (`keep`), random table at
  DMA 32 bit.

## Trained models, image 0: the cost of each activation against ReLU

| model | total cycles | vs ReLU | load_act | writeback | compute | other phases vs ReLU |
|---|---:|---:|---:|---:|---:|---:|
| trained_relu_img0 | 218,925 | +0 (+0.0%) | 0 | 11,948 | 125,648 | +0 |
| trained_leaky_relu_img0 | 238,049 | +19,124 (+8.7%) | 0 | 11,948 | 144,772 | +0 |
| trained_silu_img0 | 240,229 | +21,304 (+9.7%) | 96 | 11,948 | 146,856 | +0 |
| trained_hardswish_img0 | 240,293 | +21,368 (+9.8%) | 96 | 11,948 | 146,920 | +0 |

| model | layer | mode | input zeros | input neg | compute | compute vs ReLU | writeback | act clocks | load_act |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| trained_relu_img0 | Conv1 | relu | 50.0% | 43.4% | 9,582 | +0 (+0.0%) | 7,236 | 7,174 | 0 |
| trained_relu_img0 | Pool1 | none | 54.1% | 0.0% | 0 | +0 | 0 | 0 | 0 |
| trained_relu_img0 | Conv2 | relu | 43.5% | 0.0% | 81,042 | +0 (+0.0%) | 3,700 | 3,590 | 0 |
| trained_relu_img0 | Pool2 | none | 94.4% | 0.0% | 0 | +0 | 0 | 0 | 0 |
| trained_relu_img0 | Conv3 | relu | 87.3% | 0.0% | 31,578 | +0 (+0.0%) | 1,012 | 902 | 0 |
| trained_relu_img0 | Dense | none | 74.3% | 0.0% | 3,446 | +0 (+0.0%) | 0 | 0 | 0 |
| trained_leaky_relu_img0 | Conv1 | leaky+round | 50.0% | 43.4% | 9,582 | +0 (+0.0%) | 7,236 | 7,174 | 0 |
| trained_leaky_relu_img0 | Pool1 | none | 24.2% | 36.1% | 0 | +0 | 0 | 0 | 0 |
| trained_leaky_relu_img0 | Conv2 | leaky+round | 24.3% | 25.2% | 87,960 | +6,918 (+8.5%) | 3,700 | 3,590 | 0 |
| trained_leaky_relu_img0 | Pool2 | none | 9.0% | 83.5% | 0 | +0 | 0 | 0 | 0 |
| trained_leaky_relu_img0 | Conv3 | leaky+round | 14.7% | 68.7% | 42,962 | +11,384 (+36.1%) | 1,012 | 902 | 0 |
| trained_leaky_relu_img0 | Dense | none | 18.1% | 49.1% | 4,268 | +822 (+23.9%) | 0 | 0 | 0 |
| trained_silu_img0 | Conv1 | table+round | 50.0% | 43.4% | 9,582 | +0 (+0.0%) | 7,236 | 7,174 | 32 |
| trained_silu_img0 | Pool1 | none | 11.0% | 41.5% | 0 | +0 | 0 | 0 | 0 |
| trained_silu_img0 | Conv2 | table+round | 11.0% | 30.8% | 89,221 | +8,179 (+10.1%) | 3,700 | 3,590 | 32 |
| trained_silu_img0 | Pool2 | none | 3.9% | 82.4% | 0 | +0 | 0 | 0 | 0 |
| trained_silu_img0 | Conv3 | table+round | 7.2% | 65.3% | 43,698 | +12,120 (+38.4%) | 1,012 | 902 | 32 |
| trained_silu_img0 | Dense | none | 6.6% | 57.2% | 4,355 | +909 (+26.4%) | 0 | 0 | 0 |
| trained_hardswish_img0 | Conv1 | table+round | 50.0% | 43.4% | 9,582 | +0 (+0.0%) | 7,236 | 7,174 | 32 |
| trained_hardswish_img0 | Pool1 | none | 5.4% | 43.3% | 0 | +0 | 0 | 0 | 0 |
| trained_hardswish_img0 | Conv2 | table+round | 5.9% | 31.7% | 89,490 | +8,448 (+10.4%) | 3,700 | 3,590 | 32 |
| trained_hardswish_img0 | Pool2 | none | 8.6% | 75.5% | 0 | +0 | 0 | 0 | 0 |
| trained_hardswish_img0 | Conv3 | table+round | 14.3% | 55.2% | 43,522 | +11,944 (+37.8%) | 1,012 | 902 | 32 |
| trained_hardswish_img0 | Dense | none | 13.2% | 49.7% | 4,326 | +880 (+25.5%) | 0 | 0 | 0 |

* **The activation hardware costs 0 cycles per value**: `writeback` 11,948 cycles and the activation clocks (the
  clocks in which the write-back takes the activated lane values) are identical for the four functions; every phase
  but `compute` and `load_act` differs by 0 cycles and 0 DMA words.
* **The tables cost 32 cycles and 32 DMA words per layer** (`load_act`, 2048 bit / DMA 64 bit): 96 for the three
  Conv layers of SiLU and hard-swish (0.04 % of the model); Leaky ReLU 0.
* **The real cost is the zeros**: ReLU leaves 43.5 / 87.3 / 74.3 % zeros in the inputs of Conv2 / Conv3 / Dense, the
  others 6-24 / 7-15 / 7-18 %, so zero skipping skips less: compute +15.2 % (Leaky ReLU), +16.9 % (SiLU, hard-swish), the whole model +8.7 % (Leaky
  ReLU), +9.7 % (SiLU), +9.8 % (hard-swish). Step A predicted +7.4 / +9.2 / +9.0 % from the zero fractions of the
  10,000 test images (`doc/experiments/2026-11-02_activation.md`); its zero fractions (Leaky 23 / 15 / 17 %, SiLU
  10 / 7 / 7 %, hard-swish 7 / 14 / 13 %) agree with the ones measured here within 2 points.
* Conv1's input has 50 % zeros in every model: the zero channel added for bug #17 (the image channel has none, its
  background is -19).

## The same weights for every activation

The four trained models above have their own weights (each trained with its activation). To separate the activation
from the weights, the trained **ReLU** weights ran with each activation in place of ReLU (the toolchain calibrates the
new graph as usual; the weights were not trained for it, but the DUT still gives class 7 on image 0):
`same_weights_<activation>_img0.json`, from `doc/experiments/2026-11-02_activation/run_same_weights.py <activation> 0`.
All three PASS, bit-exact.

| model | total cycles | vs ReLU | load_act | writeback | compute | other phases vs ReLU |
|---|---:|---:|---:|---:|---:|---:|
| trained_relu_img0 | 218,925 | +0 (+0.0%) | 0 | 11,948 | 125,648 | +0 |
| same_weights_leaky_relu_img0 | 238,786 | +19,861 (+9.1%) | 0 | 11,948 | 145,509 | +0 |
| same_weights_silu_img0 | 240,728 | +21,803 (+10.0%) | 96 | 11,948 | 147,355 | +0 |
| same_weights_hardswish_img0 | 240,560 | +21,635 (+9.9%) | 96 | 11,948 | 147,187 | +0 |

| model | layer | mode | input zeros | input neg | compute | compute vs ReLU | writeback | act clocks | load_act |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| trained_relu_img0 | Conv1 | relu | 50.0% | 43.4% | 9,582 | +0 (+0.0%) | 7,236 | 7,174 | 0 |
| trained_relu_img0 | Pool1 | none | 54.1% | 0.0% | 0 | +0 | 0 | 0 | 0 |
| trained_relu_img0 | Conv2 | relu | 43.5% | 0.0% | 81,042 | +0 (+0.0%) | 3,700 | 3,590 | 0 |
| trained_relu_img0 | Pool2 | none | 94.4% | 0.0% | 0 | +0 | 0 | 0 | 0 |
| trained_relu_img0 | Conv3 | relu | 87.3% | 0.0% | 31,578 | +0 (+0.0%) | 1,012 | 902 | 0 |
| trained_relu_img0 | Dense | none | 74.3% | 0.0% | 3,446 | +0 (+0.0%) | 0 | 0 | 0 |
| same_weights_leaky_relu_img0 | Conv1 | leaky+round | 50.0% | 43.4% | 9,582 | +0 (+0.0%) | 7,236 | 7,174 | 0 |
| same_weights_leaky_relu_img0 | Pool1 | none | 8.2% | 41.2% | 0 | +0 | 0 | 0 | 0 |
| same_weights_leaky_relu_img0 | Conv2 | leaky+round | 7.5% | 30.8% | 89,202 | +8,160 (+10.1%) | 3,700 | 3,590 | 0 |
| same_weights_leaky_relu_img0 | Pool2 | none | 12.1% | 81.5% | 0 | +0 | 0 | 0 | 0 |
| same_weights_leaky_relu_img0 | Conv3 | leaky+round | 19.5% | 66.2% | 42,434 | +10,856 (+34.4%) | 1,012 | 902 | 0 |
| same_weights_leaky_relu_img0 | Dense | none | 13.7% | 46.0% | 4,291 | +845 (+24.5%) | 0 | 0 | 0 |
| same_weights_silu_img0 | Conv1 | table+round | 50.0% | 43.4% | 9,582 | +0 (+0.0%) | 7,236 | 7,174 | 32 |
| same_weights_silu_img0 | Pool1 | none | 5.1% | 48.3% | 0 | +0 | 0 | 0 | 0 |
| same_weights_silu_img0 | Conv2 | table+round | 5.1% | 37.5% | 89,743 | +8,701 (+10.7%) | 3,700 | 3,590 | 32 |
| same_weights_silu_img0 | Pool2 | none | 5.5% | 78.3% | 0 | +0 | 0 | 0 | 0 |
| same_weights_silu_img0 | Conv3 | table+round | 7.8% | 61.3% | 43,682 | +12,104 (+38.3%) | 1,012 | 902 | 32 |
| same_weights_silu_img0 | Dense | none | 7.3% | 52.0% | 4,348 | +902 (+26.2%) | 0 | 0 | 0 |
| same_weights_hardswish_img0 | Conv1 | table+round | 50.0% | 43.4% | 9,582 | +0 (+0.0%) | 7,236 | 7,174 | 32 |
| same_weights_hardswish_img0 | Pool1 | none | 5.2% | 48.2% | 0 | +0 | 0 | 0 | 0 |
| same_weights_hardswish_img0 | Conv2 | table+round | 5.3% | 37.3% | 89,743 | +8,701 (+10.7%) | 3,700 | 3,590 | 32 |
| same_weights_hardswish_img0 | Pool2 | none | 8.9% | 73.4% | 0 | +0 | 0 | 0 | 0 |
| same_weights_hardswish_img0 | Conv3 | table+round | 13.8% | 53.1% | 43,554 | +11,976 (+37.9%) | 1,012 | 902 | 32 |
| same_weights_hardswish_img0 | Dense | none | 14.0% | 45.2% | 4,308 | +862 (+25.0%) | 0 | 0 | 0 |

* Nearly the same costs as with the models' own weights: +9.1 % (Leaky ReLU), +10.0 % (SiLU), +9.9 % (hard-swish)
  against +8.7 / +9.7 / +9.8 %. The cost belongs to the activation (it keeps the negative values that ReLU sets to 0),
  not to the weights.
* Again `writeback` 11,948 and every phase but `compute` and `load_act` identical.

## Reports


## act_table_conv_stack_dma32
Convolution_Stack (2 layers) | 2x2 clusters, DMA 32 b, psum 20 b, QUANT_AMOUNT 32 | memory: ideal (legacy driver)
total 3032 cycles (30320 ns), compute 29.7%, DMA busy 47.6% of cycles, waiting for memory 0.1%

| phase | cycles | share | DMA in | DMA out | mem stall | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|
| load_config | 71 | 2.3% | 68 | 0 | 2 |  |  |
| load_iact | 32 | 1.1% | 32 | 0 | 0 |  |  |
| load_wght | 432 | 14.2% | 432 | 0 | 0 |  |  |
| load_bias | 512 | 16.9% | 512 | 0 | 0 |  |  |
| load_quant | 80 | 2.6% | 80 | 0 | 0 |  |  |
| load_act | 64 | 2.1% | 64 | 0 | 0 |  |  |
| convert_iact | 574 | 18.9% | 0 (2 refused) | 0 | 0 |  |  |
| compute | 901 | 29.7% | 0 | 0 | 0 |  |  |
| writeback | 108 | 3.6% | 0 | 0 | 0 |  |  |
| readout | 258 | 8.5% | 0 | 256 | 0 |  |  |

| # | layer | cycles | share | us (250 MHz) | load | load_wght | load_bias | convert_iact | compute | writeback | pooling | readout | DMA in | DMA out | bus eff. |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | Conv 8x4x4->4 k3x3 | 1472 | 48.5% | 5.9 | 170 | 216 | 256 | 287 | 435 | 108 | 0 | 0 | 642 | 0 | 23% |
| 1 | Conv 8x4x4->4 k3x3 | 1560 | 51.5% | 6.2 | 77 | 216 | 256 | 287 | 466 | 0 | 0 | 258 | 546 | 256 | 18% |

| # | layer | activation | load_act cycles | load_act DMA words | writeback cycles | activation clocks (in writeback) | input zeros | input negatives |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 8x4x4->4 k3x3 | table + round | 64 | 64 | 108 | 70 | 0.0% | 58.6% |
| 1 | Conv 8x4x4->4 k3x3 | none | 0 | 0 | 0 | 0 | 0.0% | 48.4% |

## act_table_keep_mlp
MLP (3 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32 | memory: ideal (legacy driver)
total 1153 cycles (11530 ns), compute 27.6%, DMA busy 36.9% of cycles, waiting for memory 0.3%

| phase | cycles | share | DMA in | DMA out | mem stall | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|
| load_config | 60 | 5.2% | 54 | 0 | 4 |  |  |
| load_iact | 4 | 0.3% | 4 | 0 | 0 |  |  |
| load_wght | 220 | 19.1% | 220 | 0 | 0 |  |  |
| load_bias | 52 | 4.5% | 52 | 0 | 0 |  |  |
| load_quant | 60 | 5.2% | 60 | 0 | 0 |  |  |
| load_act | 32 | 2.8% | 32 | 0 | 0 |  |  |
| convert_iact | 249 | 21.6% | 0 (3 refused) | 0 | 0 |  |  |
| compute | 318 | 27.6% | 0 | 0 | 0 |  |  |
| writeback | 152 | 13.2% | 0 | 0 | 0 |  |  |
| readout | 6 | 0.5% | 0 | 4 | 0 |  |  |

| # | layer | cycles | share | us (250 MHz) | load | load_wght | load_bias | convert_iact | compute | writeback | pooling | readout | DMA in | DMA out | bus eff. |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | Dense 6->32 | 435 | 37.7% | 1.7 | 74 | 80 | 32 | 77 | 102 | 70 | 0 | 0 | 186 | 0 | 53% |
| 1 | Dense 32->16 | 442 | 38.3% | 1.8 | 41 | 120 | 16 | 89 | 94 | 82 | 0 | 0 | 174 | 0 | 51% |
| 2 | Dense 16->4 | 276 | 23.9% | 1.1 | 41 | 20 | 4 | 83 | 122 | 0 | 0 | 6 | 62 | 4 | 28% |

| # | layer | activation | load_act cycles | load_act DMA words | writeback cycles | activation clocks (in writeback) | input zeros | input negatives |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | Dense 6->32 | table | 32 | 32 | 70 | 35 | 0.0% | 16.7% |
| 1 | Dense 32->16 | table (keep table) | 0 | 0 | 82 | 35 | 0.0% | 43.8% |
| 2 | Dense 16->4 | none | 0 | 0 | 0 | 0 | 0.0% | 37.5% |

## act_table_paper_network
PAPER_MNIST (7 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32 | memory: ideal (legacy driver)
total 88596 cycles (885960 ns), compute 46.9%, DMA busy 34.8% of cycles, waiting for memory 0.0%

| phase | cycles | share | DMA in | DMA out | mem stall | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|
| load_config | 144 | 0.2% | 126 | 0 | 12 |  |  |
| load_iact | 196 | 0.2% | 196 | 0 | 0 |  |  |
| load_wght | 18570 | 21.0% | 18570 | 0 | 0 |  |  |
| load_bias | 11692 | 13.2% | 11692 | 0 | 0 |  |  |
| load_quant | 140 | 0.2% | 100 (40 refused) | 0 | 0 |  |  |
| load_act | 128 | 0.1% | 128 | 0 | 0 |  |  |
| convert_iact | 5929 | 6.7% | 0 (5 refused) | 0 | 0 |  |  |
| compute | 41538 | 46.9% | 0 | 0 | 0 |  |  |
| writeback | 6269 | 7.1% | 0 | 0 | 0 |  |  |
| pooling | 3976 | 4.5% | 0 (2 refused) | 0 | 0 |  |  |
| readout | 14 | 0.0% | 0 | 12 | 0 |  |  |

| # | layer | cycles | share | us (250 MHz) | load | load_wght | load_bias | convert_iact | compute | writeback | pooling | readout | DMA in | DMA out | bus eff. |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->16 k3x3 | 17215 | 19.4% | 68.9 | 266 | 240 | 7168 | 1091 | 4798 | 3652 | 0 | 0 | 7674 | 0 | 2% |
| 1 | Pool 28x28x16 | 2617 | 3.0% | 10.5 | 41 | 0 | 0 | 0 | 0 | 0 | 2576 | 0 | 18 | 0 |  |
| 2 | Conv 14x14x16->32 k3x3 | 34117 | 38.5% | 136.5 | 73 | 3840 | 3584 | 2375 | 22337 | 1908 | 0 | 0 | 7494 | 0 | 9% |
| 3 | Pool 14x14x32 | 1441 | 1.6% | 5.8 | 41 | 0 | 0 | 0 | 0 | 0 | 1400 | 0 | 18 | 0 |  |
| 4 | Conv 7x7x32->32 k3x3 | 17401 | 19.6% | 69.6 | 73 | 3840 | 896 | 1511 | 10517 | 564 | 0 | 0 | 4806 | 0 | 25% |
| 5 | Dense 1568->32 | 15427 | 17.4% | 61.7 | 73 | 10560 | 32 | 863 | 3754 | 145 | 0 | 0 | 10662 | 0 | 60% |
| 6 | Dense 32->10 | 378 | 0.4% | 1.5 | 41 | 90 | 12 | 89 | 132 | 0 | 0 | 14 | 140 | 12 | 40% |

| # | layer | activation | load_act cycles | load_act DMA words | writeback cycles | activation clocks (in writeback) | input zeros | input negatives |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->16 k3x3 | table + round | 32 | 32 | 3652 | 3590 | 50.0% | 25.6% |
| 1 | Pool 28x28x16 | none | 0 | 0 | 0 | 0 | 14.4% | 39.1% |
| 2 | Conv 14x14x16->32 k3x3 | table + round | 32 | 32 | 1908 | 1798 | 6.1% | 2.6% |
| 3 | Pool 14x14x32 | none | 0 | 0 | 0 | 0 | 22.5% | 50.8% |
| 4 | Conv 7x7x32->32 k3x3 | table + round | 32 | 32 | 564 | 454 | 22.6% | 27.2% |
| 5 | Dense 1568->32 | table + round | 32 | 32 | 145 | 35 | 50.8% | 29.1% |
| 6 | Dense 32->10 | none | 0 | 0 | 0 | 0 | 15.6% | 12.5% |

## trained_hardswish_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)
total 240293 cycles (2402930 ns), compute 61.1%, DMA busy 26.2% of cycles, waiting for memory 0.0%

| phase | cycles | share | DMA in | DMA out | mem stall | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 0.1% | 108 | 0 | 10 |  |  |
| load_iact | 196 | 0.1% | 196 | 0 | 0 |  |  |
| load_wght | 39120 | 16.3% | 39120 | 0 | 0 |  |  |
| load_bias | 23308 | 9.7% | 23308 | 0 | 0 |  |  |
| load_quant | 240 | 0.1% | 160 (80 refused) | 0 | 0 |  |  |
| load_act | 96 | 0.0% | 96 | 0 | 0 |  |  |
| convert_iact | 10376 | 4.3% | 0 (4 refused) | 0 | 0 |  |  |
| compute | 146920 | 61.1% | 0 | 0 | 0 |  |  |
| writeback | 11948 | 5.0% | 0 | 0 | 0 |  |  |
| pooling | 7952 | 3.3% | 0 (2 refused) | 0 | 0 |  |  |
| readout | 14 | 0.0% | 0 | 12 | 0 |  |  |

| # | layer | cycles | share | us (250 MHz) | load | load_wght | load_bias | convert_iact | compute | writeback | pooling | readout | DMA in | DMA out | bus eff. |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | 33011 | 13.7% | 132.0 | 286 | 480 | 14336 | 1091 | 9582 | 7236 | 0 | 0 | 15102 | 0 | 1% |
| 1 | Pool 28x28x32 | 5213 | 2.2% | 20.9 | 61 | 0 | 0 | 0 | 0 | 0 | 5152 | 0 | 18 | 0 |  |
| 2 | Conv 14x14x32->64 k3x3 | 120490 | 50.1% | 482.0 | 93 | 15360 | 7168 | 4679 | 89490 | 3700 | 0 | 0 | 22618 | 0 | 11% |
| 3 | Pool 14x14x64 | 2861 | 1.2% | 11.4 | 61 | 0 | 0 | 0 | 0 | 0 | 2800 | 0 | 18 | 0 |  |
| 4 | Conv 7x7x64->64 k3x3 | 64730 | 26.9% | 258.9 | 93 | 15360 | 1792 | 2951 | 43522 | 1012 | 0 | 0 | 17242 | 0 | 27% |
| 5 | Dense 3136->10 | 13988 | 5.8% | 56.0 | 61 | 7920 | 12 | 1655 | 4326 | 0 | 0 | 14 | 7990 | 12 | 49% |

| # | layer | activation | load_act cycles | load_act DMA words | writeback cycles | activation clocks (in writeback) | input zeros | input negatives |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | table + round | 32 | 32 | 7236 | 7174 | 50.0% | 43.4% |
| 1 | Pool 28x28x32 | none | 0 | 0 | 0 | 0 | 5.4% | 43.3% |
| 2 | Conv 14x14x32->64 k3x3 | table + round | 32 | 32 | 3700 | 3590 | 5.9% | 31.7% |
| 3 | Pool 14x14x64 | none | 0 | 0 | 0 | 0 | 8.6% | 75.5% |
| 4 | Conv 7x7x64->64 k3x3 | table + round | 32 | 32 | 1012 | 902 | 14.3% | 55.2% |
| 5 | Dense 3136->10 | none | 0 | 0 | 0 | 0 | 13.2% | 49.7% |

## trained_leaky_relu_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)
total 238049 cycles (2380490 ns), compute 60.8%, DMA busy 26.4% of cycles, waiting for memory 0.0%

| phase | cycles | share | DMA in | DMA out | mem stall | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 0.1% | 108 | 0 | 10 |  |  |
| load_iact | 196 | 0.1% | 196 | 0 | 0 |  |  |
| load_wght | 39120 | 16.4% | 39120 | 0 | 0 |  |  |
| load_bias | 23308 | 9.8% | 23308 | 0 | 0 |  |  |
| load_quant | 240 | 0.1% | 160 (80 refused) | 0 | 0 |  |  |
| convert_iact | 10376 | 4.4% | 0 (4 refused) | 0 | 0 |  |  |
| compute | 144772 | 60.8% | 0 | 0 | 0 |  |  |
| writeback | 11948 | 5.0% | 0 | 0 | 0 |  |  |
| pooling | 7952 | 3.3% | 0 (2 refused) | 0 | 0 |  |  |
| readout | 14 | 0.0% | 0 | 12 | 0 |  |  |

| # | layer | cycles | share | us (250 MHz) | load | load_wght | load_bias | convert_iact | compute | writeback | pooling | readout | DMA in | DMA out | bus eff. |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | 32979 | 13.9% | 131.9 | 254 | 480 | 14336 | 1091 | 9582 | 7236 | 0 | 0 | 15070 | 0 | 1% |
| 1 | Pool 28x28x32 | 5213 | 2.2% | 20.9 | 61 | 0 | 0 | 0 | 0 | 0 | 5152 | 0 | 18 | 0 |  |
| 2 | Conv 14x14x32->64 k3x3 | 118928 | 50.0% | 475.7 | 61 | 15360 | 7168 | 4679 | 87960 | 3700 | 0 | 0 | 22586 | 0 | 10% |
| 3 | Pool 14x14x64 | 2861 | 1.2% | 11.4 | 61 | 0 | 0 | 0 | 0 | 0 | 2800 | 0 | 18 | 0 |  |
| 4 | Conv 7x7x64->64 k3x3 | 64138 | 26.9% | 256.6 | 61 | 15360 | 1792 | 2951 | 42962 | 1012 | 0 | 0 | 17210 | 0 | 27% |
| 5 | Dense 3136->10 | 13930 | 5.9% | 55.7 | 61 | 7920 | 12 | 1655 | 4268 | 0 | 0 | 14 | 7990 | 12 | 49% |

| # | layer | activation | load_act cycles | load_act DMA words | writeback cycles | activation clocks (in writeback) | input zeros | input negatives |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | leaky + round | 0 | 0 | 7236 | 7174 | 50.0% | 43.4% |
| 1 | Pool 28x28x32 | none | 0 | 0 | 0 | 0 | 24.2% | 36.1% |
| 2 | Conv 14x14x32->64 k3x3 | leaky + round | 0 | 0 | 3700 | 3590 | 24.3% | 25.2% |
| 3 | Pool 14x14x64 | none | 0 | 0 | 0 | 0 | 9.0% | 83.5% |
| 4 | Conv 7x7x64->64 k3x3 | leaky + round | 0 | 0 | 1012 | 902 | 14.7% | 68.7% |
| 5 | Dense 3136->10 | none | 0 | 0 | 0 | 0 | 18.1% | 49.1% |

## trained_relu_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)
total 218925 cycles (2189250 ns), compute 57.4%, DMA busy 28.7% of cycles, waiting for memory 0.0%

| phase | cycles | share | DMA in | DMA out | mem stall | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 0.1% | 108 | 0 | 10 |  |  |
| load_iact | 196 | 0.1% | 196 | 0 | 0 |  |  |
| load_wght | 39120 | 17.9% | 39120 | 0 | 0 |  |  |
| load_bias | 23308 | 10.6% | 23308 | 0 | 0 |  |  |
| load_quant | 240 | 0.1% | 160 (80 refused) | 0 | 0 |  |  |
| convert_iact | 10376 | 4.7% | 0 (4 refused) | 0 | 0 |  |  |
| compute | 125648 | 57.4% | 0 | 0 | 0 |  |  |
| writeback | 11948 | 5.5% | 0 | 0 | 0 |  |  |
| pooling | 7952 | 3.6% | 0 (2 refused) | 0 | 0 |  |  |
| readout | 14 | 0.0% | 0 | 12 | 0 |  |  |

| # | layer | cycles | share | us (250 MHz) | load | load_wght | load_bias | convert_iact | compute | writeback | pooling | readout | DMA in | DMA out | bus eff. |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | 32979 | 15.1% | 131.9 | 254 | 480 | 14336 | 1091 | 9582 | 7236 | 0 | 0 | 15070 | 0 | 1% |
| 1 | Pool 28x28x32 | 5213 | 2.4% | 20.9 | 61 | 0 | 0 | 0 | 0 | 0 | 5152 | 0 | 18 | 0 |  |
| 2 | Conv 14x14x32->64 k3x3 | 112010 | 51.2% | 448.0 | 61 | 15360 | 7168 | 4679 | 81042 | 3700 | 0 | 0 | 22586 | 0 | 10% |
| 3 | Pool 14x14x64 | 2861 | 1.3% | 11.4 | 61 | 0 | 0 | 0 | 0 | 0 | 2800 | 0 | 18 | 0 |  |
| 4 | Conv 7x7x64->64 k3x3 | 52754 | 24.1% | 211.0 | 61 | 15360 | 1792 | 2951 | 31578 | 1012 | 0 | 0 | 17210 | 0 | 27% |
| 5 | Dense 3136->10 | 13108 | 6.0% | 52.4 | 61 | 7920 | 12 | 1655 | 3446 | 0 | 0 | 14 | 7990 | 12 | 49% |

| # | layer | activation | load_act cycles | load_act DMA words | writeback cycles | activation clocks (in writeback) | input zeros | input negatives |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | relu | 0 | 0 | 7236 | 7174 | 50.0% | 43.4% |
| 1 | Pool 28x28x32 | none | 0 | 0 | 0 | 0 | 54.1% | 0.0% |
| 2 | Conv 14x14x32->64 k3x3 | relu | 0 | 0 | 3700 | 3590 | 43.5% | 0.0% |
| 3 | Pool 14x14x64 | none | 0 | 0 | 0 | 0 | 94.4% | 0.0% |
| 4 | Conv 7x7x64->64 k3x3 | relu | 0 | 0 | 1012 | 902 | 87.3% | 0.0% |
| 5 | Dense 3136->10 | none | 0 | 0 | 0 | 0 | 74.3% | 0.0% |

## trained_silu_img0
MNIST_REAL (6 layers) | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 64 | memory: ideal (legacy driver)
total 240229 cycles (2402290 ns), compute 61.1%, DMA busy 26.2% of cycles, waiting for memory 0.0%

| phase | cycles | share | DMA in | DMA out | mem stall | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|
| load_config | 123 | 0.1% | 108 | 0 | 10 |  |  |
| load_iact | 196 | 0.1% | 196 | 0 | 0 |  |  |
| load_wght | 39120 | 16.3% | 39120 | 0 | 0 |  |  |
| load_bias | 23308 | 9.7% | 23308 | 0 | 0 |  |  |
| load_quant | 240 | 0.1% | 160 (80 refused) | 0 | 0 |  |  |
| load_act | 96 | 0.0% | 96 | 0 | 0 |  |  |
| convert_iact | 10376 | 4.3% | 0 (4 refused) | 0 | 0 |  |  |
| compute | 146856 | 61.1% | 0 | 0 | 0 |  |  |
| writeback | 11948 | 5.0% | 0 | 0 | 0 |  |  |
| pooling | 7952 | 3.3% | 0 (2 refused) | 0 | 0 |  |  |
| readout | 14 | 0.0% | 0 | 12 | 0 |  |  |

| # | layer | cycles | share | us (250 MHz) | load | load_wght | load_bias | convert_iact | compute | writeback | pooling | readout | DMA in | DMA out | bus eff. |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | 33011 | 13.7% | 132.0 | 286 | 480 | 14336 | 1091 | 9582 | 7236 | 0 | 0 | 15102 | 0 | 1% |
| 1 | Pool 28x28x32 | 5213 | 2.2% | 20.9 | 61 | 0 | 0 | 0 | 0 | 0 | 5152 | 0 | 18 | 0 |  |
| 2 | Conv 14x14x32->64 k3x3 | 120221 | 50.0% | 480.9 | 93 | 15360 | 7168 | 4679 | 89221 | 3700 | 0 | 0 | 22618 | 0 | 11% |
| 3 | Pool 14x14x64 | 2861 | 1.2% | 11.4 | 61 | 0 | 0 | 0 | 0 | 0 | 2800 | 0 | 18 | 0 |  |
| 4 | Conv 7x7x64->64 k3x3 | 64906 | 27.0% | 259.6 | 93 | 15360 | 1792 | 2951 | 43698 | 1012 | 0 | 0 | 17242 | 0 | 27% |
| 5 | Dense 3136->10 | 14017 | 5.8% | 56.1 | 61 | 7920 | 12 | 1655 | 4355 | 0 | 0 | 14 | 7990 | 12 | 49% |

| # | layer | activation | load_act cycles | load_act DMA words | writeback cycles | activation clocks (in writeback) | input zeros | input negatives |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28x28x1+1pad->32 k3x3 | table + round | 32 | 32 | 7236 | 7174 | 50.0% | 43.4% |
| 1 | Pool 28x28x32 | none | 0 | 0 | 0 | 0 | 11.0% | 41.5% |
| 2 | Conv 14x14x32->64 k3x3 | table + round | 32 | 32 | 3700 | 3590 | 11.0% | 30.8% |
| 3 | Pool 14x14x64 | none | 0 | 0 | 0 | 0 | 3.9% | 82.4% |
| 4 | Conv 7x7x64->64 k3x3 | table + round | 32 | 32 | 1012 | 902 | 7.2% | 65.3% |
| 5 | Dense 3136->10 | none | 0 | 0 | 0 | 0 | 6.6% | 57.2% |
