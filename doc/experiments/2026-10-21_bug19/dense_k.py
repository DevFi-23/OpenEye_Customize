"""dense_k.py <K> <old|new>: one Dense layer (K inputs, 10 outputs, row stationary, 2x2 clusters,
NUM_GLB_IACT=3, PARALLEL_MACS=2) with the old PE (3717d12) or the current one, through probe_spad
(largest first_spad_words_o). Prints PASS/FAIL and the probe result.
Environment: N_OUT (outputs, default 10), PROBE_MODULE (probe_spad, probe_b19, probe_ctor, probe_wbuf, probe_spad2).
old: the PE of 3717d12 (oldpe/PE.v must exist); no RTL file of the repository is modified."""
import json
import os
import sys
import types

REPO = "/home/truongphi/OpenEye_orig"
HERE = os.path.dirname(os.path.abspath(__file__))
SPAD = HERE   # the probe modules live next to this script
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import cocotb_test.simulator  # noqa: E402
import test_gemm_layer as gemm  # noqa: E402

K, rtl = int(sys.argv[1]), sys.argv[2]
N_OUT = int(os.environ.get("N_OUT", "10"))
out = os.path.join(HERE, f"spad_K{K}_{rtl}.json")
orig_run = cocotb_test.simulator.run


def run(**kw):
    if rtl == "lockstep":
        src = [s for s in kw["verilog_sources"] if os.path.basename(s) != "PE.v"]
        assert len(src) == len(kw["verilog_sources"]) - 1
        kw["verilog_sources"] = src + [os.path.join(os.path.dirname(HERE), f) for f in ("PE_lockstep.v", "PE_orig.v")]
    if rtl == "old":
        src = [s for s in kw["verilog_sources"] if os.path.basename(s) != "PE.v"]
        assert len(src) == len(kw["verilog_sources"]) - 1
        kw["verilog_sources"] = src + [os.path.join(HERE, "oldpe", "PE.v")]
    kw["module"] = os.environ.get("PROBE_MODULE", "probe_spad")
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [SPAD]
    kw.setdefault("extra_env", {})["SPAD_PROBE_OUT"] = out
    kw["extra_env"]["B19_DUMP"] = os.path.join(HERE, f"dump_K{K}_{rtl}_n{N_OUT}.pkl")
    kw["extra_env"]["CTOR_DUMP"] = os.path.join(HERE, f"ctor_K{K}_{rtl}_n{N_OUT}.json")
    kw["extra_env"]["WBUF_DUMP"] = os.path.join(HERE, f"wbuf_K{K}_{rtl}_n{N_OUT}.json")
    kw["extra_env"]["SPAD2_DUMP"] = os.path.join(HERE, f"spad2_K{K}_{rtl}_n{N_OUT}.json")
    return orig_run(**kw)


gemm.cocotb_test.simulator.run = run
os.environ["OPENEYE_SKIP_FC_WRITE_CHECK"] = "1"
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=f"denseK_{K}_{rtl}_{os.environ.get('PROBE_MODULE', 'spad')}_n{N_OUT}"))
verdict = "PASS"
try:
    gemm.test_gemm_layer(INPUT_SIZE=K, OUTPUT_SIZE=N_OUT, CLUSTER_ROWS=2, NUM_GLB_IACT=3, NUM_GLB_PSUM=4, NUM_GLB_WGHT=3,
                         DATAFLOW="row_stationary", request=request, PARALLEL_MACS=2, CLUSTER_COLUMNS=2)
except BaseException as e:  # cocotb_test raises SystemExit / AssertionError on a failing test
    verdict = f"FAIL ({type(e).__name__})"
probe = json.load(open(out)) if os.path.exists(out) else {}
print(f"RESULT K={K} rtl={rtl}: {verdict} {probe}")
