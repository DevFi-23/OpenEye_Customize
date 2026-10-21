"""PE lock-step for the upstream cherry-pick (2bf497d + zero-extension): every PE carries a shadow copy of the
old PE (default revision 3717d12) with the same inputs; all 8 outputs are compared at each falling clock edge.

Writes PE_orig.v (old PE renamed PE_orig) and PE_lockstep.v (current hdl/PE.v with the shadow appended).
Usage: make_pe_lockstep.py [old revision]"""
import os
import re
import subprocess
import sys

REPO = "/home/truongphi/OpenEye_orig"
HERE = os.path.dirname(os.path.abspath(__file__))
OLD_REV = sys.argv[1] if len(sys.argv) > 1 else "3717d12"

old = subprocess.run(["git", "show", f"{OLD_REV}:hdl/PE.v"], cwd=REPO, capture_output=True, text=True, check=True).stdout
new = open(os.path.join(REPO, "hdl", "PE.v")).read()
orig = re.sub(r"^module PE\b", "module PE_orig", old, count=1, flags=re.M)
assert orig != old
open(os.path.join(HERE, "PE_orig.v"), "w").write(orig)

head = new[new.index("module PE #("):]
head = head[:head.index("\n);") + 3]
params = [m.group(1) for m in re.finditer(r"^\s*parameter\s+(?:integer\s+)?(\w+)\s*=", head, re.M)]
ports = [(m.group(1), m.group(2) or "", m.group(3)) for m in re.finditer(
    r"^\s*(input|output)\s+(?:reg\s+|wire\s+)?(\[[^\]]*\])?\s*(\w+)\s*,?\s*$", head, re.M)]
assert len(ports) == 24, len(ports)
outs = [(w, n) for d, w, n in ports if d == "output"]

blk = ["", "  // ---- lock-step shadow: old PE (" + OLD_REV + ") with the same inputs (verification only) ----"]
blk += [f"  wire {w} {n}__orig;" for w, n in outs]
plist = ", ".join(f".{p}({p})" for p in params)
conns = ", ".join(f".{n}({n}{'__orig' if d == 'output' else ''})" for d, w, n in ports)
blk.append(f"  PE_orig #({plist}) u_lockstep_orig ({conns});")
blk += ["  integer lockstep_cycles = 0;", "  integer lockstep_mismatches = 0;",
        "  always @(negedge clk_i) if (rst_ni) begin", "    lockstep_cycles = lockstep_cycles + 1;"]
for w, n in outs:
    blk.append(f"    if ({n} !== {n}__orig) begin $display(\"PE LOCKSTEP MISMATCH %0t %m: {n} new=%h old=%h\", $time, {n}, {n}__orig); "
               f"lockstep_mismatches = lockstep_mismatches + 1; $fatal(1, \"PE LOCKSTEP MISMATCH\"); end")
blk += ["  end",
        "  final $display(\"PE LOCKSTEP %s %m: %0d cycles, %0d outputs, %0d mismatches\", lockstep_mismatches ? \"FAIL\" : \"OK\", "
        f"lockstep_cycles, {len(outs)}, lockstep_mismatches);", ""]
i = new.rindex("endmodule")
open(os.path.join(HERE, "PE_lockstep.v"), "w").write(new[:i] + "\n".join(blk) + "\n" + new[i:])
print(f"{len(params)} parameters passed, {len(ports)} ports, {len(outs)} outputs compared")
