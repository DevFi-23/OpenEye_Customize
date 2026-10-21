"""dense_k.py <K> <old|new|lockstep>: one Dense layer (K inputs, 10 outputs, row stationary, 2x2 clusters,
NUM_GLB_IACT=3, PARALLEL_MACS=2) with the old PE (3717d12) or the current one, through probe_spad
(largest first_spad_words_o). Prints PASS/FAIL and the probe result.
old: the PE of 3717d12 (written to oldpe/PE.v); lockstep: PE_lockstep.v + PE_orig.v from make_pe_lockstep.py."""
import json
import os
import subprocess
import sys
import types

REPO = "/home/truongphi/OpenEye_orig"
HERE = os.path.dirname(os.path.abspath(__file__))
SPAD = HERE
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_gemm_layer as gemm  # noqa: E402

K, rtl = int(sys.argv[1]), sys.argv[2]
if rtl == "old":
    os.makedirs(os.path.join(HERE, "oldpe"), exist_ok=True)
    with open(os.path.join(HERE, "oldpe", "PE.v"), "w") as f:
        f.write(subprocess.run(["git", "show", "3717d12:hdl/PE.v"], cwd=REPO, capture_output=True, text=True, check=True).stdout)
out = os.path.join(HERE, f"spad_K{K}_{rtl}.json")
orig_run = cocotb_test.simulator.run


def run(**kw):
    if rtl == "lockstep":
        src = [s for s in kw["verilog_sources"] if os.path.basename(s) != "PE.v"]
        assert len(src) == len(kw["verilog_sources"]) - 1
        kw["verilog_sources"] = src + [os.path.join(HERE, f) for f in ("PE_lockstep.v", "PE_orig.v")]
    if rtl == "old":
        src = [s for s in kw["verilog_sources"] if os.path.basename(s) != "PE.v"]
        assert len(src) == len(kw["verilog_sources"]) - 1
        kw["verilog_sources"] = src + [os.path.join(HERE, "oldpe", "PE.v")]
    kw["module"] = "probe_spad"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [SPAD]
    kw.setdefault("extra_env", {})["SPAD_PROBE_OUT"] = out
    return orig_run(**kw)


gemm.cocotb_test.simulator.run = run
os.environ["OPENEYE_SKIP_FC_WRITE_CHECK"] = "1"
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"denseK_{K}_{rtl}"))
verdict = "PASS"
try:
    gemm.test_gemm_layer(INPUT_SIZE=K, OUTPUT_SIZE=10, CLUSTER_ROWS=2, NUM_GLB_IACT=3, NUM_GLB_PSUM=4, NUM_GLB_WGHT=3,
                         DATAFLOW="row_stationary", request=request, PARALLEL_MACS=2, CLUSTER_COLUMNS=2)
except BaseException as e:  # cocotb_test raises SystemExit / AssertionError on a failing test
    verdict = f"FAIL ({type(e).__name__})"
probe = json.load(open(out)) if os.path.exists(out) else {}
print(f"RESULT K={K} rtl={rtl}: {verdict} {probe}")
