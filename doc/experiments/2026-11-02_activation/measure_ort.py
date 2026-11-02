"""measure_ort.py: per conv layer, the difference between the toolchain reference (= the planned hardware) and ONNX
Runtime running the same statically quantized model, for the three trained activation variants of models/train_mnist.py,
with the quantizer's floor and with rounding to nearest, on MNIST test images 0-3 (max, fraction within 1, mean).
The tolerances of test/test_activation.py come from this. Run from the repository root:
  venv/bin/python doc/experiments/2026-11-02_activation/measure_ort.py"""
import os, sys, types
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 3))
sys.path[:0] = [os.path.join(REPO, "test"), os.path.join(REPO, "models"), os.path.join(REPO, "src")]
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np, onnx
import test_onnx_model_flow as flow
import test_activation as ta
for k, v in flow.PLATFORM.items():
    os.environ[k] = v
from open_eye import DRAM, data_create, onnx2model as o2m, open_eye_parameters as oep
from train_mnist import load_activation_model
work = os.path.join(REPO, "test", ".temp", "measure_ort")
os.makedirs(work, exist_ok=True)
os.chdir(work)                                   # onnx2model writes its .onnx files into the working directory
calibration, _ = data_create.mnist_images("train", range(200))
images, labels = data_create.mnist_images("test", range(4))
for name in ta.VARIANTS:
    net, _ = load_activation_model(ta.checkpoint(name))
    model = o2m.get_model(net, calibration)
    params = oep.get_oep(1)
    model, lps = flow.build_layers(model, params)
    graph = onnx.load("simple_mnist_convnet_int8.onnx")
    order = DRAM.DRAMContents.dense_input_order(lps, 5, model[5])
    for rounding in (False, True):
        for n in (0, 2, 4):
            lps[n].act_round = rounding
        worst = {0: [], 2: [], 4: []}
        for i in range(4):
            _, ref = flow.reference(model, lps, params, images[i, 0])
            acts, logits = ta.activation_outputs(graph, images[i, 0])
            theirs = {0: acts[0][0], 2: acts[1][0], 4: acts[2][0].reshape(-1)[order]}
            for n in (0, 2, 4):
                d = ref[(n, "out")].astype(np.int64) - theirs[n].astype(np.int64)
                worst[n].append((np.abs(d).max(), (np.abs(d) <= 1).mean(), d.mean()))
        print(name, "round" if rounding else "floor", {n: "max %d, <=1 %.3f, mean %+.2f" % (max(w[0] for w in worst[n]), min(w[1] for w in worst[n]), np.mean([w[2] for w in worst[n]])) for n in worst})
