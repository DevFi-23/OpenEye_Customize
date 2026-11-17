"""Bug #49: the Table 2 network with ReLU (PAPER_MNIST_RELU) on sparse hardware at one Table 3 configuration, run with the
probe49 cocotb module instead of OpenEye_FPGA_tb (same test, plus dumps). The tree under test is the one of open_eye
(PYTHONPATH=<tree>/src), so the RTL of a clean worktree can be probed while the main tree is being edited.
  P49_CASE=paper_cr2_x2_y3 (default)  P_LAYER=PAPER_MNIST_RELU (default)  P49_OUT=<dump directory>
Run from the repository root:
  PYTHONPATH=<tree>/src P49_OUT=<dir> venv/bin/python -m pytest -q -p no:cacheprovider -o log_cli=false \
      doc/experiments/2026-11-17_bug49/test_probe49.py"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
from open_eye import test_dir  # noqa: E402  (the tree under test)

sys.path.insert(0, os.path.join(test_dir, "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402
from test_profile import PAPER_CONFIGS  # noqa: E402

_run = cocotb_test.simulator.run


def run_probe(**kwargs):
    kwargs["module"] = os.environ.get("P49_MODULE", "probe49")
    kwargs["python_search"] = [HERE] + list(kwargs.get("python_search") or [])
    extra = dict(kwargs.get("extra_env") or {})
    extra["P49_OUT"] = os.path.abspath(os.environ.get("P49_OUT", os.path.join(HERE, "out")))
    kwargs["extra_env"] = extra          # cocotb_test builds PYTHONPATH from sys.path (the tree first) + python_search
    kwargs["testcase"] = os.environ.get("P49_TESTCASE", "probe_test")
    return _run(**kwargs)


def test_probe49(request, monkeypatch):
    case = os.environ.get("P49_CASE", "paper_cr2_x2_y3")
    cluster_rows, pes_x, pes_y = PAPER_CONFIGS[case]
    monkeypatch.setattr(conv.cocotb_test.simulator, "run", run_probe)
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    monkeypatch.setenv("OPENEYE_KEEP_GOING", "1")
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", pes_x)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", pes_y)
    conv._run_conv_const(os.environ.get("P_LAYER", "PAPER_MNIST_RELU"), 8, cluster_rows, num_glb_iact=1,
                         input_channels=1, request=request, input_height=28, quant_amount=32, dma_bitwidth=64,
                         random_data=True, expect_layers=7)
