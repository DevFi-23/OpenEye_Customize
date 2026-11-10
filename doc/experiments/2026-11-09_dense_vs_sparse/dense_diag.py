"""dense_diag.py <sim dir> [layer]: which weights / channels a wrong DUT output map was computed with.

Reads verify_layer<layer>.pkl (OPENEYE_DUMP_VERIFY=1) and demo/layer_0_<layer>/output.txt like
2026-11-07_bug41_stride/window_map.py. For every DUT filter f it tries every source filter f2, every subset of input
channels, the kernel as is or transposed, with and without bias, and prints the hypotheses that explain the most output
positions (stride-1 "same" convolution of the raw integers). Run from the repository root."""
import itertools
import os
import pickle
import sys

import numpy as np

sim, layer = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0
d = pickle.load(open(os.path.join(sim, f"verify_layer{layer}.pkl"), "rb"))
bits, spw = d["psum_bits"], d["dma_bits"] // 32
fm = np.array(d["fmap"], dtype=np.int64)
W = np.array(d["weights"], dtype=np.int64)        # [c][f][ky][kx]
F = d["filters"]
b = np.array(d["bias"], dtype=np.int64)[:F]
C, X, Y = fm.shape
K = W.shape[-1]
p = K // 2
pad = np.zeros((C, X + 2 * p, Y + 2 * p), dtype=np.int64)
pad[:, p:p + X, p:p + Y] = fm


def conv(c, f2, transpose):
    k = W[c, f2] if transpose else W[c, f2].T
    acc = np.zeros((X, Y), dtype=np.int64)
    for i in range(K):
        for j in range(K):
            acc += k[i][j] * pad[c, i:i + X, j:j + Y]
    return acc


T = {(c, f2, t): conv(c, f2, t) for c in range(C) for f2 in range(F) for t in (0, 1)}
order = d["output_order"]
if order and isinstance(order[0], list) and (not order[0] or isinstance(order[0][0], (list, type(None)))):
    order = [pos for rep in order for pos in rep]
lines = [l.strip() for l in open(os.path.join(sim, "demo", f"layer_{layer}_0", "output.txt")) if l.strip()]
dut = np.full((F, X, Y), np.iinfo(np.int64).min, dtype=np.int64)
for wi, line in enumerate(lines):
    for i in range(spw):
        idx = spw * wi + i
        pos = order[idx] if idx < len(order) else None
        if pos is None:
            continue
        chunk = line[len(line) - bits * (i + 1):len(line) - bits * i]
        if set(chunk) - {"0", "1"}:
            continue
        v = int(chunk, 2)
        f, x, y = pos
        if x < X and y < Y:
            dut[f, x, y] = v - (1 << bits) if v >= 1 << (bits - 1) else v
ref = np.array([[[None]]])
print(f"input {C}x{X}x{Y}, kernel {K}, {F} filters, decoded {(dut != np.iinfo(np.int64).min).sum()} of {F * X * Y}")
for f in range(F):
    good = dut[f] != np.iinfo(np.int64).min
    full = sum(T[(c, f, 0)] for c in range(C)) + b[f]
    print(f"filter {f}: {int((full == dut[f])[good].sum())} of {int(good.sum())} decoded positions right")
    best = []
    for f2 in range(F):
        for t in (0, 1):
            for n in range(1, C + 1):
                for sub in itertools.combinations(range(C), n):
                    s = sum(T[(c, f2, t)] for c in sub)
                    for bias in (0, 1):
                        m = (s + (b[f] if bias else 0)) == dut[f]
                        best.append((int(m[good].sum()), f2, t, sub, bias, m))
    best.sort(key=lambda r: -r[0])
    for hits, f2, t, sub, bias, m in best[:3]:
        print(f"   {hits:3d} hits: weights of filter {f2}{' transposed' if t else ''}, channels {list(sub)}, bias {bias}")
    hits, f2, t, sub, bias, m = best[0]
    if hits < good.sum():
        print("     positions not explained (x,y):", [(x, y) for x in range(X) for y in range(Y) if good[x, y] and not m[x, y]][:24])
