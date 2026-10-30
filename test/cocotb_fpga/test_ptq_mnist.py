# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""The trained MNIST int8 model on real test images, quantized for the hardware by open_eye.ptq.

OPENEYE_PTQ (OpenEye_FPGA_tb.py) fills the testbench model with the trained model
doc/demo_notebooks/mnist_quantized_model.tflite and one MNIST test image: int8 weights (per-tensor
scales), biases in psum units, the image as 0..127 activations (or, for a later first layer, the
model's activation there), one quantizer multiplier per layer and the ReLU bound 0. The testbench
checks the reference of every layer against the int8 model (ptq.forward) and the DUT against the
reference, so a PASS means the RTL computes those layers of the trained model bit-exactly.

1. test_ptq_layer: one layer each, the DUT's raw psums on real activations: conv1 on the image (input
   padded to two channels, bug #17), conv2 on pool1's output, conv3 on pool2's output, and fc1's first
   10 outputs on conv3's output (the whole 3136 -> 64 layer hits bug #29).
2. test_ptq_mnist: the model on chip up to fc1 (MNIST_REAL_RELU: Conv 32, MaxPool, Conv 64, MaxPool,
   Conv 64, Dense 3136 -> 10 as a probe of fc1), every layer writing back for the next.

Real data shows bugs that random test data hides (README_FI 8b, 8e; doc/experiments/2026-10-30_ptq.md):
#31 conv1 and conv2 lose their products on real, sparse inputs (the DUT returns the bias: conv1 at all
25,088 outputs, conv2 at 12,320 of 12,544), #32 conv3 (7x7x64 -> 64) swaps the biases of the filter
pairs (2k, 2k+1), #33 fc1's probe is wrong for image 0 (image 1 is right). The chained model fails at
the buffer after the first pooling (#31). Known failures are xfail(strict), so a fix shows as XPASS.

Usage (from the repository root): venv/bin/python -m pytest -q test/cocotb_fpga/test_ptq_mnist.py
(single layers 2-7 minutes, the model about 2 minutes up to the failure; run the ids in parallel,
README_FI 3c).
"""
import os

import pytest

import test_conv_const as conv
from open_eye import open_eye_dir

TRAINED_MODEL = os.path.abspath(os.path.join(open_eye_dir, os.pardir, os.pardir, "doc", "demo_notebooks",
                                             "mnist_quantized_model.tflite"))


def xfail(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


BUG31 = xfail("bug #31: products lost on real sparse inputs, the DUT returns the bias")
BUG32 = xfail("bug #32: biases of the filter pairs (2k, 2k+1) swapped (and bug #9: 7-wide output stream)")
BUG33 = xfail("bug #33: Dense 3136 -> 10 wrong on this real input")

# id: (LAYER, first quantized layer, width, height, input channels, filters, QUANT_AMOUNT, test image)
LAYERS = {
    "conv1-0": pytest.param(("Convolution_Single", 0, 28, 28, 1, 32, 32, 0), marks=BUG31),
    "conv1-1": pytest.param(("Convolution_Single", 0, 28, 28, 1, 32, 32, 1), marks=BUG31),
    "conv2-0": pytest.param(("Convolution_Single", 2, 14, 14, 32, 64, 64, 0), marks=BUG31),
    "conv2-1": pytest.param(("Convolution_Single", 2, 14, 14, 32, 64, 64, 1), marks=BUG31),
    "conv3-0": pytest.param(("Convolution_Single", 4, 7, 7, 64, 64, 64, 0), marks=BUG32),
    "conv3-1": pytest.param(("Convolution_Single", 4, 7, 7, 64, 64, 64, 1), marks=BUG32),
    "fc1_probe-0": pytest.param(("DENSE_CHAIN_3136_10", 5, 1, 1, 1, 4, 32, 0), marks=BUG33),
    "fc1_probe-1": ("DENSE_CHAIN_3136_10", 5, 1, 1, 1, 4, 32, 1),
}


@pytest.mark.parametrize("layer", list(LAYERS.values()), ids=list(LAYERS))
def test_ptq_layer(layer, request, monkeypatch):
    mode, first, width, height, channels, filters, quant_amount, image = layer
    monkeypatch.setenv("OPENEYE_PTQ", f"{TRAINED_MODEL}:{image}:{first}")
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const(mode, 8, 2, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, quant_amount=quant_amount, dma_bitwidth=64, random_data=True,
                         expect_layers=1)


@pytest.mark.parametrize("image", [pytest.param(0, marks=BUG31), pytest.param(1, marks=BUG31)])
def test_ptq_mnist(image, request, monkeypatch):
    monkeypatch.setenv("OPENEYE_PTQ", f"{TRAINED_MODEL}:{image}")
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")       # a 64-filter layer computes ~90,000 cycles
    conv._run_conv_const("MNIST_REAL_RELU", 8, 2, num_glb_iact=1, input_channels=1, request=request,
                         input_height=28, quant_amount=64, dma_bitwidth=64, random_data=True, expect_layers=6)
