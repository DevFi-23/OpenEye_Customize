#!/bin/bash
# dev_p1_subset.sh <dev copy with the upstream hunk> <out dir>: the conv-side RTL tests of dev on a copy of dev that has
# only the iact_converter_x change of upstream 12340ab (OpenEye_FPGA.v), one pytest process per test, 8 at a time.
# Each line of <out dir>/results.txt: <test id> <last pytest line>. The same tests on dev itself are in the regression
# of 2026-11-21 (doc/experiments/2026-11-21_test_dense_output/regression, logs in test/.temp/<node id>).
T=$(cd "$1" && pwd); mkdir -p "$2"; out=$(cd "$2" && pwd); R=$PWD
export PATH=$R/venv/bin:$PATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OPENEYE_SKIP_FC_WRITE_CHECK=1 PYTHONPATH=$T/src
cd "$T"
: > "$out/ids.txt"
for f in test_conv_const test_glb_psum2 test_pooling test_stride test_bias_per_filter test_bug49 test_int8_clamp; do
  $R/venv/bin/python -m pytest --collect-only -q -p no:cacheprovider test/cocotb_fpga/$f.py | grep "::" >> "$out/ids.txt"
done
$R/venv/bin/python -m pytest --collect-only -q -p no:cacheprovider test/cocotb_fpga/test_mnist_layers.py -k "mapping or random" | grep "::" >> "$out/ids.txt"
echo "test/cocotb_fpga/test_real_model.py::test_real_model[0]" >> "$out/ids.txt"
wc -l < "$out/ids.txt"
xargs -P 8 -I{} sh -c 'r=$(timeout 7200 '$R'/venv/bin/python -m pytest -q -p no:cacheprovider "{}" 2>&1 | tail -1); echo "{} $r"' \
    < "$out/ids.txt" > "$out/results.txt"
