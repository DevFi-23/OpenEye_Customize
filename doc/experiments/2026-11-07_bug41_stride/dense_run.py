"""dense_run.py <K> <N> <NUM_GLB_IACT> [CLUSTER_ROWS]: one Dense layer (K inputs, N outputs, last layer, row stationary,
2 cluster columns, NUM_GLB_PSUM 4, NUM_GLB_WGHT 3, PARALLEL_MACS 2) through test_gemm_layer.test_gemm_layer, seed 1
(OPENEYE_SEED=<n> for another),
OPENEYE_SKIP_FC_WRITE_CHECK=1 (bug #5 false alarm). Used 2026-11-07 to recheck bugs #19b and #21 on dev. From the
repository root: venv/bin/python doc/experiments/2026-11-07_bug41_stride/dense_run.py 64 40 1"""
import os, sys, types
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))
import test_gemm_layer as gemm  # noqa: E402

K, N, IACT = (int(v) for v in sys.argv[1:4])
CR = int(sys.argv[4]) if len(sys.argv) > 4 else 2
os.environ["OPENEYE_SKIP_FC_WRITE_CHECK"] = "1"
os.environ.setdefault("OPENEYE_SEED", "1")             # another seed: OPENEYE_SEED=<n> in the environment
os.environ.setdefault("OPENEYE_LAYER_SEED", os.environ["OPENEYE_SEED"])
name = f"dense_{K}_{N}_i{IACT}_cr{CR}_s{os.environ['OPENEYE_SEED']}"
request = types.SimpleNamespace(node=types.SimpleNamespace(nodeid=name))
verdict = "PASS"
try:
    gemm.test_gemm_layer(INPUT_SIZE=K, OUTPUT_SIZE=N, CLUSTER_ROWS=CR, NUM_GLB_IACT=IACT, NUM_GLB_PSUM=4, NUM_GLB_WGHT=3,
                         DATAFLOW="row_stationary", request=request, PARALLEL_MACS=2, CLUSTER_COLUMNS=2)
except BaseException as e:  # cocotb_test raises SystemExit / AssertionError on a failing test
    verdict = f"FAIL ({type(e).__name__})"
log = open(os.path.join(REPO, "test", ".temp", name, "cocotb_sim.log"), errors="replace").read()
diff = [l.split("cocotb")[-1].strip() for l in log.splitlines() if "outputs differ" in l or "feature maps differ" in l]
print(f"RESULT Dense {K} -> {N} NUM_GLB_IACT {IACT} CR {CR} seed {os.environ['OPENEYE_SEED']}: {verdict}; {diff[-1] if diff else ''}")
