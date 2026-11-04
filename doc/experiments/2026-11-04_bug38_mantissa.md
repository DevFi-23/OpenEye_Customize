# 2026-11-04: bug #38, the requantization mantissa cut to 8 bits (fixed, approved by the user)

## 1. The bug

Every entry of the quantization table is offset 8 + exponent 7 + mantissa 25 bits (`conv_mapper.write_quant_and_offset`,
`QUANT_TRANS_WIDTH`), and the quantizers multiply with a 25-bit signed mantissa (`quantization_unit.v`, `MANT_WIDTH` 25).
In between, `OpenEye_FPGA.v` cut the fields out of `quant_reg` with the wrong width:

```verilog
assign quant_exp[f]  = quant_reg[OFFSET_WIDTH + base +: OFFSET_WIDTH];                 // 8 bits into the 7-bit quant_exp
assign quant_mant[f] = quant_reg[OFFSET_WIDTH + EXPONENT_WIDTH + base +: OFFSET_WIDTH]; // 8 bits into the 25-bit quant_mant
```

The exponent came out right (8 bits into a 7-bit wire: the extra top bit, mantissa bit 0, was dropped), the mantissa lost
bits 8 ... 24, so a multiplier `mant >= 256` worked as `mant mod 256`. Verilator had flagged both lines all along (lint
baseline: `WIDTHEXPAND ... expects 25 bits ... SEL generates 8 bits`, `WIDTHTRUNC ... expects 7 bits ... generates 8 bits`).
No test noticed it because the toolchain kept every mantissa below 256 on purpose (`onnx2model.MANT_BITS = 8`, "the RTL
multiplies by 8 bits of the 25-bit mantissa field"; note (F) of README section 8d), and the random models use multiplier 1.

## 2. The fix

| File | Change |
|---|---|
| `hdl/OpenEye_FPGA.v` | the exponent slice `+:EXPONENT_WIDTH`, the mantissa slice `+:MANTISSA_WIDTH` |
| `src/open_eye/onnx2model.py` | `MANT_BITS` 8 -> **24** (the quantizer's mantissa is signed 25-bit, so 24 bits are the most; it is also float32's significand, so the multiplier equals ONNX Runtime's float32 scale); `hardware_multiplier` reads it at call time; the Leaky ReLU negative slope keeps 8 bits (`NEG_MANT_BITS`, its status field `act_neg_mant` is 8 bits) |
| `src/open_eye/data_create.py` | test hook `OPENEYE_QUANT_MANT=<m>` with `OPENEYE_QUANT_SHIFT=<s>`: every Conv/Dense requantizes with `[m, s]` |
| `test/cocotb_fpga/test_quant_mantissa.py` (new) | Conv -> Conv with a 17-bit (127,909, shift 23) and a 24-bit mantissa (11,920,113, shift 29), Dense -> Dense with the 24-bit one |
| `test/test_onnx_model_flow.py`, `test/test_activation.py` | the multiplier expectations of 24 bits, the 8-bit negative slope |

The widths of the datapath already allowed it: the sum is 21 bits (20-bit psum + offset), the product 46 bits
(`PROD_WIDTH`), `mant x sum < 2^24 x 2^20`; with 24 bits the shifts of the trained models become 31 ... 35 (were 15 ... 19),
below the rounding limit `ACT_ROUND_SHIFT_MAX` = 45 and the 7-bit field.

## 3. Verification

| Check | Result |
|---|---|
| `test_quant_mantissa.py` on the old RTL (negative control) | 3/3 FAIL: every output 0x00 or 0xff (the multiplier mod 256 with shift 23 / 29 is about 0), the reference spans the int8 range |
| ... on the fixed RTL | **3/3 PASS** |
| Lint | `fpga` 459 -> **457**: exactly the two warnings of these slices are gone, 0 new |
| Python unit tests | 328 pass, the 11 old fails |
| Precision against ONNX Runtime, 4 trained models x 20 test images (section 4) | slightly closer: exact match up to +0.9 points per layer, largest difference 3 -> 2 (ReLU conv3), 2 -> 1 (SiLU conv1), 3 -> 1 (hard-swish conv1); 20/20 right with both |
| RTL regression: the 184 tests + the 3 new = 187 | **182 PASS + 5 known xfail, 0 FAIL**; the 8 trained-model tests (now 24-bit mantissas) bit-exact |
| The 12 baseline cases (`doc/perf/baseline_2026-11-02`) | 12/12 identical: 0 cycles, 0 DMA words (they use multiplier 1) |
| Trained models, image 0, cycles (`doc/perf/activation_2026-11-04_mant24.md`) | ReLU 218,925 -> 218,924 (-1, in the Dense layer), Leaky ReLU 238,049 (0), SiLU 240,229 -> 240,230 (+1, Dense), hard-swish 240,293 -> 240,287 (-6, Dense); 4/4 PASS bit-exact; the zero shares of the layer inputs barely move (SiLU conv3 7.2 -> 7.1 %, Dense 6.6 -> 6.7 %): a few rounded values of conv3 cross zero and the PEs skip zeros |
| Vivado 4 ns (`doc/synth/2026-11-04_route4ns_fix38_zu7ev/`) | 0 CRITICAL, the same warnings; WNS +0.211 / +0.044 ns (250 MHz met); BRAM / URAM / DSP 192 / 12 / 4 unchanged; per quantizer +69 LUT, +17 FF (25 x 21 bit product: 1 DSP plus LUTs, `mant_s1` 8 -> 25 bit); worst routed path psum address -> psum BRAM, not a quantizer |

## 4. Precision: reference (= RTL) against ONNX Runtime

Test images 0 ... 19; per layer: share of values equal to ONNX Runtime / largest difference
(`venv/bin/python doc/experiments/2026-11-04_bug38/precision.py 20`). The remaining differences are rounding: ReLU floors (mean -0.28 at conv1), ONNX Runtime
rounds twice for SiLU and hard-swish.

| Model | Layer | 8-bit mantissa | 24-bit mantissa |
|---|---|---:|---:|
| ReLU | conv1 / conv2 / conv3 | 72.0 % / 97.2 % / 84.0 %, max 1 / 2 / 3 | 72.3 % / 97.3 % / 84.9 %, max 1 / 2 / **2** |
| Leaky ReLU | conv1 / conv2 / conv3 | 85.8 / 83.0 / 79.1 %, max 1 / 2 / 3 | 85.9 / 83.7 / 79.0 %, max 1 / 2 / 3 |
| SiLU | conv1 / conv2 / conv3 | 91.9 / 84.8 / 80.2 %, max 2 / 3 / 4 | 92.0 / 85.2 / 80.1 %, max **1** / 3 / 5 |
| hard-swish | conv1 / conv2 / conv3 | 98.8 / 91.1 / 87.5 %, max 3 / 3 / 3 | 99.0 / 91.8 / 88.4 %, max **1** / 3 / 3 |

The multiplier error itself drops from up to 0.2 % (8 bits, e.g. 0.0033496 -> 220 / 2^16, -0.22 %) to below 1e-7.
