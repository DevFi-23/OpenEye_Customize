import time, numpy as np, emu
d = np.load(emu.MNIST)
X, Y = d["x_test"][:, :, :, None].astype(np.int64), d["y_test"]
layers = emu.load()
runs = [
    ("S5 symmetric, clamp, #12 NOT fixed, mantissa 8, psum 20", dict(symmetric=True, clamp=True, per_filter=False, mant_bits=8, psum_bits=20, round_bias=True)),
    ("S6 symmetric, clamp, #12 NOT fixed, mantissa 25, psum 32", dict(symmetric=True, clamp=True, per_filter=False, mant_bits=25, psum_bits=32, round_bias=True)),
    ("S7 symmetric, clamp, per-filter, mantissa 8, psum 20, floor (no rounding bias)", dict(symmetric=True, clamp=True, per_filter=True, mant_bits=8, psum_bits=20)),
    ("H7 asymmetric, clamp, padding=zp, #12 NOT fixed, mantissa 8, psum 32", dict(clamp=True, pad_zp=True, per_filter=False, mant_bits=8, psum_bits=32, round_bias=True)),
    ("H8 asymmetric, clamp, padding=zp, per-filter, mantissa 8, psum 20", dict(clamp=True, pad_zp=True, per_filter=True, mant_bits=8, psum_bits=20, round_bias=True)),
]
for name, kw in runs:
    t = time.time()
    acc = emu.accuracy(lambda imgs, **k: emu.hardware(imgs, layers, **k), X, Y, **kw)
    print(f"{acc*100:6.2f} %  {name}  ({time.time()-t:.0f} s)", flush=True)
