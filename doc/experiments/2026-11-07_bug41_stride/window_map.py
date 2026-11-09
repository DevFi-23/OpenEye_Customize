"""window_map.py <sim dir> [layer]: which input window (layer: the layer number, its output in demo/layer_<n>_0) every DUT output of a strided convolution was computed on.

Reads verify_layer<layer>.pkl (OPENEYE_DUMP_VERIFY=1) and demo/layer_0_<layer>/output.txt of a simulation, computes the
stride-1 "same" convolution of the raw integers with numpy (S1[f][cx][cy], window centred at input pixel (cx, cy), zero
padding kernel // 2, as tools/verify_conv_output.py) and prints, per output position (x, y), the window centres whose
S1 value equals the DUT value in every filter, next to the centres the testbench reference uses. Run from the repository
root: venv/bin/python doc/experiments/2026-11-07_bug41_stride/window_map.py test/.temp/b39_s2"""
import os
import pickle
import sys
from collections import Counter

import numpy as np

sim, layer = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0
d = pickle.load(open(os.path.join(sim, f"verify_layer{layer}.pkl"), "rb"))
bits, spw = d["psum_bits"], d["dma_bits"] // 32
fm = np.array(d["fmap"], dtype=np.int64)          # [c][x][y]
W = np.array(d["weights"], dtype=np.int64)        # [c][f][ky][kx]
F = d["filters"]
b = np.array(d["bias"], dtype=np.int64)[:F]
C, X, Y = fm.shape
K = W.shape[-1]
p = K // 2
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
ref = d["reference"]
if isinstance(ref, dict):
    ref = [ref[k] for k in sorted(ref)]
ref = np.array(ref, dtype=np.int64)
order = d["output_order"]
if order and isinstance(order[0], list) and (not order[0] or isinstance(order[0][0], (list, type(None)))):
    order = [pos for rep in order for pos in rep]
lines = [l.strip() for l in open(os.path.join(sim, "demo", f"layer_{layer}_0", "output.txt")) if l.strip()]
dut = {}
for wi, line in enumerate(lines):
    if set(line) - {"0", "1"}:
        continue
    word = int(line, 2)
    for i in range(spw):
        idx = spw * wi + i
        pos = order[idx] if idx < len(order) else None
        if pos is None:
            continue
        v = (word >> (bits * i)) & ((1 << bits) - 1)
        dut.setdefault(tuple(pos), v - (1 << bits) if v >= 1 << (bits - 1) else v)
OX, OY = ref.shape[1], ref.shape[2]


def centres(values):
    """Window centres (cx, cy) whose S1 equals values[f] for every filter f."""
    return [(cx, cy) for cx in range(X) for cy in range(Y) if all(S1[f, cx, cy] == values[f] for f in range(F))]


print(f"input {C}x{X}x{Y}, kernel {K}, stride {d['stride']}, output {OX}x{OY}, {F} filters, decoded {len(dut)}")
rows, hits = [], Counter()
for x in range(OX):
    for y in range(OY):
        dv = [dut.get((f, x, y)) for f in range(F)]
        rc, dc = centres(ref[:, x, y]), (centres(dv) if None not in dv else "missing")
        ok = all(dut.get((f, x, y)) == ref[f, x, y] for f in range(F))
        hits[ok] += 1
        print(f"  out ({x},{y}): reference window {rc}, DUT window {dc}{'  OK' if ok else ''}")
print(f"positions equal to the reference in every filter: {hits[True]} of {OX * OY}")
