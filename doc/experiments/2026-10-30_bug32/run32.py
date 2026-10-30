"""run32.py <name> <pattern> [KEY=VALUE ...]: doc/experiments/2026-10-30_bug31/run31.py (one conv layer, chosen input,
DUT vs numpy) with the cocotb module probe32 (B32_BIAS, B32_REVERSE) instead of probe31. Same options, same log
(test/.temp/b31_<name>/cocotb_sim.log). Run from the repository root, e.g. bug #32 in about a minute:
  venv/bin/python doc/experiments/2026-10-30_bug32/run32.py w7f8 rand W=7 H=2 CH=4 NF=8 OPENEYE_BIAS_STEP=3 B32_BIAS=4"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
RUN31 = os.path.join(REPO, "doc", "experiments", "2026-10-30_bug31", "run31.py")
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402

real_run = cocotb_test.simulator.run


def run(**kw):
    kw["module"] = "probe32"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE, os.path.dirname(RUN31)]
    return real_run(**kw)


cocotb_test.simulator.run = run
sys.argv = [RUN31] + sys.argv[1:]
runpy.run_path(RUN31, run_name="__main__")
