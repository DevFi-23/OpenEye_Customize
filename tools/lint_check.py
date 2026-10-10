#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Verilator lint with a baseline: fail only on warnings that are new.

The RTL inherited from upstream already produces many Verilator warnings,
so a plain `verilator --lint-only -Wall` always fails. This script lints the
RTL, compares the result with the recorded baseline in tools/lint_baseline/
and fails only if a warning appears that is not in the baseline (or appears
more often than recorded).

A warning is identified by its code, file and message, without line and
column, so code that only moves (e.g. after merging upstream) does not count
as new. Identical warnings in one file are counted.

Targets:
  parallel  hdl/OpenEye_Parallel.v, the command of the original CI job
  fpga      hdl/OpenEye_FPGA.v (complete FPGA top level, including
            psum_pipeline.v); its generated headers and dma_storage.v are
            created first with open_eye.generator / open_eye.vh_file_creator
            using the default parameters

Usage:
  python3 tools/lint_check.py                     # check all targets
  python3 tools/lint_check.py --target fpga       # check one target
  python3 tools/lint_check.py --update            # accept the current warnings as baseline
  python3 tools/lint_check.py --verilator ~/tools/verilator-5.020/bin/verilator

Requires Verilator 5.020 (the version of Ubuntu 24.04 and of the baseline)
and PyYAML.
"""

import argparse
import collections
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_DIR = os.path.join(REPO, "tools", "lint_baseline")
BASELINE_VERSION = "5.020"

COMMON_ARGS = ["--lint-only", "-Wall", "-Ihdl/",
               "+define+USE_INTERNAL_PARAMS_PE", "+define+USE_INTERNAL_PARAMS_PE_cluster",
               "hdl/lint_waivers.vlt"]

LINE_RE = re.compile(r"^%(Warning|Error)(?:-([A-Z0-9_]+))?: (?:(.+?):(\d+):(\d+): )?(.*)$")


def generate_fpga_sources(out_dir):
    """Create parameters_*.vh, regmap_params.vh and dma_storage.v in out_dir."""
    sys.path.insert(0, os.path.join(REPO, "src"))
    import open_eye.generator as generator
    import open_eye.vh_file_creator as vh_file_creator
    cwd = os.getcwd()
    os.chdir(out_dir)  # the generator writes shared_config.json to the cwd
    try:
        generator.create_regmap_params_vh_file(
            os.path.join(REPO, "test", "cocotb_fpga"), out_dir, out_dir)
        vh_file_creator.create_vh_file_from_envvars(
            out_dir, os.path.join(REPO, "hdl") + "/", toplevel="OpenEye_FPGA")
    finally:
        os.chdir(cwd)


def lint_command(target, verilator, gen_dir):
    if target == "parallel":
        return [verilator] + COMMON_ARGS + ["hdl/OpenEye_Parallel.v"]
    if target == "fpga":
        return ([verilator] + COMMON_ARGS
                + ["-I" + gen_dir, "-y", "hdl/", "--top-module", "OpenEye_FPGA",
                   "hdl/OpenEye_FPGA.v", os.path.join(gen_dir, "dma_storage.v")])
    raise ValueError(target)


def parse(output, gen_dir):
    """Counter of 'CODE | file | message' plus the raw first lines per key."""
    counts = collections.Counter()
    raw = collections.defaultdict(list)
    for line in output.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        kind, code, path, lineno, _col, msg = m.groups()
        if kind == "Error" and code is None and msg.startswith("Exiting due to"):
            continue
        if path:
            path = os.path.abspath(os.path.join(REPO, path))
            if gen_dir and path.startswith(os.path.abspath(gen_dir)):
                path = "<generated>/" + os.path.relpath(path, gen_dir)
            else:
                path = os.path.relpath(path, REPO)
        key = f"{code or kind} | {path or '-'} | {msg.strip()}"
        counts[key] += 1
        raw[key].append(line)
    return counts, raw


def read_baseline(path):
    counts = collections.Counter()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    n, key = line.rstrip("\n").split("\t", 1)
                    counts[key] = int(n)
    return counts


def write_baseline(path, counts, version):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(f"# Verilator {version} lint baseline. count<TAB>code | file | message\n")
        f.write("# Regenerate with: python3 tools/lint_check.py --update\n")
        for key in sorted(counts):
            f.write(f"{counts[key]}\t{key}\n")


def verilator_version(verilator):
    out = subprocess.run([verilator, "--version"], capture_output=True, text=True).stdout
    m = re.search(r"Verilator (\d+\.\d+)", out)
    return m.group(1) if m else "unknown"


def check_target(target, verilator, update):
    with tempfile.TemporaryDirectory(prefix="lintgen_") as gen_dir:
        if target == "fpga":
            generate_fpga_sources(gen_dir)
        result = subprocess.run(lint_command(target, verilator, gen_dir), cwd=REPO,
                                capture_output=True, text=True)
        counts, raw = parse(result.stdout + result.stderr, gen_dir)

    baseline_path = os.path.join(BASELINE_DIR, f"{target}.txt")
    if update:
        write_baseline(baseline_path, counts, verilator_version(verilator))
        print(f"[{target}] baseline written: {sum(counts.values())} warnings/errors "
              f"-> {os.path.relpath(baseline_path, REPO)}")
        return True

    baseline = read_baseline(baseline_path)
    new = {k: counts[k] - baseline[k] for k in counts if counts[k] > baseline[k]}
    fixed = {k: baseline[k] - counts[k] for k in baseline if baseline[k] > counts[k]}
    print(f"[{target}] {sum(counts.values())} warnings/errors, baseline {sum(baseline.values())}: "
          f"{sum(new.values())} new, {sum(fixed.values())} fixed")
    for key, n in sorted(new.items()):
        print(f"  NEW (+{n}): {key}")
        for line in raw[key]:
            print(f"      {line}")
    for key, n in sorted(fixed.items()):
        print(f"  fixed (-{n}): {key}")
    if fixed and not new:
        print("  Warnings were fixed; run with --update to lower the baseline.")
    return not new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", choices=["parallel", "fpga", "all"], default="all")
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--update", action="store_true",
                        help="write the current warnings as the new baseline")
    args = parser.parse_args(argv)

    version = verilator_version(args.verilator)
    if version != BASELINE_VERSION:
        print(f"warning: Verilator {version}, baseline was made with {BASELINE_VERSION}; "
              "messages may differ")
    targets = ["parallel", "fpga"] if args.target == "all" else [args.target]
    ok = all([check_target(t, args.verilator, args.update) for t in targets])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
