# Vivado place and route after the fix of bug #31 (EMPTY_PASS in PE.v): 2026-10-31, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/fix31_impl`).
RTL = `dev` with the bug #31 fix on top of `../2026-10-28_route4ns_clamp_zu7ev`: `PE.v` gets a state `EMPTY_PASS` and a 5-bit
hold counter in both FSMs (`doc/experiments/2026-10-30_bug31_fix.md`); the bug #32 fix of the same day is Python only. Same
configuration (`config.json`) and flow. **This is the current hardware baseline.**

| | int8 saturation (clamp) | **bug #31 fix** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warning IDs and counts | - | identical |
| WNS post-synthesis / post-route at 4 ns | +0.205 / +0.076 ns | +0.205 / **+0.074 ns** (250 MHz met) |
| WHS post-route | +0.011 ns | +0.014 ns |
| fmax post-route = 1000/(4 - WNS) | ~254.8 MHz | **~254.7 MHz** |
| CLB LUT post-synthesis / post-route | 66,511 / 64,801 | 62,785 / 60,840 (-3,726 / -3,961, -5.6 / -6.1 %) |
| FF post-synthesis / post-route | 38,990 / 39,316 | 39,468 / 39,796 (+478 / +480) |
| CARRY8 / Block RAM tile / URAM / DSP | 3,313 / 192 / 8 / 4 | 3,313 / 192 / 8 / 4 |
| `OpenEye_Parallel` (48 PEs) post-synthesis LUT / FF | 54,856 / 32,799 | 51,148 / 33,277 (-3,708 / +478) |
| `psum_pipeline_inst` post-synthesis LUT / FF | 3,089 / 1,525 | 3,087 / 1,525 |

- FF +10 per PE: the 5-bit hold counter and the state register. The LUT drop is not the fix itself: with 10 states instead
  of 9, Vivado's automatic FSM encoding of `gen_sparse_fsm.current_state_computing_reg` changed from `sequential` (4 bit)
  to `one-hot` (10 bit) (`Synth 8-3354`), and the one-hot state decoding is cheaper in this FSM (about -77 LUT per PE,
  +6 FF of the +10). The same saving would be available without the fix by forcing one-hot (`fsm_encoding`); not done.
- Worst setup path after routing as in earlier runs: `psum_pipeline_inst/psum_buffer_addr_array` -> psum buffer BRAM
  (+0.074 ns). Post-synthesis worst path unchanged (`dma_storage/pipe_chain_reg` -> `fsm_iact_params`, +0.205 ns).
- Cycles: 0 change on the 12 cases of `tools/run_profile.py --compare doc/perf/baseline_2026-10-24`.

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/fix31_impl/reports/`.
