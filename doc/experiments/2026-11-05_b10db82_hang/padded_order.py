"""padded_order.py <sim dir> W H CH NF [CR]: decode the DUT output of a dev run with the reference order of the dev
Python computed for the filter count padded to passes x psums per PE x kernels per calculation, compare with numpy.
Shows whether the RTL itself computes the layer right (bug #40 question)."""
import os, sys, pickle, math, tempfile
import numpy as np
d, W, H, CH, NF = sys.argv[1], *map(int, sys.argv[2:6])
CR = int(sys.argv[6]) if len(sys.argv) > 6 else 2
os.environ.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "2", "CLUSTER_COLUMNS": "2", "CLUSTER_ROWS": str(CR),
                   "NUM_GLB_PSUM": "4", "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
                   "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "1024", "RAM_CELLS": "32", "DMA_BITWIDTH": "64", "NUM_GLB_IACT": "1",
                   "OPENEYE_PAD_CHANNELS": "0", "LOGGER_LEVEL": "30"})
sys.path.insert(0, "src")
import tensorflow as tf
from open_eye import data_create, open_eye_parameters as oep, layer_parameters as lp, test_utils_main as tum
params = oep.get_oep(1)
tf.keras.utils.set_random_seed(1)
km = data_create.create_layer("Convolution_Single", NF, 3, 3, W, H, 1, CH, 10)
layer = [l for l in km.layers if not isinstance(l, tf.keras.layers.Flatten)][0]
L = lp.LayerParameters([0], layer, params, 0, 1)
padded = L.needed_wght_cycles * L.used_psum_per_PE * L.different_kernels_per_calculation
print(f"filters {NF}: kpc {L.different_kernels_per_calculation}, psums/PE {L.used_psum_per_PE}, passes {L.needed_wght_cycles}, "
      f"padded {padded}, psum_output_words {L.psum_output_words}")
dump = pickle.load(open(os.path.join(d, "verify_layer0.pkl"), "rb"))
bits = dump["psum_bits"]
fm = np.array(dump["fmap"][0] if np.array(dump["fmap"]).ndim == 4 else dump["fmap"], dtype=np.int64)
Wt = np.array(dump["weights"][0] if np.array(dump["weights"]).ndim == 5 else dump["weights"], dtype=np.int64)
F = dump["filters"]; b = np.array(dump["bias"], dtype=np.int64)[:F]
C, X, Y = fm.shape; K = Wt.shape[-1]; p = K // 2
pad = np.zeros((C, X + 2 * p, Y + 2 * p), dtype=np.int64); pad[:, p:p + X, p:p + Y] = fm
out = np.zeros((F, X, Y), dtype=np.int64)
for f in range(F):
    acc = np.full((X, Y), b[f], dtype=np.int64)
    for c in range(C):
        k = Wt[c, f].T
        for i in range(K):
            for j in range(K):
                acc += k[i][j] * pad[c, i:i + X, j:j + Y]
    out[f] = acc
out = ((out & ((1 << bits) - 1)) ^ (1 << (bits - 1))) - (1 << (bits - 1))
L.filters = padded
calc = {f: [[int(out[f, x, y]) if f < F else 0 for y in range(Y)] for x in range(X)] for f in range(padded)}
tmp = tempfile.NamedTemporaryFile("w", delete=False)
order = tum.calculate_conv_serial(params, L, calc, tmp)
tmp.close()
lines = [l.strip() for l in open(os.path.join(d, "demo", "layer_0_0", "output.txt")) if l.strip()]
vals = []
for l in lines:
    v = int(l, 2)
    for i in range(2):
        x = (v >> (bits * i)) & ((1 << bits) - 1)
        vals.append(x - (1 << bits) if x >= 1 << (bits - 1) else x)
print(f"padded order: {len(order)} slots = {len(order) // 2} words; DUT sent {len(vals)} slots = {len(lines)} words")
eq = ne = padslots = 0; seen = set(); first_bad = []
for pos, v in zip(order, vals):
    if pos is None or pos[1] >= X or pos[2] >= Y:
        continue
    f, x, y = pos
    if f >= F:
        padslots += 1; continue
    seen.add((f, x, y))
    if out[f, x, y] == v:
        eq += 1
    else:
        ne += 1
        if len(first_bad) < 5:
            first_bad.append((f, x, y, int(out[f, x, y]), v))
print(f"real outputs in what the DUT sent: equal {eq}, differ {ne}, padding slots {padslots}; "
      f"covered {len(seen)} of {F * X * Y} outputs; first differences {first_bad}")
