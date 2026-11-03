"""params.py <out.json> cfg...: LayerParameters of the PAPER_MNIST network for configs 'cr,x,y' (as test_profile_paper),
without simulation (layer fields per configuration, e.g. to compare a failing and a passing one)."""
import json, os, sys
REPO = "/home/truongphi/OpenEye_orig"
sys.path[:0] = [os.path.join(REPO, "src"), os.path.join(REPO, "test", "cocotb_fpga")]
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
out = {}
for cfg in sys.argv[2:]:
    cr, x, y = (int(v) for v in cfg.split(","))
    env = dict(CLUSTER_ROWS=cr, NUM_GLB_IACT=1, NUM_GLB_PSUM=x, NUM_GLB_WGHT=y, DATA_PSUM_BITWIDTH=20, TRANS_WORDS=8,
               BRANCHES=1, BUFFER_WIDTH=12, QUANT_AMOUNT=32, DMA_BITWIDTH=64, RAM_CELLS=32, CLUSTER_COLUMNS=2)
    for k, v in env.items():
        os.environ[k] = str(v)
    import importlib
    from open_eye import open_eye_parameters as oepm, layer_parameters as lp, data_create, channel_pad
    importlib.reload(oepm)
    import tensorflow as tf
    tf.keras.utils.set_random_seed(1)
    oep = oepm.get_oep(1)
    model = data_create.create_layer("PAPER_MNIST", 8, 3, 3, 28, 28, (1, 1), 1, 1)
    model = [l for l in model.layers if not isinstance(l, tf.keras.layers.Flatten)]
    n = len(model)
    def build(model):
        lps = [0] * n
        for i, layer in reversed(list(enumerate(model))):
            lps[n - i - 1] = lp.LayerParameters(lps, layer, oep, i, n)
        return list(reversed(lps))
    lps = build(model)
    model, padded = channel_pad.pad_first_layer(model, lps)
    if padded:
        lps = build(model)
    rows = []
    for p in lps:
        d = {}
        for k, v in vars(p).items():
            if isinstance(v, (int, float, bool, str)) or (isinstance(v, list) and len(str(v)) < 300):
                d[k] = v
        rows.append(d)
    out[cfg] = rows
json.dump(out, open(sys.argv[1], "w"), default=str)
print("ok", list(out))
