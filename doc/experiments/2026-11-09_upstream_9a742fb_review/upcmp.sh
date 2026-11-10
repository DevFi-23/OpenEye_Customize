#!/bin/bash
# upcmp.sh <tree> <tag> [dense]: the 13 cases of 2026-11-09_upstream_9a742fb_review.md through <tree>'s own Python, RTL and
# testbench (2026-10-31_upstream_review/up_run.py, Icarus, CR 2 x CC 2, QUANT_AMOUNT 1024, random data). A third argument
# "dense" sets SPARSITY_EN=0. One line per case: tag, case, simulated ns, verdict. From the repository root:
#   doc/experiments/2026-11-09_upstream_9a742fb_review/upcmp.sh $PWD dev dense
T=$(cd "$1" && pwd); tag=$2; cd "$(dirname "$0")/../../.."
export PYTHONPATH=$T/src PATH=$PWD/venv/bin:$PATH OPENEYE_ALLOW_UNSUPPORTED=1
[ "$3" = dense ] && export SPARSITY_EN=0
U=doc/experiments/2026-10-31_upstream_review/up_run.py
while read -r name args; do
  [ -z "$name" ] && continue
  r=$(timeout 3000 venv/bin/python $U $T ${tag}_$name $args 2>&1 | grep "^RESULT" | sed 's/^RESULT [^ ]* //')
  f=$T/test/.temp/up_${tag}_$name/cocotb_sim.log
  t=$(grep -oE '(PASS|FAIL) +[0-9.]+' $f 2>/dev/null | tail -1 | awk '{print $2}')
  echo "$tag $name | ${t:-?} ns | $r"
done <<'CASES'
c1_8x4c4 Convolution_Single 8 4 4 16 2 4
c2_8x4c2 Convolution_Single 8 4 2 16 2 4
c3_8x4c3 Convolution_Single 8 4 3 16 2 4
c4_8x4c8 Convolution_Single 8 4 8 16 2 4
c5_8x4c16 Convolution_Single 8 4 16 16 2 4
c6_8x8c4_g3 Convolution_Single 8 8 4 16 2 4 1 GLBI=3
c7_8x8c2_g3 Convolution_Single 8 8 2 16 2 4 1 GLBI=3
c8_28x28c1 Convolution_Single 28 28 1 32 2 4
c9_stack_c4 Convolution_Stack 8 4 4 4 2 4 2
c10_stack_c4_p2 Convolution_Stack 8 4 4 4 2 2 2
c11_cpc Conv_Pool_Conv 8 4 2 8 2 4 3
c12_stack_c8 Convolution_Stack 8 4 8 8 2 4 2
c13_16x4c6 Convolution_Single 16 4 6 16 2 4
CASES
