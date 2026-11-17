"""run_round.py <activation> <0|1> <tag>: test_real_model's trained MNIST model (image 0, OPENEYE_PROFILE=1) with the
rounding of every activation forced to floor (0) or round to nearest (1) through probe_round.py. SPARSITY_EN from the
environment (1 sparse, 0 dense). Output: test/.temp/round_<tag>/ (cocotb_sim.log, profile.json). From the repository root:
  SPARSITY_EN=0 venv/bin/python doc/experiments/2026-11-12_rounding_modes/run_round.py relu 1 relu_dense_round"""
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

activation, rounding, tag = sys.argv[1], sys.argv[2], sys.argv[3]
real = cocotb_test.simulator.run


def run(**kw):
    kw["module"] = "probe_round"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    kw["extra_env"] = dict(kw["extra_env"], P_ROUND=rounding, OPENEYE_PROFILE="1")
    return real(**kw)


cocotb_test.simulator.run = run
checkpoint = trm.CHECKPOINT if activation == "relu" else os.path.join(trm.DEMO, f"mnist_{activation}_model.pth")
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"round_{tag}"))
mp = MonkeyPatch()
verdict = "PASS"
try:
    trm.run_trained(checkpoint, 0, request, mp)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
finally:
    mp.undo()
log = open(os.path.join(REPO, "test", ".temp", f"round_{tag}", "cocotb_sim.log"), errors="replace").read()
cls = [l.split("DUT class")[1].split("(")[0].strip() for l in log.splitlines() if "DUT class" in l]
forced = [l.split("P_ROUND=")[1][:60] for l in log.splitlines() if "P_ROUND=" in l]
print(f"RESULT {tag} {activation} round={rounding} SPARSITY_EN={os.environ.get('SPARSITY_EN', '1')}: {verdict}; "
      f"class {cls[:1]}; forced {forced[:1]}")
