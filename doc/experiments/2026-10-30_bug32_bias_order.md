# 2026-10-30: bugs #32 and #35 investigated (no RTL change, no change in src/)

Approved by the user: investigate #32 (conv3 of the real model swaps the biases of filter pairs) and #35 (conv3 wrong when
it writes back for the Dense layer), without changing the RTL. Result: **#32 is the order of the conv bias words** (the
RTL bias load fills the cluster lanes from the top, the compute and the read-out count them from the bottom), visible
only when one buffer address holds several filters; a Python-only fix makes it right (emulated in the simulation process,
not in `src/`). **#35 is not a new bug: it is #31** (an empty pass) at conv3's last output line; the earlier description
("last column x = 6") was a misreading of the Dense input layout. With the #32 fix emulated, MNIST test image 1 runs through
the whole trained model on the RTL bit-exact and the DUT gives the right class.

## 1. Bug #32: cause

Only conv3 of the real model (7x7x64 -> 64) has `different_kernels_per_calculation = 2` (two filters computed at the same
time on the two cluster rows, `LayerParameters` "kernels per calculation", chosen when one output line fits in half the PEs).
conv1 and conv2 have 1. The compute and the read-out (`test_utils_main.calculate_conv_serial`, `PSUM_SEND_RESULTS` shifting
`psum_buffer_data_temp_reg` right) put kernel group k on cluster k, i.e. the low lanes of the psum buffer bus first:
lane = cc * NUM_GLB_PSUM + cr * CLUSTER_COLUMNS * NUM_GLB_PSUM + g, filter of psum slot p in group k = f_start + 2p + k.

The bias stream (`psum_stream_mapper.PsumStreamMapper.get_psum_stream`, serial) sends, per output line, every filter in
order, each as `block_length = NUM_GLB_PSUM/2 * CLUSTERS / kernels_per_calc` words of two copies of its bias: 8 words per
filter with one kernel group, 4 words with two. `hdl/psum_pipeline.v` (PSUM_IDLE during GET_BIAS, conv branch) shifts each
word in from the bottom, `psum_buffer_data_w <= (psum_buffer_data_w << CONV_DMA_PAYLOAD_WIDTH) | data`, and writes one
buffer address after `CONV_BIAS_CYCLES` = 8 words. The first word therefore ends in the **top** lanes (cluster row 1,
column 1), the last one in cluster 0. With one kernel group the 8 words of an address carry the same bias, so the order does
not matter. With two, the first 4 words (filter 2p) land in cluster row 1, which computes filter 2p+1, and the next 4
(filter 2p+1) in cluster row 0, which computes filter 2p: every filter gets its neighbour's bias. With four kernel groups
(output lines of 4 pixels or fewer and 13 or more filters) the four filters of an address are reversed.

Seen in the simulation (`probe32.py`, `B32_BIAS`: lanes of the first bias writes, conv 7 wide, 4 channels, 8 filters, bias
1 + 3f):

```
b32bias write 0: cr0cc0=[4, 4, 4, 4]  cr0cc1=[4, 4, 4, 4]  cr1cc0=[1, 1, 1, 1]  cr1cc1=[1, 1, 1, 1]
b32bias write 1: cr0cc0=[10, 10, 10, 10]  cr0cc1=[10, 10, 10, 10]  cr1cc0=[7, 7, 7, 7]  cr1cc1=[7, 7, 7, 7]
```

| Run (`run32.py`, random data, bias 1 + 3f) | kernels per calc | DUT - numpy per filter |
|---|---|---|
| conv 7x2, 4 ch, 8 filters | 2 | +3, -3, +3, -3, ... (filter 2k has b[2k+1], 2k+1 has b[2k]) |
| conv 4x2, 4 ch, 16 filters | 4 | +9, +3, -3, -9, ... (filter 4k has b[4k+3], 4k+1 has b[4k+2], ...) |
| the same two with `B32_REVERSE=1` (bias stream with the kernel groups of every address reversed) | | **0 everywhere** (the 7-wide run still reports the known padding-lane difference of bug #9 in the raw stream; every value is right) |

Why it was not seen: every earlier test gave every filter bias 1, and the bias-step tests (`test_conv_channel_order`, 4
filters) have one kernel group. The random MNIST_REAL chain (conv3 with two kernel groups) uses bias 1.

Upstream (`upstream/main` 93f0e82): `psum_stream_mapper.py` identical, the same shift in `psum_pipeline.v` (and the same
direction before 30c01a5, which upstream also has), so the same bug by code reading.

## 2. Bug #35 = bug #31 at conv3's last output line

`run35.py` runs the real model as `test_real_model.py` with every iact buffer check dumped (`B35_DUMP`); `analyze35.py`
maps the bytes of the buffer before the Dense layer back to conv3's (f, x, y) with the Dense input order
p = f%4 + 4x + 28y + 196*(f//4) (equal to `DRAMContents.dense_input_order` for this model).

Image 0 with the #32 fix emulated (`B32_REVERSE=1`): the buffers after pool1 and pool2 are bit-exact, 113 of the 3,136
conv3 outputs are wrong, **all at y = 6, the last output line** (x = 0..6), not in a column. Searching which input lines
explain each output line: lines 0..5 are exactly the reference (448/448 each), line 6 is no combination of input lines.
Bug #31 is: the output line y = 6 sees input lines 5, 6 and the zero padding line; in that window the 4-channel chunk 11
(channels 44..47) has no non-zero activation (also chunk 14). The passes run per output line, filter refresh (32 filters:
16 psum slots x 2 kernel groups), 4-channel chunk. Model "bias + chunks 0..10 for filters 0..31, bias only for filters
32..63 at y = 6" = the DUT at **448 of 448** values: the empty pass (y 6, refresh 0, chunk 11) and every later pass were
not computed (bug #31).

| Run of the real model, the conv3 output written back for the Dense layer (3,136 values) | The model of #31 (+ #32) in `scan31.py` = RTL |
|---|---|
| image 0, as today | 3,136 / 3,136 (#32 everywhere + #31 at y = 6) |
| image 0, #32 fix emulated | 3,136 / 3,136 (#31 at y = 6) |
| image 1, as today | 3,136 / 3,136 (#32 only, no empty pass) |
| image 1, #32 fix emulated | 3,136 / 3,136, the check passes |
| image 7, #32 fix emulated (empty pass at output line 0, chunk 1: only chunk 0 of the first refresh of line 0 computed, the rest of conv3 = bias) | 3,136 / 3,136 |

The old record ("13 of 16 logged words explained by #32, the other 3 the last column x = 6 of the 7-wide rows") read
pixel = 7x + y instead of x + 7y; those 3 words were at y = 6. And "#31 did not trigger" (onnx_model_flow, section 5) was
wrong: image 0 has an empty pass in conv3. #35 is closed as a duplicate of #31.

## 3. The whole model on the RTL with #32 fixed (emulated)

**MNIST test image 1, `B32_REVERSE=1`: PASS.** Every buffer check (after pool1, pool2, conv3) and the Dense psums bit-exact
against the toolchain's reference; DUT class 2 = label 2 (raw outputs -35,406, 2,949, **77,668**, -51,959, ...); 2.21 ms
simulated time, about 11 minutes. The first real image through the whole trained model on the hardware. Image 0 still fails
at conv3 on #31.

## 4. How often #31 and #32 hit real data (`scan31.py`, Python only)

A numpy model of the hardware's arithmetic (conv with the DRAM weights and biases, the quantizer with ReLU, max pooling,
Dense in the hardware input order), equal to the testbench reference on image 0, run on the first 1,000 MNIST test images
with the bugs modelled as measured above (#31: the first empty pass of conv2 / conv3 and every later pass lost; #32: conv3
bias pairs swapped). The Dense layer is computed exactly (its own form of #31, bug #33, is not modelled):

| | Images (of 1,000) |
|---|---:|
| empty pass in conv2 | 0 |
| empty pass in conv3 | **861** (first one at output line 0: 429, line 6: 377, line 5: 52, lines 2..4: 3) |
| Dense input with a zero run of 65 or more values (where #33 can hit) | 501 |

| Accuracy (first 1,000 test images) | |
|---|---:|
| reference (no bug) | 99.5 % |
| #32 only | 99.5 % |
| #31 only (conv2 / conv3) | 72.9 % |
| #31 and #32 (the conv layers as the RTL computes them today) | 61.9 % |

The first and last output lines of conv3 see the blank border of the digit (after ReLU and two poolings mostly zero), so
#31 is the main blocker for real data; #32 alone rarely changes the class of this model but gives wrong values.

## 5. Fix directions (need the user's approval; nothing changed in `src/` or the RTL)

**#32, Python (recommended):** `psum_stream_mapper.PsumStreamMapper.get_psum_stream`, serial conv path: send the
`kernels_per_calc` filters of every buffer address in reverse order (filter f_base + D - 1 first), exactly what
`B32_REVERSE` does. Same number of words, no cycle change, no RTL change; identical stream for one kernel group (every
existing test with bias 1). Checks: a unit test of the stream order, an RTL test with distinct biases and two and four
kernel groups (`run32.py` cases, about 1 minute each), the real model image 1 (`test_real_model.py`: image 1 then passes,
the xfail must move to image 0 only), the regression. Open edge case: a filter count that is not a multiple of
`kernels_per_calc` (e.g. 5 filters with two groups) does not fill whole addresses; not used by any model here.

**#32, RTL (alternative):** shift the conv bias words in from the top in `psum_pipeline.v` (first word to cluster 0) so the
load matches the read-out. Same function, but an RTL change and `CONV_BIAS_CYCLES` rounding for other platforms has to be
checked; no advantage over the Python fix.

**#31 (= #35):** RTL fix A in `PE.v` (an empty PE still runs the pass protocol with zero products) as proposed in
`2026-10-30_bug31_empty_pass.md`; no Python-only workaround (making every pass non-empty would change the data).

## 6. Tools (`2026-10-30_bug32/`)

* `probe32.py` (cocotb module around probe31 and the unmodified testbench): `B32_BIAS=<n>` logs the lanes of the first n
  bias writes; `B32_REVERSE=1` emulates the Python fix of #32 in the simulation process; `B35_DUMP=<dir>` saves every iact
  buffer check (expected and DUT words).
* `run32.py`: `2026-10-30_bug31/run31.py` (one conv layer, chosen input, DUT vs numpy) with probe32, e.g.
  `venv/bin/python doc/experiments/2026-10-30_bug32/run32.py w7f8 rand W=7 H=2 CH=4 NF=8 OPENEYE_BIAS_STEP=3 B32_BIAS=4`.
* `run35.py <name> <image> [B32_REVERSE=1]`: the real model on the RTL (as `test_real_model.py`) with the dumps, about 10
  minutes; `analyze35.py <dump dir> [check]`: the wrong bytes of a check by (f, x, y); `explain35.py <dump dir> <image>`:
  numpy conv3 (with the padding pixel) against the wrong values.
* `scan31.py [N]`: how often #31 / #32 hit the first N test images and the accuracy with the bugs modelled;
  `scan31.py check <image> <mode> <dump dir>`: the model's conv3 output against a run35 dump.
