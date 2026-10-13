# Vivado place and route, clock 4 ns (250 MHz): 2026-10-13, xczu7ev-ffvc1156-2-e

Vivado 2024.2 (win64), `synth_ooc.tcl` with `run_impl 1` from `tools/export_vivado.py` at 5695e57 (RTL identical to 8a5bbd2,
includes the GET_BIAS fix). Out of context, top `OpenEye_FPGA`, clock constraint read before `synth_design` (timing driven),
then `opt_design`, `place_design`, `phys_opt_design`, `route_design`. Configuration = latency baseline (`config.json`).
No ERROR. Route completed with all user timing constraints met.

## Result

| | Post-synthesis | Post-route |
|---|---:|---:|
| WNS (setup) at 4 ns | +0.205 ns | **+0.025 ns** |
| WHS (hold) | +0.026 ns | +0.010 ns |
| fmax = 1000/(4 - WNS) | ~263.5 MHz | **~251.6 MHz** (target met; the tool stops pushing once met, so this is a lower bound) |
| CLB LUT | 65,600 | 63,942 (27.8 %) |
| FF | 38,631 | 38,667 (8.4 %) |
| CLB sites used | | 12,015 / 28,800 (41.7 %) |
| Block RAM tile / URAM / DSP | 192 / 8 / 4 | 192 / 8 / 4 |

Latency at 250 MHz (cycles from doc/perf/baseline_2026-10-10, ideal memory): mnist1 65,800 cycles = 0.263 ms,
mnist2 87,032 = 0.348 ms, mnist3 26,728 = 0.107 ms.

## Critical paths after routing (20 worst setup paths)

| Family | Paths | Data path | Cause |
|---|---:|---|---|
| `psum_pipeline` registers (`psum_buffer_addr_array`, `psum_buffer_data_w`) -> psum buffer BRAM inputs | 12 | 3.56-3.69 ns, **0 logic levels, ~98 % routing** | Each of the 8 psum buffers is 18 cascaded RAMB36 (16,384 x 40 bit); one register drives address/data pins spread over 144 BRAMs across the die. Pure wire delay |
| `wght_buffer` URAM -> PE `wght_data_handler/overhead_reg` | 7 | 3.86-3.89 ns, 12-13 logic levels | URAM read without output pipeline register (Synth 8-6057) followed by 12 LUT levels to the PEs |
| `rst_sync_wrapper` -> `iact_buffer_SP` REGCEB | 1 | 3.68 ns, 0 levels | Reset fan-out (routing) |

The post-synthesis worst path (iact converter control, `OpenEye_FPGA.v` ~943-950, 17 levels) no longer appears in the 20 worst
paths after routing.

## Warnings

- Synthesis: identical set to 2026-10-12 (`../2026-10-12_synth4ns_zu7ev/SUMMARY.md`), including the CRITICAL WARNING
  Synth 8-6858/8-6859 of bug #13 (`iact_stream_constructor.v:475-478`). No new message ID.
- Implementation (new stage): only out-of-context messages, all expected:
  Route 35-198 (67 ports without HD.PARTPIN_LOCS, so the port-to-register paths are not timed), Route 35-197,
  DRC 23-814 (connectivity DRCs skipped in OOC), Timing 38-242 (HD.CLK_SRC not set, no clock-insertion estimate).
  No ERROR, no CRITICAL WARNING in opt/place/route.
