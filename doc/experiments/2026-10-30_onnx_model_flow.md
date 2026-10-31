# 2026-10-30: the toolchain's real-model path (PyTorch -> onnx2model -> RTL), made to carry a trained model (Python only)

Approved by the user: Python fixes 1-5 inside the existing toolchain (no parallel path), a run of a real model, and an
investigation of the RTL failure of this path after the first pooling (no RTL change).

## 1. The path

`test/cocotb_fpga/OpenEye_FPGA_tb.py` with `USE_RANDOM_VALUES=0` (the Makefile and the runners set it to 1, which uses
`data_create`'s random Keras models): `models/mnist_conv_net.SimpleMNISTConvNet` (PyTorch) -> `onnx2model.get_model`
(ONNX export, int8 quantization, one `HardwareLayer` per Conv / MaxPool / Dense) -> `LayerParameters` (mapping, loops,
registers) -> `DRAMContents` (weights, biases, input) -> mappers (DMA streams) -> RTL (convolution, Dense, max pooling,
requantization with the fused ReLU, write-back). Before this change the path carried the model's structure only:

| Stage | Before |
|---|---|
| model | `SimpleMNISTConvNet()` untrained; the trained checkpoint `doc/demo_notebooks/mnist_unquantized_model.pth` (99.35 %) matches the architecture but was not loaded |
| `onnx2model` | `quantize_dynamic`: weights only, activations stay float, so no activation scale and no requantization multiplier; every layer named by its type (`pooling2d`) |
| `LayerParameters` | `quantize` default [1, 7] / [1, 9]; `has_relu` not read (`activation_min` knew `relu` and Keras `activation`); MaxPool configured as **average** pooling (below) |
| `DRAMContents` | int8 weights multiplied by 127 again (int8 overflow), conv bias 1, Dense bias c + 1, Dense weights and input random |

`has_relu` upstream: set by `onnx2model` and printed in its summary, read nowhere; upstream has no ReLU on the
requantization path at all (no `act_min`, no `quant_clamp_low`; `af_cluster.v` unused). In `dev`, `activation_min` (bug
#30) missed the attribute name of `onnx2model`. Not a consequence of the RTL clamp: the clamp needs `act_min = 0` from
Python to apply the ReLU.

## 2. Bug #34 (found and fixed here, Python): MaxPool of onnx2model configured as average pooling

The RTL run of this path failed at the iact buffer after the first pooling (784 of 784 words, DUT 0 / -128, reference
small values). Diffing the LayerParameters of the same architecture built from `data_create`'s MNIST_REAL (passes on
RTL) and from `onnx2model`: the pooling layers differ in `pooling_mode` (0 = max vs **1 = average**) and
`iact_converter_buffer_addr_max_cycles` (112 vs 8 / 16); otherwise only the batch name and `kernel_shape` differ.
`LayerParameters.write_pooling_layer` decides max vs average with `"max" in layer.name`; Keras names the layer
`max_pooling2d`, `onnx2model.get_model` renamed every layer to its type (`pooling2d`). Upstream has the same code.
Confirmed on RTL with a probe that only renames the pooling layers to `max_pooling2d`: the checks after pool1 (784
words) and pool2 (392 words) pass. The test-data run then still differed in 4 of 392 words before the Dense layer, at
the saturation bounds (0x80 vs 0x7f): with weights multiplied by 127 the conv3 psums can leave the 20-bit psum (the RTL
wraps, the reference does not); not checked further, the quantized path no longer multiplies.

## 3. Changes (Python, existing files)

| File | Change |
|---|---|
| `src/open_eye/onnx2model.py` | `get_model(torch_model, calibration_data=None)`: with calibration data `quantize_to_int8_static` (ONNX Runtime `quantize_static`, QOperator, int8 activations and weights with zero point 0 (`ActivationSymmetric`, `WeightSymmetric`), one weight scale per layer); without it the old dynamic quantization. `process_qlinear` reads `QLinearConv` / `QGemm` (new: the Linear layer becomes `com.microsoft.QGemm`): int8 weights (conv `[row][column][channel][filter]`, the order `DRAMContents` reads for a Keras kernel; dense `[out][in]`), int32 bias, input / weight / output scales, `quantization_factor = [mant, shift]` per filter with `hardware_multiplier` (largest shift with an 8-bit mantissa), `quantized = True`; refuses zero points or per-channel scales. `quantize_input`. Pooling layers named `max_pooling2d` / `average_pooling2d` (bug #34). `check_fused_relu` stops at the next compute node (a static graph has DequantizeLinear before the Relu, and the next layer's Relu was within reach). The output shape of `QGemm` (no ONNX shape inference) comes from the weights |
| `src/open_eye/layer_parameters.py` | `activation_min` also reads `has_relu` |
| `src/open_eye/DRAM.py` | for layers with `quantized`: conv weights and biases as they are (no x127, no bias 1); Dense weights and bias from the model, the weight columns permuted to the hardware's Dense input order (`dense_input_order`: from `test_utils_main.fill_dram_with_ref`, the order of the reference and of the RTL write-back, vs the model's NCHW flatten). The random path is unchanged |
| `src/open_eye/data_create.py` | `mnist_images(split, indices)`: MNIST preprocessed as in training (`(pixel/255 - 0.1307)/0.3081`, `mnist_pytorch.ipynb`) |
| `test/cocotb_fpga/OpenEye_FPGA_tb.py` | model path: `OPENEYE_MODEL_WEIGHTS=<.pth>` loads the checkpoint and quantizes statically (calibration `OPENEYE_CALIBRATION_IMAGES`, default 200 training images); `OPENEYE_INPUT_IMAGE=<i>` sets the layer-0 input to test image i quantized with the model's input scale; logs the DUT's class |
| `test/test_onnx_model_flow.py` (new) | 6 tests without RTL (section 4) |
| `test/cocotb_fpga/test_real_model.py` (new) | the real model on RTL, images 0 and 1 (section 5) |

The quantized model: activations int8 with zero point 0; input scale 0.0222 (the normalised background is -0.42, i.e.
-19, so the input has no zeros); quantizer settings conv1 216/16, conv2 190/17, conv3 211/17, fc 130/17; `act_min` 0 on
the three convolutions; biases well inside the 20-bit psum (checked by the test); largest psum on image 0
130,393 (20-bit psum enough). ONNX Runtime with the static
int8 model: 99.15 % on the first 2,000 test images (float 99.20 %).

## 4. The toolchain checked against ONNX Runtime (no RTL)

The testbench's reference (`collect_results`, `fill_dram_with_ref`, `batchnorm_output`) of the model built as above,
against the int8 tensors of ONNX Runtime running the same quantized model:

| Layer (test images 0-3) | exact | within 1 | largest difference |
|---|---:|---:|---:|
| conv1 (ReLU) | 70-73 % | 100 % | 1 |
| pool1 | 65-66 % | 100 % | 1 |
| conv2 (ReLU) | 96-99 % | 99.9 % | 2 |
| pool2 | 92-97 % | 99.7-99.9 % | 2 |
| conv3 (ReLU, in the Dense input order) | 83-84 % | 98.2-99.8 % | 3 |
| Dense | class = ONNX Runtime = label on all four | | logits within 1.1 |

The differences are rounding: the hardware floors `mant * psum >> shift` with an 8-bit mantissa, ONNX Runtime rounds a
float multiplier to nearest. A wrong kernel orientation or flatten order would differ everywhere. Over the first 100 test images the
reference gives the right class for all 100, and the same class as ONNX Runtime int8 for all 100.

`test/test_onnx_model_flow.py`: 6/6 (15 s): the multiplier, `has_relu`, LayerParameters (`quantize` from the scales,
`act_min`, max pooling), DRAM holds the model's data (no x127, the int32 biases, the permuted Dense weights), and the
reference vs ONNX Runtime per layer for images 0 and 1 (conv1 / pool1 within 1, deeper within 3 with >= 97 % within 1,
same class as ONNX Runtime and the label, psums below 2^19).

## 5. The real model on RTL

`test/cocotb_fpga/test_real_model.py` (MNIST_REAL platform, QUANT_AMOUNT 64, input padded to 2 channels for bug #17):

| Buffer check (images 0 and 1) | Result |
|---|---|
| after conv1 + ReLU + pool1 (conv2's input, 784 words) | **bit-exact** |
| after conv2 + ReLU + pool2 (conv3's input, 392 words) | **bit-exact** |
| after conv3 (the Dense input, 392 words) | wrong: 112 (image 0) and 138 (image 1) of 392 words right |

**Correction (same day, `2026-10-30_bug32_bias_order.md`):** the "bug #35" below is bug #31: the 3 words are at conv3's
last output line (y = 6), not the last column (the pixel index was read as 7x + y); in that line's window the channel chunk
44..47 is all zero, an empty pass, and every later pass of conv3 is lost. "Bug #31 did not trigger" is wrong for image 0.
Image 0 = #32 everywhere + #31 at y = 6, image 1 = #32 only (the model matches the DUT at 3,136 of 3,136 values for both).

The conv3 outputs, recomputed with the biases of the filter pairs (2k, 2k+1) swapped (bug #32), match the DUT in 13 of
the 16 logged wrong words (the plain reference matches none of them and all 16 logged reference values). The other 3
are the last column (x = 6) of the 7-wide rows (pixels 6, 13, 20, ..., 41), smaller in the DUT: **bug #35**, new, not
investigated (conv3 alone with random data had every value right, so it shows when conv3 writes back; possibly the
bug #9 family of 7-wide rows). Bug #31 did not trigger: the input has no zeros and no pass of conv2 / conv3 was
empty for these images. Both RTL tests are xfail(strict) on #32 / #35 (rerun after writing the test: 2 xfailed, about 9 minutes each,
the same counts).

Regression after the change: unit tests 268 pass (262 + 6), 11 pre-existing failures; RTL sample 22/22 (`test_int8_clamp`
9, `test_glb_psum2` 7, `test_dense_chain` 4, trained conv1 / conv2 of `test_mnist_layers`): the random-data path is unchanged.

## 6. Next

Bug #32 and #35 (= #31, see the correction in section 5) block the Dense layer of this model on RTL (the Dense is 3136 -> 10, so bug #29 does not apply);
bug #31 can still hit other inputs and models. Fix A for #31 and investigations of #32 / #35 need the user's approval.

## 7. The old path: dynamic quantization (2026-10-31, analysis, no change)

`onnx2model` before f4a11ef is identical to `upstream/main` (no diff): `quantize_dynamic(weight_type=QuantType.QInt8)`.
Run on the trained model with the old module (`git show f4a11ef^:src/open_eye/onnx2model.py`):

* Graph per layer: `DynamicQuantizeLinear` (the activation, **uint8**, scale and zero point computed **at run time** from
  the min / max of that tensor) -> `ConvInteger` / `MatMulInteger` (int32) -> `Cast` -> `Mul` (activation scale x weight
  scale) -> `Add` (float bias) -> `Relu` (float) -> `MaxPool` (float) -> the next `DynamicQuantizeLinear`. Weights int8,
  zero point 0, one scale per tensor. The activation scale is not in the file: it changes with every image (layer 2:
  0.01055, 0.01125, 0.0087 for test images 0, 1, 2), the input layer has zero point 33.
* The hardware has one fixed multiplier (`mant`, `shift`) per layer, programmed before the layer, signed int8 activations
  with zero point 0 (zero skipping and zero padding rely on it), and quantizes every output as it is written back, without
  a pass over the whole tensor to find its range. A run-time scale cannot be mapped; a calibrated (static) one can. Hence
  static quantization (section 3).
* ONNX Runtime itself is right: dynamic with uint8 weights 99.5 % on the first 1,000 test images, float 99.5 %, static int8
  (the new path) 99.4 %, the toolchain reference of the hardware 99.5 % (`scan31.py`). But the model the old path wrote
  (int8 weights) **cannot be run by ONNX Runtime** ("Could not find an implementation for ConvInteger(10)": the CPU
  ConvInteger takes uint8 weights), so it was never checked.
* ReLU: the old `check_fused_relu` found it (`has_relu` True on the three convs: `Relu` four nodes after `ConvInteger`), but
  nothing read the flag (upstream neither), the reference had no ReLU and the RTL quantizer wrapped instead of clamping
  until bug #30. In the dynamic graph the ReLU is a float operation of ONNX Runtime, not part of the quantization.
* What the old extraction did wrong, besides the dynamic scheme:

| | Old (= upstream) | Effect |
|---|---|---|
| activation scale | `inits.get('input_scale', 1.0)`: a run-time tensor, not an initializer, so always 1.0 | `bias_int32 = bias / w_scale` in the wrong unit (should be `/ (s_in * s_w)`); no requantization multiplier, `quantize` stays at its default [1, 7] / [1, 9] |
| conv kernel | `transpose(3, 2, 1, 0)` = [column][row][c][f] where `DRAMContents` reads [row][column][c][f] | kernel rows and columns swapped: conv1 vs ONNX Runtime 65.8 % within 1, largest difference 199 (the new `transpose(2, 3, 1, 0)`: 100 %, 0) |
| Dense | `MatMulInteger` weights are [in][out] (3136 x 10), read as [out][in] | `filters` = 3136 instead of 10 |
| MaxPool | named `pooling2d` | configured as average pooling (bug #34) |
| ReLU | `has_relu` found, read nowhere | no ReLU (bug #30 for the clamp) |
| "stable hardware reference generator" | runs the float model on a one-pixel image and divides an activation by conv2's weight scale | result unused (dead code) |
| `DRAMContents` (not onnx2model) | conv weights x127 (int8 overflow), bias 1 / c + 1, Dense weights random | the model's data never reached the hardware |
