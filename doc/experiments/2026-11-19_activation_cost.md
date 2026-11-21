# Hàm kích hoạt tốn bao nhiêu chu kỳ (2026-11-19)

Đo trên RTL hiện tại (không đổi từ `ae5665f`), model MNIST đã huấn luyện riêng cho từng hàm, 2×2 cluster, DMA 64 bit, 250 MHz.
Sparse: ảnh 0, 1, 6 (12 lần chạy) + dense ảnh 0 (4 lần), 16/16 PASS khớp từng bit. Dense: ảnh 0 (compute không phụ thuộc dữ liệu).
Profile: `doc/perf/activation_cost_2026-11-19/`. Script: `analyse.py`, `run_img.py` trong thư mục này.

## Kết luận

1. **Bản thân khối kích hoạt tốn 0 chu kỳ ở cả 4 hàm.** Pha `writeback` giống hệt từng chu kỳ (chu kỳ khối kích hoạt 7.174 / 3.590 / 902 ở Conv1/2/3
   nằm *trong* writeback, không cộng thêm).
2. **Chi phí trực tiếp duy nhất là nạp bảng (SiLU, hard-swish):** `load_act` = 32 chu kỳ × 3 layer = 96, nhưng thực tế net **+64**, vì ở Conv1
   `load_act` +32 bị `writeback` −32 bù (tổng Conv1 không đổi: 19.189 = 19.189). Nguyên nhân có lẽ là ghi lại bảng bias chạy nền (option A
   background) che mất 32 chu kỳ này; chưa kiểm bằng trace. Leaky ReLU: 0 (tham số mantissa/shift nằm trong regmap).
3. **Trên phần cứng dense: ReLU = Leaky ReLU = 202.895; SiLU = hard-swish = 202.959 (+64, +0,03 %).** Đây là chi phí thật của hàm kích hoạt.
4. **Trên phần cứng sparse: +9,5 … +11,2 % (≈ +19.000 … +22.000 chu kỳ, 75 – 88 µs).** 99,5 % nằm ở `compute` của layer *sau* hàm kích hoạt: ReLU
   cho 43/82/76 % số 0 ở input Conv2/Conv3/Dense, hàm khác chỉ còn 6–22 %, PE sparse không còn gì để bỏ qua. Đó là mất lợi ích của ReLU
   chứ không phải chi phí của hàm; đổi lại ở dense không mất gì (và sparse+Leaky vẫn chậm hơn dense 12.468 chu kỳ).

## Sparse, 3 ảnh: Δ chu kỳ so với ReLU

| hàm | ảnh 0 | ảnh 1 | ảnh 6 | trung bình |
|---|---:|---:|---:|---:|
| ReLU (tổng) | 196.238 | 197.614 | 195.786 | 196.546 |
| Leaky ReLU | +19.125 (+9,75 %) | +18.783 (+9,50 %) | +20.127 (+10,28 %) | +19.345 (+9,84 %) |
| SiLU | +21.274 (+10,84 %) | +20.185 (+10,21 %) | +21.928 (+11,20 %) | +21.129 (+10,75 %) |
| hard-swish | +21.331 (+10,87 %) | +19.867 (+10,05 %) | +21.580 (+11,02 %) | +20.926 (+10,65 %) |

Δ tổng chu kỳ từng layer (trung bình 3 ảnh; Conv1, hai Pool: 0 ở mọi hàm, trừ SiLU/hard-swish Conv1 0 nhờ che; Conv2/Conv3 SiLU/hard-swish gồm +32 của `load_act`):

| layer | ReLU (chu kỳ) | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Conv2 | 104.617 | +7.464 (+7,1 %) | +8.585 (+8,2 %) | +8.737 (+8,4 %) |
| Conv3 | 51.601 | +10.991 (+21,3 %) | +11.588 (+22,5 %) | +11.284 (+21,9 %) |
| Dense | 13.065 | +890 (+6,8 %) | +956 (+7,3 %) | +905 (+6,9 %) |

Layer nào chịu: hàm ở Conv1 làm tăng compute của Conv2 (qua Pool1), hàm ở Conv2 làm tăng Conv3, hàm ở Conv3 làm tăng Dense.

Chi tiết từng pha / từng layer / từng ảnh và chế độ: phần phụ lục (đầu ra của `analyse.py doc/perf/activation_cost_2026-11-19`).

## Phụ lục


### Ảnh 0, phần cứng sparse

| hàm | tổng chu kỳ | µs @250 MHz | so với ReLU | % | Δ load_act | Δ writeback | Δ compute | Δ pha khác |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ReLU | 196.238 | 785.0 | 0 | +0.00 % | 0 | 0 | 0 | 0 |
| Leaky ReLU | 215.363 | 861.5 | +19.125 | +9.75 % | 0 | 0 | +19.125 | 0 |
| SiLU | 217.512 | 870.0 | +21.274 | +10.84 % | +96 | -32 | +21.210 | 0 |
| hard-swish | 217.569 | 870.3 | +21.331 | +10.87 % | +96 | -32 | +21.267 | 0 |

Số chu kỳ từng pha (cả mạng):

| pha | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| load_config | 123 | 123 | 123 | 123 |
| load_iact | 100 | 100 | 100 | 100 |
| load_wght | 38.880 | 38.880 | 38.880 | 38.880 |
| load_bias | 92 | 92 | 92 | 92 |
| load_quant | 240 | 240 | 240 | 240 |
| load_act | 0 | 0 | 96 | 96 |
| convert_iact | 10.376 | 10.376 | 10.376 | 10.376 |
| compute | 125.647 | 144.772 | 146.857 | 146.914 |
| writeback | 12.814 | 12.814 | 12.782 | 12.782 |
| pooling | 7.952 | 7.952 | 7.952 | 7.952 |
| readout | 14 | 14 | 14 | 14 |
| **tổng** | 196.238 | 215.363 | 217.512 | 217.569 |

Tổng chu kỳ và `compute` từng layer (Δ so với ReLU):

| layer | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Conv1 | 19.189 (compute 9.582) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Pool1 | 5.213 (compute 0) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Conv2 | 104.874 (compute 81.042) | +6.918 (compute +6.918) | +8.211 (compute +8.179) | +8.480 (compute +8.448) |
| Pool2 | 2.861 (compute 0) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Conv3 | 50.994 (compute 31.578) | +11.384 (compute +11.384) | +12.152 (compute +12.120) | +11.976 (compute +11.944) |
| Dense | 13.107 (compute 3.445) | +823 (compute +823) | +911 (compute +911) | +875 (compute +875) |

Hàm kích hoạt chạy ở layer nào, số 0 ở input từng layer, chu kỳ khối kích hoạt (nằm trong writeback):

| layer | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Conv1 | relu; input 0 = 0.0 %; act 7.174/wb 8.102 | leaky; input 0 = 0.0 %; act 7.174/wb 8.102 | table; input 0 = 0.0 %; act 7.174/wb 8.070 | table; input 0 = 0.0 %; act 7.174/wb 8.070 |
| Pool1 | none; input 0 = 54.1 %; act 0/wb 0 | none; input 0 = 24.2 %; act 0/wb 0 | none; input 0 = 11.0 %; act 0/wb 0 | none; input 0 = 5.4 %; act 0/wb 0 |
| Conv2 | relu; input 0 = 43.5 %; act 3.590/wb 3.700 | leaky; input 0 = 24.3 %; act 3.590/wb 3.700 | table; input 0 = 11.0 %; act 3.590/wb 3.700 | table; input 0 = 5.9 %; act 3.590/wb 3.700 |
| Pool2 | none; input 0 = 94.4 %; act 0/wb 0 | none; input 0 = 9.0 %; act 0/wb 0 | none; input 0 = 3.9 %; act 0/wb 0 | none; input 0 = 8.6 %; act 0/wb 0 |
| Conv3 | relu; input 0 = 87.3 %; act 902/wb 1.012 | leaky; input 0 = 14.7 %; act 902/wb 1.012 | table; input 0 = 7.1 %; act 902/wb 1.012 | table; input 0 = 14.1 %; act 902/wb 1.012 |
| Dense | none; input 0 = 74.3 %; act 0/wb 0 | none; input 0 = 18.1 %; act 0/wb 0 | none; input 0 = 6.7 %; act 0/wb 0 | none; input 0 = 13.1 %; act 0/wb 0 |

### Ảnh 0, phần cứng dense

| hàm | tổng chu kỳ | µs @250 MHz | so với ReLU | % | Δ load_act | Δ writeback | Δ compute | Δ pha khác |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ReLU | 202.895 | 811.6 | 0 | +0.00 % | 0 | 0 | 0 | 0 |
| Leaky ReLU | 202.895 | 811.6 | 0 | +0.00 % | 0 | 0 | 0 | 0 |
| SiLU | 202.959 | 811.8 | +64 | +0.03 % | +96 | -32 | 0 | 0 |
| hard-swish | 202.959 | 811.8 | +64 | +0.03 % | +96 | -32 | 0 | 0 |

Số chu kỳ từng pha (cả mạng):

| pha | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| load_config | 123 | 123 | 123 | 123 |
| load_iact | 100 | 100 | 100 | 100 |
| load_wght | 23.328 | 23.328 | 23.328 | 23.328 |
| load_bias | 92 | 92 | 92 | 92 |
| load_quant | 240 | 240 | 240 | 240 |
| load_act | 0 | 0 | 96 | 96 |
| convert_iact | 10.376 | 10.376 | 10.376 | 10.376 |
| compute | 147.856 | 147.856 | 147.856 | 147.856 |
| writeback | 12.814 | 12.814 | 12.782 | 12.782 |
| pooling | 7.952 | 7.952 | 7.952 | 7.952 |
| readout | 14 | 14 | 14 | 14 |
| **tổng** | 202.895 | 202.895 | 202.959 | 202.959 |

Tổng chu kỳ và `compute` từng layer (Δ so với ReLU):

| layer | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Conv1 | 18.816 (compute 9.305) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Pool1 | 5.213 (compute 0) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Conv2 | 107.244 (compute 89.556) | 0 (compute 0) | +32 (compute 0) | +32 (compute 0) |
| Pool2 | 2.861 (compute 0) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Conv3 | 58.028 (compute 44.756) | 0 (compute 0) | +32 (compute 0) | +32 (compute 0) |
| Dense | 10.733 (compute 4.239) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |

Hàm kích hoạt chạy ở layer nào, số 0 ở input từng layer, chu kỳ khối kích hoạt (nằm trong writeback):

| layer | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Conv1 | relu; input 0 = 0.0 %; act 7.174/wb 8.102 | leaky; input 0 = 0.0 %; act 7.174/wb 8.102 | table; input 0 = 0.0 %; act 7.174/wb 8.070 | table; input 0 = 0.0 %; act 7.174/wb 8.070 |
| Pool1 | none; input 0 = 54.1 %; act 0/wb 0 | none; input 0 = 24.2 %; act 0/wb 0 | none; input 0 = 11.0 %; act 0/wb 0 | none; input 0 = 5.4 %; act 0/wb 0 |
| Conv2 | relu; input 0 = 43.5 %; act 3.590/wb 3.700 | leaky; input 0 = 24.3 %; act 3.590/wb 3.700 | table; input 0 = 11.0 %; act 3.590/wb 3.700 | table; input 0 = 5.9 %; act 3.590/wb 3.700 |
| Pool2 | none; input 0 = 94.4 %; act 0/wb 0 | none; input 0 = 9.0 %; act 0/wb 0 | none; input 0 = 3.9 %; act 0/wb 0 | none; input 0 = 8.6 %; act 0/wb 0 |
| Conv3 | relu; input 0 = 87.3 %; act 902/wb 1.012 | leaky; input 0 = 14.7 %; act 902/wb 1.012 | table; input 0 = 7.1 %; act 902/wb 1.012 | table; input 0 = 14.1 %; act 902/wb 1.012 |
| Dense | none; input 0 = 74.3 %; act 0/wb 0 | none; input 0 = 18.1 %; act 0/wb 0 | none; input 0 = 6.7 %; act 0/wb 0 | none; input 0 = 13.1 %; act 0/wb 0 |

### Ảnh 1, phần cứng sparse

| hàm | tổng chu kỳ | µs @250 MHz | so với ReLU | % | Δ load_act | Δ writeback | Δ compute | Δ pha khác |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ReLU | 197.614 | 790.5 | 0 | +0.00 % | 0 | 0 | 0 | 0 |
| Leaky ReLU | 216.397 | 865.6 | +18.783 | +9.50 % | 0 | 0 | +18.783 | 0 |
| SiLU | 217.799 | 871.2 | +20.185 | +10.21 % | +96 | -32 | +20.121 | 0 |
| hard-swish | 217.481 | 869.9 | +19.867 | +10.05 % | +96 | -32 | +19.803 | 0 |

Số chu kỳ từng pha (cả mạng):

| pha | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| load_config | 123 | 123 | 123 | 123 |
| load_iact | 100 | 100 | 100 | 100 |
| load_wght | 38.880 | 38.880 | 38.880 | 38.880 |
| load_bias | 92 | 92 | 92 | 92 |
| load_quant | 240 | 240 | 240 | 240 |
| load_act | 0 | 0 | 96 | 96 |
| convert_iact | 10.376 | 10.376 | 10.376 | 10.376 |
| compute | 127.023 | 145.806 | 147.144 | 146.826 |
| writeback | 12.814 | 12.814 | 12.782 | 12.782 |
| pooling | 7.952 | 7.952 | 7.952 | 7.952 |
| readout | 14 | 14 | 14 | 14 |
| **tổng** | 197.614 | 216.397 | 217.799 | 217.481 |

Tổng chu kỳ và `compute` từng layer (Δ so với ReLU):

| layer | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Conv1 | 19.189 (compute 9.582) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Pool1 | 5.213 (compute 0) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Conv2 | 105.002 (compute 81.170) | +7.367 (compute +7.367) | +8.275 (compute +8.243) | +8.352 (compute +8.320) |
| Pool2 | 2.861 (compute 0) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Conv3 | 52.318 (compute 32.902) | +10.476 (compute +10.476) | +10.924 (compute +10.892) | +10.604 (compute +10.572) |
| Dense | 13.031 (compute 3.369) | +940 (compute +940) | +986 (compute +986) | +911 (compute +911) |

Hàm kích hoạt chạy ở layer nào, số 0 ở input từng layer, chu kỳ khối kích hoạt (nằm trong writeback):

| layer | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Conv1 | relu; input 0 = 0.0 %; act 7.174/wb 8.102 | leaky; input 0 = 0.0 %; act 7.174/wb 8.102 | table; input 0 = 0.0 %; act 7.174/wb 8.070 | table; input 0 = 0.0 %; act 7.174/wb 8.070 |
| Pool1 | none; input 0 = 55.2 %; act 0/wb 0 | none; input 0 = 21.9 %; act 0/wb 0 | none; input 0 = 9.6 %; act 0/wb 0 | none; input 0 = 5.6 %; act 0/wb 0 |
| Conv2 | relu; input 0 = 43.1 %; act 3.590/wb 3.700 | leaky; input 0 = 21.7 %; act 3.590/wb 3.700 | table; input 0 = 9.6 %; act 3.590/wb 3.700 | table; input 0 = 6.8 %; act 3.590/wb 3.700 |
| Pool2 | none; input 0 = 92.1 %; act 0/wb 0 | none; input 0 = 8.0 %; act 0/wb 0 | none; input 0 = 3.8 %; act 0/wb 0 | none; input 0 = 8.9 %; act 0/wb 0 |
| Conv3 | relu; input 0 = 82.0 %; act 902/wb 1.012 | leaky; input 0 = 13.5 %; act 902/wb 1.012 | table; input 0 = 6.7 %; act 902/wb 1.012 | table; input 0 = 15.0 %; act 902/wb 1.012 |
| Dense | none; input 0 = 77.8 %; act 0/wb 0 | none; input 0 = 13.5 %; act 0/wb 0 | none; input 0 = 6.2 %; act 0/wb 0 | none; input 0 = 16.0 %; act 0/wb 0 |

### Ảnh 6, phần cứng sparse

| hàm | tổng chu kỳ | µs @250 MHz | so với ReLU | % | Δ load_act | Δ writeback | Δ compute | Δ pha khác |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ReLU | 195.786 | 783.1 | 0 | +0.00 % | 0 | 0 | 0 | 0 |
| Leaky ReLU | 215.913 | 863.7 | +20.127 | +10.28 % | 0 | 0 | +20.127 | 0 |
| SiLU | 217.714 | 870.9 | +21.928 | +11.20 % | +96 | -32 | +21.864 | 0 |
| hard-swish | 217.366 | 869.5 | +21.580 | +11.02 % | +96 | -32 | +21.516 | 0 |

Số chu kỳ từng pha (cả mạng):

| pha | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| load_config | 123 | 123 | 123 | 123 |
| load_iact | 100 | 100 | 100 | 100 |
| load_wght | 38.880 | 38.880 | 38.880 | 38.880 |
| load_bias | 92 | 92 | 92 | 92 |
| load_quant | 240 | 240 | 240 | 240 |
| load_act | 0 | 0 | 96 | 96 |
| convert_iact | 10.376 | 10.376 | 10.376 | 10.376 |
| compute | 125.195 | 145.322 | 147.059 | 146.711 |
| writeback | 12.814 | 12.814 | 12.782 | 12.782 |
| pooling | 7.952 | 7.952 | 7.952 | 7.952 |
| readout | 14 | 14 | 14 | 14 |
| **tổng** | 195.786 | 215.913 | 217.714 | 217.366 |

Tổng chu kỳ và `compute` từng layer (Δ so với ReLU):

| layer | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Conv1 | 19.189 (compute 9.582) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Pool1 | 5.213 (compute 0) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Conv2 | 103.975 (compute 80.143) | +8.107 (compute +8.107) | +9.270 (compute +9.238) | +9.379 (compute +9.347) |
| Pool2 | 2.861 (compute 0) | 0 (compute 0) | 0 (compute 0) | 0 (compute 0) |
| Conv3 | 51.490 (compute 32.074) | +11.112 (compute +11.112) | +11.688 (compute +11.656) | +11.272 (compute +11.240) |
| Dense | 13.058 (compute 3.396) | +908 (compute +908) | +970 (compute +970) | +929 (compute +929) |

Hàm kích hoạt chạy ở layer nào, số 0 ở input từng layer, chu kỳ khối kích hoạt (nằm trong writeback):

| layer | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Conv1 | relu; input 0 = 0.1 %; act 7.174/wb 8.102 | leaky; input 0 = 0.1 %; act 7.174/wb 8.102 | table; input 0 = 0.1 %; act 7.174/wb 8.070 | table; input 0 = 0.1 %; act 7.174/wb 8.070 |
| Pool1 | none; input 0 = 54.6 %; act 0/wb 0 | none; input 0 = 23.1 %; act 0/wb 0 | none; input 0 = 10.2 %; act 0/wb 0 | none; input 0 = 5.3 %; act 0/wb 0 |
| Conv2 | relu; input 0 = 43.5 %; act 3.590/wb 3.700 | leaky; input 0 = 22.4 %; act 3.590/wb 3.700 | table; input 0 = 10.1 %; act 3.590/wb 3.700 | table; input 0 = 6.1 %; act 3.590/wb 3.700 |
| Pool2 | none; input 0 = 93.3 %; act 0/wb 0 | none; input 0 = 8.5 %; act 0/wb 0 | none; input 0 = 3.7 %; act 0/wb 0 | none; input 0 = 8.8 %; act 0/wb 0 |
| Conv3 | relu; input 0 = 83.5 %; act 902/wb 1.012 | leaky; input 0 = 14.3 %; act 902/wb 1.012 | table; input 0 = 6.8 %; act 902/wb 1.012 | table; input 0 = 14.8 %; act 902/wb 1.012 |
| Dense | none; input 0 = 76.0 %; act 0/wb 0 | none; input 0 = 13.6 %; act 0/wb 0 | none; input 0 = 6.1 %; act 0/wb 0 | none; input 0 = 13.0 %; act 0/wb 0 |
