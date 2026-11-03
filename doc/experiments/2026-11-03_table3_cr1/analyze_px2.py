"""analyze_px2.py <sim dir> <layer>: broader hypotheses for wrong conv outputs."""
import itertools, os, pickle, re, sys
import numpy as np
sim, layer = sys.argv[1], int(sys.argv[2])
d = pickle.load(open(os.path.join(sim, f"verify_layer{layer}.pkl"), "rb"))
fm = np.array(d["fmap"], dtype=np.int64); W = np.array(d["weights"], dtype=np.int64); F = d["filters"]
b = np.array(d["bias"], dtype=np.int64)[:F]
C, X, Y = fm.shape
P = 3
pad = np.zeros((C, X + 2 * P, Y + 2 * P), dtype=np.int64); pad[:, P:P + X, P:P + Y] = fm
def inp(c, x, y):  # input with zero padding, x, y may be out of range
    return pad[c, x + P, y + P]
wrong = {}
for m in re.finditer(r"Difference found at f = (\d+), x = (\d+), y= (\d+): reference (-?\d+), DUT (-?\d+)", open(os.path.join(sim, "cocotb_sim.log"), errors="replace").read()):
    f, x, y, r, u = map(int, m.groups()); wrong.setdefault((x, y), {})[f] = (r, u)
groups = {f"g{g}": list(range(4 * g, 4 * g + 4)) for g in range(C // 4)}
subsets = {}
for n in range(1, len(groups) + 1):
    for combo in itertools.combinations(groups, n):
        subsets["+".join(combo)] = sum((groups[g] for g in combo), [])
def term(c, f, i, j, x, y):  # kernel column i (x offset), row j (y offset)
    return W[c, f, j, i] * inp(c, x + i - 1, y + j - 1)
# partial sums per channel set at every pixel: Ps[name][f][x][y]
def partial(chs, x, y, f):
    return sum(term(c, f, i, j, x, y) for c in chs for i in range(3) for j in range(3))
for (x0, y0), fs in wrong.items():
    ref = np.array([fs[f][0] for f in range(F)]); dut = np.array([fs[f][1] for f in range(F)])
    num = np.array([b[f] + partial(range(C), x0, y0, f) for f in range(F)])
    print(f"pixel ({x0},{y0}): reference == numpy: {np.array_equal(ref, num)}")
    delta = dut - ref
    hits = []
    for sname, chs in subsets.items():
        # A: kernel column i of these channels reads input column xs instead of x0+i-1 (all rows)
        for i in range(3):
            for xs in range(-1, X + 1):
                if xs == x0 + i - 1: continue
                cand = np.array([sum(W[c, f, j, i] * (inp(c, xs, y0 + j - 1) - inp(c, x0 + i - 1, y0 + j - 1)) for c in chs for j in range(3)) for f in range(F)])
                if np.array_equal(cand, delta): hits.append(f"column i={i} of {sname} reads x={xs}")
        # B: kernel row j of these channels reads input row ys instead
        for j in range(3):
            for ys in range(-1, Y + 1):
                if ys == y0 + j - 1: continue
                cand = np.array([sum(W[c, f, j, i] * (inp(c, x0 + i - 1, ys) - inp(c, x0 + i - 1, y0 + j - 1)) for c in chs for i in range(3)) for f in range(F)])
                if np.array_equal(cand, delta): hits.append(f"row j={j} of {sname} reads y={ys}")
        # C: partial sum of these channels taken from / added from another pixel
        own = np.array([partial(chs, x0, y0, f) for f in range(F)])
        if np.array_equal(-own, delta): hits.append(f"partial of {sname} missing")
        for xq in range(X):
            for yq in range(Y):
                if (xq, yq) == (x0, y0): continue
                other = np.array([partial(chs, xq, yq, f) for f in range(F)])
                if np.array_equal(other - own, delta): hits.append(f"partial of {sname} taken from pixel ({xq},{yq})")
                if np.array_equal(other, delta): hits.append(f"partial of {sname} of pixel ({xq},{yq}) added")
        # D: one kernel position (i, j) of these channels uses the input of another window position
        for i, j in itertools.product(range(3), range(3)):
            for xs in range(x0 - 3, x0 + 4):
                for ys in range(y0 - 3, y0 + 4):
                    if (xs, ys) == (x0 + i - 1, y0 + j - 1): continue
                    cand = np.array([sum(W[c, f, j, i] * (inp(c, xs, ys) - inp(c, x0 + i - 1, y0 + j - 1)) for c in chs) for f in range(F)])
                    if np.array_equal(cand, delta): hits.append(f"position i={i} j={j} of {sname} reads ({xs},{ys})")
    print("  hits:", hits[:20] if hits else "none")
    if np.array_equal(delta, b): print("  bias doubled")
    if np.array_equal(delta, -b): print("  bias missing")
