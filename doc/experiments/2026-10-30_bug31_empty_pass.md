# 2026-10-30: bug #31 investigated - a pass with no non-zero activation in any PE stops the rest of the layer (no RTL change)

Bug #31 (found with real MNIST data, `2026-10-30_real_data_bugs.md`): conv1 and conv2 of the trained model returned the bias
alone. Investigated with the project's own flow and random weights (bias 1); only the layer-0 input is chosen
(`2026-10-30_bug31/probe31.py`, `run31.py`). The RTL and the testbench are not modified.

## 1. Summary

* **Trigger:** a compute pass in which no PE of the array holds a non-zero activation. For a 3x3 conv that is an output line
  whose three input lines (y-1, y, y+1) are zero over the part of the line one pass covers; for a Dense layer a block of K
  inputs of one pass that is all zero (between 65 and 109 inputs for Dense 3136 -> 10: a zero block 0..63 passes, the
  109-long zero run of image 0 fails).
* **Effect:** that pass and **every later pass of the layer** are not computed; the outputs keep the bias plus the passes
  before. The layer still finishes on time (no hang), so nothing reports it.
* **Cause (RTL control, `hdl/OpenEye_FPGA.v` + `hdl/PE.v`):** a PE starts a pass only with at least one non-zero activation
  and one weight (`PE.v:1135`: `data_set & compute_pe & (second_spad_words_iact != 0) & (second_spad_words_wght != 0)`); an
  empty PE stays in IDLE with its iact ready high. OpenEye_FPGA counts a pass (Process 2, `current_cycle`) and starts the next
  converter pass and weight send (Process 5, `iact_converter_en_enc_reg`, `wght_sendable`) only when the PE array's iact
  ready bus `iact_ready_o_oep_w` leaves all-ones, i.e. when some PE starts. If no PE starts, the ready bus stays high,
  the next pass is never started and never counted.
* **Bug #33 is the same bug:** the wrong fc1 outputs of image 0 equal exactly bias + the products of inputs 0..2653;
  input 2654 starts the longest zero run of that input (109 values); image 1's longest run is 75 and it is right.
* The Python stream, the iact buffer and the converter's RAM are right; random test data never has zero activations
  (`DRAMContents` replaces each 0 by +-1), so no test met the case.

## 2. Narrowing down (single conv layer, random weights, `run31.py`)

DRAM layout of the input: `fmap[c][x][y]`; the buffer is ordered y, x, c, so a hardware line is one y over all x.
"DUT = bias" counts outputs that equal the bias alone.

| Input (28x28x1 padded to 2 channels unless noted) | Result |
|---|---|
| MNIST test image 0 | FAIL: DUT = bias at all 3,136 outputs |
| the same image with every 0 replaced by 1 | PASS |
| random, 50 % zeros scattered | PASS |
| random, 90 % zeros scattered | FAIL from output line 16 on (its window has a 20-long zero run) |
| lines y = 0..1 zero (also 2 and 4 real channels, and an 8x4x4 layer) | FAIL: all bias |
| line y = 0 zero / lines 10..11 zero / lines 4..5 zero | PASS |
| lines 4..6 zero | FAIL: bias from line 5 on (the first all-zero 3-line window) to the end |
| the last two or three lines zero | PASS (nothing after the empty window) |
| x = 0..4 zero in every line / x = 23..27 zero | PASS |
| one non-zero pixel / a non-zero block in the middle | FAIL: all bias |
| 8x4x4 layer: 90 % zeros, one non-zero pixel, a zero channel, lines 1..2 or 2..3 zero | PASS |

Dense 3136 -> 10 (`L=DENSE_CHAIN_3136_10 K=3136`): inputs 0..511 zero -> DUT = bias; inputs 1024..1535 zero -> wrong (the
passes after the block lost); inputs 0..15, 0..63 or 3000..3135 zero -> PASS.

## 3. Following the data (8x4x4 layer: lines 0..1 zero fails, lines 1..2 zero passes)

| Stage | Failing | Passing |
|---|---|---|
| Python DMA stream (`demo/layer_0_0/dma_stream_input.txt`) | 8 zero words, then the data | data, 8 zero words, data |
| BUFFER_A after the load (`DUMP_IACT_BUFFER`) | right | right |
| converter RAM writes in CONVERT_IACT (`B31_CONV`) | 72 words, 20 non-zero (lines 2, 3) | 72 words, 20 non-zero (lines 0, 3) |
| converter sends to the PEs in the compute phase | **72 words, 0 non-zero (one pass)** | 288 words, 80 non-zero (4 passes) |
| `enable_converter` after the first pass (`B31_ENC`) | **never again** | at 6,790, 7,730, 8,670 ns, each 1 clock after `iact_ready_i` falls |
| PE (`B31_WATCH`, `TRACE_PE_IACT`) | `second_spad_words_iact` 0 for the whole layer, no non-zero word on the lane, every PE stays IDLE (`TRACE_ALL_PE`: state 0, ready 1) | words arrive from 6,290 ns, PEs run states 1..7 |
| `compute_i` pulses at a PE | 12 | 12 |
| end of the layer | 10,540 ns | 10,540 ns |

In the passing run the ready bus falls two clocks after a compute pulse (the PEs with data start), and Process 5 starts
the next converter pass one clock later. In the failing run the first pass is the empty one: no PE starts, the bus stays
all-ones, and the converter is never enabled again.

## 4. The RTL involved

```verilog
// OpenEye_FPGA.v, Process 2 (cycle counting)
if (iact_ready_o_oep_w != {CLUSTERS*NUM_GLB_IACT{1'b1}}) begin
  if (!single_iteration) begin single_iteration <= 1; single_iteration3 <= 1; ... // a pass started
...
if (single_iteration3) current_cycle <= current_cycle + 1;

// OpenEye_FPGA.v, Process 5 (send phase)
if (current_cycle < needed_cycles - 1) begin
  if (iact_ready_o_oep_w != {CLUSTERS*NUM_GLB_IACT{1'b1}}) begin
    if (!single_iteration) begin
      iact_converter_en_enc_reg[a][b] <= 1;      // next converter pass
      wght_sendable <= 1; ...                     // next weight send

// PE.v, IDLE
if (data_set & compute_pe & ((second_spad_words_iact != 0) & (second_spad_words_wght != 0))) begin ... // start
```

The same holds for a pass whose PEs have no weight word (`second_spad_words_wght == 0`), not observed here.

## 5. Emulation (simulation only, `B31_EMU`): a ready pulse alone is not a fix

* Variant 1, force the ready bus low for one clock when converter (0,0) ends an ENCODE and the bus has not dropped within
  12 clocks: the 8x4x4 failing case passes (1 forced pulse), but at 28x28 the bus normally drops up to 32 clocks after
  the ENCODE (the PEs finish the previous pass first), so random data broke.
* Variant 2 (in `probe31.py`), force it after a compute pulse when no PE started within 4 clocks: no effect on passing
  runs (0 forced), but the 8x4x4 case is wrong in all 128 outputs and three 28x28 cases stall in the psum FSM (state 3),
  which waits for psums from the PEs that skipped.

So the pass bookkeeping also covers the psum collection: a fix has to make an empty pass look like a pass with zero
products through the whole protocol, not only the ready bus.

## 6. Fix directions (RTL, need the user's approval; not done)

| | Change | For | Against |
|---|---|---|---|
| A | `PE.v`: an empty PE (no non-zero activation or no weight) still runs the pass: leave IDLE, skip CALCULATING (zero products), go through WAIT_TO_SEND_PSUM / SEND_PSUM like a computing PE | local to the PE; every handshake (ready, pass count, psum collection) stays as for a normal pass; the existing protocol already handles PEs with data | a few clocks per empty pass; the psum SPad state of a PE that did not compute must be right (bias / partial sum passed on) |
| B | `OpenEye_FPGA.v`: count a pass and start the next one from an explicit event (the compute pulse or the converters' ENCODE end) instead of the ready bus, and make the psum collection not wait for skipping PEs | removes the data-dependent control | touches the central scheduling (Processes 2 and 5, psum FSM): higher regression risk |

A looks the smaller and safer step. Either way the check would be the `run31.py` cases above (8x4x4 and 28x28 with
empty windows, image 0, Dense with zero blocks) bit-exact against numpy, plus the regression, the cycle baseline (passes
with data must not change) and Vivado. No Python-only workaround: making every pass non-empty would change the data.

## 6b. Upstream has the same bug (checked 2026-10-30, `upstream/main` = 93f0e82)

* Code: the PE start condition (`PE.v`, IDLE), Process 2 (pass counting) and the ready-bus trigger of Process 5 are
  identical to `dev`; the only difference in Process 5 is the weight-send end (`wghts_per_pe + 2` in `dev`, `+ 1` upstream),
  unrelated. The start condition dates back to a83260d (2025-03-19, refined in 6006cc6 and b2f1898), the ready-bus trigger
  of the next pass to 337bd44 (2025-07-22, "Added multichannel support for X not equal to PEs"); both are on every recent
  upstream branch (no_sparsity, main_old, gemm, DAG, dev_dse).
* Simulation on upstream's own RTL and testbench (worktree of upstream/main, `run31_upstream.py` with
  `probe31_upstream.py`; conv 8x4x4, 4 filters, upstream's constant weights 8, bias 1):

| Input | Upstream |
|---|---|
| random, no zero | PASS |
| lines 1..2 zero | PASS |
| lines 0..1 zero (empty first pass) | FAIL: all 4 feature maps, the 96 logged differences all equal 1 = the bias |

Same behaviour as `dev`. Upstream's test data hides it the same way (constant or random activations, zeros replaced by +-1).

## 7. Tools (`2026-10-30_bug31/`)

`probe31.py` (cocotb module around the unmodified testbench): `B31_IACT` (layer-0 input from a .npy, 1-D for Dense),
`B31_WATCH` (start-of-compute inputs of chosen PEs), `B31_CONV` (converter RAM writes and sends per main state),
`B31_ENC` (converter start handshake), `B31_EMU` (variant 2 above). `run31.py <name> <pattern> [KEY=VALUE]`: one layer with
a chosen input, DUT vs numpy for every output (patterns and options in its docstring). `run31_upstream.py` and
`probe31_upstream.py`: the same check on a worktree of upstream/main (usage in the docstring). Testbench switches used:
`TRACE_ALL_PE`, `TRACE_PE_IACT`, `DUMP_IACT_BUFFER`, `TRACE_CONVERTER`, `TRACE_CONVERT_WINDOW`.
