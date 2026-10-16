"""Bug #14 probe: wraps the unmodified OpenEye_FPGA_tb and records, for every visit of the psum FSM to
PSUM_GET_RESULTS (state 3) and CALCULATE_PSUM (state 2), how the AND chain behind results_ready behaves."""
import json
import os

import cocotb
from cocotb.triggers import RisingEdge

import OpenEye_FPGA_tb as tb

CC, CR, NG, RM = 2, 2, 4, 3


def chain(enable, mode):
    ok = 1
    for cc in range(CC):
        for cr in range(CR):
            for g in range((NG + 1) // 2):
                idx = cc * NG + cr * CC * NG + g * 2
                start = (mode >> (cc * NG * RM + cr * CC * NG * RM + g * RM * 2 + 2)) & 1
                ok &= ((enable >> idx) & 1) | (start == 0 and CR != 1)
    return ok


@cocotb.test()
async def probe_test(dut):
    pp = dut.psum_pipeline_inst
    visits = []

    async def monitor():
        cur = None
        while True:
            await RisingEdge(dut.clk_i)
            try:
                st = int(pp.fsm_psum_current_state.value)
                mode = int(pp.router_mode_psum.value)
                c3 = chain(int(pp.psum_enable_o.value), mode)
                c2 = chain(int(pp.psum_ready_o_reg.value), mode)
                rr = int(pp.results_ready.value)
            except ValueError:
                continue
            if cur is None or cur["state"] != st:
                if cur is not None and cur["state"] in (2, 3):
                    visits.append(cur)
                cur = {"state": st, "cycles": 0, "chain": [], "rr_at_entry": rr}
            if st in (2, 3):
                cur["cycles"] += 1
                cur["chain"].append(c3 if st == 3 else c2)

    cocotb.start_soon(monitor())
    await tb.start_test_fpga.func(dut)
    out = []
    for v in visits:
        ch = v["chain"]
        first = ch.index(1) if 1 in ch else None
        gaps = sum(1 for c in ch[first:] if c == 0) if first is not None else None
        out.append({"state": v["state"], "cycles": v["cycles"], "rr_at_entry": v["rr_at_entry"],
                    "first_chain_1": first, "zero_after_first": gaps})
    with open(os.environ["BUG14_PROBE_OUT"], "w") as f:
        json.dump(out, f, indent=1)
