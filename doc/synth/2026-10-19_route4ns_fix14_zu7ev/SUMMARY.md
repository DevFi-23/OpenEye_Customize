# Vivado place and route after the fix of bug #14: 2026-10-19, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, run in batch mode from WSL
(`C:/openeye_vivado/fix14_impl`), exported from `dev` with the bug #14 fix in `hdl/psum_pipeline.v` (on top of the fixes of
bugs #13 and #6/#7). Same configuration (`config.json`) and flow as `../2026-10-15_route4ns_fix67_zu7ev`.
**This is the current hardware baseline.**

| | After bugs #6/#7 fix (2026-10-15) | **After bug #14 fix** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Synth 8-6090 (`results_ready` blocking + non-blocking) | 10 | **0** |
| WNS post-synthesis / post-route at 4 ns | +0.192 / +0.048 ns | +0.219 / **+0.097 ns** (250 MHz met) |
| WHS post-route | +0.007 ns | +0.007 ns |
| fmax post-route = 1000/(4 - WNS) | ~253.0 MHz | **~256.2 MHz** |
| CLB LUT post-synthesis / post-route | 65,909 / 64,162 | 65,839 / 64,050 (-70 / -112) |
| FF post-synthesis / post-route | 38,868 / 39,192 | 38,859 / 39,184 (-9 / -8) |
| CARRY8 | 3,293 | 3,288 |
| Block RAM tile / URAM / DSP | 192 / 8 / 4 | 192 / 8 / 4 |
| `psum_pipeline_inst` LUT / FF (post-synthesis) | 2,417 / 1,513 | 2,405 / 1,511 |

The fix keeps the same logic function (one flip-flop, the same AND terms), so the resource changes are synthesis and
placement variation. The warning list differs from fix67 only by the 10 removed Synth 8-6090 messages (`vivado_warnings.txt`).

Worst setup paths after routing (20): `psum_pipeline_inst/psum_buffer_addr_array` -> psum buffer BRAM address pins (16, wire
delay), inside the psum buffer BRAM cascade (1), `OpenEye_Parallel` (2), `fsm_cycle_reg` (1). Same structure as before; the
results_ready logic is not on a critical path. The WNS difference is placement variation.
