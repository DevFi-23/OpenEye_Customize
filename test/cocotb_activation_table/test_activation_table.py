# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Runner for the activation_table testbench (table activations, doc/experiments/2026-11-02_activation_rtl_design.md).

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_activation_table/test_activation_table.py
"""
import os
import sys

import pytest
import cocotb_test.simulator

from open_eye import hdl_dir, test_dir

tests_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, tests_dir)


# DMA widths 32, 64 (baseline) and 128 bit: 4, 8, 16 banks of 64, 32, 16 entries
@pytest.mark.parametrize("width", [32, 64, 128])
def test_activation_table(width, request):
    nodeid = request.node.nodeid.replace("::", "_").replace("/", "_").replace("[", "_").replace("]", "_")
    target_dir = os.path.join(test_dir, ".temp", nodeid)
    os.makedirs(target_dir, exist_ok=True)
    cocotb_test.simulator.run(
        python_search=[tests_dir],
        verilog_sources=[os.path.join(hdl_dir, "activation_table.v")],
        toplevel="activation_table",
        module="activation_table_tb",
        sim_build=target_dir,
        testcase="test_activation_table",
        parameters={"TABLE_WORD_WIDTH": width},
        force_compile=True,
        simulator="icarus",
        extra_env={"TABLE_WORD_WIDTH": str(width)},
    )
