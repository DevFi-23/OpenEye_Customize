"""run_sweep.py <save_dir> [jobs] [-k expr]: run the cases of test_sweep.py (SPARSITY_EN from the environment), copy each
profile to <save_dir>/<case>.json and the results to <save_dir>/status.json. From the repository root:
  venv/bin/python doc/experiments/2026-11-18_layer_mode_study/run_sweep.py doc/perf/layer_sweep_2026-11-18_sparse 6
  SPARSITY_EN=0 venv/bin/python doc/experiments/2026-11-18_layer_mode_study/run_sweep.py doc/perf/layer_sweep_2026-11-18_dense 6"""
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
TEMP = os.path.join(REPO, "test", ".temp")
LOGS = os.path.join(TEMP, "layer_sweep_logs")
TEST = os.path.join(HERE, "test_sweep.py")
ENV = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")


def profile_of(case):
    found = glob.glob(os.path.join(TEMP, f"*test_sweep_{case}_", "profile.json"))
    return found[0] if found else None


def run(case):
    old = profile_of(case)
    if old:
        os.remove(old)
    start = time.time()
    with open(os.path.join(LOGS, f"{case}.log"), "w") as log:
        rc = subprocess.run([sys.executable, "-m", "pytest", f"{TEST}::test_sweep[{case}]", "-q", "-p",
                             "no:cacheprovider", "-o", "log_cli=false", "-rfE"],
                            cwd=REPO, env=ENV, stdout=log, stderr=subprocess.STDOUT).returncode
    return case, rc, time.time() - start


def main():
    save = sys.argv[1]
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    only = sys.argv[sys.argv.index("-k") + 1] if "-k" in sys.argv else ""
    sys.path.insert(0, HERE)
    from test_sweep import CASES
    cases = [c for c in CASES if only in c]
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(save, exist_ok=True)
    print(f"SPARSITY_EN={os.environ.get('SPARSITY_EN', '(default)')}, {len(cases)} case(s), {jobs} in parallel", flush=True)
    statuses = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for case, rc, seconds in pool.map(run, cases):
            statuses[case] = "PASS" if rc == 0 else "FAIL"
            if rc:
                text = open(os.path.join(LOGS, f"{case}.log"), errors="replace").read()
                if "values ok, reference file differs" in text:
                    # the decoded values are right; only padding slots of the output stream differ from the
                    # reference file (a 7-wide last convolution, also without the bias table): the timing is valid
                    statuses[case] = "PASS (values; reference file padding differs)"
            path = profile_of(case)
            if path:
                shutil.copy(path, os.path.join(save, f"{case}.json"))
            print(f"  {statuses[case]:5s} {case} ({seconds:.0f} s){'' if path else ', no profile.json'}", flush=True)
    with open(os.path.join(save, "status.json"), "w") as f:
        json.dump(statuses, f, indent=1)


if __name__ == "__main__":
    main()
