# Vivado place and route after the bug #13 fix: 2026-10-14, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl` with `run_impl 1`, exported from `dev` at 5f1e66e (fix of bug #13 in
`hdl/iact_stream_constructor.v`). Same configuration (`config.json`) and flow as `../2026-10-13_route4ns_zu7ev`, so the two runs
differ only by the fix. **This is the current hardware baseline.**

## Result

| | Before the fix (2026-10-13) | **After the fix** |
|---|---:|---:|
| CRITICAL WARNING Synth 8-6858/8-6859 (multi-driven `rd_cycle_loop_cnt_0..3`) | 200 (capped) | **0** |
| ERROR | 0 | 0 |
| WNS post-synthesis / post-route at 4 ns | +0.205 / +0.025 ns | +0.215 / **+0.117 ns** |
| WHS post-route | +0.010 ns | +0.005 ns (met) |
| fmax post-route = 1000/(4 - WNS) | ~251.6 MHz | **~257.5 MHz** (250 MHz target met) |
| CLB LUT post-synthesis / post-route | 65,600 / 63,942 | 65,727 / 63,961 |
| FF post-synthesis / post-route | 38,631 / 38,667 | 38,765 / 39,089 |
| Block RAM tile / URAM / DSP | 192 / 8 / 4 | 192 / 8 / 4 |

Per instance (post-synthesis, `utilization_hier.txt`), each of the 4 `iact_stream_constructor` gains exactly **+32 FF**
(306/305/312/306 -> 338/337/344/338), i.e. the 4 counters x 8 bit that Vivado used to drop, and +15 to +57 LUT for their
incrementers and comparators. All other blocks change by a few LUT (normal run-to-run variation). The post-route FF delta (+422) is
larger because `phys_opt_design` replicates high-fanout registers differently from run to run; the post-synthesis +134 is the
meaningful number.

The WNS difference (+0.025 -> +0.117 ns) is placement variation, not an effect of the fix: the worst paths are elsewhere.

## Worst setup paths after routing

| Family | Paths of 20 | Example |
|---|---:|---|
| Inside the PE array (`OpenEye_Parallel`) | 8 | weight SPad BRAM -> PE logic, 9 logic levels |
| `psum_pipeline` -> psum buffer BRAMs (wire delay) | 6 | as in the previous run |
| `wght_enable_i_reg` -> PE `wght_data_handler/overhead_reg` | 3 | 12 logic levels, 3.87 ns |
| `dma_storage` -> `psum_pipeline` | 3 | configuration fan-out |

## Warnings

No CRITICAL WARNING. The remaining synthesis warnings are the same IDs as before (Synth 8-7137, 8-6090, 8-6057, 8-689, unused
registers/ports removed); implementation warnings are the expected out-of-context ones (Route 35-198/35-197, DRC 23-814,
Timing 38-242). Full list: `vivado_warnings.txt`.
