# Vivado place and route after the fix of bug #25: 2026-10-26, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/fix25_impl`).
RTL = `dev` with the bug #25 fix on top of `../2026-10-26_route4ns_fix26_zu7ev`: only `OpenEye_FPGA.v` differs
(`RECEIVE_PSUMS_TO_IACT`: write-back groups of `WRITEBACK_CHANNELS = 4` channels for any lane count). Same configuration
(`config.json`, `NUM_GLB_PSUM = 4`: 4 lanes, where every new condition is constant true) and flow. **This is the current
hardware baseline.**

| | fix26 | fix25, first run (lane test not constant-folded) | **fix25 (final RTL)** |
|---|---:|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | 0 / 0 | **0 / 0** |
| Warning IDs and counts | - | as fix26 | as fix26 (one `DRC 23-814` fewer: printed per DRC run) |
| WNS post-synthesis / post-route at 4 ns | +0.199 / +0.028 ns | +0.211 / +0.034 ns | +0.205 / **+0.084 ns** (250 MHz met) |
| WHS post-route | +0.011 ns | - | +0.013 ns |
| fmax post-route = 1000/(4 - WNS) | ~251.8 MHz | ~252.1 MHz | **~255.4 MHz** |
| CLB LUT post-synthesis / post-route | 65,541 / 63,856 | 65,633 / 63,940 | 65,654 / 63,969 (+113 / +113) |
| FF post-synthesis / post-route | 38,978 / 39,018 | 38,967 / 39,295 | 38,968 / 39,296 (-10 / +278) |
| CARRY8 / Block RAM tile / URAM / DSP | 3,289 / 192 / 8 / 4 | 3,289 / 192 / 8 / 4 | 3,289 / 192 / 8 / 4 |

- In the first run the new lane test `iact_to_psum_trans_counter <= WRITEBACK_WORDS` was a real comparison (synthesis
  cannot prove that the 4-bit counter never exceeds 4). The final RTL ors it with the constant
  `WRITEBACK_WORDS >= WRITEBACK_CHANNELS`, which makes it true for 4 lanes; the next-state functions are then those of the
  circuit before the fix. Per module (post-synthesis, final run vs fix26): the top module's own logic +97 LUT / -5 FF,
  `dma_storage` +32 LUT, `psum_pipeline_inst` +15 LUT, `OpenEye_Parallel` -30 LUT; the last three did not change at all, so
  differences of this size are synthesis variation (earlier runs moved by -60 to -112 LUT without a logic change). The
  post-route FF count moves with phys_opt register replication (+278 in both fix25 runs).
- A formal equivalence check of the top module old vs new with Yosys (`equiv_make` / `equiv_simple -seq 2` /
  `equiv_induct`, submodules as black boxes) reported "equivalent", but it also reported a deliberately planted
  difference and the 2-lane configuration (where the circuits do differ) as equivalent: the flow is not able to detect
  differences in this design and is **not** used as evidence. The evidence that the 4-lane behaviour is unchanged is the
  simulation: 146 RTL tests with the same results, 0 cycles difference on the 12 baseline cases and on the 8 X = 4
  configurations of Table 3.
- Worst setup paths after routing: `psum_pipeline_inst/psum_buffer_addr_array` -> psum buffer BRAM, PE adder outputs, as
  in earlier runs; none involves the write-back packer. The slack of these wire-dominated paths moves with placement
  (+0.028 to +0.117 ns over the last runs).

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/fix25_impl/reports/` (first run:
`C:/openeye_vivado/fix25_impl_v1/`).
