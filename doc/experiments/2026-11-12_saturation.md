# 2026-11-12: saturation of the activation outputs on real data

Question: Figure 3 of the progress report of 2026-11-10 shows the chip's activation output flat above some value (clamped
at 127). Do real inputs reach that region, and how large is the error then?

## Why the flat region exists

The int8 scales come from ONNX Runtime's static calibration (MinMax, symmetric, 200 MNIST training images). The conv
output (pre-activation) has one symmetric scale s_out = max |value| / 127; for Leaky ReLU, SiLU and hard-swish the large
magnitude is on the negative side. The activation output gets its own scale s_next (the next layer's input) = the largest
output seen / 127, which is the largest positive pre-activation seen, because the negative outputs of these functions are
small (Leaky ReLU 0.1 x, SiLU >= -0.28, hard-swish >= -0.375). So the int8 pre-activation can hold positive values that
never occurred during calibration, and the output clamps them at 127 x s_next:

| Model | Conv1: pre-activation ±, output up to | Conv2 | Conv3 |
|---|---|---|---|
| ReLU | 3.07, 3.07 | 6.06, 6.06 | 8.02, 8.02 |
| Leaky ReLU | 4.05, 2.76 | 12.08, 4.86 | 10.30, 6.53 |
| SiLU | 4.76, 2.89 | 8.66, 4.68 | 12.03, 6.21 |
| hard-swish | 4.89, 3.15 | 8.18, 4.75 | 12.05, 6.85 |

(127 x s_out and 127 x s_next, `doc/perf/activation_2026-11-10_sparse_dense/params.json`.) ReLU has the same bound on
both sides of the activation and saturates in the requantization instead. ONNX Runtime clamps at the same bounds
(QuantizeLinear saturates), so this is a property of the int8 model, not a chip error; only the float model has no bound.

## Measured on the 10,000 MNIST test images

`2026-11-12_saturation/saturation.py`: the four trained models built by the current toolchain, run through a numpy copy
of the chip's integer arithmetic (checked equal to the testbench reference on image 0), default rounding (ReLU floor, the
others round). "Saturated" = an output clamped at 127 (requantized value above 127, or for SiLU / hard-swish a table entry
clamped because f(x) / s_next > 127). Accuracy also with the upper bound removed (same integers, nothing clamped at the top).

| Model | Saturated outputs (Conv1 / Conv2 / Conv3, of 250.9 M / 125.4 M / 31.4 M) | Images with any | Excess when saturated: mean / max (units; share of the value) | Accuracy: chip / without the bound |
|---|---|---:|---|---:|
| ReLU | 19 / 113 / 12 | 141 (1.4 %) | 1.8-7.0 / 19 units (13 %) | 99.35 / 99.35 % |
| Leaky ReLU | 43 / 50 / 72 | 152 (1.5 %) | 2.3-7.0 / 21 units (14 %) | 99.35 / 99.35 % |
| SiLU | 84 / 353 / 172 | 508 (5.1 %) | 3.1-7.6 / 43 units (25 %) | 99.28 / 99.28 % |
| hard-swish | 50 / 159 / 20 | 209 (2.1 %) | 2.4-4.6 / 26 units (17 %) | 99.35 / 99.35 % |

* At most 0.0003 % of a layer's outputs saturate; one image in 20 (SiLU) to one in 70 (ReLU) has at least one.
* A saturated value is a real error: typically 2-8 units (2-5 % of the value), at worst 43 units (a value of about 170
  read as 127, 25 % low).
* It never changed a prediction: the accuracy with and without the upper bound is the same on all 10,000 images for all
  four models (the largest activations are already far above the rest, so clamping them does not change the decision).
* The pre-activation bound of SiLU / hard-swish (int8 index below -128) is reached by 2-69 values per layer, on the negative
  side where f is about 0: no effect.
* The accuracies of the current toolchain differ by at most 0.01 point from those of 2026-11-02
  (`2026-11-02_activation/eval_10000.md`, before the mantissa fix #38 and the one-channel Conv1 of #17): Leaky ReLU 99.35
  (99.34), SiLU 99.28 (99.27).

When it would matter: inputs unlike the calibration images (other data, brightness or contrast changes), a small or
unrepresentative calibration set, deeper networks with outlier activations. Remedies are in the toolchain only: calibrate
on more, representative images, or leave a margin above the calibrated maximum (a larger s_next: fewer saturations,
coarser steps). The hardware needs no change; a saturation counter in the profiler would make it visible on the chip.
