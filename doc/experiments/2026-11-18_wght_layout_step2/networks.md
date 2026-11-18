## Whole networks: dense weight layout on the sparse PE (raw forced) against today

| Network | sparse today | dense HW | P1 step 1 estimate | dense layout run | **P1 measured** | P1 with the per-layer rule | P1 vs sparse | P1 vs dense HW | bit-exact |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| MNIST ReLU | 196,238 | 202,895 | 180,686 | 196,238 | **180,686** | 180,686 | -7,9 % | -10,9 % | PASS |
| MNIST Leaky ReLU | 215,363 | 202,895 | 199,811 | 215,389 | **199,837** | 199,837 | -7,2 % | -1,5 % | PASS |
| MNIST SiLU | 217,512 | 202,959 | 201,960 | 217,525 | **201,973** | 201,973 | -7,1 % | -0,5 % | PASS |
| MNIST hard-swish | 217,569 | 202,959 | 202,017 | 217,569 | **202,017** | 202,017 | -7,1 % | -0,5 % | PASS |
| Table 2 cr1_x2_y3 ReLU | 189,519 | 196,248 | 182,931 | 189,839 | **183,251** | 183,251 | -3,3 % | -6,6 % | PASS |
| Table 2 cr1_x2_y4 ReLU | 185,710 | 192,506 | 180,190 | 186,030 | **180,510** | 180,510 | -2,8 % | -6,2 % | PASS |
| Table 2 cr1_x4_y3 ReLU | 114,969 | 115,836 | 108,381 | 115,119 | **108,531** | 108,531 | -5,6 % | -6,3 % | PASS |
| Table 2 cr1_x4_y4 ReLU | 110,908 | 111,842 | 105,388 | 111,058 | **105,538** | 105,538 | -4,8 % | -5,6 % | PASS |
| Table 2 cr2_x2_y3 ReLU | 120,554 | 117,463 | 111,638 | 120,704 | **111,788** | 111,788 | -7,3 % | -4,8 % | PASS |
| Table 2 cr2_x2_y4 ReLU | 121,945 | 119,355 | 114,001 | 122,095 | **114,151** | 114,151 | -6,4 % | -4,4 % | PASS |
| Table 2 cr2_x4_y3 ReLU | 74,177 | 70,369 | 66,797 | 74,242 | **66,862** | 66,862 | -9,9 % | -5,0 % | PASS |
| Table 2 cr2_x4_y4 ReLU | 74,632 | 71,325 | 68,224 | 74,697 | **68,289** | 68,289 | -8,5 % | -4,3 % | PASS |
| Table 2 cr4_x2_y3 ReLU | 83,831 | 78,731 | 75,947 | 83,896 | **76,012** | 76,012 | -9,3 % | -3,5 % | PASS |
| Table 2 cr4_x2_y4 ReLU | 89,388 | 82,265 | 79,668 | 89,453 | **79,733** | 79,733 | -10,8 % | -3,1 % | PASS |
| Table 2 cr4_x4_y3 ReLU | 54,803 | 50,805 | 49,223 | 54,801 | **49,221** | 49,221 | -10,2 % | -3,1 % | PASS |
| Table 2 cr4_x4_y4 ReLU | 57,972 | 52,719 | 51,324 | 57,970 | **51,322** | 51,322 | -11,5 % | -2,6 % | PASS |
| Table 2 cr8_x2_y3 ReLU | 66,879 | 59,891 | 58,635 | 66,877 | **58,633** | 58,633 | -12,3 % | -2,1 % | PASS |
| Table 2 cr8_x2_y4 ReLU | 70,931 | 62,434 | 61,347 | 70,929 | **61,345** | 61,345 | -13,5 % | -1,7 % | PASS |
| Table 2 cr8_x4_y3 ReLU | 50,199 | 44,796 | 44,331 | 50,182 | **44,314** | 44,314 | -11,7 % | -1,1 % | PASS |
| Table 2 cr8_x4_y4 ReLU | 51,879 | 45,762 | 45,463 | 51,862 | **45,446** | 45,446 | -12,4 % | -0,7 % | PASS |
| Table 2 cr1_x2_y3 no act. | 201,915 | 196,248 | 195,327 | 202,291 | **195,703** | 195,703 | -3,1 % | -0,3 % | PASS |
| Table 2 cr1_x2_y4 no act. | 197,170 | 192,506 | 191,650 | 197,546 | **192,026** | 192,026 | -2,6 % | -0,2 % | PASS |
| Table 2 cr1_x4_y3 no act. | 122,108 | 115,836 | 115,520 | 122,283 | **115,695** | 115,695 | -5,3 % | -0,1 % | PASS |
| Table 2 cr1_x4_y4 no act. | 117,111 | 111,842 | 111,591 | 117,286 | **111,766** | 111,766 | -4,6 % | -0,1 % | PASS |
| Table 2 cr2_x2_y3 no act. | 126,105 | 117,463 | 117,189 | 126,280 | **117,364** | 117,364 | -6,9 % | -0,1 % | PASS |
| Table 2 cr2_x2_y4 no act. | 127,016 | 119,355 | 119,072 | 127,191 | **119,247** | 119,247 | -6,1 % | -0,1 % | PASS |
| Table 2 cr2_x4_y3 no act. | 77,655 | 70,369 | 70,275 | 77,730 | **70,350** | 70,350 | -9,4 % | -0,0 % | PASS |
| Table 2 cr2_x4_y4 no act. | 77,630 | 71,325 | 71,222 | 77,705 | **71,297** | 71,297 | -8,2 % | -0,0 % | PASS |
| Table 2 cr4_x2_y3 no act. | 86,514 | 78,731 | 78,630 | 86,589 | **78,705** | 78,705 | -9,0 % | -0,0 % | PASS |
| Table 2 cr4_x2_y4 no act. | 91,842 | 82,265 | 82,122 | 91,917 | **82,197** | 82,197 | -10,5 % | -0,1 % | PASS |
| Table 2 cr4_x4_y3 no act. | 56,489 | 50,805 | 50,909 | 56,491 | **50,911** | 50,911 | -9,9 % | +0,2 % | PASS |
| Table 2 cr4_x4_y4 no act. | 59,429 | 52,719 | 52,781 | 59,431 | **52,783** | 52,783 | -11,2 % | +0,1 % | PASS |
| Table 2 cr8_x2_y3 no act. | 68,197 | 59,891 | 59,953 | 68,199 | **59,955** | 59,955 | -12,1 % | +0,1 % | PASS |
| Table 2 cr8_x2_y4 no act. | 72,083 | 62,434 | 62,499 | 72,085 | **62,501** | 62,501 | -13,3 % | +0,1 % | PASS |
| Table 2 cr8_x4_y3 no act. | 50,978 | 44,796 | 45,110 | 50,944 | **45,076** | 45,076 | -11,6 % | +0,6 % | PASS |
| Table 2 cr8_x4_y4 no act. | 52,495 | 45,762 | 46,079 | 52,461 | **46,045** | 46,045 | -12,3 % | +0,6 % | PASS |

## Per layer (layers with a weight load difference)

| Network | Layer | weight zeros | load_wght saved | compute added (dense layout) | added / compute | raw worth it |
|---|---|---:|---:|---:|---:|---|
| MNIST ReLU | 0 Convolution2D | 0,3 % | 96 | 0 | +0,0 % | yes |
| MNIST ReLU | 2 Convolution2D | 1,6 % | 6,144 | 0 | +0,0 % | yes |
| MNIST ReLU | 4 Convolution2D | 1,6 % | 6,144 | 0 | +0,0 % | yes |
| MNIST ReLU | 5 Dense | 2,9 % | 3,168 | 0 | +0,0 % | yes |
| MNIST Leaky ReLU | 0 Convolution2D | 0,7 % | 96 | 0 | +0,0 % | yes |
| MNIST Leaky ReLU | 2 Convolution2D | 2,0 % | 6,144 | 26 | +0,0 % | yes |
| MNIST Leaky ReLU | 4 Convolution2D | 1,5 % | 6,144 | 0 | +0,0 % | yes |
| MNIST Leaky ReLU | 5 Dense | 1,4 % | 3,168 | 0 | +0,0 % | yes |
| MNIST SiLU | 0 Convolution2D | 0,7 % | 96 | 0 | +0,0 % | yes |
| MNIST SiLU | 2 Convolution2D | 1,6 % | 6,144 | 13 | +0,0 % | yes |
| MNIST SiLU | 4 Convolution2D | 1,6 % | 6,144 | 0 | +0,0 % | yes |
| MNIST SiLU | 5 Dense | 1,7 % | 3,168 | 0 | +0,0 % | yes |
| MNIST hard-swish | 0 Convolution2D | 0,7 % | 96 | 0 | +0,0 % | yes |
| MNIST hard-swish | 2 Convolution2D | 1,6 % | 6,144 | 0 | +0,0 % | yes |
| MNIST hard-swish | 4 Convolution2D | 1,6 % | 6,144 | 0 | +0,0 % | yes |
| MNIST hard-swish | 5 Dense | 1,9 % | 3,168 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y3 ReLU | 0 Convolution2D | 3,5 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y3 ReLU | 2 Convolution2D | 3,5 % | 768 | 270 | +0,3 % | yes |
| Table 2 cr1_x2_y3 ReLU | 4 Convolution2D | 3,9 % | 1,536 | 50 | +0,1 % | yes |
| Table 2 cr1_x2_y3 ReLU | 5 Dense | 0,0 % | 4,224 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y3 ReLU | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y4 ReLU | 0 Convolution2D | 3,5 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y4 ReLU | 2 Convolution2D | 3,5 % | 768 | 270 | +0,3 % | yes |
| Table 2 cr1_x2_y4 ReLU | 4 Convolution2D | 3,9 % | 1,536 | 50 | +0,1 % | yes |
| Table 2 cr1_x2_y4 ReLU | 5 Dense | 0,0 % | 3,168 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y4 ReLU | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y3 ReLU | 0 Convolution2D | 3,5 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y3 ReLU | 2 Convolution2D | 3,5 % | 768 | 130 | +0,3 % | yes |
| Table 2 cr1_x4_y3 ReLU | 4 Convolution2D | 3,9 % | 1,536 | 20 | +0,1 % | yes |
| Table 2 cr1_x4_y3 ReLU | 5 Dense | 0,0 % | 4,224 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y3 ReLU | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y4 ReLU | 0 Convolution2D | 3,5 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y4 ReLU | 2 Convolution2D | 3,5 % | 768 | 130 | +0,3 % | yes |
| Table 2 cr1_x4_y4 ReLU | 4 Convolution2D | 3,9 % | 1,536 | 20 | +0,1 % | yes |
| Table 2 cr1_x4_y4 ReLU | 5 Dense | 0,0 % | 3,168 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y4 ReLU | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y3 ReLU | 0 Convolution2D | 3,5 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y3 ReLU | 2 Convolution2D | 3,5 % | 1,536 | 130 | +0,3 % | yes |
| Table 2 cr2_x2_y3 ReLU | 4 Convolution2D | 3,9 % | 3,072 | 20 | +0,1 % | yes |
| Table 2 cr2_x2_y3 ReLU | 5 Dense | 0,0 % | 4,224 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y3 ReLU | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y4 ReLU | 0 Convolution2D | 3,5 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y4 ReLU | 2 Convolution2D | 3,5 % | 1,536 | 130 | +0,3 % | yes |
| Table 2 cr2_x2_y4 ReLU | 4 Convolution2D | 3,9 % | 3,072 | 20 | +0,1 % | yes |
| Table 2 cr2_x2_y4 ReLU | 5 Dense | 0,0 % | 3,264 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y4 ReLU | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y3 ReLU | 0 Convolution2D | 3,5 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y3 ReLU | 2 Convolution2D | 3,5 % | 1,536 | 62 | +0,3 % | yes |
| Table 2 cr2_x4_y3 ReLU | 4 Convolution2D | 3,9 % | 1,536 | 3 | +0,0 % | yes |
| Table 2 cr2_x4_y3 ReLU | 5 Dense | 0,0 % | 4,224 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y3 ReLU | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y4 ReLU | 0 Convolution2D | 3,5 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y4 ReLU | 2 Convolution2D | 3,5 % | 1,536 | 62 | +0,3 % | yes |
| Table 2 cr2_x4_y4 ReLU | 4 Convolution2D | 3,9 % | 1,536 | 3 | +0,0 % | yes |
| Table 2 cr2_x4_y4 ReLU | 5 Dense | 0,0 % | 3,264 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y4 ReLU | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y3 ReLU | 0 Convolution2D | 3,5 % | 72 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y3 ReLU | 2 Convolution2D | 3,5 % | 2,304 | 62 | +0,3 % | yes |
| Table 2 cr4_x2_y3 ReLU | 4 Convolution2D | 3,9 % | 2,304 | 3 | +0,0 % | yes |
| Table 2 cr4_x2_y3 ReLU | 5 Dense | 0,0 % | 3,168 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y3 ReLU | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y4 ReLU | 0 Convolution2D | 3,5 % | 96 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y4 ReLU | 2 Convolution2D | 3,5 % | 3,072 | 62 | +0,3 % | yes |
| Table 2 cr4_x2_y4 ReLU | 4 Convolution2D | 3,9 % | 3,072 | 3 | +0,0 % | yes |
| Table 2 cr4_x2_y4 ReLU | 5 Dense | 0,0 % | 3,456 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y4 ReLU | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y3 ReLU | 0 Convolution2D | 3,5 % | 72 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y3 ReLU | 2 Convolution2D | 3,5 % | 1,152 | 12 | +0,1 % | yes |
| Table 2 cr4_x4_y3 ReLU | 4 Convolution2D | 3,9 % | 1,152 | -14 | -0,2 % | yes |
| Table 2 cr4_x4_y3 ReLU | 5 Dense | 0,0 % | 3,168 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y3 ReLU | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y4 ReLU | 0 Convolution2D | 3,5 % | 96 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y4 ReLU | 2 Convolution2D | 3,5 % | 1,536 | 12 | +0,1 % | yes |
| Table 2 cr4_x4_y4 ReLU | 4 Convolution2D | 3,9 % | 1,536 | -14 | -0,2 % | yes |
| Table 2 cr4_x4_y4 ReLU | 5 Dense | 0,0 % | 3,456 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y4 ReLU | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y3 ReLU | 0 Convolution2D | 3,5 % | 144 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y3 ReLU | 2 Convolution2D | 3,5 % | 2,304 | 12 | +0,1 % | yes |
| Table 2 cr8_x2_y3 ReLU | 4 Convolution2D | 3,9 % | 2,304 | -14 | -0,3 % | yes |
| Table 2 cr8_x2_y3 ReLU | 5 Dense | 0,0 % | 3,456 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y3 ReLU | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y4 ReLU | 0 Convolution2D | 3,5 % | 192 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y4 ReLU | 2 Convolution2D | 3,5 % | 3,072 | 12 | +0,1 % | yes |
| Table 2 cr8_x2_y4 ReLU | 4 Convolution2D | 3,9 % | 3,072 | -14 | -0,3 % | yes |
| Table 2 cr8_x2_y4 ReLU | 5 Dense | 0,0 % | 3,200 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y4 ReLU | 6 Dense | 0,0 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y3 ReLU | 0 Convolution2D | 3,5 % | 72 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y3 ReLU | 2 Convolution2D | 3,5 % | 1,152 | -5 | -0,1 % | yes |
| Table 2 cr8_x4_y3 ReLU | 4 Convolution2D | 3,9 % | 1,152 | -12 | -0,2 % | yes |
| Table 2 cr8_x4_y3 ReLU | 5 Dense | 0,0 % | 3,456 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y3 ReLU | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y4 ReLU | 0 Convolution2D | 3,5 % | 96 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y4 ReLU | 2 Convolution2D | 3,5 % | 1,536 | -5 | -0,1 % | yes |
| Table 2 cr8_x4_y4 ReLU | 4 Convolution2D | 3,9 % | 1,536 | -12 | -0,2 % | yes |
| Table 2 cr8_x4_y4 ReLU | 5 Dense | 0,0 % | 3,200 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y4 ReLU | 6 Dense | 0,0 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y3 no act. | 0 Convolution2D | 3,5 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y3 no act. | 2 Convolution2D | 3,5 % | 768 | 268 | +0,3 % | yes |
| Table 2 cr1_x2_y3 no act. | 4 Convolution2D | 3,9 % | 1,536 | 108 | +0,2 % | yes |
| Table 2 cr1_x2_y3 no act. | 5 Dense | 0,0 % | 4,224 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y3 no act. | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y4 no act. | 0 Convolution2D | 3,5 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y4 no act. | 2 Convolution2D | 3,5 % | 768 | 268 | +0,3 % | yes |
| Table 2 cr1_x2_y4 no act. | 4 Convolution2D | 3,9 % | 1,536 | 108 | +0,2 % | yes |
| Table 2 cr1_x2_y4 no act. | 5 Dense | 0,0 % | 3,168 | 0 | +0,0 % | yes |
| Table 2 cr1_x2_y4 no act. | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y3 no act. | 0 Convolution2D | 3,5 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y3 no act. | 2 Convolution2D | 3,5 % | 768 | 130 | +0,3 % | yes |
| Table 2 cr1_x4_y3 no act. | 4 Convolution2D | 3,9 % | 1,536 | 45 | +0,2 % | yes |
| Table 2 cr1_x4_y3 no act. | 5 Dense | 0,0 % | 4,224 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y3 no act. | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y4 no act. | 0 Convolution2D | 3,5 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y4 no act. | 2 Convolution2D | 3,5 % | 768 | 130 | +0,3 % | yes |
| Table 2 cr1_x4_y4 no act. | 4 Convolution2D | 3,9 % | 1,536 | 45 | +0,2 % | yes |
| Table 2 cr1_x4_y4 no act. | 5 Dense | 0,0 % | 3,168 | 0 | +0,0 % | yes |
| Table 2 cr1_x4_y4 no act. | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y3 no act. | 0 Convolution2D | 3,5 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y3 no act. | 2 Convolution2D | 3,5 % | 1,536 | 130 | +0,3 % | yes |
| Table 2 cr2_x2_y3 no act. | 4 Convolution2D | 3,9 % | 3,072 | 45 | +0,2 % | yes |
| Table 2 cr2_x2_y3 no act. | 5 Dense | 0,0 % | 4,224 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y3 no act. | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y4 no act. | 0 Convolution2D | 3,5 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y4 no act. | 2 Convolution2D | 3,5 % | 1,536 | 130 | +0,3 % | yes |
| Table 2 cr2_x2_y4 no act. | 4 Convolution2D | 3,9 % | 3,072 | 45 | +0,2 % | yes |
| Table 2 cr2_x2_y4 no act. | 5 Dense | 0,0 % | 3,264 | 0 | +0,0 % | yes |
| Table 2 cr2_x2_y4 no act. | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y3 no act. | 0 Convolution2D | 3,5 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y3 no act. | 2 Convolution2D | 3,5 % | 1,536 | 65 | +0,3 % | yes |
| Table 2 cr2_x4_y3 no act. | 4 Convolution2D | 3,9 % | 1,536 | 10 | +0,1 % | yes |
| Table 2 cr2_x4_y3 no act. | 5 Dense | 0,0 % | 4,224 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y3 no act. | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y4 no act. | 0 Convolution2D | 3,5 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y4 no act. | 2 Convolution2D | 3,5 % | 1,536 | 65 | +0,3 % | yes |
| Table 2 cr2_x4_y4 no act. | 4 Convolution2D | 3,9 % | 1,536 | 10 | +0,1 % | yes |
| Table 2 cr2_x4_y4 no act. | 5 Dense | 0,0 % | 3,264 | 0 | +0,0 % | yes |
| Table 2 cr2_x4_y4 no act. | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y3 no act. | 0 Convolution2D | 3,5 % | 72 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y3 no act. | 2 Convolution2D | 3,5 % | 2,304 | 65 | +0,3 % | yes |
| Table 2 cr4_x2_y3 no act. | 4 Convolution2D | 3,9 % | 2,304 | 10 | +0,1 % | yes |
| Table 2 cr4_x2_y3 no act. | 5 Dense | 0,0 % | 3,168 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y3 no act. | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y4 no act. | 0 Convolution2D | 3,5 % | 96 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y4 no act. | 2 Convolution2D | 3,5 % | 3,072 | 65 | +0,3 % | yes |
| Table 2 cr4_x2_y4 no act. | 4 Convolution2D | 3,9 % | 3,072 | 10 | +0,1 % | yes |
| Table 2 cr4_x2_y4 no act. | 5 Dense | 0,0 % | 3,456 | 0 | +0,0 % | yes |
| Table 2 cr4_x2_y4 no act. | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y3 no act. | 0 Convolution2D | 3,5 % | 72 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y3 no act. | 2 Convolution2D | 3,5 % | 1,152 | 12 | +0,1 % | yes |
| Table 2 cr4_x4_y3 no act. | 4 Convolution2D | 3,9 % | 1,152 | -10 | -0,1 % | yes |
| Table 2 cr4_x4_y3 no act. | 5 Dense | 0,0 % | 3,168 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y3 no act. | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y4 no act. | 0 Convolution2D | 3,5 % | 96 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y4 no act. | 2 Convolution2D | 3,5 % | 1,536 | 12 | +0,1 % | yes |
| Table 2 cr4_x4_y4 no act. | 4 Convolution2D | 3,9 % | 1,536 | -10 | -0,1 % | yes |
| Table 2 cr4_x4_y4 no act. | 5 Dense | 0,0 % | 3,456 | 0 | +0,0 % | yes |
| Table 2 cr4_x4_y4 no act. | 6 Dense | 0,0 % | 24 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y3 no act. | 0 Convolution2D | 3,5 % | 144 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y3 no act. | 2 Convolution2D | 3,5 % | 2,304 | 12 | +0,1 % | yes |
| Table 2 cr8_x2_y3 no act. | 4 Convolution2D | 3,9 % | 2,304 | -10 | -0,2 % | yes |
| Table 2 cr8_x2_y3 no act. | 5 Dense | 0,0 % | 3,456 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y3 no act. | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y4 no act. | 0 Convolution2D | 3,5 % | 192 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y4 no act. | 2 Convolution2D | 3,5 % | 3,072 | 12 | +0,1 % | yes |
| Table 2 cr8_x2_y4 no act. | 4 Convolution2D | 3,9 % | 3,072 | -10 | -0,2 % | yes |
| Table 2 cr8_x2_y4 no act. | 5 Dense | 0,0 % | 3,200 | 0 | +0,0 % | yes |
| Table 2 cr8_x2_y4 no act. | 6 Dense | 0,0 % | 48 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y3 no act. | 0 Convolution2D | 3,5 % | 72 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y3 no act. | 2 Convolution2D | 3,5 % | 1,152 | -4 | -0,1 % | yes |
| Table 2 cr8_x4_y3 no act. | 4 Convolution2D | 3,9 % | 1,152 | -30 | -0,5 % | yes |
| Table 2 cr8_x4_y3 no act. | 5 Dense | 0,0 % | 3,456 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y3 no act. | 6 Dense | 0,0 % | 36 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y4 no act. | 0 Convolution2D | 3,5 % | 96 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y4 no act. | 2 Convolution2D | 3,5 % | 1,536 | -4 | -0,1 % | yes |
| Table 2 cr8_x4_y4 no act. | 4 Convolution2D | 3,9 % | 1,536 | -30 | -0,5 % | yes |
| Table 2 cr8_x4_y4 no act. | 5 Dense | 0,0 % | 3,200 | 0 | +0,0 % | yes |
| Table 2 cr8_x4_y4 no act. | 6 Dense | 0,0 % | 48 | 0 | +0,0 % | yes |

