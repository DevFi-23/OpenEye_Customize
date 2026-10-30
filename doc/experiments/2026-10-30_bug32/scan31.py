"""scan31.py [N]: how often bugs #31 and #32 hit the trained MNIST model on real test images (Python only, no RTL).

Builds the model as OpenEye_FPGA_tb with OPENEYE_MODEL_WEIGHTS does (onnx2model static quantization, LayerParameters,
DRAMContents) and runs MNIST test images 0..N-1 through a numpy model of the hardware's arithmetic (conv with the
DRAM weights and biases, floor(mant * psum / 2^shift) clamped to [act_min, 127], 2x2 max pooling, Dense in the
hardware's input order), checked equal to the testbench reference on image 0. Modes:
  exact   the reference
  #32     conv3 (two kernel groups) with the biases of the filter pairs (2k, 2k+1) swapped
  #31     conv2 / conv3: the first pass without a non-zero activation and every later pass of the layer not computed
          (pass order: output line y, filter refresh r, 4-channel chunk k; window = input lines y-1..y+1, the whole line;
          a refresh holds used_psum_per_PE * different_kernels_per_calculation filters), as measured on the RTL
  both    #31 and #32 (the conv layers as the RTL computes them today)
The Dense layer is computed exactly in every mode (bug #33, the Dense side of #31, is not modelled; the number of images
with a zero run of 65 or more Dense inputs is reported as a hint). SCAN31_VERBOSE=1 lists every image. Run from the
repository root.

scan31.py check <image> <mode> <dump dir>: compare the conv3 output of <mode> with the Dense input the RTL wrote back
(iact check 2 of a run35.py run of the same image; mode both without B32_REVERSE, #31 with it)."""
import collections
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test"))
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
CHECK = sys.argv[1:2] == ["check"]
N = int(sys.argv[2]) + 1 if CHECK else int(sys.argv[1]) if len(sys.argv) > 1 else 200
import test_onnx_model_flow as flow  # noqa: E402
for key, value in flow.PLATFORM.items():
    os.environ[key] = value
sys.path.insert(0, os.path.join(REPO, "models"))
from mnist_conv_net import SimpleMNISTConvNet, load_simple_mnist_model  # noqa: E402
from open_eye import DRAM, data_create, onnx2model as o2m, open_eye_parameters as oep  # noqa: E402

work = os.path.join(REPO, "test", ".temp", "scan31")
os.makedirs(work, exist_ok=True)
cwd = os.getcwd()
os.chdir(work)
net = SimpleMNISTConvNet()
load_simple_mnist_model(flow.CHECKPOINT, net)
calibration, _ = data_create.mnist_images("train", range(200))
model = o2m.get_model(net, calibration)
params = oep.get_oep(1)
model, lps = flow.build_layers(model, params)
images, labels = data_create.mnist_images("test", range(N))
dram, ref = flow.reference(model, lps, params, images[0, 0])
os.chdir(cwd)

W = {n: np.array(dram.weights[n], dtype=np.int64) for n in (0, 2, 4)}            # [c][f][a][b]
B = {n: np.array(dram.bias[n], dtype=np.int64) for n in (0, 2, 4, 5)}
Q = {n: (lps[n].quantize[0][0], lps[n].quantize[0][1], lps[n].act_min) for n in (0, 2, 4)}
WD = np.array(dram.weights[5], dtype=np.int64)                                    # [f][hardware input position]
REFRESH = {n: lps[n].used_psum_per_PE * lps[n].different_kernels_per_calculation for n in (2, 4)}
CHUNK = {n: lps[n].used_channels for n in (2, 4)}


def contributions(x, w):
    """Per-channel conv products [c][f][X][Y] of input x [c][X][Y] (zero padding 1, kernel w[c][f].T)."""
    C, X, Y = x.shape
    F = w.shape[1]
    pad = np.zeros((C, X + 2, Y + 2), np.int64)
    pad[:, 1:-1, 1:-1] = x
    out = np.zeros((C, F, X, Y), np.int64)
    for i in range(3):
        for j in range(3):
            out += w[:, :, j, i][:, :, None, None] * pad[:, None, i:i + X, j:j + Y]
    return out


def quant(v, n):
    mant, shift, act_min = Q[n]
    return np.clip((mant * v) >> shift, act_min, 127)


def first_empty_pass(x, n):
    C, X, Y = x.shape
    for y in range(Y):
        window = x[:, :, max(0, y - 1):y + 2]
        for r in range(B[n].size // REFRESH[n]):
            for k in range(C // CHUNK[n]):
                if not window[CHUNK[n] * k:CHUNK[n] * (k + 1)].any():
                    return y, r, k
    return None


def conv(x, n, bug31, bug32):
    con = contributions(x, W[n])
    bias = B[n].copy()
    if bug32 and n == 4:
        bias = bias.reshape(-1, 2)[:, ::-1].reshape(-1)
    psum = bias[:, None, None] + con.sum(0)
    hit = first_empty_pass(x, n) if n in (2, 4) else None
    if bug31 and hit:
        y0, r0, k0 = hit
        R = REFRESH[n]
        for y in range(y0, x.shape[2]):
            for r in range(B[n].size // R):
                fs = slice(R * r, R * (r + 1))
                if (y, r) < (y0, r0):
                    continue
                kept = CHUNK[n] * k0 if (y, r) == (y0, r0) else 0
                psum[fs, :, y] = bias[fs, None] + con[:kept, fs, :, y].sum(0)
    return quant(psum, n), hit


def pool(x):
    C, X, Y = x.shape
    return x.reshape(C, X // 2, 2, Y // 2, 2).max(axis=(2, 4))


ORDER = DRAM.DRAMContents.dense_input_order(lps, 5, model[5])


def run(image, bug31, bug32):
    x = np.zeros((2, 28, 28), np.int64)                         # bug #17 padding channel: zero input, weights 1
    x[0] = o2m.quantize_input(model, image)
    a, _ = conv(x, 0, bug31, bug32)
    a, h2 = conv(pool(a), 2, bug31, bug32)
    a, h3 = conv(pool(a), 4, bug31, bug32)
    dense_in = a.reshape(-1)[ORDER]
    return B[5] + WD @ dense_in, h2, h3, dense_in


ps, _, _, _ = run(images[0, 0], False, False)
assert (ps == ref[5].ravel()).all(), "numpy model != testbench reference"
print("numpy model == the testbench reference on image 0 (Dense psums)")
if CHECK:
    image, mode, dump_dir = int(sys.argv[2]), sys.argv[3], sys.argv[4]
    b31, b32 = {"exact": (0, 0), "#32": (0, 1), "#31": (1, 0), "both": (1, 1)}[mode]
    _, h2, h3, dense_in = run(images[image, 0], b31, b32)
    d = np.load(os.path.join(dump_dir, "iact_check_2.npz"), allow_pickle=True)
    dut = np.array([(int(w) >> (8 * b)) & 0xFF for w in d["dut"] for b in range(8)], dtype=np.int64)[:dense_in.size]
    dut = np.where(dut > 127, dut - 256, dut)
    print("image %d, mode %s (first empty pass conv2 %s, conv3 %s): model == RTL at %d of %d Dense inputs" % (
        image, mode, h2, h3, int((dut == dense_in).sum()), dense_in.size))
    sys.exit(0)
correct = collections.Counter()
hits = collections.Counter()
lines = collections.Counter()
zero_runs = 0
for i in range(N):
    for mode, (b31, b32) in {"exact": (0, 0), "#32": (0, 1), "#31": (1, 0), "both": (1, 1)}.items():
        ps, h2, h3, dense_in = run(images[i, 0], b31, b32)
        correct[mode] += int(np.argmax(ps)) == int(labels[i])
    if os.environ.get("SCAN31_VERBOSE"):
        print("image %d (label %d): first empty pass conv2 %s, conv3 %s" % (i, labels[i], h2, h3))
    hits["conv2"] += h2 is not None
    hits["conv3"] += h3 is not None
    hits["conv2 or conv3"] += (h2 is not None) or (h3 is not None)
    if h2:
        lines["conv2 y=%d" % h2[0]] += 1
    if h3:
        lines["conv3 y=%d" % h3[0]] += 1
    run_len = best = 0
    for v in dense_in:
        run_len = run_len + 1 if v == 0 else 0
        best = max(best, run_len)
    zero_runs += best >= 65
print("MNIST test images 0..%d" % (N - 1))
print("images with an empty pass (bug #31):", dict(hits))
print("line of the first empty pass:", dict(sorted(lines.items())))
print("images whose Dense input has a zero run of >= 65 inputs (bug #33 possible):", zero_runs)
print("accuracy:", {m: "%.1f %%" % (100.0 * c / N) for m, c in correct.items()})
