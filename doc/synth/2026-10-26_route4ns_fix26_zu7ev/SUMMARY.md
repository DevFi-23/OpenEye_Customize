# Vivado place and route after the fix of bug #26: 2026-10-26, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, run in batch mode from WSL
(`C:/openeye_vivado/fix26_impl`). RTL = `dev` with the bug #26 fix on top of `../2026-10-21_route4ns_fix19_zu7ev`: the exported
sources differ from that run in one line of `OpenEye_FPGA.v` (`RECEIVE_PSUMS_TO_IACT`: the `x_pos` wrap also fires for a fully
connected layer, `| fully_connected_layer`) plus its comment; headers and every other file identical. Same configuration
(`config.json`) and flow. **This is the current hardware baseline.** (A first run on 2026-10-25 was cut off during placement
when the machine was shut down; this is the complete rerun.)

| | After bug #19 fix (fix19) | **After bug #26 fix** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warning IDs and counts | - | identical, except one more `DRC 23-814` ("design is seen as Out of Context", printed per DRC run) |
| WNS post-synthesis / post-route at 4 ns | +0.199 / +0.073 ns | +0.199 / **+0.028 ns** (250 MHz met) |
| WHS post-route | +0.007 ns | +0.011 ns |
| fmax post-route = 1000/(4 - WNS) | ~254.6 MHz | **~251.8 MHz** |
| CLB LUT post-synthesis / post-route | 65,545 / 63,910 | 65,541 / 63,856 (-4 / -54) |
| FF post-synthesis / post-route | 38,982 / 39,309 | 38,978 / 39,018 (-4 / -291) |
| CARRY8 / Block RAM tile / URAM / DSP | 3,288 / 192 / 8 / 4 | 3,289 / 192 / 8 / 4 |

- The change is one OR gate on the reset condition of `iact_to_psum_x_pos_counter`; the post-synthesis differences per module
  (`OpenEye_Parallel` -21 LUT, `dma_storage` +86 LUT, `psum_pipeline_inst` +13 LUT, none of them changed) and the post-route
  FF count (register replication in phys_opt) are synthesis and placement variation.
- Worst setup paths after routing (20): `wght_buffer` URAM (no output register) -> PE weight inputs (`wght_buffer/impl/
  gen_write_lane[0].mem_reg_uram_0/1` -> `pe_cluster/gen_X[*]`), the route-critical path known since the first post-route run
  (`../2026-10-13_route4ns_zu7ev`). None involves the write-back logic. The slack of these wire-dominated paths moves with
  placement (+0.028 here, +0.073 in fix19).

Files: `openeye_result.txt` (WNS lines), `timing_summary.txt` / `timing_paths.txt` (post-synthesis), `timing_summary_route.txt`,
`utilization.txt` / `utilization_hier.txt` (post-synthesis), `utilization_route.txt`, `vivado_warnings.txt`, `config.json`.
Checkpoints (`OpenEye_FPGA_synth.dcp`, `OpenEye_FPGA_route.dcp`) stay in `C:/openeye_vivado/fix26_impl/reports/`.
