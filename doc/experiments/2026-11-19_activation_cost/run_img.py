"""run_img.py <activation> <image> <tag>: test_real_model's trained MNIST model for one activation (relu, leaky_relu, silu,
hardswish) and one test image, OPENEYE_PROFILE=1, default rounding of the toolchain. SPARSITY_EN from the environment
(1 sparse, 0 dense). Output test/.temp/img_<tag>/profile.json. From the repository root:
  venv/bin/python doc/experiments/2026-11-19_activation_cost/run_img.py silu 6 silu_img6_sparse"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
from _pytest.monkeypatch import MonkeyPatch  # noqa: E402
import cocotb_test.simulator  # noqa: E402
import test_real_model as trm  # noqa: E402

activation, image, tag = sys.argv[1], int(sys.argv[2]), sys.argv[3]
real = cocotb_test.simulator.run


def run(**kw):
    kw["extra_env"] = dict(kw["extra_env"], OPENEYE_PROFILE="1")
    return real(**kw)


cocotb_test.simulator.run = run
checkpoint = trm.CHECKPOINT if activation == "relu" else os.path.join(trm.DEMO, f"mnist_{activation}_model.pth")
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"img_{tag}"))
mp = MonkeyPatch()
verdict = "PASS"
try:
    trm.run_trained(checkpoint, image, request, mp)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
finally:
    mp.undo()
print(f"RESULT {tag} {activation} image={image} SPARSITY_EN={os.environ.get('SPARSITY_EN', '1')}: {verdict}")
