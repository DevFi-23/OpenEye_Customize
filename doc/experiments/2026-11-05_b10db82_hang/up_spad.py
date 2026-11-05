"""up_spad.py <tree> W H CH NF: weight data SPad of PE cl(0,0) router 1 per weight pass, built with the tree's own
ConvWghtStreamMapper (fork formula for the weight sets patched into the tree), random non-zero weights.
Reports per pass: entries, zero-value entries, all-zero words, longest run of zero entries."""
import os, sys, random
tree = os.path.abspath(sys.argv[1]); W, H, CH, NF = map(int, sys.argv[2:6])
os.environ.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "2", "CLUSTER_COLUMNS": "2", "CLUSTER_ROWS": "2",
                   "NUM_GLB_PSUM": "4", "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
                   "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "1024", "RAM_CELLS": "32", "DMA_BITWIDTH": "64", "NUM_GLB_IACT": "1",
                   "LOGGER_LEVEL": "30"})
sys.path[:0] = [os.path.join(tree, "src"), os.path.join(tree, "test", "cocotb_fpga")]
import tensorflow as tf
from open_eye import data_create, open_eye_parameters as oep, layer_parameters as lp, wght_stream_mapper as wsm
import OpenEye_FPGA_tb as tb
params = oep.get_oep(1)
tf.keras.utils.set_random_seed(1)
km = data_create.create_net("Convolution_Single", NF, 3, 3, W, H, 1, CH, 10)
layer = [l for l in km.layers if not isinstance(l, tf.keras.layers.Flatten)][0]
L = lp.LayerParameters({}, layer, params, tb.build_layer_topology(km), 0)
random.seed(1)
dram = [[[[random.choice([v for v in range(-100, 101) if v]) for _ in range(3)] for _ in range(3)] for _ in range(NF)] for _ in range(CH)]
print(f"{W}x{H}x{CH}->{NF}: psums/PE {L.used_psum_per_PE}, kpc {L.different_kernels_per_calculation}, used_wght_per_PE "
      f"{L.used_wght_per_PE}, weight sets {L.needed_wght_transmissions}")
for rep in range(L.needed_wght_transmissions):
    m = wsm.ConvWghtStreamMapper(params, L, rep, dram, 1)
    for router in (0, 1):
        spad = m.write_wght_data_storage(0, 0, router)
        words = spad[:-(-L.used_wght_per_PE // params.PARALLEL_MACS)]
        entries = [e for w in words for e in w]
        zero_words = sum(all(e[0] == 0 and e[1] == 0 for e in w) for w in words)
        run = best = 0
        for e in entries:
            run = run + 1 if e[0] == 0 else 0
            best = max(best, run)
        print(f"  pass {rep} router {router}: {len(words)} words, zero-value entries {sum(e[0] == 0 for e in entries)}, "
              f"all-zero words {zero_words}, longest zero run {best}")
