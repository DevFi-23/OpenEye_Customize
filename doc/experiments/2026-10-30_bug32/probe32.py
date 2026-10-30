"""Bug #32 / #35 probe (cocotb module, run through run32.py): probe31 (B31_IACT, ...) plus switches (environment).

  B32_BIAS=<n>     log the first n bias writes into the psum buffers (GET_BIAS): per write, the buffer address and the
                   value of every lane, listed per cluster (cluster row cr, cluster column cc) as [g0, g1, g2, g3].
  B35_DUMP=<dir>   save every iact buffer check of the testbench (expected words and DUT words, in check order) as
                   <dir>/iact_check_<k>.npz, for an analysis of bug #35 (run35.py).
  B31_TOP=<t0>:<t1>  log, between t0 and t1 ns, every change of the pass control: main FSM, psum FSM, psum_transmitted,
                   OpenEye_Parallel's FSM and finished_cycles, compute pulses, iact ready / enable bus, weight enable,
                   current_cycle, single_iteration (bug #31 fix, Dense hang).
  B32_REVERSE=1    emulate a Python-only fix of bug #32 in the simulation process only: the conv bias stream of
                   psum_stream_mapper sends the kernel groups of every buffer address in reverse order (src/ unchanged).

The RTL and the testbench are not modified."""
import os

import cocotb
from cocotb.triggers import RisingEdge

import numpy as np

import OpenEye_FPGA_tb as tb
import probe31
from open_eye import psum_stream_mapper as psm
from open_eye import rtl_test_utils as rtu

_orig_stream = psm.PsumStreamMapper.get_psum_stream


def reversed_group_stream(self):
    """The serial conv bias stream with the kernel groups of every buffer address in reverse order."""
    stream = _orig_stream(self)
    lp = self.layer_params
    if not self.params.SERIAL or lp.different_kernels_per_calculation < 2 or getattr(lp, "layer_name", "") == "Dense":
        return stream
    words = len(stream) // (lp.iact_x_line_repetitions * lp.iact_size_y * lp.filters)    # words per filter
    group = words * lp.different_kernels_per_calculation                                  # words per buffer address
    assert len(stream) % group == 0
    out = []
    for a in range(0, len(stream), group):
        blocks = [stream[a + k * words:a + (k + 1) * words] for k in range(lp.different_kernels_per_calculation)]
        for block in reversed(blocks):
            out.extend(block)
    tb.logger.info("B32_REVERSE: bias stream of %d words, kernel groups of %d words reversed per address", len(out), words)
    return out


_orig_compare = rtu.compare_iact_storage
_checks = []


def compare_and_dump(ptp, dut, iact_ref, oep, layer_params, valid_values=None):
    """The testbench's iact buffer check, plus a dump of the expected and the DUT words."""
    ok = _orig_compare(ptp, dut, iact_ref, oep, layer_params, valid_values)
    expected = rtu._to_ram_format(rtu._iact_buffer_words(oep, layer_params, iact_ref), oep, layer_params)
    if expected is not None:
        half = rtu.iact_half_offset(dut, oep)
        got = []
        for index in range(len(expected)):
            w = rtu._ram_word(dut.BUFFER_A[index % oep.IACT_RAM_CELLS].iact_layer_buffer.impl.mem[
                half + index // oep.IACT_RAM_CELLS])
            got.append(-1 if w is None else w)
        path = os.path.join(os.environ["B35_DUMP"], "iact_check_%d.npz" % len(_checks))
        np.savez(path, expected=np.array(expected, dtype=np.uint64), dut=np.array(got, dtype=np.int64).astype(np.uint64),
                 written=np.array([g != -1 for g in got]), cells=oep.IACT_RAM_CELLS,
                 layer=str(getattr(layer_params, "layer_name", "?")), iact_ref=np.array(iact_ref, dtype=object))
        _checks.append(path)
        tb.logger.info("B35_DUMP: iact check %d (%s, %d words) saved to %s", len(_checks) - 1,
                       getattr(layer_params, "layer_name", "?"), len(expected), path)
    return ok


async def watch_bias(dut, n):
    pp = dut.psum_pipeline_inst
    cc_n, cr_n = int(os.environ["CLUSTER_COLUMNS"]), int(os.environ["CLUSTER_ROWS"])
    g_n, tb_w = int(os.environ["NUM_GLB_PSUM"]), int(os.environ["DATA_PSUM_BITWIDTH"])
    seen = 0
    while seen < n:
        await RisingEdge(dut.clk_i)
        en = pp.psum_buffer_en_w.value
        if not en.is_resolvable or int(en) == 0 or int(pp.fsm_psum_current_state.value) != 0 \
                or int(dut.fsm_current_state.value) not in (5, 6):            # PSUM_IDLE during GET_BIAS (+1 cycle)
            continue
        data = int(pp.psum_buffer_data_w.value)

        def lane(cr, cc, g):
            v = (data >> (tb_w * (cc * g_n + cr * cc_n * g_n + g))) & ((1 << tb_w) - 1)
            return v - (1 << tb_w) if v >> (tb_w - 1) else v
        tb.logger.info("b32bias write %d: %s", seen, "  ".join(
            f"cr{cr}cc{cc}={[lane(cr, cc, g) for g in range(g_n)]}" for cr in range(cr_n) for cc in range(cc_n)))
        seen += 1


TOP_SIGNALS = (("main", "fsm_current_state"), ("psum", "psum_pipeline_inst.fsm_psum_current_state"),
               ("ptx", "psum_pipeline_inst.psum_transmitted"), ("par", "OpenEye_Parallel.fsm_current_state"),
               ("fin", "OpenEye_Parallel.finished_cycles"), ("cmp", "OpenEye_Parallel.compute_cluster_i_reg"),
               ("rdy", "iact_ready_o_oep_w"), ("ien", "iact_enable_i_oep_w"), ("wen", "wght_enable_i_reg"),
               ("cur", "current_cycle"), ("si", "single_iteration"))


async def watch_top(dut, t0, t1, max_lines=4000):
    from cocotb.utils import get_sim_time
    handles = []
    for name, path in TOP_SIGNALS:
        h = dut
        try:
            for part in path.split("."):
                h = getattr(h, part)
            handles.append((name, h))
        except AttributeError:
            tb.logger.info("B31_TOP: %s not found", path)
    last, lines = None, 0
    while lines < max_lines:
        await RisingEdge(dut.clk_i)
        t = get_sim_time("ns")
        if t < t0:
            continue
        if t > t1:
            return
        vals = []
        for name, h in handles:
            v = h.value
            vals.append("%s=%s" % (name, ("%x" % int(v)) if v.is_resolvable else "x"))
        if vals != last:
            last = vals
            tb.logger.info("b31top t=%.0f %s", t, " ".join(vals))
            lines += 1


@cocotb.test()
async def probe_test(dut):
    if os.environ.get("B31_TOP"):
        t0, t1 = (float(v) for v in os.environ["B31_TOP"].split(":"))
        cocotb.start_soon(watch_top(dut, t0, t1))
    if os.environ.get("B32_REVERSE"):
        psm.PsumStreamMapper.get_psum_stream = reversed_group_stream
    if os.environ.get("B35_DUMP"):
        os.makedirs(os.environ["B35_DUMP"], exist_ok=True)
        rtu.compare_iact_storage = compare_and_dump
    if os.environ.get("B32_BIAS"):
        cocotb.start_soon(watch_bias(dut, int(os.environ["B32_BIAS"])))
    await probe31.probe_test.func(dut)
