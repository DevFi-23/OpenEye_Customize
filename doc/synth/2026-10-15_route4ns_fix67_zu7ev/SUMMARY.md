# Vivado place and route after the fixes of bugs #6/#7: 2026-10-15, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl` with `run_impl 1`, exported from `dev` at 949559e (fix of bugs #6/#7 in
`hdl/iact_stream_constructor.v`, on top of the bug #13 fix). Same configuration (`config.json`) and flow as
`../2026-10-14_route4ns_fix13_zu7ev`. The bug #18 fix (2026-10-15) is Python only and does not change the hardware.
**This is the current hardware baseline.**

| | After bug #13 fix (2026-10-14) | **After bugs #6/#7 fix** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| WNS post-synthesis / post-route at 4 ns | +0.215 / +0.117 ns | +0.192 / **+0.048 ns** (250 MHz met) |
| WHS post-route | +0.005 ns | +0.007 ns |
| fmax post-route = 1000/(4 - WNS) | ~257.5 MHz | **~253.0 MHz** |
| CLB LUT post-synthesis / post-route | 65,727 / 63,961 | 65,909 / 64,162 (+182 / +201) |
| FF post-synthesis / post-route | 38,765 / 39,089 | 38,868 / 39,192 (+103 / +103) |
| CARRY8 | 3,273 | 3,293 (+20) |
| Block RAM tile / URAM / DSP | 192 / 8 / 4 | 192 / 8 / 4 |

Per instance (post-synthesis): each of the 4 `iact_stream_constructor` gains **+25 to +26 FF** (338/337/344/338 ->
364/363/369/364) and +3 to +51 LUT: the one-channel address logic (`ram_wr_addr_q`, row/column counters) that synthesis used to
remove because nothing read it (lint `UNUSEDSIGNAL ram_wr_addr_q`). Matches the Yosys estimate (+104 FF). All other blocks
change by a few LUT (run-to-run variation). The WNS difference is placement variation.

Worst setup paths after routing (20): `psum_pipeline` -> psum buffer BRAMs (12, wire delay), inside the psum buffer BRAM
cascade (6), `fsm_cycle_reg` -> `router_configurator` (2).

Warnings: the same message IDs as before, no new ID; no CRITICAL WARNING. Full list: `vivado_warnings.txt`.
