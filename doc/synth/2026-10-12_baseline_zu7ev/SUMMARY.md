# Vivado synthesis baseline: 2026-10-12, xczu7ev-ffvc1156-2-e

Vivado 2024.2 (win64), `synth_ooc.tcl` from `tools/export_vivado.py` (commit 8a5bbd2), out-of-context, top `OpenEye_FPGA`,
clock constraint 10 ns. Configuration (`config.json`) = the latency baseline (`test_profile.py`):
2x2 clusters, NUM_GLB_IACT=1, NUM_GLB_PSUM=4, NUM_GLB_WGHT=3, psum 20 bit, QUANT_AMOUNT=32, DMA 64 bit, BUFFER_WIDTH_PSUM=14 (default).
RTL = dev at 8a5bbd2 (includes the GET_BIAS fix 77f0477).

## Resources (post-synthesis)

| Resource | Used | Available | Util |
|---|---:|---:|---:|
| CLB LUT | 64,540 | 230,400 | 28.0 % |
| - LUT as logic | 61,877 | | |
| - LUT as memory (distributed RAM 2,324, SRL 339) | 2,663 | 101,760 | 2.6 % |
| Flip-flop | 38,655 | 460,800 | 8.4 % |
| Block RAM tile (RAMB36 168 + RAMB18 48) | 192 | 312 | 61.5 % |
| URAM | 8 | 96 | 8.3 % |
| DSP48E2 | 4 | 1,728 | 0.2 % |

## Where the resources go (`utilization_hier.txt`)

| Block | LUT | FF | RAMB36 | RAMB18 | URAM | DSP |
|---|---:|---:|---:|---:|---:|---:|
| OpenEye_Parallel (4 clusters x 12 PEs = 48 PEs) | 54,483 (84 %) | 32,717 (85 %) | 0 | 48 | 0 | 0 |
| - one PE | ~1,100 | ~655 | 0 | 1 | 0 | 0 |
| psum buffers (8 x RAM_SP, 16,384 x 40 bit) | 8 x 18 | 8 x 37 | **144** | 0 | 0 | 0 |
| iact_stream_constructor (4x) | 4 x ~510 | 4 x ~307 | 24 | 0 | 0 | 0 |
| iact_layer_buffer (4x) / wght_buffer | ~35 each / 13 | 0 | 0 | 0 | 4 / 4 | 0 |
| router_configurator | 2,477 | 131 | 0 | 0 | 0 | 0 |
| psum_pipeline (incl. 4 quantization units) | 2,438 | 1,514 | 0 | 0 | 0 | 4 |
| dma_storage | 2,130 | 771 | 0 | 0 | 0 | 0 |
| OpenEye_FPGA own logic (FSMs) | 611 | 1,953 | 0 | 0 | 0 | 0 |

- The PE multipliers are built from LUTs (PE parameter `USE_DSP=0`, not passed from the top); only the 4 quantization units use DSPs.
- 144 of the 168 RAMB36 (46 % of all block RAM of the chip) are the psum buffers, sized by `BUFFER_WIDTH_PSUM=14` (16,384 entries).

## Timing (post-synthesis, no routing yet)

| | Value |
|---|---|
| WNS / TNS (setup) | +6.116 ns / 0 (133,073 endpoints) |
| WHS (hold) | +0.026 ns |
| Worst path | 3.865 ns, 17 logic levels (6 CARRY8), 66 % routing estimate |
| Estimated fmax | 1000 / (10 - 6.116) = **~257 MHz** (optimistic: post-route is typically 10-30 % lower) |
| check_timing | 0 unclocked, 0 unconstrained internal endpoints, 0 loops, 0 latches; 67 inputs / 67 outputs without I/O delay (expected in OOC) |

Worst paths: `iact_converter_x_reg[3]` -> `iact_converter_x`, `fsm_iact_params`, `fsm_row_offset`, `fsm_row` (iact converter control in
`hdl/OpenEye_FPGA.v` around lines 943-950): `(iact_converter_x + CLUSTER_COLUMNS*iact_x_per_cluster) * iact_x_line_repetitions >=
iact_x_add_up * needed_y_cls_reg`, i.e. two multiplications of run-time configuration values, an add and a compare in one cycle.
This is control logic, not the MAC datapath.

## Cycle counts converted to time (mnist1_28x28_c4_f32, 65,800 cycles, ideal memory)

| Clock | Time |
|---|---:|
| 100 MHz (constraint used) | 0.658 ms |
| 200 MHz (plausible post-route) | 0.329 ms |
| 257 MHz (post-synthesis estimate) | 0.256 ms |

## Yosys estimate vs Vivado

| | Yosys 0.69 synth_xilinx (xc7) | Vivado 2024.2 (ZU7EV) |
|---|---:|---:|
| Logic LUT | 61,277 | 61,877 |
| FF | 45,274 | 38,655 |
| BRAM36 equivalent | 272 | 192 tiles + 8 URAM |
| DSP | 121 | 4 |

Yosys tracks Vivado for logic LUTs (within 1 %), so it is usable for relative LUT comparisons; BRAM/URAM/DSP mapping differs and
must come from Vivado.
