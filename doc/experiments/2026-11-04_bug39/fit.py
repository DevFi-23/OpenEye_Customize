"""fit.py <sim dir>: DUT output of a one-layer conv decoded as verify_conv_output does; for every wrong filter, the
effective 7x7 kernel (least squares over all output pixels) and its match with the real kernels."""
import os, pickle, sys
import numpy as np
d = sys.argv[1]
dump = pickle.load(open(os.path.join(d, "verify_layer0.pkl"), "rb"))
bits, spw = dump["psum_bits"], dump["dma_bits"] // 32
fm = np.array(dump["fmap"], dtype=np.int64); W = np.array(dump["weights"], dtype=np.int64)
F = dump["filters"]; b = np.array(dump["bias"], dtype=np.int64)[:F]
C, X, Y = fm.shape
order = dump["output_order"]
if order and isinstance(order[0], list) and (not order[0] or isinstance(order[0][0], (list, type(None)))):
    order = [p for rep in order for p in rep]
lines = [l.strip() for l in open(os.path.join(d, "demo", "layer_0_0", "output.txt")) if l.strip()]
D = np.full((F, X, Y), np.nan)
for wi, line in enumerate(lines):
    word = int(line, 2)
    for i in range(spw):
        idx = spw * wi + i
        pos = order[idx] if idx < len(order) else None
        if pos is None: continue
        v = (word >> (bits * i)) & ((1 << bits) - 1)
        D[tuple(pos)] = v - (1 << bits) if v >= 1 << (bits - 1) else v
R = 3
pad = np.zeros((X + 2 * R, Y + 2 * R)); pad[R:R + X, R:R + Y] = fm[0]
A = np.stack([pad[R + i:R + i + X, R + j:R + j + Y].ravel() for i in range(-R, R + 1) for j in range(-R, R + 1)], 1)
def expected(f):
    k = W[0, f].T; p = np.zeros((X + 2, Y + 2)); p[1:1 + X, 1:1 + Y] = fm[0]
    return b[f] + sum(k[i][j] * p[i:i + X, j:j + Y] for i in range(3) for j in range(3))
for f in range(F):
    if np.array_equal(D[f], expected(f)): continue
    y = (D[f] - b[f]).ravel()
    coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
    K = np.round(coef).reshape(2 * R + 1, 2 * R + 1).astype(int)
    fit = np.abs(A @ np.round(coef) - y).max()
    nz = [(i - R, j - R, K[i, j]) for i in range(2 * R + 1) for j in range(2 * R + 1) if K[i, j]]
    # which real kernel (any filter, normal / transposed) equals the non-zero part
    print(f"f {f}: fit max err {fit:.1f}; effective taps (dx, dy, w): {nz[:12]}")
    print(f"      real kernel f{f} (x rows):", W[0, f].T.tolist())
    if f > F // 2 + 1: break
print("--- effective kernel of every wrong filter against all real kernels")
for f in range(F):
    if np.array_equal(D[f], expected(f)): continue
    coef = np.round(np.linalg.lstsq(A, (D[f] - b[f]).ravel(), rcond=None)[0]).reshape(2 * R + 1, 2 * R + 1).astype(int)
    K3 = coef[R - 1:R + 2, R - 1:R + 2]
    hits = [g for g in range(F) if np.array_equal(K3, W[0, g].T)]
    hits_t = [g for g in range(F) if np.array_equal(K3, W[0, g])]
    rows = [g for g in range(F) for r in range(3) if any(np.array_equal(K3[i], W[0, g].T[r]) for i in range(3))]
    print(f"f {f}: same as kernel of {hits} (transposed {hits_t}); rows shared with filters {sorted(set(rows))}")
