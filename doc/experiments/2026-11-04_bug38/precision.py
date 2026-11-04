"""precision.py <n_images> (from the repository root, about 5 minutes for 20 images): the toolchain reference (= what the RTL computes) against ONNX Runtime for the four trained
MNIST models, with the requantization mantissa of 8 and of 24 bits (onnx2model.MANT_BITS, bug #38)."""
import json, os, sys, tempfile
REPO = "/home/truongphi/OpenEye_orig"
sys.path[:0] = [os.path.join(REPO, "src"), os.path.join(REPO, "test"), os.path.join(REPO, "models")]
import numpy as np
import onnx
import test_onnx_model_flow as flow
import test_activation as ta
from open_eye import DRAM, data_create, onnx2model as o2m, open_eye_parameters as oep
from train_mnist import load_activation_model

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
for k, v in flow.PLATFORM.items():
    os.environ[k] = v
calibration, _ = data_create.mnist_images("train", range(200))
images, labels = data_create.mnist_images("test", range(N))
result = {}
for bits in (8, 24):
    o2m.MANT_BITS = bits
    for name in ("relu", "leaky_relu", "silu", "hardswish"):
        ck = flow.CHECKPOINT if name == "relu" else ta.checkpoint(name)
        net, _ = load_activation_model(ck)
        cwd = os.getcwd(); os.chdir(tempfile.mkdtemp())
        try:
            model = o2m.get_model(net, calibration)
            params = oep.get_oep(1)
            model, lps = flow.build_layers(model, params)
            graph = onnx.load("simple_mnist_convnet_int8.onnx")
        finally:
            os.chdir(cwd)
        order = DRAM.DRAMContents.dense_input_order(lps, 5, model[5])
        diffs = {0: [], 2: [], 4: []}
        correct = 0
        for i in range(N):
            _, ref = flow.reference(model, lps, params, images[i, 0])
            if name == "relu":
                convs, _, logits = flow.onnxruntime_tensors(graph, images[i, 0])
                theirs = [np.maximum(convs[0][0], 0), np.maximum(convs[1][0], 0), np.maximum(convs[2][0], 0).reshape(-1)[order]]
            else:
                acts, logits = ta.activation_outputs(graph, images[i, 0])
                theirs = [acts[0][0], acts[1][0], acts[2][0].reshape(-1)[order]]
            for n, (a, b) in zip((0, 2, 4), zip([ref[(0, "out")], ref[(2, "out")], ref[(4, "out")]], theirs)):
                diffs[n].append((a.astype(np.int64) - b.astype(np.int64)).ravel())
            correct += int(np.argmax(ref[5].ravel())) == int(labels[i])
        row = {"mant": [lps[n].quantize[0] for n in (0, 2, 4, 5)], "correct": correct}
        for n, d in diffs.items():
            d = np.concatenate(d)
            row[f"conv{n // 2 + 1}"] = {"mean": round(float(d.mean()), 3), "max": int(np.abs(d).max()),
                                        "within1": round(float((np.abs(d) <= 1).mean()), 4), "exact": round(float((d == 0).mean()), 4)}
        result[f"{name}_{bits}"] = row
        print(name, bits, json.dumps(row), flush=True)
json.dump(result, open("precision.json", "w"), indent=1)   # in the working directory
