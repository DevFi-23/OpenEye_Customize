# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""The trained PyTorch MNIST model through the toolchain's own path on the RTL.

OpenEye_FPGA_tb with USE_RANDOM_VALUES=0 builds models/mnist_conv_net.SimpleMNISTConvNet; OPENEYE_MODEL_WEIGHTS loads the
trained checkpoint doc/demo_notebooks/mnist_unquantized_model.pth, which onnx2model quantizes statically (calibration
on MNIST training images, zero point 0, one weight scale per layer); OPENEYE_INPUT_IMAGE feeds MNIST test image <i>,
preprocessed as in training. LayerParameters, DRAMContents and the mappers then carry the model's int8 weights, int32
biases, quantizer multipliers and ReLU bounds to the RTL, which runs Conv 32, MaxPool, Conv 64, MaxPool, Conv 64,
Dense 3136 -> 10 on chip. The testbench checks the iact buffer after every layer and the final psums against its
reference; test/test_onnx_model_flow.py checks that reference against ONNX Runtime (rounding differences only).

Today conv1 + pool1 and conv2 + pool2 are bit-exact on chip, conv3 is not (xfail(strict)): bug #32 (conv3 computes two
filters at a time and gets the biases of the filter pairs (2k, 2k+1) swapped) on both images, and on image 0 also bug #31
(an empty pass at conv3's last output line loses the rest of the layer; the old bug #35).
doc/experiments/2026-10-30_bug32_bias_order.md: with #32 corrected in the simulation, image 1 passes end to end.

Usage (from the repository root; about 11 minutes per image):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_real_model.py
"""
import os

import pytest

import test_conv_const as conv
from open_eye import open_eye_dir

CHECKPOINT = os.path.abspath(os.path.join(open_eye_dir, os.pardir, os.pardir, "doc", "demo_notebooks",
                                          "mnist_unquantized_model.pth"))
BUG32 = "bug #32: conv3 swaps the biases of filter pairs (iact buffer check before the Dense layer)"
BUG31 = "; bug #31: empty pass at conv3's last output line"


@pytest.mark.parametrize("image", [pytest.param(0, marks=pytest.mark.xfail(strict=True, reason=BUG32 + BUG31)),
                                   pytest.param(1, marks=pytest.mark.xfail(strict=True, reason=BUG32))])
def test_real_model(image, request, monkeypatch):
    if not os.path.exists(CHECKPOINT):
        pytest.skip("trained checkpoint not available")
    real_run = conv.cocotb_test.simulator.run

    def run(**kw):
        kw["extra_env"] = dict(kw["extra_env"], USE_RANDOM_VALUES="0", OPENEYE_MODEL_WEIGHTS=CHECKPOINT,
                               OPENEYE_INPUT_IMAGE=str(image), OPENEYE_FAIL_ON_STALL="400000")
        return real_run(**kw)
    monkeypatch.setattr(conv.cocotb_test.simulator, "run", run)
    conv._run_conv_const("MNIST_REAL", 8, 2, num_glb_iact=1, input_channels=1, request=request, input_height=28,
                         quant_amount=64, dma_bitwidth=64, random_data=True, expect_layers=6)
