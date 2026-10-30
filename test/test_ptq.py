# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Post-training quantization of the trained MNIST int8 model for the hardware (open_eye.ptq).

1. The parameters fit their fields (int8 weights, bias in the 20-bit psum, 8-bit mantissa, one multiplier
   per layer for bug #12) and the quantized model keeps TFLite's accuracy (forward() is the hardware's
   arithmetic: floor, saturation with the ReLU bound, raw psums of the last layer).
2. The testbench path: the model of the RTL test (MNIST_REAL_RELU, Dense 3136 -> 10 as a probe of the
   trained 3136 -> 64 layer) gets its DRAM and layer parameters from TestbenchModel.fill, and the
   testbench reference (collect_results, fill_dram_with_ref, batchnorm_output) equals forward() on every
   layer. Without the flatten permutation of the first Dense layer it does not.

Needs the trained model (doc/demo_notebooks/mnist_quantized_model.tflite) and the MNIST test set
(~/.keras/datasets/mnist.npz, downloaded by tf.keras.datasets.mnist.load_data()).
"""
import os

import numpy as np
import pytest

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
tf = pytest.importorskip("tensorflow")

from open_eye import DRAM, channel_pad, data_create, ptq  # noqa: E402
from open_eye import layer_parameters as lp  # noqa: E402
from open_eye import open_eye_parameters as oep  # noqa: E402
from open_eye import simple_layer_operations as slo  # noqa: E402
from open_eye import test_utils_main as tum  # noqa: E402

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "doc", "demo_notebooks",
                     "mnist_quantized_model.tflite")
# Platform of test/cocotb_fpga/test_ptq_mnist.py (test_conv_const._run_conv_const, QUANT_AMOUNT 64)
PLATFORM = {"CLUSTER_ROWS": "2", "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4",
            "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
            "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "64", "DMA_BITWIDTH": "64", "RAM_CELLS": "32"}


@pytest.fixture(scope="module")
def layers():
    return ptq.quantize_tflite(MODEL)


@pytest.fixture(scope="module")
def mnist():
    try:
        return ptq.load_mnist_test()
    except Exception as exc:                    # no cached copy and no network
        pytest.skip("MNIST test set not available: %s" % exc)


@pytest.mark.parametrize("m,mant,shift", [(0.0033496, 220, 16), (0.5, 128, 8), (1.0, 128, 7), (200.0, 200, 0)])
def test_mant_shift(m, mant, shift):
    assert ptq.mant_shift(m) == (mant, shift)
    assert abs(mant / 2 ** shift - m) <= m / 256


@pytest.mark.parametrize("m", [0.0, -0.1, 300.0])
def test_mant_shift_out_of_range(m):
    with pytest.raises(ValueError):
        ptq.mant_shift(m)


def test_parameters_fit_the_hardware(layers):
    assert [l.kind for l in layers] == ["conv", "pool", "conv", "pool", "conv", "dense", "dense"]
    for l in layers:
        if l.kind == "pool":
            continue
        assert np.abs(l.w).max() == 127                         # per tensor: the largest weight is +-127
        assert np.abs(l.b).max() < 1 << 19                     # bias in the 20-bit psum
        assert len(set(l.mant)) == 1 and len(set(l.shift)) == 1   # one multiplier (bug #12)
        assert 128 <= l.mant[0] <= 255
        m = l.s_in * l.s_w[0] / l.s_out
        assert abs(l.mant[0] / 2 ** l.shift[0] - m) <= m / 256
    assert [l.act_min for l in layers if l.kind != "pool"] == [0, 0, 0, 0, -128]   # ReLU but the last layer


def test_input_quantization():
    assert ptq.quantize_image(np.array([[[0, 1, 2, 128, 253, 255]]], np.uint8)).ravel().tolist() == \
        [0, 0, 1, 64, 126, 127]


def test_requantize_floor_and_saturation(layers):
    l = layers[0]
    s, m = int(l.shift[0]), int(l.mant[0])
    psum = np.array([[0, 2 ** s // m + 1, -1, 10 ** 6, -(10 ** 6)] + [0] * (len(l.b) - 5)])
    assert ptq.requantize(psum, l)[0, :5].tolist() == [0, 1, 0, 127, 0]     # ReLU bound 0


def tflite_predict(images):
    """Classes the TFLite interpreter gives (float input: the image / 255, as in training)."""
    interpreter = tf.lite.Interpreter(model_path=MODEL)
    interpreter.allocate_tensors()
    inp, out = interpreter.get_input_details()[0], interpreter.get_output_details()[0]
    classes = []
    for image in images:
        interpreter.set_tensor(inp["index"], (image[None, :, :, None] / 255.0).astype(np.float32))
        interpreter.invoke()
        classes.append(int(np.argmax(interpreter.get_tensor(out["index"]))))
    return np.array(classes)


def test_accuracy_and_psum_range(layers, mnist):
    """Accuracy as TFLite's on the same images (all 10,000: 99.23 % both), psums in 20 bits."""
    images, labels = mnist
    images, labels = images[:2000], labels[:2000]
    x = ptq.quantize_image(images)
    ours, theirs = ptq.predict(layers, x), tflite_predict(images)
    assert (ours == labels).mean() >= (theirs == labels).mean() - 0.003
    assert (ours == theirs).mean() >= 0.99
    assert max(ptq.max_psum(layers, x)) < 1 << 19                         # largest on 10,000 images: 216,908


def test_per_channel_variant(layers, mnist):
    """per_channel=True (needs bug #12 fixed in the RTL): own multiplier per filter, same accuracy."""
    per_channel = ptq.quantize_tflite(MODEL, per_channel=True)
    assert len(set(per_channel[2].mant.tolist() + per_channel[2].shift.tolist())) > 2
    images, labels = mnist
    x = ptq.quantize_image(images[:2000])
    assert (ptq.predict(per_channel, x) == ptq.predict(layers, x)).mean() >= 0.99


def test_testbench_model_from_a_later_layer(layers, mnist):
    """first=2: conv2 alone, fed with pool1's output; as the last layer it gives its raw psums."""
    images, _ = mnist
    full = ptq.forward(layers, ptq.quantize_image(images[:1]))
    tb_model = ptq.TestbenchModel(layers, images[0], first=2, count=1)
    assert [l.kind for l in tb_model.layers] == ["conv"]
    assert np.array_equal(tb_model.input, full[1]["out"])
    assert np.array_equal(tb_model.results[0]["out"], full[2]["psum"])


def build_testbench_model():
    """The model, layer parameters and DRAM of test_ptq_mnist.py, built as OpenEye_FPGA_tb.py does."""
    tf.keras.utils.set_random_seed(1)
    model = data_create.create_layer("MNIST_REAL_RELU", 4, 3, 3, 28, 28, (1, 1), 1, 10)
    model = [layer for layer in model.layers if not isinstance(layer, tf.keras.layers.Flatten)]
    params = oep.get_oep(1)

    def build(model):
        out = [0 for _ in model]
        for n, layer in reversed(list(enumerate(model))):
            out[len(model) - n - 1] = lp.LayerParameters(out, layer, params, n, len(model))
        return list(reversed(out))

    layer_parameters = build(model)
    model, padded = channel_pad.pad_first_layer(model, layer_parameters)
    if padded:
        layer_parameters = build(model)
        layer_parameters[0].pad_channels = model[0].pad_channels
    dram = DRAM.DRAMContents(model, layer_parameters)
    dram.write_initial_data_to_dram(model, layer_parameters, 0, 0)
    return model, layer_parameters, dram, params


@pytest.fixture(scope="module")
def testbench(layers, mnist):
    """The testbench model filled with the int8 model and image 0, and the testbench reference of every
    layer (OpenEye_FPGA_tb.execute_model without the DUT). Runs once: the conv references take a minute."""
    images, _ = mnist
    with pytest.MonkeyPatch.context() as mp:
        for key, value in PLATFORM.items():
            mp.setenv(key, value)
        model, layer_parameters, dram, params = build_testbench_model()
        tb_model = ptq.TestbenchModel(layers[:6], images[0])           # fc1 cut to the probe's 10 outputs
        tb_model.fill(dram, layer_parameters)
        channel_pad.fill_padding_channels(model, dram)
        diffs = []
        for n in range(len(model)):
            results = tum.collect_results(n, layer_parameters[n], dram, params.SERIAL)
            diffs.append(tb_model.check(n, layer_parameters[n], results))
            if n != len(model) - 1:
                dram.fmap[n + 1] = tum.fill_dram_with_ref(results, dram.fmap[n + 1], layer_parameters[n],
                                                          layer_parameters[n + 1])
                if layer_parameters[n].layer_name != "Pooling":
                    slo.batchnorm_output(layer_parameters[n], 1, n, dram)
    return model, layer_parameters, dram, params, tb_model, diffs


def test_testbench_settings(layers, testbench):
    _, layer_parameters, dram, _, _, _ = testbench
    assert [p.quantize[0] for p in layer_parameters if p.layer_name != "Pooling"] == \
        [[int(l.mant[0]), int(l.shift[0])] for l in layers[:6] if l.kind != "pool"]
    assert [p.act_min for p in layer_parameters] == [0, -128, 0, -128, 0, 0]       # fc1 has a ReLU (raw psums here)
    assert dram.bias[0] == layers[0].b.tolist() and dram.bias[5] == layers[5].b[:10].tolist()
    assert all(v == 0 for row in dram.fmap[0][1] for v in row)                     # padding channel (bug #17)


def test_testbench_reference_equals_int8_model(testbench):
    assert testbench[-1] == [0] * 6


def test_testbench_reference_without_flatten_order(layers, testbench, monkeypatch):
    """Negative control: the Dense weights in TFLite's NHWC order give a different Dense result."""
    model, layer_parameters, dram, params, tb_model, _ = testbench
    for key, value in PLATFORM.items():
        monkeypatch.setenv(key, value)
    w = layers[5].w[:10]
    monkeypatch.setattr(dram, "weights", list(dram.weights))
    dram.weights[5] = [[int(v) for v in row] for row in w]
    results = tum.collect_results(5, layer_parameters[5], dram, params.SERIAL)
    assert tb_model.check(5, layer_parameters[5], results) > 0


def test_layer_count_must_match(layers, mnist, monkeypatch):
    for key, value in PLATFORM.items():
        monkeypatch.setenv(key, value)
    _, layer_parameters, dram, _ = build_testbench_model()
    with pytest.raises(ValueError):
        ptq.TestbenchModel(layers, mnist[0][0]).fill(dram, layer_parameters)    # 7 layers vs 6
