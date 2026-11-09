# Vivado place and route with stride in the hardware (STRIDE_ENABLED = 1): 2026-11-09, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL
(`C:/openeye_vivado/stride1_impl`, exported with `tools/export_vivado.py --clock-ns 4 --set STRIDE_ENABLED=1`). RTL identical
to `../2026-11-08_route4ns_fix41_zu7ev` (the export differs in one line of `parameters_FPGA.vh`, `STRIDE_ENABLED = 1`);
`config.json` as fix41 plus `"STRIDE_ENABLED": 1`. Proposal 5 of README_FI 8e (approved 2026-11-09): with it the hardware
uses the stride of each layer's status registers instead of the constant 1.

| | fix41 (`STRIDE_ENABLED = 0`) | **stride1 (`STRIDE_ENABLED = 1`)** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warnings | 311 | 311, the same list |
| WNS post-synthesis / post-route at 4 ns | +0.196 / +0.009 ns | +0.171 / **+0.042 ns** (250 MHz met), hold met |
| fmax post-route = 1000/(4 - WNS) | ~250.6 MHz | **~252.7 MHz** |
| CLB LUT post-synthesis / post-route | 61,519 / 59,373 | 61,674 / **59,548** (+155 / +175, +0.25 / +0.29 %) |
| FF post-synthesis / post-route | 39,399 / 39,436 | 39,406 / **39,449** (+7 / +13) |
| CARRY8 | 3,242 | 3,246 (+4) |
| Block RAM tile / URAM / DSP | 188 / 12 / 4 | **188 / 12 / 4** |

- Where the LUTs go (post-synthesis, `utilization_hier.txt`): `dma_storage` +220 LUT, +8 FF (the 3-bit `stride_x` /
  `stride_y` fields of the status registers are used now and keep their decode); the four `iact_stream_constructor` did
  not grow (-7 ... -17 LUT, synthesis variation): `pec * stride_x_i` has a constant `pec` per PE column, which Vivado
  builds from shifts and adds. The Yosys estimate of +75 LUT per constructor (2026-11-07, module synthesised alone with a
  free stride input) was pessimistic.
- Timing: the worst routed path is `fsm_cycle_reg` -> `router_configurator_inst/router_mode_psum_o_reg` CE, 14 logic
  levels (6 CARRY8), the same path as the 2026-11-02 run; not on the stride logic. Post-route slack differs from run to
  run by placement (+0.009 fix41, +0.042 here, +0.077 rowO).
- Cycles of stride-1 layers: unchanged (README_FI 9, "STRIDE_ENABLED = 1 làm mặc định").

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/stride1_impl/reports/`.
