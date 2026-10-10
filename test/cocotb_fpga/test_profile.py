# This file is part of the OpenEye project.
# © Fachhochschule Dortmund – University of Applied Sciences and Arts (until 2025), Universität Duisburg-Essen (since 2025).
# SPDX-License-Identifier: SHL-2.1
# For more details, see the LICENSE file in the root directory of this project.

"""Latency and bandwidth baseline of single convolution layers.

Every case runs one Convolution_Single layer (ramp activations, 3x3 kernel,
CLUSTER_ROWS=2, CLUSTER_COLUMNS=2) with the cycle and
DMA profiler enabled (OPENEYE_PROFILE=1, see
rtl_test_utils.profile_dma_phases). The result check of the testbench still
applies, so a profile is only meaningful for a passing case.

Each case writes test/.temp/<test id>/profile.json. Summarise with:

    python -m open_eye.profile_report test/.temp/*test_profile*/profile.json

Usage:
    pytest test_profile.py -v
    pytest test_profile.py -v -k "not mnist"     # small layers only
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
