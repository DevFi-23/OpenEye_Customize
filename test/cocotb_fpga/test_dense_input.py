# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Dense layers with 4096 or more inputs (bug #50, fixed in Python 2026-11-22).

A Dense layer sets the 12-bit iact_x_add_up register to its input count K. The FC write path of
iact_stream_constructor.v compares its input-pair counters with it; below 4096 inputs they never reach it, from 4096 on
the field wrapped (K mod 4096) and every output came out wrong, whether the input came from the host or from the
write-back of the layer before. Since 2026-11-22 the Dense mapper sends min(K, 4095) (dense_add_up_register) and
check_dense_input refuses only the layers whose pair counters would reach that bound. Each case checks the final
outputs against the integer reference (random data, seed 1). doc/experiments/2026-11-22_bug50_51.md.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_dense_input.py         # about 5 min per case
"""
import pytest

import test_conv_const as conv

# case: (LAYER, INPUT_SIZE_X, input height, input channels, NUM_FILTERS, CLUSTER_ROWS, layers); 10 outputs,
# NUM_GLB_PSUM 4, 2 cluster columns
CASES = {
    "k4096_cr2":        ("GEMM", 4096, 1, 1, 1, 2, 1),       # the first K that was wrong
    "k6001_cr2":        ("GEMM", 6001, 1, 1, 1, 2, 1),       # odd K
    "k8136_cr2":        ("GEMM", 8136, 1, 1, 1, 2, 1),       # the limit at 2 x 2 clusters (113 passes of 72)
    "k4096_cr1":        ("GEMM", 4096, 1, 1, 1, 1, 1),
    "k4096_cr4":        ("GEMM", 4096, 1, 1, 1, 4, 1),
    "conv_flatten4096": ("Conv_Dense", 8, 8, 4, 64, 2, 2),   # Conv 8 x 8 x 4 -> 64, flatten, Dense 4096 -> 10
}


@pytest.mark.parametrize("case", list(CASES))
def test_dense_input(case, request, monkeypatch):
    layer, width, height, channels, filters, cluster_rows, layers = CASES[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OUTPUT_SIZE", "10")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "200000")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", 4)
    conv._run_conv_const(layer, 8, cluster_rows, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, random_data=True, expect_layers=layers)
