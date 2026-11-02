# Vivado place and route of the activation hardware (step B): 2026-11-02, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/act_impl`).
RTL = `dev` with step B of the activation functions (`doc/experiments/2026-11-02_activation_rtl.md`) on top of
`../2026-11-02_route4ns_wsend_zu7ev`: Leaky ReLU slope and rounding in `quantization_unit.v`, `activation_table.v`
(4 write-back lanes), state `GET_ACTIVATION`, five status fields. Same configuration (`config.json`) and flow.
**This is the current hardware baseline.**

| | wsend | **act (step B)** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warnings | 411 | 311: 100 fewer `Synth 8-3332` (upper product bits of two quantizers no longer constant, see below), one `DRC 23-814` less, one `Synth 8-7080` (parallel synthesis not used) more; the rest the same apart from hierarchy names |
| WNS post-synthesis / post-route at 4 ns | +0.205 / +0.020 ns | +0.203 / **+0.045 ns** (250 MHz met) |
| WHS post-route | +0.006 ns | +0.007 ns |
| fmax post-route = 1000/(4 - WNS) | ~251.3 MHz | **~252.8 MHz** |
| CLB LUT post-synthesis / post-route | 62,525 / 60,641 | 63,440 / 61,419 (+915 / +778) |
| LUT as memory post-route | 2,279 | 2,535 (+256: the 4 tables, 4 x 64 LUTRAM) |
| FF post-synthesis / post-route | 39,466 / 39,790 | 39,529 / 39,849 (+63 / +59) |
| CARRY8 / Block RAM tile / URAM / DSP | 3,313 / 192 / 8 / 4 | 3,346 / 192 / 8 / 4 |

Post-synthesis by module (LUT, of which LUTRAM):

| Module | wsend | act |
|---|---:|---:|
| `psum_pipeline_inst` | 3,084 | 3,644 (+560) |
| 4 x `gen_quant_unit[i].u_quant_unit` | 169 + 166 + 166 + 678 = 1,179 | 4 x 343 = 1,372 (+193) |
| 4 x `gen_quant_unit[i].gen_act_table.u_act_table` | - | 88 + 88 + 88 + 90 = 354 (4 x 64 LUTRAM) |
| `OpenEye_Parallel` (not changed) | 51,057 | 51,362 (+305: synthesis variation) |

- Attributable to step B: about +550 LUT (+0.9 %), +60 FF, 256 of them LUTRAM; no BRAM, URAM or DSP. More than the
  ~300 LUT of the design estimate: the rounding constant 2^(shift-1) (shift up to 45) makes every bit of the 46-bit
  product significant, so Vivado no longer removes the upper product bits it used to remove in two of the quantizers.
- Timing: the worst path after routing is again `fsm_cycle_reg` -> `router_configurator_inst/router_mode_psum_o_reg`
  (13 logic levels, the main FSM's compare chain), as in the wsend run; the activation logic is not among the
  reported paths. Post-route WNS +0.045 ns (wsend +0.020 ns): placement variation.
- Cycles: 0 change on the 12 baseline cases (`doc/perf/baseline_2026-11-02`) and on the 16 Table 3 configurations
  in mode 0; RTL regression 180 tests 175 PASS + 5 known xfail.

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/act_impl/reports/`.
