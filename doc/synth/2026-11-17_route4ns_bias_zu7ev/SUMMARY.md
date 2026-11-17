# Vivado place and route with the bias table (BIAS_PER_FILTER_EN=1): 2026-11-17, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL
(`C:/openeye_vivado/bias_impl`, exported with `tools/export_vivado.py --clock-ns 4 --set BIAS_PER_FILTER_EN=1`, otherwise
the default configuration). RTL: `dev` `f435068` plus the bias-per-filter change (`psum_pipeline.v`, `OpenEye_FPGA.v`,
`regmap.yaml`; `doc/experiments/2026-11-17_bias_per_filter.md` section 6). Compared with the hardware baseline
`2026-11-09_route4ns_stride1_zu7ev` (= `2026-11-10_route4ns_fix4647_zu7ev`, same netlist).

| | baseline (stride1 / fix4647) | bias (`BIAS_PER_FILTER_EN=1`) | change |
|---|---:|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | 0 / 0 | |
| Warnings | 311 | 310 | same kinds, none about the new logic |
| WNS post-synthesis / post-route at 4 ns | +0.171 / +0.042 ns | +0.218 / +0.026 ns | 250 MHz met |
| CLB LUT post-synthesis / post-route | 61,674 / 59,548 | 62,108 / 59,982 | +434 (+0.7 %) |
| of which LUT as memory (post-route) | 2,549 | 2,562 | +13 (the bias table) |
| FF post-synthesis / post-route | 39,406 / 39,449 | 39,513 / 39,548 | +99 |
| CARRY8, Block RAM tile / URAM / DSP | 3,246, 188 / 12 / 4 | 3,249, 188 / 12 / 4 | +3, 0 |
| `psum_pipeline_inst` LUT (hierarchy, post-synthesis) | 3,918 | 4,081 | +163 |

The worst post-route path is the known one: `psum_pipeline_inst/psum_buffer_addr_array_reg` -> address pins of the psum
buffer BRAMs (routing); none of the 20 reported paths goes through the bias table or the rewrite counters. Built with
`BIAS_PER_FILTER_EN=0` (the default) the table and the rewrite are absent (generate / constant 0) and the 12 baseline
cases are cycle-identical; that build was not re-run in Vivado. Checkpoints stay in `C:/openeye_vivado/bias_impl/reports/`.
