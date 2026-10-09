# This file is part of the OpenEye project.
# © Fachhochschule Dortmund – University of Applied Sciences and Arts (until 2025), Universität Duisburg-Essen (since 2025).
# SPDX-License-Identifier: SHL-2.1
# For more details, see the LICENSE file in the root directory of this project.

"""Latency and bandwidth baseline of single convolution layers.

Every case runs one Convolution_Single layer (ramp activations, 4 input
channels, 3x3 kernel, CLUSTER_ROWS=2, CLUSTER_COLUMNS=2) with the cycle and
DMA profiler enabled (OPENEYE_PROFILE=1, see
rtl_test_utils.profile_dma_phases). The result check of the testbench still
applies, so a profile is only meaningful for a passing case.

Each case writes test/.temp/<test id>/profile.json. Summarise with:

    python -m open_eye.profile_report test/.temp/*test_profile*/profile.json

Usage:
    pytest test_profile.py -v
"""

import pytest

import test_conv_const as conv

# id: (width, height, filters, QUANT_AMOUNT, DMA_BITWIDTH)
CASES = {
    "8x1_f4_q1024_dma64": (8, 1, 4, 1024, 64),   # geometry of test_conv_const
    "8x1_f4_q32_dma64":   (8, 1, 4, 32, 64),
    "16x3_f4_q32_dma64":  (16, 3, 4, 32, 64),
    "32x3_f4_q32_dma64":  (32, 3, 4, 32, 64),
    "32x3_f16_q32_dma64": (32, 3, 16, 32, 64),
    "32x3_f4_q32_dma32":  (32, 3, 4, 32, 32),
}


@pytest.mark.parametrize("case", list(CASES))
def test_profile_conv(case, request, monkeypatch):
    width, height, filters, quant_amount, dma_bitwidth = CASES[case]
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=4,
                         request=request, input_height=height, ramp_iacts=True,
                         asymmetric_kernel=True, quant_amount=quant_amount,
                         dma_bitwidth=dma_bitwidth)
