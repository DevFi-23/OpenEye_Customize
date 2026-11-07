#!/bin/bash
# mkv.sh <tree> <tag> [VAR=VALUE...]: run upstream's own cocotb Makefile flow (test/cocotb_fpga) of a worktree with
# Verilator 5.044 (cocotb 2.0.1 needs >= 5.036; the lint Verilator 5.020 is too old), no waveforms.
# Upstream's testbench ignores OPENEYE_SEED (the data of the 2026-11-06 runs was not seeded; OPENEYE_LAYER_SEED would fix
# the Keras weights only); OPENEYE_FAIL_ON_STALL / OPENEYE_PROBE_FSM exist upstream too.
# Log: <tree>/mkv_<tag>.log. Prints the exit code and the verdict lines.
#   git worktree add ../up_new b1e02a0; git worktree add ../up_old b10db82
#   doc/experiments/2026-11-06_upstream_dw_review/mkv.sh ../up_new dw12                     (DW, Makefile default 12x2x8)
#   doc/experiments/2026-11-06_upstream_dw_review/mkv.sh ../up_old dw12 EXTRA_ARGS= INPUT_SIZE_X=12 INPUT_SIZE_Y=2 \
#       INPUT_CHANNELS=8 NUM_FILTERS=8   (b10db82's Makefile always adds --trace-fst: EXTRA_ARGS= or the build needs zlib.h)
#   ... LAYER=Convolution_Single INPUT_SIZE_X=8 INPUT_SIZE_Y=8 INPUT_CHANNELS=4 NUM_FILTERS=16    (dense conv control)
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
tree=$(cd "$1" && pwd); tag=$2; shift 2
cd "$tree/test/cocotb_fpga" || exit 1
export PATH=$REPO/venv/bin:$HOME/tools/verilator-5.044/bin:$PATH
export PYTHONPATH=$tree/src
export OPENEYE_SEED=1 OPENEYE_FAIL_ON_STALL=200000 OPENEYE_PROBE_FSM=1
rm -rf sim_build
/usr/bin/time -v timeout 5400 make run WAVES=0 "$@" > "$tree/mkv_$tag.log" 2>&1
echo "EXIT $? $tag"
grep -E "TESTS=|feature maps differ|result check|No FSM progress|Maximum resident" "$tree/mkv_$tag.log" | tail -5 | cut -c1-250
