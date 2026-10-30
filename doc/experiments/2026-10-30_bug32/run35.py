"""run35.py <name> <image> [KEY=VALUE ...]: the trained PyTorch MNIST model on the RTL as test/cocotb_fpga/test_real_model.py
(OpenEye_FPGA_tb, USE_RANDOM_VALUES=0, OPENEYE_MODEL_WEIGHTS, OPENEYE_INPUT_IMAGE=<image>, MNIST_REAL platform,
QUANT_AMOUNT 64) with the cocotb module probe32: every iact buffer check is dumped (B35_DUMP, into
test/.temp/b35_<name>/dump). KEY=VALUE go to the simulation, e.g. B32_REVERSE=1 (bias order of bug #32 corrected in
the simulation process). About 10 minutes. Run from the repository root:
  venv/bin/python doc/experiments/2026-10-30_bug32/run35.py img0_rev 0 B32_REVERSE=1"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

name, image = sys.argv[1], sys.argv[2]
extra = dict(a.split("=", 1) for a in sys.argv[3:])
sim = os.path.join(REPO, "test", ".temp", f"b35_{name}")
CHECKPOINT = os.path.join(REPO, "doc", "demo_notebooks", "mnist_unquantized_model.pth")
real_run = cocotb_test.simulator.run


def run(**kw):
    kw["extra_env"] = dict(kw["extra_env"], USE_RANDOM_VALUES="0", OPENEYE_MODEL_WEIGHTS=CHECKPOINT,
                           OPENEYE_INPUT_IMAGE=str(image), OPENEYE_FAIL_ON_STALL="400000",
                           B35_DUMP=os.path.join(sim, "dump"), **extra)
    kw["module"] = "probe32"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE, os.path.join(REPO, "doc", "experiments",
                                                                                  "2026-10-30_bug31")]
    return real_run(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"b35_{name}"))
verdict = "PASS"
try:
    conv._run_conv_const("MNIST_REAL", 8, 2, num_glb_iact=1, input_channels=1, request=request, input_height=28,
                         quant_amount=64, dma_bitwidth=64, random_data=True, expect_layers=6)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
print(f"RESULT {name} image {image} {extra}: {verdict}; log {os.path.join(sim, 'cocotb_sim.log')}")
