"""Cycle model of RECEIVE_PSUMS_TO_IACT (hdl/OpenEye_FPGA.v) for bug #25: lanes W (pixels read per cycle, WRITEBACK_WORDS)
and group length C (channels per pixel group). C = W, gate=False is today's RTL; the proposal keeps C = 4 for any W and
only emits (and counts in x_pos) the first W lanes of each group. `python3 model25.py` prints the comparison."""


def pack(lane_values, n_cycles, w, c, cells=4, iact_size_x=10**6, add_up=10**6, fc=False, gate=True):
    groups = 8 * cells // c
    mux = [[0] * c for _ in range(w)]
    shift = [[0] * c for _ in range(w)]
    bus = [[0] * c for _ in range(groups)]
    trans = x_pos = sc = 0
    shifting = False
    rows = []
    for t in range(n_cycles):                       # capture cycles (cycle 7 + t of SEND_PSUM_TO_IACT); no flush modelled
        write = False
        new_x, new_trans = 0, trans + 1
        new_shift, new_bus, new_sc = shift, bus, sc
        emit = shifting and (not gate or (1 <= trans <= w))
        if emit:
            new_x = x_pos + 1
            if x_pos < iact_size_x:
                new_sc = sc + 1
                if sc == groups - 1:
                    new_sc, write = 0, True
                new_bus = bus[1:] + [shift[0]]
                new_shift = shift[1:] + [[0] * c]
        elif shifting and gate:
            new_x = x_pos                           # no lane left in this group: x_pos holds
        new_mux = [lane[1:] + [lane_values(t, a)] for a, lane in enumerate(mux)]
        new_shifting = shifting
        if trans == c:
            new_trans, new_shift, new_shifting = 1, [list(l) for l in mux], True
            if x_pos >= add_up - 1 or fc:
                new_x = 0
        mux, shift, bus, trans, x_pos, sc, shifting = new_mux, new_shift, new_bus, new_trans, new_x, new_sc, new_shifting
        if write:
            rows.append([b for g in bus for b in g])
    return rows


def conv_stream(w, c=4):
    """What the psum read loops deliver (seen in RTL, bug #25): per window of 4 cycles the channels c0..c3 of the W pixels
    of one cluster; value = 10 * pixel + channel."""
    return lambda t, a: 10 * (w * (t // c) + a) + t % c


if __name__ == "__main__":
    pixels = 16
    want = [10 * p + ch for p in range(pixels) for ch in range(4)]
    for w in (4, 2):
        cycles = pixels // w * 4 + 8
        old = [v for r in pack(conv_stream(w), cycles, w, w, gate=False) for v in r]
        new = [v for r in pack(conv_stream(w), cycles, w, 4) for v in r]
        print(f"W={w}: today's RTL (C=W) right: {old[:len(want)] == want}; proposal (C=4) right: {new[:len(want)] == want}")
        if w == 2:
            print("  today's first 16 bytes:", old[:16])
    # W = C = 4: the proposal is the old circuit (gate never blocks)
    s = conv_stream(4)
    assert pack(s, 72, 4, 4) == pack(s, 72, 4, 4, gate=False)
    # FC: lane 0 only, C = 4, any W: the outputs in order
    for w in (2, 4):
        rows = pack(lambda t, a: t if a == 0 else -1, 40, w, 4, iact_size_x=1, fc=True)
        print(f"FC W={w}: first row in order: {rows[0] == list(range(32))}")


def padded_rows_check(width, add_up, rows, w):
    """Rows of `width` pixels read as `add_up` pixels (padding at the row end); the proposal keeps the real pixels."""
    pix = [(r, x) for r in range(rows) for x in range(add_up)]
    stream = lambda t, a: (lambda p: -1 if p[1] >= width else 10 * (p[0] * width + p[1]) + t % 4)(pix[w * (t // 4) + a]) \
        if w * (t // 4) + a < len(pix) else -2
    cycles = len(pix) // w * 4 + 8
    got = [v for r in pack(stream, cycles, w, 4, iact_size_x=width, add_up=add_up) for v in r]
    want = [10 * p + ch for p in range(rows * width) for ch in range(4)]
    old = [v for r in pack(stream, cycles, w, w, iact_size_x=width, add_up=add_up, gate=False) for v in r]
    return got[:len(want)] == want, old[:len(want)] == want


if __name__ == "__main__":
    # whole buffer rows only (the flush after the last group is not modelled)
    for width, add_up, rows in ((7, 8, 8), (6, 8, 8), (14, 16, 4), (28, 32, 4), (8, 8, 4)):
        for w in (4, 2):
            new_ok, old_ok = padded_rows_check(width, add_up, rows, w)
            print(f"width {width} read as {add_up}, W={w}: proposal right {new_ok}, today's RTL right {old_ok}")
