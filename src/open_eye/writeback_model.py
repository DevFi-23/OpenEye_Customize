# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Cycle model of the interlayer write-back (psum buffer -> iact buffer), for unit tests of its configuration.

Two parts of the RTL:
  read_sequence  the address and cluster-select loops of SEND_PSUM_TO_IACT (hdl/psum_pipeline.v): which cluster and
                 psum buffer address each read step uses, from the psum_pagu_* registers of LayerParameters;
  pack           RECEIVE_PSUMS_TO_IACT (hdl/OpenEye_FPGA.v): WRITEBACK_WORDS lanes (the GLBs of one cluster, one pixel
                 or, for a Dense layer, one result each) x WRITEBACK_CHANNELS cycles (channels) per transposition; one
                 group (the channels of one pixel) per cycle while lanes are left, kept if x_pos < iact_size_x; x_pos
                 restarts at the row period iact_x_add_up (and at every group of a fully connected layer); a buffer row
                 is written when the storage counter wraps; after the state the flush shifts every cycle until the
                 counter is back at 0.
Timing as seen in RTL simulation (doc/experiments/2026-10-24_bug26_dense_writeback.md, section 3): the value read in
step s reaches the main FSM at cycle 7 + s of SEND_PSUM_TO_IACT; after the state ends (cycle `limit`) the quantizer
output runs on for three cycles and then holds. `channels == lanes` models the RTL before the bug #25 fix
(doc/experiments/2026-10-26_bug25_glb_psum2.md).
"""


def read_sequence(lp, clusters, steps):
    """(cluster, address) of read step 0, 1, ...: the psum_cycle_addr_* and psum_cluster_select_* counters."""
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


def pack(lane_value, limit, lanes, cells, channels=4, iact_size_x=10**6, add_up=10**6, fc=False):
    """Buffer rows (lists of bytes, cell 0 first) the write-back writes.

    lane_value(s, a): quantizer output of lane a for read step s; limit: fsm_psum_limit (last cycle of the state);
    lanes: WRITEBACK_WORDS; cells: IACT_RAM_CELLS; channels: WRITEBACK_CHANNELS."""
    groups = 8 * cells // channels
    last = limit - 3

    def quant(c, a):
        return lane_value(min(c - 7, last), a)

    mux = [[0] * channels for _ in range(lanes)]
    shift = [[0] * channels for _ in range(lanes)]
    bus = [[0] * channels for _ in range(groups)]
    trans = x_pos = sc = 0
    shifting = False
    rows = []
    c = 7
    while True:
        idle = c > limit
        if idle and sc == 0:
            return rows
        write = False
        new_x = x_pos if shifting else 0
        new_trans = trans + 1
        new_shift, new_bus, new_sc = shift, bus, sc
        if shifting and trans <= lanes:
            new_x = x_pos + 1
            if x_pos < iact_size_x:
                new_sc = sc + 1
                if sc == groups - 1:
                    new_sc, write = 0, True
                new_bus = bus[1:] + [shift[0]]
                new_shift = shift[1:] + [[0] * channels]
        new_mux = [lane[1:] + [quant(c, a)] for a, lane in enumerate(mux)]
        new_shifting = shifting
        if trans == channels:
            new_trans, new_shift, new_shifting = 1, [list(lane) for lane in mux], True
            if x_pos >= add_up - 1 or fc:
                new_x = 0
        if idle:                        # flush: count and shift every cycle; the top group as above
            new_sc = sc + 1
            write = False
            if sc == groups - 1:
                new_sc, write = 0, True
            new_bus = bus[1:groups] + [new_bus[-1]]
        mux, shift, bus, trans, x_pos, sc, shifting = new_mux, new_shift, new_bus, new_trans, new_x, new_sc, new_shifting
        if write:
            rows.append([b for g in bus for b in g])
        c += 1
