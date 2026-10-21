"""Bug #19b probe: track the weight-buffer write and read pointers (BUFFER_WIDTH_WGHT bits) of the unmodified
OpenEye_FPGA: number of writes, highest write address, wraps of the read pointer, total read steps. Dump to WBUF_DUMP."""
import json
import os

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly

import OpenEye_FPGA_tb as tb


@cocotb.test()
async def probe_test(dut):
    st = {"wr_max": 0, "wr_wraps": 0, "rd_max": 0, "rd_wraps": 0, "rd_steps": 0, "wr_steps": 0}

    async def monitor():
        prev_rd = prev_wr = None
        while True:
            await RisingEdge(dut.clk_i)
            await ReadOnly()
            try:
                rd = int(dut.wght_buffer_rd_addr.value)
                wr = int(dut.wght_buffer_wr_addr.value)
            except ValueError:
                continue
            if prev_rd is not None and rd != prev_rd:
                if rd == prev_rd + 1:
                    st["rd_steps"] += 1
                elif rd == 0 and prev_rd == (1 << len(dut.wght_buffer_rd_addr)) - 1:
                    st["rd_steps"] += 1
                    st["rd_wraps"] += 1
            if prev_wr is not None and wr != prev_wr:
                if wr == prev_wr + 1:
                    st["wr_steps"] += 1
                elif wr == 0 and prev_wr == (1 << len(dut.wght_buffer_wr_addr)) - 1:
                    st["wr_steps"] += 1
                    st["wr_wraps"] += 1
            st["rd_max"] = max(st["rd_max"], rd)
            st["wr_max"] = max(st["wr_max"], wr)
            prev_rd, prev_wr = rd, wr

    cocotb.start_soon(monitor())
    try:
        await tb.start_test_fpga.func(dut)
    finally:
        st["width"] = len(dut.wght_buffer_rd_addr)
        with open(os.environ["WBUF_DUMP"], "w") as f:
            json.dump(st, f)
