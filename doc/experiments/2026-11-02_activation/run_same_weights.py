"""run_same_weights.py <activation> [image]: the trained ReLU MNIST model (doc/demo_notebooks/mnist_unquantized_model.pth)
with its activation replaced by <activation> (leaky_relu, silu, hardswish; weights unchanged), on the RTL with the
profiler, as test/cocotb_fpga/test_real_model.py (MNIST_REAL platform, QUANT_AMOUNT 64, DMA 64 bit). The same weights and
input for every activation, so the cycles differ by the activation alone (doc/experiments/2026-11-02_activation_profiler.md,
section 4b). The checkpoint goes to test/.temp/same_weights/, the profile to test/.temp/same_<activation>/profile.json.
About 20 minutes. Run from the repository root:
  venv/bin/python doc/experiments/2026-11-02_activation/run_same_weights.py silu 0"""
import os
import sys
import types

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
activation = sys.argv[1]
image = sys.argv[2] if len(sys.argv) > 2 else "0"

relu = torch.load(os.path.join(REPO, "doc", "demo_notebooks", "mnist_unquantized_model.pth"), map_location="cpu")
checkpoint = os.path.join(REPO, "test", ".temp", "same_weights", f"relu_weights_{activation}.pth")
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
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"same_{activation}"))
verdict = "PASS"
try:
    conv._run_conv_const("MNIST_REAL", 8, 2, num_glb_iact=1, input_channels=1, request=request, input_height=28,
                         quant_amount=64, dma_bitwidth=64, random_data=True, expect_layers=6)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__}: {e})"
print(f"RESULT {activation} image {image}: {verdict}; profile test/.temp/same_{activation}/profile.json")
