"""run.py <save_dir> [jobs] [-k expr] [--grid]: run the cases of test_act_wzero.py (or of test_grid.py with --grid; the
mode is in the case name), copy each profile to <save_dir>/<case>.json and the results to <save_dir>/status.json;
progress in <save_dir>/progress.txt. From the repository root:
  venv/bin/python doc/experiments/2026-11-20_act_wzero/run.py doc/perf/act_wzero_2026-11-20 6
  venv/bin/python doc/experiments/2026-11-20_act_wzero/run.py doc/perf/zero_grid_2026-11-20 6 --grid"""
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
LOGS = os.path.join(TEMP, "act_wzero_logs")
NAME = "test_grid" if "--grid" in sys.argv else "test_act_wzero"
TEST = os.path.join(HERE, NAME + ".py")
ENV = {k: v for k, v in os.environ.items() if k != "SPARSITY_EN"}
ENV["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"


def profile_of(case):
    found = glob.glob(os.path.join(TEMP, f"*{NAME}_{case}_", "profile.json"))
    return found[0] if found else None


def run(case):
    old = profile_of(case)
    if old:
        os.remove(old)
    start = time.time()
    with open(os.path.join(LOGS, f"{case}.log"), "w") as log:
        rc = subprocess.run([sys.executable, "-m", "pytest", f"{TEST}::{NAME}[{case}]", "-q", "-p",
                             "no:cacheprovider", "-o", "log_cli=false", "-rfE"],
                            cwd=REPO, env=ENV, stdout=log, stderr=subprocess.STDOUT).returncode
    return case, rc, time.time() - start


def main():
    save = sys.argv[1]
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 6
    only = sys.argv[sys.argv.index("-k") + 1] if "-k" in sys.argv else ""
    sys.path.insert(0, HERE)
    CASES = __import__(NAME).CASES
    cases = [c for c in CASES if only in c]
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(save, exist_ok=True)
    status_file = os.path.join(save, "status.json")
    statuses = json.load(open(status_file)) if os.path.exists(status_file) else {}
    progress = open(os.path.join(save, "progress.txt"), "a")
    progress.write(f"{time.strftime('%m-%d %H:%M')} start: {len(cases)} case(s), {jobs} in parallel\n")
    progress.flush()
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for case, rc, seconds in pool.map(run, cases):
            statuses[case] = "PASS" if rc == 0 else "FAIL"
            if rc and "values ok, reference file differs" in open(os.path.join(LOGS, f"{case}.log"),
                                                                    errors="replace").read():
                # decoded values right, only padding slots of the output stream differ from the reference file
                # (the 7-wide layer, as in the step 1 sweep): the timing is valid
                statuses[case] = "PASS (values)"
            path = profile_of(case)
            if path:
                shutil.copy(path, os.path.join(save, f"{case}.json"))
            line = f"{time.strftime('%m-%d %H:%M')} {statuses[case]:4s} {case} ({seconds:.0f} s)" + \
                ("" if path else ", no profile.json")
            print(line, flush=True)
            progress.write(line + "\n")
            progress.flush()
            with open(status_file, "w") as f:
                json.dump(statuses, f, indent=1)
    progress.write(f"{time.strftime('%m-%d %H:%M')} done\n")


if __name__ == "__main__":
    main()
