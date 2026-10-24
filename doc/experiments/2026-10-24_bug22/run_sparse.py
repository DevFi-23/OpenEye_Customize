"""run_sparse.py <name> <test id params>: one test_conv3x3_sparse case through probe_spad (B22_PATTERN=keep, so the
test's checkerboard weights stay; B22_ENCODER from the environment)."""
import os
import sys
import types

REPO = "/home/truongphi/OpenEye_orig"
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv3x3_sparse as sp  # noqa: E402

name = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
orig_run = cocotb_test.simulator.run


def run(**kw):
    env = kw.setdefault("extra_env", {})
    env["B22_PATTERN"] = "keep"
    env["B22_NO_DUMP"] = "1"
    env["B22_DUMP"] = os.path.join(HERE, f"spad_{name}.json")
    for k in ("B22_ENCODER",):
        if k in os.environ:
            env[k] = os.environ[k]
    kw["module"] = "probe_spad"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    return orig_run(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"b22_{name}"))
verdict = "PASS"
try:
    sp.test_conv3x3_8ch_sparse50(NUM_FILTERS=8, STRIDE=1, KERNEL_SIZE_X=3, KERNEL_SIZE_Y=3, INPUT_SIZE_X=32,
                                 INPUT_SIZE_Y=1, INPUT_CHANNELS=4, SPARSE=1, CLUSTER_ROWS=2, NUM_GLB_IACT=3,
                                 NUM_GLB_PSUM=4, NUM_GLB_WGHT=3, request=request)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
print(f"RESULT b22 {name}: {verdict}")
