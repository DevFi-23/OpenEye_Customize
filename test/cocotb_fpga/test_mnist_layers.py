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
   quantisation entry per filter). All three still fail for reasons outside
   the 2026-10-14 fixes (bugs #17, #18, #9 in README_FI 8b); they are marked
   xfail(strict) so that a fix shows up as XPASS and the mark has to be
   removed. The FC layer (3136 -> 10) is not included: Dense layers with 10
   outputs fail with the open bug #5 (test_gemm_layer.py::test_dense_ten_outputs).

The README_FI file documents the findings (sections 8b and 9). Usage:
    pytest test_mnist_layers.py -v -k mapping     # about 30 s per case
    pytest test_mnist_layers.py -v -k mnist       # 4-15 min per layer
"""

import pytest

import test_conv_const as conv

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
    "conv1_28x28_c1_f32": pytest.param(
        (28, 28, 1, 32, 32), marks=pytest.mark.xfail(
            strict=True, reason="bug #17: one-channel packing ignores the x passes of images wider than one pass")),
    "conv2_14x14_c32_f64": pytest.param(
        (14, 14, 32, 64, 64), marks=pytest.mark.xfail(
            strict=True, reason="bug #18: with 32+ input channels the filters 32-63 (second filter pass) are wrong")),
    "conv3_7x7_c64_f64": pytest.param(
        (7, 7, 64, 64, 64), marks=pytest.mark.xfail(
            strict=True, reason="bug #18 (filters 32-63 wrong) and bug #9 (padding cells of 7-wide images)")),
}


@pytest.mark.parametrize("layer", list(MNIST_LAYERS.values()), ids=list(MNIST_LAYERS))
def test_mnist_conv(layer, request, monkeypatch):
    width, height, channels, filters, quant_amount = layer
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=channels,
                         request=request, input_height=height, ramp_iacts=True,
                         asymmetric_kernel=True, quant_amount=quant_amount, dma_bitwidth=64)
