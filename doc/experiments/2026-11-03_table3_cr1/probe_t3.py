"""probe_t3 (cocotb module, run through run.py): probe25 (doc/experiments/2026-10-26_bug25, the unmodified OpenEye_FPGA_tb
plus switches) and these monitors / emulations. Observation only unless a T3_FIX* switch is set; no RTL file is changed.
  T3_WBUF=<json>      weight staging buffer: rows written per layer, largest write address, wraps (bug #29)
  T3_INJECT=<pkl>     layer 0 gets the fmap / weights / bias of a dumped conv layer (verify_layer<n>.pkl);
                      T3_NOZERO_IACT=1 (+ T3_REGION=x0:x1,y0:y1, T3_CHANNELS=c,..) zero iacts -> 1, T3_SET=c,x,y=v;..
                      single iacts, T3_NOZERO_WGHT=1 zero weights -> 1
  T3_PES=<json>       per PE: accepted iact words, psum outputs (handshake), compute_i pulses
  T3_PESPAD=cx.cy.col.row:p0:p1 + T3_PESPAD_OUT=<json>   one PE's iact SPad ports and state, passes p0..p1
  T3_START=<json>     at every start of the psum collection (CALCULATE_PSUM, results_ready_calc rises): psum_ready_o_reg
  T3_CAPTURE=1        log psum_enable_o / psum_buffer_en_w / psum slots in every PSUM_GET_RESULTS cycle
  T3_FIXREADY=1       emulate the proposed fix of bug #28: force all_psum_ready = AND of every GLB's ready bit
  T3_FIXENABLE=1      the same for all_psum_enable (not needed for any failure found)"""
import json
import os

import cocotb
from cocotb.triggers import RisingEdge

import probe25


async def watch_wbuf(dut, path):
    layers, cur, last_state = [], None, None
    while True:
        await RisingEdge(dut.clk_i)
        try:
            state = int(dut.fsm_current_state.value)
            we = int(dut.wght_buffer_en_w.value)
            addr = int(dut.wght_buffer_wr_addr.value)
        except ValueError:
            continue
        if state == 4 and last_state != 4:
            cur = {"layer": len(layers), "writes": 0, "max_addr": 0, "wraps": 0, "prev": None}
            layers.append(cur)
        if cur is not None and we:
            cur["writes"] += 1
            if cur["prev"] is not None and addr < cur["prev"]:
                cur["wraps"] += 1
            cur["prev"] = addr
            cur["max_addr"] = max(cur["max_addr"], addr)
            json.dump(layers, open(path, "w"))
        last_state = state


def install_inject_data():
    """T3_INJECT=<verify_layer*.pkl>: layer 0 gets the fmap, weights and bias of a dumped conv layer (the reference is
    computed from the same DRAM, so it stays exact)."""
    path = os.environ.get("T3_INJECT")
    if not path:
        return
    import pickle
    import OpenEye_FPGA_tb as tb
    data = pickle.load(open(path, "rb"))
    orig = tb.channel_pad.fill_padding_channels

    def fill_padding_channels(model, dram):
        n = orig(model, dram)
        assert len(dram.fmap[0]) == len(data["fmap"]) and len(dram.weights[0]) == len(data["weights"]), "shape differs"
        import copy
        fmap, wght = copy.deepcopy(data["fmap"]), copy.deepcopy(data["weights"])
        # T3_REGION=x0:x1,y0:y1 limits the iact edits below to that region (all channels)
        reg = os.environ.get("T3_REGION")
        (x0, x1), (y0, y1) = ([int(v) for v in r.split(":")] for r in reg.split(",")) if reg else ((0, 99), (0, 99))
        chans = [int(c) for c in os.environ["T3_CHANNELS"].split(",")] if os.environ.get("T3_CHANNELS") else range(len(fmap))
        if os.environ.get("T3_NOZERO_IACT"):
            n = 0
            for c in chans:
                for x in range(len(fmap[c])):
                    for y in range(len(fmap[c][x])):
                        if x0 <= x < x1 and y0 <= y < y1 and fmap[c][x][y] == 0:
                            fmap[c][x][y] = 1; n += 1
            dut_log("T3_NOZERO_IACT: %d zero iacts set to 1" % n)
        for item in filter(None, os.environ.get("T3_SET", "").split(";")):
            pos, v = item.split("=")
            c, x, y = (int(t) for t in pos.split(","))
            fmap[c][x][y] = int(v)
            dut_log("T3_SET: iact (%d,%d,%d) = %s" % (c, x, y, v))
        if os.environ.get("T3_NOZERO_WGHT"):
            n = 0
            for c in range(len(wght)):
                for f in range(len(wght[c])):
                    for a in range(len(wght[c][f])):
                        for b in range(len(wght[c][f][a])):
                            if wght[c][f][a][b] == 0:
                                wght[c][f][a][b] = 1; n += 1
            dut_log("T3_NOZERO_WGHT: %d zero weights set to 1" % n)
        dram.fmap[0] = fmap
        dram.weights[0] = wght
        dram.bias[0] = list(data["bias"]) + list(dram.bias[0][len(data["bias"]):])
        dut_log("T3_INJECT: layer 0 data from %s" % path)
        return n
    tb.channel_pad.fill_padding_channels = fill_padding_channels


def dut_log(msg):
    import logging
    logging.getLogger("cocotb").info(msg)


PE_LOG = {}


async def watch_pes(dut, path):
    """T3_PES=<json>: per PE, every accepted iact word (lane, data), psum output (handshake) and compute_i pulse."""
    pes = {}
    cx = 0
    while True:
        try:
            dut.OpenEye_Parallel.gen_x[cx]._discover_all()
        except Exception:
            pass
        found = False
        for cy in range(8):
            for col in range(8):
                for row in range(8):
                    try:
                        pe = dut.OpenEye_Parallel.gen_x[cx].gen_y[cy].OpenEye_Cluster.pe_cluster.gen_X[col].gen_Y[row].pe
                        _ = pe.psum_enable_o.value
                    except Exception:
                        continue
                    pes[f"{cx}.{cy}.{col}.{row}"] = pe
                    found = True
        if not found:
            break
        cx += 1
    log = {k: {"iact": [], "psum": [], "compute": []} for k in pes}
    PE_LOG.update(pes=list(pes), log=log)
    cyc = 0
    def u(sig):
        try:
            return int(sig.value)
        except ValueError:
            return None
    while True:
        await RisingEdge(dut.clk_i)
        cyc += 1
        for k, pe in pes.items():
            if u(pe.compute_i) == 1:
                log[k]["compute"].append(cyc)
            if u(pe.psum_enable_o) == 1 and u(pe.psum_ready_i) == 1:
                v = u(pe.psum_data_o)
                if v is not None and v >= 1 << 19:
                    v -= 1 << 20
                log[k]["psum"].append([cyc, v])
            en = u(pe.iact_enable_i); rd = u(pe.iact_ready_o)
            if en and rd and (en & rd):
                log[k]["iact"].append([cyc, en & rd, u(pe.iact_data_i)])


SPAD_LOG = []


async def watch_pe_spads(dut, spec):
    """T3_PESPAD=cx.cy.col.row:p0:p1 (+ T3_PESPAD_OUT=<json>): every cycle of passes p0..p1 of one PE, the iact address /
    data SPad port activity (we, re, addr, data in / out), the PE state and word counts."""
    pe_id, p0, p1 = spec.split(":")
    cx, cy, col, row = (int(v) for v in pe_id.split("."))
    pe = dut.OpenEye_Parallel.gen_x[cx].gen_y[cy].OpenEye_Cluster.pe_cluster.gen_X[col].gen_Y[row].pe
    a = pe.gen_iact_addr_spad.iact_addr_SPad
    d = pe.iact_data_SPad
    def u(sig):
        try:
            return int(sig.value)
        except ValueError:
            return -1
    passes = 0
    cyc = 0
    while True:
        await RisingEdge(dut.clk_i)
        cyc += 1
        if u(pe.compute_i) == 1:
            passes += 1
        if not int(p0) <= passes <= int(p1):
            if passes > int(p1):
                return
            continue
        SPAD_LOG.append([cyc, passes, u(pe.current_state_computing),
                         u(a.we_i), u(a.re_i), u(a.addr_i), u(a.data_i), u(a.data_o),
                         u(d.we_i), u(d.re_i), u(d.addr_i), u(d.data_i), u(d.data_o),
                         u(pe.first_spad_words_iact_S), u(pe.second_spad_words_iact)])


START_LOG = []


async def watch_psum_start(dut):
    """T3_START=<json>: at the first cycle of every CALCULATE_PSUM in which results_ready_calc is 1 (the psum FSM
    starts collecting), the GLB ready bits psum_ready_o_reg and the PE pass count of PE (0,0,0,0)."""
    pp = dut.psum_pipeline_inst
    pe0 = dut.OpenEye_Parallel.gen_x[0].gen_y[0].OpenEye_Cluster.pe_cluster.gen_X[0].gen_Y[0].pe
    cyc, passes, armed = 0, 0, True
    while True:
        await RisingEdge(dut.clk_i)
        cyc += 1
        try:
            if int(pe0.compute_i.value) == 1:
                passes += 1
            st = int(pp.fsm_psum_current_state.value)
            rr = int(pp.results_ready.value)
            calc = int(pp.results_ready_calc.value)
            ready = str(pp.psum_ready_o_reg.value)
        except ValueError:
            continue
        if st != 2:
            armed = True
            continue
        if armed and calc == 1 and rr == 0:
            START_LOG.append([cyc, passes, ready])
            armed = False


async def emulate_ready_fix(dut):
    """T3_FIXREADY=1: simulation-only emulation of the proposed psum_pipeline fix at CLUSTER_ROWS = 1: all_psum_ready
    = AND of every GLB's psum_ready_o_reg bit (the RTL ANDs only the even GLB of each pair). Forces the wire every
    cycle at the falling edge; no RTL file is changed."""
    from cocotb.handle import Force
    from cocotb.triggers import FallingEdge
    pp = dut.psum_pipeline_inst
    while True:
        await FallingEdge(dut.clk_i)
        bits = str(pp.psum_ready_o_reg.value)
        pp.all_psum_ready.value = Force(1 if bits and all(b == "1" for b in bits) else 0)


async def emulate_enable_fix(dut):
    """T3_FIXENABLE=1: like T3_FIXREADY for all_psum_enable (PSUM_GET_RESULTS): AND of every GLB's psum_enable_o."""
    from cocotb.handle import Force
    from cocotb.triggers import FallingEdge
    pp = dut.psum_pipeline_inst
    while True:
        await FallingEdge(dut.clk_i)
        bits = str(pp.psum_enable_o.value)
        pp.all_psum_enable.value = Force(1 if bits and all(b == "1" for b in bits) else 0)


async def watch_capture(dut):
    """T3_CAPTURE=1: every cycle the psum FSM is in PSUM_GET_RESULTS (3): psum_enable_o, psum_buffer_en_w,
    fsm_psum_cycle and the 20-bit psum slots of psum_data_o_w (cluster-major, GLB-minor)."""
    import logging
    log = logging.getLogger("cocotb")
    pp = dut.psum_pipeline_inst
    while True:
        await RisingEdge(dut.clk_i)
        try:
            st = int(pp.fsm_psum_current_state.value)
        except ValueError:
            continue
        if st != 3:
            continue
        txt = str(pp.psum_data_o_w.value)
        n = len(txt) // 20
        slots = []
        for k in range(n):
            b = txt[len(txt) - 20 * (k + 1):len(txt) - 20 * k]
            if all(c in "01" for c in b):
                v = int(b, 2); slots.append(v - (1 << 20) if v >= 1 << 19 else v)
            else:
                slots.append("X")
        log.info("t3cap en_o=%s en_w=%s cyc=%s slots=%s", str(pp.psum_enable_o.value), str(pp.psum_buffer_en_w.value),
                 str(pp.fsm_psum_cycle.value), slots)


@cocotb.test()
async def probe_test(dut):
    if os.environ.get("T3_CAPTURE"):
        cocotb.start_soon(watch_capture(dut))
    if os.environ.get("T3_FIXENABLE"):
        cocotb.start_soon(emulate_enable_fix(dut))
    if os.environ.get("T3_FIXREADY"):
        cocotb.start_soon(emulate_ready_fix(dut))
    if os.environ.get("T3_START"):
        cocotb.start_soon(watch_psum_start(dut))
    if os.environ.get("T3_PESPAD"):
        cocotb.start_soon(watch_pe_spads(dut, os.environ["T3_PESPAD"]))
    if os.environ.get("T3_PES"):
        cocotb.start_soon(watch_pes(dut, os.environ["T3_PES"]))
    install_inject_data()
    if os.environ.get("T3_WBUF"):
        cocotb.start_soon(watch_wbuf(dut, os.environ["T3_WBUF"]))
    try:
        await probe25.probe_test.func(dut)
    finally:
        if os.environ.get("T3_PES") and PE_LOG:
            json.dump(PE_LOG, open(os.environ["T3_PES"], "w"))
        if os.environ.get("T3_START"):
            json.dump(START_LOG, open(os.environ["T3_START"], "w"))
        if os.environ.get("T3_PESPAD_OUT"):
            json.dump(SPAD_LOG, open(os.environ["T3_PESPAD_OUT"], "w"))
