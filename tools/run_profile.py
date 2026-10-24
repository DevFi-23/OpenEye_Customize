#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Run the latency/bandwidth profiling cases and compare them with a baseline.

One command for the whole measurement loop:
  1. collect the cases of test/cocotb_fpga/test_profile.py (optionally -k filtered; the 16 Table 3
     cases test_profile_paper only when the -k expression names "paper", see tools/paper_table3.py),
  2. delete their old profile.json files, so no stale numbers are reported,
  3. run every case in its own pytest process, several in parallel,
  4. report the profiles of the passing cases, or compare them with a baseline,
  5. optionally save them as a new snapshot directory (<case>.json).

Failing cases are listed and left out of the report: their numbers are not
trustworthy because the testbench result check failed.

Usage (from the repository root, with the project venv):
  venv/bin/python tools/run_profile.py                    # the 12 baseline cases (9 single layers, 3 models)
  venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-10-24 --clock-mhz 250
  venv/bin/python tools/run_profile.py -k q32 --jobs 4 --compare doc/perf/baseline_2026-10-24
  venv/bin/python tools/run_profile.py --save doc/perf/after_bias_fix --report doc/perf/after_bias_fix.md
  venv/bin/python tools/run_profile.py --mem typical --compare doc/perf/baseline_2026-10-24
  venv/bin/python tools/run_profile.py --mem typical --mem-set latency=60 --mem-set outstanding=1
  venv/bin/python tools/run_profile.py -k "not model"     # single layers only (the 3 models take ~4, ~11, ~11 min)
  venv/bin/python tools/run_profile.py -k model --compare doc/perf/baseline_2026-10-24 --clock-mhz 250

--mem selects a memory model preset (open_eye.memory_model.PRESETS: ideal,
typical, slow) and --mem-set overrides single parameters (latency,
burst_beats, outstanding, bandwidth, fifo_beats, setup, jitter, seed).
Without them the testbench uses its original ideal stream driver.
"""

import argparse
import concurrent.futures
import contextlib
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = os.path.join(REPO, "test", "cocotb_fpga")
TEMP_DIR = os.path.join(REPO, "test", ".temp")
LOG_DIR = os.path.join(TEMP_DIR, "run_profile_logs")
TEST_FILE = "test_profile.py"

sys.path.insert(0, os.path.join(REPO, "src"))
from open_eye import profile_report  # noqa: E402
from open_eye import memory_model  # noqa: E402

ENV = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")


def memory_env(preset, settings):
    """OPENEYE_MEM* variables for a preset and KEY=VALUE overrides."""
    env = {}
    if preset:
        if preset not in memory_model.PRESETS:
            raise SystemExit(f"unknown --mem {preset!r}; presets: {sorted(memory_model.PRESETS)}")
        env["OPENEYE_MEM"] = preset
    for setting in settings or []:
        key, _, value = setting.partition("=")
        if key not in memory_model.ENV_KEYS or not value:
            raise SystemExit(f"bad --mem-set {setting!r}; keys: {sorted(memory_model.ENV_KEYS)}")
        env[memory_model.ENV_KEYS[key]] = value
    return env


def collect(keyword):
    # The Table 3 cases (16 configurations, about an hour, known failures) are
    # not part of the baseline: only an expression that names them selects them.
    if not keyword:
        keyword = "not paper"
    elif "paper" not in keyword:
        keyword = f"({keyword}) and not paper"
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", TEST_FILE, "-k", keyword]
    out = subprocess.run(cmd, cwd=TEST_DIR, env=ENV, capture_output=True, text=True).stdout
    ids = [line.strip() for line in out.splitlines() if "::" in line]
    # pytest prints ids relative to the rootdir (repository root); run from TEST_DIR
    return [i.split("test/cocotb_fpga/", 1)[-1] for i in ids]


def case_of(test_id):
    m = re.search(r"\[(.+)\]$", test_id)
    return m.group(1) if m else test_id


def profile_path(case):
    found = []
    for test in ("conv", "model", "paper"):   # test_profile_conv / _model / _paper
        found += glob.glob(os.path.join(TEMP_DIR, f"*test_profile_{test}_{case}_", "profile.json"))
    return found[0] if found else None


def run_case(test_id):
    case = case_of(test_id)
    old = profile_path(case)
    if old:
        os.remove(old)
    start = time.time()
    with open(os.path.join(LOG_DIR, f"{case}.log"), "w") as log:
        rc = subprocess.run([sys.executable, "-m", "pytest", test_id, "-q", "-p", "no:cacheprovider",
                             "-o", "log_cli=false", "-rfE"],
                            cwd=TEST_DIR, env=ENV, stdout=log, stderr=subprocess.STDOUT).returncode
    return case, rc, time.time() - start


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-k", dest="keyword", help="pytest -k expression to select cases")
    parser.add_argument("--jobs", type=int, default=3, help="cases run in parallel (default 3)")
    parser.add_argument("--compare", action="append", metavar="BASELINE",
                        help="baseline profile file or directory to compare with (repeatable)")
    parser.add_argument("--save", metavar="DIR", help="copy the new profiles to DIR/<case>.json")
    parser.add_argument("--report", metavar="FILE", help="also write the report (markdown) to FILE")
    parser.add_argument("--mem", metavar="PRESET", help="memory model preset (ideal, typical, slow)")
    parser.add_argument("--mem-set", action="append", metavar="KEY=VALUE",
                        help="override one memory model parameter (repeatable)")
    parser.add_argument("--clock-mhz", type=float,
                        help="FPGA clock for the time column of the per-layer table (e.g. 250)")
    args = parser.parse_args(argv)

    # The memory model is configured through the environment of the test processes;
    # clear inherited OPENEYE_MEM* so a run is defined by its command line only.
    for name in ["OPENEYE_MEM"] + list(memory_model.ENV_KEYS.values()):
        ENV.pop(name, None)
    ENV.update(memory_env(args.mem, args.mem_set))
    if args.mem or args.mem_set:
        print("memory model: " + ", ".join(f"{k}={v}" for k, v in sorted(ENV.items())
                                           if k.startswith("OPENEYE_MEM")))

    ids = collect(args.keyword)
    if not ids:
        print("no profiling cases selected")
        return 1
    os.makedirs(LOG_DIR, exist_ok=True)
    print(f"running {len(ids)} case(s), {args.jobs} in parallel; logs in "
          f"{os.path.relpath(LOG_DIR, REPO)}/")

    passed, failed = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for case, rc, seconds in pool.map(run_case, ids):
            print(f"  {'PASS' if rc == 0 else 'FAIL'} {case} ({seconds:.0f} s)")
            (passed if rc == 0 else failed).append(case)

    profiles = {}
    for case in passed:
        path = profile_path(case)
        if path:
            profiles[case] = path
        else:
            print(f"  warning: {case} passed but wrote no profile.json")

    if args.save and profiles:
        os.makedirs(args.save, exist_ok=True)
        for case, path in profiles.items():
            shutil.copy(path, os.path.join(args.save, f"{case}.json"))
        print(f"saved {len(profiles)} profile(s) to {args.save}/")

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        if failed:
            print("Failed cases (excluded): " + ", ".join(failed) + "\n")
        report_args = list(profiles.values())
        if report_args:
            for base in args.compare or []:
                report_args += ["--compare", base]
            if args.clock_mhz:
                report_args += ["--clock-mhz", str(args.clock_mhz)]
            profile_report.main(report_args)
    report = buffer.getvalue()
    print(report)
    if args.report:
        with open(args.report, "w") as f:
            f.write(report)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
