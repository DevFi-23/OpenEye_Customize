# Vivado place and route of the dense hardware (SPARSITY_EN = 0): 2026-11-09, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL
(`C:/openeye_vivado/dense_impl`, exported with `tools/export_vivado.py --clock-ns 4 --set SPARSITY_EN=0`). RTL identical
to `../2026-11-09_route4ns_stride1_zu7ev` (the current hardware baseline; the only text difference is the unused
`USE_INTERNAL_PARAMS` default of `STRIDE_ENABLED`, both builds take 1 from `parameters_FPGA.vh`); the headers differ in
`SPARSITY_EN = 0` (FPGA, PE cluster, PE) and `TRANS_BITWIDTH_IACT` / `TRANS_BITWIDTH_WGHT` 16 instead of 24. Measurement
for `doc/experiments/2026-11-09_dense_vs_sparse.md`; the dense mode is not correct yet (bugs #46, #47 of README_FI 8b),
so this is the area of the dense datapath as it is in the RTL today, not of a verified design.

| | stride1 (sparse, baseline) | **dense** | dense - sparse |
|---|---:|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** | |
| Warnings | 311 | 303 | the sparse-only logic now removed as unused, see below |
| WNS post-synthesis / post-route at 4 ns | +0.171 / +0.042 ns | +0.202 / **+0.062 ns** (250 MHz met), hold met | |
| fmax post-route = 1000/(4 - WNS) | ~252.7 MHz | **~253.9 MHz** | within run-to-run placement noise |
| CLB LUT post-synthesis / post-route | 61,674 / 59,548 | 44,141 / **43,554** | -17,533 / **-15,994 (-26.9 %)** |
| FF post-synthesis / post-route | 39,406 / 39,449 | 28,676 / **28,797** | **-10,652 (-27.0 %)** |
| CARRY8 | 3,246 | 1,998 | -1,248 (-38 %) |
| Block RAM tile / URAM / DSP | 188 / 12 / 4 | **184 / 10 / 4** | -4 / -2 / 0 |

- Where the LUTs go (post-synthesis, `utilization_hier.txt`): `OpenEye_Parallel` -17,077 of the -17,533; every PE about
  1,000 -> 620 LUT (-38 %, the weight / iact address SPads, the overhead pipelines and the zero-skipping control of the
  sparse FSM are not generated), each `pe_cluster` about -4,500, `router_configurator` -615. The 16-bit instead of 24-bit
  iact / weight transfer words narrow the routers and GLB paths (4 BRAM tiles, 2 URAM less).
- New warnings against the baseline are sparse-only signals left unused (`overhead_next_word` of `data_pipeline_wght`
  without driver, `gen_dense_fsm.iact_addr_SPad_*` / `wght_addr_SPad_en_r` / `fast_cycle` removed, `over_ending`,
  `overhead_delay_reg`, `mem_data_overhead_reg`).
- Timing: worst post-synthesis path `dma_storage/pipe_chain_reg` -> `fsm_iact_params_reg` (17 logic levels, 6 CARRY8,
  top level); worst post-route path a reset synchronizer replica inside cluster (0,0) (0 logic levels, routing). Neither
  is in the PE, so the smaller PE does not raise the clock.

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/dense_impl/reports/`.
