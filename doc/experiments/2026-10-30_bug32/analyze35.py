"""analyze35.py <dump dir> [check index]: the bytes of one iact buffer check dumped by probe32 (B35_DUMP) that differ,
as (filter f, x, y) of the layer that wrote them. For the check before the Dense layer of the real model (check 2:
after pool1, after pool2, after conv3) the flat Dense input order of fill_dram_with_ref is mapped back to conv3's
[f][x][y] with DRAMContents.dense_input_order (x = iact_size_x axis = image row, y = column).
Run from the repository root with the venv's python."""
import collections
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
dump_dir = sys.argv[1]
k = int(sys.argv[2]) if len(sys.argv) > 2 else 2
d = np.load(os.path.join(dump_dir, "iact_check_%d.npz" % k), allow_pickle=True)
exp_words, dut_words, written = d["expected"], d["dut"], d["written"]


def to_bytes(words):
    return np.array([(int(w) >> (8 * b)) & 0xFF for w in words for b in range(8)], dtype=np.int64)


e, g = to_bytes(exp_words), to_bytes(dut_words)
e = np.where(e > 127, e - 256, e)
g = np.where(g > 127, g - 256, g)
print("check %d (%s): %d words, %d never written, %d of %d bytes differ" % (
    k, d["layer"], len(exp_words), int((~written).sum()), int((e != g).sum()), e.size))
if str(d["layer"]) != "Dense":
    sys.exit(0)
F, X, Y = 64, 7, 7
# Dense input position p holds conv3 output order[p] of [f][x][y] flat: p = f%4 + 4x + 4X*y + 4XY*(f//4), the order of
# fill_dram_with_ref (checked equal to DRAMContents.dense_input_order for this model)
order = [0] * (F * X * Y)
for f in range(F):
    for x in range(X):
        for y in range(Y):
            order[f % 4 + 4 * x + 4 * X * y + 4 * X * Y * (f // 4)] = (f * X + x) * Y + y
n = F * X * Y
bad = [p for p in range(n) if e[p] != g[p]]
pos = [(order[p] // (X * Y), (order[p] // Y) % X, order[p] % Y) for p in bad]
print("wrong bytes by x:", dict(sorted(collections.Counter(x for _, x, _ in pos).items())))
print("wrong bytes by y:", dict(sorted(collections.Counter(y for _, _, y in pos).items())))
print("wrong bytes by f%4:", dict(sorted(collections.Counter(f % 4 for f, _, _ in pos).items())))
print("wrong bytes by f%2:", dict(sorted(collections.Counter(f % 2 for f, _, _ in pos).items())))
print("DUT - expected:", dict(sorted(collections.Counter(int(g[p] - e[p]) for p in bad).most_common(12))))
print("expected 0 at", sum(e[p] == 0 for p in bad), "DUT 0 at", sum(g[p] == 0 for p in bad))
print("first 30 (f, x, y, expected, DUT):", [(f, x, y, int(e[p]), int(g[p])) for (f, x, y), p in zip(pos[:30], bad[:30])])
np.savez(os.path.join(dump_dir, "conv3_compare.npz"), exp=np.array([e[order.index(i)] for i in range(n)]).reshape(F, X, Y),
         dut=np.array([g[order.index(i)] for i in range(n)]).reshape(F, X, Y))
