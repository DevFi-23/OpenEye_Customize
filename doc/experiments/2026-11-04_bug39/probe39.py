"""probe39 (cocotb module, run through run39.py): the unmodified OpenEye_FPGA_tb plus one monitor, observation only, no
RTL file changed. B39_LOG=<json>: every change of the weight-pass bookkeeping of OpenEye_FPGA.v (iact_cycle_count,
single_iteration, current_cycle, iact_channels_counter) and every jump of wght_buffer_rd_addr (any step other than +1),
with the simulation cycle and the main FSM state. B39_WDATA=<json>: every weight buffer read (wght_buffer_en_r): read
address, whether the row read out is all zero, and the weight-pass counter. B39_ZERO_FILTERS=a:b: the weights of filters
a ... b-1 of layer 0 set to 0 in DRAM before the stream and the reference are built (the reference stays exact: their
outputs must be the bias)."""
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


async def watch_wdata(dut, path):
    reads, cycle, pending = [], 0, []
    while True:
        await RisingEdge(dut.clk_i)
        cycle += 1
        try:
            en = int(dut.wght_buffer_en_r.value)
            addr = int(dut.wght_buffer_rd_addr.value)
            data = dut.wght_buffer_data_r.value
            data_zero = data.is_resolvable and int(data) == 0
            data_x = not data.is_resolvable
            passno = int(dut.iact_cycle_count.value)
        except ValueError:
            continue
        # the buffer has a read latency: log the address now and the data a few clocks later
        pending.append((cycle, en, addr, passno))
        if len(pending) > 3:
            c, e, a, p = pending.pop(0)
            if e:
                reads.append({"cycle": c, "addr": a, "pass": p, "data_now_zero": data_zero, "data_now_x": data_x})
                if len(reads) % 50 == 0:
                    json.dump(reads, open(path, "w"))


def install_zero_filters():
    spec = os.environ.get("B39_ZERO_FILTERS")
    if not spec:
        return
    a, b = (int(v) for v in spec.split(":"))
    orig = tb.channel_pad.fill_padding_channels

    def fill_padding_channels(model, dram):
        n = orig(model, dram)
        for c in range(len(dram.weights[0])):
            for f in range(a, min(b, len(dram.weights[0][c]))):
                k = dram.weights[0][c][f]
                dram.weights[0][c][f] = [[0] * len(row) for row in k]
        import logging
        logging.getLogger("cocotb").info("B39_ZERO_FILTERS: weights of filters %d ... %d set to 0", a, b - 1)
        return n
    tb.channel_pad.fill_padding_channels = fill_padding_channels


@cocotb.test()
async def probe_test(dut):
    install_zero_filters()
    path = os.environ.get("B39_LOG")
    if path:
        cocotb.start_soon(watch(dut, path))
    if os.environ.get("B39_WDATA"):
        cocotb.start_soon(watch_wdata(dut, os.environ["B39_WDATA"]))
    await tb.start_test_fpga.func(dut)
