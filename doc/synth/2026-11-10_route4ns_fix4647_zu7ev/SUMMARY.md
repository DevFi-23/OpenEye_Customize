# Vivado place and route after the fixes of #46 / #47 (default sparse build): 2026-11-10, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL
(`C:/openeye_vivado/fix4647_impl`, exported with `tools/export_vivado.py --clock-ns 4`, the default configuration). RTL:
`dev` with the fixes of bugs #46 / #47 (`PE.v` dense FSM, `data_pipeline_wght.v` behind `!SPARSITY_EN`,
`doc/experiments/2026-11-10_bug46_47.md` section 6); the headers are identical to `../2026-11-09_route4ns_stride1_zu7ev`.

**Result: the same netlist as the hardware baseline `2026-11-09_route4ns_stride1_zu7ev`.** Both changes only exist in a
dense build (the dense FSM is a generate branch, `!SPARSITY_EN` is the constant 0), so the sparse build is unchanged:

| | stride1 (baseline) | fix4647 |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | 0 / 0 |
| Warnings | 311 | 311, the same list |
| WNS post-synthesis / post-route at 4 ns | +0.171 / +0.042 ns | +0.171 / +0.042 ns |
| CLB LUT post-synthesis / post-route | 61,674 / 59,548 | 61,674 / 59,548 |
| FF post-synthesis / post-route | 39,406 / 39,449 | 39,406 / 39,449 |
| CARRY8, Block RAM tile / URAM / DSP | 3,246, 188 / 12 / 4 | 3,246, 188 / 12 / 4 |

`utilization_route.txt` (resource table) and `utilization_hier.txt` are identical line for line apart from the header.
The hardware baseline stays `2026-11-09_route4ns_stride1_zu7ev` (same numbers). Checkpoints stay in
`C:/openeye_vivado/fix4647_impl/reports/`.
