# This file is part of the OpenEye project.
# © Fachhochschule Dortmund – University of Applied Sciences and Arts (until 2025), Universität Duisburg-Essen (since 2025).
# SPDX-License-Identifier: SHL-2.1
# For more details, see the LICENSE file in the root directory of this project.

"""Summarise profile.json files written by rtl_test_utils.profile_dma_phases.

For every profile it prints the cycles spent in each phase of a layer and
the DMA words moved in that phase. For a single convolution layer
(LAYER=Convolution_Single) it also computes the payload the phase really
needs (e.g. F*C*Kx*Ky weight bytes) and the resulting bus efficiency:

    efficiency = payload bytes / (DMA words * DMA_BITWIDTH / 8)

With --compare it puts two sets of profiles side by side (e.g. a saved
baseline and the profiles of a modified RTL), matched by case name, and
prints the change per phase and per case.

Profiles can be given as profile.json files or as directories: a directory
of snapshots (<case>.json, as in doc/perf/baseline_*/) or of simulation
directories (<dir>/profile.json).

Usage:
    python -m open_eye.profile_report test/.temp/*/profile.json
    python -m open_eye.profile_report --csv baseline.csv test/.temp/*/profile.json
    python -m open_eye.profile_report --compare doc/perf/baseline_2026-10-09 test/.temp/*test_profile*/profile.json
"""

import argparse
import csv
import json
import math
import glob
import os
import re
import sys

PHASE_ORDER = ["load_config", "load_iact", "load_wght", "load_bias", "load_quant",
               "convert_iact", "compute", "writeback", "pooling", "readout"]

# OFFSET_WIDTH + EXPONENT_WIDTH + MANTISSA_WIDTH in OpenEye_FPGA.v
QUANT_ENTRY_BITS = 8 + 7 + 25


def payload_bytes(config):
    """Bytes each phase must move at minimum, for one conv layer; {} if unknown."""
    if config.get("LAYER") != "Convolution_Single":
        return {}
    try:
        f = int(config["NUM_FILTERS"])
        c = int(config["INPUT_CHANNELS"])
        x = int(config["INPUT_SIZE_X"])
        y = int(config["INPUT_SIZE_Y"])
        kx = int(config["KERNEL_SIZE_X"])
        ky = int(config["KERNEL_SIZE_Y"])
        stride = int(config["STRIDE"])
    except (KeyError, TypeError, ValueError):
        return {}
    psum_bytes = math.ceil(int(config["DATA_PSUM_BITWIDTH"]) / 8)
    outputs = math.ceil(x / stride) * math.ceil(y / stride) * f  # padding="same"
    return {
        "load_iact": x * y * c,
        "load_wght": f * c * kx * ky,
        "load_bias": f * psum_bytes,                       # one bias per filter
        "load_quant": math.ceil(f * QUANT_ENTRY_BITS / 8),  # one entry per filter
        "readout": outputs * psum_bytes,
    }


def summarise(profile):
    config = profile["config"]
    phases = profile["phases"]
    word_bytes = config["DMA_BITWIDTH"] // 8
    payload = payload_bytes(config)
    total = profile["total_cycles"]
    rows = []
    for name in PHASE_ORDER + sorted(set(phases) - set(PHASE_ORDER)):
        if name not in phases:
            continue
        p = phases[name]
        words = p["in_accepted"] + p["out_words"]
        need = payload.get(name)
        rows.append({
            "phase": name,
            "cycles": p["cycles"],
            "share": p["cycles"] / total if total else 0.0,
            "in_words": p["in_accepted"],
            "refused_words": p["in_offered"] - p["in_accepted"],
            "out_words": p["out_words"],
            "payload_bytes": need,
            "efficiency": need / (words * word_bytes) if need is not None and words else None,
            # memory stalls (memory model only; absent in older profiles)
            "mem_stall": p.get("in_stall", 0) + p.get("out_stall", 0),
        })
    return rows


def case_name(path):
    """Case name of a profile: <case>.json -> case; .../<sim dir>/profile.json -> sim dir.

    Simulation directories of test_profile.py are named after the pytest node
    id, e.g. test_cocotb_fpga_test_profile.py_test_profile_conv_8x1_f4_q32_dma64_;
    only the parameter id (8x1_f4_q32_dma64) is kept.
    """
    path = os.path.abspath(path)
    base = os.path.basename(path)
    if base != "profile.json":
        return os.path.splitext(base)[0]
    name = os.path.basename(os.path.dirname(path))
    m = re.search(r"test_profile_conv_(.+?)_?$", name)
    return m.group(1) if m else name


def load_profiles(paths):
    """{case: (path, profile)} from profile files and directories."""
    files = []
    for path in paths:
        if os.path.isdir(path):
            found = sorted(glob.glob(os.path.join(path, "*.json")))
            found += sorted(glob.glob(os.path.join(path, "*", "profile.json")))
            files += found
        else:
            files.append(path)
    profiles = {}
    for path in files:
        with open(path) as f:
            profiles[case_name(path)] = (path, json.load(f))
    return profiles


def memory_name(config):
    """Name of the memory model a profile was measured with."""
    return (config.get("MEMORY") or {}).get("name", "ideal (legacy driver)")


def describe(config):
    return ("{LAYER} {INPUT_SIZE_X}x{INPUT_SIZE_Y}x{INPUT_CHANNELS} k{KERNEL_SIZE_X}x{KERNEL_SIZE_Y} "
            "f{NUM_FILTERS} | {CLUSTER_ROWS}x{CLUSTER_COLUMNS} clusters, DMA {DMA_BITWIDTH} b, "
            "psum {DATA_PSUM_BITWIDTH} b, QUANT_AMOUNT {QUANT_AMOUNT}").format(**config) \
        + f" | memory: {memory_name(config)}"


def print_report(case, profile, rows):
    config = profile["config"]
    total = profile["total_cycles"]
    words = sum(r["in_words"] + r["out_words"] for r in rows)
    compute = sum(r["cycles"] for r in rows if r["phase"] == "compute")
    print(f"\n## {case}")
    print(describe(config))
    stall = sum(r["mem_stall"] for r in rows)
    print(f"total {total} cycles ({total * config['CLOCK_NS']} ns), compute {compute / total:.1%}, "
          f"DMA busy {words / total:.1%} of cycles, waiting for memory {stall / total:.1%}\n")
    print("| phase | cycles | share | DMA in | DMA out | mem stall | payload B | bus eff. |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        eff = f"{r['efficiency']:.0%}" if r["efficiency"] is not None else ""
        need = r["payload_bytes"] if r["payload_bytes"] is not None else ""
        drop = f" ({r['refused_words']} refused)" if r["refused_words"] else ""
        print(f"| {r['phase']} | {r['cycles']} | {r['share']:.1%} | {r['in_words']}{drop} | "
              f"{r['out_words']} | {r['mem_stall']} | {need} | {eff} |")


# Configuration keys that must agree for two profiles to be comparable
COMPARE_CONFIG_KEYS = ("LAYER", "NUM_FILTERS", "KERNEL_SIZE_X", "KERNEL_SIZE_Y", "INPUT_SIZE_X",
                       "INPUT_SIZE_Y", "INPUT_CHANNELS", "STRIDE", "DMA_BITWIDTH",
                       "CLUSTER_ROWS", "CLUSTER_COLUMNS", "QUANT_AMOUNT")


def _delta(old, new):
    if old is None or new is None:
        return ""
    d = new - old
    pct = f" ({d / old:+.1%})" if old else ""
    return f"{d:+d}{pct}" if d else "0"


def _eff(value):
    return f"{value:.0%}" if value is not None else ""


def compare_rows(base_profile, new_profile):
    """Per-phase comparison rows plus a total row."""
    base = {r["phase"]: r for r in summarise(base_profile)}
    new = {r["phase"]: r for r in summarise(new_profile)}
    names = [p for p in PHASE_ORDER if p in base or p in new]
    names += sorted((set(base) | set(new)) - set(PHASE_ORDER))
    rows = []
    for name in names:
        b, n = base.get(name), new.get(name)
        rows.append({
            "phase": name,
            "cycles_base": b["cycles"] if b else 0,
            "cycles_new": n["cycles"] if n else 0,
            "words_base": (b["in_words"] + b["out_words"]) if b else 0,
            "words_new": (n["in_words"] + n["out_words"]) if n else 0,
            "eff_base": b["efficiency"] if b else None,
            "eff_new": n["efficiency"] if n else None,
            "stall_base": b["mem_stall"] if b else 0,
            "stall_new": n["mem_stall"] if n else 0,
        })
    rows.append({
        "phase": "TOTAL",
        "cycles_base": base_profile["total_cycles"],
        "cycles_new": new_profile["total_cycles"],
        "words_base": sum(r["words_base"] for r in rows),
        "words_new": sum(r["words_new"] for r in rows),
        "eff_base": None, "eff_new": None,
        "stall_base": sum(r["stall_base"] for r in rows),
        "stall_new": sum(r["stall_new"] for r in rows),
    })
    return rows


def print_comparison(base, new):
    """Markdown comparison of two {case: (path, profile)} sets."""
    common = [c for c in sorted(base) if c in new]
    summary = []
    for case in common:
        b, n = base[case][1], new[case][1]
        rows = compare_rows(b, n)
        print(f"\n## {case}")
        print(describe(n["config"]))
        mismatch = [k for k in COMPARE_CONFIG_KEYS
                    if str(b["config"].get(k)) != str(n["config"].get(k))]
        if mismatch:
            print("WARNING: configuration differs in " + ", ".join(
                f"{k} ({b['config'].get(k)} -> {n['config'].get(k)})" for k in mismatch))
        if memory_name(b["config"]) != memory_name(n["config"]):
            print(f"memory model: {memory_name(b['config'])} -> {memory_name(n['config'])}")
        print("\n| phase | cycles base | cycles new | change | DMA words base | DMA words new | change "
              "| mem stall | bus eff. |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in rows:
            eff = ""
            if r["eff_base"] is not None or r["eff_new"] is not None:
                eff = f"{_eff(r['eff_base'])} -> {_eff(r['eff_new'])}"
            bold = "**" if r["phase"] == "TOTAL" else ""
            print(f"| {bold}{r['phase']}{bold} | {r['cycles_base']} | {r['cycles_new']} | "
                  f"{_delta(r['cycles_base'], r['cycles_new'])} | {r['words_base']} | {r['words_new']} | "
                  f"{_delta(r['words_base'], r['words_new'])} | {r['stall_base']} -> {r['stall_new']} | {eff} |")
        summary.append((case, rows[-1]))

    print("\n## Summary\n")
    print("| case | cycles base | cycles new | change | DMA words base | DMA words new | change |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for case, t in summary:
        print(f"| {case} | {t['cycles_base']} | {t['cycles_new']} | {_delta(t['cycles_base'], t['cycles_new'])} | "
              f"{t['words_base']} | {t['words_new']} | {_delta(t['words_base'], t['words_new'])} |")
    for case in sorted(set(base) - set(new)):
        print(f"| {case} | {base[case][1]['total_cycles']} | (not run) | | | | |")
    for case in sorted(set(new) - set(base)):
        print(f"| {case} | (not in baseline) | {new[case][1]['total_cycles']} | | | | |")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("profiles", nargs="+", help="profile.json files or directories")
    parser.add_argument("--csv", help="also write one row per (profile, phase) to this file")
    parser.add_argument("--compare", action="append", metavar="BASELINE",
                        help="baseline profile file or directory to compare against (repeatable)")
    args = parser.parse_args(argv)

    profiles = load_profiles(args.profiles)
    if args.compare:
        print_comparison(load_profiles(args.compare), profiles)
        return 0

    csv_rows = []
    for case, (path, profile) in profiles.items():
        rows = summarise(profile)
        print_report(case, profile, rows)
        for r in rows:
            csv_rows.append({"profile": case, **profile["config"], **r})
    if args.csv and csv_rows:
        with open(args.csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0]))
            writer.writeheader()
            writer.writerows(csv_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
