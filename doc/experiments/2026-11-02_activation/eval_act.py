"""eval_act.py [N]: the trained MNIST model with ReLU, Leaky ReLU (0.1), SiLU and hard-swish as the planned activation
hardware computes it (Python only, no RTL; doc/experiments/2026-11-02_activation_plan.md, step A).

Builds every variant as OpenEye_FPGA_tb with OPENEYE_MODEL_WEIGHTS does (onnx2model static quantization,
LayerParameters, DRAMContents; checkpoints of models/train_mnist.py, the original one for ReLU) and runs MNIST test
images 0..N-1 (default 10000) through a numpy model of the integer arithmetic: conv with the DRAM weights and biases,
the requantization floor(mant * psum / 2^shift) or rounded half up, the activation (clamp at 0 for ReLU, a second
[mant, shift] for negative sums for Leaky ReLU, the 256-entry table for SiLU / hard-swish), 2x2 max pooling, Dense in
the hardware's input order. The numpy model is checked equal to the testbench reference (every layer output) on two
images for each variant and rounding. Reports per variant and option: accuracy (int8 as the hardware computes it,
next to the float model and ONNX Runtime's int8 model), the fraction of zeros in every layer's input (what zero
skipping uses), and the compute cycles this predicts (linear in the zero fraction between the two measured points of
each layer: random data and the trained ReLU model, doc/perf/trained_mnist_2026-10-31.md). Options for the table
activations: band1 (table outputs -1 and 1 set to 0) and neg0 (every negative table output set to 0). Run from the
repository root: venv/bin/python doc/experiments/2026-11-02_activation/eval_act.py [N]"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path[:0] = [os.path.join(REPO, "test"), os.path.join(REPO, "models")]
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
import test_onnx_model_flow as flow  # noqa: E402
for key, value in flow.PLATFORM.items():
    os.environ[key] = value
import onnx  # noqa: E402
import onnxruntime as ort  # noqa: E402
import torch  # noqa: E402
from open_eye import DRAM, data_create, onnx2model as o2m, open_eye_parameters as oep  # noqa: E402
from train_mnist import load_activation_model  # noqa: E402

CHECKPOINTS = {"relu": "mnist_unquantized_model.pth", "leaky_relu": "mnist_leaky_relu_model.pth",
               "silu": "mnist_silu_model.pth", "hardswish": "mnist_hardswish_model.pth"}
# Compute cycles of the layers that read activations, measured at two zero fractions of their input (image 0 of the
# trained ReLU model and the random-data case model_mnist_real_c1, before the wghts_per_pe + 1 line):
# (zeros random, cycles random, zeros trained, cycles trained). Conv1 reads the image: 9,582 cycles, no zeros.
COMPUTE = {"conv2": (0.06, 89838, 0.44, 81489), "conv3": (0.11, 43636, 0.87, 31801), "dense": (0.10, 4335, 0.74, 3446)}
CONV1_COMPUTE = 9582
MODEL_CYCLES = 219598                       # trained ReLU model, image 0, 2026-10-31


def build(activation):
    work = os.path.join(REPO, "test", ".temp", "eval_act", activation)
    os.makedirs(work, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(work)
    try:
        net, _ = load_activation_model(os.path.join(REPO, "doc", "demo_notebooks", CHECKPOINTS[activation]))
        calibration, _ = data_create.mnist_images("train", range(200))
        model = o2m.get_model(net, calibration)
        params = oep.get_oep(1)
        model, lps = flow.build_layers(model, params)
        graph = onnx.load("simple_mnist_convnet_int8.onnx")
        image, _ = data_create.mnist_images("test", [0])
        dram, _ = flow.reference(model, lps, params, image[0, 0])
    finally:
        os.chdir(cwd)
    return net, model, lps, params, graph, dram


class Hardware:
    """numpy model of the integer arithmetic (as scan31.py, with the activation modes)."""

    def __init__(self, model, lps, dram, rounding=False, table_option=None):
        self.model, self.lps, self.rounding = model, lps, rounding
        self.W = {n: np.array(dram.weights[n], dtype=np.int64) for n in (0, 2, 4)}       # [c][f][a][b]
        self.B = {n: np.array(dram.bias[n], dtype=np.int64) for n in (0, 2, 4, 5)}
        self.WD = np.array(dram.weights[5], dtype=np.int64)
        self.order = DRAM.DRAMContents.dense_input_order(lps, 5, model[5])
        self.tables = {}
        for n in (0, 2, 4):
            if lps[n].act_mode == "table":
                t = np.array(lps[n].act_table, dtype=np.int64)
                if table_option == "band1":
                    t = np.where(np.abs(t) <= 1, 0, t)
                elif table_option == "neg0":
                    t = np.maximum(t, 0)
                self.tables[n] = t

    def requantize(self, v, mant, shift):
        return (mant * v + ((1 << (shift - 1)) if self.rounding and shift > 0 else 0)) >> shift

    def activate(self, psum, n):
        p = self.lps[n]
        mant, shift = p.quantize[0]
        q = self.requantize(psum, mant, shift)
        if p.act_mode == "leaky":
            neg = self.requantize(psum, *p.act_negative)
            return np.clip(np.where(psum < 0, neg, q), -128, 127)
        if p.act_mode == "table":
            return self.tables[n][np.clip(q, -128, 127) + 128]
        return np.clip(q, p.act_min, 127)

    def conv(self, x, n):
        C, X, Y = x.shape
        w = self.W[n]
        pad = np.zeros((C, X + 2, Y + 2), np.int64)
        pad[:, 1:-1, 1:-1] = x
        psum = np.broadcast_to(self.B[n][:, None, None], (w.shape[1], X, Y)).copy()
        for i in range(3):
            for j in range(3):
                psum += np.einsum("cf,cxy->fxy", w[:, :, j, i], pad[:, i:i + X, j:j + Y])
        return self.activate(psum, n)

    @staticmethod
    def pool(x):
        C, X, Y = x.shape
        return x.reshape(C, X // 2, 2, Y // 2, 2).max(axis=(2, 4))

    def run(self, image):
        x = np.zeros((2, 28, 28), np.int64)                      # bug #17 padding channel: zero input
        x[0] = o2m.quantize_input(self.model, image)
        a1 = self.conv(x, 0)
        p1 = self.pool(a1)
        a2 = self.conv(p1, 2)
        p2 = self.pool(a2)
        a3 = self.conv(p2, 4)
        dense_in = a3.reshape(-1)[self.order]
        return self.B[5] + self.WD @ dense_in, {"conv1_out": a1, "conv2": p1, "conv3": p2, "dense": dense_in}


def check_against_reference(model, lps, params, hw, images):
    for i in range(len(images)):
        _, ref = flow.reference(model, lps, params, images[i, 0])
        ps, layers = hw.run(images[i, 0])
        assert (ps == ref[5].ravel()).all(), "Dense psums differ from the testbench reference"
        assert (layers["conv1_out"] == ref[(0, "out")]).all() and (layers["dense"] == ref[(4, "out")]).all()


def predicted_compute(zeros):
    """Compute cycles of conv1..dense from the zero fraction of conv2, conv3 and dense inputs (linear per layer)."""
    total = CONV1_COMPUTE
    for layer, (z0, c0, z1, c1) in COMPUTE.items():
        total += c0 + (zeros[layer] - z0) * (c1 - c0) / (z1 - z0)
    return total


def main():
    images, labels = data_create.mnist_images("test", range(N))
    rows = []
    relu_compute = None
    for activation in CHECKPOINTS:
        net, model, lps, params, graph, dram = build(activation)
        with torch.no_grad():
            float_acc = float((net(torch.from_numpy(images)).argmax(1).numpy() == labels).mean())
        sess = ort.InferenceSession(graph.SerializeToString())
        ort_pred = np.concatenate([sess.run(["output"], {"input": images[i:i + 500]})[0].argmax(1)
                                   for i in range(0, N, 500)])
        ort_acc = float((ort_pred == labels).mean())
        options = [("floor", False, None), ("round", True, None)]
        if activation in ("silu", "hardswish"):
            options += [("round+band1", True, "band1"), ("round+neg0", True, "neg0")]
        for label, rounding, table_option in options:
            for n in (0, 2, 4):
                lps[n].act_round = rounding
            hw = Hardware(model, lps, dram, rounding, table_option)
            if table_option is None:
                check_against_reference(model, lps, params, hw, images[:2])
            correct = 0
            zeros = {"conv1_out": 0.0, "conv2": 0.0, "conv3": 0.0, "dense": 0.0}
            for i in range(N):
                ps, layers = hw.run(images[i, 0])
                correct += int(np.argmax(ps)) == int(labels[i])
                for k in zeros:
                    zeros[k] += float((layers[k] == 0).mean()) / N
            compute = predicted_compute(zeros)
            if activation == "relu" and label == "floor":
                relu_compute = compute
            rows.append((activation, label, 100 * float_acc, 100 * ort_acc, 100.0 * correct / N, zeros, compute))
            print(rows[-1], flush=True)
        for n in (0, 2, 4):
            lps[n].act_round = False
    print("\nMNIST test images 0..%d; numpy model == testbench reference on images 0, 1 for every variant and rounding" % (N - 1))
    print("| activation | option | float | ONNX Runtime int8 | hardware int8 | zeros conv1 out | conv2 in | conv3 in | "
          "dense in | predicted compute | vs ReLU (cycles, % of the model) |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for activation, label, fa, oa, ha, z, c in rows:
        d = c - relu_compute
        print("| %s | %s | %.2f %% | %.2f %% | %.2f %% | %.0f %% | %.0f %% | %.0f %% | %.0f %% | %d | %+d (%+.1f %%) |" % (
            activation, label, fa, oa, ha, 100 * z["conv1_out"], 100 * z["conv2"], 100 * z["conv3"],
            100 * z["dense"], c, d, 100.0 * d / MODEL_CYCLES))


if __name__ == "__main__":
    main()
