# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""The toolchain's real-model path, checked against ONNX Runtime without the RTL.

OpenEye_FPGA_tb with USE_RANDOM_VALUES=0 and OPENEYE_MODEL_WEIGHTS runs models/mnist_conv_net.SimpleMNISTConvNet with the
trained checkpoint doc/demo_notebooks/mnist_unquantized_model.pth through onnx2model.get_model with calibration data
(static quantization: zero point 0, one weight scale per layer), LayerParameters, DRAMContents and the testbench
reference (collect_results, fill_dram_with_ref, batchnorm_output). This test builds the same and compares every
layer's reference with the int8 tensors of ONNX Runtime running the same quantized model: they differ only by rounding
(the hardware floors with an 8-bit multiplier, ONNX Runtime rounds to nearest), and the class is the same.
Also: MaxPool is configured as max pooling (onnx2model used to name it "pooling2d", which LayerParameters took for
average pooling), the fused ReLU (has_relu) reaches act_min, and the data in DRAM is the model's (no x127, no test
pattern bias).
"""
import os
import types

import numpy as np
import pytest

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
torch = pytest.importorskip("torch")
onnx = pytest.importorskip("onnx")
ort = pytest.importorskip("onnxruntime")

from open_eye import DRAM, channel_pad, data_create  # noqa: E402
from open_eye import layer_parameters as lp  # noqa: E402
from open_eye import onnx2model as o2m  # noqa: E402
from open_eye import open_eye_parameters as oep  # noqa: E402
from open_eye import simple_layer_operations as slo  # noqa: E402
from open_eye import test_utils_main as tum  # noqa: E402

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
CHECKPOINT = os.path.join(REPO, "doc", "demo_notebooks", "mnist_unquantized_model.pth")
# Platform of the cocotb_fpga model runs (test_profile model cases, QUANT_AMOUNT 64)
PLATFORM = {"CLUSTER_ROWS": "2", "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4",
            "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
            "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "64", "DMA_BITWIDTH": "64", "RAM_CELLS": "32"}


def build_layers(model, params):
    """LayerParameters as OpenEye_FPGA_tb builds them, with the bug #17 channel padding."""
    def build(m):
        out = [0] * len(m)
        for n, layer in reversed(list(enumerate(m))):
            out[len(m) - n - 1] = lp.LayerParameters(out, layer, params, n, len(m))
        return list(reversed(out))
    layer_parameters = build(model)
    model, padded = channel_pad.pad_first_layer(model, layer_parameters)
    if padded:
        layer_parameters = build(model)
        layer_parameters[0].pad_channels = model[0].pad_channels
    return model, layer_parameters


def reference(model, layer_parameters, params, image):
    """DRAMContents with the model's data and one input image, and the testbench reference of every layer."""
    dram = DRAM.DRAMContents(model, layer_parameters)
    dram.write_initial_data_to_dram(model, layer_parameters, 0, 0)
    dram.fmap[0][0] = o2m.quantize_input(model, image).tolist()          # as OPENEYE_INPUT_IMAGE
    channel_pad.fill_padding_channels(model, dram)
    out = {}
    for n in range(len(model)):
        res = tum.collect_results(n, layer_parameters[n], dram, params.SERIAL)
        if hasattr(res, "keys"):
            res = [res[f] for f in range(len(res))]
        out[n] = np.array(res, dtype=np.int64)
        if n != len(model) - 1:
            dram.fmap[n + 1] = tum.fill_dram_with_ref(res, dram.fmap[n + 1], layer_parameters[n], layer_parameters[n + 1])
            if layer_parameters[n].layer_name != "Pooling":
                slo.batchnorm_output(layer_parameters[n], 1, n, dram)
            out[(n, "out")] = np.array(dram.fmap[n + 1], dtype=np.int64)
    return dram, out


@pytest.fixture(scope="module")
def flow(tmp_path_factory):
    if not os.path.exists(CHECKPOINT):
        pytest.skip("trained checkpoint not available")
    import sys
    sys.path.insert(0, os.path.join(REPO, "models"))
    from mnist_conv_net import SimpleMNISTConvNet, load_simple_mnist_model
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("onnx"))                 # onnx2model writes its .onnx files here
    with pytest.MonkeyPatch.context() as mp:
        for key, value in PLATFORM.items():
            mp.setenv(key, value)
        try:
            net = SimpleMNISTConvNet()
            load_simple_mnist_model(CHECKPOINT, net)
            calibration, _ = data_create.mnist_images("train", range(200))
            model = o2m.get_model(net, calibration)
            params = oep.get_oep(1)
            model, layer_parameters = build_layers(model, params)
            graph = onnx.load("simple_mnist_convnet_int8.onnx")
            images, labels = data_create.mnist_images("test", range(2))
            runs = [reference(model, layer_parameters, params, images[i, 0]) for i in range(2)]
        finally:
            os.chdir(cwd)
    return types.SimpleNamespace(model=model, layer_parameters=layer_parameters, graph=graph, images=images,
                                 labels=labels, runs=runs)


def onnxruntime_tensors(model_proto, image):
    """The int8 outputs of every QLinearConv (before the ReLU), of the QuantizeLinear after every MaxPool, and the
    float model output, from ONNX Runtime."""
    model = onnx.ModelProto()
    model.CopyFrom(model_proto)
    nodes = model.graph.node
    names = []
    for i, node in enumerate(nodes):
        if node.op_type == "QLinearConv":
            names.append(("conv", node.output[0]))
        if node.op_type == "QuantizeLinear" and i > 0 and nodes[i - 1].op_type == "MaxPool":
            names.append(("pool", node.output[0]))
    for _, t in names:
        vi = onnx.ValueInfoProto()
        vi.name = t
        model.graph.output.append(vi)
    sess = ort.InferenceSession(model.SerializeToString())
    out = sess.run([t for _, t in names] + ["output"], {"input": image[None, None].astype(np.float32)})
    return [o for (k, _), o in zip(names, out) if k == "conv"], [o for (k, _), o in zip(names, out) if k == "pool"], out[-1]


def test_hardware_multiplier():
    assert o2m.hardware_multiplier(0.0033496) == (220, 16)
    assert o2m.hardware_multiplier(0.5) == (128, 8)
    with pytest.raises(ValueError):
        o2m.hardware_multiplier(300.0)


def test_relu_flag_of_onnx2model_is_read():
    assert lp.activation_min(types.SimpleNamespace(has_relu=True)) == 0
    assert lp.activation_min(types.SimpleNamespace(has_relu=False)) == -128


def test_layer_parameters_from_the_model(flow):
    m, lps = flow.model, flow.layer_parameters
    assert [p.layer_name for p in lps] == ["Convolution2D", "Pooling", "Convolution2D", "Pooling", "Convolution2D", "Dense"]
    assert [m[n].name for n in (1, 3)] == ["max_pooling2d", "max_pooling2d"]
    assert [lps[n].pooling_mode for n in (1, 3)] == [0, 0]              # max pooling, as the RTL computes
    assert [lps[n].act_min for n in (0, 2, 4, 5)] == [0, 0, 0, -128]     # fused ReLU of the three convs
    for n in (0, 2, 4, 5):
        mant, shift = o2m.hardware_multiplier(m[n].input_scale * m[n].scale / m[n].output_scale)
        assert lps[n].quantize[0] == [mant, shift] and lps[n].quantize[lps[n].filters - 1] == [mant, shift]


def test_dram_holds_the_model(flow):
    m, lps = flow.model, flow.layer_parameters
    dram = flow.runs[0][0]
    for n in (0, 2, 4):
        w = np.asarray(m[n].weights[0])                                  # [row][column][channel][filter]
        c = 0
        assert dram.weights[n][c][3][2][1] == int(w[1][2][c][3])          # weights[c][f][column][row], no x127
        assert dram.bias[n] == [int(v) for v in m[n].weights[1]]        # the model's int32 bias, not 1
    order = DRAM.DRAMContents.dense_input_order(lps, 5, m[5])
    w = np.asarray(m[5].weights[0])
    assert dram.weights[5][3][:20] == [int(w[3][order[k]]) for k in range(20)]
    assert dram.bias[5] == [int(v) for v in m[5].weights[1]]
    assert all(np.abs(np.asarray(dram.bias[n])).max() < 1 << 19 for n in (0, 2, 4, 5))


@pytest.mark.parametrize("i", [0, 1])
def test_reference_matches_onnxruntime(flow, i):
    """Rounding differences only (the hardware floors with an 8-bit multiplier, ONNX Runtime rounds to nearest; they
    grow slowly with depth: measured on test images 0-3, conv1/pool1 at most 1, conv2..conv3 at most 3 with >= 98 %
    within 1), and the same class."""
    m, lps = flow.model, flow.layer_parameters
    _, ref = flow.runs[i]
    convs, pools, logits = onnxruntime_tensors(flow.graph, flow.images[i, 0])

    def close(a, b, max_diff=3):
        d = np.abs(a.astype(np.int64) - b.astype(np.int64))
        return d.max() <= max_diff and (d <= 1).mean() >= 0.97

    assert close(ref[(0, "out")], np.maximum(convs[0][0], 0), 1)        # conv1, ReLU (layout [channel][row][column])
    assert close(ref[1], pools[0][0], 1)                                # pool1
    assert close(ref[(2, "out")], np.maximum(convs[1][0], 0))           # conv2
    assert close(ref[3], pools[1][0])                                   # pool2
    order = DRAM.DRAMContents.dense_input_order(lps, 5, m[5])
    assert close(ref[(4, "out")], np.maximum(convs[2][0], 0).reshape(-1)[order])   # conv3, in the Dense input order
    psums = ref[5].ravel()
    assert np.abs(np.concatenate([ref[n].ravel() for n in (0, 2, 4, 5)])).max() < 1 << 19   # 20-bit psums
    assert int(np.argmax(psums)) == int(np.argmax(logits[0])) == int(flow.labels[i])
