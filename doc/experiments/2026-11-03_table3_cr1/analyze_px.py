"""analyze_px.py <sim dir> <layer>: which inputs explain the wrong conv outputs (Difference lines of cocotb_sim.log)."""
import itertools, os, pickle, re, sys
import numpy as np
sim, layer = sys.argv[1], int(sys.argv[2])
d = pickle.load(open(os.path.join(sim, f"verify_layer{layer}.pkl"), "rb"))
fm = np.array(d["fmap"], dtype=np.int64); W = np.array(d["weights"], dtype=np.int64); F = d["filters"]
C, X, Y = fm.shape
pad = np.zeros((C, X + 2, Y + 2), dtype=np.int64); pad[:, 1:1 + X, 1:1 + Y] = fm
wrong = {}
for m in re.finditer(r"Difference found at f = (\d+), x = (\d+), y= (\d+): reference (-?\d+), DUT (-?\d+)", open(os.path.join(sim, "cocotb_sim.log"), errors="replace").read()):
    f, x, y, r, u = map(int, m.groups())
    wrong.setdefault((x, y), {})[f] = (r, u)
print("conv input", fm.shape, "zeros %.1f%%" % (100 * (fm == 0).mean()), "wrong pixels", {k: len(v) for k, v in wrong.items()})
for (x, y), fs in wrong.items():
    delta = np.array([fs[f][1] - fs[f][0] if f in fs else 0 for f in range(F)])
    print(f"pixel x={x} y={y}: delta[0:8] = {delta[:8]}")
    # window inputs fm[c][x+i-1][y+j-1], term T[f][c][i][j] = W[c][f][j][i] * input
    win = pad[:, x:x + 3, y:y + 3]                      # [c][i][j]
    print("  window inputs (per channel, i rows, j cols) zeros:", int((win == 0).sum()), "of", win.size)
    T = np.einsum("cfji,cij->fcij", W[:, :F], win)      # contribution of each input to each filter
    # 1) one window position (i, j) with all channels replaced: solve sum_c W[c][f][j][i] * e[c] = delta
    for i, j in itertools.product(range(3), range(3)):
        A = W[:, :F, j, i].T.astype(float)              # [f][c]
        e, *_ = np.linalg.lstsq(A, delta.astype(float), rcond=None)
        res = np.abs(A @ np.rint(e) - delta).max()
        if res == 0:
            print(f"  EXACT: position i={i} j={j} (input x={x+i-1}, y={y+j-1}): channel errors {np.rint(e).astype(int)}; DUT used {(win[:, i, j] + np.rint(e)).astype(int)} instead of {win[:, i, j]}")
    # 2) subsets of terms dropped / doubled: channel groups of 4 x kernel rows / cols / single positions
    groups = [list(range(g, g + 4)) for g in range(0, C, 4)] + [list(range(C))]
    sets = []
    for gi, g in enumerate(groups):
        for i in range(3):
            sets.append((f"group {gi} i={i}", [(c, i, j) for c in g for j in range(3)]))
        for j in range(3):
            sets.append((f"group {gi} j={j}", [(c, i, j) for c in g for i in range(3)]))
        for i, j in itertools.product(range(3), range(3)):
            sets.append((f"group {gi} i={i} j={j}", [(c, i, j) for c in g]))
        sets.append((f"group {gi} all", [(c, i, j) for c in g for i in range(3) for j in range(3)]))
    for name, s in sets:
        tot = sum(T[:, c, i, j] for c, i, j in s)
        for sign, word in ((-1, "missing"), (1, "doubled")):
            if np.array_equal(sign * tot, delta):
                print(f"  EXACT: {word} terms {name}")
