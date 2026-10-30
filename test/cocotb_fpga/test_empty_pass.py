# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Passes in which no PE holds a non-zero activation (bug #31).

A PE starts a pass only with a non-zero activation; OpenEye_FPGA counts a pass and loads the next one when the PE array's
iact ready bus leaves all-ones. Before the fix in PE.v (EMPTY_PASS), a pass with no non-zero activation in any PE
started nothing, the next pass was never loaded and every later pass of the layer kept the bias. Random test data never
has such a pass (DRAMContents replaces every 0 by +-1); real data does (zeros after ReLU, the background of an image).
OPENEYE_ZERO_BLOCK sets a block of the layer-0 input to 0; the testbench reference is computed from the same data.
doc/experiments/2026-10-30_bug31_fix.md.

Usage (from the repository root; under a minute per conv case, a few minutes for the Dense case):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_empty_pass.py
"""
import pytest

import test_conv_const as conv


# id: (LAYER, width, height, input channels, filters, zeroed block)
CASES = {
    # 3x3 conv: the window of output line 0 (input lines -1, 0, 1) is all zero: the first pass is empty
    "conv_first_pass": ("Convolution_Single", 8, 4, 4, 4, "y:0:2"),
    # input lines 3..5 zero: the pass of output line 4 is empty, the later ones were lost
    "conv_middle_pass": ("Convolution_Single", 8, 8, 4, 4, "y:3:6"),
    # Dense 1024 -> 10, inputs 256..511 zero: the passes of that block are empty (bug #33)
    "dense_zero_block": ("DENSE_CHAIN_1024_10", 8, 1, 1, 4, "k:256:512"),
}


@pytest.mark.parametrize("case", list(CASES.values()), ids=list(CASES))
def test_empty_pass(case, request, monkeypatch):
    layer, width, height, channels, filters, zeros = case
    monkeypatch.setenv("OPENEYE_ZERO_BLOCK", zeros)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=1)
