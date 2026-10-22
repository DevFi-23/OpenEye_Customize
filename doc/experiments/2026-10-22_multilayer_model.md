# 2026-10-22: running a whole multi-layer model - what works, what is missing, how to measure phases

No RTL and no repository code was changed. Tools (`2026-10-22_multilayer/`): `run_model.py` (runs a multi-layer net through the
unmodified `OpenEye_FPGA_tb` on the standard platform: 2x2 clusters, `NUM_GLB_PSUM=4`, `NUM_GLB_WGHT=3`, DMA 64 bit, psum 20 bit,
max-pool hardware, random data, profiler on) and `probe_model.py` (defines `LAYER=MNIST_REAL` = the architecture of
`models/mnist_conv_net.py`, and a per-layer phase profiler). RTL = `dev` at `10bcaf7` (bug #19 fixed).

## 1. How the testbench runs a model

`OpenEye_FPGA_tb.execute_model` sends one DMA stream per layer. Layers are **chained on chip**: a non-final layer writes its
requantized outputs back into the iact buffer (main FSM state 11 `RECEIVE_PSUMS_TO_IACT`, psum FSM `SEND_PSUM_TO_IACT`), the
next stream skips the activations (`skipIact`), and after every layer the testbench compares the iact buffer with the reference
input of the next layer (`compare_iact_storage`). Only the last layer sends results out (compared value by value).

The reference between layers is `slo.batchnorm_output`: `floor(mant * x / 2^shift)`, no offset, **no int8 clamp, no ReLU**, and
`_to_ram_format` adds 256 to negative values only, so a reference value in 128..255 looks like a wrapped int8 value: the check
follows the hardware's arithmetic, it does not check the semantics of a real int8 network.

## 2. Results (random data)

| Model | NUM_GLB_IACT | Result |
|---|---|---|
| `LAYER=MNIST` of `data_create.py`: Conv 28x28x2->16, MaxPool, Conv 14x14x16->16, MaxPool, Conv 7x7x16->16, Dense 784->10 | 1 and 3 | **PASS** (every inter-layer buffer check and the final outputs); failed at the Dense layer before the bug #19 fix |
| `MNIST_REAL` (architecture of `models/mnist_conv_net.py`) with the input **padded to 2 channels**: Conv 28x28x2->32, MaxPool, Conv 14x14x32->64, MaxPool, Conv 7x7x64->64, Dense 3136->10, `QUANT_AMOUNT=64` | 1 | **PASS** |
| `MNIST_REAL` with **1 input channel** (the real model) | 1 | **FAIL**: iact buffer check after Conv1+Pool1 (bug #17) |

The 7-wide Conv3 written back into the Dense input passes, so bug #9 (non-zero padding slots in the readout stream) does not
block chaining. The stall detector printed "FSM stuck in state 11 for 20000 cycles" for the two 64-filter layers: not a hang,
those layers compute for 90,000 and 44,000 cycles inside state 11 (section 4).

Cost of the 2-channel workaround: Conv1 32,508 -> 35,591 cycles (+9.5 %, +1.3 % of the model), +456 DMA words.

## 3. What is still missing

### 3a. To simulate the real MNIST net (testbench semantics)

| # | Item | Kind | Solution |
|---|---|---|---|
| 1 | Bug #17: one input channel on images wider than one x pass (Conv1 28x28x1) | RTL or Python | Python: pad the input to 2 channels (zero channel, zero weights) in the mapper - verified above; or fix the one-channel writer address (RTL, needs approval) |
| 2 | `QUANT_AMOUNT` must be >= the largest filter count (64) | configuration | build with `QUANT_AMOUNT=64` (the synthesized baseline has 32) and re-run Vivado |
| 3 | Stall detector threshold (20,000 cycles in one state) shorter than a 64-filter layer | testbench | raise `OPENEYE_FAIL_ON_STALL`/the per-state limit for model runs |
| 4 | Other models: Dense with 32 outputs and K >= 508 (bug #19b), Dense with more than 32 outputs (bug #21), layers needing several transmissions (not exercised by MNIST) | RTL / Python | investigate before running MLPs or larger nets |

### 3b. To run a trained int8 model with the right results

| # | Item | Where | Solution |
|---|---|---|---|
| A | No int8 saturation: `quantization_unit.v` truncates `prod >>> shift` to 8 bits (a value 130 becomes -126) | RTL | clamp to [qmin, qmax] before the truncation |
| B | No ReLU: `af_cluster.v` exists but is never instantiated; only its mode signal is wired | RTL | fold ReLU into the clamp: qmin = output zero point (0 for symmetric) - one programmable clamp covers saturation, ReLU and ReLU6 (two 8-bit configuration fields per layer) |
| C | Offset is added **before** the multiplication (`(psum + offset) * mant`), 8 bits; int8 TFLite adds the output zero point **after** scaling | RTL or Python | post-scale zero-point add (RTL), or symmetric activation quantization (zero point 0) in the converter; the input zero point is folded into the bias in Python |
| D | Rounding is floor (`>>>`), TFLite rounds to nearest | RTL | add `2^(shift-1)` before the shift (or accept the small error) |
| E | Mantissa sliced to 8 bits (`OpenEye_FPGA.v:1345`, `+:OFFSET_WIDTH` instead of `MANTISSA_WIDTH`) | RTL, one line | use `MANTISSA_WIDTH` (and `EXPONENT_WIDTH` on line 1344) |
| F | Bug #12: `current_filter` never increments, every filter uses the parameters of filter 0 (per-channel quantization broken) | RTL | step `current_filter` with the output channel during `SEND_PSUM_TO_IACT` |
| G | 20-bit psum: real MNIST accumulators reach about 740,000 (21 bits) | configuration | `DATA_PSUM_BITWIDTH` 24 or 32 (works for conv) - the psum buffers grow, so `BUFFER_WIDTH_PSUM` has to shrink to stay inside the BRAM (the buffers are 89 % unused, README 8c item D) |
| H | No end-to-end real-model flow: `DRAM.write_initial_data_to_dram` quantizes conv weights as `floor(w*127)`, Dense weights and the input are random; `test/cocotb_fpga/tflite.py` is an unconnected MobileNet script | Python | converter from the int8 TFLite / PyTorch model (int8 weights, int32 bias with zero-point folding, per-channel multiplier -> mant/exp, clamp bounds, flatten order of the Dense weights), real MNIST images, a bit-exact numpy model of the hardware semantics plus the TFLite interpreter as golden, accuracy over N images |

Earlier emulation (2026-10-19, 2,000 MNIST images, not repeated here): float reference 98.80 %; with 20-bit psum wrap 98.75 %,
8-bit mantissa 98.75 %, bug #12 98.60 %, **without int8 saturation 9.30 %**. Item A (with B) is the one that decides whether
the chained hardware classifies at all.

Path without RTL change: run every layer as its own layer with `send_values_out` (raw psums out), requantize, clamp, ReLU and
pool on the host and send the next input by DMA. Correct with today's RTL (plus item 1), at the cost of reading every
intermediate result and reloading every input - the opposite of the bandwidth goal, but a correctness baseline.

## 4. Measuring phases of a multi-layer model

The repository profiler (`OPENEYE_PROFILE=1`, `rtl_test_utils.profile_dma_phases`) adds all layers together and only stores
`layer_starts`. In a chained layer the main FSM computes inside state 11, so the profiler books the whole computation as
`writeback` (`compute = 0` for every intermediate layer). `probe_model.py` shows the fix: a new segment at every entry into
`GET_PARAMETERS`, and states 10/11 split by the psum FSM (1-3 = compute, 4/6 = writeback).

`MNIST_REAL`, input padded to 2 channels, ideal memory (`layers_mnist_real_c2.json`):

| Layer | load_wght | load_bias | convert | compute | writeback | pooling | total cycles | us at 250 MHz | DMA in |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Conv1 28x28x2->32 | 480 | 14,336 | 1,091 | 12,193 | 7,183 | - | 35,591 | 142.4 | 15,070 |
| Pool1 | - | - | - | - | - | 5,152 | 5,213 | 20.9 | 18 |
| Conv2 14x14x32->64 | 15,360 | 7,168 | 4,679 | 90,193 | 3,599 | - | 121,162 | 484.6 | 22,586 |
| Pool2 | - | - | - | - | - | 2,800 | 2,861 | 11.4 | 18 |
| Conv3 7x7x64->64 | 15,360 | 1,792 | 2,951 | 44,017 | 911 | - | 65,194 | 260.8 | 17,210 |
| Dense 3136->10 | 7,920 | 12 | 1,655 | 4,311 | 3 | - | 14,031 | 56.1 | 7,990 |
| **Model** | | | | | | | **244,052** | **976** | |

Shares over the model: compute 62 %, weight load 16 %, bias load 10 % (40 % of Conv1), writeback 5 %, convert 4 %, pooling 3 %.
The 16-filter `LAYER=MNIST` net: 50,024 cycles = 200 us (compute 44 %, bias 19 %, weights 10 %, writeback 9 %).

Proposed integration (Python only): per-layer counters in `profile_dma_phases` (a `layers` list next to the totals), the
state 10/11 split by the psum FSM, a per-layer table and model totals in `profile_report`, and model cases (for example the
MNIST nets) in `tools/run_profile.py` with `--compare`.

**Done the same day** (README section 6.13): the cases `model_mnist16_c2` and `model_mnist_real_c2` of `test_profile.py`, the
`layers` list of `profile.json`, the per-layer table of `profile_report`, baseline `doc/perf/baseline_2026-10-22/`. The numbers
above came from unseeded runs; with `OPENEYE_SEED=1` the nets take 50,020 and 244,050 cycles, and the integrated profiler matches
`probe_model.py` on all 6 layers (start cycles, DMA words and every phase, with `wait_psum_idle` counted as `writeback`).
