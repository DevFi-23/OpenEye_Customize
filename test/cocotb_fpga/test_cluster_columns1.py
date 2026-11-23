# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Convolutions on hardware built with CLUSTER_COLUMNS = 1 (bug #51, fixed 2026-11-22).

With one cluster column and several kernel groups per calculation (CR 4 / 8, NUM_GLB_PSUM 4), the iact converter of
OpenEye_FPGA.v started the row sweep of every kernel group after the first at x = iact_x_per_cluster instead of 0, so
the second kernel group was computed from the wrong activations and half the feature maps came out wrong (4 of 8,
8 of 16). Upstream 12340ab removed the same branch. At 2 cluster columns the branch never acted (8,208 layers scanned),
so the other suites did not see it. The "cr2" cases have one kernel group per row and were right before the fix.
doc/experiments/2026-11-21_upstream_12340ab_review.md section 4, doc/experiments/2026-11-22_bug50_51.md.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_cluster_columns1.py
"""
import pytest

import test_conv_const as conv

# id: (LAYER, layers, CLUSTER_ROWS, input width, input height, input channels, filters, NUM_GLB_PSUM)
CASES = {
    "cr4_4x4_c4_f8":   ("Convolution_Single", 1, 4, 4, 4, 4, 8, 4),     # 2 kernel groups; before the fix 4 of 8 wrong
    "cr4_6x2_c1_f16":  ("Convolution_Single", 1, 4, 6, 2, 1, 16, 4),    # 1 input channel; before 8 of 16 wrong
    "cr4_4x8_c16_f8":  ("Convolution_Single", 1, 4, 4, 8, 16, 8, 4),    # 16 channels; before 4 of 8 wrong
    "cr8_8x4_c4_f16":  ("Convolution_Single", 1, 8, 8, 4, 4, 16, 4),    # 4 kernel groups at CR 8
    "cr2_8x4_c4_f16":  ("Convolution_Single", 1, 2, 8, 4, 4, 16, 4),    # one kernel group per row: right before too
    "cr2_4x4_c4_f8":   ("Convolution_Single", 1, 2, 4, 4, 4, 8, 4),
}


@pytest.mark.parametrize("case", list(CASES))
def test_cluster_columns1(case, request, monkeypatch):
    layer, layers, cluster_rows, width, height, channels, filters, glb_psum = CASES[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.delenv("OPENEYE_ALLOW_UNSUPPORTED", raising=False)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", glb_psum)
    conv._run_conv_const(layer, 8, cluster_rows, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, random_data=True, expect_layers=layers, cluster_columns=1)
