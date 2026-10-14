# Investigation 2026-10-14: bugs #6 (1 input channel) and #7 (3 channels, NUM_GLB_IACT=3)

No RTL was changed. Tools: a scratch reproducer (single Conv layer 8x1, 4 filters, ramp activations, constant weights 8,
QUANT_AMOUNT=32, 2x2 clusters) and a scratch cocotb probe that wraps the unmodified `OpenEye_FPGA_tb` and logs the internal RAM
ports of `iact_stream_constructor` (0,0); existing hooks `TRACE_PE_IACT`, `TRACE_PE_SPADS`; two temporary git worktrees of
upstream commits for a bisection (removed afterwards).

## Bisection: which commit broke what

| Case | `5516278` (before 23be043) | `23be043` "Fixed many bugs for Dense Layer" (2026-10-01) | `dev` today |
|---|---|---|---|
| 1 channel, NUM_GLB_IACT=1 (`test_conv_input_mapping[1-1]`) | **PASS** | FAIL | FAIL |
| 4 channels, NUM_GLB_IACT=3 (`test_conv_input_mapping[4-3]`) | **PASS** | FAIL | FAIL |
| 4 channels, NUM_GLB_IACT=1 (`test_conv_input_mapping[4-1]`) | PASS | PASS | PASS |
| 3 channels, NUM_GLB_IACT=1 | FAIL (481, 489, 553, ...) | FAIL | FAIL (same values) |

Bug #6 and the NUM_GLB_IACT=3 part of bug #7 are **regressions of 23be043**, which rewrote 249 lines of
`hdl/iact_stream_constructor.v` for the Dense layer and dropped parts of 6d513f6 ("Fix convolution activation mapping and
single-channel packing", 2026-09-21). The 3-channel failure is older and has a different cause.

## Bug #6: one input channel -> output = bias only

Symptom: every PE iact scratchpad stays empty (weights are loaded), so every psum keeps its bias value.

Design (6d513f6): with one channel, each 24-bit converter RAM word holds two image rows: row 2k in the low 12-bit slot,
row 2k+1 in the high slot **of the same address** (`single_write_half`, write mask). The address is computed as
`single_write_row + single_write_column` and stored in `ram_wr_addr_q`; the reader reads addresses 0..5 for the low half,
then the same addresses 0..5 for the high half.

What happens: 23be043 changed the RAM address from `ram_wr_addr_q` to `ram_wr_addr`
(`wire bank_addr = ram_wr_en_q ? ram_wr_addr : ...`, line 700). The probe shows the high-slot writes of the second row going to
addresses 6..11 (`ram_wr_addr`) although `ram_wr_addr_q` holds the correct 0..5. Reading 0..5 (high) then returns the zeros the
first row wrote, and 6..11 (low) were never written: `X` in simulation, the BRAM init value on the FPGA. The PE receives no
non-zero activation (in simulation the `X` also suppresses its scratchpad write).

Note: in the multi-channel path `ram_wr_addr` and `ram_wr_addr_q` differ on 35 of 36 writes and that path is correct with
`ram_wr_addr`, so the fix must only touch the single-channel path.

**Proposed fix (1 line, not applied):**
```verilog
wire [ADDRWIDTH-1:0] bank_addr = ram_wr_en_q ? (single_channel ? ram_wr_addr_q : ram_wr_addr) :
    (ram_rd_addr + (fully_connected_i ? 0 : r_gen * channel_div_trans));
```
Alternative without RTL change: pad 1-channel inputs to 2 channels (one zero channel, zero weights) in the Python mappers.

## Bug #7, part 1: NUM_GLB_IACT=3 -> wrong values

Symptom (4 channels): PE row 1 iact scratchpad empty, PE row 2 holds [1, 9, 18, 26] = channels 0-1 of pixel x0 and channels 2-3
of pixel x1 (expected [2, 10, 18, 26]).

Design (6d513f6 reader): "Every bank holds the serial input window" - all NUM_GLB_IACT banks hold the same pixel stream at
consecutive addresses, and bank r reads at `ram_rd_addr + r*channel_div_trans` to get the neighbouring pixel.

What happens: 23be043 made the writer rotate banks for every transfer when NUM_GLB_IACT > 1 (only bank `router_cycle` gets new
data, `mem_data_payload_reg[r]` updated only when `router_cycle == r`) and advance the address only every NUM_GLB_IACT writes
(`if ((NUM_GLB_IACT == 1) | (router_cycle == 0) | (switching_cycle == 0))`). That is the layout the Dense (FC) reader needs,
but a Conv pixel of 4 channels (2 transfers) is now split over two banks and two addresses (probe: x0 c0c1 -> bank 2 addr 4,
x0 c2c3 -> bank 0 addr 5), which the Conv reader does not expect. Before 23be043 the Conv writer broadcast every transfer to all
banks (`for r: mem_data_payload_reg[r][w] <= storage_i...`) and advanced the address on every write.

**Proposed fix (not applied):** keep the rotation only for Dense:
```verilog
wire rotate_banks = fully_connected_i && (NUM_GLB_IACT > 1);
// WRITE_TO_MEMORY: data
if (!rotate_banks || (router_cycle == r)) mem_data_payload_reg[r][w] <= single_channel ? storage_i[7:0] : storage_i[w*8+:8];
// WRITE_TO_MEMORY: address
if (!rotate_banks | (router_cycle == 0) | (switching_cycle == 0)) begin ... end
```

## Bug #7, part 2: 3 input channels -> wrong values (older than 23be043)

The Python stream packs channels back to back, 3 bytes per pixel (word: [1, 9, 17, 2, 10, 18, 3, 11]), while the RTL moves
activations in pairs (`PARALLEL_MACS = 2`, `channel_div_trans = ceil(C/2) = 2` transfers = 4 slots per pixel). Pixels then
straddle transfers: PE row 1 gets [1, 9] (missing 17), row 2 gets [10, 18], row 0 (padding) gets [7, 15].

**Proposed fix (Python only, no RTL change):** pad odd channel counts to the next even number (3 -> 4) with a zero channel and
zero weights in the iact and weight mappers and in `layer_parameters` (`used_channels`). Sparse mode skips the zeros, so the cost
is mainly 33 % more iact bytes for such layers.

## Verification plan for the fixes (after approval)

1. Reproducers: `test_conv_input_mapping` 4 cases, `test_conv_tall_ramp` 4 cases, 1/2/3/4/8 channels x NUM_GLB_IACT 1/3.
2. Regression: 16 Conv + 63 GEMM/Dense tests (same verdict or better per test), 9 baseline cases (0 cycle change expected for
   the 4-channel, NUM_GLB_IACT=1 cases), lint baseline.
3. Then MNIST Conv1 with its real single input channel becomes possible.
