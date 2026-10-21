"""Bug #19b probe: per PE weight pipeline, wraps of first_spad_addr_o (63 -> 0 without compute) and the largest
first/second SPad write addresses. Dump to SPAD2_DUMP (json)."""
import json
import os

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly

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
    hs = []
    find(dut.OpenEye_Parallel, "wght_data_handler", hs)
    st = {"pes": len(hs), "first_wraps": 0, "pes_with_wrap": 0, "first_max": 0, "second_max": 0, "second_ge_96": 0}
    prev = [None] * len(hs)
    wrapped = [False] * len(hs)

    async def monitor():
        while True:
            await RisingEdge(dut.clk_i)
            await ReadOnly()
            for i, h in enumerate(hs):
                try:
                    a1 = int(h.first_spad_addr_o.value)
                    a2 = int(h.second_spad_addr_o.value)
                    cd = int(h.compute_delay.value)
                except ValueError:
                    continue
                st["first_max"] = max(st["first_max"], a1)
                st["second_max"] = max(st["second_max"], a2)
                st["second_ge_96"] += a2 >= 96
                if prev[i] is not None and prev[i] == (1 << len(h.first_spad_addr_o)) - 1 and a1 == 0 and not cd:
                    st["first_wraps"] += 1
                    wrapped[i] = True
                prev[i] = a1

    cocotb.start_soon(monitor())
    try:
        await tb.start_test_fpga.func(dut)
    finally:
        st["pes_with_wrap"] = sum(wrapped)
        with open(os.environ["SPAD2_DUMP"], "w") as f:
            json.dump(st, f)
