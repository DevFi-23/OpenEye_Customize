#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Decode the iact read-loop registers (iact_read_limit_0..4, iact_read_inc_0..4) that each
profile case sent to the DUT, from test/.temp/*test_profile_conv_*/demo/layer_0_0/dma_stream_input.txt.

Usage: venv/bin/python tools/decode_iact_read_loops.py   (after tools/run_profile.py)
"""
import glob, os, re, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
names = ["iact_read_limit_%d" % i for i in range(5)] + ["iact_read_inc_%d" % i for i in range(5)]
rows = []
for d in sorted(glob.glob(os.path.join(REPO, "test/.temp/*test_profile_conv_*"))):
    case = re.search(r"test_profile_conv_(.*)_$", d).group(1)
    params = dict(re.findall(r"parameter (\w+)\s*=\s*(\d+)", open(os.path.join(d, "parameters_FPGA.vh")).read()))
    env = {k: params[k] for k in ("CLUSTER_ROWS", "CLUSTER_COLUMNS", "NUM_GLB_IACT", "NUM_GLB_PSUM", "NUM_GLB_WGHT",
                                  "DATA_PSUM_BITWIDTH", "TRANS_WORDS", "DMA_BITWIDTH", "QUANT_AMOUNT", "BUFFER_WIDTH", "BRANCHES")}
    os.environ.update(env)
    import importlib, open_eye.open_eye_parameters as oep, open_eye.generator as gen
    importlib.reload(oep); importlib.reload(gen)
    n = gen.regmap_transmissions(os.path.join(REPO, "test/cocotb_fpga"))
    assert n == int(params["TRANSMISSIONS"]), (case, n, params["TRANSMISSIONS"])
    words = [int(l) for l in open(os.path.join(d, "demo/layer_0_0/dma_stream_input.txt")) if l.strip()][:n]
    v = gen.unpack_registers(words, os.path.join(REPO, "test/cocotb_fpga"))
    rows.append((case, [v[k] for k in names], v.get("iact_size_x"), v.get("iact_size_y")))
print("case | limit_0..4 | inc_0..4 | (iact_size_x, iact_size_y) decoded")
for case, vals, sx, sy in rows:
    print(f"{case:32s} {vals[:5]} {vals[5:]} ({sx},{sy})")
