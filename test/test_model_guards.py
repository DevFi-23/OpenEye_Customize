# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""The toolchain refuses the layers the RTL computes differently from the model (README_FI section 8e, group A).

Before 2026-11-07 each of these ran to the end and gave wrong outputs without any sign: stride above 1 on an RTL built
with STRIDE_ENABLED=0 (bug #41), a padding other than kernel // 2 (#42), unsupported ONNX nodes, branches, grouped /
dilated convolutions (#43), an odd input channel count above 1 (#7), pooling inputs 4 or fewer pixels wide (#27), a last
Dense layer with more than one psum pass (#21). doc/experiments/2026-11-07_bug41_stride.md has the measurements.
Since 2026-11-10 also an odd number of filters per PE on dense hardware (#48, doc/experiments/2026-11-10_bug46_47.md).
"""
import os
import types

import numpy as np
import pytest

tf = pytest.importorskip("tensorflow")

from open_eye import layer_parameters as lp  # noqa: E402
from open_eye import open_eye_parameters as oep  # noqa: E402

# Platform of the cocotb_fpga tests (test_conv_const._run_conv_const)
PLATFORM = {"CLUSTER_ROWS": "2", "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4",
            "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
            "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "64", "DMA_BITWIDTH": "64", "RAM_CELLS": "32"}


def platform(monkeypatch, stride_enabled=0):
    for key, value in dict(PLATFORM, STRIDE_ENABLED=str(stride_enabled)).items():
        monkeypatch.setenv(key, value)
    return oep.get_oep(1)


def build(layers, params):
    """LayerParameters of a list of Keras layers, built last to first as OpenEye_FPGA_tb does."""
    out = [0] * len(layers)
    for n, layer in reversed(list(enumerate(layers))):
        out[len(layers) - n - 1] = lp.LayerParameters(out, layer, params, n, len(layers))
    return list(reversed(out))


def keras(input_shape, *layers):
    tf.keras.utils.set_random_seed(3)
    return tf.keras.models.Sequential([tf.keras.Input(input_shape), *layers]).layers


def conv(width, channels=4, filters=16, **kw):
    kw.setdefault("padding", "same")
    return keras((width, width, channels), tf.keras.layers.Conv2D(filters, kw.pop("kernel", (3, 3)), **kw))


# --- dense hardware (SPARSITY_EN = 0): the weight block layout the PE reads (#48) -----------------------------------

@pytest.mark.parametrize("filters,refused", [(2, False), (3, True), (4, False), (6, True), (8, False), (10, True),
                                             (16, False)])
def test_dense_odd_filters_per_pe(filters, refused, monkeypatch, caplog):
    # Bug #48: on dense hardware 8 x 4 x 4 -> 6 (3 filters per PE) read 24 weight words per pass from an 18-word block
    # and was wrong everywhere; an even filter count per PE is right (doc/experiments/2026-11-10_bug46_47.md)
    monkeypatch.setenv("SPARSITY_EN", "0")
    params = platform(monkeypatch, stride_enabled=1)
    p = build(keras((8, 4, 4), tf.keras.layers.Conv2D(filters, (3, 3), padding="same")), params)[0]
    assert (p.used_psum_per_PE % 2 == 1) == refused
    if not refused:
        assert lp.check_dense_wght_slots(p, params) == -(-p.used_wght_per_PE // params.PARALLEL_MACS)
        return
    with pytest.raises(NotImplementedError, match="bug #48"):
        lp.check_dense_wght_slots(p, params)
    monkeypatch.setenv(lp.ALLOW_UNSUPPORTED_ENV, "1")
    lp.check_dense_wght_slots(p, params)
    assert "bug #48" in caplog.text


def test_dense_slot_check_is_for_dense_hardware_only(monkeypatch):
    # sparse hardware stops the same layer in the column encoder of bug #22 (ValueError at stream generation)
    monkeypatch.setenv("SPARSITY_EN", "1")
    params = platform(monkeypatch, stride_enabled=1)
    p = build(keras((8, 4, 4), tf.keras.layers.Conv2D(6, (3, 3), padding="same")), params)[0]
    assert p.used_psum_per_PE == 3
    assert lp.check_dense_wght_slots(p, params) is None


# --- convolution: stride (#41), padding (#42), dilation / groups, channels (#7) ---------------------------------------

def test_conv_geometry_accepts_the_working_layers(monkeypatch):
    params = platform(monkeypatch)
    for layer in (conv(8), conv(28, channels=1, filters=32), conv(14, channels=32, filters=64), conv(7, channels=64),
                  conv(8, kernel=(1, 1), padding="valid"), conv(8, channels=2, filters=8)):
        p = build(layer, params)[0]
        assert lp.check_conv_geometry(p, params) is p


def test_stride_needs_stride_enabled(monkeypatch):
    # Bug #41: 8 x 8 x 4 -> 16 with stride 2 was wrong at 13 of 16 positions on the default RTL (STRIDE_ENABLED=0).
    # With STRIDE_ENABLED=1 a strided layer is right since the fixes of #41b-#41d (2026-11-08), so it is accepted
    # (7 x 7: TensorFlow's "same" pads symmetrically there, as the RTL).
    params = platform(monkeypatch, stride_enabled=0)
    p = build(conv(7, strides=2), params)[0]
    with pytest.raises(NotImplementedError, match="STRIDE_ENABLED=0.*bug #41\\)"):
        lp.check_conv_geometry(p, params)
    params = platform(monkeypatch, stride_enabled=1)
    p = build(conv(7, strides=2), params)[0]
    assert lp.check_conv_geometry(p, params) is p


def test_allow_unsupported_only_warns(monkeypatch, caplog):
    # OPENEYE_ALLOW_UNSUPPORTED=1: the layer is streamed anyway (to reproduce a bug on the RTL), with a warning
    params = platform(monkeypatch)
    p = build(conv(8, channels=3), params)[0]
    monkeypatch.setenv(lp.ALLOW_UNSUPPORTED_ENV, "1")
    assert lp.check_conv_geometry(p, params) is p
    assert "bug #7" in caplog.text
    monkeypatch.setenv(lp.ALLOW_UNSUPPORTED_ENV, "0")
    with pytest.raises(NotImplementedError):
        lp.check_conv_geometry(p, params)


@pytest.mark.parametrize("size,kernel,stride", [(8, 3, 2), (7, 3, 2), (16, 3, 2), (15, 3, 2), (8, 3, 1), (9, 5, 2),
                                                (8, 1, 2)])
def test_tf_same_pads_is_tensorflow(size, kernel, stride):
    """tf_same_pads gives the padding TensorFlow's "same" uses: the same output as padding by hand and "valid"."""
    rng = np.random.default_rng(1)
    x = rng.standard_normal((1, size, size, 1)).astype(np.float32)
    w = rng.standard_normal((kernel, kernel, 1, 1)).astype(np.float32)
    lead, trail = lp.tf_same_pads(size, kernel, stride)
    same = tf.nn.conv2d(x, w, stride, "SAME").numpy()
    by_hand = tf.nn.conv2d(np.pad(x, ((0, 0), (lead, trail), (lead, trail), (0, 0))), w, stride, "VALID").numpy()
    np.testing.assert_allclose(same, by_hand, rtol=1e-5, atol=1e-5)


def test_tensorflow_same_with_stride_2_on_an_even_input(monkeypatch):
    # TensorFlow pads 8 x 8, kernel 3, stride 2 by [0, 0, 1, 1] (windows centred at 1, 3, 5, 7); the RTL and the
    # testbench reference pad 1 on every side (centres 0, 2, 4, 6): another convolution, refused even with
    # STRIDE_ENABLED=1 (the stride-2 runs of 2026-11-07/08 passed against the toolchain's reference, not TensorFlow's).
    params = platform(monkeypatch, stride_enabled=1)
    p = build(conv(8, strides=2), params)[0]
    with pytest.raises(NotImplementedError, match=r"pads \[0, 0, 1, 1\].*bug #42"):
        lp.check_conv_geometry(p, params)
    p = build(conv(7, strides=2), params)[0]                      # 7 x 7: [1, 1, 1, 1], as the RTL
    assert lp.check_conv_geometry(p, params) is p


def test_valid_padding_is_refused(monkeypatch):
    # Bug #42: LayerParameters always computed "same"; a 3 x 3 "valid" convolution came out larger and shifted
    params = platform(monkeypatch)
    p = build(conv(8, padding="valid"), params)[0]
    assert p.model_padding == "valid"
    with pytest.raises(NotImplementedError, match="bug #42"):
        lp.check_conv_geometry(p, params)


@pytest.mark.parametrize("layer,expected", [
    (types.SimpleNamespace(padding_pads=[1, 1, 1, 1], padding="same"), [1, 1, 1, 1]),   # onnx2model: the pads win
    (types.SimpleNamespace(padding="SAME"), "same"),
    (types.SimpleNamespace(padding=1), [1, 1, 1, 1]),                                   # PyTorch int
    (types.SimpleNamespace(padding=(0, 2)), [0, 2, 0, 2]),                               # PyTorch pair (H, W)
    (types.SimpleNamespace(), None),
])
def test_model_padding(layer, expected):
    assert lp.model_padding(layer) == expected


def test_onnx_pads(monkeypatch):
    params = platform(monkeypatch)
    p = build(conv(8), params)[0]
    p.model_padding = [1, 1, 1, 1]
    assert lp.check_conv_geometry(p, params) is p
    p.model_padding = [0, 0, 0, 0]
    with pytest.raises(NotImplementedError, match="bug #42"):
        lp.check_conv_geometry(p, params)


def test_dilation_and_groups_are_refused(monkeypatch):
    params = platform(monkeypatch)
    p = build(conv(8, dilation_rate=2), params)[0]
    with pytest.raises(NotImplementedError, match="dilation"):
        lp.check_conv_geometry(p, params)
    p = build(conv(8, groups=2), params)[0]
    assert p.model_groups == 2
    with pytest.raises(NotImplementedError, match="groups 2"):
        lp.check_conv_geometry(p, params)


@pytest.mark.parametrize("channels,refused", [(1, False), (2, False), (3, True), (4, False), (5, True), (8, False)])
def test_odd_channel_counts(channels, refused, monkeypatch):
    # Bug #7: 3 channels are packed 3 bytes per pixel, the RTL moves pairs (test_mnist_layers mapping: 3 channels xfail)
    params = platform(monkeypatch)
    p = build(conv(8, channels=channels), params)[0]
    if refused:
        with pytest.raises(NotImplementedError, match="bug #7"):
            lp.check_conv_geometry(p, params)
    else:
        assert lp.check_conv_geometry(p, params) is p


# --- pooling (#27 and the 2 x 2 window) --------------------------------------------------------------------------------

def conv_pool_conv(width, height=None, pool=(2, 2), strides=None):
    height = height or width
    return keras((width, height, 4), tf.keras.layers.Conv2D(4, (3, 3), padding="same"),
                 tf.keras.layers.MaxPooling2D(pool_size=pool, strides=strides or pool, padding="valid"),
                 tf.keras.layers.Conv2D(4, (3, 3), padding="same"))


@pytest.mark.parametrize("width,height,refused", [(8, 8, False), (6, 6, False), (8, 4, False), (28, 28, False),
                                                  (14, 14, False), (4, 4, True), (4, 8, True), (2, 2, True)])
def test_pooling_width(width, height, refused, monkeypatch):
    # Bug #27, measured 2026-11-07 (Conv_Pool_Conv, CR 2 x CC 2): widths 2 and 4 wrong at every height, 6 and 8 right
    params = platform(monkeypatch)
    pool = build(conv_pool_conv(width, height), params)[1]
    assert pool.layer_name == "Pooling" and pool.pool_size == (2, 2)
    if refused:
        with pytest.raises(NotImplementedError, match="bug #27"):
            lp.check_pooling_geometry(pool)
    else:
        assert lp.check_pooling_geometry(pool) is pool


@pytest.mark.parametrize("pool,strides", [((3, 3), (2, 2)), ((2, 2), (1, 1))])
def test_pooling_window(pool, strides, monkeypatch):
    params = platform(monkeypatch)
    layer = build(conv_pool_conv(16, pool=pool, strides=strides), params)[1]
    with pytest.raises(NotImplementedError, match="2 x 2 windows"):
        lp.check_pooling_geometry(layer)


# --- Dense read-out (#21) ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("outputs,refused", [(10, False), (32, False), (40, True), (64, True)])
def test_dense_readout(outputs, refused, monkeypatch):
    # Bug #21: a last Dense layer with more than 32 outputs (two psum passes at 2 cluster columns): only the first
    # used_psum_per_PE outputs come out right
    params = platform(monkeypatch)
    layer = build(keras((64,), tf.keras.layers.Dense(outputs)), params)[0]
    assert layer.send_values_out == 1 and layer.needed_psum_transmissions == (2 if outputs > 32 else 1)
    if refused:
        with pytest.raises(NotImplementedError, match="bug #21"):
            lp.check_dense_readout(layer)
    else:
        assert lp.check_dense_readout(layer) is layer


def test_dense_written_back_is_accepted():
    # The same layer written back on chip for the next layer is right (doc/experiments/2026-10-24_bug26...)
    layer = types.SimpleNamespace(layer_name="Dense", filters=64, needed_psum_transmissions=2, send_values_out=0)
    assert lp.check_dense_readout(layer) is layer


# --- onnx2model (#43) --------------------------------------------------------------------------------------------------

torch = pytest.importorskip("torch")
pytest.importorskip("onnxruntime")
from open_eye import onnx2model as o2m  # noqa: E402

nn = torch.nn


class Net(nn.Module):
    """A small conv net on 2 x 8 x 8 inputs; `variant` swaps one part for a node the hardware does not compute."""

    def __init__(self, variant="plain"):
        super().__init__()
        self.variant = variant
        groups = 4 if variant == "depthwise" else 1
        dilation = 2 if variant == "dilated" else 1
        self.conv1 = nn.Conv2d(2, 4, 3, padding=1)
        self.conv2 = nn.Conv2d(4, 4, 3, padding=dilation, dilation=dilation, groups=groups)
        self.pool = nn.AvgPool2d(2) if variant == "avgpool" else nn.MaxPool2d(2)
        self.fc = nn.Linear(4 * 4 * 4, 10)

    def forward(self, x):
        x = torch.relu(self.conv1(x))
        y = self.conv2(x)
        y = y + x if self.variant == "residual" else y
        if self.variant == "pool_then_relu":
            y = torch.relu(self.pool(y))
        else:
            y = self.pool(torch.relu(y))
        y = self.fc(torch.flatten(y, 1))
        return torch.softmax(y, 1) if self.variant == "softmax" else y


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                     # onnx2model writes its .onnx files into the working directory
    return tmp_path


def get_model(variant):
    torch.manual_seed(0)
    calibration = np.random.default_rng(0).standard_normal((8, 2, 8, 8)).astype(np.float32)
    return o2m.get_model(Net(variant).eval(), calibration)


def test_onnx_plain_net_passes(in_tmp):
    model = get_model("plain")
    assert [layer.type for layer in model] == ["conv2d", "conv2d", "pooling2d", "dense"]
    assert [layer.activation for layer in model[:2]] == ["relu", "relu"]
    assert model[0].input.shape[1:3] == [8, 8]     # the export follows the calibration data, not MNIST's 28 x 28


@pytest.mark.parametrize("variant,message", [
    ("residual", "QLinearAdd"),
    ("avgpool", "AveragePool"),
    ("softmax", "Softmax"),
    ("depthwise", "group 4"),
    ("dilated", "dilations"),
    ("pool_then_relu", "not an activation of a Conv / Dense layer"),
])
def test_onnx_unsupported_parts_are_refused(variant, message, in_tmp):
    with pytest.raises(NotImplementedError, match=message):
        get_model(variant)


def test_onnx_mnist_graphs_pass(in_tmp):
    """The quantized graphs of the trained MNIST nets (static: ReLU, Leaky ReLU, SiLU, hard-swish) pass the check."""
    import sys
    repo = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
    if not os.path.exists(os.path.join(repo, "doc", "demo_notebooks", "mnist_silu_model.pth")):
        pytest.skip("trained checkpoints not available")
    sys.path.insert(0, os.path.join(repo, "models"))
    from open_eye import data_create
    from train_mnist import load_activation_model
    calibration, _ = data_create.mnist_images("train", range(16))
    for name, activation in [("unquantized", "relu"), ("leaky_relu", "leaky_relu"), ("silu", "silu"),
                             ("hardswish", "hardswish")]:
        net, _ = load_activation_model(os.path.join(repo, "doc", "demo_notebooks", f"mnist_{name}_model.pth"))
        model = o2m.get_model(net, calibration)
        assert [layer.activation for layer in model if layer.type == "conv2d"] == [activation] * 3


# --- pytorch2model (model_loader format='pytorch') ----------------------------------------------------------------------

def test_pytorch2model_accepts_supported_modules():
    # Only modules that do not reach extract_quantization_params: with the installed torch that function calls
    # layer.weight() on every float Conv2d / Linear (a Parameter has q_scale) and fails with a TypeError, an older,
    # unrelated defect of pytorch2model (2026-11-07). The geometry checks run before it.
    from open_eye import pytorch2model as p2m
    net = nn.Sequential(nn.MaxPool2d(2), nn.ReLU(), nn.Dropout(0.1), nn.Identity(), nn.Flatten())
    assert len(p2m.create_model_from_pytorch(net, (1, 1, 28, 28)).layers) == 1
    with pytest.raises(TypeError):
        p2m.create_model_from_pytorch(nn.Sequential(nn.Conv2d(1, 4, 3, padding="same")), (1, 1, 28, 28))


@pytest.mark.parametrize("module,message", [
    (nn.Conv2d(1, 4, 3, padding=1, stride=2), "stride"),            # was converted as stride 1
    (nn.Conv2d(1, 4, 3, padding=0), "padding"),                     # was computed as "same"
    (nn.Conv2d(2, 2, 3, padding=1, groups=2), "groups"),
    (nn.Conv2d(1, 4, 3, padding=2, dilation=2), "dilation"),
    (nn.MaxPool2d(3, 2), "2 x 2 windows"),
    (nn.AvgPool2d(2), "Unsupported layer type AvgPool2d"),          # was skipped with a warning
    (nn.BatchNorm2d(1), "Unsupported layer type BatchNorm2d"),
])
def test_pytorch2model_refuses(module, message):
    from open_eye import pytorch2model as p2m
    with pytest.raises(NotImplementedError, match=message):
        p2m.create_model_from_pytorch(nn.Sequential(module), (1, 1 if not isinstance(module, nn.Conv2d) or
                                                              module.in_channels == 1 else 2, 28, 28))
