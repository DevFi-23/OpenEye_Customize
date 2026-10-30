# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Post-training quantization (PTQ) of a trained int8 TFLite model for the OpenEye datapath.

DRAMContents fills a model with test data (conv weights floor(127*w) without a scale, random Dense
weights, bias 1 or c+1, random inputs, quantize [1, 7] / [1, 9]). This module produces the numbers a
trained model needs instead, in the arithmetic the hardware has today (doc/experiments/2026-10-30_ptq.md):

  activations  int8 with zero point 0 (symmetric): the image pixel p (0..255) becomes round(p*127/255),
               scale 1/127 on the [0, 1] image the model was trained on. Zero stays a raw 0, so the PE
               zero skipping keeps working, and the conv padding (raw 0) is the real zero.
  weights      int8 [-127, 127] with one scale per layer (per tensor). Every filter then has the same
               multiplier M, which the quantizer needs: it uses filter 0's multiplier for all (bug #12).
  bias         round(b / (s_in * s_w)) in psum units, loaded into the psum (DATA_PSUM_BITWIDTH bits).
  quantizer    q = clamp(floor(mant * psum / 2^shift), act_min, 127) with mant / 2^shift ~ M =
               s_in * s_w / s_out, mant < 2^MANT_BITS (OpenEye_FPGA.v reads 8 bits of the mantissa
               field), offset 0, act_min = 0 after a ReLU (the fused ReLU of bug #30) and -128 otherwise.
  max pooling  no parameters (it commutes with the monotonic quantizer, the scale is unchanged).
  last layer   raw psums to the host (PSUM_SEND_RESULTS); the class is argmax(psum * s_w).

The model is read from the int8 TFLite file: its weights are already int8 (symmetric, one scale per
output channel) and its activation scales come from TFLite's calibration. Only the activations change,
from TFLite's zero point -128 to zero point 0, and the weights from per-channel to per-tensor scales.
The trained MNIST model (doc/demo_notebooks/mnist_quantized_model.tflite, TFLite 99.23 %) reaches
99.22 % on the 10,000 test images this way.

forward() computes the model exactly as the hardware does and is the reference for the testbench:
TestbenchModel fills the DRAM and the layer parameters of a testbench model (OPENEYE_PTQ in
OpenEye_FPGA_tb.py) and checks the testbench reference of every layer against it.
"""

import math
import os

import numpy as np

MANT_BITS = 8           # the RTL multiplies by 8 bits of the 25-bit mantissa field (OpenEye_FPGA.v:1350)
SHIFT_MAX = 127         # 7-bit shift field
PSUM_BITS = 20          # DATA_PSUM_BITWIDTH of the cocotb_fpga platform
INPUT_LEVELS = 127      # the image [0, 1] maps to 0..127
MNIST_CACHE = os.path.expanduser("~/.keras/datasets/mnist.npz")    # tf.keras.datasets.mnist.load_data()


def mant_shift(m, mant_bits=MANT_BITS, shift_max=SHIFT_MAX):
    """Multiplier m as mant / 2^shift with the largest shift for which mant still fits mant_bits bits."""
    if not m > 0:
        raise ValueError("multiplier %r is not positive" % (m,))
    shift = 0
    while shift < shift_max and round(m * 2 ** (shift + 1)) < (1 << mant_bits):
        shift += 1
    mant = int(round(m * 2 ** shift))
    if mant >= (1 << mant_bits) or mant == 0:
        raise ValueError("multiplier %g does not fit %d mantissa bits and shift <= %d" % (m, mant_bits, shift_max))
    return mant, shift


def symmetric_scale(scale, zero_point):
    """Scale of the same real range with zero point 0: the larger side of [-128, 127] - zero_point."""
    return scale * max(abs(-128 - zero_point), abs(127 - zero_point)) / 127.0


def read_tflite(path):
    """CONV_2D, MAX_POOL_2D and FULLY_CONNECTED of an int8 TFLite model, with their quantization.

    Conv weights stay [filter][kernel row][kernel column][channel] (OHWI), Dense weights [out][in] with
    the input in TFLite's flatten order (NHWC). relu: the fused ReLU, seen in the output tensor's name.
    """
    import tensorflow as tf
    interpreter = tf.lite.Interpreter(model_path=str(path))
    interpreter.allocate_tensors()
    tensors = {t["index"]: t for t in interpreter.get_tensor_details()}
    layers = []
    for op in interpreter._get_ops_details():
        kind = {"CONV_2D": "conv", "MAX_POOL_2D": "pool", "FULLY_CONNECTED": "dense"}.get(op["op_name"])
        if kind is None:
            continue
        x, y = tensors[op["inputs"][0]], tensors[op["outputs"][0]]
        layer = {"kind": kind, "in_shape": tuple(int(v) for v in x["shape"][1:]),
                 "out_shape": tuple(int(v) for v in y["shape"][1:]),
                 "s_in": float(x["quantization"][0]), "zp_in": int(x["quantization"][1]),
                 "s_out": float(y["quantization"][0]), "zp_out": int(y["quantization"][1])}
        if kind != "pool":
            w, b = tensors[op["inputs"][1]], tensors[op["inputs"][2]]
            if w["dtype"] != np.int8 or b["dtype"] != np.int32:
                raise ValueError("%s: not an int8 model (weights %s, bias %s)" % (path, w["dtype"], b["dtype"]))
            zp_w = w["quantization_parameters"]["zero_points"]
            if np.any(zp_w != 0):
                raise ValueError("%s: weights with a zero point are not supported" % (path,))
            layer.update(w=interpreter.get_tensor(w["index"]).astype(np.int64),
                         b=interpreter.get_tensor(b["index"]).astype(np.int64),
                         s_w=w["quantization_parameters"]["scales"].astype(np.float64),
                         relu="Relu" in y["name"])
        layers.append(layer)
    return layers


class QuantLayer:
    """One layer as the hardware computes it.

    kind: "conv", "pool" or "dense". w: int weights (conv OHWI, dense [out][in] in NHWC flatten order),
    b: bias in psum units, mant / shift: quantizer per output filter, act_min: lower clamp bound,
    s_in / s_w / s_out: the real scales (s_w per output filter), in_shape / out_shape without the batch.
    """

    def __init__(self, kind, in_shape, out_shape, s_in, s_out, w=None, b=None, s_w=None, mant=None,
                 shift=None, act_min=-128, relu=False):
        self.kind, self.in_shape, self.out_shape = kind, in_shape, out_shape
        self.s_in, self.s_out, self.w, self.b, self.s_w = s_in, s_out, w, b, s_w
        self.mant, self.shift, self.act_min, self.relu = mant, shift, act_min, relu


def quantize_tflite(path, per_channel=False, mant_bits=MANT_BITS):
    """The layers of an int8 TFLite model for the hardware (symmetric activations, see the module text).

    per_channel=False: one weight scale per layer, the only exact choice while bug #12 makes every filter
    use filter 0's multiplier. per_channel=True keeps TFLite's per-channel weights and gives every filter
    its own mant / shift (for the emulation; the hardware needs bug #12 fixed for it).
    """
    layers = []
    s_in = 1.0 / INPUT_LEVELS
    for t in read_tflite(path):
        if t["kind"] == "pool":
            layers.append(QuantLayer("pool", t["in_shape"], t["out_shape"], s_in, s_in))
            continue
        s_out = symmetric_scale(t["s_out"], t["zp_out"])
        s_c = t["s_w"]
        w_real = t["w"] * s_c.reshape((-1,) + (1,) * (t["w"].ndim - 1))
        b_real = t["b"] * t["s_in"] * s_c                      # TFLite: bias scale = input scale * weight scale
        if per_channel:
            s_w, w = s_c, t["w"]
        else:
            s_w = np.full_like(s_c, np.abs(w_real).max() / 127.0)
            w = np.rint(w_real / s_w[0]).astype(np.int64)
        b = np.rint(b_real / (s_in * s_w)).astype(np.int64)
        ms = [mant_shift(m, mant_bits) for m in s_in * s_w / s_out]
        layers.append(QuantLayer(t["kind"], t["in_shape"], t["out_shape"], s_in, s_out, w=w, b=b, s_w=s_w,
                                 mant=np.array([m for m, _ in ms], np.int64),
                                 shift=np.array([s for _, s in ms], np.int64),
                                 act_min=0 if t["relu"] else -128, relu=t["relu"]))
        s_in = s_out
    check_parameters(layers, mant_bits)
    return layers


def check_parameters(layers, mant_bits=MANT_BITS, psum_bits=PSUM_BITS):
    """The parameters fit their fields: weights int8, bias in the psum, mant / shift in the quantizer."""
    for n, layer in enumerate(layers):
        if layer.kind == "pool":
            continue
        if np.abs(layer.w).max() > 127:
            raise ValueError("layer %d: weight outside int8" % n)
        if np.abs(layer.b).max() >= 1 << (psum_bits - 1):
            raise ValueError("layer %d: bias %d outside %d bits" % (n, np.abs(layer.b).max(), psum_bits))
        if layer.mant.max() >= 1 << mant_bits or layer.shift.max() > SHIFT_MAX:
            raise ValueError("layer %d: mant / shift outside their fields" % n)


def quantize_image(images):
    """uint8 images [N, H, W] or [N, H, W, C] (pixel 0..255) -> int8 activations [N, H, W, C] (0..127)."""
    x = np.asarray(images, dtype=np.float64)
    if x.ndim == 3:
        x = x[..., None]
    return np.rint(x * INPUT_LEVELS / 255.0).astype(np.int64)


def _conv3x3(x, w):
    """'same' 3x3 stride-1 convolution with padding 0: x [N,H,W,C], w [F,3,3,C] -> [N,H,W,F] (exact int64)."""
    n, h, wd, c = x.shape
    p = np.zeros((n, h + 2, wd + 2, c), dtype=np.float64)
    p[:, 1:-1, 1:-1, :] = x
    cols = np.concatenate([p[:, i:i + h, j:j + wd, :] for i in range(3) for j in range(3)], axis=-1)
    acc = cols.reshape(n * h * wd, 9 * c) @ w.reshape(w.shape[0], -1).T.astype(np.float64)
    return np.rint(acc).astype(np.int64).reshape(n, h, wd, -1)       # integers far below 2^53: exact


def requantize(psum, layer):
    """The quantizer: clamp(floor(mant * psum / 2^shift), act_min, 127), mant / shift per output filter."""
    return np.clip((psum * layer.mant) >> layer.shift, layer.act_min, 127)


def forward(layers, x):
    """Run int8 activations x [N,H,W,C] through the layers as the hardware does.

    Returns one dict per layer: "psum" (conv / dense: bias + products, the testbench reference) and
    "out" (the layer's output: requantized, the pooled values, or the raw psums of the last layer).
    """
    results = []
    for n, layer in enumerate(layers):
        last = n == len(layers) - 1
        if layer.kind == "pool":
            h, wd = x.shape[1] // 2, x.shape[2] // 2
            x = x[:, :2 * h, :2 * wd, :].reshape(x.shape[0], h, 2, wd, 2, x.shape[3]).max(axis=(2, 4))
            results.append({"out": x})
            continue
        if layer.kind == "conv":
            psum = _conv3x3(x, layer.w) + layer.b
        else:
            flat = x.reshape(x.shape[0], -1).astype(np.float64)
            psum = np.rint(flat @ layer.w.T.astype(np.float64)).astype(np.int64) + layer.b
        x = psum if last else requantize(psum, layer)
        results.append({"psum": psum, "out": x})
    return results


def predict(layers, x):
    """Class of each input: argmax of the last layer's psums times their weight scale (the host's part)."""
    return np.argmax(forward(layers, x)[-1]["psum"] * layers[-1].s_w, axis=-1)


def max_psum(layers, x):
    """Largest |psum| of each conv / dense layer for the inputs x (must stay below 2^(PSUM_BITS-1))."""
    return [int(np.abs(r["psum"]).max()) if "psum" in r else 0 for r in forward(layers, x)]


def load_mnist_test():
    """MNIST test images (uint8 [10000, 28, 28]) and labels."""
    if os.path.exists(MNIST_CACHE):
        with np.load(MNIST_CACHE) as d:
            return d["x_test"], d["y_test"]
    import tensorflow as tf
    (_, _), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
    return x_test, y_test


def dense_input_order(prev_params, dense_params, rows, cols, channels):
    """Position in the hardware's Dense input of every NHWC flatten index.

    The Dense input after a Conv or Pooling layer is not NHWC: the hardware writes it in blocks of
    4 channels (test_utils_main.fill_dram_with_ref, the layout the RTL write-back produces). The order
    comes from that same function, fed with the NHWC index of every value.
    """
    from open_eye import test_utils_main as tum
    index = [[[(r * cols + c) * channels + f for c in range(cols)] for r in range(rows)] for f in range(channels)]
    order = tum.fill_dram_with_ref(index, [None] * (rows * cols * channels), prev_params, dense_params)
    if sorted(order) != list(range(rows * cols * channels)):
        raise ValueError("the hardware flatten order is not a permutation")
    return order


class TestbenchModel:
    """A quantized model on one image, for the FPGA testbench (OPENEYE_PTQ).

    fill() puts the weights, biases, input and quantizer settings into the testbench's DRAMContents and
    LayerParameters in place of its test data; check() compares the testbench reference of a layer
    (test_utils_main.collect_results) with forward(). The testbench layers map in order onto count
    quantized layers from layer first on; the input of a later first layer is the model's activation
    there (forward() of the layers before). A last Dense layer with fewer outputs takes the first ones
    (a probe of a layer the hardware cannot run whole, e.g. the 3136 -> 64 Dense of bug #29).
    """

    def __init__(self, layers, image, first=0, count=None):
        count = len(layers) - first if count is None else count
        image = quantize_image(np.asarray(image)[None])
        results = forward(layers[:first + count], image)
        self.layers = layers[first:first + count]
        self.results = results[first:first + count]
        self.input = image if first == 0 else results[first - 1]["out"]
        self.first = first

    def _check_mapping(self, layer_parameters):
        if len(layer_parameters) != len(self.layers):
            raise ValueError("testbench model has %d layers, the quantized model %d"
                             % (len(layer_parameters), len(self.layers)))
        for n, (params, layer) in enumerate(zip(layer_parameters, self.layers)):
            name = str(params.layer_name)
            kind = "conv" if "Conv" in name else "pool" if "Pooling" in name else "dense" if "Dense" in name else name
            if kind != layer.kind:
                raise ValueError("layer %d: testbench %s, quantized model %s" % (n, name, layer.kind))
            if kind != "pool" and params.filters > len(layer.b):
                raise ValueError("layer %d: %d outputs, the quantized layer has %d" % (n, params.filters, len(layer.b)))
            if kind != "pool" and params.filters < len(layer.b) and n != len(self.layers) - 1:
                raise ValueError("layer %d: only the last layer may be cut to fewer outputs" % n)

    def fill(self, dram, layer_parameters):
        """Weights, biases, layer-0 input and quantizer settings of every layer (padding channels stay)."""
        self._check_mapping(layer_parameters)
        for n, (params, layer) in enumerate(zip(layer_parameters, self.layers)):
            if layer.kind == "pool":
                continue
            outputs = params.filters
            if len(set(layer.mant[:outputs])) != 1 or len(set(layer.shift[:outputs])) != 1:
                raise ValueError("layer %d: per-filter multipliers need bug #12 fixed; quantize per tensor" % n)
            for f in range(len(params.quantize)):
                params.quantize[f] = [int(layer.mant[0]), int(layer.shift[0])]
                params.offset[f] = 0
            params.act_min = layer.act_min
            dram.bias[n] = [int(v) for v in layer.b[:outputs]]
            if layer.kind == "conv":
                # DRAM weights[c][f][column][row] = kernel[row][column] (DRAMContents.load_conv_weights_tflite)
                for c in range(layer.w.shape[3]):
                    for f in range(outputs):
                        dram.weights[n][c][f] = [[int(layer.w[f, row, col, c]) for row in range(layer.w.shape[1])]
                                                 for col in range(layer.w.shape[2])]
            else:
                w = layer.w[:outputs]
                if n > 0 and self.layers[n - 1].kind != "dense":
                    rows, cols, channels = self.layers[n - 1].out_shape
                    order = dense_input_order(layer_parameters[n - 1], params, rows, cols, channels)
                    w = w[:, order]
                dram.weights[n] = [[int(v) for v in row] for row in w]
        x = self.input[0]
        if self.layers[0].kind == "dense":
            # A Dense layer fed by the DMA takes its input as sent: TFLite's flatten order, like its weights.
            dram.fmap[0] = [int(v) for v in x.reshape(-1)]
        else:
            for c in range(x.shape[2]):
                dram.fmap[0][c] = [[int(x[row, col, c]) for col in range(x.shape[1])] for row in range(x.shape[0])]

    def expected(self, n, outputs=None):
        """The testbench reference of layer n as forward() computes it, in the testbench's layout."""
        r, layer = self.results[n], self.layers[n]
        if layer.kind == "dense":
            return [int(v) for v in r["psum"][0][:outputs]]
        values = r["out"] if layer.kind == "pool" else r["psum"]
        return np.transpose(values[0], (2, 0, 1)).tolist()             # [filter][row][column]

    def check(self, n, layer_params, calculated_results):
        """Number of values where the testbench reference of layer n differs from forward()."""
        if self.layers[n].kind == "dense":
            got = [int(calculated_results[f]) for f in range(layer_params.filters)]
            want = self.expected(n, layer_params.filters)
        else:
            if hasattr(calculated_results, "keys"):                     # conv: {filter: [row][column]}
                calculated_results = [calculated_results[f] for f in range(len(calculated_results))]
            got = np.asarray(calculated_results, dtype=np.int64)
            want = np.asarray(self.expected(n), dtype=np.int64)
            if got.shape != want.shape:
                raise ValueError("layer %d: reference shape %s, int8 model %s" % (n, got.shape, want.shape))
        return int(np.sum(np.asarray(got) != np.asarray(want)))
