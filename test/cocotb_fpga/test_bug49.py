# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Bug #49: the psum collection started before an odd PE column was ready at CLUSTER_ROWS >= 2.

The ready condition of CALCULATE_PSUM (psum_pipeline.v, chain_ready_terms) read only the even GLB of each GLB pair; the
fix of bug #28 had added the odd GLB at CLUSTER_ROWS == 1 only. At CR 2 X 2 every GLB starts a psum chain, and when an
odd PE column finished late (its compute time depends on the zeros it skips) its rows handed their psums up out of step:
one output pixel of that column was wrong in many filters. Found with the Table 2 network of the OpenEye paper with
ReLU (the zeros make the columns finish unevenly): Conv2 had 20 of 6,272 values wrong (x = 7, y = 1 and 3), the
testbench saw it only after the pooling (doc/experiments/2026-11-17_bug49.md). Fixed 2026-11-17: the odd GLB of a pair
counts when it starts a chain, at every CLUSTER_ROWS; the testbench now also checks a convolution output that a
pooling layer reads (rtl_test_utils.compare_pooling_input).

The cases are those configurations, sparse hardware, random weights and input (seed 1), every buffer check and the
result must pass.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_bug49.py
"""
import pytest

import test_conv_const as conv

# id: (CLUSTER_ROWS, NUM_GLB_PSUM, NUM_GLB_WGHT)
CASES = {
    "paper_relu_cr2_x2_y3": (2, 2, 3),
    "paper_relu_cr2_x2_y4": (2, 2, 4),
}


@pytest.mark.parametrize("case", list(CASES))
def test_bug49(case, request, monkeypatch):
    cluster_rows, pes_x, pes_y = CASES[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    monkeypatch.setenv("SPARSITY_EN", "1")
    monkeypatch.delenv("OPENEYE_KEEP_GOING", raising=False)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", pes_x)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", pes_y)
    conv._run_conv_const("PAPER_MNIST_RELU", 8, cluster_rows, num_glb_iact=1, input_channels=1, request=request,
                         input_height=28, quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=7)
