# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Bias once per filter on the RTL (BIAS_PER_FILTER_EN=1, doc/experiments/2026-11-17_bias_per_filter.md).

Hardware built with BIAS_PER_FILTER_EN=1 (the default since 2026-11-17) lets a Conv layer send one bias per filter;
psum_pipeline.v stores them in a table and rewrites the psum buffer the old per-output stream filled, while the main
FSM goes on. Every case below runs
on such hardware with random data and biases (seed 1) and must pass the testbench's checks (every iact buffer between
layers, the final values against the reference); the log must show the per-filter stream for every Conv layer it is
meant for. test/test_bias_per_filter.py checks the buffer word by word against a model of the old GET_BIAS.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_bias_per_filter.py
"""
import os
import re

import pytest

import test_conv_const as conv
import test_real_model

# id: (LAYER, layers, input width, input height, input channels, filters, NUM_GLB_PSUM, CLUSTER_ROWS, SPARSITY_EN)
CASES = {
    "single_c4_f16":        ("Convolution_Single", 1, 8, 4, 4, 16, 4, 2, 1),
    "single_c4_f4":         ("Convolution_Single", 1, 8, 4, 4, 4, 4, 2, 1),    # 4 filters: kernel groups
    "single_c4_f16_cr1":    ("Convolution_Single", 1, 8, 4, 4, 16, 4, 1, 1),
    "single_c4_f16_cr4":    ("Convolution_Single", 1, 8, 4, 4, 16, 4, 4, 1),
    "stack_c4_f16":         ("Convolution_Stack", 2, 8, 4, 4, 16, 4, 2, 1),
    "stack_c4_f4_glbp2":    ("Convolution_Stack", 2, 8, 4, 4, 4, 2, 2, 1),
    "conv_pool_conv_c2_f8": ("Conv_Pool_Conv", 3, 8, 4, 2, 8, 4, 2, 1),
    "single_c4_f16_dense":  ("Convolution_Single", 1, 8, 4, 4, 16, 4, 2, 0),   # dense hardware
    "stack_c4_f16_dense":   ("Convolution_Stack", 2, 8, 4, 4, 16, 4, 2, 0),
}

# The old hardware (BIAS_PER_FILTER_EN=0, the whole bias map; the default until 2026-11-17) stays covered.
OFF_CASES = {
    "single_c4_f16_off":    ("Convolution_Single", 1, 8, 4, 4, 16, 4, 2, 1),
    "conv_pool_conv_c2_f8_off": ("Conv_Pool_Conv", 3, 8, 4, 2, 8, 4, 2, 1),
}


def bias_lines(request):
    nodeid = request.node.nodeid.replace("::", "_").replace("/", "_").replace("[", "_").replace("]", "_")
    log = os.path.join(conv.test_dir, ".temp", nodeid, "cocotb_sim.log")
    text = open(log, errors="replace").read()
    return re.findall(r"bias per filter (on|off)", text)


@pytest.mark.parametrize("case", list(CASES))
def test_bias_per_filter(case, request, monkeypatch):
    layer, layers, width, height, channels, filters, glb_psum, rows, sparse = CASES[case]
    monkeypatch.setenv("BIAS_PER_FILTER_EN", "1")
    monkeypatch.setenv("SPARSITY_EN", str(sparse))
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", glb_psum)
    conv._run_conv_const(layer, 8, rows, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, random_data=True, expect_layers=layers)
    assert "on" in bias_lines(request), "no Conv layer used the per-filter bias stream"


def test_bias_per_filter_trained_mnist(request, monkeypatch):
    """The trained MNIST net, image 0 (real biases): every buffer check and the Dense psums bit-exact."""
    monkeypatch.setenv("BIAS_PER_FILTER_EN", "1")
    test_real_model.run_trained(test_real_model.CHECKPOINT, 0, request, monkeypatch)
    assert bias_lines(request).count("on") == 3, "Conv1, Conv2 and Conv3 must use the per-filter bias stream"


@pytest.mark.parametrize("case", list(OFF_CASES))
def test_bias_per_filter_off(case, request, monkeypatch):
    layer, layers, width, height, channels, filters, glb_psum, rows, sparse = OFF_CASES[case]
    monkeypatch.setenv("BIAS_PER_FILTER_EN", "0")
    monkeypatch.setenv("SPARSITY_EN", str(sparse))
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", glb_psum)
    conv._run_conv_const(layer, 8, rows, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, random_data=True, expect_layers=layers)
    assert "on" not in bias_lines(request), "hardware without the bias table used the per-filter stream"
