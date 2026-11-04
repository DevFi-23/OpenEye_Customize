"""wtrans.py: LayerParameters of one Convolution_Single over channels x filters x sizes (platform CR 2 CC 2, PSUM 4,
WGHT 3): the weight sets the stream carries (needed_wght_transmissions) against the weight passes the RTL reads
(needed_wght_cycles x channel batches)."""
import os, sys, itertools
os.environ.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "2", "CLUSTER_ROWS": sys.argv[1] if len(sys.argv) > 1 else "2",
                   "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4", "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20",
                   "TRANS_WORDS": "8", "BRANCHES": "1", "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "1024", "RAM_CELLS": "32",
                   "DMA_BITWIDTH": "64", "OPENEYE_PAD_CHANNELS": "0"})
sys.path.insert(0, "/home/truongphi/OpenEye_orig/src")
import tensorflow as tf
from open_eye import data_create, open_eye_parameters as oep, layer_parameters as lp
params = oep.get_oep(1)
rows = []
for (w, h), ch, nf in itertools.product([(8, 4), (14, 14), (28, 28)], [1, 2, 3, 4, 8, 32, 64], [4, 8, 16, 32, 64]):
    tf.keras.utils.set_random_seed(1)
    try:
        km = data_create.create_layer("Convolution_Single", nf, 3, 3, w, h, 1, ch, 10)
        model = [l for l in km.layers if not isinstance(l, tf.keras.layers.Flatten)]
        L = lp.LayerParameters([0], model[0], params, 0, 1)
    except Exception as e:
        print(f"{w}x{h}x{ch}->{nf}: {type(e).__name__}"); continue
    sets = L.needed_wght_transmissions
    passes = L.needed_wght_cycles
    flag = "" if sets == passes * L.iact_transmissions_pe or sets == passes else "  <-- differs"
    print(f"{w}x{h}x{ch:>2}->{nf:>2}: kpc {L.different_kernels_per_calculation} psum/PE {L.used_psum_per_PE:>2} "
          f"used_ch {L.used_channels} div {L.channel_div_trans} diff_iact {L.diff_iact_layer} iact_tr {L.iact_transmissions_pe} "
          f"| wght sets {sets} wght_cycles {passes}{flag}")
