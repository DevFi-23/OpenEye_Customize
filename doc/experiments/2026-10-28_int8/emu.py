"""Int8 investigation (no repository change): the trained MNIST int8 TFLite model, emulated bit-exact the TFLite way and
the way the OpenEye datapath computes, with each hardware difference switchable. Accuracy on the 10,000 MNIST test images.

Hardware model of one Conv/Dense layer (what the RTL does today, plus switches):
  psum   = bias_hw + sum(x_raw * w)            x_raw: int8 activation as stored, padding = 0 raw (or zp_in, pad_zp)
           wrapped to psum_bits (two's complement)
  bias_hw = b - zp_in*sum(w) + round(zp_out/M_c) [+ round(2^(s-1)/mant) if round_bias]   (Python-only folds)
  q      = floor(mant * psum / 2^shift)       mant/shift from M_c (or M_0 for every filter: bug #12), mant < 2^mant_bits
  out    = clamp(q, act_min, 127) if clamp else wrap to int8 (low 8 bits, today's RTL)
The last layer returns raw psums to the host (as PSUM_SEND_RESULTS does); the host takes argmax over M_c * psum_c.
Symmetric mode: activations requantized with zero point 0 (scale for the same max: s * 255/127), ReLU = clamp at 0.

Usage (from this directory, with the repository's venv; doc/experiments/2026-10-28_int8_clamp.md):
  python validate.py     # emulator vs TFLite reference kernels, per layer (300 images)
  python variants.py     # accuracy of the hardware variants on the 10,000 test images (variants_result.txt)
  python variants2.py    # more variants (#12 not fixed, rounding, asymmetric with 20-bit psum)
  python sparsity.py     # share of activations at the real zero after each layer
"""
import math
import sys
import numpy as np

import os
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 2, "demo_notebooks",
                     "mnist_quantized_model.tflite")
MNIST = os.path.expanduser("~/.keras/datasets/mnist.npz")   # tf.keras.datasets.mnist.load_data() caches it here


def load():
    import tensorflow as tf
    it = tf.lite.Interpreter(model_path=MODEL)
    it.allocate_tensors()
    td = {t["index"]: t for t in it.get_tensor_details()}
    layers = []
    for op in it._get_ops_details():
        if op["op_name"] not in ("CONV_2D", "FULLY_CONNECTED", "MAX_POOL_2D"):
            continue
        y = td[op["outputs"][0]]
        L = {"kind": op["op_name"], "s_out": y["quantization"][0], "zp_out": y["quantization"][1]}
        if op["op_name"] != "MAX_POOL_2D":
            x, w, b = td[op["inputs"][0]], td[op["inputs"][1]], td[op["inputs"][2]]
            L.update(s_in=x["quantization"][0], zp_in=x["quantization"][1],
                     w=it.get_tensor(w["index"]).astype(np.int64), b=it.get_tensor(b["index"]).astype(np.int64),
                     s_w=w["quantization_parameters"]["scales"].astype(np.float64),
                     relu="Relu" in y["name"])
            L["M"] = L["s_in"] * L["s_w"] / L["s_out"]
        layers.append(L)
    return layers


def quantize_multiplier(M):
    q, e = math.frexp(M)
    qf = int(round(q * (1 << 31)))
    if qf == (1 << 31):
        qf //= 2
        e += 1
    return qf, e


def mbqm(x, qf, shift):
    """TFLite MultiplyByQuantizedMultiplier (double rounding), x int64 array, qf/shift per channel (last axis)."""
    left = np.maximum(shift, 0)
    right = np.maximum(-shift, 0)
    x = x * (1 << left)
    ab = x * qf
    nudge = np.where(ab >= 0, 1 << 30, 1 - (1 << 30))
    t = ab + nudge
    high = np.where(t >= 0, t >> 31, -((-t) >> 31))
    mask = (1 << right) - 1
    rem = high & mask
    thr = (mask >> 1) + (high < 0)
    return (high >> right) + (rem > thr)


def im2col(x, pad_value):
    """x [N,H,W,C] -> [N*H*W, 9*C] for a 3x3 'same' stride-1 conv (kernel order kh, kw, c)."""
    n, h, w, c = x.shape
    p = np.full((n, h + 2, w + 2, c), pad_value, dtype=np.float64)
    p[:, 1:-1, 1:-1, :] = x
    cols = [p[:, i:i + h, j:j + w, :] for i in range(3) for j in range(3)]
    return np.concatenate(cols, axis=-1).reshape(n * h * w, 9 * c)


def linear(x, L, pad_value):
    """sum(x * w) over the layer, x as given (float64 holding integers): returns int64 [..., out]."""
    w = L["w"].reshape(L["w"].shape[0], -1).astype(np.float64)        # [out, kh*kw*in] or [out, in]
    if L["kind"] == "CONV_2D":
        n, h, wd, _ = x.shape
        acc = im2col(x, pad_value) @ w.T
        return np.rint(acc).astype(np.int64).reshape(n, h, wd, -1)
    return np.rint(x.reshape(x.shape[0], -1) @ w.T).astype(np.int64)


def maxpool(x):
    n, h, w, c = x.shape
    return x.reshape(n, h // 2, 2, w // 2, 2, c).max(axis=(2, 4))


def tflite_exact(images, layers, collect=None):
    x = images.astype(np.int64) - 128                     # QUANTIZE: round(img/255 / (1/255)) - 128
    for i, L in enumerate(layers):
        if L["kind"] == "MAX_POOL_2D":
            x = maxpool(x)
        else:
            acc = linear((x - L["zp_in"]).astype(np.float64), L, 0.0) + L["b"]
            qm = [quantize_multiplier(m) for m in L["M"]]
            qf = np.array([a for a, _ in qm], np.int64)
            sh = np.array([b for _, b in qm], np.int64)
            y = mbqm(acc, qf, sh) + L["zp_out"]
            lo = max(-128, L["zp_out"]) if L["relu"] else -128
            x = np.clip(y, lo, 127)
        if collect is not None:
            collect.append(x.copy())
    return x


def mant_shift(M, mant_bits, shift_max=127):
    s = 0
    while s < shift_max and round(M * 2 ** (s + 1)) < (1 << mant_bits):
        s += 1
    return int(round(M * 2 ** s)), s


def wrap(v, bits):
    m = 1 << bits
    return ((v + (m >> 1)) % m) - (m >> 1)


def hardware(images, layers, *, clamp=False, per_filter=False, mant_bits=8, pad_zp=False, round_bias=False,
             psum_bits=32, symmetric=False, stats=None):
    if symmetric:
        x = np.rint(images * 127.0 / 255.0).astype(np.int64)           # image [0,1], scale 1/127, zp 0
        s_prev = 1.0 / 127.0
    else:
        x = images.astype(np.int64) - 128
    nl = len(layers)
    for i, L in enumerate(layers):
        last = i == nl - 1
        if L["kind"] == "MAX_POOL_2D":
            x = maxpool(x)
            continue
        if symmetric:
            s_in, zp_in = s_prev, 0
            s_out = L["s_out"] * 255.0 / 127.0 if L["relu"] else L["s_out"]
            zp_out = 0
            M = s_in * L["s_w"] / s_out
            b = np.rint(L["b"] * L["s_in"] / s_in).astype(np.int64)
            lo = 0 if L["relu"] else -128
        else:
            s_in, zp_in, zp_out, M, b = L["s_in"], L["zp_in"], L["zp_out"], L["M"], L["b"]
            lo = -128
        w2 = L["w"].reshape(L["w"].shape[0], -1)
        Mq = M if per_filter else np.full_like(M, M[0])                 # bug #12: filter 0's multiplier for all
        ms = [mant_shift(m, mant_bits) for m in Mq]
        mant = np.array([a for a, _ in ms], np.int64)
        shift = np.array([c for _, c in ms], np.int64)
        bias = b - zp_in * w2.sum(axis=1)                               # fold the input zero point
        if not last:
            bias = bias + np.rint(zp_out / (mant / 2.0 ** shift)).astype(np.int64)    # fold the output zero point
            if round_bias:
                bias = bias + np.rint(2.0 ** (shift - 1) / mant).astype(np.int64)
        acc = linear(x.astype(np.float64), L, float(zp_in) if pad_zp else 0.0) + bias
        if stats is not None:
            stats.setdefault(i, []).append(int(np.abs(acc).max()))
        acc = wrap(acc, psum_bits)
        if last:
            return acc * M                            # host: real-valued logits from the raw psums (argmax only)
        q = (acc * mant) >> shift
        x = np.clip(q, lo, 127) if clamp else wrap(q, 8)
        if symmetric:
            s_prev = s_out
    return x


def accuracy(fn, images, labels, batch=500, **kw):
    hits = 0
    for k in range(0, len(images), batch):
        out = fn(images[k:k + batch], **kw)
        hits += int((np.argmax(out.reshape(out.shape[0], -1), axis=1) == labels[k:k + batch]).sum())
    return hits / len(images)
