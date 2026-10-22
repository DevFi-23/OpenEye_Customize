"""run_padw.py <name> <width> <height> <filters> <quant> [random]: one 1-channel conv layer through probe_padw."""
import os
import sys
import types

REPO = "/home/truongphi/OpenEye_orig"
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

name, width, height, filters, quant = sys.argv[1], *map(int, sys.argv[2:6])
random_data = len(sys.argv) > 6
HERE = os.path.dirname(os.path.abspath(__file__))
orig_run = cocotb_test.simulator.run


def run(**kw):
    env = kw.setdefault("extra_env", {})
    env["OPENEYE_PROFILE"] = "1"
    env["OPENEYE_DUMP_VERIFY"] = "1"
    kw["module"] = "probe_padw"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    return orig_run(**kw)


cocotb_test.simulator.run = run
conv.INPUT_SIZE_X = width
conv.NUM_FILTERS = filters
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"padw_{name}"))
verdict = "PASS"
try:
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=1, request=request,
                         input_height=height, quant_amount=quant, dma_bitwidth=64,
                         ramp_iacts=not random_data, asymmetric_kernel=not random_data, random_data=random_data)
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import verify_conv_output
    from open_eye import test_dir
    ok = verify_conv_output.check(os.path.join(test_dir, ".temp", f"padw_{name}"))
    verdict = "PASS" if ok else "FAIL (verify)"
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
print(f"RESULT padw {name}: {verdict}")
