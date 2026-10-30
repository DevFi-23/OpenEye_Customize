"""explain35.py <dump dir> <image>: tests explanations of the wrong conv3 outputs (bug #35) of a run35.py run.
Rebuilds the toolchain's reference of the real model for MNIST test image <image> (as test/test_onnx_model_flow.py),
recomputes conv3 with numpy from conv3's input, its int8 weights, int32 biases and the quantizer (floor(mant * psum /
2^shift), clamped to [act_min, 127]) on a wider x range (the padding pixel x = 7 of the 7-wide rows included), and
compares every wrong DUT value (conv3_compare.npz of analyze35.py) with candidate values. Run from the repository root."""
import collections
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test"))
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
dump_dir, image = sys.argv[1], int(sys.argv[2])
import test_onnx_model_flow as flow  # noqa: E402
for key, value in flow.PLATFORM.items():
    os.environ[key] = value
sys.path.insert(0, os.path.join(REPO, "models"))
from mnist_conv_net import SimpleMNISTConvNet, load_simple_mnist_model  # noqa: E402
from open_eye import data_create, onnx2model as o2m, open_eye_parameters as oep  # noqa: E402

cwd = os.getcwd()
os.makedirs(os.path.join(dump_dir, "onnx"), exist_ok=True)
os.chdir(os.path.join(dump_dir, "onnx"))
net = SimpleMNISTConvNet()
load_simple_mnist_model(flow.CHECKPOINT, net)
calibration, _ = data_create.mnist_images("train", range(200))
model = o2m.get_model(net, calibration)
params = oep.get_oep(1)
model, lps = flow.build_layers(model, params)
images, labels = data_create.mnist_images("test", [image])
dram, ref = flow.reference(model, lps, params, images[0, 0])
os.chdir(cwd)

L = 4
inp = np.array(dram.fmap[L], dtype=np.int64)                  # conv3 input [c][x][y]
w = np.array(dram.weights[L], dtype=np.int64)                 # [c][f][a][b]
bias = np.array(dram.bias[L], dtype=np.int64)
mant, shift = lps[L].quantize[0]
act_min = lps[L].act_min
C, X, Y = inp.shape
F = w.shape[1]
K = w.shape[2]
p = K // 2
EXTRA = 2                                                      # outputs at x = X .. X+EXTRA-1 (padding pixels)
pad = np.zeros((C, X + EXTRA + 2 * p, Y + 2 * p), np.int64)
pad[:, p:p + X, p:p + Y] = inp
psum = np.zeros((F, X + EXTRA, Y), np.int64)
for f in range(F):
    psum[f] = bias[f]
    for c in range(C):
        k = w[c, f].T                                          # as run31.dut_and_numpy / verify_conv_output
        for i in range(K):
            for j in range(K):
                psum[f] += k[i][j] * pad[c, i:i + X + EXTRA, j:j + Y]


def quant(v):
    return np.clip((mant * v) >> shift, act_min, 127)


q = quant(psum)
r = np.load(os.path.join(dump_dir, "conv3_compare.npz"))
exp, dut = r["exp"], r["dut"]
assert (q[:, :X] == exp).all(), "numpy conv3 != toolchain reference"
print("numpy conv3 == the toolchain reference at all %d outputs; quantizer %d/%d act_min %d" % (exp.size, mant, shift, act_min))
bad = np.argwhere(dut != exp)
print("%d wrong outputs; by x %s" % (len(bad), dict(sorted(collections.Counter(int(x) for _, x, _ in bad).items()))))
tests = {
    "padding pixel x=7 of the same filter and y": lambda f, x, y: q[f, X, y],
    "same position, filter f^1 (bias pair)": lambda f, x, y: q[f ^ 1, x, y],
    "x=7 of filter f^1": lambda f, x, y: q[f ^ 1, X, y],
    "x-1 same filter": lambda f, x, y: q[f, x - 1, y],
    "same filter, y-1": lambda f, x, y: q[f, x, y - 1] if y else None,
    "same filter, y+1": lambda f, x, y: q[f, x, y + 1] if y + 1 < Y else None,
    "0": lambda f, x, y: 0,
}
for name, fn in tests.items():
    hits = sum(int(fn(f, x, y) == dut[f, x, y]) for f, x, y in bad)
    print("  DUT == %-45s at %d of %d" % (name, hits, len(bad)))
print("wrong (f, x, y): expected, DUT, x=7 value, psum, x=7 psum:")
for f, x, y in bad[:40]:
    print("  ", (int(f), int(x), int(y)), int(exp[f, x, y]), int(dut[f, x, y]), int(q[f, X, y]), int(psum[f, x, y]), int(psum[f, X, y]))
np.savez(os.path.join(dump_dir, "conv3_numpy.npz"), psum=psum, q=q, inp=inp, w=w, bias=bias)
