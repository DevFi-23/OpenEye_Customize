"""run_relu.py <save_dir> [jobs] [-k expr]: run the 16 cases of test_paper_relu.py (the Table 2 network with ReLU),
copy each profile to <save_dir>/paper_cr<R>_x<X>_y<Y>.json and the results to <save_dir>/status.json, in the layout of
tools/paper_table3.py --save, so that `venv/bin/python tools/paper_table3.py <save_dir> --report <file>` prints the
tables. The hardware mode comes from the environment (SPARSITY_EN=0 for dense, unset or 1 for sparse).
Run from the repository root:
  venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/run_relu.py doc/perf/paper_table3_2026-11-17_relu_sparse 6
  SPARSITY_EN=0 venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/run_relu.py doc/perf/paper_table3_2026-11-17_relu_dense 6"""
import concurrent.futures
import glob
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "tools"))
import paper_table3 as t3  # noqa: E402

TEMP = os.path.join(REPO, "test", ".temp")
LOGS = os.path.join(TEMP, "paper_relu_logs")
TEST = os.path.join(HERE, "test_paper_relu.py")
ENV = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")


def profile_of(case):
    found = glob.glob(os.path.join(TEMP, f"*test_paper_relu_{case}_", "profile.json"))
    return found[0] if found else None


def run(case):
    old = profile_of(case)
    if old:
        os.remove(old)
    start = time.time()
    with open(os.path.join(LOGS, f"{case}.log"), "w") as log:
        rc = subprocess.run([sys.executable, "-m", "pytest", f"{TEST}::test_paper_relu[{case}]", "-q", "-p",
                             "no:cacheprovider", "-o", "log_cli=false", "-rfE"],
                            cwd=REPO, env=ENV, stdout=log, stderr=subprocess.STDOUT).returncode
    return case, rc, time.time() - start


def status(case, rc):
    if rc == 0:
        return "PASS"
    t3.rp.LOG_DIR = LOGS                                # reuse the classification of paper_table3.status_of
    return t3.status_of(case, rc)


def main():
    save = sys.argv[1]
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    only = sys.argv[sys.argv.index("-k") + 1] if "-k" in sys.argv else ""
    from test_profile import PAPER_CONFIGS          # noqa: E402 (sys.path set by test_paper_relu's directory below)
    cases = [c for c in PAPER_CONFIGS if only in c]
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(save, exist_ok=True)
    print(f"SPARSITY_EN={os.environ.get('SPARSITY_EN', '1 (default)')}, P_LAYER={os.environ.get('P_LAYER', 'PAPER_MNIST_RELU')}, "
          f"{len(cases)} case(s), {jobs} in parallel", flush=True)
    statuses = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for case, rc, seconds in pool.map(run, cases):
            statuses[case] = status(case, rc)
            path = profile_of(case)
            if path:
                shutil.copy(path, os.path.join(save, f"{case}.json"))
            print(f"  {statuses[case]:20s} {case} ({seconds:.0f} s){'' if path else ', no profile.json'}", flush=True)
    with open(os.path.join(save, "status.json"), "w") as f:
        json.dump(statuses, f, indent=1)


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
    main()
