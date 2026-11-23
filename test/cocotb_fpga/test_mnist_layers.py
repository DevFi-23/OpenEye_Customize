# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Activation-mapping regressions and the real MNIST convolution layers.

1. test_iact_channel_mapping: one small Conv layer (8x4, ramp activations,
   asymmetric kernel) for 1/2/3/4/5/8 input channels and NUM_GLB_IACT 1 and 3.
   Guards the iact_stream_constructor fixes:
     - one input channel (bug #6, output was the bias only; fixed 2026-10-14
       with a row-pair address, since the bug #17 fix of 2026-11-04 every
       pixel is a word of its own on the multi-channel address loops);
     - NUM_GLB_IACT=3: a convolution broadcasts every word to all iact banks
       instead of the Dense-style bank rotation (bug #7).
   An odd channel count above 1 (3, 5) failed until 2026-11-22: the Python
   stream packs three bytes per pixel while the RTL moves activations in pairs
   (bug #7, README_FI 8b). Since then the testbench pads such a first layer to
   the next even count with a zero channel (open_eye.channel_pad).

2. test_mnist_conv: the three convolution layers of models/mnist_conv_net.py
   with their real shapes. The 64-filter layers need QUANT_AMOUNT >= 64 (one
   quantisation entry per filter). Known failures were marked
   xfail(strict) so that a fix showed up as XPASS; none is left since
   2026-11-22. Conv2 passes since the bug #18 fix (2026-10-15); Conv1 passes
   with its one channel since the RTL fix of bug #17 (2026-11-04; from
   2026-10-22 on with its input padded to two channels, open_eye.channel_pad,
   which test_mnist_conv1_with_padding still runs); Conv3 passes since the testbench fix of bug #9 (2026-11-22: the
   file check skips the padding slot of its 7-wide rows; every value was always right). The FC layer (3136 -> 10) is not included: Dense layers with 10
   outputs fail with the open bug #5 (test_gemm_layer.py::test_dense_ten_outputs).

3. test_random_data: random activations and weights (the constant-weight
   hooks hid bug #18), each followed by tools/verify_conv_output.py, an
   independent numpy recomputation that checks every DMA output word. The
   one-channel layers wider than one x pass run as one channel since the RTL
   fix of bug #17 (2026-11-04; they were padded to two channels before).
   Random conv weights keep their zeros since 2026-10-24 (bug #22).

4. test_trained_mnist_conv: the three convolution layers with the weights of
   the trained int8 model doc/demo_notebooks/mnist_quantized_model.tflite
   (about 1 % zero weights, which the conv weight encoding got wrong before
   the bug #22 fix: Conv2 and Conv3 hung), random activations, each followed
   by the independent check.

The README_FI file documents the findings (sections 8b and 9). Usage:
    pytest test_mnist_layers.py -v -k mapping     # about 30 s per case
    pytest test_mnist_layers.py -v -k test_mnist_conv   # 4-15 min per layer
    pytest test_mnist_layers.py -v -k random      # 0.5-8 min per layer
    pytest test_mnist_layers.py -v -k trained     # 4-7 min per layer
"""

import os
import sys

import pytest

import test_conv_const as conv
from open_eye import test_dir, open_eye_dir

@pytest.mark.parametrize("channels", [1, 2, 3, 4, 5, 8])
@pytest.mark.parametrize("num_glb_iact", [1, 3])
def test_iact_channel_mapping(num_glb_iact, channels, request, monkeypatch):
    # 3 and 5 channels: the testbench pads the input to 4 / 8 with zero channels (bug #7, open_eye.channel_pad)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", 8)
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=num_glb_iact,
                         input_channels=channels, request=request, input_height=4,
                         ramp_iacts=True, asymmetric_kernel=True, quant_amount=32,
                         dma_bitwidth=64)


# id: (width, height, input channels, filters, QUANT_AMOUNT)
MNIST_LAYERS = {
    "conv1_28x28_c1_f32": (28, 28, 1, 32, 32),          # one channel, 2 x passes (bug #17, fixed)
    "conv2_14x14_c32_f64": (14, 14, 32, 64, 64),
    # 7-wide rows: the padding slot after x = 6 is not compared (bug #9, fixed in the testbench 2026-11-22)
    "conv3_7x7_c64_f64": (7, 7, 64, 64, 64),
}


def _sim_dir(request):
    """Simulation directory _run_conv_const uses for this test."""
    nodeid = request.node.nodeid.replace("::", "_").replace("/", "_").replace("[", "_").replace("]", "_")
    return os.path.join(test_dir, ".temp", nodeid)


def _verify_independently(request):
    """Recompute the layer with numpy and check every DUT output word (tools/verify_conv_output.py)."""
    sys.path.insert(0, os.path.join(test_dir, os.pardir, "tools"))
    import verify_conv_output
    assert verify_conv_output.check(_sim_dir(request)), "independent word-by-word check failed"


@pytest.mark.parametrize("layer", list(MNIST_LAYERS.values()), ids=list(MNIST_LAYERS))
def test_mnist_conv(layer, request, monkeypatch):
    width, height, channels, filters, quant_amount = layer
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_DUMP_VERIFY", "1")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=channels,
                         request=request, input_height=height, ramp_iacts=True,
                         asymmetric_kernel=True, quant_amount=quant_amount, dma_bitwidth=64)
    _verify_independently(request)


def test_mnist_conv1_with_padding(request, monkeypatch):
    """MNIST Conv1 with the former bug #17 workaround (input padded to two channels, OPENEYE_PAD_CHANNELS=1): the
    same results as the one-channel run. It was test_mnist_conv1_without_padding, xfail(strict) until the RTL fix of
    2026-11-04 made it XPASS; since then test_mnist_conv runs Conv1 without padding."""
    monkeypatch.setenv("OPENEYE_PAD_CHANNELS", "1")
    test_mnist_conv(MNIST_LAYERS["conv1_28x28_c1_f32"], request, monkeypatch)


# Random activations and weights. Constant test weights are identical for every
# channel and filter and hid bug #18 (weights of the wrong channel chunk).
# id: (width, height, input channels, filters, QUANT_AMOUNT)
RANDOM_LAYERS = {
    "8x4_c8_f4": (8, 4, 8, 4, 32),
    "8x4_c32_f32": (8, 4, 32, 32, 32),
    "8x4_c8_f64": (8, 4, 8, 64, 64),
    "8x4_c64_f64": (8, 4, 64, 64, 64),
    "14x14_c32_f32": (14, 14, 32, 32, 32),
    "mnist_conv2_14x14_c32_f64": (14, 14, 32, 64, 64),
    # One channel, two and three x passes (bug #17, fixed in the RTL 2026-11-04; padded to 2 channels before)
    "20x8_c1_f8": (20, 8, 1, 8, 32),
    "28x28_c1_f32": (28, 28, 1, 32, 32),
    "40x8_c1_f8": (40, 8, 1, 8, 32),
    # One channel, 64 filters: two weight passes (bug #39, the second filter group got the first group's weights)
    "8x4_c1_f64": (8, 4, 1, 64, 64),
}


@pytest.mark.parametrize("layer", list(RANDOM_LAYERS.values()), ids=list(RANDOM_LAYERS))
def test_random_data(layer, request, monkeypatch):
    width, height, channels, filters, quant_amount = layer
    monkeypatch.setenv("OPENEYE_DUMP_VERIFY", "1")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=channels,
                         request=request, input_height=height, quant_amount=quant_amount,
                         dma_bitwidth=64, random_data=True)
    _verify_independently(request)


# Weights of the trained int8 MNIST model; id: (width, height, input channels, filters, QUANT_AMOUNT, tensor)
TRAINED_MODEL = os.path.join(open_eye_dir, os.pardir, os.pardir, "doc", "demo_notebooks", "mnist_quantized_model.tflite")
TRAINED_LAYERS = {
    "conv1_28x28_c1_f32": (28, 28, 1, 32, 32, "sequential_1/conv2d_1/convolution"),        # 1 zero weight
    "conv2_14x14_c32_f64": (14, 14, 32, 64, 64, "sequential_1/conv2d_1_2/convolution"),    # 189 zero weights
    "conv3_7x7_c64_f64": (7, 7, 64, 64, 64, "sequential_1/conv2d_2_1/convolution"),          # 418 zero weights
}


@pytest.mark.parametrize("layer", list(TRAINED_LAYERS.values()), ids=list(TRAINED_LAYERS))
def test_trained_mnist_conv(layer, request, monkeypatch):
    width, height, channels, filters, quant_amount, tensor = layer
    monkeypatch.setenv("OPENEYE_DUMP_VERIFY", "1")
    monkeypatch.setenv("OPENEYE_TFLITE_CONV", f"{os.path.abspath(TRAINED_MODEL)}:{tensor}")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=channels,
                         request=request, input_height=height, quant_amount=quant_amount,
                         dma_bitwidth=64, random_data=True)
    _verify_independently(request)

