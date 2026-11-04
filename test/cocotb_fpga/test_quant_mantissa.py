# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""The full 25-bit mantissa of the requantization multiplier (bug #38).

Every quantization entry carries offset 8, exponent 7 and mantissa 25 bits (conv_mapper.write_quant_and_offset), and the
quantizers multiply with a 25-bit signed mantissa (quantization_unit.v), but OpenEye_FPGA.v took only the low 8 bits of
the mantissa field (its slice used OFFSET_WIDTH): a multiplier >= 256 lost its upper bits. The toolchain therefore kept
every mantissa below 256 (onnx2model.MANT_BITS = 8). Here every Conv/Dense requantizes with a 17- or 24-bit mantissa
(test hooks OPENEYE_QUANT_MANT / OPENEYE_QUANT_SHIFT, data_create); the testbench reference uses the whole value and checks
the iact buffer after every layer and the final outputs.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_quant_mantissa.py
"""
import pytest

import test_conv_const as conv

# case: (LAYER, layers, width, height, channels, filters, mantissa, shift)
CASES = {
    "mant17_conv_stack":   ("Convolution_Stack", 2, 8, 4, 4, 4, 127909, 23),       # 0x1F3A5: M = 0.0152
    "mant24_conv_stack":   ("Convolution_Stack", 2, 8, 4, 4, 4, 11920113, 29),     # 0xB5E2F1: M = 0.0222
    "mant24_dense_chain":  ("DENSE_CHAIN_64_32_10", 2, 8, 1, 1, 4, 11920113, 29),
}


@pytest.mark.parametrize("case", list(CASES))
def test_quant_mantissa(case, request, monkeypatch):
    layer, layers, width, height, channels, filters, mant, shift = CASES[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_QUANT_MANT", str(mant))
    monkeypatch.setenv("OPENEYE_QUANT_SHIFT", str(shift))
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=channels, request=request, input_height=height,
                         quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=layers)
