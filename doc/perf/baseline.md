# Latency and DMA bandwidth baseline (2026-10-09)

Single convolution layers on the `OpenEye_FPGA` top level, measured with the
cycle/DMA profiler (`rtl_test_utils.profile_dma_phases`, `OPENEYE_PROFILE=1`).
Code: branch `dev` on top of upstream `c4bd562`. Raw numbers: `baseline_2026-10-09.csv`.

## Reproduce and compare

Raw profiles of this baseline: `baseline_2026-10-09/<case>.json`. Rerun all cases and compare in one command:

```sh
venv/bin/python tools/run_profile.py --compare doc/perf/baseline_2026-10-09
```

Rerunning the unchanged RTL reproduces every number exactly (checked 2026-10-10: 0 change in all
6 cases), so any difference in a comparison comes from a code change.

All cases pass the testbench result check. Common setup: `Convolution_Single`, 3x3
kernel, 4 input channels, ramp activations, `CLUSTER_ROWS=2`, `CLUSTER_COLUMNS=2`,
`NUM_GLB_IACT=1`, `NUM_GLB_WGHT=3`, `NUM_GLB_PSUM=4`, 20-bit psums. The 5 cases with
`QUANT_AMOUNT=32` take about 15 s each; `QUANT_AMOUNT=1024` takes about 4 min.

## How to read the tables

- **Phases** follow the main FSM of `OpenEye_FPGA.v` (`load_*` = `GET_*` states,
  `convert_iact` = `START_CONVERTER`/`CONVERT_IACT`/`WAIT_CYCLE`, `compute` =
  `WAIT_FOR_RESULTS`); `readout` is the psum FSM in `PSUM_SEND_RESULTS`.
- The window runs from the first accepted input word to the last output word.
- **payload B** is the minimum a phase has to move: iact `X*Y*C`, weights `F*C*Kx*Ky`,
  bias one psum per filter, quantization one 40-bit entry per filter, readout
  one psum per output.
- **bus eff.** = payload bytes / (DMA words x DMA width). 100% means every bit on
  the bus is needed data.
- **DMA busy** = cycles with a DMA word in or out / total cycles. There is one DMA
  link, used in one direction at a time.
- `1 refused`: the host driver repeats its last word for one cycle after the
  stream; the DUT refuses it. No data is lost.

## Results


### 8x1_f4_q1024_dma64
Convolution_Single 8x1x4 k3x3 f4 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 1024
total 1188 cycles (11880 ns), compute 13.6%, DMA busy 71.2% of cycles

| phase | cycles | share | DMA in | DMA out | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 1.5% | 18 | 0 |  |  |
| load_iact | 4 | 0.3% | 4 | 0 | 32 | 100% |
| load_wght | 120 | 10.1% | 120 | 0 | 144 | 15% |
| load_bias | 32 | 2.7% | 32 | 0 | 12 | 5% |
| load_quant | 640 | 53.9% | 640 | 0 | 20 | 0% |
| convert_iact | 179 | 15.1% | 0 (1 refused) | 0 |  |  |
| compute | 161 | 13.6% | 0 | 0 |  |  |
| readout | 34 | 2.9% | 0 | 32 | 96 | 38% |

### 8x1_f4_q32_dma64
Convolution_Single 8x1x4 k3x3 f4 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32
total 568 cycles (5680 ns), compute 28.3%, DMA busy 39.8% of cycles

| phase | cycles | share | DMA in | DMA out | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 3.2% | 18 | 0 |  |  |
| load_iact | 4 | 0.7% | 4 | 0 | 32 | 100% |
| load_wght | 120 | 21.1% | 120 | 0 | 144 | 15% |
| load_bias | 32 | 5.6% | 32 | 0 | 12 | 5% |
| load_quant | 20 | 3.5% | 20 | 0 | 20 | 12% |
| convert_iact | 179 | 31.5% | 0 (1 refused) | 0 |  |  |
| compute | 161 | 28.3% | 0 | 0 |  |  |
| readout | 34 | 6.0% | 0 | 32 | 96 | 38% |

### 16x3_f4_q32_dma64
Convolution_Single 16x3x4 k3x3 f4 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32
total 984 cycles (9840 ns), compute 36.3%, DMA busy 38.0% of cycles

| phase | cycles | share | DMA in | DMA out | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 1.8% | 18 | 0 |  |  |
| load_iact | 24 | 2.4% | 24 | 0 | 192 | 100% |
| load_wght | 120 | 12.2% | 120 | 0 | 144 | 15% |
| load_bias | 96 | 9.8% | 96 | 0 | 12 | 2% |
| load_quant | 20 | 2.0% | 20 | 0 | 20 | 12% |
| convert_iact | 251 | 25.5% | 0 (1 refused) | 0 |  |  |
| compute | 357 | 36.3% | 0 | 0 |  |  |
| readout | 98 | 10.0% | 0 | 96 | 576 | 75% |

### 32x3_f4_q32_dma64
Convolution_Single 32x3x4 k3x3 f4 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32
total 1672 cycles (16720 ns), compute 40.0%, DMA busy 35.3% of cycles

| phase | cycles | share | DMA in | DMA out | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 1.1% | 18 | 0 |  |  |
| load_iact | 48 | 2.9% | 48 | 0 | 384 | 100% |
| load_wght | 120 | 7.2% | 120 | 0 | 144 | 15% |
| load_bias | 192 | 11.5% | 192 | 0 | 12 | 1% |
| load_quant | 20 | 1.2% | 20 | 0 | 20 | 12% |
| convert_iact | 411 | 24.6% | 0 (1 refused) | 0 |  |  |
| compute | 669 | 40.0% | 0 | 0 |  |  |
| readout | 194 | 11.6% | 0 | 192 | 1152 | 75% |

### 32x3_f16_q32_dma64
Convolution_Single 32x3x4 k3x3 f16 | 2x2 clusters, DMA 64 b, psum 20 b, QUANT_AMOUNT 32
total 3652 cycles (36520 ns), compute 31.1%, DMA busy 57.6% of cycles

| phase | cycles | share | DMA in | DMA out | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|
| load_config | 18 | 0.5% | 18 | 0 |  |  |
| load_iact | 48 | 1.3% | 48 | 0 | 384 | 100% |
| load_wght | 480 | 13.1% | 480 | 0 | 576 | 15% |
| load_bias | 768 | 21.0% | 768 | 0 | 48 | 1% |
| load_quant | 20 | 0.5% | 20 | 0 | 80 | 50% |
| convert_iact | 411 | 11.3% | 0 (1 refused) | 0 |  |  |
| compute | 1137 | 31.1% | 0 | 0 |  |  |
| readout | 770 | 21.1% | 0 | 768 | 4608 | 75% |

### 32x3_f4_q32_dma32
Convolution_Single 32x3x4 k3x3 f4 | 2x2 clusters, DMA 32 b, psum 20 b, QUANT_AMOUNT 32
total 2236 cycles (22360 ns), compute 29.9%, DMA busy 51.6% of cycles

| phase | cycles | share | DMA in | DMA out | payload B | bus eff. |
|---|---:|---:|---:|---:|---:|---:|
| load_config | 34 | 1.5% | 34 | 0 |  |  |
| load_iact | 96 | 4.3% | 96 | 0 | 384 | 100% |
| load_wght | 216 | 9.7% | 216 | 0 | 144 | 17% |
| load_bias | 384 | 17.2% | 384 | 0 | 12 | 1% |
| load_quant | 40 | 1.8% | 40 | 0 | 20 | 12% |
| convert_iact | 411 | 18.4% | 0 (1 refused) | 0 |  |  |
| compute | 669 | 29.9% | 0 | 0 |  |  |
| readout | 386 | 17.3% | 0 | 384 | 1152 | 75% |

## Observations

1. **Compute is 14-40% of the layer latency.** Every phase runs strictly after the
   previous one; nothing overlaps.
2. **The DMA link is idle 42-65% of the time** (DMA busy 35-58% with
   `QUANT_AMOUNT=32`), yet most transferred words carry little payload.
3. **Bias is sent per output pixel, not per filter**: 1-5% bus efficiency. It
   scales with the output size (192 words at 32x3x4f, 768 at 32x3x16f, which is
   21% of the 16-filter layer).
4. **Weights use 15% of the bus**: 30 words per 3x3x4 filter (36 bytes, 4.5 words
   at 64 bit). Halving the bus to 32 bit costs only 120 -> 216 words, so the
   encoding, not the bus width, limits this phase. Needs investigation.
5. **The quantization table is sent in full** (`QUANT_AMOUNT` entries) whatever the
   filter count: 640 words (54% of the layer) at `QUANT_AMOUNT=1024`, 20 words at 32.
   `QUANT_AMOUNT=1024` also makes the simulation about 16x slower (244 s vs 15 s).
6. **Readout carries 20-bit psums in 32-bit slots** (75% at best, 38% for the
   8-wide layer, which sends one psum per word). Results are not quantized to
   int8 before leaving the chip.
7. **`convert_iact` costs 11-32%** with no DMA traffic; it grows with the input
   height (179 -> 411 cycles from 8x1 to 32x3).
8. **32-bit DMA**: +34% latency for 32x3x4f (1672 -> 2236 cycles).

## Upper-bound estimates for the 32x3, 16-filter layer (3652 cycles)

If only the DMA words of one phase shrink to its payload (everything else unchanged):

| change | words before -> after | cycles saved |
|---|---|---:|
| bias per filter | 768 -> 6 | ~760 |
| weights packed densely | 480 -> 72 | ~400 |
| readout as int8 | 768 -> 192 | ~575 |

Together about 1,700 cycles (~48%). These are bounds on the DMA time, not
measured results; each needs an RTL change and a new measurement.

## Limits of this baseline

- Small single layers only; multi-layer runs and pooling are not profiled here.
- The host is always ready and has no memory latency (testbench `chance = 100`),
  so the numbers are a best case for the external memory side.
