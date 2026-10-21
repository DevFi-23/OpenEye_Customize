"""Largest data_pipeline_wght.first_spad_words_o over all PEs during any test (wraps OpenEye_FPGA_tb)."""
import json
import os

import cocotb
from cocotb.triggers import ClockCycles

import OpenEye_FPGA_tb as tb


def find(handle, name, out, depth=0):
    if depth > 12:
        return
    try:
        children = list(handle)
    except TypeError:
        return
    for child in children:
        if child._name == name:
            out.append(child)
        else:
            try:
                list(child)
            except TypeError:
                continue
            find(child, name, out, depth + 1)


@cocotb.test()
async def probe_test(dut):
    handlers = []
    find(dut.OpenEye_Parallel, "wght_data_handler", handlers)
    stats = {"pes": len(handlers), "max": 0, "samples_ge_32": 0}

    async def monitor():
        while True:
            await ClockCycles(dut.clk_i, 4)
            for h in handlers:
                try:
                    v = int(h.first_spad_words_o.value)
                except ValueError:
                    continue
                stats["max"] = max(stats["max"], v)
                stats["samples_ge_32"] += v >= 32

    cocotb.start_soon(monitor())
    try:
        await tb.start_test_fpga.func(dut)
    finally:
        with open(os.environ["SPAD_PROBE_OUT"], "w") as f:
            json.dump(stats, f)
