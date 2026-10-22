"""Weight stream word count of a padded MNIST Conv1 (28x28x1+1 -> 32) for pad weights 0 vs 1 (pure Python)."""
import os, sys
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
PLATFORM = {"CLUSTER_ROWS": "2", "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4",
            "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
            "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "32", "DMA_BITWIDTH": "64", "RAM_CELLS": "32"}
os.environ.update(PLATFORM)
import numpy as np, tensorflow as tf
from open_eye import channel_pad, layer_parameters as lp, open_eye_parameters as oep
from open_eye import wght_stream_mapper as wsm
import open_eye.test_utils_main as tum

tf.keras.utils.set_random_seed(1)
m = tf.keras.Sequential([tf.keras.Input((28, 28, 1)), tf.keras.layers.Conv2D(32, (3, 3), padding="same")])
layer = channel_pad.ChannelPaddedConv2D(m.layers[0])
params = oep.get_oep(1)
lpar = lp.LayerParameters([0], layer, params, 0, 1)
rng = np.random.default_rng(0)
base = [[[[int(v) or 1 for v in rng.integers(-64, 64, 3)] for _ in range(3)] for _ in range(32)] for _ in range(2)]
fmap = [[[1] * 28 for _ in range(28)], [[0] * 28 for _ in range(28)]]
bias = [1] * 32
for pad_w in (0, 1):
    w = [base[0], [[[pad_w] * 3 for _ in range(3)] for _ in range(32)]]
    for skip in (True, False):
        wsm.WghtStreamMapper.SKIP_ZERO_WORDS = skip
        stream = tum.write_stream(params, lpar, [fmap, w, bias], 0, 0)
        s = stream[0]
        def size(x):
            return sum(size(v) for v in x) if isinstance(x, (list, tuple)) else 1
        print(f"pad weight {pad_w}, SKIP_ZERO_WORDS={skip}: sections", [size(x) for x in s],
              "types", [type(x).__name__ for x in s][:7])
