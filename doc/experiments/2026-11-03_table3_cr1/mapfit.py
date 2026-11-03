"""mapfit.py <pes.json> <verify pkl>: match each PE pass's 16 psum outputs to partial sums (output x, y, channel group,
kernel rows, filters) computed with numpy."""
import itertools, json, pickle, sys
import numpy as np
A = json.load(open(sys.argv[1])); d = pickle.load(open(sys.argv[2], "rb"))
fm = np.array(d["fmap"], dtype=np.int64); W = np.array(d["weights"], dtype=np.int64); F = d["filters"]
C, X, Y = fm.shape
pad = np.zeros((C, X + 2, Y + 2), dtype=np.int64); pad[:, 1:1 + X, 1:1 + Y] = fm
# partial[f, x, y, g, j] = sum over channels of group g, kernel columns i, of kernel row j
part = np.zeros((F, X, Y, C // 4, 3), dtype=np.int64)
for g in range(C // 4):
    for j in range(3):
        for i in range(3):
            for c in range(4 * g, 4 * g + 4):
                part[:, :, :, g, j] += W[c, :F, j, i][:, None, None] * pad[c, i:i + X, j:j + Y][None]
jsets = [(0,), (1,), (2,), (0, 1), (1, 2), (0, 1, 2)]
fmaps = [(f0, s) for f0 in range(0, 17) for s in (1, 2)]
index = {}
for (x, y, g) in itertools.product(range(X), range(Y), range(C // 4)):
    for js in jsets:
        tot = part[:, x, y, g, list(js)].sum(axis=1)
        for f0, s in fmaps:
            fs = [f0 + s * k for k in range(16)]
            if fs[-1] < F:
                index.setdefault(tuple(int(v) for v in tot[fs]), []).append((x, y, g, js, f0, s))
pes = sys.argv[3].split(",") if len(sys.argv) > 3 else A["pes"]
for k in pes:
    ps = [v for _, v in A["log"][k]["psum"]]
    print("PE", k)
    for p in range(int(sys.argv[4]) if len(sys.argv) > 4 else 8):
        vec = tuple(ps[16 * p:16 * p + 16])
        print(f"  pass {p:3d}: {index.get(vec, 'no match')[:3]}  first {vec[:4]}")
