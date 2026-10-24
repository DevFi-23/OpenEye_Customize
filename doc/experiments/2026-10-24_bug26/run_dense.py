"""run_dense.py <name> <LAYER> <layers> [KEY=VALUE ...]: one model through probe_dense (2 cluster columns, NUM_GLB_IACT=1,
NUM_GLB_WGHT=3, DMA 64, random data, seed 1, profiler, OPENEYE_KEEP_GOING); prints the iact checks and the result.

Runner options: CR=<cluster rows> (2), IACT=<NUM_GLB_IACT> (1), GLBP=<NUM_GLB_PSUM> (4), QA=<QUANT_AMOUNT> (32),
H=<input height> (1; 28 for PAPER_MNIST). Every other KEY=VALUE goes to the simulation environment (probe_dense switches,
TRACE_* of the testbench). Log: test/.temp/b26_<name>/cocotb_sim.log, profile: test/.temp/b26_<name>/profile.json.
Run from the repository root, e.g.
  venv/bin/python doc/experiments/2026-10-24_bug26/run_dense.py x16 D_16_8_10 2
  venv/bin/python doc/experiments/2026-10-24_bug26/run_dense.py e16 D_16_8_10 2 B26_WB=1 B26_WB_KEEP_ADDUP=1 B26_LIMIT_ROWS=1 B26_EMU=1"""
import os, sys, types
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

name, layer, n_layers = sys.argv[1], sys.argv[2], int(sys.argv[3])
extra = dict(a.split("=", 1) for a in sys.argv[4:])
HERE = os.path.dirname(os.path.abspath(__file__))
orig_run = cocotb_test.simulator.run


def run(**kw):
    env = kw.setdefault("extra_env", {})
    env.update({"OPENEYE_PROFILE": "1", "OPENEYE_SEED": "1", "OPENEYE_KEEP_GOING": "1"})
    env.update(extra)
    env["B26_DUMP"] = os.path.join(REPO, "test", ".temp", f"b26_{name}", "dump.json")
    kw["module"] = "probe_dense"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    return orig_run(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"b26_{name}"))
if "GLBP" in extra:
    conv.NUM_GLB_PSUM = int(extra.pop("GLBP"))
verdict = "PASS"
try:
    conv._run_conv_const(layer, 8, int(extra.pop("CR", "2")), num_glb_iact=int(extra.pop("IACT", "1")), input_channels=1,
                         request=request, input_height=int(extra.pop("H", "1")), quant_amount=int(extra.pop("QA", "32")), dma_bitwidth=64, random_data=True,
                         expect_layers=n_layers)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
log = open(os.path.join(REPO, "test", ".temp", f"b26_{name}", "cocotb_sim.log"), errors="replace").read()
checks = [l.split("cocotb")[-1].strip() for l in log.splitlines() if "Iact buffer check failed" in l or "Iact storages are checked" in l]
print(f"RESULT {name} {layer}: {verdict}; checks: {checks}; result check failed: {'result check failed' in log}")
