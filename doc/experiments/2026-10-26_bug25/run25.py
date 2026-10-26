"""run25.py <name> <LAYER> <layers> [KEY=VALUE ...]: one model through probe25 (the unmodified OpenEye_FPGA_tb + probe
switches), 2 cluster columns, NUM_GLB_WGHT=3, DMA 64, seed 1, profiler, OPENEYE_KEEP_GOING.
Runner options: CR (2), IACT (1), GLBP (NUM_GLB_PSUM, 4), QA (32), H (input height, 1), W (input width, 8), CH (input
channels, 1), NF (filters, 4), RAMP=1 (ramp iacts), MAXPOOL=1 (MAX_POOLING=1, AVERAGE_POOLING=0), CONST=<v> (constant data
instead of random). Other KEY=VALUE go to the simulation (probe25 switches, TRACE_* of the testbench).
Log: test/.temp/b25_<name>/cocotb_sim.log. Run from the repository root, e.g.
  venv/bin/python doc/experiments/2026-10-26_bug25/run25.py k2 Convolution_Stack 2 GLBP=2 CH=4 H=4"""
import os, sys, types
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

name, layer, n_layers = sys.argv[1], sys.argv[2], int(sys.argv[3])
extra = dict(a.split("=", 1) for a in sys.argv[4:])
HERE = os.path.dirname(os.path.abspath(__file__))
opt = {k: extra.pop(k) for k in ("CR", "IACT", "GLBP", "QA", "H", "W", "CH", "NF", "RAMP", "MAXPOOL", "CONST") if k in extra}
conv.NUM_GLB_PSUM = int(opt.get("GLBP", 4))
conv.INPUT_SIZE_X = int(opt.get("W", 8))
conv.NUM_FILTERS = int(opt.get("NF", 4))
orig_run = cocotb_test.simulator.run


def run(**kw):
    env = kw.setdefault("extra_env", {})
    env.update({"OPENEYE_PROFILE": "1", "OPENEYE_SEED": "1", "OPENEYE_KEEP_GOING": "1"})
    env.update(extra)
    env["B26_DUMP"] = os.path.join(REPO, "test", ".temp", f"b25_{name}", "dump.json")
    if opt.get("MAXPOOL"):
        kw["parameters"] = {"MAX_POOLING": 1, "AVERAGE_POOLING": 0}
    kw["module"] = "probe25"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    return orig_run(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"b25_{name}"))
verdict = "PASS"
try:
    const = opt.get("CONST")
    conv._run_conv_const(layer, int(const or 8), int(opt.get("CR", 2)), num_glb_iact=int(opt.get("IACT", 1)),
                         input_channels=int(opt.get("CH", 1)), request=request, input_height=int(opt.get("H", 1)),
                         quant_amount=int(opt.get("QA", 32)), dma_bitwidth=64, random_data=not const,
                         ramp_iacts=bool(opt.get("RAMP")), expect_layers=n_layers)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
log = open(os.path.join(REPO, "test", ".temp", f"b25_{name}", "cocotb_sim.log"), errors="replace").read()
done = [l.split("after layer ")[1].split(" ")[0] for l in log.splitlines() if "Iact buffer check failed" in l]
n_checked = log.count("expected words, ")
n_skipped = log.count("skipping the check")
print(f"RESULT {name} {layer}: {verdict}; buffer checks: {n_checked} done, {n_skipped} skipped, failed after layers {done}; result differ: {'outputs differ' in log or 'result check failed' in log}")
