"""Shadow lock-step for one RTL module: the current hdl/<file> gets a shadow instance of the same module from an old
revision (renamed <module>_orig), same parameters and inputs; every output is compared with !== at each falling clock
edge and the first difference stops the simulation with $fatal. The real hierarchy is unchanged.

Usage: make_shadow_lockstep.py <module> <file in hdl/> <old revision> [clock] [active-low reset]
Writes <module>_orig.v and <module>_lockstep.v next to this script."""
import os
import re
import subprocess
import sys

REPO = "/home/truongphi/OpenEye_orig"
HERE = os.path.dirname(os.path.abspath(__file__))
mod, fname, old_rev = sys.argv[1], sys.argv[2], sys.argv[3]
clk = sys.argv[4] if len(sys.argv) > 4 else "clk_i"
rstn = sys.argv[5] if len(sys.argv) > 5 else "rst_ni"

old = subprocess.run(["git", "show", f"{old_rev}:hdl/{fname}"], cwd=REPO, capture_output=True, text=True, check=True).stdout
new = open(os.path.join(REPO, "hdl", fname)).read()
orig = re.sub(rf"^module {mod}\b", f"module {mod}_orig", old, count=1, flags=re.M)
assert orig != old
open(os.path.join(HERE, f"{mod}_orig.v"), "w").write(orig)

start = new.index(f"module {mod} #(")
head = new[start:new.index("\n);", start) + 3]
params = [m.group(1) for m in re.finditer(r"^\s*parameter\s+(?:integer\s+)?(\w+)\s*=", head, re.M)]
ports = [(m.group(1), m.group(2) or "", m.group(3)) for m in re.finditer(
    r"^\s*(input|output)\s+(?:reg\s+|wire\s+)?(\[[^\]]*\])?\s*(\w+)\s*,?\s*(?://.*)?$", head, re.M)]
n_lines = len(re.findall(r"^\s*(input|output)\b", head, re.M))
assert len(ports) == n_lines, (len(ports), n_lines)
outs = [(w, n) for d, w, n in ports if d == "output"]

blk = ["", f"  // ---- lock-step shadow: {mod} of {old_rev} with the same inputs (verification only) ----"]
blk += [f"  wire {w} {n}__orig;" for w, n in outs]
plist = ", ".join(f".{p}({p})" for p in params)
conns = ", ".join(f".{n}({n}{'__orig' if d == 'output' else ''})" for d, w, n in ports)
blk.append(f"  {mod}_orig #({plist}) u_lockstep_orig ({conns});")
blk += ["  integer lockstep_cycles = 0;", "  integer lockstep_mismatches = 0;",
        f"  always @(negedge {clk}) if ({rstn}) begin", "    lockstep_cycles = lockstep_cycles + 1;"]
for w, n in outs:
    blk.append(f"    if ({n} !== {n}__orig) begin $display(\"{mod.upper()} LOCKSTEP MISMATCH %0t %m: {n} new=%h old=%h\", $time, {n}, {n}__orig); "
               f"lockstep_mismatches = lockstep_mismatches + 1; $fatal(1, \"LOCKSTEP MISMATCH\"); end")
blk += ["  end",
        f"  final $display(\"{mod.upper()} LOCKSTEP %s %m: %0d cycles, %0d outputs, %0d mismatches\", lockstep_mismatches ? \"FAIL\" : \"OK\", "
        f"lockstep_cycles, {len(outs)}, lockstep_mismatches);", ""]
i = new.rindex("endmodule")
open(os.path.join(HERE, f"{mod}_lockstep.v"), "w").write(new[:i] + "\n".join(blk) + "\n" + new[i:])
print(f"{mod}: {len(params)} parameters, {len(ports)} ports, {len(outs)} outputs compared")
