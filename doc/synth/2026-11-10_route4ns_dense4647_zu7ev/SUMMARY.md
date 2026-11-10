# Vivado place and route of the dense hardware after the fixes of #46 / #47: 2026-11-10, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL
(`C:/openeye_vivado/dense4647_impl`, exported with `tools/export_vivado.py --clock-ns 4 --set SPARSITY_EN=0`). The same
configuration as `../2026-11-09_route4ns_dense_zu7ev` (dense before the fixes), now with the RTL fixes of #46 / #47
(`doc/experiments/2026-11-10_bug46_47.md`): the dense mode is correct (`test_dense_mode.py`, the trained MNIST net
bit-exact), so this is the area of a verified dense design.

| | sparse (baseline `stride1`) | dense before the fixes | **dense, fixed** | fixed dense - sparse |
|---|---:|---:|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | 0 / 0 | **0 / 0** | |
| Warnings | 311 | 303 | 303 | |
| WNS post-synthesis / post-route at 4 ns | +0.171 / +0.042 ns | +0.202 / +0.062 ns | +0.202 / **+0.123 ns** (250 MHz met) | |
| CLB LUT post-synthesis / post-route | 61,674 / 59,548 | 44,141 / 43,554 | 44,109 / **43,523** | **-16,025 (-26.9 %)** |
| FF post-route | 39,449 | 28,797 | **28,797** | -10,652 (-27.0 %) |
| CARRY8 | 3,246 | 1,998 | 1,998 | |
| Block RAM tile / URAM / DSP | 188 / 12 / 4 | 184 / 10 / 4 | **184 / 10 / 4** | -4 / -2 / 0 |

- The fixes cost about 15-17 LUT per PE (the psum forwarding multiplexers of the dense `CALCULATING`); `OpenEye_Parallel`
  +464 LUT post-synthesis, the whole design -32 (the rest moves by synthesis variation). The weight pipeline change
  removes logic in a dense build (`raw_mode_i | !SPARSITY_EN` is constant 1).
- Warnings: the same list as before the fixes except one new "Port raw_mode_i in module data_pipeline_wght is either
  unconnected or has no load" (expected: in dense hardware every weight word is stored) and one PE_cluster port warning
  less (synthesis variation).
- Timing: worst post-route path `OpenEye_Parallel/router_mode_wght_reg` -> a PE's `wght_data_handler/data_storage_2_reg`
  (1 LUT level, routing); post-synthesis as before (`dma_storage` -> `fsm_iact_params_reg`, top level).

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/dense4647_impl/reports/`.
