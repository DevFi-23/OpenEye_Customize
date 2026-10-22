"""run_model.py <name> <NUM_GLB_IACT> [KEY=VALUE ...]: the LAYER=MNIST net (Conv-Pool-Conv-Pool-Conv-Dense) of
data_create.py on the standard platform (2x2 clusters, NUM_GLB_PSUM=4, NUM_GLB_WGHT=3, QUANT_AMOUNT=32, DMA 64 bit,
max-pool hardware), random data, profiler and stall detector on. No repository file is modified."""
import os
import sys
import types

REPO = "/home/truongphi/OpenEye_orig"
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

name, nglb = sys.argv[1], int(sys.argv[2])
HERE = os.path.dirname(os.path.abspath(__file__))
extra = dict(a.split("=", 1) for a in sys.argv[3:])
orig_run = cocotb_test.simulator.run


def run(**kw):
    env = kw.setdefault("extra_env", {})
    env.pop("OPENEYE_EXPECT_LAYERS", None)            # the net has 6 layers
    env["OPENEYE_PROFILE"] = "1"
    env.update(extra)
    kw["parameters"] = {"MAX_POOLING": 1, "AVERAGE_POOLING": 0}   # the net uses MaxPooling2D
    kw["module"] = "probe_model"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    env["LAYER_PROFILE"] = os.path.join(HERE, f"layers_{name}.json")
    return orig_run(**kw)


cocotb_test.simulator.run = run
os.environ["OPENEYE_FAIL_ON_STALL"] = os.environ.get("OPENEYE_FAIL_ON_STALL", "200000")
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"model_{name}"))
verdict = "PASS"
try:
    layer = extra.pop("LAYER", "MNIST")
    qa = int(extra.pop("QUANT_AMOUNT", "32"))
    conv._run_conv_const(layer, 8, 2, num_glb_iact=nglb, input_channels=2, request=request, input_height=28,
                         quant_amount=qa, dma_bitwidth=64, random_data=True)
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
print(f"RESULT model {name} NUM_GLB_IACT={nglb}: {verdict}")
