"""Bug #19 analysis: which activations did the DUT effectively use? usage: analyze.py dump.pkl"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], "rb"))
x = np.array(d["fmap"], dtype=np.int64).reshape(-1)
W = np.array(d["weights"], dtype=np.int64)            # [filter][k]
b = np.array(d["bias"], dtype=np.int64).reshape(-1)
ref = np.array(d["ref"], dtype=np.int64)
dut = np.array(d["dut"], dtype=np.int64)
N, K = W.shape
print(f"K={K}, N={N}; numpy ref == testbench ref: {np.array_equal(W @ x + b, ref)}; outputs wrong: {(dut != ref).sum()}/{N}")
diff = dut - ref
print("DUT - ref:", diff.tolist())


def test(name, xp):
    pred = W @ xp + b
    print(f"  {name:62s} -> matches DUT in {(pred == dut).sum()}/{N} outputs")


hi = np.arange(512, K)
x0 = x.copy(); x0[hi] = 0
test("H0: activations >= 512 read as 0", x0)
x1 = x.copy(); x1[hi] = x[hi - 512]
test("H1: activation k >= 512 read as x[k-512]", x1)
x2 = x.copy(); x2[hi - 512] = x[hi]
test("H2: x[k-512] overwritten by x[k] (k >= 512)", x2)
x3 = x2.copy(); x3[hi] = 0
test("H3: H2 and activations >= 512 read as 0", x3)
x4 = x2.copy(); x4[hi] = x[hi]
test("H4: H2 but activations >= 512 still correct", x4)

# Least squares on a candidate set of positions: diff = W[:, P] @ delta
for name, P in (("512..K-1", list(range(512, K))), ("0..K-513 and 512..K-1", list(range(0, K - 512)) + list(range(512, K)))):
    if len(P) > N:
        print(f"  LSQ {name}: {len(P)} unknowns > {N} equations, skipped")
        continue
    A = W[:, P].astype(float)
    delta, *_ = np.linalg.lstsq(A, diff.astype(float), rcond=None)
    res = np.abs(A @ delta - diff).max()
    print(f"  LSQ on positions {name}: max residual {res:.3g}; delta = {np.round(delta, 2).tolist()}")
    if res < 1e-6:
        xe = x[P] + np.round(delta).astype(np.int64)
        print(f"     effective activations at those positions: {xe.tolist()}")
        print(f"     true activations:                         {x[P].tolist()}")
        lookup = {}
        for p, v in zip(P, xe):
            lookup[p] = [int(i) for i in np.where(x == v)[0][:6]]
        print(f"     indices with the same value (first 6): {lookup}")
