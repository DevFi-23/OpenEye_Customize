"""Bug #31 probe (cocotb module, run through run31.py): the unmodified OpenEye_FPGA_tb plus switches (environment).

  B31_IACT=<file.npy>  layer-0 input [C][X][Y] (a 1-D array for a Dense layer, integers) in place of the random activations of DRAMContents, which
                       never contain a zero (every 0 is replaced by +-1). Channels beyond the file (the bug #17 padding
                       channel) keep what the testbench put there (zeros). The weights stay the project's random ones,
                       the reference is computed from the same DRAM.

The RTL and the testbench are not modified; B31_EMU forces one wire in the simulation only."""
import os

import cocotb
import numpy as np

import OpenEye_FPGA_tb as tb

_orig_fill = tb.channel_pad.fill_padding_channels


def fill_padding_channels(model, dram):
    _orig_fill(model, dram)
    path = os.environ.get("B31_IACT")
    if not path:
        return
    a = np.load(path)
    if a.ndim == 1:                                  # a Dense layer's input
        assert len(dram.fmap[0]) == len(a), "B31_IACT length"
        dram.fmap[0] = [int(v) for v in a]
        tb.logger.info("B31_IACT: Dense input from %s (%d of %d values zero)", os.path.basename(path),
                       int((a == 0).sum()), a.size)
        return
    for c in range(a.shape[0]):
        assert len(dram.fmap[0][c]) == a.shape[1] and len(dram.fmap[0][c][0]) == a.shape[2], "B31_IACT shape"
        dram.fmap[0][c] = [[int(v) for v in row] for row in a[c]]
    tb.logger.info("B31_IACT: layer-0 channels 0..%d from %s (%d of %d values zero)", a.shape[0] - 1,
                   os.path.basename(path), int((a == 0).sum()), a.size)


PE_SIGNALS = ("current_state_computing", "compute_i", "compute_pending", "enable_stream_i", "iact_set", "wght_set",
              "mux_iact_b_o_w", "wght_enable_i", "second_spad_words_iact", "second_spad_words_wght")


async def watch_pes(dut, spec, t1, max_lines=3000):
    """B31_WATCH=<cx>,<cy>,<col>,<row>[;...][@t1]: log the start-of-compute inputs of these PEs whenever one changes."""
    from cocotb.triggers import RisingEdge
    from cocotb.utils import get_sim_time
    pes = []
    for item in spec.split(";"):
        cx, cy, col, row = (int(v) for v in item.split(","))
        pes.append(((cx, cy, col, row), dut.OpenEye_Parallel.gen_x[cx].gen_y[cy].OpenEye_Cluster
                    .pe_cluster.gen_X[col].gen_Y[row].pe))
    last, lines = {}, 0
    while lines < max_lines:
        await RisingEdge(dut.clk_i)
        t = get_sim_time("ns")
        if t > t1:
            return
        for key, pe in pes:
            vals = []
            for name in PE_SIGNALS:
                try:
                    v = getattr(pe, name).value
                    vals.append(str(int(v)) if v.is_resolvable else "x")
                except AttributeError:
                    vals.append("-")
            if last.get(key) != vals:
                last[key] = vals
                tb.logger.info("b31pe t=%.0f pe%s %s", t, key, " ".join(f"{n}={v}" for n, v in zip(PE_SIGNALS, vals)))
                lines += 1


CONV_STATS = {}


async def watch_converter(dut, cx, cy, max_events=40):
    """B31_CONV=<cx>,<cy>: per main FSM state, count what one iact converter writes into its RAM (ram_wr_en: the
    window word storage_i taken in, with the window line current_y) and what it sends to the PE array (iact_enable_o,
    non-zero iact_data_o); log the first non-zero sends. Printed when the test ends (CONV_STATS)."""
    from cocotb.triggers import RisingEdge
    from cocotb.utils import get_sim_time
    cv = dut.IACT_CONVERTER_X[cx].IACT_CONVERTER_Y[cy].iact_stream_constructor

    def num(sig):
        v = sig.value
        return int(v) if v.is_resolvable else -1

    counts, ys = CONV_STATS.setdefault("counts", {}), CONV_STATS.setdefault("writes_per_line", [])
    events = 0
    while True:
        await RisingEdge(dut.clk_i)
        st = num(dut.fsm_current_state)
        if st < 8:
            continue
        c = counts.setdefault(st, {"wr": 0, "wr_nz": 0, "out": 0, "out_nz": 0})
        if num(cv.ram_wr_en) == 1:
            nz = num(cv.storage_i) not in (0, -1)
            c["wr"] += 1
            c["wr_nz"] += nz
            y = num(dut.current_y)
            y = y - 4096 if y > 2047 else y
            if not ys or ys[-1][0] != y:
                ys.append([y, 0, 0])
            ys[-1][1] += 1
            ys[-1][2] += nz
        if num(cv.iact_enable_o) > 0:
            c["out"] += 1
            if num(cv.iact_data_o) not in (0, -1):
                c["out_nz"] += 1
                if events < max_events:
                    events += 1
                    tb.logger.info("b31conv t=%.0f st=%d out data=%x rd_addr=%d", get_sim_time("ns"), st,
                                   num(cv.iact_data_o), num(cv.ram_rd_addr))


async def watch_encoder(dut, cx, cy, max_lines=400):
    """B31_ENC=<cx>,<cy>: from main FSM state 9 on, log every change of the converter's start handshake:
    enable_converter, iact_ready_i, the ENCODE state and whether fsm_enc_cycle is 0, 1 or counting."""
    from cocotb.triggers import RisingEdge
    from cocotb.utils import get_sim_time
    cv = dut.IACT_CONVERTER_X[cx].IACT_CONVERTER_Y[cy].iact_stream_constructor

    def num(sig):
        v = sig.value
        return int(v) if v.is_resolvable else -1

    prev, lines = None, 0
    while lines < max_lines:
        await RisingEdge(dut.clk_i)
        st = num(dut.fsm_current_state)
        if st < 9:
            continue
        cyc = num(cv.fsm_enc_cycle)
        vals = (st, num(cv.enable_converter), num(cv.iact_ready_i), num(cv.fsm_enc_current_state),
                cyc if cyc in (0, 1) else "n")
        if vals != prev:
            prev = vals
            lines += 1
            tb.logger.info("b31enc t=%.0f main=%s enable_converter=%s iact_ready_i=%s enc_state=%s enc_cycle=%s",
                           get_sim_time("ns"), *vals)


async def emulate_empty_pass(dut, wait_cycles=4):
    """B31_EMU=1: emulate a fix of bug #31 in the simulation only. OpenEye_FPGA counts a pass (Process 2) and starts
    the next converter and weight pass (Process 5) when iact_ready_o_oep_w leaves all-ones, which happens two clocks
    after the compute pulse when some PE starts computing; when no PE has a non-zero activation, none starts and the
    rest of the layer is lost. After every compute pulse (compute_i of PE (0,0,0,0), broadcast to all PEs), if the
    ready bus is still all-ones wait_cycles clocks later, force it to 0 for one clock: the pass counts as done."""
    from cocotb.handle import Force, Release
    from cocotb.triggers import RisingEdge
    from cocotb.utils import get_sim_time
    pe = dut.OpenEye_Parallel.gen_x[0].gen_y[0].OpenEye_Cluster.pe_cluster.gen_X[0].gen_Y[0].pe
    full = (1 << len(dut.iact_ready_o_oep_w)) - 1

    def num(sig):
        v = sig.value
        return int(v) if v.is_resolvable else -1

    while True:
        await RisingEdge(dut.clk_i)
        if num(pe.compute_i) != 1 or num(dut.fsm_current_state) < 9:
            continue
        dropped = False
        for _ in range(wait_cycles):
            await RisingEdge(dut.clk_i)
            if num(dut.iact_ready_o_oep_w) != full:
                dropped = True
        if not dropped:
            tb.logger.info("b31emu t=%.0f: no PE started after the compute pulse, iact ready forced low for one clock",
                           get_sim_time("ns"))
            dut.iact_ready_o_oep_w.value = Force(0)
            await RisingEdge(dut.clk_i)
            dut.iact_ready_o_oep_w.value = Release()


@cocotb.test()
async def probe_test(dut):
    tb.channel_pad.fill_padding_channels = fill_padding_channels
    if os.environ.get("B31_WATCH"):
        spec, _, t1 = os.environ["B31_WATCH"].partition("@")
        cocotb.start_soon(watch_pes(dut, spec, float(t1 or 1e12)))
    if os.environ.get("B31_EMU"):
        cocotb.start_soon(emulate_empty_pass(dut))
    if os.environ.get("B31_ENC"):
        cx, cy = (int(v) for v in os.environ["B31_ENC"].split(","))
        cocotb.start_soon(watch_encoder(dut, cx, cy))
    if os.environ.get("B31_CONV"):
        cx, cy = (int(v) for v in os.environ["B31_CONV"].split(","))
        cocotb.start_soon(watch_converter(dut, cx, cy))
    try:
        await tb.start_test_fpga.func(dut)
    finally:
        if CONV_STATS:
            tb.logger.info("b31conv counts per main state: %s", CONV_STATS["counts"])
            tb.logger.info("b31conv RAM writes per window line current_y [y, writes, non-zero]: %s",
                           CONV_STATS["writes_per_line"])
