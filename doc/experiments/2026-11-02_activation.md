# 2026-11-02: activation functions, step A (toolchain and reference, Python only, no RTL)

Step A of `2026-11-02_activation_plan.md`: Leaky ReLU, SiLU and hard-swish (ReLU exists) in the toolchain's own
real-model path (`USE_RANDOM_VALUES=0`: PyTorch -> `onnx2model` -> `LayerParameters` -> `DRAMContents` -> testbench
reference), computed by the reference exactly as the planned hardware will; three trained MNIST variants; accuracy and
zero fractions on the 10,000 MNIST test images. The RTL is unchanged: a layer with the new activations is refused
before it is streamed to the RTL (`check_rtl_activation`).

## 1. What ONNX Runtime's static quantization makes of the activations

The toolchain exports with opset 18 and quantizes with `quantize_static` (QOperator, symmetric int8, zero point 0, one
weight scale per layer). After every `QLinearConv` (int8 output at scale s_c, the pre-activation):

| PyTorch | Nodes after the conv | Output scale of the activation |
|---|---|---|
| `F.relu` | `DequantizeLinear` -> `Relu` (float) -> `MaxPool` -> `QuantizeLinear` | = s_c (ratio 1.000 in all layers) |
| `nn.LeakyReLU(0.1)` | `QLinearLeakyRelu` (com.microsoft) | Y_scale |
| `nn.SiLU` | `QLinearSigmoid` + `QLinearMul(x, sigmoid(x))` | C_scale of the multiplication |
| `nn.Hardswish` | `DequantizeLinear` -> `HardSigmoid(1/6, 1/2)` (float) -> `QuantizeLinear` -> `QLinearMul(x, hard_sigmoid(x))` | C_scale (ONNX Runtime has no quantized HardSwish) |

* With ReLU the scale after the activation equals the conv's output scale, so one [mant, shift] does it. With the
  others it is 0.58 to 0.80 of it (untrained net; trained similar): **the activation also has to rescale** from s_c
  to the next layer's input scale.
* Between the last conv and the Dense, ONNX Runtime goes through a float `Flatten` with its own `QuantizeLinear`. The
  hardware writes the conv output straight into the Dense input, so the activation targets **the next compute
  layer's input scale**, folding that requantization in.
* ONNX shape inference does not know the com.microsoft ops, so every tensor after a quantized activation had no shape
  (`onnx2model` gave the next layers the shape "Unknown"; with ReLU the MaxPool runs in float and the shapes are known).

## 2. Changes

| File | Change |
|---|---|
| `models/mnist_conv_net.py` | `SimpleMNISTConvNet(activation="relu", negative_slope=0.1)`: relu (default: the original model, `F.relu`, same graph), leaky_relu, silu, hardswish; the state dict is the same for all |
| `models/train_mnist.py` (new) | trains a variant the way `doc/demo_notebooks/mnist_pytorch.ipynb` trained the original (Adam 0.001, batch 64, 5 epochs, StepLR(3, 0.7), dropout 0.5), seed 0, CPU; checkpoint `doc/demo_notebooks/mnist_<activation>_model.pth` (ignored by git like the original), with the activation in it; `load_activation_model()` |
| `src/open_eye/onnx2model.py` | `tensor_consumers`, `find_activation` (the patterns of section 1), `finish_activations` (hardware parameters against the next compute layer's input scale), `activation_table`, `fill_missing_shapes`; new `HardwareLayer` fields `activation`, `activation_alpha`, `activation_output_scale`, `activation_negative_factor`, `activation_table`, `activation_round` |
| `src/open_eye/layer_parameters.py` | `activation_config()`: `act_mode` "none" / "relu" / "leaky" / "table", `act_negative`, `act_table`, `act_round`; `check_rtl_activation()` |
| `src/open_eye/simple_layer_operations.py` | `batchnorm_output` (the testbench reference of the quantizer) computes the modes and the rounding option; the old path ("none" / "relu", floor) is unchanged line for line |
| `src/open_eye/conv_mapper.py`, `dense_mapper.py` | call `check_rtl_activation` before packing the status registers |
| `test/test_activation.py` (new) | 29 tests (section 5) |
| `doc/experiments/2026-11-02_activation/` | `eval_act.py` (10,000 images), `measure_ort.py` (difference to ONNX Runtime), `eval_10000.md` (result) |

The hardware arithmetic the reference now models (s = the quantizer's [mant, shift], v = the 20-bit psum):

* requantize(v) = (mant * v + r) >> shift, r = 0 (floor, today's quantizer) or 2^(shift-1) (round half up, the planned
  rounding bit; applies to every mode)
* none / relu: clamp(requantize(v), act_min, 127), act_min -128 or 0 (as today)
* leaky: clamp(requantize(v) with [mant, shift] if v >= 0, with the negative factor [mant_n, shift_n] if v < 0,
  -128, 127); [mant, shift] ~ s_in * s_w / s_next, [mant_n, shift_n] ~ alpha * s_in * s_w / s_next
* table: T[clamp(requantize(v), -128, 127) + 128]; [mant, shift] ~ s_in * s_w / s_c (int8 pre-activation),
  T[i] = clamp(round(f((i - 128) * s_c) / s_next), -128, 127) (round half away from zero)

## 3. Trained variants (float, PyTorch)

| Activation | Test accuracy after 5 epochs |
|---|---:|
| ReLU (original checkpoint `mnist_unquantized_model.pth`) | 99.35 % |
| Leaky ReLU, alpha 0.1 | 99.33 % |
| SiLU | 99.29 % |
| hard-swish | 99.36 % |

`venv/bin/python models/train_mnist.py --activation <name>`: about 15 minutes each on this machine (three in
parallel, 4 threads each).

## 4. The reference against ONNX Runtime (`measure_ort.py`, test images 0-3, per conv layer)

| Variant | Rounding | conv1: max / within 1 / mean | conv2 | conv3 (= Dense input) |
|---|---|---|---|---|
| Leaky ReLU | floor | 2 / 99.9 % / -0.58 | 6 / 96.7 % / -0.36 | 7 / 82.7 % / +0.00 |
| | round | 1 / 100 % / +0.04 | 2 / 99.4 % / -0.11 | 3 / 97.7 % / +0.10 |
| SiLU | floor | 3 / 97.9 % / -0.43 | 5 / 97.7 % / +0.11 | 7 / 86.5 % / -0.47 |
| | round | 2 / 99.9 % / -0.05 | 3 / 99.4 % / +0.11 | 4 / 94.5 % / -0.11 |
| hard-swish | floor | 3 / 99.2 % / -0.46 | 5 / 98.0 % / +0.06 | 5 / 90.4 % / -0.46 |
| | round | 3 / 99.9 % / +0.00 | 3 / 99.6 % / -0.05 | 3 / 97.9 % / +0.02 |

The floor of today's quantizer biases every layer by about -0.5 LSB and the difference grows with depth; rounding to
nearest, as ONNX Runtime does, keeps it within 1-4 (ONNX Runtime itself rounds twice for SiLU and hard-swish). The
class is the same as ONNX Runtime's and the label on every compared image.

## 5. Tests

`test/test_activation.py`, 29 tests, all pass:

* reference against the integer formulas: two slopes (floor and round), table (floor and round), Dense with filter
  0's parameters (bug #12), rounding for ReLU, the old ReLU path unchanged;
* `activation_table` against the float functions (within 0.5 LSB, entry 0 = 0);
* `activation_config` and `check_rtl_activation` (refuses leaky, table and rounding until step B);
* `onnx2model` on untrained (seeded) variants: the activation of every conv, `has_relu` only for ReLU, the output
  scale = the next compute layer's input scale, the factors and tables as computed from the scales;
* `LayerParameters` take the modes (`act_min` -128 for the new ones);
* the trained variants (skipped without the checkpoints): every conv layer against ONNX Runtime, floor and round,
  within the tolerances of section 4, the class = ONNX Runtime's = the label (test images 0 and 1).

Regression: Python unit tests 319 pass (290 + 29), the 11 old fails of `test_dense_output.py`;
`test_onnx_model_flow.py` 6/6; on the RTL with the changed toolchain `test_real_model.py` 2/2 (the trained ReLU
model, bit-exact) and `test_int8_clamp.py` 9/9.

## 6. Accuracy and zeros on the 10,000 test images (`eval_act.py`, `2026-11-02_activation/eval_10000.md`)

"hardware int8" is the planned hardware's arithmetic (the numpy model is checked equal to the testbench reference on
two images for every variant and rounding). Zeros = fraction of exact zeros in the layer's input (what zero skipping
skips). Predicted compute = conv1 + conv2 + conv3 + Dense compute cycles, linear in each layer's input zero fraction
between the two points measured on the RTL (random data and the trained ReLU model, `doc/perf/trained_mnist_2026-10-31.md`):
a rough estimate, to be measured in step D.

| Activation | Option | Float | ONNX Runtime int8 | Hardware int8 | Zeros: conv2 in | conv3 in | Dense in | Predicted compute vs ReLU |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ReLU | floor (today) | 99.35 % | 99.33 % | **99.35 %** | 44 % | 83 % | 78 % | 0 |
| ReLU | round | | | 99.36 % | 39 % | 83 % | 76 % | +1,070 (+0.5 %) |
| Leaky ReLU | floor | 99.33 % | 99.34 % | 99.34 % | **1 %** | 2 % | 3 % | +23,080 (+10.5 %) |
| Leaky ReLU | round | | | **99.34 %** | 23 % | 15 % | 17 % | +16,195 (+7.4 %) |
| SiLU | floor | 99.29 % | 99.29 % | 99.25 % | 9 % | 6 % | 6 % | +20,597 (+9.4 %) |
| SiLU | round | | | 99.27 % | 10 % | 7 % | 7 % | +20,304 (+9.2 %) |
| SiLU | round + band1 | | | **99.30 %** | 21 % | 21 % | 20 % | +15,401 (+7.0 %) |
| SiLU | round + neg0 | | | 98.73 % | 42 % | 80 % | 82 % | +879 (+0.4 %) |
| hard-swish | floor | 99.36 % | 99.29 % | 99.33 % | 6 % | 13 % | 13 % | +20,036 (+9.1 %) |
| hard-swish | round | | | **99.35 %** | 7 % | 14 % | 13 % | +19,817 (+9.0 %) |
| hard-swish | round + band1 | | | 99.32 % | 19 % | 27 % | 24 % | +14,910 (+6.8 %) |
| hard-swish | round + neg0 | | | 98.45 % | 38 % | 78 % | 81 % | +1,942 (+0.9 %) |

(band1: table outputs -1 and +1 set to 0; neg0: every negative table output set to 0. Percentages of the trained
ReLU model's 219,598 cycles.)

## 7. Conclusions for step B

1. **Accuracy is not the problem.** The planned integer arithmetic keeps every activation within 0.04 points of its
   float model (99.25-99.36 %); the table and the two slopes are exact enough at int8.
2. **The cost of the new activations is the lost zeros, not the activation unit.** The unit itself adds 0 cycles per
   value (plan, design A) and about 100 table-load cycles per network; but ReLU leaves 44-83 % zeros in the next
   layers' inputs and the others 1-23 %, so zero skipping saves much less: an estimated +7 to +10.5 % compute cycles
   for this model. This is a property of the model (its activation), measurable in step D.
3. **The rounding bit is needed** (and should be per layer): with the floor, Leaky ReLU turns every small negative
   value into -1 and keeps 1-3 % zeros (+10.5 %); rounded to nearest it keeps 15-23 % (+7.4 %) with the same
   accuracy, and every variant gets 2-3 times closer to ONNX Runtime. For ReLU rounding gives nothing (99.36 vs
   99.35 %) and costs 0.5 % (values between 0.5 and 1 LSB no longer become 0), so the ReLU default stays floor.
4. **The table is a latency knob.** Setting the table's +-1 outputs to 0 (band1) raises the zeros of SiLU and
   hard-swish to about 20-27 % at no accuracy cost (99.30 / 99.32 %), worth about 2 % of the model's cycles. Zeroing
   the whole negative part (neg0) brings back ReLU-like sparsity but costs 0.6-0.9 points: not as a default, only if
   a model tolerates it. The toolchain can choose per layer; the hardware does not change.
5. **Two slopes for Leaky ReLU** work as planned (no table, no extra DMA words), and the activation rescales to the
   next layer's input scale in the same multiplication.
