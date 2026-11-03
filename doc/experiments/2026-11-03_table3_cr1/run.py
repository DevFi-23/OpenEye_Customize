"""run.py <name> <LAYER> <layers> [KEY=VALUE ...]: one model through probe_t3 (probe25 of doc/experiments/2026-10-26_bug25 =
the unmodified OpenEye_FPGA_tb + probe switches, plus the monitors and emulations of probe_t3.py), 2 cluster columns, DMA 64,
seed 1, profiler, OPENEYE_KEEP_GOING. Investigation of the CR 1 rows of Table 3 (doc/experiments/2026-11-03_table3_cr1.md).
Options: CR, IACT, GLBP (NUM_GLB_PSUM), GLBW (NUM_GLB_WGHT), QA, H, W, CH, NF, MAXPOOL=1, DUMP=1 (OPENEYE_DUMP_VERIFY),
BWW (BUFFER_WIDTH_WGHT, a build parameter: depth of the weight staging buffer, no RTL edit). Other KEY=VALUE go to the
simulation (probe_t3 switches T3_*, testbench TRACE_*). Sim dir test/.temp/t3_<name>. From the repository root, e.g.
  venv/bin/python doc/experiments/2026-11-03_table3_cr1/run.py d1568 D_1568_32 1 CR=1 GLBP=4 GLBW=3
  venv/bin/python doc/experiments/2026-11-03_table3_cr1/run.py c2 PAPER_MNIST_FIRST3 3 CR=1 GLBP=2 GLBW=3 DUMP=1"""
import os, sys, types
REPO = "/home/truongphi/OpenEye_orig"
PROBE = os.path.join(REPO, "doc", "experiments", "2026-10-26_bug25")
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

name, layer, n_layers = sys.argv[1], sys.argv[2], int(sys.argv[3])
extra = dict(a.split("=", 1) for a in sys.argv[4:])
opt = {k: extra.pop(k) for k in ("CR", "IACT", "GLBP", "GLBW", "QA", "H", "W", "CH", "NF", "MAXPOOL", "DUMP", "BWW") if k in extra}
if opt.get("BWW"):
    os.environ["BUFFER_WIDTH_WGHT"] = opt["BWW"]   # weight staging buffer depth 2^BWW (a build parameter, no RTL edit)
conv.NUM_GLB_PSUM = int(opt.get("GLBP", 4))
conv.NUM_GLB_WGHT = int(opt.get("GLBW", 3))
conv.INPUT_SIZE_X = int(opt.get("W", 8))
conv.NUM_FILTERS = int(opt.get("NF", 4))
sim = os.path.join(REPO, "test", ".temp", f"t3_{name}")
orig_run = cocotb_test.simulator.run


def run(**kw):
    env = kw.setdefault("extra_env", {})
    env.update({"OPENEYE_PROFILE": "1", "OPENEYE_SEED": "1", "OPENEYE_KEEP_GOING": "1", "OPENEYE_FAIL_ON_STALL": "400000",
                "OPENEYE_SKIP_FC_WRITE_CHECK": "1", "DUMP_PSUM_BUFFERS": "1"})
    if opt.get("DUMP"):
        env["OPENEYE_DUMP_VERIFY"] = "1"
    env.update(extra)
    env.setdefault("B26_DUMP", os.path.join(sim, "dump.json"))
    env.setdefault("T3_WBUF", os.path.join(sim, "wbuf.json"))
    if opt.get("MAXPOOL"):
        kw["parameters"] = {"MAX_POOLING": 1, "AVERAGE_POOLING": 0}
    kw["module"] = "probe_t3"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [PROBE, os.path.dirname(os.path.abspath(__file__))]
    return orig_run(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"t3_{name}"))
verdict = "PASS"
try:
    conv._run_conv_const(layer, 8, int(opt.get("CR", 2)), num_glb_iact=int(opt.get("IACT", 1)),
                         input_channels=int(opt.get("CH", 1)), request=request, input_height=int(opt.get("H", 1)),
                         quant_amount=int(opt.get("QA", 32)), dma_bitwidth=64, random_data=True, expect_layers=n_layers)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
log = open(os.path.join(sim, "cocotb_sim.log"), errors="replace").read()
failed = [l.split("after layer ")[1].split(" ")[0] for l in log.splitlines() if "Iact buffer check failed" in l]
diffs = [l for l in log.splitlines() if "differ from the reference" in l]
print(f"RESULT {name} {layer} {opt}: {verdict}; iact checks failed after {failed}; {diffs[-1].split('cocotb')[-1].strip() if diffs else 'outputs equal'}")
