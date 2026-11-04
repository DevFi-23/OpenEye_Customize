# This file is part of the OpenEye project.
# © Fachhochschule Dortmund – University of Applied Sciences and Arts (until 2025), Universität Duisburg-Essen (since 2025).
# SPDX-License-Identifier: SHL-2.1
# For more details, see the LICENSE file in the root directory of this project.

"""Latency and bandwidth baseline of single convolution layers and of whole models.

test_profile_conv: one Convolution_Single layer (ramp activations, 3x3 kernel,
CLUSTER_ROWS=2, CLUSTER_COLUMNS=2). test_profile_model: a whole net whose
layers are chained on chip (each non-final layer writes its requantized
results back into the iact buffer), random data with a fixed seed
(OPENEYE_SEED) so the cycle counts are reproducible. test_profile_paper: the
network of Table 2 of the OpenEye paper on every configuration of its Table 3
(tools/paper_table3.py runs them and prints the per-layer tables). Both run with the cycle
and DMA profiler enabled (OPENEYE_PROFILE=1, see
rtl_test_utils.profile_dma_phases), which also splits the counters per layer.
The result check of the testbench still applies, so a profile is only
meaningful for a passing case.

Each case writes test/.temp/<test id>/profile.json. Summarise with:

    python -m open_eye.profile_report test/.temp/*test_profile*/profile.json

Usage:
    pytest test_profile.py -v
    pytest test_profile.py -v -k "not mnist"     # small layers only
    pytest test_profile.py -v -k model           # whole models (5-30 min each)
Prefer tools/run_profile.py, which runs the cases in parallel and compares them.
"""

import pytest

import test_conv_const as conv

# id: (width, height, input channels, filters, QUANT_AMOUNT, DMA_BITWIDTH)
CASES = {
    # Small layers (baseline 2026-10-09). Fast: about 15 s each, the q1024 case about 4 min.
    "8x1_f4_q1024_dma64": (8, 1, 4, 4, 1024, 64),   # geometry of test_conv_const
    "8x1_f4_q32_dma64":   (8, 1, 4, 4, 32, 64),
    "16x3_f4_q32_dma64":  (16, 3, 4, 4, 32, 64),
    "32x3_f4_q32_dma64":  (32, 3, 4, 4, 32, 64),
    "32x3_f16_q32_dma64": (32, 3, 4, 16, 32, 64),
    "32x3_f4_q32_dma32":  (32, 3, 4, 4, 32, 32),
    # MNIST-like layers (Phase 0.3, 2026-10-10), scaled to what the RTL and the
    # reference generator currently support: at most 32 filters (64 fails in
    # layer_parameters.read_data_from_layer), 4/8/16/32 input channels with
    # NUM_GLB_IACT=1, and widths without padding columns (7x7 fails the strict
    # DMA reference check, so 8x8 stands in for Conv3). Slow: 4-9 min each.
    #   MNIST Conv1 28x28, 1 -> 32 channels (1 input channel fails on the RTL)
    "mnist1_28x28_c4_f32_q32_dma64": (28, 28, 4, 32, 32, 64),
    #   MNIST Conv2 14x14, 32 -> 64 channels
    "mnist2_14x14_c32_f32_q32_dma64": (14, 14, 32, 32, 32, 64),
    #   MNIST Conv3 7x7, 64 -> 64 channels
    "mnist3_8x8_c32_f32_q32_dma64": (8, 8, 32, 32, 32, 64),
}


@pytest.mark.parametrize("case", list(CASES))
def test_profile_conv(case, request, monkeypatch):
    width, height, channels, filters, quant_amount, dma_bitwidth = CASES[case]
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=channels,
                         request=request, input_height=height, ramp_iacts=True,
                         asymmetric_kernel=True, quant_amount=quant_amount,
                         dma_bitwidth=dma_bitwidth)


# Whole models: id -> (LAYER of data_create.create_layer, input channels, QUANT_AMOUNT).
# The 64-filter layers of MNIST_REAL need QUANT_AMOUNT >= 64. _c1 is the real
# one-channel model: until the RTL fix of bug #17 (2026-11-04) the testbench padded
# it to 2 channels, the second with zero activations (open_eye.channel_pad).
MODEL_CASES = {
    #   Conv 28x28x2->16, MaxPool, Conv 16->16, MaxPool, Conv 7x7 16->16, Dense 784->10 (about 5 min)
    "model_mnist16_c2": ("MNIST", 2, 32),
    #   models/mnist_conv_net.py: Conv 32, MaxPool, Conv 64, MaxPool, Conv 64, FC 3136->10 (about 11 min)
    "model_mnist_real_c2": ("MNIST_REAL", 2, 64),
    #   the same with its real one-channel input (padded to 2 channels before the #17 fix) (about 11 min)
    "model_mnist_real_c1": ("MNIST_REAL", 1, 64),
}


@pytest.mark.parametrize("case", list(MODEL_CASES))
def test_profile_model(case, request, monkeypatch):
    layer, channels, quant_amount = MODEL_CASES[case]
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_SEED", "1")
    # A 64-filter layer computes for about 90,000 cycles in one main FSM state.
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=28, quant_amount=quant_amount, dma_bitwidth=64,
                         random_data=True, expect_layers=6)


# Table 3 of the OpenEye paper (arXiv 2606.01450): the network of its Table 2
# (LAYER=PAPER_MNIST, 7 layers, 28x28x1 input) on every configuration of the
# table: CLUSTER ROWS x PEs X-axis (NUM_GLB_PSUM) x PEs Y-axis (NUM_GLB_WGHT),
# CLUSTER_COLUMNS = 2 as in every runner here. Random data with a fixed seed.
PAPER_CONFIGS = {f"paper_cr{cr}_x{x}_y{y}": (cr, x, y) for y in (3, 4) for x in (2, 4) for cr in (1, 2, 4, 8)}


@pytest.mark.parametrize("case", list(PAPER_CONFIGS))
def test_profile_paper(case, request, monkeypatch):
    cluster_rows, pes_x, pes_y = PAPER_CONFIGS[case]
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    monkeypatch.setenv("OPENEYE_KEEP_GOING", "1")      # time every layer even after a failed buffer check
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", pes_x)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", pes_y)
    conv._run_conv_const("PAPER_MNIST", 8, cluster_rows, num_glb_iact=1, input_channels=1, request=request,
                         input_height=28, quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=7)

