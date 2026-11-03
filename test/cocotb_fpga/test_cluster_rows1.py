# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""One cluster row (CLUSTER_ROWS = 1): the three bugs of the failing Table 3 rows (doc/experiments/2026-11-03_table3_cr1.md).

#29  the weight staging buffer (2^BUFFER_WIDTH_WGHT rows) overflowed silently: Dense 1568 -> 32 at CLUSTER_ROWS 1,
     NUM_GLB_WGHT 3 needs 4,224 rows (12 bit: 4,096). BUFFER_WIDTH_WGHT is 13 since the fix, and the toolchain refuses
     a layer that does not fit (layer_parameters.check_wght_buffer).
#28  at CLUSTER_ROWS 1 the psum collection waited only for the even PE column of each GLB pair, so with NUM_GLB_PSUM 2
     it could start while column 1 was still computing; one pixel per pass came out wrong, depending on the data
     (zero skipping). The paper network shows it in conv2 (pixel x = 7, y = 1 with seed 1).
#36  the read-out of a final Dense layer dropped the results of cluster column 1 at CLUSTER_ROWS 1, NUM_GLB_PSUM 2 (the
     read-out register was 80 bits, column 1 needs bits 64-83): Dense 32 -> 10 read 0 for outputs 6-9.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_cluster_rows1.py
"""
import pytest

import test_conv_const as conv

# case: (LAYER, layers, input width, input height, NUM_GLB_PSUM, NUM_GLB_WGHT)
CASES = {
    "dense32_10_x2":        ("DENSE_CHAIN_32_10", 1, 8, 1, 2, 3),          # #36 alone, about 20 s
    "dense1568_32_10_x4":   ("DENSE_CHAIN_1568_32_10", 2, 8, 1, 4, 3),     # #29: 4,224 weight rows
    "dense1568_32_10_x2":   ("DENSE_CHAIN_1568_32_10", 2, 8, 1, 2, 3),     # #29 and #36
    "paper_x2_y3":          ("PAPER_MNIST", 7, 8, 28, 2, 3),               # #28, #29, #36: Table 3 row CR 1 X 2 Y 3
}


@pytest.mark.parametrize("case", list(CASES))
def test_cluster_rows1(case, request, monkeypatch):
    layer, layers, width, height, glb_psum, glb_wght = CASES[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", glb_psum)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", glb_wght)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    conv._run_conv_const(layer, 8, 1, num_glb_iact=1, input_channels=1, request=request, input_height=height,
                         quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=layers)
