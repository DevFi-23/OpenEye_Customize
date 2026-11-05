"""params_up.py <tree>: LayerParameters of a few one-layer models with that tree's Python (CR 2, GLB psum 4, wght 3)."""
import os, sys
tree = os.path.abspath(sys.argv[1])
os.environ.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "2", "CLUSTER_COLUMNS": "2", "CLUSTER_ROWS": "2",
                   "NUM_GLB_PSUM": "4", "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
                   "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "1024", "RAM_CELLS": "32", "DMA_BITWIDTH": "64", "NUM_GLB_IACT": "1"})
os.environ.setdefault("LOGGER_LEVEL", "30")
sys.path[:0] = [os.path.join(tree, "src"), os.path.join(tree, "test", "cocotb_fpga")]
import tensorflow as tf
from open_eye import data_create, open_eye_parameters as oep, layer_parameters as lp
import OpenEye_FPGA_tb as tb
params = oep.get_oep(1)
F = ["filters", "channels", "different_kernels_per_calculation", "used_psum_per_PE", "used_wght_per_PE", "Wghts_per_PE",
     "iact_transmissions_pe", "needed_wght_cycles", "needed_wght_transmissions", "needed_psum_transmissions",
     "needed_total_transmissions", "psum_delay", "used_Y_cluster", "Used_refreshes", "used_wght_addr_per_PE"]
for w, h, ch, nf in [(8, 4, 1, 64), (8, 4, 1, 96), (8, 4, 1, 128), (28, 28, 1, 32), (28, 28, 1, 48), (28, 28, 1, 64),
                     (28, 28, 2, 64), (28, 28, 2, 96)]:
    tf.keras.utils.set_random_seed(1)
    km = data_create.create_net("Convolution_Single", nf, 3, 3, w, h, 1, ch, 10)
    rel = tb.build_layer_topology(km)
    layers = [l for l in km.layers if not isinstance(l, tf.keras.layers.Flatten)]
    L = lp.LayerParameters({}, layers[0], params, rel, 0)
    vals = {f: getattr(L, f, getattr(params, f, None)) for f in F}
    print(f"{w}x{h}x{ch}->{nf}", " ".join(f"{k}={v}" for k, v in vals.items() if k not in ("filters", "channels")))
