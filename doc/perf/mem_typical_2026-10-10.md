
## 16x3_f4_q32_dma64
Convolution_Single 16x3x4 k3x3 f4 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32 | memory: typical
memory model: ideal (legacy driver) -> typical

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 18 | 0 | 18 | 18 | 0 | 0 -> 0 |  |
| load_iact | 24 | 38 | +14 (+58.3%) | 24 | 24 | 0 | 0 -> 14 | 100% -> 100% |
| load_wght | 120 | 176 | +56 (+46.7%) | 120 | 120 | 0 | 0 -> 56 | 15% -> 15% |
| load_bias | 96 | 138 | +42 (+43.8%) | 96 | 96 | 0 | 0 -> 42 | 2% -> 2% |
| load_quant | 20 | 20 | 0 | 20 | 20 | 0 | 0 -> 0 | 12% -> 12% |
| convert_iact | 251 | 251 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 357 | 357 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 98 | 98 | 0 | 96 | 96 | 0 | 0 -> 0 | 75% -> 75% |
| **TOTAL** | 984 | 1096 | +112 (+11.4%) | 374 | 374 | 0 | 0 -> 112 |  |

## 32x3_f16_q32_dma64
Convolution_Single 32x3x4 k3x3 f16 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32 | memory: typical
memory model: ideal (legacy driver) -> typical

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 18 | 0 | 18 | 18 | 0 | 0 -> 0 |  |
| load_iact | 48 | 76 | +28 (+58.3%) | 48 | 48 | 0 | 0 -> 28 | 100% -> 100% |
| load_wght | 480 | 690 | +210 (+43.8%) | 480 | 480 | 0 | 0 -> 210 | 15% -> 15% |
| load_bias | 768 | 1104 | +336 (+43.8%) | 768 | 768 | 0 | 0 -> 336 | 1% -> 1% |
| load_quant | 20 | 20 | 0 | 20 | 20 | 0 | 0 -> 0 | 50% -> 50% |
| convert_iact | 411 | 411 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 1137 | 1137 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 770 | 995 | +225 (+29.2%) | 768 | 768 | 0 | 0 -> 225 | 75% -> 75% |
| **TOTAL** | 3652 | 4451 | +799 (+21.9%) | 2102 | 2102 | 0 | 0 -> 799 |  |

## 32x3_f4_q32_dma32
Convolution_Single 32x3x4 k3x3 f4 | 2x2 clusters, DMA 32 b, psum 20 b, QUANT_AMOUNT 32 | memory: typical
memory model: ideal (legacy driver) -> typical

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 34 | 48 | +14 (+41.2%) | 34 | 34 | 0 | 0 -> 14 |  |
| load_iact | 96 | 138 | +42 (+43.8%) | 96 | 96 | 0 | 0 -> 42 | 100% -> 100% |
| load_wght | 216 | 300 | +84 (+38.9%) | 216 | 216 | 0 | 0 -> 84 | 17% -> 17% |
| load_bias | 384 | 552 | +168 (+43.8%) | 384 | 384 | 0 | 0 -> 168 | 1% -> 1% |
| load_quant | 40 | 68 | +28 (+70.0%) | 40 | 40 | 0 | 0 -> 28 | 12% -> 12% |
| convert_iact | 411 | 411 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 669 | 669 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 386 | 455 | +69 (+17.9%) | 384 | 384 | 0 | 0 -> 69 | 75% -> 75% |
| **TOTAL** | 2236 | 2641 | +405 (+18.1%) | 1154 | 1154 | 0 | 0 -> 405 |  |

## 32x3_f4_q32_dma64
Convolution_Single 32x3x4 k3x3 f4 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32 | memory: typical
memory model: ideal (legacy driver) -> typical

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 18 | 0 | 18 | 18 | 0 | 0 -> 0 |  |
| load_iact | 48 | 76 | +28 (+58.3%) | 48 | 48 | 0 | 0 -> 28 | 100% -> 100% |
| load_wght | 120 | 162 | +42 (+35.0%) | 120 | 120 | 0 | 0 -> 42 | 15% -> 15% |
| load_bias | 192 | 276 | +84 (+43.8%) | 192 | 192 | 0 | 0 -> 84 | 1% -> 1% |
| load_quant | 20 | 34 | +14 (+70.0%) | 20 | 20 | 0 | 0 -> 14 | 12% -> 12% |
| convert_iact | 411 | 411 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 669 | 669 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 194 | 194 | 0 | 192 | 192 | 0 | 0 -> 0 | 75% -> 75% |
| **TOTAL** | 1672 | 1840 | +168 (+10.0%) | 590 | 590 | 0 | 0 -> 168 |  |

## 8x1_f4_q32_dma64
Convolution_Single 8x1x4 k3x3 f4 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32 | memory: typical
memory model: ideal (legacy driver) -> typical

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 18 | 0 | 18 | 18 | 0 | 0 -> 0 |  |
| load_iact | 4 | 4 | 0 | 4 | 4 | 0 | 0 -> 0 | 100% -> 100% |
| load_wght | 120 | 176 | +56 (+46.7%) | 120 | 120 | 0 | 0 -> 56 | 15% -> 15% |
| load_bias | 32 | 46 | +14 (+43.8%) | 32 | 32 | 0 | 0 -> 14 | 5% -> 5% |
| load_quant | 20 | 34 | +14 (+70.0%) | 20 | 20 | 0 | 0 -> 14 | 12% -> 12% |
| convert_iact | 179 | 179 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 161 | 161 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 34 | 34 | 0 | 32 | 32 | 0 | 0 -> 0 | 38% -> 38% |
| **TOTAL** | 568 | 652 | +84 (+14.8%) | 226 | 226 | 0 | 0 -> 84 |  |

## mnist1_28x28_c4_f32_q32_dma64
Convolution_Single 28x28x4 k3x3 f32 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32 | memory: typical
memory model: ideal (legacy driver) -> typical

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 18 | 0 | 18 | 18 | 0 | 0 -> 0 |  |
| load_iact | 392 | 560 | +168 (+42.9%) | 392 | 392 | 0 | 0 -> 168 | 100% -> 100% |
| load_wght | 960 | 1380 | +420 (+43.8%) | 960 | 960 | 0 | 0 -> 420 | 15% -> 15% |
| load_bias | 14336 | 20608 | +6272 (+43.8%) | 14336 | 14336 | 0 | 0 -> 6272 | 0% -> 0% |
| load_quant | 20 | 34 | +14 (+70.0%) | 20 | 20 | 0 | 0 -> 14 | 100% -> 100% |
| convert_iact | 2111 | 2111 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 33625 | 33625 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 14338 | 20075 | +5737 (+40.0%) | 14336 | 14336 | 0 | 0 -> 5737 | 66% -> 66% |
| **TOTAL** | 65800 | 78411 | +12611 (+19.2%) | 30062 | 30062 | 0 | 0 -> 12611 |  |

## mnist2_14x14_c32_f32_q32_dma64
Convolution_Single 14x14x32 k3x3 f32 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32 | memory: typical
memory model: ideal (legacy driver) -> typical

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 18 | 0 | 18 | 18 | 0 | 0 -> 0 |  |
| load_iact | 784 | 1134 | +350 (+44.6%) | 784 | 784 | 0 | 0 -> 350 | 100% -> 100% |
| load_wght | 7680 | 11040 | +3360 (+43.8%) | 7680 | 7680 | 0 | 0 -> 3360 | 15% -> 15% |
| load_bias | 3584 | 5152 | +1568 (+43.8%) | 3584 | 3584 | 0 | 0 -> 1568 | 0% -> 0% |
| load_quant | 20 | 20 | 0 | 20 | 20 | 0 | 0 -> 0 | 100% -> 100% |
| convert_iact | 4679 | 4679 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 66681 | 66681 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 3586 | 4955 | +1369 (+38.2%) | 3584 | 3584 | 0 | 0 -> 1369 | 66% -> 66% |
| **TOTAL** | 87032 | 93679 | +6647 (+7.6%) | 15670 | 15670 | 0 | 0 -> 6647 |  |

## mnist3_8x8_c32_f32_q32_dma64
Convolution_Single 8x8x32 k3x3 f32 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32 | memory: typical
memory model: ideal (legacy driver) -> typical

| phase | cycles base | cycles new | change | DMA words base | DMA words new | change | mem stall | bus eff. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 18 | 0 | 18 | 18 | 0 | 0 -> 0 |  |
| load_iact | 256 | 368 | +112 (+43.8%) | 256 | 256 | 0 | 0 -> 112 | 100% -> 100% |
| load_wght | 3840 | 5520 | +1680 (+43.8%) | 3840 | 3840 | 0 | 0 -> 1680 | 30% -> 30% |
| load_bias | 1024 | 1472 | +448 (+43.8%) | 1024 | 1024 | 0 | 0 -> 448 | 1% -> 1% |
| load_quant | 20 | 34 | +14 (+70.0%) | 20 | 20 | 0 | 0 -> 14 | 100% -> 100% |
| convert_iact | 1671 | 1671 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| compute | 18873 | 18873 | 0 | 0 | 0 | 0 | 0 -> 0 |  |
| readout | 1026 | 1355 | +329 (+32.1%) | 1024 | 1024 | 0 | 0 -> 329 | 75% -> 75% |
| **TOTAL** | 26728 | 29311 | +2583 (+9.7%) | 6182 | 6182 | 0 | 0 -> 2583 |  |

## Summary

| case | cycles base | cycles new | change | DMA words base | DMA words new | change |
|---|---:|---:|---:|---:|---:|---:|
| 16x3_f4_q32_dma64 | 984 | 1096 | +112 (+11.4%) | 374 | 374 | 0 |
| 32x3_f16_q32_dma64 | 3652 | 4451 | +799 (+21.9%) | 2102 | 2102 | 0 |
| 32x3_f4_q32_dma32 | 2236 | 2641 | +405 (+18.1%) | 1154 | 1154 | 0 |
| 32x3_f4_q32_dma64 | 1672 | 1840 | +168 (+10.0%) | 590 | 590 | 0 |
| 8x1_f4_q32_dma64 | 568 | 652 | +84 (+14.8%) | 226 | 226 | 0 |
| mnist1_28x28_c4_f32_q32_dma64 | 65800 | 78411 | +12611 (+19.2%) | 30062 | 30062 | 0 |
| mnist2_14x14_c32_f32_q32_dma64 | 87032 | 93679 | +6647 (+7.6%) | 15670 | 15670 | 0 |
| mnist3_8x8_c32_f32_q32_dma64 | 26728 | 29311 | +2583 (+9.7%) | 6182 | 6182 | 0 |
| 8x1_f4_q1024_dma64 | 1188 | (not run) | | | | |
