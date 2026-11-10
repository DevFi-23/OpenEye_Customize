"""run47.py <tree> <name> LAYER W H CH NF CR GLBP [layers] [KEY=VALUE...]: like 2026-10-31_upstream_review/up_run.py
(the tree's own Python, RTL and testbench, random data, seed 1, 2 cluster columns), but through probe47 (PE monitor,
P47_PE=...). Run with PYTHONPATH=<tree>/src from the repository root; SPARSITY_EN=0 in the environment for dense."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
UP = os.path.join(HERE, os.pardir, "2026-10-31_upstream_review", "up_run.py")
import cocotb_test.simulator  # noqa: E402
real = cocotb_test.simulator.run


def run(**kw):
    kw["module"] = "probe47"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    return real(**kw)


cocotb_test.simulator.run = run
sys.argv = [UP] + sys.argv[1:]
exec(compile(open(UP).read(), UP, "exec"), {"__name__": "__main__", "__file__": UP})
