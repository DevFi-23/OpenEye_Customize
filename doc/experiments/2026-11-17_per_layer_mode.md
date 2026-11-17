# 2026-11-17: sparse or dense per layer (proposal, nothing changed)

Question: run every layer in the mode that suits it (sparse for layers whose input has many zeros, dense for the others)
instead of one mode for the whole network. Analysis on the 16 measured runs of `doc/perf/activation_2026-11-12_rounding`
(trained MNIST, image 0, default rounding); no RTL or Python change.

## 1. Two different "mixed" ideas

* **Per operand** (proposal of 2026-11-11, README_FI section 2 "Chế độ trộn"): activations stay sparse (zero skipping),
  weights are sent as plain 8 bits, for every layer; a build-time choice.
* **Per layer** (this note): each layer chooses the sparse or the dense datapath at run time (a status bit), with the
  formats of today's two builds.

## 2. Measured per layer (cycles of the layer, its weight load included)

| Layer | Input zeros (ReLU) | ReLU: sparse / dense | Leaky ReLU: sparse / dense | SiLU: sparse / dense | hard-swish: sparse / dense |
|---|---:|---:|---:|---:|---:|
| Conv1 | 0 % | 32,619 / **32,246** | 32,619 / **32,246** | 32,651 / **32,278** | 32,651 / **32,278** |
| Conv2 | 43.5 % | **112,010** / 114,380 | 118,928 / **114,380** | 120,221 / **114,412** | 120,490 / **114,412** |
| Conv3 | 87.3 % | **52,754** / 59,788 | 64,138 / **59,788** | 64,906 / **59,820** | 64,730 / **59,820** |
| Dense | 74.3 % | 13,107 / **10,733** | 13,930 / **10,733** | 14,018 / **10,733** | 13,982 / **10,733** |
| Whole net | | 218,564 / 225,221 | 237,689 / 225,221 | 239,870 / 225,317 | 239,927 / 225,317 |
| Best mode per layer | | **215,817 (−1.26 %)** | 225,221 (0) | 225,317 (0) | 225,317 (0) |

(pooling layers are the same in both modes; the zero shares of Leaky ReLU / SiLU / hard-swish are 6-24 %, section 6.16
of README_FI.)

* With today's formats, per-layer choice helps only the ReLU model (−1.26 %: Conv1 and the Dense layer dense, Conv2 and
  Conv3 sparse); for the other activations every layer prefers dense, which a dense build already does.
* The Dense layer prefers dense even with 74 % zeros: its weight load (7,920 sparse / 4,752 dense words) dominates.

With the per-operand mixed mode (weights 8 bit everywhere; estimate: sparse layer minus its weight-load difference,
upper bound because zero weights are no longer skipped):

| | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Mixed per operand | 203,012 | 222,137 | 224,318 | 224,375 |
| Mixed + per-layer FSM choice | 202,735 (−0.14 %) | 221,831 (−0.14 %) | 223,924 (−0.18 %) | 224,017 (−0.16 %) |

Once the weights are 8 bit, the two FSMs differ only in compute: the sparse FSM is slower than the dense one only when the
layer input has almost no zeros (Conv1, 0 %: 9,582 against 9,305, +3 %; the Dense layer of SiLU, 6.7 %: 4,356 against
4,239), and already faster at 7-11 % (SiLU Conv2 89,221 / 89,556, Conv3 43,698 / 44,756). The per-layer choice is then
worth 0.1-0.2 % on MNIST.

## 3. Design, if it is done

Prerequisite: the per-operand mixed mode, so that both FSMs read the same 8-bit weights (otherwise the weight bus must
carry the 12-bit sparse format for the sparse layers and the dense layers lose their bandwidth saving).

RTL:

| File | Change |
|---|---|
| `test/cocotb_fpga/regmap.yaml` | status field `layer_dense` (1 bit) in a free slot of the last status word (the word counts at DMA 32 / 64 / 128 bit checked as for the activation fields) |
| `hdl/OpenEye_FPGA.v` | the field from `dma_storage` to `OpenEye_Parallel` (as `raw_wght_i`) and to the iact constructors |
| `hdl/OpenEye_Parallel.v` | the bit into the PE configuration stream (`data_stream_reg`, 3 spare bits next to `raw_wght`) |
| `hdl/PE.v` | both FSMs in one PE: today a generate keeps one (`gen_sparse_fsm` / `gen_dense_fsm`); a run-time choice needs both blocks (separate register copies plus muxes on the SPad / psum address paths) or one merged FSM with a `layer_dense` branch |
| `hdl/data_pipeline_iact.v` | the store-every-word condition `\| !SPARSITY_EN` becomes `\| layer_dense` |
| `hdl/iact_stream_constructor.v` | the overhead encoding becomes run-time: a dense layer sends every value with overhead 0 (the iact transfer stays 12 bit; on-chip traffic only) |

Python: `layer_parameters.py` decides `layer_dense` per layer (rule: expected zero share of the layer input below about
5 % -> dense; the image input -> dense; a ReLU-fed input -> sparse; or measure the zero share on the calibration images in
`onnx2model`); `conv_mapper.py` / `dense_mapper.py` pack the bit; the profiler records the mode per layer; tests with
models that alternate the modes, unit tests for the rule.

Cost: two FSMs in each of the 48 PEs. Yosys on one PE (`2026-11-11_mixed_mode/pe_area.sh`): the PE's own logic is 513 LUT
sparse and 410 dense, so the second FSM is a large part of a PE: roughly +100-200 LUT per PE, +5-10k LUT (+8-16 %) for
the chip, plus muxes on the SPad address paths (timing risk).

## 4. Recommendation

Not now: after the per-operand mixed mode it is worth 0.1-0.2 % on MNIST (1.3 % without it) for +8-16 % LUT and a PE
rewrite. Do the per-operand mixed mode first (ReLU −4.5 to −7 %, the other activations about dense, fewer LUT), then
measure a larger model: if some large layer with almost no input zeros shows a big sparse-FSM overhead (a first RGB
convolution, say), the cheaper fix is to lower that overhead in the sparse FSM (mixed mode variant B: weight column
addresses computed instead of read from the weight address SPad) rather than a second FSM in every PE.
