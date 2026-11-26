"""run_channels.py <out dir> [jobs] [-k expr]: run the cases of test_channels.py, classify each one from its simulation
log (PASS; REFUSED by a Python check; STOPPED = the Python stream generation raised before the RTL ran; FAIL = wrong
values; HANG = no FSM progress; ERROR = anything else) and write <out dir>/status.json (case -> [verdict, detail,
seconds]) and progress.txt. --reclassify re-reads the logs of the cases in status.json. From the repository root:
  venv/bin/python doc/experiments/2026-11-23_channel_sweep/run_channels.py doc/experiments/2026-11-23_channel_sweep/out 6
  venv/bin/python doc/experiments/2026-11-23_channel_sweep/run_channels.py doc/experiments/2026-11-23_channel_sweep/out --reclassify"""
import concurrent.futures
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
TEMP = os.path.join(REPO, "test", ".temp")
LOGS = os.path.join(TEMP, "channel_sweep_logs")
TEST = os.path.join(HERE, "test_channels.py")
ENV = {k: v for k, v in os.environ.items() if k != "SPARSITY_EN"}
ENV["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"


def sim_log(case):
    found = glob.glob(os.path.join(TEMP, f"*test_channels_{case}_", "cocotb_sim.log"))
    return open(found[0], errors="replace").read() if found else ""


def classify(rc, text):
    """PASS; REFUSED (a Python check refused the layer on purpose); HANG; FAIL (the RTL ran and a value differs from the
    reference: output or iact buffer); STOPPED (the Python toolchain / testbench raised an error, so the layer could
    not run or not be checked; detail = the exception); ERROR (anything else)."""
    if rc == 0:
        padded = re.search(r"padded from (\d+) to (\d+) channels", text)
        return "PASS", ("padded %s -> %s" % padded.groups()) if padded else ""
    m = re.search(r"NotImplementedError: ([^\n]+)", text)
    if m:
        return "REFUSED", m.group(1)[:220]
    m = re.search(r"No FSM progress for \d+ cycles[^\n]*", text)
    if m:
        return "HANG", m.group(0)[:160]
    if "values ok, reference file differs" in text:
        return "PASS (values)", "reference file padding differs"
    m = re.search(r"(Difference found[^\n]*|Error found in Iact storage[^\n]*)", text)
    if m:
        return "FAIL", m.group(1)[:200]
    if "X detected" in text and "non-0/1 values" in text:
        return "FAIL", "the DUT output holds X (undefined) values"
    m = re.search(r"stream generation of \w+ failed: ([^\n]+)", text) or \
        re.search(r"\n((?:KeyError|IndexError|ValueError|TypeError|ZeroDivisionError|RuntimeError|AttributeError)"
                  r"[^\n]*)", text)
    if m:
        where = re.findall(r'File "[^"]*/(src/open_eye/\w+\.py|test/cocotb_fpga/\w+\.py)", line (\d+), in (\w+)', text)
        loc = f" ({where[-1][0]}:{where[-1][1]} {where[-1][2]})" if where else ""
        return "STOPPED", (m.group(1)[:180] + loc)
    return "ERROR", text.strip().splitlines()[-1][:200] if text.strip() else "no log"


def run(case):
    start = time.time()
    with open(os.path.join(LOGS, f"{case}.log"), "w") as log:
        rc = subprocess.run([sys.executable, "-m", "pytest", f"{TEST}::test_channels[{case}]", "-q", "-p",
                             "no:cacheprovider", "-o", "log_cli=false", "-rfE"],
                            cwd=REPO, env=ENV, stdout=log, stderr=subprocess.STDOUT).returncode
    text = sim_log(case) + "\n" + open(os.path.join(LOGS, f"{case}.log"), errors="replace").read()
    verdict, detail = classify(rc, text)
    return case, verdict, detail, time.time() - start


def reclassify(out):
    status_file = os.path.join(out, "status.json")
    statuses = json.load(open(status_file))
    for case, entry in statuses.items():
        log = os.path.join(LOGS, f"{case}.log")
        text = sim_log(case) + "\n" + (open(log, errors="replace").read() if os.path.exists(log) else "")
        rc = 0 if entry[0].startswith("PASS") else 1
        statuses[case] = list(classify(rc, text)) + [entry[2]]
    json.dump(statuses, open(status_file, "w"), indent=1)
    print(f"reclassified {len(statuses)} case(s)")


def main():
    out = sys.argv[1]
    if "--reclassify" in sys.argv:
        reclassify(out)
        return
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 6
    only = sys.argv[sys.argv.index("-k") + 1] if "-k" in sys.argv else ""
    sys.path.insert(0, HERE)
    from test_channels import CASES
    cases = [c for c in CASES if only in c]
    os.makedirs(LOGS, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    status_file = os.path.join(out, "status.json")
    statuses = json.load(open(status_file)) if os.path.exists(status_file) else {}
    progress = open(os.path.join(out, "progress.txt"), "a")
    progress.write(f"{time.strftime('%m-%d %H:%M')} start at {subprocess.getoutput('git -C ' + REPO + ' log --oneline -1')}: "
                   f"{len(cases)} case(s), {jobs} in parallel\n")
    progress.flush()
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for case, verdict, detail, seconds in pool.map(run, cases):
            statuses[case] = [verdict, detail, round(seconds)]
            line = f"{time.strftime('%m-%d %H:%M')} {verdict:8s} {case} ({seconds:.0f} s) {detail}"
            print(line, flush=True)
            progress.write(line + "\n")
            progress.flush()
            with open(status_file, "w") as f:
                json.dump(statuses, f, indent=1)
    progress.write(f"{time.strftime('%m-%d %H:%M')} done\n")


if __name__ == "__main__":
    main()
