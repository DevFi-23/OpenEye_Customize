# Vivado place and route after ending the weight send at wghts_per_pe + 1: 2026-11-02, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/wsend_impl`).
RTL = `dev` at `659b8d3`: on top of `../2026-10-31_route4ns_e78_zu7ev`, Process 5 of `OpenEye_FPGA.v` ends the weight
send at `fsm_sending_cycle > wghts_per_pe + 1` instead of `+ 2` (the RTL line of upstream `3258813`,
`doc/experiments/2026-10-31_wght_send_end.md`). Same configuration (`config.json`, identical to the e78 run) and flow.
**This is the current hardware baseline.**

| | e78 | **wsend (`+ 1`)** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warnings | 410 | 411: the same IDs and messages, plus one more `DRC 23-814` (out-of-context note printed once per DRC run; 4 instead of 3) |
| WNS post-synthesis / post-route at 4 ns | +0.205 / +0.074 ns | +0.205 / **+0.020 ns** (250 MHz met, 0 failing endpoints) |
| WHS post-route | +0.014 ns | +0.006 ns |
| fmax post-route = 1000/(4 - WNS) | ~254.7 MHz | **~251.3 MHz** |
| CLB LUT post-synthesis / post-route | 62,785 / 60,840 | 62,525 / 60,641 (-260 / -199) |
| FF post-synthesis / post-route | 39,468 / 39,796 | 39,466 / 39,790 (-2 / -6) |
| CARRY8 / Block RAM tile / URAM / DSP | 3,313 / 192 / 8 / 4 | 3,313 / 192 / 8 / 4 |
| `OpenEye_Parallel` (48 PEs) post-synthesis LUT / FF | 51,148 / 33,277 | 51,057 / 33,277 |
| `psum_pipeline_inst` post-synthesis LUT / FF | 3,087 / 1,525 | 3,084 / 1,525 |

- Resources: the change is the constant of one comparison. LUT -0.4 % post-synthesis, most of it (-91) in
  `OpenEye_Parallel`, which the change does not touch: optimisation noise of the same size as between earlier runs
  of unchanged modules (about +-30 to +-100 LUT).
- Timing: the post-synthesis worst path and slack are unchanged (+0.205 ns), so the logic depth did not change. After
  routing the worst path is now `fsm_cycle_reg[0]` -> `router_configurator_inst/router_mode_psum_o_reg[19]/CE`
  (13 logic levels, main FSM counter compare chain while configuring the routers, +0.020 ns); in the e78 run the worst
  path was `psum_pipeline_inst/psum_buffer_addr_array` -> psum buffer BRAM (+0.074 ns) and this router path was not
  among the ten worst (all >= +0.104 ns). Neither path contains the changed comparison (`fsm_sending_cycle`), so the
  smaller margin is placement and routing variation. The ten worst slacks are +0.020 ... +0.061 ns (e78: +0.074 ...
  +0.104 ns). 250 MHz is still met; the margin is the smallest of the post-route runs so far (earlier +0.025 to
  +0.117 ns).
- Cycles: `doc/perf/baseline_2026-11-02` (12 cases, -0 to -673 cycles against `baseline_2026-10-24`). With the
  post-route fmax of about 251 MHz the design is still timed at 250 MHz, so the latency gain is the cycle gain.

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/wsend_impl/reports/`.
