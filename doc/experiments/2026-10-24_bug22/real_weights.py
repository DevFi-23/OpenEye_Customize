"""real_weights.py: conv weights of the trained int8 MNIST model (doc/demo_notebooks/mnist_quantized_model.tflite) as
[c][f][ky][kx] lists -> real_mnist_conv_weights.json (conv1 with the bug #17 padding channel, weights 1), and the
offline check of the repository encoding vs the candidate encoder for each layer."""
import json
import os
import sys

import numpy as np
import tensorflow as tf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from offline_check import check  # noqa: E402
from encoder import encode  # noqa: E402

MODEL = os.path.join(HERE, "..", "..", "demo_notebooks", "mnist_quantized_model.tflite")
LAYERS = {"conv1": ("sequential_1/conv2d_1/convolution", 28, 28),
          "conv2": ("sequential_1/conv2d_1_2/convolution", 14, 14),
          "conv3": ("sequential_1/conv2d_2_1/convolution", 7, 7)}

it = tf.lite.Interpreter(model_path=MODEL)
it.allocate_tensors()
tensors = {d["name"]: it.get_tensor(d["index"]) for d in it.get_tensor_details()
           if d["name"].endswith("/convolution") and d["dtype"] == np.int8}
out = {}
for name, (key, W, H) in LAYERS.items():
    t = tensors[key]                                     # OHWI
    F, _, _, C = t.shape
    w = [[[[int(t[f][y][x][c]) for x in range(3)] for y in range(3)] for f in range(F)] for c in range(C)]
    if C == 1:
        w.append([[[1] * 3 for _ in range(3)] for _ in range(F)])
    out[name] = w
    old, new = check(w, W, H, skip=True), check(w, W, H, skip=False, encoder=encode)
    print(f"{name}: {int((t == 0).sum())} zero weights of {t.size}; PE loads decoded wrong: repository "
          f"{old['bad_pes']}/{old['pes']}, candidate encoder {new['bad_pes']}/{new['pes']}")
json.dump(out, open(os.path.join(HERE, "real_mnist_conv_weights.json"), "w"))
