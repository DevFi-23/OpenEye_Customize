# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Runner for the quantization_unit testbench (int8 saturation, fused ReLU bound).

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_quantization/test_quantization_unit.py
"""
import os
import sys

import pytest
import cocotb_test.simulator

from open_eye import hdl_dir, test_dir

tests_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, tests_dir)


# psum widths of the design: 20 bit (default DATA_PSUM_BITWIDTH) and 32 bit; mantissa, offset and shift widths as
# instantiated in psum_pipeline.v
@pytest.mark.parametrize("psum_width", [20, 32])
def test_quantization_unit(psum_width, request):
    nodeid = request.node.nodeid.replace("::", "_").replace("/", "_").replace("[", "_").replace("]", "_")
    target_dir = os.path.join(test_dir, ".temp", nodeid)
    os.makedirs(target_dir, exist_ok=True)
    widths = {"PSUM_WIDTH": psum_width, "MANT_WIDTH": 25, "OFFSET_WIDTH": 8, "SHIFT_WIDTH": 7, "OUT_WIDTH": 8}
    cocotb_test.simulator.run(
        python_search=[tests_dir],
        verilog_sources=[os.path.join(hdl_dir, "quantization_unit.v")],
        toplevel="quantization_unit",
        module="quantization_unit_tb",
        sim_build=target_dir,
        testcase="test_quantization_unit",
        parameters=widths,
        force_compile=True,
        simulator="icarus",
        extra_env={k: str(v) for k, v in widths.items()},
    )
