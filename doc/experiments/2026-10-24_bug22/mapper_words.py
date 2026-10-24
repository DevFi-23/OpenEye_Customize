"""mapper_words.py: the conv weight words the repository mapper sends to each PE, for given weights (library + CLI).

words_per_pe(weights, W, H) -> {pe_key 'cxcyr': [[(value, overhead), (value, overhead)], ...]} using the real
ConvWghtStreamMapper (single transmission, platform of the cocotb_fpga tests); pe_key has no PE column (all 4 PE
columns of a cluster row get the same words)."""
import os, sys, json
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
PLATFORM = {"CLUSTER_ROWS": "2", "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4",
            "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
            "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "64", "DMA_BITWIDTH": "64", "RAM_CELLS": "32"}
os.environ.update(PLATFORM)
import tensorflow as tf
from open_eye import layer_parameters as lp, open_eye_parameters as oep
from open_eye import wght_stream_mapper as wsm

_cache = {}

def layer(W, H, C, F):
    key = (W, H, C, F)
    if key not in _cache:
        m = tf.keras.Sequential([tf.keras.Input((W, H, C)), tf.keras.layers.Conv2D(F, (3, 3), padding="same")])
        params = oep.get_oep(1)
        _cache[key] = (params, lp.LayerParameters([0], m.layers[0], params, 0, 1))
    return _cache[key]

def words_per_pe(weights, W, H):
    C, F = len(weights), len(weights[0])
    params, L = layer(W, H, C, F)
    mp = wsm.ConvWghtStreamMapper(params, L, 0, weights, 0)
    out = {}
    for cx in range(params.Clusters_X):
        for cy in range(params.Clusters_Y):
            for r in range(params.Wght_Routers):
                if L.computing_mx[cx][cy][r][0] != 1:
                    continue
                spad = mp.write_wght_pe(cx, cy, r)
                ws = [[(e[0], e[1]) for e in word] for word in spad]
                while ws and all(e == (0, 0) for e in ws[-1]):
                    ws.pop()
                out[f"{cx}{cy}{r}"] = ws
    return out

if __name__ == "__main__":
    w = json.load(open(sys.argv[1]))["weights"]
    W, H, pe = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    for i, word in enumerate(words_per_pe(w, W, H)[pe]):
        print(i, word)
