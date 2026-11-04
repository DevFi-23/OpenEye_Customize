"""run39.py <name> W H CH NF [KEY=VALUE ...]: one Convolution_Single through probe39 (the unmodified testbench plus the
weight-pass monitor), CR 2 x CC 2, NUM_GLB_PSUM 4, NUM_GLB_IACT 1, DMA 64, random data, seed 1, OPENEYE_DUMP_VERIFY.
KEY=VALUE pairs go to the simulation (e.g. OPENEYE_PAD_CHANNELS=1). Sim dir test/.temp/b39_<name>, monitor log
test/.temp/b39_<name>/b39.json. From the repository root:
  venv/bin/python doc/experiments/2026-11-04_bug39/run39.py n8f64 8 4 1 64"""
import os, sys, types
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

name = sys.argv[1]
W, H, CH, NF = (int(v) for v in sys.argv[2:6])
extra = dict(a.split("=", 1) for a in sys.argv[6:])
conv.INPUT_SIZE_X, conv.NUM_FILTERS, conv.NUM_GLB_PSUM = W, NF, 4
sim = os.path.join(REPO, "test", ".temp", f"b39_{name}")
orig_run = cocotb_test.simulator.run


def run(**kw):
    env = kw.setdefault("extra_env", {})
    env.update({"OPENEYE_SEED": "1", "OPENEYE_KEEP_GOING": "1", "OPENEYE_FAIL_ON_STALL": "200000",
                "OPENEYE_DUMP_VERIFY": "1", "B39_LOG": os.path.join(sim, "b39.json")})
    env.update(extra)
    kw["module"] = "probe39"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [os.path.dirname(os.path.abspath(__file__))]
    return orig_run(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"b39_{name}"))
verdict = "PASS"
try:
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=CH, request=request, input_height=H,
                         quant_amount=1024, dma_bitwidth=64, random_data=True)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
log = open(os.path.join(sim, "cocotb_sim.log"), errors="replace").read()
diffs = [l for l in log.splitlines() if "differ from the reference" in l]
print(f"RESULT {name} {W}x{H}x{CH}->{NF}: {verdict}; {diffs[-1].split('cocotb')[-1].strip() if diffs else 'outputs equal'}")
