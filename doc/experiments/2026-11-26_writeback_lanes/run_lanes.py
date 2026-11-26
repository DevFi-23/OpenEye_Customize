"""run_lanes.py <tag> <seed> <glb_psum> [width] [filters]: Convolution_Stack <width> x 4 x 4 -> <filters> -> <filters>
(the first layer writes back), random data with OPENEYE_SEED=<seed>, CR 2 (2 x 2 clusters), NUM_GLB_PSUM = <glb_psum>
(X), NUM_GLB_WGHT 3, sparse, no activation, through probe_lanes.py. Output test/.temp/lanes_<tag>/lanes.json.
From the repository root:
  venv/bin/python doc/experiments/2026-11-26_writeback_lanes/run_lanes.py x4_s1 1 4"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
from _pytest.monkeypatch import MonkeyPatch  # noqa: E402
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

tag, seed, glb_psum = sys.argv[1], sys.argv[2], int(sys.argv[3])
width = int(sys.argv[4]) if len(sys.argv) > 4 else 8
filters = int(sys.argv[5]) if len(sys.argv) > 5 else 8
real = cocotb_test.simulator.run


def run(**kw):
    kw["module"] = "probe_lanes"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    kw["extra_env"] = dict(kw["extra_env"], OPENEYE_SEED=seed, SPARSITY_EN="1")
    return real(**kw)


cocotb_test.simulator.run = run
mp = MonkeyPatch()
mp.setattr(conv, "NUM_GLB_PSUM", glb_psum)
mp.setattr(conv, "NUM_GLB_WGHT", 3)
mp.setattr(conv, "INPUT_SIZE_X", width)
mp.setattr(conv, "NUM_FILTERS", filters)
for name in ("OPENEYE_ACTIVATION", "OPENEYE_WGHT_ZERO_FRACTION", "OPENEYE_IACT_ZERO_FRACTION"):
    os.environ.pop(name, None)
os.environ["SPARSITY_EN"] = "1"
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"lanes_{tag}"))
verdict = "PASS"
try:
    conv._run_conv_const("Convolution_Stack", 8, 2, num_glb_iact=1, input_channels=4, request=request, input_height=4,
                         quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=2)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__}: {e})"
finally:
    mp.undo()
print(f"RESULT {tag} seed={seed} X={glb_psum} width={width} filters={filters}: {verdict}", flush=True)
