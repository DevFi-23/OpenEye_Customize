"""branch_scan.py: for which conv layers does the converter branch that upstream 12340ab removed act in dev?
Simulates the iact_converter_x sequence of OpenEye_FPGA.v (non-FC path) from dev's LayerParameters registers over
8,208 layers; SCAN_CC=1 for one cluster column (default 2). Prints the kernel-group statistics and the hits."""
import os, itertools, logging
logging.disable(logging.CRITICAL)
base = {"NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4", "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8",
        "BRANCHES": "1", "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "64", "DMA_BITWIDTH": "64", "RAM_CELLS": "32",
        "CLUSTER_COLUMNS": os.environ.get("SCAN_CC", "2"), "OPENEYE_ALLOW_UNSUPPORTED": "1"}
os.environ.update(base)
import tensorflow as tf
from open_eye import layer_parameters as lp, open_eye_parameters as oep
hits, total, errors = [], 0, 0
multi, near = 0, []
for cr, glbp in [(1, 2), (1, 4), (2, 2), (2, 4), (4, 4), (8, 4)]:
    os.environ["CLUSTER_ROWS"] = str(cr); os.environ["NUM_GLB_PSUM"] = str(glbp)
    params = oep.get_oep(1)
    CC = params.Clusters_X
    for w, h, c, f in itertools.product([4, 6, 7, 8, 12, 14, 16, 28], [2, 4, 7, 8, 14], [1, 2, 4, 8, 16, 32], [2, 4, 8, 16, 32, 64]):
        if h > w * 2:
            continue
        try:
            layer = tf.keras.models.Sequential([tf.keras.Input((w, h, c)), tf.keras.layers.Conv2D(f, (3, 3), padding="same")]).layers[0]
            p = lp.LayerParameters([0], layer, params, 0, 1)
        except Exception:
            errors += 1; continue
        total += 1
        xpc, add_up, kpc = int(p.iact_x_per_cluster), int(p.iact_x_add_up), int(p.different_kernels_per_calculation)
        reps, ycls = int(p.iact_x_line_repetitions), int(p.used_Y_cluster)
        if kpc == 1 or xpc <= 0:
            continue
        multi += 1
        x, fired = 0, False
        for k in range(kpc):
            for _ in range(10000):
                if (x + CC * xpc) * reps >= add_up * ycls:
                    near.append(((x + xpc) >= add_up, xpc < add_up, x, xpc, add_up, reps, ycls))
                    if (x + xpc) >= add_up and xpc < add_up:
                        fired = True; x = xpc
                    else:
                        x = 0
                    break
                x += CC * xpc
        if fired:
            hits.append((cr, glbp, w, h, c, f, xpc, add_up, kpc, reps, ycls))
import collections
print("kpc>1 layers", multi, "wrap events", len(near), collections.Counter((a, b) for a, b, *_ in near))
print("examples", sorted(set(n[2:] for n in near))[:12])
print("layers", total, "errors", errors, "branch fires in", len(hits))
for hcase in hits[:40]:
    print("CR %d GLBP %d  %dx%dx%d->%d  xpc %d add_up %d kpc %d reps %d ycls %d" % hcase)
