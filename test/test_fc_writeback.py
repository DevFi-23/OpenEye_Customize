# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Write-back of a Dense layer into the iact buffer (bug #26), checked on a cycle model of the RTL.

The model (open_eye.writeback_model) follows hdl/psum_pipeline.v (SEND_PSUM_TO_IACT: address and cluster-select loops)
and hdl/OpenEye_FPGA.v (RECEIVE_PSUMS_TO_IACT: lanes x 4-channel transposition, group filter, storage counter, flush in
PSUM_IDLE). The registers come from LayerParameters.configure_fc_writeback.
"""
import math
import types

import pytest

from open_eye.layer_parameters import LayerParameters
from open_eye.writeback_model import pack, read_sequence


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


def fc_values(filters):
    """Lane values of a Dense write-back: lane 0 carries the result read in that step, the other lanes other GLBs."""
    return lambda s, a: filters[s] if a == 0 else -1


def fc_rows(filters, limit, lanes, cells, **kw):
    return pack(fc_values(filters), limit, lanes, cells, iact_size_x=1, fc=True, **kw)


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
    rows = fc_rows(filters, lp.fsm_psum_limit, w, cells)
    flat = [v for row in rows for v in row]
    assert len(rows) == math.ceil(reps * cx * p / (8 * cells))
    assert flat[:n] == list(range(n))


def test_old_wrap_duplicates_groups():
    """Without the RTL line (x_pos only wraps at iact_x_add_up = K) the row is the first group over and over."""
    lp = writeback_registers(8, 2, 4)
    seq = read_sequence(lp, 4, lp.fsm_psum_limit)
    filters = [(addr // 4) * 8 + cl * 4 + addr % 4 for cl, addr in seq]
    rows = pack(fc_values(filters), lp.fsm_psum_limit, 4, 4, iact_size_x=1, add_up=16)
    assert rows[0] == [0, 1, 2, 3] * 8          # the RTL simulation showed f0..f3 eight times (run wb16k)


def test_padding_matches_rtl():
    """Dense 64 -> 10 (P = 6): after the 12 values of both columns the row continues with f0..f3 (RTL run e6410)."""
    lp = writeback_registers(10, 2, 4)
    seq = read_sequence(lp, 4, lp.fsm_psum_limit)
    filters = [cl * 6 + addr % 6 for cl, addr in seq]
    rows = fc_rows(filters, lp.fsm_psum_limit, 4, 4)
    assert rows[0][:16] == list(range(12)) + [0, 1, 2, 3]
