"""Bug #49 probe (cocotb module, run through test_probe49.py): the unmodified OpenEye_FPGA_tb, with every iact buffer
check (rtl_test_utils.compare_iact_storage) also dumped to $P49_OUT/check_<n>.json: the layer whose input it is, the
reference image (dram.fmap of the previous layer), the expected buffer words, and the whole iact buffer of the DUT
(both halves of every cell) with the offset of the half the check reads. The main FSM state and the pooling state are
sampled every cycle while a pooling layer runs ($P49_OUT/fsm.json). Nothing of the toolchain or the RTL is modified."""
import json
import os

import cocotb
import numpy as np
from cocotb.triggers import RisingEdge

import OpenEye_FPGA_tb as tb
from open_eye import rtl_test_utils as rtu

OUT = os.environ.get("P49_OUT", "p49_out")
os.makedirs(OUT, exist_ok=True)
_compare = rtu.compare_iact_storage
_count = [0]


def _mem(dut, cell):
    mem = dut.BUFFER_A[cell].iact_layer_buffer.impl.mem
    words = []
    for i in range(len(mem)):
        w = rtu._ram_word(mem[i])
        words.append(-1 if w is None else int(w))
    return words


def compare_iact_storage(ptp, dut, iact_ref, oep, layer_params, valid_values=None):
    ok = _compare(ptp, dut, iact_ref, oep, layer_params, valid_values=valid_values)
    n = _count[0]
    _count[0] += 1
    try:
        expected = rtu._to_ram_format(rtu._iact_buffer_words(oep, layer_params, iact_ref), oep, layer_params)
        data = {
            "check": n, "ok": bool(ok), "layer_name": str(getattr(layer_params, "layer_name", "?")),
            "iact_size_x": getattr(layer_params, "iact_size_x", None),
            "iact_size_y": getattr(layer_params, "iact_size_y", None),
            "channels": getattr(layer_params, "channels", None),
            "used_channels": getattr(layer_params, "used_channels", None),
            "IACT_RAM_CELLS": oep.IACT_RAM_CELLS,
            "half_offset": int(rtu.iact_half_offset(dut, oep)),
            "iact_ref": np.array(iact_ref).tolist(),
            "expected": [int(w) for w in expected] if expected is not None else None,
            "dut": [_mem(dut, c) for c in range(oep.IACT_RAM_CELLS)],
        }
        # Position-coded images through the same layout code: which (channel, x, y) every expected byte holds.
        ref = np.array(iact_ref)
        if ref.ndim == 3 and expected is not None:
            C, X, Y = ref.shape
            code_c = np.broadcast_to(np.arange(C)[:, None, None], ref.shape).copy()
            code_x = np.broadcast_to(np.arange(X)[None, :, None], ref.shape).copy()
            code_y = np.broadcast_to(np.arange(Y)[None, None, :], ref.shape).copy()
            for name, code in (("code_c", code_c), ("code_x", code_x), ("code_y", code_y)):
                words = rtu._to_ram_format(rtu._iact_buffer_words(oep, layer_params, code), oep, layer_params)
                data[name] = [int(w) for w in words]
        with open(os.path.join(OUT, f"check_{n}.json"), "w") as f:
            json.dump(data, f)
        tb.logger.info("P49: dumped check %d (%s, ok=%s)", n, data["layer_name"], ok)
    except Exception as exc:                      # the probe must not change the run
        tb.logger.warning("P49: dump of check %d failed: %r", n, exc)
    return ok


rtu.compare_iact_storage = compare_iact_storage


async def sample_fsm(dut):
    """Main FSM state every cycle (run-length encoded), to see the pooling phases."""
    runs = []
    last = None
    start = 0
    cycle = 0
    while True:
        await RisingEdge(dut.clk_i)
        try:
            state = int(dut.fsm_current_state.value)
        except ValueError:
            state = -1
        if state != last:
            if last is not None:
                runs.append((start, cycle - start, last))
                if len(runs) % 200 == 0:
                    with open(os.path.join(OUT, "fsm.json"), "w") as f:
                        json.dump(runs, f)
            last, start = state, cycle
        cycle += 1


@cocotb.test()
async def probe_test(dut):
    cocotb.start_soon(sample_fsm(dut))
    await tb.start_test_fpga.func(dut)


async def watch_ready(dut):
    """P49_READY=1: at every collection start (results_ready of psum_pipeline rising in CALCULATE_PSUM) the
    psum_ready_o_reg bits of every GLB and the chain-start bit (router_mode_psum bit 2) of every GLB; written to
    $P49_OUT/ready.json as (cycle, ready bits, chain-start bits), bit 0 = GLB 0."""
    p = dut.psum_pipeline_inst
    starts = READY_STARTS
    last = 0
    cycle = 0
    n_glb = len(p.psum_ready_o_reg.value)
    rm = int(os.environ.get("P49_ROUTER_MODES", "3"))
    while True:
        await RisingEdge(dut.clk_i)
        cycle += 1
        try:
            rr = int(p.results_ready.value)
            st = int(p.fsm_psum_current_state.value)
        except ValueError:
            continue
        if rr and not last and st == 2:
            ready = p.psum_ready_o_reg.value.binstr[::-1]
            modes = p.router_mode_psum.value.binstr[::-1]
            chain = "".join(modes[g * rm + 2] for g in range(n_glb))
            starts.append((cycle, ready, chain))
            if len(starts) % 100 == 0:
                with open(os.path.join(OUT, "ready.json"), "w") as f:
                    json.dump(starts, f)
        last = rr


READY_STARTS = []


@cocotb.test()
async def probe_ready_test(dut):
    if os.environ.get("P49_READY"):
        cocotb.start_soon(watch_ready(dut))
    cocotb.start_soon(sample_fsm(dut))
    try:
        await tb.start_test_fpga.func(dut)
    finally:
        with open(os.path.join(OUT, "ready.json"), "w") as f:
            json.dump(READY_STARTS, f)
