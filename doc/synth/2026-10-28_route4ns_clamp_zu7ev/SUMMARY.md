# Vivado place and route after the int8 saturation fix (#30): 2026-10-28, xczu7ev-ffvc1156-2-e, clock 4 ns

Vivado 2024.2 (win64), `synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`, batch mode from WSL (`C:/openeye_vivado/clamp_impl`).
RTL = `dev` with the int8 saturation fix on top of `../2026-10-26_route4ns_fix25_zu7ev`: `quantization_unit.v` (stage 3 clamps
`prod >>> shift` to `[act_min, 127]` instead of keeping its low 8 bits), `psum_pipeline.v` (input `quant_clamp_low`, act_min to
the 8 quantizers), `OpenEye_FPGA.v` (wire), generated `dma_storage.v` (new status field `quant_clamp_low`, 8 bit, in the last
status word). Same configuration (`config.json`) and flow. **This is the current hardware baseline.**

| | fix25 | **int8 saturation** |
|---|---:|---:|
| ERROR / CRITICAL WARNING | 0 / 0 | **0 / 0** |
| Warning IDs and counts | - | identical |
| WNS post-synthesis / post-route at 4 ns | +0.205 / +0.084 ns | +0.205 / **+0.076 ns** (250 MHz met) |
| WHS post-route | +0.013 ns | +0.011 ns |
| fmax post-route = 1000/(4 - WNS) | ~255.4 MHz | **~254.8 MHz** |
| CLB LUT post-synthesis / post-route | 65,654 / 63,969 | 66,511 / 64,801 (+857 / +832, +1.3 %) |
| FF post-synthesis / post-route | 38,968 / 39,296 | 38,990 / 39,316 (+22 / +20) |
| CARRY8 / Block RAM tile / URAM / DSP | 3,289 / 192 / 8 / 4 | 3,313 / 192 / 8 / 4 |
| `psum_pipeline_inst` post-synthesis LUT / FF | 2,413 / 1,513 | 3,089 / 1,525 (+676 / +12) |

- The cost sits where expected: the 8 quantizers in `psum_pipeline` grow by about 85 LUT each. Before, synthesis only had to
  produce the low 8 bits of `prod >>> shift`; the saturation needs the whole shifted value (to see whether it leaves the
  int8 range) and two comparisons plus a multiplexer. The other modules did not change (`OpenEye_Parallel` +152,
  `dma_storage` -106 LUT: synthesis variation). DSP unchanged.
- Worst setup paths after routing: reset synchronizers, PE weight data, `psum_pipeline_inst/psum_buffer_addr_array` and
  `psum_buffer_data_w` to the psum buffer BRAM, as in earlier runs; none through the quantizers. Post-synthesis worst path
  unchanged (`dma_storage/pipe_chain_reg` -> `fsm_iact_params`, +0.205 ns).
- A cheaper saturation is possible if needed (e.g. limit the shift range, or detect the overflow on `prod` against
  `±128 << shift`), not done: +1.3 % LUT and timing met.

Files as in the earlier runs. Checkpoints stay in `C:/openeye_vivado/clamp_impl/reports/`.
