# Vivado place and route after taking upstream e78e5b7: 2026-10-31, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/e78_impl`).
RTL = `dev` at `5595d15`: upstream `e78e5b7` cherry-picked on top of `../2026-10-30_route4ns_fix31_zu7ev`. The commit
removes one `temp_var = 0;` that sat outside the `if (!rst_n) ... else ...` of the asynchronous-reset block of Process 5
in `OpenEye_FPGA.v` (`temp_var` is a scratch variable set and cleared inside the weight-enable mask loop). Same
configuration (`config.json`, identical to the fix31 run) and flow. **This is the current hardware baseline.**

| | bug #31 fix (fix31) | **e78e5b7** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warnings | 410 | 410, the same IDs and messages (line numbers shift by one in `OpenEye_FPGA.v`) |
| WNS post-synthesis / post-route at 4 ns | +0.205 / +0.074 ns | +0.205 / **+0.074 ns** (250 MHz met) |
| fmax post-route = 1000/(4 - WNS) | ~254.7 MHz | **~254.7 MHz** |
| CLB LUT post-synthesis / post-route | 62,785 / 60,840 | 62,785 / 60,840 |
| FF post-synthesis / post-route | 39,468 / 39,796 | 39,468 / 39,796 |
| CARRY8 / Block RAM tile / URAM / DSP | 3,313 / 192 / 8 / 4 | 3,313 / 192 / 8 / 4 |

- Every report (`utilization*.txt`, `timing_summary_route.txt`, `timing_paths.txt`) is identical line by line to the
  fix31 run apart from the header (date, command). Vivado already built the same netlist with the old line: the
  change is a clean-up of the reset template, with no effect on the hardware.
- Cycles: 0 change on the 12 cases of `tools/run_profile.py --compare doc/perf/baseline_2026-10-24` and on the 16
  Table 3 configurations (`paper_table3_2026-10-26_fix25`); RTL regression 162 tests 157 PASS + 5 known xfail.

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/e78_impl/reports/`.
