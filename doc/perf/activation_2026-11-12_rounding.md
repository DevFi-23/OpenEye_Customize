# 2026-11-12: the trained activation models, floor and round to nearest, on sparse and dense hardware

16 runs: the trained MNIST models (ReLU, Leaky ReLU 0.1, SiLU, hard-swish; `test_real_model.py`, test image 0,
`OPENEYE_PROFILE=1`) x rounding of every activation (floor / round half up, status field `act_round`) x hardware
(`SPARSITY_EN` 1 sparse / 0 dense). The default rounding (ReLU floor, the others round) is the run of
`activation_2026-11-10_sparse_dense`; the other rounding is forced by `doc/experiments/2026-11-12_rounding_modes/probe_round.py`
(`run_round.py <activation> <0|1> <tag>`: `activation_round` set after `onnx2model.finish_activations`, so the testbench
reference and the RTL use the same setting; no toolchain or RTL change). All 16 PASS: every iact buffer check and the
Dense psums bit-exact, DUT class 7.

| Model | Rounding | Sparse: total / compute | Dense: total / compute | Zeros into Conv2 / Conv3 / Dense |
|---|---|---:|---:|---:|
| ReLU | floor (default) | **218,564** / 125,647 | 225,221 / 147,856 | 43.5 / 87.3 / 74.3 % |
| ReLU | round | 219,659 / 126,742 | 225,221 / 147,856 | 38.3 / 87.3 / 72.3 % |
| Leaky ReLU | floor | 240,379 / 147,462 | **225,221** / 147,856 | 0.9 / 1.8 / 3.4 % |
| Leaky ReLU | round (default) | 237,689 / 144,772 | **225,221** / 147,856 | 24.3 / 14.7 / 18.1 % |
| SiLU | floor | 240,435 / 147,422 | **225,317** / 147,856 | 10.3 / 6.1 / 6.7 % |
| SiLU | round (default) | 239,870 / 146,857 | **225,317** / 147,856 | 11.0 / 7.1 / 6.7 % |
| hard-swish | floor | 240,244 / 147,231 | **225,317** / 147,856 | 5.6 / 13.0 / 13.3 % |
| hard-swish | round (default) | 239,927 / 146,914 | **225,317** / 147,856 | 5.9 / 14.1 / 13.1 % |

Bold: the fastest case of each model. The zeros are the same in both modes (the same integers).

* **Dense: floor and round give exactly the same cycles** (the dense FSM multiplies every value): rounding only changes
  accuracy there. The SiLU / hard-swish runs are 96 cycles longer (three 32-word table loads).
* **Sparse, ReLU:** round costs +1,095 cycles (+0.50 %; the estimate of step A was +1,070): values below one unit become 1
  instead of 0 (zeros into Conv2 43.5 -> 38.3 %).
* **Sparse, Leaky ReLU:** floor costs +2,690 cycles (+1.1 %): small negative values become -1 (zeros into Conv2 24.3 ->
  0.9 %). Step A estimated +6,885 with a model linear in the zero share; the measured saving of zero skipping is smaller
  than linear at these low zero shares (Conv2 compute 89,719 with 0.9 % zeros, 87,960 with 24.3 %, 81,042 for ReLU with
  43.5 %).
* **Sparse, SiLU / hard-swish:** floor +565 / +317 cycles (+0.2 / +0.1 %).
* Accuracy (10,000 test images, the chip's arithmetic, `doc/experiments/2026-11-02_activation/eval_10000.md`) depends
  only on the rounding: ReLU 99.35 / 99.36 %, Leaky ReLU 99.34 / 99.34 %, SiLU 99.25 / 99.27 %, hard-swish 99.33 / 99.35 %
  (floor / round). ReLU rounded matches ONNX Runtime exactly in every layer (`2026-11-12_rounding_modes/measure_ort_relu.py`;
  floor: up to 2 units, 70-97 % exact).

Choice: on sparse hardware the present defaults are right (ReLU floor: +0.5 % faster, same accuracy; the others round:
faster for Leaky ReLU and more accurate); on dense hardware rounding is free, so every activation should round, ReLU
included (bit-exact with ONNX Runtime). The fastest build per model: ReLU sparse, the other three dense.
