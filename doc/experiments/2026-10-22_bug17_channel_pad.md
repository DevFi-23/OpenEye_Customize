# 2026-10-22: bug #17 worked around in Python (one-channel input padded to two channels); new bug #22 (all-zero weight words)

No RTL change. Code: `src/open_eye/channel_pad.py` (new), `test/cocotb_fpga/OpenEye_FPGA_tb.py` (calls it),
`rtl_test_utils.profile_set_layer_info` / `profile_report` (padding shown in the layer table). Probes:
`2026-10-22_bug17/` (`run_padw.py` + `probe_padw.py`, `run_zerok.py` + `probe_zerok.py` / `probe_skip.py`, `count_words.py`).
Platform of all runs: 2x2 clusters, `NUM_GLB_PSUM=4`, `NUM_GLB_WGHT=3`, `NUM_GLB_IACT=1`, DMA 64 bit, psum 20 bit.

## 1. Bug #17 and the workaround

The one-channel writer of `hdl/iact_stream_constructor.v` computes its RAM address from row and column only and ignores the x
passes of an image wider than one pass (`iact_x_line_repetitions > 1`; on this platform: width > 16, e.g. MNIST Conv1 28x28x1).
Two or more channels take the multi-channel writer, which handles the x passes (2026-10-14, `2026-10-14_channel_bugs.md`).

Workaround (host side, no RTL change): when layer 0 is a convolution with one input channel and more than one x pass, it is run
as a two-channel convolution:

| | channel 0 | channel 1 (padding) |
|---|---|---|
| activations | the image | all 0 |
| weights | the model's | all 1 (any non-zero value, see section 3) |

Every product of channel 1 is `0 * 1 = 0`, so every output equals the one-channel result exactly (integer accumulation, no
rounding). Implementation:

1. The testbench builds the layer parameters as before; `channel_pad.pad_first_layer` checks `needs_padding(layer_parameters[0])`
   (`layer_name == "Convolution2D"`, `channels == 1`, `iact_x_line_repetitions > 1`, the exact condition of bug #17) and, if so,
   wraps the Keras layer in `ChannelPaddedConv2D`: `input.shape` and `kernel.shape` with 2 channels, `weights[0]` = kernel with a
   zero channel appended (the float model is unchanged), every other attribute from the original layer. The layer parameters
   are rebuilt from the wrapped model, so every derived value (stream lengths, loop limits) is the two-channel one.
2. After `DRAMContents` and every data hook (`OPENEYE_RAMP_IACTS`, `OPENEYE_ASYMMETRIC_KERNEL`, ...),
   `channel_pad.fill_padding_channels` sets the integer data of the padding channel: activations 0, weights 1. The streams and
   the reference are built afterwards from this data.
3. On by default; `OPENEYE_PAD_CHANNELS=0` turns it off (reproduces bug #17). Only layer 0 is padded: it is the only layer whose
   activations reach the converter from the DMA stream.

## 2. Results

| Layer (random data unless noted) | x passes | Without padding | With padding |
|---|---:|---|---|
| Conv 20x8x1 -> 8 | 2 | FAIL: 8/8 feature maps differ | **PASS**, 1,280/1,280 outputs = numpy |
| Conv 28x28x1 -> 32 (MNIST Conv1) | 2 | FAIL: 32/32 differ (hangs 20,000 cycles in state 10 first) | **PASS**, 25,088/25,088 = numpy |
| Conv 28x28x1 -> 32, ramp + asymmetric kernel (`test_mnist_conv`) | 2 | FAIL (xfail, `test_mnist_conv1_without_padding`) | **PASS**, 25,088/25,088 = numpy |
| Conv 40x8x1 -> 8 | 3 | FAIL: 8/8 differ | **PASS**, 2,560/2,560 = numpy |
| `MNIST_REAL` with 1 input channel, 6 chained layers, `OPENEYE_SEED=1` | 2 (Conv1) | FAIL: iact buffer check after Conv1 | **PASS**, every inter-layer buffer and the outputs |

"= numpy": `tools/verify_conv_output.py` recomputes the layer from the raw integers the DUT received and checks every output word;
the dumped data shows channel 1 all zero and its weights all 1. The DMA output of the padded layers has non-zero padding slots
(3,584 at 28x28); a real two-channel layer of the same size shows the same count (768 at 20x8 in both), so this is the existing
bug #9 behaviour, not caused by the padding. Not padded (unchanged): `test_conv_const.py` 34/34 PASS and the mapping tests
8 PASS + 2 xfail (3 channels, as before), none of them padded (their 1-channel layers are 8 wide); the 9 single-layer profiling
cases change by 0 cycles vs `baseline_2026-10-22`. Python unit tests: `test/test_channel_pad.py` 10 PASS (the 11 failures of
`test_dense_output.py` are pre-existing).

**Cost** (MNIST Conv1, single layer; the one-channel numbers are those of the failing run without padding):

| | 1 channel (wrong result) | padded (1 + 1 zero channel) | change |
|---|---:|---:|---:|
| load_iact (DMA words) | 100 | 196 | +96 |
| load_wght (DMA words) | 120 | 480 | +360 |
| compute (cycles) | 9,622 | 9,638 | +16 |
| total cycles | 39,645 | 40,117 | **+472 (+1.2 %)** |

In the whole model: Conv1 32,980 cycles (vs 35,591 with a real random second channel: the zero activations are skipped), model
241,250 cycles = 965 us at 250 MHz (`model_mnist_real_c1`). Weights `+-1` instead of `1` in the padding channel give the same
cycle counts (`run_padw.py`), so the value does not matter as long as it is non-zero.

## 3. New bug #22: all-zero packed weight words

The first version padded with zero weights and failed everywhere (28x28: 32/32 maps wrong after a hang; 20x8, 40x8, model: wrong
values). Probes on real two-channel layers (no padding), weights zeroed after all data hooks (`probe_zerok.py`):

| Zeroed weights (Conv 20x8x2 -> 8) | Result |
|---|---|
| none (control) | PASS |
| channel 1, every filter | **FAIL** (also at 8x4x2 -> 4, one x pass: not related to bug #17) |
| channel 1, filter 0 only | PASS |
| filter 0, every channel | PASS |

The serial conv weight stream packs `PARALLEL_MACS = 2` weights per 24-bit word (8-bit value + 4-bit overhead each; two
neighbouring filters at the same kernel tap) in dense form (overhead always 0), and `WghtStreamMapper.SKIP_ZERO_WORDS = True`
drops every all-zero word. `count_words.py`: the padded Conv1 weight section has **240 words with zero padding weights instead of
480**; the RTL still waits for 480, so the bias words that follow are taken as weights. A single zero weight next to a non-zero
one is harmless (the word stays), which is why "channel 1, filter 0" and "filter 0" pass.

Keeping the all-zero words does not fix it (`probe_skip.py`, `SKIP_WORDS=0`): the stream then has the right length, but the
layer still computes wrong values (20x8x2 -> 8 with 30 % zero weights) or hangs in state 10 with the psum FSM in
`CALCULATE_PSUM` (8x4x8 -> 16 with 10 % zero weights; padded Conv1 with zero padding weights). So the PE side also
mishandles an all-zero weight word (presumably read as "no weight"/end of data), consistent with the comment in the mapper
("safe only for the overhead-encoded conv format, where meaningful words are never all-zero"). Every existing test hides the
problem: `DRAMContents` replaces every zero weight by +-1 and the `sparse_wghts` pattern alternates zero and non-zero filters.

**Impact:** a trained int8 model has zero weights; with a fraction p of zeros, a word is all zero with probability about p^2
(1 % at p = 10 %), and MNIST Conv2 alone has 18,432 weights = 9,216 packed pairs. Such a model fails until #22 is fixed. Not investigated
further (needs the PE weight path, RTL). Possible directions: real zero-skipping in the serial conv mapper (the overhead field
exists but is always 0) plus the matching RTL handling, or an RTL fix for all-zero words; a Python-only mitigation would be to
order the filters so that no pair of neighbouring filters shares a zero tap (not always possible).
