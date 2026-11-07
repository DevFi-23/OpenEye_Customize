"""scan_guards.py <profile dir> [...]: every layer of the saved profiles (the platform of each profile's config, the
layer's shape) through the checks added 2026-11-07: check_conv_geometry (stride #41, padding #42, odd channels #7),
check_pooling_geometry (2 x 2 window, width #27) and check_dense_readout (#21). Conv and Dense layers are rebuilt as a
single Keras layer of the same shape and LayerParameters (the Dense one sends its results out when the profile says so);
a pooling layer is checked from its recorded size and stride. The profiles were made with Keras "same" convolutions,
so the padding check sees "same". Expected: 0 refused (the layers ran and passed).
    venv/bin/python doc/experiments/2026-11-07_bug41_stride/scan_guards.py doc/perf/paper_table3_2026-11-04 \
        doc/perf/baseline_2026-11-04 doc/perf/activation_2026-11-04_rowO"""
import glob, json, os, sys, types
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
os.environ.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "2", "LOGGER_LEVEL": "30", "OPENEYE_PAD_CHANNELS": "0"})
sys.path.insert(0, os.path.join(REPO, "src"))
import tensorflow as tf
from open_eye import open_eye_parameters as oep, layer_parameters as lp
DEFAULTS = {"TRANS_WORDS": "8", "BRANCHES": "1", "BUFFER_WIDTH": "12", "RAM_CELLS": "32", "NUM_GLB_IACT": "1",
            "CLUSTER_COLUMNS": "2", "DATA_PSUM_BITWIDTH": "20", "DMA_BITWIDTH": "64", "QUANT_AMOUNT": "32"}
KEYS = ["DMA_BITWIDTH", "DATA_PSUM_BITWIDTH", "CLUSTER_ROWS", "CLUSTER_COLUMNS", "NUM_GLB_IACT", "NUM_GLB_WGHT",
        "NUM_GLB_PSUM", "QUANT_AMOUNT"]
counts = {"Convolution2D": 0, "Pooling": 0, "Dense": 0}
refused = 0
for d in sys.argv[1:]:
    for path in sorted(glob.glob(os.path.join(d, "*.json"))):
        prof = json.load(open(path))
        if "config" not in prof or "layers" not in prof:
            continue
        env = dict(DEFAULTS)
        env.update({k: str(prof["config"][k]) for k in KEYS if k in prof["config"]})
        os.environ.update(env)
        params = oep.get_oep(1)
        for layer in prof["layers"]:
            info = layer["info"]
            name = info["name"]
            if name not in counts:
                continue
            counts[name] += 1
            tf.keras.utils.set_random_seed(1)
            try:
                if name == "Convolution2D":
                    ch = info["channels"] - info.get("pad_channels", 0)
                    m = tf.keras.models.Sequential([tf.keras.Input((info["iact_size_x"], info["iact_size_y"], ch)),
                                                    tf.keras.layers.Conv2D(info["filters"], tuple(info["kernel"]),
                                                                           strides=info["stride"], padding="same")])
                    lp.check_conv_geometry(lp.LayerParameters([0], m.layers[0], params, 0, 1), params)
                elif name == "Pooling":
                    s = info["stride"]
                    lp.check_pooling_geometry(types.SimpleNamespace(
                        layer_name="Pooling", strideX=s, strideY=s, pool_size=None, model_padding="valid",
                        iact_size_x=info["iact_size_x"]))
                elif info["send_values_out"]:        # a Dense layer written back on chip is not checked (#21)
                    m = tf.keras.models.Sequential([tf.keras.Input((info["iact_size_x"],)),
                                                    tf.keras.layers.Dense(info["filters"])])
                    lp.check_dense_readout(lp.LayerParameters([0], m.layers[0], params, 0, 1))
                verdict = "ok"
            except NotImplementedError as e:
                refused += 1
                verdict = f"REFUSED {e}"
            print(f"{os.path.basename(d)}/{os.path.basename(path)} layer {layer['index']} {name} "
                  f"{info['iact_size_x']}x{info['iact_size_y']}x{info['channels']}->{info['filters']}: {verdict}")
print(f"{counts} layers, {refused} refused")
