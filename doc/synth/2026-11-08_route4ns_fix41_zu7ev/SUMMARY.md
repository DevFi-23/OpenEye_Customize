# Vivado place and route after the bug #41c fix: 2026-11-08, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/fix41_impl`).
RTL = `dev` with the two lines of `doc/experiments/2026-11-07_bug41_stride.md` section 9 (fix C) on top of
`../2026-11-04_route4ns_rowO_zu7ev`: in `RECEIVE_PSUMS_TO_IACT` of `OpenEye_FPGA.v` a write-back row counts `psum_size_x`
outputs (`iact_size_x` for a fully connected layer) and wraps at `x_pos * stride_x >= iact_x_add_up - stride_x`. The
configuration (`config.json`) is identical to rowO, so `STRIDE_ENABLED = 0`: `stride_x` is the constant 1 and the product
folds away; only the `psum_size_x` / `iact_size_x` select is new logic. **This is the current hardware baseline.**

| | rowO | **fix41** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warnings | 311 | 311, the same list (one internal instance name differs, `i_9` -> `i_11`) |
| WNS post-synthesis / post-route at 4 ns | +0.169 / +0.077 ns | +0.196 / **+0.009 ns** (250 MHz met), see below |
| fmax post-route = 1000/(4 - WNS) | ~254.9 MHz | **~250.6 MHz** |
| CLB LUT post-synthesis / post-route | 61,498 / 59,389 | 61,519 / **59,373** (+21 / -16) |
| FF post-synthesis / post-route | 39,398 / 39,398 | 39,399 / **39,436** (+1 / +38, replication by placement) |
| Block RAM tile / URAM / DSP | 188 / 12 / 4 | **188 / 12 / 4** |
| one `iact_stream_constructor` (x 4) | 569-594 LUT, 330-337 FF | 560-581 LUT, 331 FF (unchanged module, synthesis variation) |

- The changed logic is in the top level (`OpenEye_FPGA`): +21 LUT post-synthesis, within the +-30 LUT the same modules
  move between runs.
- Timing: the worst routed path is PE `stream_data_reg` in cluster (1, 1) -> PE `iact_addr_SPad_addr_reg` in cluster
  (0, 1), 1 logic level, 95.5 % of the 3.97 ns routing: a placement result, not the changed write-back logic (which is
  not on any of the 20 reported paths). The same kind of variation gave +0.020 ns on 2026-11-02. Post-synthesis slack
  improved (+0.169 -> +0.196 ns). If margin is wanted, a rerun with another placement seed or a register on that
  inter-cluster stream would be the place to look.
- Cycles: `doc/perf/baseline_2026-11-04` 12/12 identical, Table 3 `doc/perf/paper_table3_2026-11-04` 16/16 identical
  (the change only acts on strided layers).

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/fix41_impl/reports/`.
