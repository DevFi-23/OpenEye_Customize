# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Strided convolutions on the RTL built with STRIDE_ENABLED=1 (bugs #41, #41b, #41c, #41d).

Stride is an optional part of the RTL (parameter STRIDE_ENABLED of OpenEye_FPGA.v, default 1 since 2026-11-09, 0 before
as upstream); the toolchain refuses a strided layer on an RTL built without it (check_conv_geometry, bug #41). These tests
set STRIDE_ENABLED=1 explicitly and
cover what was wrong before 2026-11-08 (doc/experiments/2026-11-07_bug41_stride.md section 8):
  #41b  the output order with padded output rows (widths 4, 12) and the columns of odd widths (7);
  #41c  the write-back of a strided layer for the next layer (RTL, OpenEye_FPGA.v RECEIVE_PSUMS_TO_IACT);
  #41d  a strided layer whose on-chip input has an odd height (its bottom padding row), also over a buffer half that
        holds older data (Conv -> Pool -> Conv, 28 x 28);
  and the flat layout of a strided convolution's output for a Dense layer.
Every case passes the iact buffer checks and the final comparison; widths whose output rows end in padding slots the
RTL fills with non-zero values (bug #9, values right: 6, 9, 10, 14) are left out because the stream check fails them.

The testbench reference pads kernel // 2 on every side (PyTorch semantics); for an even size Keras "same" with stride 2
pads [0, 1] instead, so check_conv_geometry refuses the Keras layer (bug #42) and these cases set
OPENEYE_ALLOW_UNSUPPORTED=1: the hardware is checked against the symmetric reference, which is what it computes. The
7 x 7 case needs no override (TensorFlow pads 7 x 7 symmetrically).

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_stride.py
"""
import pytest

import test_conv_const as conv

# id: (LAYER, layers, input width, input height, input channels, filters, NUM_GLB_PSUM)
CASES = {
    "single_8x8":         ("Convolution_Single", 1, 8, 8, 4, 16, 4),
    "single_4x8":         ("Convolution_Single", 1, 4, 8, 4, 16, 4),     # 2 outputs + 2 padding slots a kernel (#41b)
    "single_12x8":        ("Convolution_Single", 1, 12, 8, 4, 16, 4),    # 6 outputs + 2 padding slots (#41b)
    "single_7x7":         ("Convolution_Single", 1, 7, 7, 4, 16, 4),     # odd width and height (#41b), no override
    "single_24x8":        ("Convolution_Single", 1, 24, 8, 4, 16, 4),
    "single_7x8_glbp2":   ("Convolution_Single", 1, 7, 8, 4, 16, 2),
    "stack_8x8":          ("Convolution_Stack", 2, 8, 8, 4, 4, 4),       # write-back of a strided layer (#41c)
    "stack_14x8":         ("Convolution_Stack", 2, 14, 8, 4, 4, 4),      # odd intermediate width
    "stack_16x14":        ("Convolution_Stack", 2, 16, 14, 4, 4, 4),     # odd intermediate height (#41d)
    "conv_pool_conv_28":  ("Conv_Pool_Conv", 3, 28, 28, 4, 4, 4),        # 7 x 7 pooled over older buffer data (#41d)
    "conv_dense_8x8":     ("Conv_Dense", 2, 8, 8, 4, 4, 4),              # flat Dense input after a strided conv
    "conv_dense_16x14":   ("Conv_Dense", 2, 16, 14, 4, 4, 4),
}
OVERRIDE_FREE = {"single_7x7"}


@pytest.mark.parametrize("case", list(CASES))
def test_stride2(case, request, monkeypatch):
    layer, layers, width, height, channels, filters, glb_psum = CASES[case]
    monkeypatch.setenv("STRIDE_ENABLED", "1")          # parameters_FPGA.vh and OpenEyeParameters of the testbench
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OUTPUT_SIZE", "10")            # the Dense layer of Conv_Dense
    if case not in OVERRIDE_FREE:
        monkeypatch.setenv("OPENEYE_ALLOW_UNSUPPORTED", "1")
    else:
        monkeypatch.delenv("OPENEYE_ALLOW_UNSUPPORTED", raising=False)
    monkeypatch.setattr(conv, "STRIDE", 2)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", glb_psum)
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=channels, request=request, input_height=height,
                         quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=layers)
