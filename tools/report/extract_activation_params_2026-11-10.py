#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""The quantization and activation parameters of the four trained MNIST models, for the 2026-11-10 progress report.

Builds every variant as OpenEye_FPGA_tb with OPENEYE_MODEL_WEIGHTS does (doc/experiments/2026-11-02_activation/
eval_act.py: onnx2model static quantization on 200 training images, LayerParameters, DRAMContents) and writes, per
model and compute layer, the scales, the quantizer's [mant, shift] (filter 0, the one the hardware uses), the Leaky
ReLU negative factor, the 256-entry table, act_min and the rounding flag, plus a worked example: a few psums through
the three quantizer stages and the table exactly as hdl/quantization_unit.v and hdl/activation_table.v compute them.
Needs the project venv (torch, onnxruntime); the report itself is built by make_progress_report_2026-11-10.py in the
docx environment. Run from the repository root:
    venv/bin/python tools/report/extract_activation_params_2026-11-10.py
Output: doc/perf/activation_2026-11-10_sparse_dense/params.json
"""
import importlib.util
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVAL = os.path.join(REPO, "doc", "experiments", "2026-11-02_activation", "eval_act.py")
OUT = os.path.join(REPO, "doc", "perf", "activation_2026-11-10_sparse_dense", "params.json")
LAYERS = {0: "Conv1", 2: "Conv2", 4: "Conv3", 5: "Dense"}
EXAMPLE_PSUMS = [-5000, -200, 0, 200, 5000]


def stages(lp, psum):
    """psum through stage 1 (sign, chosen [mant, shift]), stage 2 (mant * psum + rounding constant), stage 3 (arithmetic
    shift, clamp) and the table, as the RTL does."""
    mant, shift = lp.quantize[0]
    use_neg = lp.act_mode == "leaky" and psum < 0
    if use_neg:
        mant, shift = lp.act_negative
    rc = (1 << (shift - 1)) if (lp.act_round and shift > 0) else 0
    product = mant * psum + rc
    shifted = product >> shift
    low = -128 if lp.act_mode in ("leaky", "table") else lp.act_min
    q = max(low, min(127, shifted))
    out = lp.act_table[q + 128] if lp.act_mode == "table" else q
    return {"psum": psum, "negative_slope": use_neg, "mant": mant, "shift": shift, "round_const": rc,
            "product": product, "shifted": shifted, "clamped": q, "out": out}


def main():
    spec = importlib.util.spec_from_file_location("eval_act", EVAL)
    sys.argv = [EVAL, "1"]
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    result = {}
    for activation in ("relu", "leaky_relu", "silu", "hardswish"):
        _, model, lps, _, _, _ = ev.build(activation)
        layers = []
        for n, name in LAYERS.items():
            lp, m = lps[n], model[n]
            layers.append({
                "index": n, "name": name,
                "input_scale": float(getattr(m, "input_scale", 0) or 0),
                "weight_scale": float(getattr(m, "scale", 0) or 0),
                "output_scale": float(getattr(m, "output_scale", 0) or 0),
                "activation": getattr(m, "activation", None),
                "activation_output_scale": float(getattr(m, "activation_output_scale", 0) or 0),
                "act_mode": lp.act_mode, "act_round": bool(lp.act_round), "act_min": int(lp.act_min),
                "quantize": [int(v) for v in lp.quantize[0]],
                "act_negative": [int(v) for v in lp.act_negative] if lp.act_negative else None,
                "act_table": [int(v) for v in lp.act_table] if lp.act_table is not None else None,
                "example": [stages(lp, p) for p in EXAMPLE_PSUMS] if n != 5 else None,
            })
        result[activation] = layers
        print(activation, [(l["name"], l["act_mode"], l["quantize"], l["act_negative"]) for l in layers])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(result, f, indent=1)
    print("written", OUT)


if __name__ == "__main__":
    main()
