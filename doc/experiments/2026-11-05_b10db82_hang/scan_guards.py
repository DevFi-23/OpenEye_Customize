"""scan_guards.py <profile dir> [...]: every Conv layer of the saved profiles (the platform of each profile's config, the
layer's shape) through LayerParameters and the two stream checks of ConvMapper, check_wght_sets (#39) and
check_full_passes (#40). A layer is rebuilt as a single Conv2D of the same shape: the parameters the checks use
(passes, psums per PE, kernels per calculation, channel batches) depend on the shape and the platform.
    venv/bin/python doc/experiments/2026-11-05_b10db82_hang/scan_guards.py doc/perf/paper_table3_2026-11-04 doc/perf/baseline_2026-11-04"""
import glob, json, os, sys
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
os.environ.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "2", "LOGGER_LEVEL": "30", "OPENEYE_PAD_CHANNELS": "0"})
sys.path.insert(0, os.path.join(REPO, "src"))
import tensorflow as tf
from open_eye import open_eye_parameters as oep, layer_parameters as lp
DEFAULTS = {"TRANS_WORDS": "8", "BRANCHES": "1", "BUFFER_WIDTH": "12", "RAM_CELLS": "32", "NUM_GLB_IACT": "1",
            "CLUSTER_COLUMNS": "2", "DATA_PSUM_BITWIDTH": "20", "DMA_BITWIDTH": "64", "QUANT_AMOUNT": "32"}
KEYS = ["DMA_BITWIDTH", "DATA_PSUM_BITWIDTH", "CLUSTER_ROWS", "CLUSTER_COLUMNS", "NUM_GLB_IACT", "NUM_GLB_WGHT",
        "NUM_GLB_PSUM", "QUANT_AMOUNT"]
total = refused = 0
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
            if info["name"] != "Convolution2D":
                continue
            ch = info["channels"] - info.get("pad_channels", 0)
            k = info["kernel"]
            tf.keras.utils.set_random_seed(1)
            m = tf.keras.models.Sequential([tf.keras.Input((info["iact_size_x"], info["iact_size_y"], ch)),
                                            tf.keras.layers.Conv2D(info["filters"], tuple(k), strides=info["stride"],
                                                                   padding="same")])
            p = lp.LayerParameters([0], m.layers[0], params, 0, 1)
            total += 1
            try:
                lp.check_wght_sets(p)
                lp.check_full_passes(p)
                verdict = "ok"
            except NotImplementedError as e:
                refused += 1
                verdict = f"REFUSED {e}"
            print(f"{os.path.basename(d)}/{os.path.basename(path)} layer {layer['index']} "
                  f"{info['iact_size_x']}x{info['iact_size_y']}x{ch}->{info['filters']} k{k[0]}: "
                  f"passes {p.needed_wght_cycles} x psums {p.used_psum_per_PE} x kernels {p.different_kernels_per_calculation}: {verdict}")
print(f"{total} conv layers, {refused} refused")
