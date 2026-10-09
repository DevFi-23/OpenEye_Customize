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

Usage:
    python -m open_eye.profile_report test/.temp/*/profile.json
    python -m open_eye.profile_report --csv baseline.csv test/.temp/*/profile.json
"""

import argparse
import csv
import json
import math
import os
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
        })
    return rows


def describe(config):
    return ("{LAYER} {INPUT_SIZE_X}x{INPUT_SIZE_Y}x{INPUT_CHANNELS} k{KERNEL_SIZE_X}x{KERNEL_SIZE_Y} "
            "f{NUM_FILTERS} | {CLUSTER_ROWS}x{CLUSTER_COLUMNS} clusters, DMA {DMA_BITWIDTH} b, "
            "psum {DATA_PSUM_BITWIDTH} b, QUANT_AMOUNT {QUANT_AMOUNT}").format(**config)


def print_report(path, profile, rows):
    config = profile["config"]
    total = profile["total_cycles"]
    words = sum(r["in_words"] + r["out_words"] for r in rows)
    compute = sum(r["cycles"] for r in rows if r["phase"] == "compute")
    print(f"\n## {os.path.basename(os.path.dirname(os.path.abspath(path)))}")
    print(describe(config))
    print(f"total {total} cycles ({total * config['CLOCK_NS']} ns), compute {compute / total:.1%}, "
          f"DMA busy {words / total:.1%} of cycles\n")
    print("| phase | cycles | share | DMA in | DMA out | payload B | bus eff. |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        eff = f"{r['efficiency']:.0%}" if r["efficiency"] is not None else ""
        need = r["payload_bytes"] if r["payload_bytes"] is not None else ""
        drop = f" ({r['refused_words']} refused)" if r["refused_words"] else ""
        print(f"| {r['phase']} | {r['cycles']} | {r['share']:.1%} | {r['in_words']}{drop} | "
              f"{r['out_words']} | {need} | {eff} |")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("profiles", nargs="+", help="profile.json files")
    parser.add_argument("--csv", help="also write one row per (profile, phase) to this file")
    args = parser.parse_args(argv)

    csv_rows = []
    for path in args.profiles:
        with open(path) as f:
            profile = json.load(f)
        rows = summarise(profile)
        print_report(path, profile, rows)
        for r in rows:
            csv_rows.append({"profile": path, **profile["config"], **r})
    if args.csv and csv_rows:
        with open(args.csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0]))
            writer.writeheader()
            writer.writerows(csv_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
