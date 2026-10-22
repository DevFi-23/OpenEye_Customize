# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Activation-mapping regressions and the real MNIST convolution layers.

1. test_iact_channel_mapping: one small Conv layer (8x4, ramp activations,
   asymmetric kernel) for 1/2/4/8 input channels and NUM_GLB_IACT 1 and 3.
   Guards the two iact_stream_constructor fixes of 2026-10-14:
     - one input channel: the RAM is written at the row-pair address
       ram_wr_addr_q (bug #6, output was the bias only);
     - NUM_GLB_IACT=3: a convolution broadcasts every word to all iact banks
       instead of the Dense-style bank rotation (bug #7).
   Three input channels still fail: the Python stream packs three bytes per
   pixel while the RTL moves activations in pairs (xfail, see README_FI 8b).

2. test_mnist_conv: the three convolution layers of models/mnist_conv_net.py
   with their real shapes. The 64-filter layers need QUANT_AMOUNT >= 64 (one
   quantisation entry per filter). Known failures are marked
   xfail(strict) so that a fix shows up as XPASS and the mark has to be
   removed. Conv2 passes since the bug #18 fix (2026-10-15); Conv1 passes
   since 2026-10-22 with its input padded to two channels (open_eye.channel_pad,
   Python workaround for bug #17), test_mnist_conv1_without_padding keeps the
   RTL bug visible; Conv3 computes every value correctly but fails the stream
   check of bug #9. The FC layer (3136 -> 10) is not included: Dense layers with 10
   outputs fail with the open bug #5 (test_gemm_layer.py::test_dense_ten_outputs).

3. test_random_data: random activations and weights (the constant-weight
   hooks hid bug #18), each followed by tools/verify_conv_output.py, an
   independent numpy recomputation that checks every DMA output word. The
   one-channel layers wider than 16 are padded to two channels (bug #17).

The README_FI file documents the findings (sections 8b and 9). Usage:
    pytest test_mnist_layers.py -v -k mapping     # about 30 s per case
    pytest test_mnist_layers.py -v -k mnist       # 4-15 min per layer
    pytest test_mnist_layers.py -v -k random      # 0.5-8 min per layer
"""

import os
import sys

import pytest

import test_conv_const as conv
from open_eye import test_dir

THREE_CHANNELS = pytest.mark.xfail(
    strict=True, reason="bug #7: Python packs 3 bytes per pixel, the RTL moves activations in pairs")


@pytest.mark.parametrize("channels", [1, 2, pytest.param(3, marks=THREE_CHANNELS), 4, 8])
@pytest.mark.parametrize("num_glb_iact", [1, 3])
def test_iact_channel_mapping(num_glb_iact, channels, request, monkeypatch):
    monkeypatch.setattr(conv, "INPUT_SIZE_X", 8)
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=num_glb_iact,
                         input_channels=channels, request=request, input_height=4,
                         ramp_iacts=True, asymmetric_kernel=True, quant_amount=32,
                         dma_bitwidth=64)


# id: (width, height, input channels, filters, QUANT_AMOUNT)
MNIST_LAYERS = {
    "conv1_28x28_c1_f32": (28, 28, 1, 32, 32),          # padded to 2 channels (bug #17)
    "conv2_14x14_c32_f64": (14, 14, 32, 64, 64),
    "conv3_7x7_c64_f64": pytest.param(
        (7, 7, 64, 64, 64), marks=pytest.mark.xfail(
            strict=True, reason="bug #9: padding slots of 7-wide rows are non-zero; every result value is correct "
                                "(tools/verify_conv_output.py)")),
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


@pytest.mark.xfail(strict=True, reason="bug #17: one-channel packing ignores the x passes of images wider than one pass")
def test_mnist_conv1_without_padding(request, monkeypatch):
    """MNIST Conv1 as the RTL gets it without the Python workaround: XPASS once bug #17 is fixed in the RTL."""
    monkeypatch.setenv("OPENEYE_PAD_CHANNELS", "0")
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
    # One channel, two and three x passes: padded to 2 channels (bug #17)
    "20x8_c1_f8": (20, 8, 1, 8, 32),
    "28x28_c1_f32": (28, 28, 1, 32, 32),
    "40x8_c1_f8": (40, 8, 1, 8, 32),
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
