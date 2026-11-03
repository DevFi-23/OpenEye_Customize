# Vivado place and route after the fixes of bugs #28, #29, #36: 2026-11-03, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/fixN_uram`).
RTL = `dev` with the fixes of `doc/experiments/2026-11-03_table3_cr1.md` on top of `../2026-11-02_route4ns_act_zu7ev`:
weight staging buffer `BUFFER_WIDTH_WGHT` 12 -> 13 (8,192 rows) placed in URAM (`RAM_SP` parameter `RamStyle("ultra")`), the
`CLUSTER_ROWS == 1` ready condition (#28) and the wider Dense read-out registers (#36). Same configuration (`config.json`,
the latency baseline CR 2 X 4 Y 3, now with `BUFFER_WIDTH_WGHT: 13`) and flow. **This is the current hardware baseline.**

At this configuration (CLUSTER_ROWS 2, NUM_GLB_PSUM 4) the #28 and #36 changes generate the old circuit by construction (the
new ready term exists only at CLUSTER_ROWS 1; the read-out registers keep their width when the psum bus is at least
CLUSTER_COLUMNS DMA words wide): `psum_pipeline_inst` 3,644 -> 3,640 LUT, 1,581 FF both. The cost is the deeper buffer.

| | act | **cr1fix (URAM)** | first run (Vivado's own choice) |
|---|---:|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** | 0 / 0 |
| Warnings | 311 | 311, the same list (only line numbers differ) | 310 |
| WNS post-synthesis / post-route at 4 ns | +0.203 / +0.045 ns | +0.211 / **+0.075 ns** (250 MHz met) | +0.231 / +0.054 ns |
| fmax post-route = 1000/(4 - WNS) | ~252.8 MHz | **~254.8 MHz** | ~253.4 MHz |
| CLB LUT post-synthesis / post-route | 63,440 / 61,419 | 62,680 / 60,643 | 64,415 / 62,266 |
| FF post-synthesis / post-route | 39,529 / 39,849 | 39,801 / 39,838 | 39,515 / 39,553 |
| Block RAM tile / URAM / DSP | 192 / 8 / 4 | **192 / 12 / 4** | **256** / 4 / 4 |
| `wght_buffer` (post-synthesis) | 427 LUT, 4 URAM | 422 LUT, 288 FF, 8 URAM | 845 LUT, 64 RAMB36 |

- Attributable: **+4 URAM** (8 -> 12 of 96) and 288 FF (the output register of the URAM cascade), no LUT, BRAM and DSP
  unchanged. The LUT difference of the whole design (-760 / -776) is synthesis variation: `OpenEye_Parallel`, not changed,
  moved by -742 LUT.
- Without the attribute (first run, `C:/openeye_vivado/fixN_impl`), Vivado put the 8,192 x 288-bit buffer into 64 RAMB36 with
  845 LUT of read multiplexers: Block RAM 192 -> 256 tiles (61.5 % -> 82 % of the chip), URAM 8 -> 4. Hence `RamStyle("ultra")`.
- Timing: the worst path after routing is again `fsm_cycle_reg` -> `router_configurator_inst/router_mode_psum_o_reg[19]/CE`
  (the main FSM's compare chain), +0.075 ns; the buffer is not on it.
- Cycles: 0 change on the 12 baseline cases; Table 3 16/16 (`doc/perf/paper_table3_2026-11-03`).

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/fixN_uram/reports/`.
