"""run_spad.py <name> <pattern> <width> <height> <channels> <filters> <quant>: one random conv layer through probe_spad
(weights replaced by unique values with the zero pattern; SPad writes dumped to spad_<name>.json next to this file)."""
import os
import sys
import types

REPO = "/home/truongphi/OpenEye_orig"
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

name, mode = sys.argv[1:3]
width, height, channels, filters, quant = map(int, sys.argv[3:8])
random_data = True
HERE = os.path.dirname(os.path.abspath(__file__))
orig_run = cocotb_test.simulator.run


def run(**kw):
    env = kw.setdefault("extra_env", {})
    env["OPENEYE_PROFILE"] = "1"
    env["OPENEYE_DUMP_VERIFY"] = "1"
    env["B22_PATTERN"] = mode
    env["B22_DUMP"] = os.path.join(HERE, f"spad_{name}.json")
    for k in ("B22_SEED", "B22_NOSKIP", "B22_ENCODER", "B22_NO_DUMP", "B22_SNAPSHOT"):
        if k in os.environ:
            env[k] = os.environ[k]
    kw["module"] = "probe_spad"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    return orig_run(**kw)


cocotb_test.simulator.run = run
conv.INPUT_SIZE_X = width
conv.NUM_FILTERS = filters
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"b22_{name}"))
verdict = "PASS"
try:
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, quant_amount=quant, dma_bitwidth=64,
                         ramp_iacts=not random_data, asymmetric_kernel=not random_data, random_data=random_data)
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import verify_conv_output
    from open_eye import test_dir
    ok = verify_conv_output.check(os.path.join(test_dir, ".temp", f"b22_{name}"))
    verdict = "PASS" if ok else "FAIL (verify)"
except BaseException as e:
    verdict = f"FAIL ({type(e).__name__})"
print(f"RESULT b22 {name}: {verdict}")
