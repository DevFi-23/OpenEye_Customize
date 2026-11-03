#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Export a self-contained source folder for synthesising OpenEye_FPGA in Vivado.

The repository alone is not enough for Vivado: OpenEye_FPGA.v, PE.v,
PE_cluster.v and dma_storage.v include headers that the test runners generate
per configuration (parameters_FPGA.vh, parameters_PE.vh,
parameters_PE_cluster.vh, regmap_params.vh), and the checked-in
hdl/dma_storage.v is older than test/cocotb_fpga/regmap.yaml. This script
generates all of them from ONE configuration (the same environment variables
the tests use), copies the RTL next to them and writes a non-project Tcl flow
for an out-of-context synthesis of OpenEye_FPGA.

Output (default vivado/<name>/, ignored by git):
  rtl/            hdl/*.v (without the stale dma_storage.v) + generated dma_storage.v
  include/        the four generated .vh headers
  filelist.f      the sources in a fixed order
  config.json     the configuration the headers were generated from
  constraints.xdc clock constraint (out-of-context)
  synth_ooc.tcl   vivado -mode batch -source synth_ooc.tcl
  regmap_pack.py  status-word packing for this configuration (for reference)

The default configuration is the one of the latency baseline
(test/cocotb_fpga/test_profile.py), so the measured cycle counts and the
synthesised clock frequency belong to the same hardware.

Usage:
  python3 tools/export_vivado.py                        # baseline config, ZU7EV, 100 MHz
  python3 tools/export_vivado.py --part xc7z020clg400-1 --set CLUSTER_ROWS=1 --set CLUSTER_COLUMNS=1 --name z7020_1x1
  python3 tools/export_vivado.py --set CLUSTER_ROWS=4 --name rows4
"""

import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

# Configuration of the latency baseline (test_profile.py -> test_conv_const.py).
BASELINE = {
    "CLUSTER_ROWS": 2,
    "CLUSTER_COLUMNS": 2,
    "NUM_GLB_IACT": 1,
    "NUM_GLB_PSUM": 4,
    "NUM_GLB_WGHT": 3,
    "DATA_PSUM_BITWIDTH": 20,
    "TRANS_WORDS": 8,
    "BRANCHES": 1,
    "BUFFER_WIDTH": 12,
    "BUFFER_WIDTH_WGHT": 13,   # weight staging buffer 8,192 rows (bug #29); open_eye_parameters' default, written out for config.json
    "QUANT_AMOUNT": 32,
    "DMA_BITWIDTH": 64,
    "RAM_CELLS": 32,
}

DEFINES = ["SYNTHESIS", "NO_TRACE"]
TOP = "OpenEye_FPGA"


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", default="baseline", help="output folder name under --out (default: baseline)")
    p.add_argument("--out", default=os.path.join(ROOT, "vivado"), help="parent output directory")
    # The baseline configuration needs about 64k LUT and 272 BRAM36 (Yosys
    # estimate), more than an xc7z020 (53k LUT, 140 BRAM36) has.
    p.add_argument("--part", default="xczu7ev-ffvc1156-2-e",
                   help="FPGA part for synth_ooc.tcl (default: xczu7ev-ffvc1156-2-e, ZCU104)")
    p.add_argument("--clock-ns", type=float, default=10.0, help="clock period target in ns (default: 10 = 100 MHz)")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override one configuration value, e.g. --set CLUSTER_ROWS=4 (repeatable)")
    return p.parse_args(argv)


def configure(overrides):
    config = dict(BASELINE)
    for item in overrides:
        key, _, value = item.partition("=")
        if not value:
            raise SystemExit(f"--set expects KEY=VALUE, got {item!r}")
        config[key.strip()] = int(value)
    # open_eye_parameters and the regmap generator read the configuration from
    # the environment, exactly as in the test runners.
    for key, value in config.items():
        os.environ[key] = str(value)
    return config


def generate(out_dir):
    import open_eye.open_eye_parameters as oep
    import open_eye.vh_file_creator as vh_file_creator
    import open_eye.generator as generator

    rtl_dir = os.path.join(out_dir, "rtl")
    inc_dir = os.path.join(out_dir, "include")
    os.makedirs(rtl_dir)
    os.makedirs(inc_dir)

    # Both generators write helper files into the current directory
    # (demo/, shared_config.json); keep them inside the export folder.
    cwd = os.getcwd()
    os.chdir(out_dir)
    try:
        params = oep.get_oep(serial=False)
        for module, suffix in (("OpenEye_FPGA", "_FPGA"), ("PE_cluster", "_PE_cluster"), ("PE", "_PE")):
            vh_file_creator.create_vh_file(params, os.path.join(inc_dir, f"parameters{suffix}.vh"),
                                           toplevel=module)
        regmap_dir = os.path.join(ROOT, "test", "cocotb_fpga")
        generator.create_regmap_params_vh_file(regmap_dir, inc_dir, rtl_dir, out_dir)
        for leftover in ("shared_config.json", "demo"):
            path = os.path.join(out_dir, leftover)
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
    finally:
        os.chdir(cwd)

    hdl = os.path.join(ROOT, "hdl")
    sources = []
    for name in sorted(os.listdir(hdl)):
        # hdl/dma_storage.v predates test/cocotb_fpga/regmap.yaml; the
        # generated one written above replaces it (as in the test runners).
        if name.endswith(".v") and name != "dma_storage.v":
            shutil.copy2(os.path.join(hdl, name), os.path.join(rtl_dir, name))
            sources.append(f"rtl/{name}")
    sources.append("rtl/dma_storage.v")
    return sources


def write_flow(out_dir, sources, config, part, clock_ns):
    with open(os.path.join(out_dir, "filelist.f"), "w") as f:
        f.write("\n".join(sources) + "\n")

    with open(os.path.join(out_dir, "config.json"), "w") as f:
        json.dump({"top": TOP, "part": part, "clock_ns": clock_ns, "defines": DEFINES,
                   "config": config}, f, indent=2)
        f.write("\n")

    with open(os.path.join(out_dir, "constraints.xdc"), "w") as f:
        f.write(f"# Out-of-context clock constraint for {TOP} ({1000 / clock_ns:.1f} MHz).\n")
        f.write(f"create_clock -name clk -period {clock_ns:.3f} [get_ports clk_i]\n")

    defines = " ".join(f"-verilog_define {d}" for d in DEFINES)
    with open(os.path.join(out_dir, "synth_ooc.tcl"), "w") as f:
        f.write(f"""# Out-of-context synthesis of {TOP}, non-project mode.
# Run from this folder:  vivado -mode batch -source synth_ooc.tcl
# Optional arguments:    -tclargs <part> <clock_ns> [impl]
#   impl: continue with opt/place/route (out-of-context) for a post-route fmax.
# In the Vivado Tcl shell (no -tclargs) set run_impl 1 before sourcing to do the same.
set part     {part}
set clock_ns {clock_ns}
if {{![info exists run_impl]}} {{ set run_impl 0 }}
if {{$argc >= 1}} {{ set part     [lindex $argv 0] }}
if {{$argc >= 2}} {{ set clock_ns [lindex $argv 1] }}
if {{$argc >= 3 && [lindex $argv 2] eq "impl"}} {{ set run_impl 1 }}

proc openeye_result {{stage part clock_ns}} {{
    set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
    set fmax [expr {{1000.0 / ($clock_ns - $wns)}}]
    puts [format "OPENEYE_RESULT %s part=%s clock_ns=%s WNS=%.3f ns  fmax~%.1f MHz" \\
        $stage $part $clock_ns $wns $fmax]
}}

set here [file normalize [file dirname [info script]]]
cd $here
file mkdir reports

set_part $part
set fh [open filelist.f r]
foreach src [split [string trim [read $fh]] "\\n"] {{
    # -sv: the sources use Verilog-2005 plus a few SystemVerilog constructs
    # (the simulators and Yosys read them as SystemVerilog as well).
    read_verilog -sv $src
}}
close $fh

# Clock constraint before synthesis so that synthesis is timing driven
# (the OOC clock port is clk_i). constraints.xdc holds the same for the GUI.
set xdc [open reports/clock.xdc w]
puts $xdc "create_clock -name clk -period $clock_ns \[get_ports clk_i\]"
close $xdc
read_xdc reports/clock.xdc

synth_design -top {TOP} -part $part -mode out_of_context \\
    -include_dirs [list [file join $here include]] {defines} \\
    -flatten_hierarchy rebuilt

report_utilization                        -file reports/utilization.txt
report_utilization -hierarchical -hierarchical_depth 4 -file reports/utilization_hier.txt
report_timing_summary -max_paths 20       -file reports/timing_summary.txt
report_timing -max_paths 20 -sort_by group -file reports/timing_paths.txt
write_checkpoint -force reports/{TOP}_synth.dcp

openeye_result post-synthesis $part $clock_ns

if {{$run_impl}} {{
    opt_design
    place_design
    phys_opt_design
    route_design
    report_utilization                  -file reports/utilization_route.txt
    report_timing_summary -max_paths 20 -file reports/timing_summary_route.txt
    write_checkpoint -force reports/{TOP}_route.dcp
    openeye_result post-route $part $clock_ns
}}
""")


def main(argv):
    args = parse_args(argv)
    out_dir = os.path.abspath(os.path.join(args.out, args.name))
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    config = configure(args.set)
    sources = generate(out_dir)
    write_flow(out_dir, sources, config, args.part, args.clock_ns)
    print(f"[OK] Vivado sources for {TOP} written to {out_dir}")
    print(f"     {len(sources)} sources, headers in include/, part {args.part}, clock {args.clock_ns} ns")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
