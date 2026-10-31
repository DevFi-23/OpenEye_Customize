"""up_run.py <tree> <name> LAYER W H CH NF CR GLBP [layers]: one model through <tree>'s own test_conv_const._run_conv_const
(RTL, testbench and Python of that tree), random data (no constant operands), 2 cluster columns, NUM_GLB_IACT 1.
Run with PYTHONPATH=<tree>/src so that open_eye (hdl_dir, test_dir) is the tree's."""
import os, re, sys, types
tree, name, layer = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3]
W, H, CH, NF, CR, GLBP = (int(v) for v in sys.argv[4:10])
layers = sys.argv[10] if len(sys.argv) > 10 else "1"
extra = dict(a.split("=", 1) for a in sys.argv[11:])
sys.path.insert(0, os.path.join(tree, "test", "cocotb_fpga"))
os.chdir(os.path.join(tree, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402
conv.INPUT_SIZE_X, conv.NUM_FILTERS, conv.NUM_GLB_PSUM = W, NF, GLBP
real = cocotb_test.simulator.run


def run(**kw):
    env = dict(kw["extra_env"])
    env.update({"OPENEYE_CONST_IACTS": "", "OPENEYE_CONST_WGHTS": "", "OPENEYE_EXPECT_LAYERS": layers,
                "OPENEYE_SEED": "1", "OPENEYE_FAIL_ON_STALL": "200000", "OPENEYE_KEEP_GOING": "1"})
    env.update(extra)
    kw["extra_env"] = env
    return real(**kw)


cocotb_test.simulator.run = run
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"up_{name}"))
verdict = "PASS"
try:
    conv._run_conv_const(layer, 8, CR, num_glb_iact=1, input_channels=CH, request=request, input_height=H)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
log = open(os.path.join(tree, "test", ".temp", f"up_{name}", "cocotb_sim.log"), errors="replace").read()
keys = ["result check failed[^\n]*", r"\d+ of \d+ feature maps differ", r"Error found in Iact storage[^\n]*",
        r"further Iact storage mismatches", r"No FSM progress[^\n]*", r"Difference found at line \d+",
        r"\d+ of \d+ outputs differ", r"Dense results[^\n]*"]
found = [m.group(0) for k in keys for m in [re.search(k, log)] if m]
print(f"RESULT {os.path.basename(tree)} {name} {layer} {W}x{H}x{CH}->{NF} CR{CR} GLB_PSUM{GLBP}: {verdict}; {found[:4]}")
