# Vivado place and route after row O (bugs #37, #17): 2026-11-04, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/fixO_impl`).
RTL = `dev` with the changes of `doc/experiments/2026-11-04_rowO_bug17_bug37.md` on top of `../2026-11-04_route4ns_fix38_zu7ev`:
#37 iact buffer fields, constructor ports and address registers 12 -> 13 bit; #17 one-channel row-pair writer and
half-word read state removed from `iact_stream_constructor.v`, uneven-ending bookkeeping removed from
`data_pipeline_iact.v` (every PE). (#39 is Python only.) Same configuration (`config.json`, identical to fix38) and flow.
**This is the current hardware baseline.**

| | fix38 | **rowO** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warnings | 311 | 311 (4 new Synth 8-7129 "port iact_x_line_repetitions_i[0..3] of data_pipeline_iact has no load", the port kept unused; 4 Synth 8-7129 of PE_cluster no longer printed: Vivado prints at most 100 messages per ID; one line number) |
| WNS post-synthesis / post-route at 4 ns | +0.211 / +0.044 ns | +0.169 / **+0.077 ns** (250 MHz met), hold +0.011 |
| fmax post-route = 1000/(4 - WNS) | ~252.8 MHz | **~254.9 MHz** |
| CLB LUT post-synthesis / post-route | 62,998 / 60,936 | 61,498 / **59,389** (-1,500 / -1,547) |
| FF post-synthesis / post-route | 39,886 / 39,923 | 39,398 / **39,398** (-488 / -525) |
| Block RAM tile / URAM / DSP | 192 / 12 / 4 | **188** / 12 / 4 |
| one PE (post-synthesis, x 48) | 1,017-1,029 LUT, 666-667 FF | 1,001-1,011 LUT, 660 FF |
| one `iact_stream_constructor` (x 4) | 616-652 LUT, 367-374 FF, 6 RAMB36 | 569-594 LUT, 330-337 FF, **5 RAMB36** |

- PEs: -14 ... -18 LUT and -7 FF each (the uneven-ending state: two flags and a 4-bit counter plus its logic), about
  -770 LUT and -340 FF over 48 PEs.
- Constructors: -37 FF each (the row-pair write address, column and half registers and `ram_wr_addr_q`, minus 8 FF of
  the address registers that grew to 13 bits), -25 ... -58 LUT, and one RAMB36 less in every iact buffer: its byte write
  mask is constant now (it masked sub-word 0 for the row pairs), so Vivado packs the 8,192 x 72-bit bank into 5
  RAMB36 instead of 6 (Block RAM 192 -> 188 tiles).
- `dma_storage` +17 LUT, +23 FF: the 10 status fields that grew by one bit pass its register pipeline.
- Timing: the worst routed path is again a psum buffer address register -> psum BRAM (routing dominated), +0.077 ns;
  post-synthesis the iact converter control as before.
- Cycles: `doc/perf/baseline_2026-11-04` (11 cases identical, `model_mnist_real_c1` -360), Table 3
  `doc/perf/paper_table3_2026-11-04` (16/16).

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/fixO_impl/reports/`.
