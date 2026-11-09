"""slot_map.py <sim dir> [first line] [lines] [layer]: for every 20-bit slot of the DMA output words of a convolution, the
(filter, window centre) the testbench expects there (output_order of verify_layer0.pkl, centre = stride x position) and
the (filter, centre) whose stride-1 "same" window value equals what the DUT sent (numpy on the raw integers, as
window_map.py; '?' when no window has that value, '*' for several). Shows how a strided layer's outputs are permuted.
    venv/bin/python doc/experiments/2026-11-07_bug41_stride/slot_map.py test/.temp/b39_f12x8 0 24"""
import os
import pickle
import sys

import numpy as np

sim = sys.argv[1]
first = int(sys.argv[2]) if len(sys.argv) > 2 else 0
count = int(sys.argv[3]) if len(sys.argv) > 3 else 32
layer = int(sys.argv[4]) if len(sys.argv) > 4 else 0
d = pickle.load(open(os.path.join(sim, f"verify_layer{layer}.pkl"), "rb"))
bits, spw = d["psum_bits"], d["dma_bits"] // 32
fm = np.array(d["fmap"], dtype=np.int64)
W = np.array(d["weights"], dtype=np.int64)
F = d["filters"]
b = np.array(d["bias"], dtype=np.int64)[:F]
C, X, Y = fm.shape
K = W.shape[-1]
p = K // 2
sx, sy = d["stride"]
pad = np.zeros((C, X + 2 * p, Y + 2 * p), dtype=np.int64)
pad[:, p:p + X, p:p + Y] = fm
S1 = np.zeros((F, X, Y), dtype=np.int64)
for f in range(F):
    acc = np.full((X, Y), b[f], dtype=np.int64)
    for c in range(C):
        k = W[c, f].T
        for i in range(K):
            for j in range(K):
                acc += k[i][j] * pad[c, i:i + X, j:j + Y]
    S1[f] = acc
wrap = lambda a: ((a + (1 << (bits - 1))) % (1 << bits)) - (1 << (bits - 1))   # noqa: E731
where = {}
for f in range(F):
    for cx in range(X):
        for cy in range(Y):
            where.setdefault(int(wrap(S1[f, cx, cy])), []).append((f, cx, cy))
order = d["output_order"]
if order and isinstance(order[0], list) and (not order[0] or isinstance(order[0][0], (list, type(None)))):
    order = [q for r in order for q in r]
lines = [l.strip() for l in open(os.path.join(sim, "demo", f"layer_{layer}_0", "output.txt")) if l.strip()]
print(f"input {C}x{X}x{Y}, stride {sx}x{sy}, {len(lines)} words, {spw} slots per word")
print("word slot | expected (f, cx, cy)   | DUT value -> (f, cx, cy)")
for wi in range(first, min(first + count, len(lines))):
    word = int(lines[wi], 2) if not set(lines[wi]) - {"0", "1"} else None
    for s in range(spw):
        idx = spw * wi + s
        pos = order[idx] if idx < len(order) else None
        exp = f"({pos[0]:2},{pos[1] * sx:2},{pos[2] * sy:2})" if pos else "   padding  "
        if word is None:
            got = "X"
        else:
            v = (word >> (bits * s)) & ((1 << bits) - 1)
            v = v - (1 << bits) if v >= 1 << (bits - 1) else v
            hits = where.get(v, [])
            got = f"{v:8} -> " + ("?" if not hits else "*" if len(hits) > 1 else f"({hits[0][0]:2},{hits[0][1]:2},{hits[0][2]:2})")
        print(f"{wi:4} {s:4} | {exp:22} | {got}")
