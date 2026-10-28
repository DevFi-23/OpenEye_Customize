"""What the old quantizer's wrap-around did (low 8 bits instead of saturation, bug #30), on the trained MNIST int8 model.

1. Accuracy (10,000 test images) with each half of the clamp alone: the upper bound 127 and the lower bound (act_min,
   = the fused ReLU), for TFLite's activations (zero point -128; #12 not fixed, mantissa 8 bit, psum 32 bit = variant H2)
   and symmetric ones (zero point 0, ReLU bound 0; per filter, mantissa 8 bit, psum 20 bit = variant S7).
2. Share of the quantizer outputs (before the clamp) outside int8, per layer (1,000 images).
3. A worked example: conv1, filter 0, test image 0, requantized the TFLite way.

Usage (from this directory, with the repository's venv): python wrap.py   (wrap_result.txt)
"""
import time
import numpy as np
import emu

d = np.load(emu.MNIST)
X, Y = d["x_test"][:, :, :, None].astype(np.int64), d["y_test"]
layers = emu.load()
clip = np.clip
OUTPUTS = {
    "wrap, low 8 bits (old RTL)":           lambda q, lo, hi: emu.wrap(q, 8),
    "upper bound 127 only, low end wraps":  lambda q, lo, hi: emu.wrap(np.minimum(q, 127), 8),
    "lower bound only (ReLU), high wraps":  lambda q, lo, hi: emu.wrap(np.maximum(q, lo), 8),
    "int8 clamp [-128, 127], no ReLU":      lambda q, lo, hi: clip(q, -128, 127),
    "clamp [act_min, 127] (new RTL)":       lambda q, lo, hi: clip(q, lo, hi),
}
CONFIGS = {
    "zp -128": dict(per_filter=False, mant_bits=8, psum_bits=32),
    "zp 0":    dict(symmetric=True, per_filter=True, mant_bits=8, psum_bits=20),
}

print("1. accuracy, 10,000 MNIST test images (TFLite int8: 99.23 %)")
for cfg, kw in CONFIGS.items():
    for name, out in OUTPUTS.items():
        t = time.time()
        emu.np.clip = out                       # hardware() saturates with np.clip(q, lo, 127) when clamp=True
        try:
            acc = emu.accuracy(lambda imgs, **k: emu.hardware(imgs, layers, clamp=True, **k), X, Y, **kw)
        finally:
            emu.np.clip = clip
        print(f"  {cfg:8s} | {name:36s} | {acc*100:6.2f} %  ({time.time()-t:.0f} s)", flush=True)

print("2. quantizer outputs before the clamp, 1,000 images")
for cfg, kw in CONFIGS.items():
    seen = []
    emu.np.clip = lambda q, lo, hi: (seen.append((q.copy(), lo)), clip(q, lo, hi))[1]
    try:
        emu.hardware(X[:1000], layers, clamp=True, **kw)
    finally:
        emu.np.clip = clip
    for i, (q, lo) in enumerate(seen):
        n = q.size
        print(f"  {cfg:8s} quantizer {i}: > 127 {100*(q > 127).mean():5.2f} %  < -128 {100*(q < -128).mean():5.2f} %  "
              f"< act_min ({lo}) {100*(q < lo).mean():5.1f} %  min {q.min()}  max {q.max()}  "
              f"wrap != clamp {100*(emu.wrap(q, 8) != clip(q, lo, 127)).mean():5.1f} %")

print("3. conv1, filter 0, test image 0 (TFLite requantization: s_out %.5g, zp_out %d, M %.3g)"
      % (layers[0]["s_out"], layers[0]["zp_out"], layers[0]["M"][0]))
L = layers[0]
x = X[:1] - 128
acc = emu.linear((x - L["zp_in"]).astype(np.float64), L, 0.0) + L["b"]
qm = [emu.quantize_multiplier(m) for m in L["M"]]
y = emu.mbqm(acc, np.array([a for a, _ in qm], np.int64), np.array([b for _, b in qm], np.int64)) + L["zp_out"]
a, yy = acc.reshape(-1, acc.shape[-1])[:, 0], y.reshape(-1, y.shape[-1])[:, 0]
real = lambda v: (v - L["zp_out"]) * L["s_out"]
for k in (int(np.argmax(yy)), int(np.argmin(np.abs(yy + 150))), int(np.argmin(yy))):
    c, w = int(clip(yy[k], -128, 127)), int(emu.wrap(yy[k], 8))
    print(f"  position {k:3d}: psum {int(a[k]):7d}  requantized {int(yy[k]):5d}  clamp {c:4d} (real {real(c):.3f})  "
          f"wrap {w:4d} (real {real(w):.3f})")
