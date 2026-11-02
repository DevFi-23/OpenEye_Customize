# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Activation functions beyond ReLU in the toolchain (step A of doc/experiments/2026-11-02_activation_plan.md, no RTL).

The planned hardware: Leaky ReLU as a second [mant, shift] of the quantizer for negative sums, SiLU and hard-swish as
a 256-entry int8 -> int8 table applied to the clamped quantizer output, optionally rounding to nearest. Checked here:
the testbench reference (simple_layer_operations.batchnorm_output) against the integer formulas, onnx2model's
detection of the activations in ONNX Runtime's statically quantized graph, LayerParameters, the guard that keeps these
layers off the RTL, and (with the trained checkpoints of models/train_mnist.py) the reference of every layer against
ONNX Runtime running the same quantized model.
"""
import os
import sys
import types

import numpy as np
import pytest

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
torch = pytest.importorskip("torch")
onnx = pytest.importorskip("onnx")
ort = pytest.importorskip("onnxruntime")

from open_eye import DRAM, data_create  # noqa: E402
from open_eye import layer_parameters as lp  # noqa: E402
from open_eye import onnx2model as o2m  # noqa: E402
from open_eye import open_eye_parameters as oep  # noqa: E402
from open_eye import simple_layer_operations as slo  # noqa: E402

import test_onnx_model_flow as flow  # noqa: E402

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, os.path.join(REPO, "models"))
from mnist_conv_net import SimpleMNISTConvNet  # noqa: E402

VARIANTS = ("leaky_relu", "silu", "hardswish")


def checkpoint(activation):
    return os.path.join(REPO, "doc", "demo_notebooks", f"mnist_{activation}_model.pth")


def requantize(v, mant, shift, rounding):
    """The quantizer's integer step: floor(mant * v / 2^shift), or rounded half up."""
    return (mant * v + ((1 << (shift - 1)) if rounding and shift > 0 else 0)) >> shift


def run_reference(mode, values, quantize, negative=None, table=None, rounding=False, dense=False):
    """batchnorm_output on one layer output: conv values [filter][x][y], dense values [filter]."""
    layer = types.SimpleNamespace(act_min=-128, act_mode=mode, act_negative=negative, act_table=table,
                                  act_round=rounding, quantize=quantize, layer_name="Dense" if dense else "Conv")
    dram = types.SimpleNamespace(fmap=[None, [list(map(list, f)) if not dense else f for f in values]])
    if dense:
        dram.fmap[1] = list(values)
    slo.batchnorm_output(layer, 1, 0, dram)
    return np.array(dram.fmap[1], dtype=np.int64)


@pytest.mark.parametrize("rounding", [False, True])
def test_reference_leaky_two_slopes(rounding):
    rng = np.random.default_rng(1)
    psum = rng.integers(-40000, 40000, size=(3, 4, 5))
    quantize = [[201, 14], [150, 13], [99, 12]]
    negative = [164, 17]                                    # alpha ~ 0.1 of filter 0's slope
    got = run_reference("leaky", psum.tolist(), quantize, negative=negative, rounding=rounding)
    for f in range(3):
        pos = requantize(psum[f], quantize[f][0], quantize[f][1], rounding)
        neg = requantize(psum[f], negative[0], negative[1], rounding)
        assert (got[f] == np.clip(np.where(psum[f] < 0, neg, pos), -128, 127)).all()


@pytest.mark.parametrize("rounding", [False, True])
def test_reference_table(rounding):
    rng = np.random.default_rng(2)
    psum = rng.integers(-60000, 60000, size=(2, 3, 3))
    quantize = [[180, 14], [181, 14]]
    table = [(i * 7) % 256 - 128 for i in range(256)]       # any int8 table
    got = run_reference("table", psum.tolist(), quantize, table=table, rounding=rounding)
    for f in range(2):
        index = np.clip(requantize(psum[f], quantize[f][0], quantize[f][1], rounding), -128, 127)
        assert (got[f] == np.array(table)[index + 128]).all()


def test_reference_dense_uses_filter_0():
    psum = [-3000, 2000, -10, 77777]
    got = run_reference("leaky", psum, [[100, 12], [7, 1]], negative=[10, 12], dense=True)
    assert got.tolist() == [int(np.clip(requantize(v, *([10, 12] if v < 0 else [100, 12]), False), -128, 127))
                            for v in psum]


def test_reference_round_applies_to_relu():
    psum = [[[-500, 0, 300], [70000, -70000, 5], [13, 14, 15]]]
    layer = types.SimpleNamespace(act_min=0, act_mode="relu", act_negative=None, act_table=None, act_round=True,
                                  quantize=[[200, 4]], layer_name="Conv")
    dram = types.SimpleNamespace(fmap=[None, [list(map(list, psum[0]))]])
    slo.batchnorm_output(layer, 1, 0, dram)
    expected = np.clip(requantize(np.array(psum[0]), 200, 4, True), 0, 127)
    assert (np.array(dram.fmap[1][0]) == expected).all()


def test_reference_relu_unchanged():
    psum = [[[-500, 0, 300], [70000, -70000, 5]]]
    layer_relu = run_reference("relu", psum, [[200, 14]])
    expected = np.clip(np.floor(200 * np.array(psum[0]) / 2 ** 14), -128, 127)
    assert (layer_relu[0] == expected).all()                # act_min -128 here: the mode alone changes nothing


@pytest.mark.parametrize("function", ["silu", "hardswish"])
def test_activation_table(function):
    s_in, s_out = 0.05, 0.03
    table = o2m.activation_table(function, None, s_in, s_out)
    x = np.arange(-128, 128) * s_in
    y = o2m.ACTIVATION_FUNCTIONS[function](x, None) / s_out
    assert len(table) == 256 and table[128] == 0            # f(0) = 0
    assert np.abs(np.array(table) - np.clip(y, -128, 127)).max() <= 0.5 + 1e-9
    assert min(table) < 0                                   # both have a small negative part


def test_activation_config():
    def layer(**kw):
        return types.SimpleNamespace(**kw)
    assert lp.activation_config(layer(has_relu=True)) == ("relu", None, None, False)
    assert lp.activation_config(layer(has_relu=False)) == ("none", None, None, False)
    assert lp.activation_config(layer(has_relu=False, activation="leaky_relu",
                                      activation_negative_factor=[3, 5])) == ("leaky", [3, 5], None, False)
    table = list(range(-128, 128))
    assert lp.activation_config(layer(has_relu=False, activation="silu", activation_table=table,
                                      activation_round=True)) == ("table", None, table, True)
    lp.check_rtl_activation(layer(act_mode="relu", act_round=False))
    for mode, rounding in (("leaky", False), ("table", False), ("relu", True)):
        with pytest.raises(NotImplementedError):
            lp.check_rtl_activation(layer(act_mode=mode, act_round=rounding))


@pytest.fixture(scope="module")
def untrained(tmp_path_factory):
    """onnx2model on untrained variants (seeded): the activations it finds and their parameters."""
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("act_onnx"))
    try:
        calibration, _ = data_create.mnist_images("train", range(20))
        out = {}
        for name in ("relu",) + VARIANTS:
            torch.manual_seed(0)
            out[name] = o2m.get_model(SimpleMNISTConvNet(name), calibration)
    finally:
        os.chdir(cwd)
    return out


@pytest.mark.parametrize("name", ("relu",) + VARIANTS)
def test_onnx2model_finds_the_activation(untrained, name):
    model = untrained[name]
    convs = [model[n] for n in (0, 2, 4)]
    assert [layer.activation for layer in convs] == [name] * 3
    assert model[5].activation == "none"
    for n, layer in zip((0, 2, 4), convs):
        nxt = model[n + 2] if n < 4 else model[5]               # the next compute layer reads the activation's output
        m = layer.input_scale * layer.scale
        if name == "relu":
            assert layer.has_relu and layer.activation_output_scale is None and layer.activation_table is None
            continue
        assert not layer.has_relu
        assert layer.activation_output_scale == pytest.approx(nxt.input_scale)
        if name == "leaky_relu":
            assert layer.activation_alpha == pytest.approx(0.1)
            assert layer.quantization_factor[0] == list(o2m.hardware_multiplier(m / nxt.input_scale))
            assert layer.activation_negative_factor == list(o2m.hardware_multiplier(0.1 * m / nxt.input_scale))
            assert layer.activation_table is None
        else:
            assert layer.quantization_factor[0] == list(o2m.hardware_multiplier(m / layer.output_scale))
            assert layer.activation_table == o2m.activation_table(name, None, layer.output_scale, nxt.input_scale)


@pytest.mark.parametrize("name", VARIANTS)
def test_layer_parameters_take_the_activation(untrained, name, monkeypatch):
    for key, value in flow.PLATFORM.items():                   # QUANT_AMOUNT 64 for the 64-filter layers
        monkeypatch.setenv(key, value)
    model, lps = flow.build_layers(untrained[name], oep.get_oep(1))
    mode = "leaky" if name == "leaky_relu" else "table"
    assert [lps[n].act_mode for n in (0, 2, 4, 5)] == [mode, mode, mode, "none"]
    assert [lps[n].act_min for n in (0, 2, 4)] == [-128] * 3       # no clamp at 0: the activation has a negative part
    for n in (0, 2, 4):
        assert (lps[n].act_negative is not None) == (mode == "leaky")
        assert (lps[n].act_table is not None) == (mode == "table")
        with pytest.raises(NotImplementedError):
            lp.check_rtl_activation(lps[n])


def activation_outputs(model_proto, image):
    """ONNX Runtime's int8 output of every conv layer's activation (QLinearLeakyRelu or the QLinearMul of SiLU /
    hard-swish) and the float model output."""
    model = onnx.ModelProto()
    model.CopyFrom(model_proto)
    consumers = o2m.tensor_consumers(model)
    names = []
    for node in model.graph.node:
        if node.op_type != "QLinearConv":
            continue
        readers = consumers[node.output[0]]
        act = next((n for n in readers if n.op_type in ("QLinearLeakyRelu", "QLinearMul")), None)
        names.append(act.output[0])
    for t in names:
        vi = onnx.ValueInfoProto()
        vi.name = t
        model.graph.output.append(vi)
    out = ort.InferenceSession(model.SerializeToString()).run(names + ["output"],
                                                               {"input": image[None, None].astype(np.float32)})
    return out[:-1], out[-1]


@pytest.fixture(scope="module", params=VARIANTS)
def trained(request, tmp_path_factory):
    name = request.param
    if not os.path.exists(checkpoint(name)):
        pytest.skip(f"no checkpoint {checkpoint(name)} (models/train_mnist.py --activation {name})")
    from train_mnist import load_activation_model
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp(f"act_{name}"))
    with pytest.MonkeyPatch.context() as mp:
        for key, value in flow.PLATFORM.items():
            mp.setenv(key, value)
        try:
            net, _ = load_activation_model(checkpoint(name))
            calibration, _ = data_create.mnist_images("train", range(200))
            model = o2m.get_model(net, calibration)
            params = oep.get_oep(1)
            model, layer_parameters = flow.build_layers(model, params)
            graph = onnx.load("simple_mnist_convnet_int8.onnx")
            images, labels = data_create.mnist_images("test", range(2))
        finally:
            os.chdir(cwd)
    return types.SimpleNamespace(name=name, model=model, layer_parameters=layer_parameters, params=params,
                                 graph=graph, images=images, labels=labels)


# Measured on test images 0-3 (2026-11-02, doc/experiments/2026-11-02_activation.md), all three variants: with the
# floor of today's quantizer every layer is biased by about -0.5 (mean -0.4 ... -0.6) and the difference grows to 7 at
# conv3 (>= 83 % within 1); rounding to nearest, as ONNX Runtime does, keeps it at <= 4 (>= 94 % within 1). ONNX Runtime
# also rounds twice for SiLU and hard-swish (sigmoid or hard sigmoid, then a multiplication).
TOLERANCE = {False: (7, 0.82), True: (4, 0.94)}


@pytest.mark.parametrize("rounding", [False, True])
@pytest.mark.parametrize("i", [0, 1])
def test_reference_matches_onnxruntime(trained, i, rounding):
    m, lps = trained.model, trained.layer_parameters
    for n in (0, 2, 4):
        lps[n].act_round = rounding
    try:
        _, ref = flow.reference(m, lps, trained.params, trained.images[i, 0])
    finally:
        for n in (0, 2, 4):
            lps[n].act_round = False
    acts, logits = activation_outputs(trained.graph, trained.images[i, 0])
    order = DRAM.DRAMContents.dense_input_order(lps, 5, m[5])
    ours = [ref[(0, "out")], ref[(2, "out")], ref[(4, "out")]]
    theirs = [acts[0][0], acts[1][0], acts[2][0].reshape(-1)[order]]
    max_diff, within_1 = TOLERANCE[rounding]
    for n, (a, b) in enumerate(zip(ours, theirs)):
        d = np.abs(a.astype(np.int64) - b.astype(np.int64))
        assert d.max() <= max_diff, (trained.name, n, d.max())
        assert (d <= 1).mean() >= within_1, (trained.name, n, (d <= 1).mean())
    assert int(np.argmax(ref[5].ravel())) == int(np.argmax(logits[0])) == int(trained.labels[i])
