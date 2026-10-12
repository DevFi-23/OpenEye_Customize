# Vivado synthesis, clock 4 ns: 2026-10-12 23:13, xczu7ev-ffvc1156-2-e

Second run in the same Vivado session as `../2026-10-12_baseline_zu7ev` (journal: `set run_impl 1`,
`set argv [list xczu7ev-ffvc1156-2-e 4]; set argc 2`, `source synth_ooc.tcl`). Same configuration and RTL (6512827 sources
exported at 8a5bbd2; RTL identical).

**Place and route did NOT run.** The folder on C: was exported before the `impl` option existed (synth_ooc.tcl of 20:58 has no
`run_impl`), so the script ignored `run_impl` and only synthesised again. That old script also applies the clock constraint only
after `synth_design`, so this synthesis was not timing driven either: the result is the same netlist evaluated against 4 ns.

| | 10 ns run | 4 ns run |
|---|---:|---:|
| WNS | +6.116 ns | +0.116 ns |
| Worst path | 3.865 ns | 3.884 ns |
| fmax estimate (post-synthesis) | ~257 MHz | ~257 MHz |
| Hold (WHS) | +0.026 ns | +0.026 ns |
| LUT / FF | 64,540 / 38,655 | 64,553 / 38,639 (run-to-run noise) |

## Warnings (`vivado_warnings.txt`; Vivado prints at most 100 messages per ID)

| ID | Count | Where | Meaning |
|---|---:|---|---|
| **Synth 8-6858/8-6859 (CRITICAL)** | 200 (capped) | `iact_stream_constructor.v:475-478` | `rd_cycle_loop_cnt_0..3` are reset in one always block (line 437) and counted in another (line 233). Vivado keeps the constant (reset) driver and **ignores the counter logic**: in hardware the four counters stay 0. Simulators let the last write win, so simulation does not show it. New bug #13 |
| Synth 8-6090 | 3 | `psum_pipeline.v:485/522/900` | `results_ready` written with blocking and non-blocking assignments, "entire logic could be removed" (the BLKANDNBLK lint warning, #11) |
| Synth 8-7137 | 12 | `psum_pipeline.v:322/776`, `OpenEye_Parallel.v:443/448`, `PE.v:1113` | Register with set and reset of equal priority, "may cause simulation mismatches" |
| Synth 8-689 | 2 | `PE.v:2210/2211` | Port width mismatch 5 vs 7 and 6 vs 8 bit (lint #11) |
| Synth 8-6057 | 4+ | iact_layer_buffer (URAM) | URAM without output pipeline register: can limit fmax after routing |
| Synth 8-10788 | 1 | `OpenEye_FPGA.v:241` | `$ceil` of an integer: harmless |
| Synth 8-3332/8-6014/8-7129 | 100 each (capped) | many | Unused registers/ports removed: normal for a parameterised design |
| Timing 38-242 | 1 | clk_i | HD.CLK_SRC not set in OOC: only the clock skew estimate is missing |
| filemgmt 56-12 | 39 | all sources | Second `source` in the same session re-read the files: harmless |
