#!/bin/bash
# step2.sh <out dir>: step 2 of the per-layer weight format P1 (README_FI section 2), one part after the other, 6 jobs at
# a time, sparse hardware, no RTL change: the single-layer runs of test_step2.py (zero-compressed and dense weight
# layout, controls), then whole networks with the dense layout and raw_wght_i forced in simulation: Table 2 without and
# with ReLU (16 configurations each) and trained MNIST with 4 activations. Progress in <out dir>/progress.txt. From the
# repository root. Then: analyse_step2.py single / networks.
set -u
OUT=${1:?out dir}; mkdir -p "$OUT"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
unset SPARSITY_EN OPENEYE_WGHT_LAYOUT OPENEYE_FORCE_RAW_WGHT OPENEYE_WGHT_ZERO_FRACTION OPENEYE_WGHT_ZERO_PARITY
D=doc/experiments/2026-11-18_wght_layout_step2
log() { echo "$(date '+%m-%d %H:%M') $*" >> "$OUT/progress.txt"; }
log "start at $(git log --oneline -1) (+ working tree)"
venv/bin/python $D/run_step2.py doc/perf/wght_layout_2026-11-18 6 > "$OUT/single.log" 2>&1
log "single layers: $(grep -c '"PASS' doc/perf/wght_layout_2026-11-18/status.json) PASS of $(grep -c '": "' doc/perf/wght_layout_2026-11-18/status.json)"
export OPENEYE_WGHT_LAYOUT=dense OPENEYE_FORCE_RAW_WGHT=1
venv/bin/python tools/paper_table3.py --run --jobs 6 --save doc/perf/paper_table3_2026-11-18_wlayout \
    --report doc/perf/paper_table3_2026-11-18_wlayout.md > "$OUT/t3.log" 2>&1
log "Table 2 no act., dense layout: $(grep -c PASS doc/perf/paper_table3_2026-11-18_wlayout/status.json) PASS"
venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/run_relu.py doc/perf/paper_table3_2026-11-18_relu_wlayout 6 \
    > "$OUT/t3_relu.log" 2>&1
venv/bin/python tools/paper_table3.py doc/perf/paper_table3_2026-11-18_relu_wlayout \
    --report doc/perf/paper_table3_2026-11-18_relu_wlayout.md > /dev/null 2>&1
log "Table 2 ReLU, dense layout: $(grep -c PASS doc/perf/paper_table3_2026-11-18_relu_wlayout/status.json) PASS"
M=doc/perf/wght_layout_2026-11-18_mnist; mkdir -p $M
for a in relu leaky_relu silu hardswish; do echo $a; done | \
    xargs -P 4 -L 1 sh -c 'r=$([ $0 = relu ] && echo 0 || echo 1); venv/bin/python \
    doc/experiments/2026-11-12_rounding_modes/run_round.py $0 $r 1118w_$0 2>&1 | grep RESULT; \
    cp test/.temp/round_1118w_$0/profile.json '$M'/trained_${0}_img0_sparse.json' > "$OUT/mnist.log" 2>&1
venv/bin/python - "$OUT/mnist.log" "$M/status.json" <<'EOF'
import json, sys
st = {}
for line in open(sys.argv[1]):
    if line.startswith("RESULT"):
        act = line.split()[2]
        st[act] = "PASS" if ": PASS" in line else line.split(": ", 1)[1].split(";")[0]
json.dump(st, open(sys.argv[2], "w"), indent=1)
EOF
log "MNIST dense layout: $(grep -c ': PASS' "$OUT/mnist.log") PASS of 4"
log "done"
