# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Layer chains with NUM_GLB_PSUM = 2 (two psum GLBs per cluster, "PEs X-axis" 2 in the OpenEye paper) (bug #25).

A convolution that writes its output back into the iact buffer reads two pixels per cycle; RECEIVE_PSUMS_TO_IACT has to
write them as groups of 4 channels per pixel, the layout the next layer reads. Before the fix the groups held 2
channels and the row padding was cut in the wrong place (doc/experiments/2026-10-26_bug25_glb_psum2.md). The testbench
checks the iact buffer after every layer whose next layer has a known layout, and the final outputs. The Dense chain
with two GLBs is in test_dense_chain.py, the paper's network in test_profile.py::test_profile_paper (x2 cases).

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_glb_psum2.py
"""
import pytest

import test_conv_const as conv

# case: (LAYER, layers, input width, input height, input channels, filters, max pooling)
CASES = {
    "conv_single":        ("Convolution_Single", 1, 8, 4, 4, 4, False),     # read out directly: no write-back
    "conv_stack":         ("Convolution_Stack", 2, 8, 4, 4, 4, False),
    "conv_stack_c16":     ("Convolution_Stack", 2, 8, 8, 16, 16, False),    # four channel groups
    "conv_stack_w14":     ("Convolution_Stack", 2, 14, 4, 4, 8, False),     # row read as 16 pixels: padding dropped
    "conv_pool_conv_w8":  ("Conv_Pool_Conv", 3, 8, 4, 2, 8, True),
    "conv_pool_conv_w6":  ("Conv_Pool_Conv", 3, 6, 4, 2, 8, True),          # odd pooled width
    # 16 x 16: an 8 x 8 input pools 4 x 4 -> 2 x 2 in the second pooling layer, which fails with 4 GLBs as well (bug #27)
    "conv_pool_conv_x2":  ("Conv_Pool_Conv_Pool_Conv", 5, 16, 16, 2, 8, True),
}


@pytest.mark.parametrize("case", list(CASES))
def test_glb_psum2(case, request, monkeypatch):
    layer, layers, width, height, channels, filters, max_pooling = CASES[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", 2)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    if max_pooling:
        real_run = conv.cocotb_test.simulator.run

        def run(**kw):
            # as test_pooling.py: max pooling, and the decoded outputs checked instead of the raw DMA file (which
            # holds zeros in lanes the hardware computes from padding when the width is not a multiple of the lanes)
            kw["extra_env"] = dict(kw["extra_env"], LOGGER_LEVEL="20")
            kw["parameters"] = {"MAX_POOLING": 1, "AVERAGE_POOLING": 0}
            return real_run(**kw)
        monkeypatch.setattr(conv.cocotb_test.simulator, "run", run)
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=channels, request=request, input_height=height,
                         quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=layers)
