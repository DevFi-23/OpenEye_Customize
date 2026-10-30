"""run31.py <name> <pattern> [KEY=VALUE ...]: one conv layer (Convolution_Single) through probe31 with a chosen layer-0
input, 2x2 clusters, NUM_GLB_IACT 1, NUM_GLB_PSUM 4, NUM_GLB_WGHT 3, DMA 64, seed 1, random weights from the project's
Keras model, bias 1 (OPENEYE_BIAS_STEP=<s> for distinct biases). Then compares every DUT output with numpy (as
tools/verify_conv_output.py) and reports how many outputs differ and how many equal the bias alone.

Patterns: values of input channels 0..CH-1 in the DRAM layout fmap[c][x][y], x < W (INPUT_SIZE_X, the Keras
input's first spatial axis), y < H; a bug #17 padding channel stays 0:
  rand            random -31..31 without 0 (like DRAMContents)
  image:<i>       MNIST test image i as int8 0..127 (round(p*127/255)) as fmap[0][row][column], only 28x28 (CH 1)
  image_nz:<i>    the same with every 0 replaced by 1
  zfrac:<p>       random, a fraction p of the values set to 0 (scattered)
  zx:<a>:<b>      random, x = a..b-1 zero in every channel
  zy:<a>:<b>      random, y = a..b-1 zero in every channel
  zchan:<c>       random, channel c zero everywhere
  keep:<x0>:<x1>:<y0>:<y1>  zero except the random block x0..x1-1, y0..y1-1
Runner options: W (width, 8), H (height, 4), CH (input channels, 4), NF (filters, 4), QA (32), CR (2), IACT (1),
L (LAYER of data_create, Convolution_Single), K (a Dense layer's input length; patterns rand and zk:<a>:<b>).
Other KEY=VALUE go to the simulation (testbench switches such as TRACE_*, OPENEYE_BIAS_STEP).
Log: test/.temp/b31_<name>/cocotb_sim.log. Run from the repository root, e.g.
  venv/bin/python doc/experiments/2026-10-30_bug31/run31.py img0 image:0 W=28 H=28 CH=1 NF=4"""
import os
import pickle
import sys
import types

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 3))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

name, pattern = sys.argv[1], sys.argv[2]
extra = dict(a.split("=", 1) for a in sys.argv[3:])
opt = {k: extra.pop(k) for k in ("W", "H", "CH", "NF", "QA", "CR", "IACT", "L", "K") if k in extra}
LAYER = opt.get("L", "Convolution_Single")
K = int(opt.get("K", 0))
W, H, CH = int(opt.get("W", 8)), int(opt.get("H", 4)), int(opt.get("CH", 4))
sim = os.path.join(REPO, "test", ".temp", f"b31_{name}")
os.makedirs(sim, exist_ok=True)


def make_input():
    rng = np.random.default_rng(31)
    shape = (K,) if K else (CH, W, H)
    rand = rng.integers(1, 32, size=shape) * rng.choice([-1, 1], size=shape)
    a = rand
    for part in pattern.split("+"):                 # patterns joined by + apply one after the other
        a = apply(part, a, rand, rng)
    return a


def apply(part, a, rand, rng):
    kind, *args = part.split(":")
    if kind == "rand":
        return rand.copy()
    if kind in ("image", "image_nz"):
        with np.load(os.path.expanduser("~/.keras/datasets/mnist.npz")) as d:
            img = np.rint(d["x_test"][int(args[0])] * 127.0 / 255.0).astype(np.int64)
        assert (CH, H, W) == (1, 28, 28), "image patterns are 28x28x1"
        if kind == "image_nz":
            img[img == 0] = 1
        return img[None]
    a = a.copy()
    if kind == "zfrac":
        a[rng.random(a.shape) < float(args[0])] = 0
        return a
    if kind == "zk":                                 # Dense input k = a..b-1 zero
        a[int(args[0]):int(args[1])] = 0
        return a
    if kind == "zx":
        a[:, int(args[0]):int(args[1]), :] = 0
    elif kind == "zy":
        a[:, :, int(args[0]):int(args[1])] = 0
    elif kind == "zchan":
        a[int(args[0])] = 0
    elif kind == "keep":
        x0, x1, y0, y1 = map(int, args)
        keep = np.zeros_like(a)
        keep[:, x0:x1, y0:y1] = a[:, x0:x1, y0:y1]
        a = keep
    else:
        raise SystemExit(f"unknown pattern {part}")
    return a


iact = make_input()
np.save(os.path.join(sim, "iact.npy"), iact)
conv.INPUT_SIZE_X = W
conv.NUM_FILTERS = int(opt.get("NF", 4))
orig_run = cocotb_test.simulator.run


def run(**kw):
    env = kw.setdefault("extra_env", {})
    env.update({"OPENEYE_SEED": "1", "OPENEYE_DUMP_VERIFY": "1", "B31_IACT": os.path.join(sim, "iact.npy")})
    env.update(extra)
    kw["module"] = "probe31"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    return orig_run(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"b31_{name}"))
verdict = "PASS"
try:
    conv._run_conv_const(LAYER, 8, int(opt.get("CR", 2)), num_glb_iact=int(opt.get("IACT", 1)),
                         input_channels=1 if K else CH, request=request, input_height=1 if K else H,
                         quant_amount=int(opt.get("QA", 32)), dma_bitwidth=64, random_data=True, expect_layers=1)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"


def dut_and_numpy(sim_dir):
    """DUT outputs and numpy results [F][X][Y] from verify_layer0.pkl and demo/layer_0_0/output.txt."""
    dump = pickle.load(open(os.path.join(sim_dir, "verify_layer0.pkl"), "rb"))
    bits, spw = dump["psum_bits"], dump["dma_bits"] // 32
    fm, wt = np.array(dump["fmap"], np.int64), np.array(dump["weights"], np.int64)
    F = dump["filters"]
    b = np.array(dump["bias"], np.int64)[:F]
    C, X, Y = fm.shape
    K = wt.shape[-1]
    p = K // 2
    pad = np.zeros((C, X + 2 * p, Y + 2 * p), np.int64)
    pad[:, p:p + X, p:p + Y] = fm
    exp = np.zeros((F, X, Y), np.int64)
    for f in range(F):
        exp[f] = b[f]
        for c in range(C):
            k = wt[c, f].T
            for i in range(K):
                for j in range(K):
                    exp[f] += k[i][j] * pad[c, i:i + X, j:j + Y]
    order = dump["output_order"]
    if order and isinstance(order[0], list) and (not order[0] or isinstance(order[0][0], (list, type(None)))):
        order = [pos for rep in order for pos in rep]
    dut = np.full((F, X, Y), 10 ** 9, np.int64)
    lines = [l.strip() for l in open(os.path.join(sim_dir, "demo", "layer_0_0", "output.txt")) if l.strip()]
    for wi, line in enumerate(lines):
        if set(line.lower()) - {"0", "1"}:
            continue
        word = int(line, 2)
        for i in range(spw):
            idx = spw * wi + i
            pos = order[idx] if idx < len(order) else None
            if pos is not None:
                v = (word >> (bits * i)) & ((1 << bits) - 1)
                dut[tuple(pos)] = v - (1 << bits) if v >= 1 << (bits - 1) else v
    return dut, exp, b, fm


if K:                                                  # Dense: the testbench lists the differing outputs
    import re
    log = open(os.path.join(sim, "cocotb_sim.log"), errors="replace").read()
    pairs = re.findall(r"f = (\d+): reference (-?\d+), DUT (-?\d+)", log)
    m = re.search(r"(\d+) of (\d+) outputs differ", log)
    print(f"RESULT {name} {pattern} (Dense K={K}, {int((iact == 0).sum())} inputs 0): {verdict}; "
          f"{m.group(0) if m else '0 outputs differ'}; DUT == bias (f+1) at {sum(int(d) == int(f) + 1 for f, r, d in pairs)} "
          f"of the {len(pairs)} listed")
    sys.exit(0)
try:
    dut, exp, b, fm = dut_and_numpy(sim)
    bad = dut != exp
    only_bias = dut == b[:, None, None]
    rows = sorted(set(np.nonzero(bad)[1].tolist()))
    print(f"RESULT {name} {pattern} ({CH}x{H}x{W}, {int((fm == 0).sum())}/{fm.size} inputs 0 incl. padding channels): "
          f"{verdict}; DUT vs numpy {int(bad.sum())}/{bad.size} differ; DUT == bias at {int(only_bias.sum())} "
          f"(numpy == bias at {int((exp == b[:, None, None]).sum())}); wrong outputs at x {rows}")
    np.savez(os.path.join(sim, "result.npz"), dut=dut, exp=exp, bias=b, fmap=fm)
except Exception as e:
    print(f"RESULT {name} {pattern}: {verdict}; no output decoded ({type(e).__name__}: {e})")
