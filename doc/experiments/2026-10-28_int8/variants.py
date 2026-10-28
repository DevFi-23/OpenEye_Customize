import time, numpy as np, emu
d = np.load(emu.MNIST)
X, Y = d["x_test"][:, :, :, None].astype(np.int64), d["y_test"]
layers = emu.load()
runs = [
    ("TFLite int8 (emulator, = interpreter)", emu.tflite_exact, {}),
    ("H0 hardware today, Python-only mapping, psum 20 bit", emu.hardware, dict(psum_bits=20)),
    ("H1 same, psum 32 bit", emu.hardware, dict(psum_bits=32)),
    ("H2 + clamp int8", emu.hardware, dict(psum_bits=32, clamp=True)),
    ("H3 + per-filter M (fix #12)", emu.hardware, dict(psum_bits=32, clamp=True, per_filter=True)),
    ("H4 + mantissa 25 bit (fix slice)", emu.hardware, dict(psum_bits=32, clamp=True, per_filter=True, mant_bits=25)),
    ("H5 + padding = zp_in", emu.hardware, dict(psum_bits=32, clamp=True, per_filter=True, mant_bits=25, pad_zp=True)),
    ("H6 + rounding via bias", emu.hardware, dict(psum_bits=32, clamp=True, per_filter=True, mant_bits=25, pad_zp=True, round_bias=True)),
    ("H6' as H6 but mantissa 8 bit", emu.hardware, dict(psum_bits=32, clamp=True, per_filter=True, mant_bits=8, pad_zp=True, round_bias=True)),
    ("H6'' as H6 but padding 0 raw", emu.hardware, dict(psum_bits=32, clamp=True, per_filter=True, mant_bits=25, round_bias=True)),
    ("S1 symmetric zp=0, ReLU clamp at 0, psum 32", emu.hardware, dict(symmetric=True, psum_bits=32, clamp=True, per_filter=True, mant_bits=25, round_bias=True)),
    ("S2 symmetric, psum 20", emu.hardware, dict(symmetric=True, psum_bits=20, clamp=True, per_filter=True, mant_bits=25, round_bias=True)),
    ("S3 symmetric, psum 20, mantissa 8", emu.hardware, dict(symmetric=True, psum_bits=20, clamp=True, per_filter=True, mant_bits=8, round_bias=True)),
    ("S4 symmetric but NO clamp (wrap)", emu.hardware, dict(symmetric=True, psum_bits=32, clamp=False, per_filter=True, mant_bits=25, round_bias=True)),
]
for name, fn, kw in runs:
    t = time.time()
    st = {} if fn is emu.hardware else None
    if st is not None:
        kw = dict(kw, stats=st)
    acc = emu.accuracy(lambda imgs, **k: fn(imgs, layers, **k), X, Y, **kw)
    extra = ""
    if st:
        extra = "  max|psum| per layer: " + " ".join(f"{max(v):,}" for _, v in sorted(st.items()))
    print(f"{acc*100:6.2f} %  {name}  ({time.time()-t:.0f} s){extra}", flush=True)
