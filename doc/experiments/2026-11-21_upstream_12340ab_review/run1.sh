#!/bin/bash
# run1.sh <tree> <tag> <sparse|dense> <case> <args...>: one case of the 2026-11-21 review through <tree>'s own Python,
# RTL and testbench (2026-10-31_upstream_review/up_run.py, Icarus, CR 2 x CC 2, QUANT_AMOUNT 1024, random data, seed 1).
# Prints: tag mode case | simulated ns | RESULT line. From the repository root.
T=$(cd "$1" && pwd); tag=$2; mode=$3; name=$4; shift 4
export PYTHONPATH=$T/src PATH=$PWD/venv/bin:$PATH OPENEYE_ALLOW_UNSUPPORTED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
[ "$mode" = dense ] && export SPARSITY_EN=0 || export SPARSITY_EN=1
r=$(timeout 3600 venv/bin/python doc/experiments/2026-10-31_upstream_review/up_run.py $T ${tag}_${mode}_$name "$@" 2>&1 | grep "^RESULT" | sed 's/^RESULT [^ ]* //')
f=$T/test/.temp/up_${tag}_${mode}_$name/cocotb_sim.log
t=$(grep -oE '(PASS|FAIL) +[0-9.]+' $f 2>/dev/null | tail -1 | awk '{print $2}')
echo "$tag $mode $name | ${t:-?} ns | ${r:-no RESULT line}"
