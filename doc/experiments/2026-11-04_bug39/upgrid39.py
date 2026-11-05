"""upgrid39.py <upstream tree> [out.json]: the check of grid39.py (weight sets in the stream against weight passes x
channel batches) with the Python of an upstream tree (its LayerParameters takes the DAG topology of the model: built
with the tree's own OpenEye_FPGA_tb.build_layer_topology). 3 x 3 kernels, the grid and platforms of grid39.py."""
import itertools, json, os, sys
tree = os.path.abspath(sys.argv[1])
os.environ.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "2", "CLUSTER_COLUMNS": "2", "DATA_PSUM_BITWIDTH": "20",
                   "TRANS_WORDS": "8", "BRANCHES": "1", "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "256", "RAM_CELLS": "32",
                   "DMA_BITWIDTH": "64", "NUM_GLB_IACT": "1"})
os.environ.setdefault("LOGGER_LEVEL", "30")   # read when the testbench module is imported
sys.path[:0] = [os.path.join(tree, "src"), os.path.join(tree, "test", "cocotb_fpga")]
import tensorflow as tf
from open_eye import data_create, open_eye_parameters as oep, layer_parameters as lp
import OpenEye_FPGA_tb as tb

PLATFORMS = [(cr, gp, gw) for cr in (1, 2, 4, 8) for gp in (2, 4) for gw in (3, 4)]
SHAPES = [(8, 4), (28, 28)]
CHANNELS = [1, 2, 3, 4, 5, 6, 8, 16, 32, 64]
FILTERS = [4, 8, 16, 24, 32, 48, 64, 96, 128]
models = {}
for (w, h), ch, nf in itertools.product(SHAPES, CHANNELS, FILTERS):
    tf.keras.utils.set_random_seed(1)
    km = data_create.create_net("Convolution_Single", nf, 3, 3, w, h, 1, ch, 10)
    models[(w, h, ch, nf)] = (km, tb.build_layer_topology(km))
rows = []
for cr, gp, gw in PLATFORMS:
    os.environ.update({"CLUSTER_ROWS": str(cr), "NUM_GLB_PSUM": str(gp), "NUM_GLB_WGHT": str(gw)})
    params = oep.get_oep(1)
    for (w, h, ch, nf), (km, rel) in models.items():
        layers = [l for l in km.layers if not isinstance(l, tf.keras.layers.Flatten)]
        try:
            L = lp.LayerParameters({}, layers[0], params, rel, 0)
        except Exception as e:
            rows.append({"cr": cr, "gp": gp, "gw": gw, "w": w, "ch": ch, "nf": nf, "error": f"{type(e).__name__}: {e}"[:120]})
            continue
        rows.append({"cr": cr, "gp": gp, "gw": gw, "w": w, "ch": ch, "nf": nf, "kpc": L.different_kernels_per_calculation,
                     "psum_pe": L.used_psum_per_PE, "batches": L.iact_transmissions_pe, "passes": L.needed_wght_cycles,
                     "needed": L.needed_wght_cycles * L.iact_transmissions_pe, "sets": L.needed_wght_transmissions})
json.dump(rows, open(sys.argv[2] if len(sys.argv) > 2 else "upgrid39.json", "w"))
ok = [r for r in rows if "error" not in r]
bad = [r for r in ok if r["sets"] != r["needed"]]
print(f"{os.path.basename(tree)}: {len(rows)} configurations, {len(rows) - len(ok)} not buildable, weight sets != passes x batches: {len(bad)}")
import collections
print("  by (channels, filters):", sorted(collections.Counter((r["ch"], r["nf"]) for r in bad).items()))
