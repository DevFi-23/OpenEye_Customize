"""grid39.py [out.json] [kernel]: bug #39 over a grid of one-layer convs (kernel x kernel, default 3, stride 1) and
platforms, Python only.
For every configuration: the weight sets the stream carries (needed_wght_transmissions) with the formula before the fix
(branch "more than 16 filters per calculation": ceil(channels / channel_div_trans)) and with the current one, against
the sets the RTL reads (needed_wght_cycles weight passes x iact_transmissions_pe channel batches)."""
import itertools, json, os, sys
os.environ.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "2", "CLUSTER_COLUMNS": "2", "DATA_PSUM_BITWIDTH": "20",
                   "TRANS_WORDS": "8", "BRANCHES": "1", "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "256", "RAM_CELLS": "32",
                   "DMA_BITWIDTH": "64", "OPENEYE_PAD_CHANNELS": "0", "NUM_GLB_IACT": "1"})
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "src"))
import math
import tensorflow as tf
from open_eye import data_create, open_eye_parameters as oep, layer_parameters as lp

K = int(sys.argv[2]) if len(sys.argv) > 2 else 3
PLATFORMS = [(cr, gp, gw) for cr in (1, 2, 4, 8) for gp in (2, 4) for gw in (3, 4)]
SHAPES = [(8, 4), (28, 28)]
CHANNELS = [1, 2, 3, 4, 5, 6, 8, 16, 32, 64]
FILTERS = [4, 8, 16, 24, 32, 48, 64, 96, 128]
rows = []
models = {}
for (w, h), ch, nf in itertools.product(SHAPES, CHANNELS, FILTERS):
    tf.keras.utils.set_random_seed(1)
    km = data_create.create_layer("Convolution_Single", nf, K, K, w, h, 1, ch, 10)
    models[(w, h, ch, nf)] = [l for l in km.layers if not isinstance(l, tf.keras.layers.Flatten)][0]
for cr, gp, gw in PLATFORMS:
    os.environ.update({"CLUSTER_ROWS": str(cr), "NUM_GLB_PSUM": str(gp), "NUM_GLB_WGHT": str(gw)})
    params = oep.get_oep(1)
    for (w, h, ch, nf), layer in models.items():
        try:
            L = lp.LayerParameters([0], layer, params, 0, 1)
        except Exception as e:
            rows.append({"cr": cr, "gp": gp, "gw": gw, "w": w, "h": h, "ch": ch, "nf": nf, "k": K, "error": type(e).__name__})
            continue
        kpc = L.different_kernels_per_calculation
        many = ((L.filters * L.used_iact_per_PE) // kpc <= params.Wghts_per_PE) and (L.filters // kpc > 16)
        needed = L.needed_wght_cycles * L.iact_transmissions_pe
        new = L.needed_wght_transmissions
        old = math.ceil(L.channels / L.channel_div_trans) * L.wght_transmissions_glb if many else new
        rows.append({"cr": cr, "gp": gp, "gw": gw, "w": w, "h": h, "ch": ch, "nf": nf, "k": K, "kpc": kpc, "psum_pe": L.used_psum_per_PE,
                     "branch": "many" if many else ("fit" if (L.filters * L.used_iact_per_PE) // kpc <= params.Wghts_per_PE else "tile"),
                     "used_ch": L.used_channels, "div": L.channel_div_trans, "batches": L.iact_transmissions_pe,
                     "passes": L.needed_wght_cycles, "needed": needed, "old": old, "new": new})
out = sys.argv[1] if len(sys.argv) > 1 else "grid39.json"
json.dump(rows, open(out, "w"))
ok = [r for r in rows if "error" not in r]
print(f"{len(rows)} configurations, {len(rows) - len(ok)} not buildable")
print("old formula wrong:", sum(r["old"] != r["needed"] for r in ok), " current wrong:", sum(r["new"] != r["needed"] for r in ok))
