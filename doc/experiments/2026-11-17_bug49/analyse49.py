"""analyse49.py <dump dir>: the wrong bytes of the pooled image (the input of Conv3, check 3 of probe49) with their
(channel, x, y), the 2 x 2 window of the Conv2 output reference behind each, and where the DUT value could come from."""
import json
import os
import sys

import numpy as np

D = sys.argv[1]
c3 = json.load(open(os.path.join(D, "check_3.json")))
c2 = json.load(open(os.path.join(D, "check_2.json")))
cells = c3["IACT_RAM_CELLS"]
conv2 = np.array(c2["iact_ref"])          # Conv2 output (reference), (C, X, Y)
pooled = np.array(c3["iact_ref"])         # pooled reference
print("conv2 ref", conv2.shape, "pooled ref", pooled.shape)
bad = []
for i, (e, cc, cx, cy) in enumerate(zip(c3["expected"], c3["code_c"], c3["code_x"], c3["code_y"])):
    d = c3["dut"][i % cells][i // cells]
    for b in range(8):
        eb, db = (e >> 8 * b) & 255, (d >> 8 * b) & 255 if d >= 0 else -1
        if eb != db:
            c, x, y = (cc >> 8 * b) & 255, (cx >> 8 * b) & 255, (cy >> 8 * b) & 255
            bad.append((i, b, c, x, y, eb, db))
print(len(bad), "wrong bytes")
for i, b, c, x, y, eb, db in bad:
    win = conv2[c, 2 * x:2 * x + 2, 2 * y:2 * y + 2]
    # windows of the same channel whose max is the DUT value
    cands = [(xx, yy) for xx in range(pooled.shape[1]) for yy in range(pooled.shape[2])
             if conv2[c, 2 * xx:2 * xx + 2, 2 * yy:2 * yy + 2].max() == db]
    print(f"word {i:3d} byte {b} -> c {c:2d} x {x} y {y}: ref {eb} (pooled ref {pooled[c, x, y]}), dut {db}; "
          f"window {win.ravel().tolist()}; same-channel windows with max {db}: {cands[:6]}")


def conv_output_check(dump, ref, cells):
    """The buffer after a convolution against its reference, with the layout of the iact buffer (groups of 4
    channels; within a group row y, column x, the 4 channels): byte ((c // 4 * Y + y) * X + x) * 4 + c % 4."""
    C, X, Y = ref.shape
    wrong = []
    for c in range(C):
        for x in range(X):
            for y in range(Y):
                k = ((c // 4 * Y + y) * X + x) * 4 + c % 4
                i, b = divmod(k, 8)
                w = dump[i % cells][i // cells]
                v = (w >> 8 * b) & 255 if w >= 0 else -1
                r = int(ref[c, x, y]) & 255
                if v != r:
                    wrong.append((c, x, y, r, v))
    return wrong


wrong = conv_output_check(c2["dut"], conv2, cells)
print(f"\nConv2 output in the buffer (check 2, before the pooling): {len(wrong)} of {conv2.size} values differ")
for c, x, y, r, v in wrong[:40]:
    print(f"  c {c:2d} x {x:2d} y {y:2d}: ref {r} dut {v}")
xs = sorted({w[1] for w in wrong}); ys = sorted({w[2] for w in wrong}); cs = sorted({w[0] for w in wrong})
print("  x:", xs, " y:", ys, " channels:", cs)
