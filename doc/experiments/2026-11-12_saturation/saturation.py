"""saturation.py [N]: how often the activation output of the trained MNIST models saturates at the int8 bounds on the
MNIST test images, how far beyond the bound the value would be, and what the saturation costs in accuracy.

The models are built as the RTL runs them (doc/experiments/2026-11-02_activation/eval_act.py build(): onnx2model static
quantization on 200 training images, LayerParameters, DRAMContents) and run through a numpy copy of the chip's integer
arithmetic with the toolchain's default rounding (ReLU floor, the others round to nearest). Per conv layer:
  high / low  the requantized value beyond 127 / below -128 (clamped by stage 3 of quantization_unit.v); for SiLU and
              hard-swish this is the int8 pre-activation that indexes the table (scale s_out of the conv)
  table       SiLU / hard-swish: outputs whose table entry is clamped at 127 (f(x) / s_next > 127)
  excess      how far beyond the bound the unclamped value is, in int8 units of the output scale and as a share of the
              unclamped value
and the accuracy with saturation (the chip) and with the int8 bounds removed (the same integers, nothing clamped at the
top; the tables computed from the float function without clamping). N test images (default 10000). Run from the
repository root: venv/bin/python doc/experiments/2026-11-12_saturation/saturation.py [N]"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
EVAL = os.path.join(REPO, "doc", "experiments", "2026-11-02_activation", "eval_act.py")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
spec = importlib.util.spec_from_file_location("eval_act", EVAL)
sys.argv = [EVAL, "1"]
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)
o2m, data_create, DRAM = ev.o2m, ev.data_create, ev.DRAM
DEFAULT_ROUND = {"relu": False, "leaky_relu": True, "silu": True, "hardswish": True}
LAYERS = {0: "Conv1", 2: "Conv2", 4: "Conv3"}


def requantize(v, mant, shift, rounding):
    return (mant * v + ((1 << (shift - 1)) if rounding and shift > 0 else 0)) >> shift


class Model:
    def __init__(self, activation, model, lps, dram):
        self.activation, self.model, self.lps = activation, model, lps
        self.rounding = DEFAULT_ROUND[activation]
        self.W = {n: np.array(dram.weights[n], dtype=np.int64) for n in (0, 2, 4)}
        self.B = {n: np.array(dram.bias[n], dtype=np.int64) for n in (0, 2, 4, 5)}
        self.WD = np.array(dram.weights[5], dtype=np.int64)
        self.order = DRAM.DRAMContents.dense_input_order(lps, 5, model[5])
        self.func = o2m.ACTIVATION_FUNCTIONS.get(activation)
        self.stats = {n: dict(values=0, high=0, low=0, table=0, excess=[], share=[]) for n in LAYERS}

    def table_unclamped(self, q, n):
        """f(q * s_out) / s_next rounded half away from zero, without the int8 bounds (activation_table's formula)."""
        m = self.model[n]
        y = self.func(q.astype(np.float64) * m.output_scale, m.activation_alpha) / m.activation_output_scale
        return (np.sign(y) * np.floor(np.abs(y) + 0.5)).astype(np.int64)

    def activate(self, psum, n, clamp):
        lp = self.lps[n]
        mant, shift = lp.quantize[0]
        q = requantize(psum, mant, shift, self.rounding)
        st = self.stats[n]
        if lp.act_mode == "leaky":
            q = np.where(psum < 0, requantize(psum, *lp.act_negative, self.rounding), q)
            low_bound = -128
        elif lp.act_mode == "table":
            low_bound = -128
        else:
            low_bound = lp.act_min
        if lp.act_mode == "table":
            qc = np.clip(q, -128, 127)
            out = np.array(lp.act_table, dtype=np.int64)[qc + 128]
            free = self.table_unclamped(q, n)
            if clamp:
                st["values"] += q.size
                st["high"] += int((q > 127).sum())
                st["low"] += int((q < -128).sum())
                sat = free > 127
                st["table"] += int((free[~((q > 127) | (q < -128))] > 127).sum())
                if sat.any():
                    st["excess"].extend((free[sat] - 127).tolist())
                    st["share"].extend(((free[sat] - 127) / free[sat]).tolist())
                return out
            return np.maximum(free, -128)
        if clamp:
            st["values"] += q.size
            st["high"] += int((q > 127).sum())
            st["low"] += int((q < low_bound).sum())
            sat = q > 127
            if sat.any():
                st["excess"].extend((q[sat] - 127).tolist())
                st["share"].extend(((q[sat] - 127) / q[sat]).tolist())
            return np.clip(q, low_bound, 127)
        return np.maximum(q, low_bound)

    def conv(self, x, n, clamp):
        C, X, Y = x.shape
        w = self.W[n]
        pad = np.zeros((C, X + 2, Y + 2), np.int64)
        pad[:, 1:-1, 1:-1] = x
        psum = np.broadcast_to(self.B[n][:, None, None], (w.shape[1], X, Y)).copy()
        for i in range(3):
            for j in range(3):
                psum += np.einsum("cf,cxy->fxy", w[:, :, j, i], pad[:, i:i + X, j:j + Y])
        return self.activate(psum, n, clamp)

    @staticmethod
    def pool(x):
        C, X, Y = x.shape
        return x.reshape(C, X // 2, 2, Y // 2, 2).max(axis=(2, 4))

    def run(self, image, clamp=True):
        x = np.zeros((self.W[0].shape[0], 28, 28), np.int64)
        x[0] = o2m.quantize_input(self.model, image)
        a = self.pool(self.conv(x, 0, clamp))
        a = self.pool(self.conv(a, 2, clamp))
        a = self.conv(a, 4, clamp)
        return self.B[5] + self.WD @ a.reshape(-1)[self.order]


def main():
    images, labels = data_create.mnist_images("test", range(N))
    for activation in ("relu", "leaky_relu", "silu", "hardswish"):
        _, model, lps, params, _, dram = ev.build(activation)
        for n in LAYERS:
            lps[n].act_round = DEFAULT_ROUND[activation]
        m = Model(activation, model, lps, dram)
        _, ref = ev.flow.reference(model, lps, params, images[0, 0])           # the chip's arithmetic, checked once
        assert (m.run(images[0, 0]) == np.array(ref[5]).ravel()).all(), "differs from the testbench reference"
        m.stats = {n: dict(values=0, high=0, low=0, table=0, excess=[], share=[]) for n in LAYERS}
        correct = correct_free = images_sat = 0
        for i in range(N):
            before = sum(s["high"] + s["table"] for s in m.stats.values())
            correct += int(np.argmax(m.run(images[i, 0]))) == int(labels[i])
            images_sat += sum(s["high"] + s["table"] for s in m.stats.values()) > before
            correct_free += int(np.argmax(m.run(images[i, 0], clamp=False))) == int(labels[i])
        print(f"== {activation}: accuracy {100 * correct / N:.2f} % (chip), {100 * correct_free / N:.2f} % (no upper bound); "
              f"images with a saturated output {images_sat} of {N}")
        for n, name in LAYERS.items():
            s = m.stats[n]
            ex = np.array(s["excess"]) if s["excess"] else np.zeros(1)
            sh = np.array(s["share"]) if s["share"] else np.zeros(1)
            print(f"  {name}: {s['values']} outputs; above 127: {s['high']} ({100 * s['high'] / s['values']:.4f} %); "
                  f"below the lower bound: {s['low']}; table entry clamped: {s['table']}; excess units max {int(ex.max())} "
                  f"mean {ex.mean():.2f}, share of the value max {100 * sh.max():.1f} % mean {100 * sh.mean():.1f} %")


if __name__ == "__main__":
    main()
