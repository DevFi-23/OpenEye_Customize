# 2026-10-24: bug #26 investigated - a Dense layer never writes its output back for a following Dense (no RTL change)

No RTL and no repository code was changed. Tools in `2026-10-24_bug26/` (section 9). Platform of all runs unless noted:
2x2 clusters (`CLUSTER_COLUMNS=2`, `CLUSTER_ROWS=2`), `NUM_GLB_PSUM=4`, `NUM_GLB_WGHT=3`, `NUM_GLB_IACT=1`,
`IACT_RAM_CELLS=4`, `TRANS_WORDS=8` (so `WRITEBACK_WORDS = min(TRANS_WORDS, NUM_GLB_PSUM) = 4`), DMA 64 bit, psum 20 bit,
random data, `OPENEYE_SEED=1`.

## 1. Summary

Every model with a Dense layer followed by another Dense layer on chip (MLP heads, the network of the paper's Table 2:
`Dense 1568->32 -> Dense 32->10`) computes a wrong result. The first Dense computes its psums correctly, but the
write-back of those results into the iact buffer (psum FSM `SEND_PSUM_TO_IACT` + main FSM `RECEIVE_PSUMS_TO_IACT`) **writes
nothing**: after the layer the buffer still holds the layer's own input, and the next Dense reads that.

Three causes, all on the write-back path, none in the computation:

| | Cause | Side |
|---|---|---|
| W1 | `fsm_psum_limit = used_psum_per_PE + 3` for Dense: `SEND_PSUM_TO_IACT` lasts 8 cycles, the main FSM only starts capturing at `fsm_psum_cycle >= 7`, so it captures one value, finds its storage counter at 0 when the psum FSM goes idle and leaves without a single RAM write | Python (`layer_parameters.write_dense_layer`) |
| W2 | the read loops of `SEND_PSUM_TO_IACT` are not set up for Dense: the cluster-select loops are all 0 (`psum_pagu_cs_*` never set) and the address loop counts 0, 1, 2, ...; the generic path reads `WRITEBACK_WORDS` GLBs of one cluster per cycle (the conv layout: 4 GLBs = 4 pixels), but a Dense result exists only in GLB 0 of cluster row 0 of each cluster column; cluster column 1 (half of the filters) is never read | Python |
| W3 | `RECEIVE_PSUMS_TO_IACT` transposes `WRITEBACK_WORDS` lanes x `WRITEBACK_WORDS` cycles into pixel-major groups (conv); for Dense only lane 0 carries data, and the group filter (`x_pos < iact_size_x`, `x_pos` wraps at `iact_x_add_up`) cannot keep "lane 0 of every group" without changing `iact_x_add_up`, which the FC iact converter needs | RTL (no register setting gives the Dense layout) |

**Isolation:** writing the expected image into the buffer after the first Dense (testbench, `B26_INJECT`) makes every
chain tried compute the right final result (D 16->8->10, 64->8->10, 256->32->10, MLP 6->32->16->4): the write-back is the
only blocker.

**History:** the on-chip FC write-back existed upstream and was switched off for area: the FC packer in
`RECEIVE_PSUMS_TO_IACT` was commented out in `1320759` (2026-07-14, "Reduced logic for smaller designs") and the FC branch of
`SEND_PSUM_TO_IACT` disappeared in `8350a00` (2026-07-20, "Optimized PSUM Flow for LUT Efficiency"), which replaced the
hand-written read patterns by generic counter loops. Section 5.

**Proposed fix** (needs approval, RTL): one line in `OpenEye_FPGA.v` (the `x_pos` wrap also fires for a fully connected
layer) plus Python register settings for a Dense that keeps its output on chip. Validated by **emulating** the RTL line in
cocotb (the testbench deposits the value the new line would store; the RTL source is untouched): 11 Dense chains (MLP
included) and the paper network in 4 hardware configurations all give the right final result, and the buffer checks pass
except for padding bytes in one case (section 7); the paper network passes all 7 layers at `CLUSTER_ROWS=2`. Alternative without any RTL change: send the first
Dense's output to the host and load it back as the next layer's input (section 6.3).

Side finding on the known bug #21 (Dense with more than `16 x CLUSTER_COLUMNS` filters, two psum passes, only the first
P outputs right): the same layer written back on chip gives all 64 values right, so its computation and psum buffer are
right and #21 is in the final readout (section 8).

## 2. Symptom

`LAYER=D_16_8_10` (Dense 16->8 -> Dense 8->10), log of the iact check after layer 0:

```
Iact buffer check: 1 expected words, 4 cells per group, depth 4096 (layer 'Dense')
Ref-Value: 0xfffe01fdfefb0303 DUT-Value: 0x808fbfd09f00907
Iact buffer occupancy: 4 written words, cells [0, 1, 2, 3], first entries
  [(0, 0, '0x808fbfd09f00907'), (1, 0, '0xfa07f801fd08f5f2'), (2, 0, '0x0'), (3, 0, '0x0')]
```

The reference is the 8 quantized outputs `[3, 3, -5, -2, -3, 1, -2, -1]` (byte 0 = filter 0). The DUT words, read low byte
first, are `[7, 9, -16, 9, -3, -5, 8, 8]` and `[-14, -11, 8, -3, 1, -8, 7, -6]`: **the 16 input activations of layer 0**.
`TRACE_RAM_WRITES` lists one RAM write in the whole layer, the DMA load of the input at 275 ns (state 4); the write-back
state (11) writes nothing. Every Dense -> Dense chain tried fails the same way (K = 16, 64, 256, 1568; N = 8, 10, 16, 32;
the MLP case at both junctions), in every configuration of the Table 3 run (`doc/perf/paper_table3_2026-10-24`: layer 5).

(The earlier note in README 8b, "4 low/high bytes of a word end up in 2 words", was a misreading of these input words.)

## 3. Where it goes wrong

`TRACE_CONV_WRITEBACK` during `SEND_PSUM_TO_IACT` of layer 0 (`rd` = psum buffer read bus, 16 words = 4 clusters x 4 GLBs,
cluster index = row x 2 + column):

| cycle | addr | cluster 0 GLB 0..3 | cluster 1 GLB 0 | quant lane 0 |
|---:|---:|---|---:|---:|
| 3 | 0 | 1610, 0, 1, 0 | -1272 | |
| 4 | 1 | 1750, 0, 2, 0 | 767 | |
| 5 | 2 | -2435, 0, 3, 0 | -750 | |
| 6 | 3 | -797, 0, 4, 0 | -402 | |
| 7 | 4 | X | X | 3 |

The psum buffer is **right**: cluster column 0, GLB 0, address a holds filter a, column 1 holds filter 4 + a, each value =
psum + bias (1609 + 1, -1277 + 5, ...); GLB 2 holds the bias, GLB 1/3 zero. In general filter
`f = r*CX*P + c*P + a` sits in cluster column `c`, row 0, GLB 0, address `r*P + a` (`P = used_psum_per_PE`, `CX` =
cluster columns, `r` = psum pass), the layout `DensePsumStreamMapper` writes the bias in and `PSUM_SEND_RESULTS` reads
the final Dense from. The quantizer is right too (lane 0 at cycle 7 = floor(1610 / 2^9) = 3).

W1: `fsm_psum_limit = 4 + 3 = 7`, the state ends after cycle 7. `RECEIVE_PSUMS_TO_IACT` captures
`quantized_value_reg` from `fsm_psum_cycle >= 7` on, so it gets one value. With the psum FSM idle it flushes until its
storage counter (groups per buffer row, `(8/WRITEBACK_WORDS) x IACT_RAM_CELLS = 8`) is 0, which it already is: it
returns to `GET_PARAMETERS` at once, `iact_buffer_en_w` never set.

W2: `write_dense_layer` sets the address loop to `[255, 0, 0, 0, 0]`, increment `[1, 0, ...]`, and leaves
`psum_pagu_cs_limit/inc` at 0: `psum_cluster_select` stays 0. Each cycle reads cluster 0, GLB 0..3, address t; lanes 1..3
are GLB 1..3 (zero, bias, zero), cluster column 1 is never read.

W3: the main FSM collects `WRITEBACK_WORDS` cycles in `iact_to_psum_mux_reg` (lane j keeps its 4 values), then shifts one
4-byte group per cycle onto the RAM write bus, lane 0 first, and keeps a group only if
`iact_to_psum_x_pos_counter < iact_size_x`; `x_pos` counts the groups and returns to 0 at a group reload when
`x_pos >= iact_x_add_up - 1` (`OpenEye_FPGA.v`, `RECEIVE_PSUMS_TO_IACT`). For conv, lanes are pixels and `iact_x_add_up` is
the row width. For Dense, lanes 1..3 are junk; the flat layout the next Dense reads (`DenseIactStreamMapper`: value i in
byte i % 8 of cell (i / 8) % 4, address i / 32) needs exactly the lane-0 groups.

## 4. The write-back is the only blocker

`B26_INJECT=1`: when the iact check after a layer fails, the testbench writes the expected image into `BUFFER_A` (the half
`choose_iact_buffer` selects) and the model runs on.

| LAYER | layers | iact check | final result |
|---|---:|---|---|
| D_16_8_10 | 2 | fails, image injected | **right** (10/10) |
| D_64_8_10 | 2 | fails, image injected | **right** |
| D_256_32_10 | 2 | fails, image injected | **right** |
| MLP (6->32->16->4) | 3 | fails twice, injected twice | **right** |

So the second Dense, its weights, its iact converter and the readout work; nothing but the buffer content is missing.

## 5. History: the FC write-back was removed for area

| Commit | Date, author | What it did to the Dense write-back |
|---|---|---|
| `8d20636` | 2026-06-18, DenLeb | `fsm_psum_limit = used_psum_per_PE + 3` for Dense (still today) |
| `1320759` | 2026-07-14, DenLeb, "Reduced logic for smaller designs" | comments out (`/* ... */`) the `iact_channels_per_pe_next_layer == 2` and `== 1` packers of `RECEIVE_PSUMS_TO_IACT`; the `== 1` packer had the FC case (`quantized_value_reg[0]` at byte `overhang + 8*sel`, `[1]` at `filters + ...`, i.e. the two cluster columns at `c*P + a`) |
| `8350a00` | 2026-07-20, DenLeb, "Optimized PSUM Flow for LUT Efficiency" | rewrites `SEND_PSUM_TO_IACT` with generic counter loops (`psum_cycle_loop_*`, `psum_cluster_select_*`); the FC branch (`quantized_value[0]` = column 0 GLB 0, `[1]` = column 1) is gone |
| `e8f39ad` | 2026-09-03, DenLeb, "Increased performance for MLP Nets" | adds `LAYER=MLP` (Dense 6->32->16->4, the Makefile default since) and sets `self.psum_pagu_loop_limit_0 = 255`, ... as scalar attributes, which no mapper reads |
| `96e18af` | 2026-09-29, DenLeb | turns them into the list entries the mapper reads (`[255, 0, ...]`, inc `[1, 0, ...]`) - the values of W2 |
| `7494d7b` | 2026-09-10, Hendrik Woehrle | comment in `psum_pipeline.v` still refers to "the FC branch of SEND_PSUM_TO_IACT" |

Upstream head (`e78e5b7`, 2026-10-21) is unchanged here. Upstream evidently meant MLPs to work (MLP case, Makefile
default) but the generic write-back was never configured for Dense.

## 6. Can Python alone fix it?

### 6.1 The read side: yes

`B26_WB=1` overrides, at packing time, the registers of a Dense with `send_data_out = 0` (`install_writeback`):

* cluster select: `psum_pagu_cs_limit = [P-1, CX-1, 0]`, `inc = [0, 1, 0]` (P cycles on a column, then the next column,
  then back to column 0);
* address: `psum_pagu_loop_limit = [P-1, CX-1, R-1, 255, 0]`, `inc = [1, 0, P, 0, 0]` (a = 0..P-1, the same P addresses
  for every column, then the next psum pass at `r*P`);
* `fsm_psum_limit` long enough (W1).

The trace (run `wb16`) shows `psum_cluster_select` switching to column 1 exactly at value P and back to column 0 at 2P,
and the quantizer emitting the 8 values in filter order (that run's values themselves are off because it also changed
`iact_x_add_up`, 6.2; run `wb16k`, which keeps it, writes `f0..f3 = 3, 3, -5, -2` = reference). The reads after the
last value wrap to f0, so nothing unwritten (X) is ever read.

### 6.2 The packing side: no

What `RECEIVE_PSUMS_TO_IACT` has to keep is lane 0 of every group:

* `iact_size_x = 1` keeps only groups with `x_pos = 0`. The register is free for Dense: the FC converter uses
  `fc_size_reg`, and layer 0 computes the same psums with it (run `wb16k`).
* but `x_pos` only returns to 0 when `x_pos >= iact_x_add_up - 1`, and the FC iact converter uses `iact_x_add_up` (= K):
  with `iact_x_add_up = 4` layer 0's psums change (filter 0: 1025 instead of 1610, run `wb16`). With `iact_x_add_up = K`
  `x_pos` runs over `ceil(K/4)` reloads (4 groups each) before it wraps, so one group survives per `ceil(K/4)` reloads,
  and the flush in `PSUM_IDLE` (shifts the bus every cycle) duplicates it: the buffer row becomes `f0..f3` eight times
  (run `wb16k`).
* a read pattern "stretched" to match (the 4 values in the one kept window of every `ceil(K/4)` windows) would need
  `N x ceil(K/4)` cycles (12.544 for 1568->32) and cluster-select counts beyond the 4-bit limits for large K. Not viable.

### 6.3 Host round trip (no RTL change)

The first Dense sends its psums out (`send_values_out = 1`, `PSUM_SEND_RESULTS`, the path every final Dense uses), the
host quantizes them, and the next Dense loads them as input by DMA (`skipIact = 0`). Cost per junction: one 64-bit DMA word
per output value out (FC readout carries one psum per word) plus `ceil(N/8)` words in, plus the host's turnaround; e.g.
32 + 4 words for the paper's 1568->32 -> 32->10 (that layer's weight load alone is 10.560 DMA words). The testbench only reads
outputs after the last layer today and would need intermediate outputs and DUT-to-host quantization. Not prototyped.

## 7. Proposed fix: one RTL line + Python, validated by emulation

RTL (`hdl/OpenEye_FPGA.v`, `RECEIVE_PSUMS_TO_IACT`, the `x_pos` wrap at the group reload):

```verilog
-              if (iact_to_psum_x_pos_counter >= iact_x_add_up - 1) begin
+              if ((iact_to_psum_x_pos_counter >= iact_x_add_up - 1) | fully_connected_layer) begin
                 iact_to_psum_x_pos_counter <= 0;
```

For a fully connected layer `x_pos` then restarts with every group of `WRITEBACK_WORDS` lanes, and with `iact_size_x = 1`
only lane 0 is kept: the groups `f0..f3`, `f4..f7`, ... land on the bus in order, 8 groups = one buffer row of 32 values =
the flat Dense layout. Conv is untouched (`fully_connected_layer = 0`). An equivalent form keeps the register meaning:
`if (fully_connected_layer ? (x_pos == 0) : (x_pos < iact_size_x))` for the keep test plus the same wrap. Area: one OR
gate.

Python (`write_dense_layer` / `dense_mapper`, only for a Dense with `send_values_out = 0`):

| Register | Value | Why |
|---|---|---|
| `iact_size_x` (register only) | 1 | keep lane 0 of every group |
| `fsm_psum_limit` | `8 + 8*IACT_RAM_CELLS * ceil(R*CX*P / (8*IACT_RAM_CELLS))` | group j is kept at cycle `12 + 4j`; ending one cycle after the last group of a full row leaves the storage counter at 0, so the flush stops at once instead of duplicating groups |
| address loops | limit `[P-1, CX-1, R-1, 255, 0]`, inc `[1, 0, P, 0, 0]` | 6.1 |
| cluster-select loops | limit `[P-1, CX-1, 0]`, inc `[0, 1, 0]` | 6.1 (4-bit limits: P <= 16 always holds, `needed_psum_transmissions` splits at 16 x CX) |

Testbench: for a Dense next layer the bytes after the N real activations are don't-care (the next layer's weights for
those positions are 0); the fix leaves wrapped values there (`f0, f1, ...`), so the image check has to compare the first N
bytes only.

**Validation by emulation** (`B26_EMU=1`): at every group reload of a fully connected layer in state 11 the testbench
deposits `x_pos = 0` (exactly what the new line stores), with `B26_WB=1 B26_WB_KEEP_ADDUP=1 B26_LIMIT_ROWS=1`:

| Run | Model | Configuration | iact check | Final result |
|---|---|---|---|---|
| e16 | D_16_8_10 | default | PASS | PASS |
| e64 | D_64_8_10 | default | PASS | PASS |
| e256 | D_256_32_10 | default | PASS | PASS |
| e1568 | D_1568_32_10 (the paper's Dense pair) | default | PASS | PASS |
| emlp | MLP 6->32->16->4 | default | PASS (both junctions) | PASS |
| e6410 | D_64_10_10 | default | bytes 12-15 differ (wrapped f0..f3 where the reference has 0: padding, see above); bytes 0-11 right | PASS |
| r64 | D_16_64_10 (2 psum passes, `QUANT_AMOUNT=64`; as a last layer this Dense hits bug #21) | default | PASS | PASS |
| g2 | D_64_8_10 | `NUM_GLB_PSUM=2` (`WRITEBACK_WORDS=2`) | PASS | PASS |
| cr1 | D_64_8_10 | `CLUSTER_ROWS=1` | PASS | PASS |
| cr4 | D_64_32_10 | `CLUSTER_ROWS=4` | PASS | PASS |
| mlp4 | MLP | `CLUSTER_ROWS=4` | PASS | PASS |
| pcr2 | PAPER_MNIST (paper Table 2, 7 layers, 28x28 input padded to 2 channels) | `CLUSTER_ROWS=2` (Table 3 row CR 2, X 4, Y 3) | **PASS after all 6 layers** | **PASS** |
| pcr1 | PAPER_MNIST | `CLUSTER_ROWS=1` | layers 0-4 PASS, after layer 5 the values are close but off (17 vs 14, -5 vs -6) | FAIL |

The `CLUSTER_ROWS=1` failure is not the write-back: the Dense 1568->32 alone, as the last layer (no write-back at all),
gives 32 of 32 wrong outputs at `CLUSTER_ROWS=1` (run s1568cr1) and is right at `CLUSTER_ROWS=2` - the computation bug
#19b (Dense with 32 outputs and many K passes; one cluster row doubles the passes). So with the fix, the paper network
computes right wherever its layers compute right: 5 of the 6 failing checks of the X = 4 rows of Table 3 were #26 only.

Cost (profiler): the write-back phase of the first Dense is 146 cycles for N = 32 (0.9 % of the 1568->32 layer, 4.6 % of
256->32), 70 and 82 cycles for the MLP's 32 and 16 outputs; no DMA traffic.

Without the emulation the same register settings fail (6.2), so the RTL line is needed.

## 8. Side finding: bug #21 is in the readout

`D_16_64` (one Dense 16->64, the last layer, `QUANT_AMOUNT=64`; `needed_psum_transmissions = 2`, P = 16): 48 of 64 outputs
differ, filters 0-15 right - the pattern of bug #21 (README 8b: N = 40 only the first 10 right, N = 48 the first 12; P = 10
and 12 there). The same layer as the first layer of `D_16_64_10`, written back with the emulated fix, gives the right 64
activations (run r64, buffer check and final result pass) - so the computation and the psum buffer layout
(`f = r*CX*P + c*P + a` at address `r*P + a` of column c) are right, and #21 is in the final readout (`PSUM_SEND_RESULTS`
order/count for two passes, or the testbench's decoding of it). Not investigated further.

## 9. Tools (`2026-10-24_bug26/`)

* `probe_dense.py`: cocotb module wrapping the unmodified `OpenEye_FPGA_tb` (Dense chains `D_<K>_<N1>_<N2>...`, switches
  `B26_DUMP`, `B26_INJECT`, `B26_WB`, `B26_WB_KEEP_ADDUP`, `B26_ADDUP`, `B26_LIMIT_ROWS`, `B26_EMU`; docstring).
* `run_dense.py <name> <LAYER> <layers> [KEY=VALUE ...]`: runs one model through it (options `CR`, `IACT`, `GLBP`, `QA`,
  `H`; other keys go to the simulation, e.g. `TRACE_CONV_WRITEBACK=1 TRACE_RAM_WRITES=1 TRACE_WB_EVENTS=1`).

```bash
venv/bin/python doc/experiments/2026-10-24_bug26/run_dense.py x16 D_16_8_10 2                       # the bug
venv/bin/python doc/experiments/2026-10-24_bug26/run_dense.py i16 D_16_8_10 2 B26_INJECT=1          # section 4
venv/bin/python doc/experiments/2026-10-24_bug26/run_dense.py e16 D_16_8_10 2 B26_WB=1 B26_WB_KEEP_ADDUP=1 B26_LIMIT_ROWS=1 B26_EMU=1
```
