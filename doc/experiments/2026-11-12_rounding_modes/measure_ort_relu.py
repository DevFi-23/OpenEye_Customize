"""measure_ort_relu.py: the method of doc/experiments/2026-11-02_activation/measure_ort.py (which covers only the three
new activations) for the original trained ReLU model: per conv layer, floor and round to nearest, MNIST test images 0-3,
the difference to ONNX Runtime (max, fraction within 1 and exact, worst image; mean) and the zero share of the output.
ONNX Runtime keeps ReLU in float between DequantizeLinear and QuantizeLinear at the same scale, so its int8 ReLU output
is max(QLinearConv output, 0). Run from the repository root:
  venv/bin/python doc/experiments/2026-11-12_rounding_modes/measure_ort_relu.py"""
import os, sys
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 3))
sys.path[:0] = [os.path.join(REPO, "test"), os.path.join(REPO, "models"), os.path.join(REPO, "src")]
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np, onnx, onnxruntime as ort
import test_onnx_model_flow as flow
for k, v in flow.PLATFORM.items():
    os.environ[k] = v
from open_eye import DRAM, data_create, onnx2model as o2m, open_eye_parameters as oep
from train_mnist import load_activation_model
work = os.path.join(REPO, "test", ".temp", "measure_ort_relu")
os.makedirs(work, exist_ok=True)
os.chdir(work)
calibration, _ = data_create.mnist_images("train", range(200))
images, _ = data_create.mnist_images("test", range(4))
net, _ = load_activation_model(os.path.join(REPO, "doc", "demo_notebooks", "mnist_unquantized_model.pth"))
model = o2m.get_model(net, calibration)
params = oep.get_oep(1)
model, lps = flow.build_layers(model, params)
graph = onnx.load("simple_mnist_convnet_int8.onnx")
convs = [n.output[0] for n in graph.graph.node if n.op_type == "QLinearConv"]
g = onnx.ModelProto(); g.CopyFrom(graph)
for t in convs:
    vi = onnx.ValueInfoProto(); vi.name = t; g.graph.output.append(vi)
sess = ort.InferenceSession(g.SerializeToString())
order = DRAM.DRAMContents.dense_input_order(lps, 5, model[5])
print("act_round default:", [bool(lps[n].act_round) for n in (0, 2, 4)], "act_min:", [lps[n].act_min for n in (0, 2, 4)])
for rounding in (False, True):
    for n in (0, 2, 4):
        lps[n].act_round = rounding
    worst = {0: [], 2: [], 4: []}
    zeros = {0: [], 2: [], 4: []}
    for i in range(4):
        _, ref = flow.reference(model, lps, params, images[i, 0])
        outs = sess.run(convs, {"input": images[i, 0][None, None].astype(np.float32)})
        theirs = {0: np.maximum(outs[0][0], 0), 2: np.maximum(outs[1][0], 0), 4: np.maximum(outs[2][0], 0).reshape(-1)[order]}
        for n in (0, 2, 4):
            d = ref[(n, "out")].astype(np.int64) - theirs[n].astype(np.int64)
            worst[n].append((np.abs(d).max(), (np.abs(d) <= 1).mean(), (d == 0).mean(), d.mean()))
            zeros[n].append((ref[(n, "out")] == 0).mean())
    print("relu", "round" if rounding else "floor",
          {n: "max %d, <=1 %.3f, exact %.3f, mean %+.2f, zeros %.1f%%" % (max(w[0] for w in worst[n]), min(w[1] for w in worst[n]),
              min(w[2] for w in worst[n]), np.mean([w[3] for w in worst[n]]), 100 * np.mean(zeros[n])) for n in worst})
