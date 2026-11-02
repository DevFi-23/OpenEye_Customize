#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Table 3 of the OpenEye paper (arXiv 2606.01450) measured with the cycle profiler, per layer and per phase.

The paper times its Table 2 network on 16 configurations (CLUSTER ROWS 1/2/4/8 x PEs X-axis 2/4 x PEs Y-axis 3/4) at
200 MHz and reports two phases (Data Send, Proc. Time) for the whole network. Here the same network
(LAYER=PAPER_MNIST, test_profile.py::test_profile_paper) runs in the cocotb simulation of this repository's RTL with
the profiler on, and every layer gets its own table: one row per configuration, one column per profiler phase
(rtl_test_utils.profile_dma_phases), as time at --clock-mhz (default 200, the paper's clock). A last table sums the
layers and puts the paper's numbers next to them. A configuration whose result check fails is kept and marked: its
cycle counts are measured, but they belong to a run that computes something wrong. The cases run with
OPENEYE_KEEP_GOING, so a failed buffer check between chained layers is logged and every layer is still timed;
the status names the layers after which the check failed ("iact after L1,5") and a wrong final result.

Usage (from the repository root):
  venv/bin/python tools/paper_table3.py --run --jobs 6 --save doc/perf/paper_table3_<date> --report doc/perf/paper_table3_<date>.md
  venv/bin/python tools/paper_table3.py doc/perf/paper_table3_<date>        # the tables again, from saved profiles
"""
import argparse
import concurrent.futures
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_profile as rp  # noqa: E402
from open_eye import profile_report  # noqa: E402

PHASES = ["load_config", "load_iact", "load_wght", "load_bias", "load_quant", "load_act",
          "convert_iact", "compute", "writeback", "pooling", "readout"]
LOAD_PHASES = PHASES[:6]
# Table 3 of the paper, (CLUSTER ROWS, PEs X, PEs Y): (Data Send, Proc. Time, Total) in ns at 200 MHz
PAPER = {
    (1, 2, 3): (70680, 228635, 299315), (2, 2, 3): (106720, 124545, 231265),
    (4, 2, 3): (131235, 71475, 202710), (8, 2, 3): (132995, 44525, 177520),
    (1, 4, 3): (71960, 127270, 199230), (2, 4, 3): (83680, 70325, 154005),
    (4, 4, 3): (85225, 42785, 128010), (8, 4, 3): (85580, 29760, 115340),
    (1, 2, 4): (82785, 223310, 306095), (2, 2, 4): (130660, 122020, 252680),
    (4, 2, 4): (162355, 70180, 232535), (8, 2, 4): (163135, 48745, 211880),
    (1, 4, 4): (84045, 121060, 205105), (2, 4, 4): (99920, 67540, 167460),
    (4, 4, 4): (100985, 41380, 142365), (8, 4, 4): (99915, 29250, 129165),
}
CASE_RE = re.compile(r"paper_cr(\d+)_x(\d+)_y(\d+)")


def config_of(case):
    m = CASE_RE.search(case)
    return tuple(int(v) for v in m.groups()) if m else None


def status_of(case, rc):
    """PASS, or what went wrong, from the pytest log run_profile keeps per case."""
    if rc == 0:
        return "PASS"
    try:
        log = open(os.path.join(rp.LOG_DIR, f"{case}.log"), errors="replace").read()
    except OSError:
        return "FAIL"
    if "No FSM progress" in log:
        return "FAIL (hang)"
    layers = sorted({int(n) for n in re.findall(r"Iact buffer check failed after layer (\d+)", log)})
    parts = ["iact after L" + ",".join(str(n) for n in layers)] if layers else []
    if "Error found in Iact storage" in log and not layers:
        parts.append("iact buffer")
    if "result check failed" in log or "Difference found" in log:
        parts.append("result")
    return "FAIL (" + "; ".join(parts) + ")" if parts else "FAIL"


def run_all(jobs, save):
    ids = rp.collect("paper")
    os.makedirs(rp.LOG_DIR, exist_ok=True)
    os.makedirs(save, exist_ok=True)
    print(f"running {len(ids)} configuration(s), {jobs} in parallel; logs in {os.path.relpath(rp.LOG_DIR, rp.REPO)}/")
    statuses = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for case, rc, seconds in pool.map(rp.run_case, ids):
            statuses[case] = status_of(case, rc)
            path = rp.profile_path(case)
            if path:
                shutil.copy(path, os.path.join(save, f"{case}.json"))
            print(f"  {statuses[case]:20s} {case} ({seconds:.0f} s){'' if path else ', no profile.json'}", flush=True)
    with open(os.path.join(save, "status.json"), "w") as f:
        json.dump(statuses, f, indent=1)


def load_dir(directory):
    statuses = {}
    if os.path.exists(os.path.join(directory, "status.json")):
        statuses = json.load(open(os.path.join(directory, "status.json")))
    runs = {}
    for name in sorted(os.listdir(directory)):
        cfg = config_of(name)
        if cfg and name.endswith(".json"):
            case = name[:-5]
            runs[cfg] = (case, json.load(open(os.path.join(directory, name))), statuses.get(case, "?"))
    return runs


def ordered(runs):
    return sorted(runs, key=lambda c: (c[2], c[1], c[0]))      # as in the paper: Y, then X, then CLUSTER ROWS


def fmt(v):
    return "" if v is None else f"{v:,.0f}".replace(",", ".")


def tables(runs, clock_mhz):
    ns = 1000.0 / clock_mhz
    out = []
    configs = ordered(runs)
    n_layers = max(len(p.get("layers") or []) for _, p, _ in runs.values())
    out.append(f"Times in ns at {clock_mhz:g} MHz (cycles x {ns:g}); ideal memory (one DMA word per cycle); "
               f"seed OPENEYE_SEED=1; status = result check of the testbench.\n")
    for i in range(n_layers):
        labels = set()
        rows, used = [], set()
        for cfg in configs:
            case, prof, status = runs[cfg]
            layers = prof.get("layers") or []
            if i >= len(layers):
                rows.append((cfg, status, None, None))
                continue
            layer = layers[i]
            info = layer.get("info") or {}
            pad = info.get("pad_channels") or 0           # label the model's layer, mark the padding in status
            labels.add(profile_report.layer_label(dict(info, channels=(info.get("channels") or 0) - pad, pad_channels=0), i))
            phases = {k: v["cycles"] for k, v in layer["phases"].items()}
            used.update(k for k, v in phases.items() if v)
            rows.append((cfg, status + (" pad" if info.get("pad_channels") else ""), phases, layer["total_cycles"]))
        cols = [p for p in PHASES if p in used]
        out.append(f"\n## Layer {i}: {' / '.join(sorted(labels))}\n")
        out.append("| CR | X | Y | status | " + " | ".join(cols) + " | total | load share |")
        out.append("|---:|---:|---:|---|" + "---:|" * (len(cols) + 2))
        for cfg, status, phases, total in rows:
            if phases is None:
                out.append(f"| {cfg[0]} | {cfg[1]} | {cfg[2]} | {status} | " + " | ".join("-" for _ in cols) + " | - | |")
                continue
            load = sum(phases.get(p, 0) for p in LOAD_PHASES)
            out.append(f"| {cfg[0]} | {cfg[1]} | {cfg[2]} | {status} | "
                       + " | ".join(fmt(phases.get(p, 0) * ns) for p in cols)
                       + f" | **{fmt(total * ns)}** | {load / total:.0%} |")
    # whole network
    out.append("\n## Whole network (sum of the layers) and the paper's Table 3\n")
    # load_act only when some configuration has a table activation (the columns of earlier runs unchanged)
    net_cols = [p for p in PHASES
                if p != "load_act" or any(runs[cfg][1]["phases"].get(p, {}).get("cycles") for cfg in configs)]
    out.append("| CR | X | Y | status | " + " | ".join(net_cols) + " | total | paper Data Send | paper Proc. | paper Total | total / paper |")
    out.append("|---:|---:|---:|---|" + "---:|" * (len(net_cols) + 5))
    for cfg in configs:
        case, prof, status = runs[cfg]
        phases = {k: v["cycles"] for k, v in prof["phases"].items()}
        total = prof["total_cycles"]
        paper = PAPER.get(cfg)
        ratio = f"{total * ns / paper[2]:.2f}" if paper and len(prof.get("layers") or []) == n_layers else ""
        out.append(f"| {cfg[0]} | {cfg[1]} | {cfg[2]} | {status} | "
                   + " | ".join(fmt(phases.get(p, 0) * ns) for p in net_cols)
                   + f" | **{fmt(total * ns)}** | {fmt(paper[0]) if paper else ''} | {fmt(paper[1]) if paper else ''} | "
                   f"{fmt(paper[2]) if paper else ''} | {ratio} |")
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("profiles", nargs="?", help="directory of saved profiles (from --save)")
    parser.add_argument("--run", action="store_true", help="run the 16 test_profile_paper cases first")
    parser.add_argument("--jobs", type=int, default=4, help="cases run in parallel (default 4)")
    parser.add_argument("--save", metavar="DIR", help="where --run copies the profiles (required with --run)")
    parser.add_argument("--report", metavar="FILE", help="also write the tables (markdown) to FILE")
    parser.add_argument("--clock-mhz", type=float, default=200.0, help="clock for the times (default 200, the paper's)")
    args = parser.parse_args(argv)
    if args.run:
        if not args.save:
            parser.error("--run needs --save DIR")
        run_all(args.jobs, args.save)
    directory = args.save if args.run else args.profiles
    if not directory:
        parser.error("give a directory of profiles, or --run --save DIR")
    runs = load_dir(directory)
    if not runs:
        print(f"no paper_cr*_x*_y* profiles in {directory}")
        return 1
    text = tables(runs, args.clock_mhz)
    print(text)
    if args.report:
        with open(args.report, "w") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
