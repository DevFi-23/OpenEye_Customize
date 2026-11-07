#!/bin/bash
# regression.sh <out dir>: the full RTL regression of README_FI 3c (189 tests, 6 at a time), one line per test
# (<id> <last pytest line>) in <out dir>/results.txt. About 1 hour. From the repository root.
out=${1:?out dir}; mkdir -p "$out"
export PATH=$PWD/venv/bin:$PATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OPENEYE_SKIP_FC_WRITE_CHECK=1   # test_nets calls "python"
F="test_conv_const test_mnist_layers test_gemm_layer test_pooling test_nets test_dense_chain test_glb_psum2 test_int8_clamp
   test_empty_pass test_activation_rtl test_real_model test_cluster_rows1 test_quant_mantissa"
: > "$out/ids.txt"
for f in $F; do venv/bin/python -m pytest --collect-only -q -p no:cacheprovider test/cocotb_fpga/$f.py | grep "::" >> "$out/ids.txt"; done
wc -l < "$out/ids.txt"
xargs -P 6 -I{} sh -c 'r=$(timeout 7200 venv/bin/python -m pytest -q -p no:cacheprovider "{}" 2>&1 | tail -1); echo "{} $r"' \
    < "$out/ids.txt" > "$out/results.txt"
grep -c " passed" "$out/results.txt"; grep -c "xfailed" "$out/results.txt"; grep -v " passed\| xfailed" "$out/results.txt"
