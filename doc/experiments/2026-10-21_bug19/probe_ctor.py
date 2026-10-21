"""Bug #19 probe: in every iact_stream_constructor, record each activation pair position seen in WRITE_TO_MEMORY
(channel_trans_cycle == 0): pass number, position p in the pass, x_pos_in_w_cycle, x_range_lower_bound, x_start,
the pair on storage_i, and whether it is written (enable_write_to_storage one cycle later). Dump to CTOR_DUMP (json)."""
import json
import os

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly

import OpenEye_FPGA_tb as tb

WRITE_TO_MEMORY = 2


@cocotb.test()
async def probe_test(dut):
    ctors = {}
    for i in range(2):
        for j in range(2):
            ctors[f"{i}{j}"] = dut.IACT_CONVERTER_X[i].IACT_CONVERTER_Y[j].iact_stream_constructor
    rec = {k: [] for k in ctors}
    state = {k: {"in_wtm": False, "pass": -1, "p": 0, "pending": None} for k in ctors}

    async def monitor():
        while True:
            await RisingEdge(dut.clk_i)
            await ReadOnly()
            for k, c in ctors.items():
                st = state[k]
                try:
                    fsm = int(c.fsm_current_state.value)
                    ctc = int(c.channel_trans_cycle.value)
                    xpos = int(c.x_pos_in_w_cycle.value)
                    lb = int(c.x_range_lower_bound.value)
                    xs = int(c.x_start.value)
                    ews = int(c.enable_write_to_storage.value)
                    data = int(c.storage_i.value) & 0xFFFF
                except ValueError:
                    continue
                if st["pending"] is not None:
                    st["pending"]["written"] = ews
                    rec[k].append(st["pending"])
                    st["pending"] = None
                if fsm == WRITE_TO_MEMORY:
                    if not st["in_wtm"]:
                        st["in_wtm"], st["pass"], st["p"] = True, st["pass"] + 1, 0
                    if ctc == 0:
                        st["pending"] = {"pass": st["pass"], "p": st["p"], "x_pos": xpos, "lb": lb, "x_start": xs,
                                         "pair": [data & 0xFF, data >> 8]}
                        st["p"] += 1
                else:
                    st["in_wtm"] = False

    cocotb.start_soon(monitor())
    try:
        await tb.start_test_fpga.func(dut)
    finally:
        with open(os.environ["CTOR_DUMP"], "w") as f:
            json.dump(rec, f)
