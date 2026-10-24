# 2026-10-24: bug #22 investigated - zero weights break the serial conv weight encoding (no RTL change)

No RTL and no repository code was changed. Tools in `2026-10-24_bug22/` (section 7). Platform of all runs unless noted:
2x2 clusters, `NUM_GLB_PSUM=4`, `NUM_GLB_WGHT=3`, `NUM_GLB_IACT=1`, DMA 64 bit, psum 20 bit, `SPARSITY_EN=1`, `PARALLEL_MACS=2`.

## 1. Summary

A conv layer whose weights contain zeros is computed wrong, or hangs, on the serial (FPGA) path. The cause is a mismatch
between the zero-compressed weight format the Python mapper (`ConvWghtStreamMapper.write_wght_data_storage`) writes and
the format `hdl/data_pipeline_wght.v` decodes, plus two stream-level problems in the serializer. Six mechanisms, all
reproduced in RTL simulation and by a cycle model of the RTL that matches it write for write:

| | Mechanism | Side |
|---|---|---|
| F1 | an all-zero column (all filters of one iact position) has no entry; the RTL cannot create an empty column (one column step per word at most), so every later column of the PE shifts and the last pointer is missing | format mismatch |
| F2 | a column with an odd number of entries gets a padding slot `(0, 0)`; the RTL counts that slot as one position, the mapper does not, and also carries all trailing zeros of the column into the overhead of the next column's first entry: one position is counted twice, the next column is off by one filter | format mismatch |
| F3 | a run of more than 15 zeros does not fit the 4-bit overhead field (columns of more than 16 filters, or carried zeros) | format mismatch |
| F7 | the serializer emits, for every PE, as many words as PE (0,0,0) has (`create_complete_wght_stream`); with compression the PEs differ and longer ones are cut | Python |
| F8 | `SKIP_ZERO_WORDS` drops the all-zero tail words, so the weight stream gets shorter; `layer_mapper` sets `trans_cycles_wght` to the emitted length (so the stream itself stays aligned), but every PE still receives `used_wght_per_PE / 2` words (the dense count) from the weight buffer, so a PE block no longer matches its data (corrected: an earlier version of this document said the RTL takes bias words as weights) | Python |
| F9 | the RTL resets the data SPad write address at every all-zero word, and a PE captures one word beyond its block; when the block ends with zero words (compressed data shorter than the block) that extra word, if it is real data (multi-transmission layers), lands at address 0 and sets `second_spad_words` to 2, and the PE hangs in `CALCULATE_PSUM` | format mismatch |

Correction of 2026-10-22 (`2026-10-22_bug17_channel_pad.md` section 3, README section 9 of that day): the conv mapper is
**not** dense (zeros are skipped with an overhead count; the dense `write_wght_data_storage` of the base class is overridden);
"the PE also mishandles all-zero words" was F1/F2/F9 in `data_pipeline_wght`, not the MAC loop; and the failure needs no pair
of zeros: one zero at the last filter of a column with an odd count (F2) is enough, so the "p^2" estimate was wrong.

**Impact on the trained int8 MNIST model** (`doc/demo_notebooks/mnist_quantized_model.tflite`, 1 % zero weights): Conv2 140
of 384 PE weight loads decode wrong, Conv3 116 of 384 (Conv1: 0 of 24, its single zero is harmless); in RTL simulation Conv2
and Conv3 with these weights fail (hang). Every existing test hides the problem: `DRAMContents` replaces each zero weight by
+-1, and `test_conv3x3_sparse` passes for a configuration-specific reason (section 6).

**Fix without RTL change** (prototype `encoder.py`; integrated into `src/` the same day, section 8): an encoder that only writes what the RTL decodes
correctly. Verified offline on 6 layer shapes x 9 zero patterns and the trained MNIST weights (0 wrong loads) and in RTL
simulation (12 layer runs pass, incl. MNIST Conv1/Conv2 with the trained weights and the existing sparse test; MNIST Conv3
with the trained weights: every output equal to numpy, the stream check fails with bug #9 as before). Identical stream for
weights without zeros, so no existing test or baseline changes. Same DMA words; compute cycles drop slightly with zeros.

## 2. The format, as the RTL decodes it

Serial conv weights reach each PE as 24-bit words of two 12-bit entries `{overhead[3:0], value[7:0]}`. For one PE the
weights form columns: one column per iact position (kernel x, channel), holding the weights of `M0` filters
(`filters_reg_M0` = `used_psum_per_PE`, 6-bit field; `filters_w` = 16 when 0). `data_pipeline_wght` writes:

- the data SPad: one word per non-zero input word, the entry-0 overhead corrected at column wraps; the write address
  restarts at 0 after any cycle without a non-zero word (F9);
- the address SPad: the running count of data words at each column end (the PE reads column k as data words
  `[addr[k-1], addr[k])`); the column ends when the positions counted reach `filters_w`: each entry counts `overhead + 1`,
  the padding slot counts 1 (F2); one column step per word (F1); an overshoot of exactly one position is corrected
  (`over_ending`), which is what makes odd columns ending at filter `M0-1` work;
- `second_spad_words` = last data address + 2, which bounds the PE's MAC loop (F9).

The PE reads column k entry by entry: position += overhead, weight[position] = value, position += 1.

## 3. Evidence

**RTL dumps** (`probe_spad.py`): unique weight values per (c, f, ky, kx), then every write into the weight address and data
SPads and every input word of all 48 PEs. Conv 20x8x2 -> 8: control without zeros: pointers `[4, 8, 12, 16, 20, 24]`, every
PE decodes to the weights (`check_spad.py`: 0/48 wrong). Channel 1 all zero (F1): pointers `[4, 5, 8, 9, 12]` instead of
`[4, 4, 8, 8, 12, 12]`, the entry `(4, oh 8)` meant for filter 0 of column 2 is read as filter 8 of column 1: 48/48 wrong.
30 % zeros: 48/48 wrong (F2 in PE 0000: column 3 has 3 entries and 2 trailing zeros, entry `43` of column 4 gets overhead 5
instead of 4 and column 4 is cut one word early; F7 in PE 0001: 18 words, cut to PE 0000's 16, last column missing).

**Cycle model** (`wght_pipeline_model.py`): the registers of `data_pipeline_wght` that reach the SPad ports, with the RTL
widths. Replaying the recorded input words gives exactly the RTL's address and data SPad write sequences for all 336 PE loads
of 7 runs (with and without `SKIP_ZERO_WORDS`, 0 to 50 % zeros, channel zero; `validate_model.py`), and the
`second_spad_words` = 2 of the hang (F9).

**Offline end-to-end check** (`offline_check.py`): repository mapper -> serializer -> cycle model -> PE reading, compared
with the layer's weights (intended columns from the mapper run on unique ids); the RTL takes the dense word count per PE,
and every PE captures one non-zero word beyond its block. It predicts the RTL result in every simulated case (the 20x8 and
8x4 runs, MNIST Conv2/Conv3 with trained weights).

| Layer (sweep, `sweep.py`) | 5 % | 10 % | 30 % | 50 % | 90 % | 100 % zeros | channel 0 zero | filter 0 zero | kernel row 0 zero |
|---|---|---|---|---|---|---|---|---|---|
| repository, every shape below | wrong | wrong | wrong | wrong | wrong | wrong | wrong | ok | wrong |
| candidate encoder, every shape below | ok | ok | ok | ok | ok | ok | ok | ok | ok |

Shapes: 20x8x2->8, 8x4x8->16 (2 kernels per calculation, 2 transmissions), 8x4x4->32, 28x28x2->32 (MNIST Conv1 padded),
14x14x32->64 (MNIST Conv2, 32 transmissions), 7x7x64->64 (MNIST Conv3); 3 seeds per random pattern ("wrong": at least one PE
load decodes wrong, in practice most of them). "Filter 0 zero" works today: each column has one leading zero.

## 4. Candidate encoder (`encoder.py`)

Per column of `M0` weights:
1. non-zero weight -> `(w, zeros since the previous entry of the column)`; runs over 15 zeros are cut by explicit zero
   entries `(0, 15)` (16 positions each) (F3);
2. the column ends at filter `M0-1`: if the last weight is zero, the padding slot covers it when the entry count is odd and
   exactly one zero trails, otherwise an explicit zero `(0, trailing - 1)` ends the column; an all-zero column becomes
   `(0, M0-1)` (F1, F2); never `(0, 0)` in entry 0 with the padding slot after it (an all-zero word): an earlier gap
   `(v, g)` is split into `(0, g-1), (v, 0)` instead, which makes the count odd;
3. no zeros carried into the next column; every column starts at a word boundary (padding slot when the count is odd);
4. the PE block (the `ceil(used_wght_per_PE / 2)` words the RTL transfers per PE) contains no all-zero word: after the data
   it is filled with `[(0, 0), (0, 1)]` (value 0, 3 positions per word, so only columns the PE never reads; the pointer count
   stays below the dense one) (F9); every PE block has the dense length and `SKIP_ZERO_WORDS` is off (F7, F8).

For weights without zeros it produces exactly the repository stream (checked word for word on 8 shapes, 30 to 15,360 DMA
words). Installed for the RTL runs by `probe_spad.py` (`B22_ENCODER=new`), which wraps the unmodified testbench.

## 5. RTL verification of the candidate (`run_spad.py`, results checked by the testbench and `tools/verify_conv_output.py`)

| Layer | Weights | Repository | Candidate |
|---|---|---|---|
| 20x8x2 -> 8 | 30 % zeros / 90 % / channel 1 zero | FAIL (30 % and channel 1; also 10 %/50 % without `SKIP_ZERO_WORDS`) | **PASS** each |
| 8x4x8 -> 16 (2 kernels/calc., 2 transmissions) | 30 % / 50 % zeros / none | FAIL (30 %) | **PASS** each |
| 8x4x4 -> 32 | 30 % zeros, channel 1 zero (empty 16-filter columns) | - | **PASS** each |
| MNIST Conv1 28x28x1 -> 32 (padded, bug #17) | trained int8 | PASS (1 harmless zero) | **PASS** |
| MNIST Conv2 14x14x32 -> 64 | trained int8 (189 zeros) | FAIL (hang) | **PASS** |
| MNIST Conv2 shape | 30 % zeros | - | **PASS** |
| MNIST Conv3 7x7x64 -> 64 | trained int8 (418 zeros) | FAIL (hang, no output) | 3,136/3,136 outputs = numpy; the stream check fails with bug #9 as before (`test_mnist_conv` xfail) |
| `test_conv3x3_sparse` 32x1x4 -> 8, `NUM_GLB_IACT=3` (`run_sparse.py`) | checkerboard 50 % | PASS | **PASS** |

The first candidate, without the filler words of rule 4, passed the single-transmission layers but hung 8x4x8 -> 16 and
MNIST Conv2/Conv3; PE state snapshots (`B22_SNAPSHOT`) showed `second_spad_words_wght = 2` in the hanging PEs, which the
model reproduced and traced to F9.

Cost (profile of the runs): weight DMA words unchanged (480 / 15,360: the per-PE block length is fixed by the RTL
configuration, so skipping zeros cannot shorten the stream without an RTL change); compute cycles 1,054 dense -> 1,001
(30 % zeros) -> 963 (50 %) at 8x4x8 -> 16; MNIST Conv2 with the trained weights 90,297 compute cycles (dense random weights:
90,193 in `model_mnist_real_c2`).

## 6. Open points

- `test_conv3x3_sparse` (`NUM_GLB_IACT=3`, height 1, checkerboard zeros) passes with the repository encoding and with the
  candidate: in that configuration the RTL takes 24 words per PE, the same as the compressed checkerboard data, so F8 does
  not occur and the checkerboard has no F1/F2 column. The offline check, which assumes `ceil(used_wght_per_PE / 2)` words
  per PE (true for every layer in section 3), does not model that configuration.
- RTL-side improvements (need approval, not done): empty columns (F1), padding-slot semantics (F2), address reset (F9);
  a variable weight stream length would let zero weights also save DMA words.
- Dense/GEMM weights use the raw format (`raw_mode_i`, `SKIP_ZERO_WORDS = False`) and are not affected.

## 7. Tools (`2026-10-24_bug22/`)

| File | Purpose |
|---|---|
| `probe_spad.py`, `run_spad.py`, `run_sparse.py` | cocotb probe around the unmodified testbench: weight patterns (`none`, `chan1`, `rand<p>`, `file:<json>:<layer>`, ...), SPad/input-word dump, PE state snapshots, `B22_ENCODER=new`, `B22_NOSKIP=1` |
| `wght_pipeline_model.py`, `validate_model.py` | cycle model of `data_pipeline_wght` and its check against the RTL dumps |
| `show_spad.py`, `check_spad.py` | SPad contents of a dump, decoded and compared with the weights |
| `mapper_words.py`, `offline_check.py`, `sweep.py` | per-PE mapper words; end-to-end offline check; shape x pattern sweep |
| `encoder.py` | the candidate encoder |
| `real_weights.py`, `real_mnist_conv_weights.json` | conv weights of the trained int8 MNIST model and their offline check |

## 8. Fix integrated (2026-10-24, approved)

`src/open_eye/conv_wght_encoding.py` (the encoder of section 4), `ConvWghtStreamMapper.write_wght_data_storage` (columns from
the dense layout of `write_dense_wght_data_storage`, the old loop without compression, then `encode_columns`;
`SKIP_ZERO_WORDS = False`), `DRAMContents` keeps real zero conv weights, `OPENEYE_TFLITE_CONV` loads trained conv weights,
`src/open_eye/wght_pipeline_model.py` for the unit tests (`test/test_conv_wght_encoding.py`, 39 tests).

- Same stream as the committed mapper for weights without zeros (8 shapes) and as the RTL-verified prototype for 27
  zero-weight cases (incl. the trained MNIST weights).
- RTL regression: `test_conv_const` 34 pass; `test_mnist_layers` 26: 21 pass, 5 xfail as before (incl. the new
  `test_trained_mnist_conv`: Conv1 25,088/25,088, Conv2 12,544/12,544, Conv3 3,136/3,136 outputs equal numpy, Conv3
  xfail by bug #9); `test_conv3x3_sparse` 32x1x4 -> 8 pass, 32x4x8 -> 16 fails as it did before the change (bug #23;
  its weights decode correctly in the model, so the failure is on the activation side).
- Profiling: the 9 single-layer cases unchanged; the model cases 13 to 579 cycles faster (random conv weights now keep
  1 to 5 % zeros), same DMA words: `doc/perf/baseline_2026-10-24/`.
- Limitation of the offline check (section 3): it treats a shortened stream (F8) as broken for every PE; in RTL such a
  stream can work (single transmission, no odd columns, equal PE lengths: `test_conv3x3_sparse` 32x1x4 -> 8 with the old
  encoding). Its other predictions matched every simulated case.

