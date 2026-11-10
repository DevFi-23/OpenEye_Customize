#!/bin/bash
# cases.sh <tree> <tag> [dense|sparse] [P]: the dense / sparse check set of bugs #46 / #47 through <tree>'s own flow
# (2026-10-31_upstream_review/up_run.py), P runs in parallel (default 3). One line per case: tag case | ns | verdict.
# From the repository root: doc/experiments/2026-11-10_bug46_47/cases.sh /path/to/tree fexp dense
T=$(cd "$1" && pwd); tag=$2; mode=${3:-dense}; P=${4:-3}; cd "$(dirname "$0")/../../.."
export PYTHONPATH=$T/src PATH=$PWD/venv/bin:$PATH OPENEYE_ALLOW_UNSUPPORTED=1 T tag
[ "$mode" = dense ] && export SPARSITY_EN=0 || export SPARSITY_EN=1
run() {
  set -- $1; name=$1; shift
  r=$(timeout 3000 venv/bin/python doc/experiments/2026-10-31_upstream_review/up_run.py $T ${tag}_$name "$@" 2>&1 | grep "^RESULT" | sed 's/^RESULT [^ ]* //' | cut -c1-150)
  t=$(grep -oE '(PASS|FAIL) +[0-9.]+' $T/test/.temp/up_${tag}_$name/cocotb_sim.log 2>/dev/null | tail -1 | awk '{print $2}')
  echo "$tag $name | ${t:-?} ns | $r"
}
export -f run
cat <<'CASES' | grep -v '^$' | xargs -P "$P" -I{} bash -c 'run "{}"'
f2 Convolution_Single 8 4 4 2 2 4 1
f4 Convolution_Single 8 4 4 4 2 4 1
f6 Convolution_Single 8 4 4 6 2 4 1
f8 Convolution_Single 8 4 8 8 2 4 1
f16 Convolution_Single 8 4 4 16 2 4 1
c16 Convolution_Single 8 4 16 16 2 4 1
c16s2 Convolution_Single 8 4 16 16 2 4 1 OPENEYE_SEED=2
c32 Convolution_Single 8 4 32 32 2 4 1
g3 Convolution_Single 8 8 4 16 2 4 1 GLBI=3
p28 Convolution_Single 28 28 1 32 2 4 1
stk4 Convolution_Stack 8 4 4 4 2 4 2
stk4p2 Convolution_Stack 8 4 4 4 2 2 2
cpc Conv_Pool_Conv 8 4 2 8 2 4 3
stk8 Convolution_Stack 8 4 8 8 2 4 2
stk16 Convolution_Stack 8 4 4 16 2 4 2
CASES
