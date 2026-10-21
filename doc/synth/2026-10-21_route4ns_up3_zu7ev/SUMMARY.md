# Vivado place and route after taking 3 upstream commits: 2026-10-21, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, run in batch mode from WSL
(`C:/openeye_vivado/up3_impl`). RTL = `dev` after the cherry-picks of upstream `b6fa369` (comment), `2c8c324` (generate block
names in `OpenEye_Parallel.v`) and `2bf497d` (`PE.v` widths of `first_spad_words_wght` / `filters_reg_M0`), plus the explicit
zero extension of `filters_reg_M0`. Same configuration (`config.json`) and flow as `../2026-10-19_route4ns_fix14_zu7ev`.
**This is the current hardware baseline.**

| | After bug #14 fix (2026-10-19) | **After the 3 upstream commits** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Synth 8-689 (port width mismatch, `PE.v:2210/2211`) | 2 | **0** |
| WNS post-synthesis / post-route at 4 ns | +0.219 / +0.097 ns | +0.219 / **+0.070 ns** (250 MHz met) |
| WHS post-route | +0.007 ns | +0.006 ns |
| fmax post-route = 1000/(4 - WNS) | ~256.2 MHz | **~254.5 MHz** |
| CLB LUT post-synthesis / post-route | 65,839 / 64,050 | 65,630 / 63,970 (-209 / -80) |
| FF post-synthesis / post-route | 38,859 / 39,184 | 38,960 / 39,285 (+101 / +101) |
| One PE (`gen_X[0].gen_Y[0].pe`), post-synthesis LUT / FF | 1,119 / 654 | 1,117 / 656 |
| CARRY8 / Block RAM tile / URAM / DSP | 3,288 / 192 / 8 / 4 | 3,288 / 192 / 8 / 4 |

- **+2 FF per PE (48 PEs = +96, plus noise):** `data_pipeline_wght.first_spad_words_o` is a 7-bit register. With the old 5-bit
  wire in `PE.v` its two upper bits had no load and synthesis removed them; now they are used.
- The warning list differs from fix14 only by the 2 removed Synth 8-689 messages (`vivado_warnings.txt`).
- Worst setup paths after routing (20): 18 inside one PE (`gen_sparse_fsm` state register -> clock enables of
  `iact_data_handler`, 3 logic levels, 89 % route delay), 2 from `psum_pipeline_inst` to the psum buffer BRAMs. Neither involves
  the changed signals; the WNS difference (+0.097 -> +0.070 ns) is placement variation.
