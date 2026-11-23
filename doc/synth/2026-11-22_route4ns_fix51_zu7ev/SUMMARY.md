# Vivado place and route after the #51 fix: 2026-11-22, xczu7ev-ffvc1156-2-e, clock 4 ns

Run with Vivado 2024.2 (win64): `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, in batch mode from WSL, run on its
own. Exported with `tools/export_vivado.py --clock-ns 4 --name fix51_2026-11-22` to `C:/openeye_vivado/fix51_2026-11-22`,
in the default configuration (`config.json` identical to `2026-11-18_route4ns_default_zu7ev`): `SPARSITY_EN = 1`,
`STRIDE_ENABLED = 1`, `BIAS_PER_FILTER_EN = 1`, 2 × 2 clusters.

The RTL is `dev` after `f6df9af` plus the #51 fix: the branch `iact_converter_x <= iact_x_per_cluster` of the iact
converter in `OpenEye_FPGA.v` removed (3 lines; `doc/experiments/2026-11-22_bug50_51.md`). The #50 fix is Python only.
**It is the new hardware baseline of the default build.**

| | default 2026-11-18 | **fix51 2026-11-22** | change |
|---|---:|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** | |
| Warnings | 310 | 310 | same messages (ignoring paths and line numbers) |
| WNS post-synthesis / post-route at 4 ns | +0.218 / +0.096 ns | +0.210 / **+0.114 ns** (~257 MHz) | 250 MHz met |
| CLB LUT post-synthesis / post-route | 62,128 / 60,113 | 61,956 / **59,933** | −172 / −180 |
| of which LUT as memory (post-route) | 2,562 | 2,562 | 0 |
| FF post-synthesis / post-route | 39,521 / 39,556 | 39,527 / **39,568** | +6 / +12 |
| CARRY8, Block RAM tile / URAM / DSP | 3,249, 188 / 12 / 4 | 3,248, **188 / 12 / 4** | −1 CARRY8 |

- **The fix saves logic**: the removed branch was a 12-bit add and two compares feeding the converter x register;
  −172 LUT post-synthesis (−0.3 %). The FF and post-route differences are placement variation.
- **Worst post-route path**: the known kind, `psum_pipeline_inst/psum_buffer_addr_array_reg` to a psum buffer BRAM
  (address pin this time, write enable before), routing; not related to the change.

Files as in the earlier runs (`utilization*.txt`, `timing_*.txt`, `openeye_result.txt`, `vivado_warnings.txt`,
`config.json`). The checkpoints stay in `C:/openeye_vivado/fix51_2026-11-22/reports/`.
