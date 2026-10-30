"""run31_upstream.py <worktree of upstream> <name> <pattern>: one conv layer (Convolution_Single, 8x4 input, 4 channels,
4 filters, 2x2 clusters, NUM_GLB_IACT 1) on upstream's RTL and testbench, with the layer-0 input of <pattern>
(rand | zy:<a>:<b>: lines y = a..b-1 zero, as in run31.py) and upstream's constant weights (OPENEYE_CONST_WGHTS=8).
Prints whether the testbench's check passes and how many logged outputs equal the bias alone.
Run from this repository's root, e.g.
  git worktree add ../oe_upstream upstream/main
  PYTHONPATH=$PWD/../oe_upstream/src venv/bin/python doc/experiments/2026-10-30_bug31/run31_upstream.py ../oe_upstream u_zy02 zy:0:2"""
import os
import re
import sys
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WT, name, pattern = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(WT, "test", "cocotb_fpga"))
os.chdir(os.path.join(WT, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

CH, W, H = 4, 8, 4
rng = np.random.default_rng(31)
a = rng.integers(1, 32, size=(CH, W, H)) * rng.choice([-1, 1], size=(CH, W, H))
if pattern.startswith("zy:"):
    y0, y1 = (int(v) for v in pattern.split(":")[1:])
    a[:, :, y0:y1] = 0
sim = os.path.join(WT, "test", ".temp", f"b31u_{name}")
os.makedirs(sim, exist_ok=True)
np.save(os.path.join(sim, "iact.npy"), a)
orig_run = cocotb_test.simulator.run


def run(**kw):
    kw.setdefault("extra_env", {})["B31_IACT"] = os.path.join(sim, "iact.npy")
    kw["module"] = "probe31_upstream"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    return orig_run(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"b31u_{name}"))
verdict = "PASS"
try:
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=CH, request=request,
                         input_height=H)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
log = open(os.path.join(sim, "cocotb_sim.log"), errors="replace").read()
diffs = re.findall(r"Difference found at f = (\d+), x = (\d+), y= (\d+): reference (-?\d+), DUT (-?\d+)", log)
summary = re.search(r"(\d+) of (\d+) feature maps differ", log)
bias_like = sorted({int(d) for *_, d in diffs})
print(f"RESULT upstream {name} {pattern} ({int((a == 0).sum())}/{a.size} inputs 0): {verdict}; "
      f"{summary.group(0) if summary else 'no feature map differs'}; logged differences {len(diffs)}, "
      f"distinct DUT values among them {bias_like[:6]}; B31_IACT applied: {'B31_IACT: input' in log}")
