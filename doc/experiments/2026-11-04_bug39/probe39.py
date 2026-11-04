"""probe39 (cocotb module, run through run39.py): the unmodified OpenEye_FPGA_tb plus one monitor, observation only, no
RTL file changed. B39_LOG=<json>: every change of the weight-pass bookkeeping of OpenEye_FPGA.v (iact_cycle_count,
single_iteration, current_cycle, iact_channels_counter) and every jump of wght_buffer_rd_addr (any step other than +1),
with the simulation cycle and the main FSM state."""
import json
import os

import cocotb
from cocotb.triggers import RisingEdge

import OpenEye_FPGA_tb as tb

SIGNALS = ("iact_cycle_count", "single_iteration", "current_cycle", "iact_channels_counter", "fsm_current_state")


async def watch(dut, path):
    log, last, cycle, last_addr = [], {}, 0, None
    while True:
        await RisingEdge(dut.clk_i)
        cycle += 1
        try:
            now = {s: int(getattr(dut, s).value) for s in SIGNALS}
            addr = int(dut.wght_buffer_rd_addr.value)
            ready = int(dut.iact_ready_o_oep_w.value)
        except ValueError:
            continue
        changed = {s: v for s, v in now.items() if last.get(s) != v and s != "fsm_current_state"}
        if changed:
            log.append({"cycle": cycle, "state": now["fsm_current_state"], "ready": ready, "wght_addr": addr, **changed})
        if last_addr is not None and addr not in (last_addr, last_addr + 1):
            log.append({"cycle": cycle, "state": now["fsm_current_state"], "wght_addr_jump": [last_addr, addr],
                        "iact_cycle_count": now["iact_cycle_count"], "current_cycle": now["current_cycle"]})
        if changed or (last_addr is not None and addr not in (last_addr, last_addr + 1)):
            json.dump(log, open(path, "w"))
        last, last_addr = now, addr


@cocotb.test()
async def probe_test(dut):
    path = os.environ.get("B39_LOG")
    if path:
        cocotb.start_soon(watch(dut, path))
    await tb.start_test_fpga.func(dut)
