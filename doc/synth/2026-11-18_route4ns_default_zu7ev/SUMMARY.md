# Vivado place and route of the default build (bias table + #49 fix): 2026-11-18, xczu7ev-ffvc1156-2-e, clock 4 ns

Run with Vivado 2024.2 (win64): `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, in batch mode from WSL, run on its own. The design was exported with `tools/export_vivado.py --clock-ns 4 --name default_2026-11-18` to `C:/openeye_vivado/default_2026-11-18`, in the default configuration:
- `SPARSITY_EN = 1`
- `STRIDE_ENABLED = 1`
- `BIAS_PER_FILTER_EN = 1` (the default since 2026-11-17)

The RTL is `dev` `ae5665f`: the bias table plus the #49 fix in `psum_pipeline.v` (`gen_pair_ready_rows`). This run is step 0 of the per-layer plan (`doc/experiments/2026-11-18_layer_mode_study.md`). **It is the new hardware baseline of the default build.**

| | stride1 / fix4647 (2026-11-09/10, no bias table) | bias (2026-11-17, before #49) | **default 2026-11-18** | change vs bias |
|---|---:|---:|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | 0 / 0 | **0 / 0** | |
| Warnings | 311 | 310 | 310 | same IDs and counts |
| WNS post-synthesis / post-route at 4 ns | +0.171 / +0.042 ns | +0.218 / +0.026 ns | +0.218 / **+0.096 ns** (~256 MHz) | 250 MHz met |
| CLB LUT post-synthesis / post-route | 61,674 / 59,548 | 62,108 / 59,982 | 62,128 / **60,113** | +20 / +131 |
| of which LUT as memory (post-route) | 2,549 | 2,562 | 2,562 | 0 |
| FF post-synthesis / post-route | 39,406 / 39,449 | 39,513 / 39,548 | 39,521 / **39,556** | +8 / +8 |
| CARRY8, Block RAM tile / URAM / DSP | 3,246, 188 / 12 / 4 | 3,249, 188 / 12 / 4 | 3,249, **188 / 12 / 4** | 0 |
| `psum_pipeline_inst` LUT / FF (hierarchy, post-synthesis) | 3,918 / | 4,081 / 1,725 | 4,081 / 1,724 | 0 / −1 |

- **The #49 fix costs no measurable logic.** `psum_pipeline` has the same LUT count post-synthesis, and the post-synthesis total moves by +20 LUT. The +131 LUT post-route is placement variation, as is the better WNS (+0.096 against +0.026 ns).
- **Against the hardware baseline without the bias table** (stride1, 2026-11-09): +565 LUT (+0.9 %) and +107 FF post-route; BRAM, URAM and DSP unchanged.
- **Worst post-route path**: the known one, `psum_pipeline_inst/psum_buffer_addr_array_reg` to the write enable of a psum buffer BRAM (routing).

Files are as in the earlier runs. The checkpoints stay in `C:/openeye_vivado/default_2026-11-18/reports/`.
