"""run_same.py <activation> <sparse|dense> [image]: the trained ReLU MNIST model (doc/demo_notebooks/
mnist_unquantized_model.pth) with its activation replaced by <activation> (none, relu, leaky_relu, silu, hardswish;
weights unchanged), on the RTL with the profiler, as test/cocotb_fpga/test_real_model.py (MNIST_REAL, CR 2 X 4 Y 3, QUANT_AMOUNT
64, DMA 64 bit). The same weights and input for every activation, so the cycles differ by the activation alone; "none"
gives the network without an activation, which no trained checkpoint has. Based on
doc/experiments/2026-11-02_activation/run_same_weights.py, with the hardware mode and a separate simulation directory per
mode. Profile: test/.temp/same_<activation>_<mode>/profile.json. From the repository root:
  venv/bin/python doc/experiments/2026-11-26_mnist_same_weights/run_same.py none sparse"""
import os
import sys
import types

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
activation, mode = sys.argv[1], sys.argv[2]
image = sys.argv[3] if len(sys.argv) > 3 else "0"
os.environ["SPARSITY_EN"] = {"sparse": "1", "dense": "0"}[mode]

relu = torch.load(os.path.join(REPO, "doc", "demo_notebooks", "mnist_unquantized_model.pth"), map_location="cpu")
checkpoint = os.path.join(REPO, "test", ".temp", "same_weights", f"relu_weights_{activation}_{mode}.pth")
os.makedirs(os.path.dirname(checkpoint), exist_ok=True)
torch.save({"model_state_dict": relu["model_state_dict"], "activation": activation, "negative_slope": 0.1}, checkpoint)

sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

real_run = cocotb_test.simulator.run


def run(**kw):
    kw["extra_env"] = dict(kw["extra_env"], USE_RANDOM_VALUES="0", OPENEYE_MODEL_WEIGHTS=checkpoint,
                           OPENEYE_INPUT_IMAGE=image, OPENEYE_FAIL_ON_STALL="400000", OPENEYE_PROFILE="1")
    return real_run(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"same_{activation}_{mode}"))
verdict = "PASS"
try:
    conv._run_conv_const("MNIST_REAL", 8, 2, num_glb_iact=1, input_channels=1, request=request, input_height=28,
                         quant_amount=64, dma_bitwidth=64, random_data=True, expect_layers=6)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__}: {e})"
print(f"RESULT {activation} {mode} image {image}: {verdict}; profile test/.temp/same_{activation}_{mode}/profile.json",
      flush=True)
