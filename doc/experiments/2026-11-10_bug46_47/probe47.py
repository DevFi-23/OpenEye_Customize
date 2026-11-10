"""Bugs #46 / #47 probe (cocotb module, run through run47.py): the unmodified OpenEye_FPGA_tb plus a PE monitor.

P47_PE=cx,cy,col,row[,t0,t1]: every clock of that PE outside IDLE, the dense FSM counters and the operands it reads
(weight SPad address and word, iact SPad address and word, the configuration registers), and every weight / iact SPad
write. Values that are X print as X. P47_WIN=t0,t1: also the PE's weight / iact port handshake every clock in that window. P47_MAX lines (default 3000). Works with any tree whose PE has the dense FSM
(gen_dense_fsm); the RTL is never modified (P47_FORCE_RAW forces a register in the simulation only)."""
import os

import cocotb
from cocotb.triggers import FallingEdge
import OpenEye_FPGA_tb as tb


def _v(sig):
    try:
        return int(sig.value)
    except Exception:
        try:
            return str(sig.value).replace("x", "X").replace("z", "Z")
        except Exception:
            return "?"


def _get(obj, path):
    for p in path.split("."):
        try:
            obj = getattr(obj, p)
        except Exception:
            return None
    return obj


async def pe_monitor(dut):
    parts = [float(v) for v in os.environ["P47_PE"].split(",")]
    cx, cy, col, row = (int(v) for v in parts[:4])
    t0, t1 = (parts[4], parts[5]) if len(parts) >= 6 else (0.0, 1e12)
    limit = int(os.environ.get("P47_MAX", "3000"))
    pe = dut.OpenEye_Parallel.gen_x[cx].gen_y[cy].OpenEye_Cluster.pe_cluster.gen_X[col].gen_Y[row].pe
    names = {"st": "current_state_computing", "wvec": "wght_data_vec", "wfil": "gen_dense_fsm.wght_filter",
             "ich": "gen_dense_fsm.iact_channel", "iaddr": "iact_data_SPad_addr", "wr": "wght_data_SPad_data_r",
             "ir": "iact_data_SPad_data_r", "icur": "iact_data_current_3", "mux": "mux_iact_ready",
             "pa0": "psum_spad_addr_mem", "c0": "channel_reg_C0", "m0": "filters_reg_M0",
             "amax": "iact_addr_max_reg", "sw": "second_spad_words_wght", "si": "second_spad_words_iact"}
    sig = {k: _get(pe, p) for k, p in names.items()}
    ws, isp = _get(pe, "weight_data_SPad"), _get(pe, "iact_data_SPad")
    tb.logger.info("p47 PE %s: signals found %s", (cx, cy, col, row), [k for k, s in sig.items() if s is not None])
    win = [float(v) for v in os.environ["P47_WIN"].split(",")] if os.environ.get("P47_WIN") else None
    lines, last_cfg = 0, None
    while lines < limit:
        await FallingEdge(dut.clk_i)
        now = cocotb.utils.get_sim_time("ns")
        if now < t0:
            continue
        if now > t1:
            return
        cfg = tuple(_v(sig[k]) for k in ("c0", "m0", "amax", "sw", "si") if sig[k] is not None)
        if cfg != last_cfg:
            tb.logger.info("p47 t=%s cfg C0,M0,iact_addr_max,second_words_wght,second_words_iact=%s", now, cfg)
            last_cfg = cfg
            lines += 1
        if ws is not None and _v(ws.we_i) == 1:
            tb.logger.info("p47 t=%s Wwr addr=%s data=%s", now, _v(ws.addr_i), _v(ws.data_i))
            lines += 1
        if isp is not None and _v(isp.we_i) == 1:
            tb.logger.info("p47 t=%s Iwr addr=%s data=%s", now, _v(isp.addr_i), _v(isp.data_i))
            lines += 1
        if win and win[0] <= now <= win[1]:
            tb.logger.info("p47 t=%s port wght_en=%s wght_rdy=%s wght_data=%s iact_en=%s iact_rdy=%s", now,
                           _v(pe.wght_enable_i), _v(pe.wght_ready_o), _v(pe.wght_data_i), _v(pe.iact_enable_i),
                           _v(pe.iact_ready_o))
            lines += 1
        if _v(pe.compute_i) == 1:
            tb.logger.info("p47 t=%s compute_i st=%s", now, _v(sig["st"]))
            lines += 1
        st = _v(sig["st"])
        if st not in (0, "?"):
            vals = " ".join(f"{k}={_v(sig[k])}" for k in ("wvec", "wfil", "ich", "iaddr", "mux", "wr", "ir", "icur")
                            if sig[k] is not None)
            tb.logger.info("p47 t=%s st=%s %s", now, st, vals)
            lines += 1


async def force_raw(dut):
    """P47_FORCE_RAW=1: hold OpenEye_Parallel.raw_wght_i_reg at 1 (simulation only), so every layer's PEs store
    all-zero weight words like the Dense / GEMM raw mode instead of treating them as "no data"."""
    from cocotb.handle import Force
    dut.OpenEye_Parallel.raw_wght_i_reg.value = Force(1)
    tb.logger.info("p47 P47_FORCE_RAW: OpenEye_Parallel.raw_wght_i_reg forced to 1")


@cocotb.test()
async def probe_test(dut):
    if os.environ.get("P47_FORCE_RAW"):
        cocotb.start_soon(force_raw(dut))
    if os.environ.get("P47_PE"):
        cocotb.start_soon(pe_monitor(dut))
    await tb.start_test_fpga.func(dut)
