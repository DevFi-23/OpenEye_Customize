# Vivado place and route after the fix of bug #19: 2026-10-21, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, run in batch mode from WSL
(`C:/openeye_vivado/fix19_impl`). RTL = `dev` with the bug #19 fix (`iact_stream_constructor.v`: `x_pos_in_w_cycle` 8 -> 12 bit;
`OpenEye_FPGA.v`: FC store condition does not use the sign of `current_x`) on top of `../2026-10-21_route4ns_up3_zu7ev`. Same
configuration (`config.json`) and flow. **This is the current hardware baseline.**

| | After the upstream commits (up3) | **After bug #19 fix** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warning IDs and counts | - | identical |
| WNS post-synthesis / post-route at 4 ns | +0.219 / +0.070 ns | +0.199 / **+0.073 ns** (250 MHz met) |
| WHS post-route | +0.006 ns | +0.007 ns |
| fmax post-route = 1000/(4 - WNS) | ~254.5 MHz | **~254.6 MHz** |
| CLB LUT post-synthesis / post-route | 65,630 / 63,970 | 65,545 / 63,910 (-85 / -60) |
| FF post-synthesis / post-route | 38,960 / 39,285 | 38,982 / 39,309 (+22 / +24) |
| One `iact_stream_constructor`, post-synthesis LUT / FF | 569 / 364 | 579 / 367 |
| CARRY8 / Block RAM tile / URAM / DSP | 3,288 / 192 / 8 / 4 | 3,288 / 192 / 8 / 4 |

- The four wider counters cost about +3 FF and +10 LUT per constructor; the rest of the differences is synthesis and placement
  variation.
- Worst setup paths after routing (20): `psum_pipeline_inst/psum_buffer_addr_array` -> psum buffer BRAM address pins (19, 0 logic
  levels, wire delay), `fsm_cycle_reg` (1). None involves `x_pos_in_w_cycle` or `current_x`.
