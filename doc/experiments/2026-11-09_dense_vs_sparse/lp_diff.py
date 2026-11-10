"""lp_diff.py "<KEY=V ...>" "<KEY=V ...>": LayerParameters attributes that differ between two Convolution_Single
configurations (keys W, H, CH, NF, CR, GLBP, SP for SPARSITY_EN) of the test_conv_const platform. Run from the repo root."""
import os
import subprocess
import sys
import json

CHILD = r'''
import os, sys, json
cfg = dict(a.split("=") for a in sys.argv[1].split())
env = {"CLUSTER_ROWS": cfg.get("CR", "2"), "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": cfg.get("GLBP", "4"), "NUM_GLB_WGHT": "3",
       "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1", "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "1024",
       "RAM_CELLS": "32", "CLUSTER_COLUMNS": "2", "SPARSITY_EN": cfg.get("SP", "0"), "OPENEYE_ALLOW_UNSUPPORTED": "1"}
os.environ.update(env)
import open_eye.open_eye_parameters as oep, open_eye.layer_parameters as lp, open_eye.data_create as dc
p = oep.get_oep(False)
m = dc.create_layer(cfg.get("L", "Convolution_Single"), int(cfg.get("NF", 4)), 3, 3, int(cfg.get("W", 8)), int(cfg.get("H", 4)), 1,
                    int(cfg.get("CH", 4)), 10)
layers = [l for l in m.layers if l.__class__.__name__ != "Flatten"]
n = len(layers)
lps = [0] * n
for i, l in reversed(list(enumerate(layers))):
    lps[n - i - 1] = lp.LayerParameters(lps, l, p, i, n)
out = {}
for k, v in vars(list(reversed(lps))[0]).items():
    if isinstance(v, (int, float, str, bool)):
        out[k] = v
print("JSON" + json.dumps(out))
'''
res = []
for arg in sys.argv[1:3]:
    o = subprocess.run([sys.executable, "-c", CHILD, arg], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH="src", TF_CPP_MIN_LOG_LEVEL="3"))
    line = [l for l in o.stdout.splitlines() if l.startswith("JSON")]
    if not line:
        print(o.stdout[-2000:], o.stderr[-3000:])
        sys.exit(1)
    res.append(json.loads(line[0][4:]))
a, b = res
for k in sorted(set(a) | set(b)):
    if a.get(k) != b.get(k):
        print(f"{k:40s} {str(a.get(k)):>12s} {str(b.get(k)):>12s}")
