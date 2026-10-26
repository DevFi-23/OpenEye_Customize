# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Write-back of a Dense layer into the iact buffer (bug #26), checked on a cycle model of the RTL.

The model follows hdl/psum_pipeline.v (SEND_PSUM_TO_IACT: address and cluster-select loops) and hdl/OpenEye_FPGA.v
(RECEIVE_PSUMS_TO_IACT: WRITEBACK_WORDS-lane transposition, group filter, storage counter, flush in PSUM_IDLE), with
the pipeline timing seen in RTL simulation (doc/experiments/2026-10-24_bug26_dense_writeback.md, section 3): the value
read for loop step s reaches the main FSM at cycle 7 + s of the state, and after the state ends the quantizer output
runs on for three cycles and then holds. The registers come from LayerParameters.configure_fc_writeback.
"""
import math
import types

import pytest

from open_eye.layer_parameters import LayerParameters


def writeback_registers(n_filters, cx, cells, macs=2):
    """Write-back registers of a Dense layer with n_filters outputs (the parts of write_dense_layer they need)."""
    lp = LayerParameters.__new__(LayerParameters)
    lp.needed_psum_transmissions = math.ceil(n_filters / (16 * cx))
    lp.used_psum_per_PE = math.ceil(n_filters / cx / macs / lp.needed_psum_transmissions) * macs
    lp.psum_pagu_loop_limit = [0] * 6
    lp.psum_pagu_addr_inc = [0] * 6
    lp.psum_pagu_cs_limit = [0] * 6
    lp.psum_pagu_cs_inc = [0] * 6
    lp.configure_fc_writeback(types.SimpleNamespace(Clusters_X=cx, IACT_RAM_CELLS=cells))
    return lp


def read_sequence(lp, clusters, steps):
    """(cluster, address) of loop step 0, 1, ...: the psum_cycle_addr_* and psum_cluster_select_* counters."""
    lim, inc = lp.psum_pagu_loop_limit, lp.psum_pagu_addr_inc
    cs_lim, cs_inc = lp.psum_pagu_cs_limit[:4] + [0], lp.psum_pagu_cs_inc[:4] + [0]
    addr, cnt = [0] * 5, [0] * 5
    sel, scnt = [0] * 4, [0] * 4
    out = []
    for _ in range(steps):
        out.append((sel[0], addr[0]))
        # address loops (5 levels): the counter of a level that wraps loads the next level's address + increment
        level = 0
        while level < 5 and cnt[level] == lim[level]:
            cnt[level] = 0
            level += 1
        if level < 5:
            cnt[level] += 1
        nxt = addr[level] + inc[level] if level < 5 else addr[4] + inc[4]
        for i in range(min(level, 4) + 1):
            addr[i] = nxt
        # cluster-select loops (4 levels), modulo the cluster count
        level = 0
        while level < 4 and scnt[level] == cs_lim[level]:
            scnt[level] = 0
            level += 1
        if level < 4:
            scnt[level] += 1
            nxt = (sel[level] + cs_inc[level]) % clusters
            for i in range(level + 1):
                sel[i] = nxt
        else:
            sel = [0] * 4
    return out


def pack(values, limit, w, cells, iact_size_x=1, add_up=10**6, fc=True):
    """Buffer rows RECEIVE_PSUMS_TO_IACT writes when value s of `values` reaches it at cycle 7 + s of the state."""
    groups = 8 * cells // w
    held = values[min(limit - 3, len(values) - 1)]

    def quant(c):                       # quantizer output in cycle c (state ends after cycle `limit`)
        s = c - 7
        return values[s] if c <= limit + 4 else held

    mux = [[0] * w for _ in range(w)]
    shift = [[0] * w for _ in range(w)]
    bus = [[0] * w for _ in range(groups)]
    trans = x_pos = sc = 0
    shifting = False
    rows = []
    c = 7
    while True:
        idle = c > limit
        if idle and sc == 0:
            return rows
        write = False
        # capture branch
        new_x = 0
        new_trans = trans + 1
        new_shift, new_bus, new_sc = shift, bus, sc
        if shifting:
            new_x = x_pos + 1
            if x_pos < iact_size_x:
                new_sc = sc + 1
                if sc == groups - 1:
                    new_sc, write = 0, True
                new_bus = bus[1:] + [shift[0]]
                new_shift = shift[1:] + [[0] * w]
        new_mux = [lane[1:] + [quant(c) if a == 0 else 0] for a, lane in enumerate(mux)]
        new_shifting = shifting
        if trans == w:
            new_trans, new_shift, new_shifting = 1, [list(l) for l in mux], True
            if x_pos >= add_up - 1 or fc:
                new_x = 0
        if idle:                        # flush: count and shift every cycle, the top group as above
            new_sc = sc + 1
            write = False
            if sc == groups - 1:
                new_sc, write = 0, True
            new_bus = bus[1:groups] + [new_bus[-1]]
        mux, shift, bus, trans, x_pos, sc, shifting = new_mux, new_shift, new_bus, new_trans, new_x, new_sc, new_shifting
        if write:
            rows.append([b for g in bus for b in g])
        c += 1


CONFIGS = [(n, cx, cells, w) for n in (4, 8, 10, 16, 32, 40, 64, 96, 128)
           for cx in (1, 2, 4) for cells in (4, 8) for w in (2, 4)]


@pytest.mark.parametrize("n,cx,cells,w", CONFIGS)
def test_writeback_order(n, cx, cells, w):
    """The rows hold the outputs in filter order; only addresses and clusters that hold results are read."""
    lp = writeback_registers(n, cx, cells)
    p, reps = lp.used_psum_per_PE, lp.needed_psum_transmissions
    assert p <= 16 and lp.psum_pagu_cs_limit[0] <= 15        # 4-bit cluster-select limits
    # the psum buffer: filter f = r*CX*P + c*P + a in cluster column c (cluster index c), address r*P + a
    seq = read_sequence(lp, 2 * cx, lp.fsm_psum_limit)            # two cluster rows
    assert all(cl < cx and addr < reps * p for cl, addr in seq)
    filters = [(addr // p) * cx * p + cl * p + addr % p for cl, addr in seq]
    assert filters[:reps * cx * p] == list(range(reps * cx * p))
    rows = pack(filters, lp.fsm_psum_limit, w, cells)
    flat = [v for row in rows for v in row]
    assert len(rows) == math.ceil(reps * cx * p / (8 * cells))
    assert flat[:n] == list(range(n))


def test_old_wrap_duplicates_groups():
    """Without the RTL line (x_pos only wraps at iact_x_add_up = K) the row is the first group over and over."""
    lp = writeback_registers(8, 2, 4)
    seq = read_sequence(lp, 4, lp.fsm_psum_limit)
    filters = [(addr // 4) * 8 + cl * 4 + addr % 4 for cl, addr in seq]
    rows = pack(filters, lp.fsm_psum_limit, 4, 4, add_up=16, fc=False)
    assert rows[0] == [0, 1, 2, 3] * 8          # the RTL simulation showed f0..f3 eight times (run wb16k)


def test_padding_matches_rtl():
    """Dense 64 -> 10 (P = 6): after the 12 values of both columns the row continues with f0..f3 (RTL run e6410)."""
    lp = writeback_registers(10, 2, 4)
    seq = read_sequence(lp, 4, lp.fsm_psum_limit)
    filters = [cl * 6 + addr % 6 for cl, addr in seq]
    rows = pack(filters, lp.fsm_psum_limit, 4, 4)
    assert rows[0][:16] == list(range(12)) + [0, 1, 2, 3]
