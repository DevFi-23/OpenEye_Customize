# Vivado place and route after the fix of bug #38: 2026-11-04, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/fix38_impl`).
RTL = `dev` with the fix of `doc/experiments/2026-11-04_bug38_mantissa.md` on top of `../2026-11-03_route4ns_cr1fix_zu7ev`:
`OpenEye_FPGA.v` cuts the exponent and the mantissa of every quantization table entry with their own widths (7 and 25 bit)
instead of `OFFSET_WIDTH` (8). Same configuration (`config.json`, identical to cr1fix) and flow. **This is the current
hardware baseline.**

Before the fix the quantizers' 25-bit mantissa input had its bits 8 ... 24 tied to 0, so synthesis built an 8 x 21 bit
multiplier; now it is the full 25 x 21 bit one.

| | cr1fix | **fix38** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warnings | 311 | 311, the same list (only line numbers differ) |
| WNS post-synthesis / post-route at 4 ns | +0.211 / +0.075 ns | +0.211 / **+0.044 ns** (250 MHz met) |
| fmax post-route = 1000/(4 - WNS) | ~254.8 MHz | **~252.8 MHz** |
| CLB LUT post-synthesis / post-route | 62,680 / 60,643 | 62,998 / 60,936 (+318 / +293) |
| FF post-synthesis / post-route | 39,801 / 39,838 | 39,886 / 39,923 (+85 / +85) |
| Block RAM tile / URAM / DSP | 192 / 12 / 4 | **192 / 12 / 4** |
| one `quantization_unit` (post-synthesis, x 4) | 343 LUT, 97 FF, 1 DSP | **412 LUT, 114 FF, 1 DSP** |
| `psum_pipeline_inst` (post-synthesis) | 3,640 LUT, 1,581 FF | 3,916 LUT, 1,649 FF |

- Attributable: per quantizer **+69 LUT, +17 FF, 0 DSP**: the stage-1 register `mant_s1` is 25 bit instead of 8 (+17 FF),
  and the product no longer fits one DSP48E2 (27 x 18; the 21-bit sum and the 25-bit mantissa are both wider than 18 bit),
  so Vivado keeps 1 DSP per quantizer and builds the rest of the partial product in LUT/CARRY8 (CARRY8 +16). 4 quantizers =
  +276 LUT, +68 FF; the top level +8 LUT, +17 FF (the wider field multiplexers). The rest of the LUT difference (+34 in the
  unchanged `dma_storage`) is synthesis variation.
- Timing: post-synthesis identical (worst path the iact converter control, as before). After routing the worst path is
  `psum_pipeline_inst/psum_buffer_addr_array_reg` -> write enable of a psum buffer BRAM (1 LUT, 95 % routing), +0.044 ns: the
  known routing-dominated class of paths into the 144 psum buffer BRAMs, moved by the slightly larger `psum_pipeline`; no
  quantizer path among the 10 worst.
- Cycles: 0 change on the 12 baseline cases; trained models image 0 ReLU -1, SiLU +1 (different rounding, not the hardware).

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/fix38_impl/reports/`.
