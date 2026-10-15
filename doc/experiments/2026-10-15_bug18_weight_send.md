# Investigation 2026-10-15: bug #18 (wrong results for filters 32-63) is a weight-send length bug

No RTL and no repository code was changed. Tools: scratch reproducers (Conv layers through `test_conv_const._run_conv_const`),
a scratch cocotb probe around the unmodified `OpenEye_FPGA_tb` that logs the weight-buffer read address of every weight send,
random-data runs (the const/ramp hooks removed), and a temporary git worktree with a one-line Python change (removed afterwards).

## 1. Localisation

| Case (W x H, channels, filters, QUANT_AMOUNT=64) | Const weights (existing tests) |
|---|---|
| 8x4, 4/8/16/32 ch, 32 f; 8x4, 4/8/16/32 ch, 64 f; 8x4, 64 ch, 32 f; 14x4, 32 ch, 32 f | PASS |
| 8x4, 64 ch, 64 f; 14x2 / 14x4 / 16x4, 32 ch, 64 f; MNIST Conv2 14x14x32->64; Conv3 7x7x64->64 | FAIL, filters 32-63 only |

Every failing case has 32 weight sends per pass (`needed_wght_cycles x iact_channel_max_cycles` = 2x16 or 4x8) and
`trans_cycles_wght` = 15,360 weight words; every passing case has at most 16 sends.

The probe shows each send reading **192** weight-buffer addresses (`wghts_per_pe` = 192), so 32 sends need 6,144 addresses, but
`wght_buffer_rd_addr` is 12 bits (`BUFFER_WIDTH_WGHT` = 12): the send for filter group 1 / channel chunk 6 starts at 4032, wraps
at 4096 and continues at 0, 128, 320, ... - real weights of filter group 0, misaligned by 4096 mod 96 = 64 positions.

The writer, however, stored only 3,071 addresses (15,360 words / 5 words per address). Half of all reads, in passing cases too,
fall into never-written addresses and return `X` (the PE does not store them).

## 2. Root cause

- `src/open_eye/conv_mapper.py` builds the register dict with the key `used_wght_per_PE` **twice** (since 3fbb272 / fa602e6,
  2026-07):
  ```python
  "used_wght_per_PE": math.ceil(layer_params.used_wght_per_PE/params.PARALLEL_MACS),   # packed: 96
  ...
  "used_wght_per_PE": layer_params.used_wght_per_PE,                                   # unpacked: 192, wins
  ```
  In a Python dict literal the later key wins, so the hardware receives the unpacked count.
- RTL commit 3e2e20f (2026-09-19, "Fixed the two-MAC weight-loading shortfall") changed the send loop of `OpenEye_FPGA.v` from
  `fsm_sending_cycle + PARALLEL_MACS` to `+ 1` with the comment "wghts_per_pe and the RAM address count packed words": the RTL
  now expects the packed count (96) but still gets 192.
- Consequence: every send reads twice as many addresses as it should, send k starts at 192k instead of 96k, i.e. **every
  layer with more than one weight send gets the weights of the wrong channel chunk**. The existing tests do not see it because
  `OPENEYE_CONST_WGHTS` gives every channel and filter the same weights; only the wrap at 4096 changes the kernel-position
  alignment and makes it visible.

## 3. Confirmation with random data (const/ramp hooks removed)

| Case | Current code | With the one-line Python fix |
|---|---|---|
| 8x4, 4 ch, 4 f (one send) | PASS | PASS |
| 8x4, 8 ch, 4 f | **FAIL** (4/4 maps) | PASS |
| 8x4, 4 ch, 32 f | PASS | - |
| 8x4, 32 ch, 32 f | **FAIL** (32/32) | PASS |
| 8x4, 8 ch, 64 f | **FAIL** (64/64) | PASS |
| 14x14, 32 ch, 32 f (= baseline case `mnist2`) | **FAIL** (32/32) | PASS |

So with real weights every convolution with more than 4 input channels is currently wrong, including the baseline cases
`mnist2` and `mnist3`.

## 4. Proposed fix (Python only, no RTL change, not applied)

Delete the second key in `src/open_eye/conv_mapper.py`:
```python
        "used_wght_per_PE": layer_params.used_wght_per_PE,      # remove: overrides the packed value above
```
For `PARALLEL_MACS = 1` both values are equal, so nothing changes there; Dense, Depthwise and Pooling use other mappers.

Results with the fix (temporary worktree, RTL of 949559e):

| Check | Result |
|---|---|
| Failing #18 cases: 8x4x64->64 const, random cases above | all PASS |
| MNIST Conv2 14x14, 32 -> 64 (real shape) | **PASS** |
| MNIST Conv3 7x7, 64 -> 64 (real shape) | **values all correct**; the test still fails on the DMA-stream file check of bug #9 (padding cells of 7-wide images) |
| 9 baseline cases | 9/9 PASS; **cycles: mnist1 65,800 -> 55,048 (-16.3 %), mnist2 87,032 -> 65,528 (-24.7 %), mnist3 26,728 -> 20,584 (-23.0 %)**, 32x3_f16 -2.6 %, others 0; DMA words unchanged |

The cycle reduction is all in `compute` (-32 %): each weight send now takes 96 instead of 192 cycles. The existing baseline
`doc/perf/baseline_2026-10-10` was measured with the wrong send length and has to be replaced after the fix.

Verification still to do after approval: the 34 Conv + 63 GEMM/Dense regression, the new `test_mnist_layers.py`, random-data
variants of the baseline cases, a new baseline snapshot.

## 5. Separate finding: bug #18b (filters > 32 and not a multiple of 32)

40 and 48 filters (8x4, 4 channels) still fail with the fix, even for filter 0 from row y=1 on. The Python side is inconsistent:
it tells the DUT `psum_output_words = 768` but writes a 1,024-line reference stream (2 passes x 32 filter slots). The psum
address generator parameters (`psum_pagu_addr_inc_3` = 24, `psum_pagu_loop_limit_4` = 11) are the first suspects. MNIST uses
32 and 64 filters and is not affected.

## 6. Word-by-word verification of the fix (2026-10-15, before applying it)

The testbench compares the DUT with a reference built by the same Python package that builds the input stream, so a mistake
shared by both could pass. Every output word was therefore checked independently (scratch version of what is now
`tools/verify_conv_output.py`): the layer is recomputed with numpy from the raw integers the DUT received
(`dram.fmap`, `dram.weights`, `dram.bias`), each 64-bit DMA output word is split into its two 20-bit signed psum slots, each slot is
placed at the (filter, x, y) given by `output_order`, and

- every result slot must equal numpy (the transposed kernel orientation is printed as a control: it must differ),
- every (filter, x, y) must be decoded exactly once (no missing or duplicated output),
- the bits above the two psum slots must be 0, no word may contain X,
- the testbench reference is compared with numpy as well.

With random data a wrong value or a wrong position cannot match by chance (thousands of distinct values).

| Case (W x H, channels -> filters) | Data | Result words identical to the reference | Values = numpy | Coverage | Testbench ref = numpy |
|---|---|---|---|---|---|
| 8x4, 8 -> 4 | random | 64/64 (+64 padding-only lines) | **128/128** | complete | yes |
| 8x4, 32 -> 32 | random | 512/512 | **1,024/1,024** | complete | yes |
| 8x4, 8 -> 64 | random | 1,024/1,024 | **2,048/2,048** | complete | yes |
| 8x4, 64 -> 64 (former #18 case) | random | 1,024/1,024 | **2,048/2,048** | complete | yes |
| 14x14, 32 -> 32 (= baseline mnist2) | random | 3,136/3,136 (+448 padding-only) | **6,272/6,272** | complete | yes |
| 28x28, 4 -> 32 (= baseline mnist1) | random | 12,544/12,544 (+1,792 padding-only) | **25,088/25,088** | complete | yes |
| MNIST Conv2 14x14, 32 -> 64 | random | 6,272/6,272 (+896 padding-only) | **12,544/12,544** | complete | yes |
| MNIST Conv2 14x14, 32 -> 64 | ramp, asymmetric kernel | 6,272/6,272 | **12,544/12,544** | complete | yes |
| MNIST Conv3 7x7, 64 -> 64 | random | 1,344/1,792 | **3,136/3,136** | complete | yes |

No word contained X, no bit above the psum slots was set, no value exceeded 20 bit.

Lines that differ from the reference file are of two kinds, neither is a result error:
- **padding-only lines** (all slots of the reference are padding): the DUT sends the psums of PE slots that hold no output (bias
  plus partial sums) where the reference has zeros. The testbench ignores all-zero reference lines on purpose; the host must
  ignore these slots, and they cost readout bandwidth.
- **Conv3 (7-wide rows):** the last psum of each row shares a word with a padding slot; the result slot is correct, the padding
  slot is non-zero. This is bug #9 and the reason the Conv3 test still fails the stream-file check.

## 7. Fix applied (2026-10-15, approved after the word-by-word check)

`src/open_eye/conv_mapper.py`: the second `used_wght_per_PE` key removed (comment added at the remaining one). No RTL change.

| Check after applying | Result |
|---|---|
| `test_conv_const.py` (34) | 34/34 PASS, unchanged |
| `test_gemm_layer.py` (63) | 40 PASS / 23 FAIL, identical per test (Dense bug #5) |
| `test_mnist_layers.py` (19, new) | mapping 8 passed + 2 xfailed (3 channels); MNIST Conv2 passed; Conv1 xfailed (#17), Conv3 xfailed (#9, all 3,136 values correct); 6 random-data tests passed, each with `tools/verify_conv_output.py` |
| Baseline (9 cases) | 9/9 PASS, saved as `doc/perf/baseline_2026-10-15/` |

New tools: `tools/verify_conv_output.py` (this check, permanent) with `OPENEYE_DUMP_VERIFY=1` in the testbench, and
`_run_conv_const(..., random_data=True)`.

