#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Build the fifth Word progress report (Vietnamese, 2026-11-10). Main topic: the activation functions, explained in
detail (algorithms, quantization, how they run on the chip), with the new measurement of every activation on the
sparse and the dense hardware; the other work since the report of 2026-11-05 in a shorter part.

Inputs:
  doc/perf/activation_2026-11-10_sparse_dense/trained_<act>_img0_<sparse|dense>.json   (test_real_model, OPENEYE_PROFILE)
  doc/perf/activation_2026-11-10_sparse_dense/params.json   (tools/report/extract_activation_params_2026-11-10.py)
  the step documents doc/experiments/2026-11-02_activation*.md (accuracy, ONNX Runtime comparison, tests) and
  doc/synth/ (Vivado), quoted below where noted.
Formatting helpers are shared with make_progress_report.py (the 2026-10-10 report).

    ~/tools/docenv/bin/python tools/report/make_progress_report_2026-11-10.py
Output: doc/reports/2026-11-10_TienDo/BaoCao_TienDo_OpenEye_2026-11-10.docx (+ five figure PNGs next to it)
"""

import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_progress_report as base_report  # noqa: E402
from make_progress_report import bullets, fmt, para, table  # noqa: E402

REPO = base_report.REPO
DATA = os.path.join(REPO, "doc", "perf", "activation_2026-11-10_sparse_dense")
OUT_DIR = os.path.join(REPO, "doc", "reports", "2026-11-10_TienDo")
DATE = "10/11/2026"
OUT = os.path.join(OUT_DIR, "BaoCao_TienDo_OpenEye_2026-11-10.docx")
FIG_FUNCS = os.path.join(OUT_DIR, "ham_kich_hoat_int8_2026-11-10.png")
FIG_QUANT = os.path.join(OUT_DIR, "luong_tu_hoa_2026-11-10.png")
FIG_CHIP = os.path.join(OUT_DIR, "duong_du_lieu_chip_2026-11-10.png")
FIG_ROUND = os.path.join(OUT_DIR, "lam_tron_2026-11-10.png")
FIG_MODES = os.path.join(OUT_DIR, "sparse_dense_ham_kich_hoat_2026-11-10.png")
CLOCK_NS = 4.0     # 250 MHz, met after place and route (doc/synth/2026-11-09_route4ns_stride1_zu7ev)

# Chart tokens: the validated reference palette of the dataviz method (as in the 2026-10-31 and 2026-11-05 reports);
# one fixed categorical slot per activation, the same in every figure
SURFACE, INK, INK_2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e8e7e2", "#d6d5cf"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
ACTS = [("relu", "ReLU"), ("leaky_relu", "Leaky ReLU"), ("silu", "SiLU"), ("hardswish", "hard-swish")]
COLOR = {key: c for (key, _), c in zip(ACTS, SLOTS)}
LABEL = dict(ACTS)
COMPUTE_LAYERS = [(0, "Conv1"), (2, "Conv2"), (4, "Conv3"), (5, "Dense")]

# State of the repository this report describes (README_FI.md section 3c, the log of 2026-11-10)
REGRESSION = "211 test RTL: 207 PASS + 4 xfail đã biết, 0 FAIL"
UNIT_TESTS = "485 unit test Python pass (11 lỗi cũ của test_dense_output.py, không liên quan)"


def load(path):
    with open(path) as f:
        return json.load(f)


def us(cycles):
    return f"{cycles * CLOCK_NS / 1000:.1f}".replace(".", ",")


def num(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",")


def pct(x, digits=1, sign=False):
    s = f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"
    return s.replace(".", ",").replace("-", "−") + " %"


def zeros(layer):
    inp = layer["info"]["input"]
    return 100.0 * inp["zeros"] / inp["values"] if inp["values"] else 0.0


def phase(profile_or_layer, name):
    return profile_or_layer["phases"].get(name, {}).get("cycles", 0)


def style_axes(ax, grid_axis="x"):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=INK_2, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    getattr(ax, grid_axis + "axis").grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def new_figure(w, h, rows=1, cols=1):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, axes = plt.subplots(rows, cols, figsize=(w, h), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    return fig, axes


def caption(doc, text):
    cap = doc.add_paragraph(text)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True
    cap.runs[0].font.size = Pt(10)


def formula(doc, text):
    """A centred formula line."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.font.name = "Cambria Math"
    r.font.size = Pt(11.5)
    return p


# ---------------------------------------------------------------- the arithmetic of the chip (hdl/quantization_unit.v)
def requantize(psum, mant, shift, rounding):
    product = mant * psum + ((1 << (shift - 1)) if rounding and shift > 0 else 0)
    return product >> shift


def hardware(layer, psum):
    """Output int8 of one psum, as quantization_unit.v (3 stages) and activation_table.v compute it."""
    mant, shift = layer["quantize"]
    if layer["act_mode"] == "leaky" and psum < 0:
        mant, shift = layer["act_negative"]
    q = requantize(psum, mant, shift, layer["act_round"])
    low = -128 if layer["act_mode"] in ("leaky", "table") else layer["act_min"]
    q = max(low, min(127, q))
    return layer["act_table"][q + 128] if layer["act_mode"] == "table" else q


def stages(layer, psum):
    mant, shift = layer["quantize"]
    neg = layer["act_mode"] == "leaky" and psum < 0
    if neg:
        mant, shift = layer["act_negative"]
    rc = (1 << (shift - 1)) if (layer["act_round"] and shift > 0) else 0
    product = mant * psum + rc
    shifted = product >> shift
    low = -128 if layer["act_mode"] in ("leaky", "table") else layer["act_min"]
    q = max(low, min(127, shifted))
    out = layer["act_table"][q + 128] if layer["act_mode"] == "table" else q
    return mant, shift, rc, product, shifted, q, out


# ---------------------------------------------------------------- figures
def figure_functions(params):
    """2 x 2: the float activation against what the chip outputs (int8 x scale), Conv2 of each trained model."""
    fig, axes = new_figure(9.4, 6.4, 2, 2)
    funcs = {
        "relu": lambda x: max(x, 0.0),
        "leaky_relu": lambda x: x if x >= 0 else 0.1 * x,
        "silu": lambda x: x / (1.0 + math.exp(-x)),
        "hardswish": lambda x: x * min(max(x + 3.0, 0.0), 6.0) / 6.0,
    }
    for ax, (key, label) in zip(axes.ravel(), ACTS):
        style_axes(ax, "y")
        ax.xaxis.grid(True, color=GRID, linewidth=0.6)
        layer = params[key][1]                                   # Conv2
        s_mul = layer["input_scale"] * layer["weight_scale"]     # real value of one psum unit
        s_pre = layer["output_scale"]                            # scale of the int8 pre-activation (conv output)
        s_next = layer["activation_output_scale"] or s_pre       # scale of the next layer's input
        xs_hw, ys_hw = [], []
        if layer["act_mode"] == "table":
            for i in range(256):
                xs_hw.append((i - 128) * s_pre)
                ys_hw.append(layer["act_table"][i] * s_next)
            lo, hi = -128 * s_pre, 127 * s_pre
        else:
            lo, hi = -128 * s_pre, 127 * s_pre
            for k in range(-1200, 1201):
                x = lo + (hi - lo) * (k + 1200) / 2400
                xs_hw.append(x)
                ys_hw.append(hardware(layer, int(round(x / s_mul))) * s_next)
        xf = [lo + (hi - lo) * k / 600 for k in range(601)]
        ax.plot(xf, [funcs[key](x) for x in xf], color=INK_2, linewidth=1.0, label="hàm thực (float)")
        ax.step(xs_hw, ys_hw, where="mid", color=COLOR[key], linewidth=1.6, label="chip (int8 × scale)")
        ax.set_title(label, fontsize=10, color=INK, loc="left")
        ax.set_xlim(lo, hi)
        ax.set_xlabel("giá trị trước hàm kích hoạt (số thực)", color=INK_2, fontsize=8)
        ax.tick_params(labelsize=7.5)
        if key in ("silu", "hardswish"):
            ins = ax.inset_axes([0.07, 0.5, 0.36, 0.42])
            ins.set_facecolor(SURFACE)
            win = range(96, 141)
            ins.step([(i - 128) * s_pre for i in win], [layer["act_table"][i] * s_next for i in win], where="mid",
                     color=COLOR[key], linewidth=1.3)
            ins.plot([(i - 128) * s_pre for i in win], [funcs[key]((i - 128) * s_pre) for i in win], color=INK_2,
                     linewidth=0.9)
            ins.tick_params(labelsize=6, colors=INK_2, length=0)
            for side in ins.spines.values():
                side.set_color(AXIS)
            ins.set_title("phóng to quanh 0", fontsize=6.5, color=INK_2)
    axes[0][0].legend(loc="upper left", frameon=False, fontsize=7.5)
    fig.tight_layout()
    fig.savefig(FIG_FUNCS, facecolor=fig.get_facecolor())
    plt.close(fig)


def boxes(ax, items, fontsize=7.3):
    for x, y, w, h, (fill, edge), text in items:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.0", linewidth=1.1,
                                    facecolor=fill, edgecolor=edge))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, color=INK, linespacing=1.35)


def arrow(ax, a, b, width=1.1, style="-|>"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=10, color=INK_2, linewidth=width,
                                 shrinkA=0, shrinkB=0))


BLUE, ORANGE, GREEN = ("#e9f1fb", "#2a78d6"), ("#fdece4", "#eb6834"), ("#e3f5ee", "#1baf7a")


def figure_quantization():
    """From the float model to the integers the chip computes: who computes what, with the formulas."""
    fig, ax = new_figure(9.6, 3.6)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")
    boxes(ax, [
        (0.5, 20, 17, 14, BLUE, "Model float\n(PyTorch, đã huấn luyện)\nx, w, b số thực"),
        (21, 20, 23, 14, BLUE, "Lượng tử tĩnh\n(ONNX Runtime, 200 ảnh\nhiệu chỉnh): mỗi tensor 1 scale\ns_x, s_w, s_out; zero point 0"),
        (47.5, 20, 25, 14, ORANGE, "Toolchain (onnx2model)\nq_w = làm_tròn(w / s_w), int8\nq_b = làm_tròn(b / (s_in·s_w)), int32\n"
                                   "M = s_in·s_w / s_đích ≈ mant / 2^shift\nbảng T hoặc hệ số âm"),
        (76, 20, 23.5, 14, GREEN, "Chip, mỗi layer\npsum = Σ q_x·q_w + q_b\n(số nguyên 20 bit)\nq = kẹp((mant·psum + r) >> shift)\nra = q hoặc T[q + 128]"),
        (21, 1, 23, 11, BLUE, "Giá trị thật ≈ scale × số nguyên\nx ≈ s_x · q_x,  w ≈ s_w · q_w\npsum · s_in · s_w ≈ Σ x·w + b"),
        (47.5, 1, 25, 11, ORANGE, "Gửi xuống chip qua DMA mỗi layer:\nweight, bias, mỗi filter 1 word lượng tử\n"
                                  "40 bit (offset 8, shift 7, mant 25),\n5 trường hàm kích hoạt, bảng 32 word"),
        (76, 1, 23.5, 11, GREEN, "Ra: int8 ở đúng scale input\ncủa layer tính kế tiếp\n(s_đích), đi thẳng vào\nbộ đệm iact trên chip"),
    ])
    for x0, x1 in ((17.6, 20.8), (44.2, 47.3), (72.7, 75.8)):
        arrow(ax, (x0, 27), (x1, 27))
    for xc in (32.5, 60, 87.75):
        arrow(ax, (xc, 19.7), (xc, 12.3), width=0.9)
    ax.text(36.5, 37.3, "Trên máy tính (một lần cho mỗi model)", ha="center", fontsize=8, color=INK_2)
    ax.text(87.75, 37.3, "Trên chip (mỗi ảnh)", ha="center", fontsize=8, color=INK_2)
    ax.plot([0.5, 72.5], [36, 36], color=AXIS, linewidth=0.8)
    ax.plot([76, 99.5], [36, 36], color=AXIS, linewidth=0.8)
    fig.tight_layout()
    fig.savefig(FIG_QUANT, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_chip():
    """Where the activation is computed in the chip: compute, psum buffer, quantizer stages, table, write-back."""
    fig, ax = new_figure(9.8, 5.0)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 54)
    ax.axis("off")
    boxes(ax, [
        # configuration path (top)
        (0.5, 40, 16, 11, BLUE, "DMA AXI 64 bit\n(bộ nhớ ngoài)"),
        (20, 40, 22, 11, BLUE, "Word trạng thái mỗi layer\n+ 5 trường hàm kích hoạt\n(19 bit, 0 word thêm)"),
        (45, 40, 22, 11, BLUE, "GET_QUANTIZE: mỗi filter\n1 word lượng tử 40 bit\n(mant 25, shift 7, offset 8)"),
        (70, 40, 29.5, 11, GREEN, "GET_ACTIVATION (trạng thái 15):\n32 word → bảng 256 ô, 1 word/chu kỳ\n(0 word nếu giữ bảng cũ)"),
        # data path (middle)
        (0.5, 20, 13, 13, BLUE, "Mảng PE\n4 cluster × 12 PE\nMAC int8\n(bỏ qua số 0)"),
        (16, 20, 11, 13, BLUE, "Bộ đệm\npsum\n(20 bit)"),
        (29.5, 20, 14.5, 13, GREEN, "Tầng 1\n+ offset, lấy dấu;\nLeaky: chọn\n(mant, shift)"),
        (46.5, 20, 14, 13, GREEN, "Tầng 2 (1 DSP)\nmant × sum\n+ 2^(shift−1)\nnếu làm tròn"),
        (63, 20, 13, 13, ORANGE, "Tầng 3\n>> shift\nkẹp [act_min,\n127]"),
        (78.5, 20, 9.5, 13, GREEN, "Bảng\n256 ô\nLUTRAM"),
        (90.5, 20, 9, 13, BLUE, "MUX\ntheo\nact_mode"),
        # destinations (bottom)
        (29.5, 2, 33, 11, BLUE, "Lớp cuối: psum thô 20 bit → DMA ra ngoài\n(không qua bộ lượng tử)"),
        (66, 2, 33.5, 11, BLUE, "RECEIVE_PSUMS_TO_IACT: ghi int8 vào bộ đệm iact\ncủa layer sau (Conv, Dense; max-pool đọc sau)"),
    ], fontsize=7.0)
    for x0, x1 in ((13.7, 15.8), (27.2, 29.3), (44.2, 46.3), (60.7, 62.8), (76.2, 78.3), (88.2, 90.3)):
        arrow(ax, (x0, 26.5), (x1, 26.5))
    arrow(ax, (16.7, 45.5), (19.8, 45.5))
    arrow(ax, (42.2, 45.5), (44.8, 45.5))
    arrow(ax, (67.2, 45.5), (69.8, 45.5))
    arrow(ax, (31, 39.8), (36, 33.3), width=0.9)
    arrow(ax, (56, 39.8), (53, 33.3), width=0.9)
    arrow(ax, (83, 39.8), (83, 33.3), width=0.9)
    arrow(ax, (95, 19.8), (88, 13.3), width=0.9)
    arrow(ax, (21.5, 19.8), (35, 13.3), width=0.9)
    ax.text(63, 17.2, "4 lane song song (WRITEBACK_WORDS); trễ 3 chu kỳ như trước khi có hàm kích hoạt",
            ha="center", fontsize=7.2, color=INK_2)
    for i, (label, (fill, edge)) in enumerate((("có từ trước", BLUE), ("kẹp ReLU (#30)", ORANGE),
                                               ("thêm cho hàm kích hoạt", GREEN))):
        ax.add_patch(FancyBboxPatch((1.0, 9.5 - 4 * i), 1.8, 1.8, boxstyle="round,pad=0.15", facecolor=fill,
                                    edgecolor=edge))
        ax.text(3.6, 10.4 - 4 * i, label, fontsize=6.8, color=INK_2, va="center")
    fig.tight_layout()
    fig.savefig(FIG_CHIP, facecolor=fig.get_facecolor())
    plt.close(fig)


# Share of the outputs within 1 int8 unit of ONNX Runtime, test images 0-3 (doc/experiments/2026-11-02_activation.md,
# section 4, measure_ort.py)
ORT_WITHIN1 = {
    "leaky_relu": {"floor": [99.9, 96.7, 82.7], "round": [100.0, 99.4, 97.7]},
    "silu": {"floor": [97.9, 97.7, 86.5], "round": [99.9, 99.4, 94.5]},
    "hardswish": {"floor": [99.2, 98.0, 90.4], "round": [99.9, 99.6, 97.9]},
}


def figure_rounding():
    fig, axes = new_figure(9.4, 3.1, 1, 3)
    w = 0.36
    for ax, key in zip(axes, ("leaky_relu", "silu", "hardswish")):
        style_axes(ax, "y")
        xs = list(range(3))
        floor, rnd = ORT_WITHIN1[key]["floor"], ORT_WITHIN1[key]["round"]
        ax.bar([x - w / 2 - 0.01 for x in xs], floor, w, color=SURFACE, edgecolor=COLOR[key], hatch="////",
               linewidth=1.0, label="làm tròn xuống (floor)")
        ax.bar([x + w / 2 + 0.01 for x in xs], rnd, w, color=COLOR[key], edgecolor=SURFACE, linewidth=1.0,
               label="làm tròn gần nhất")
        for x, a, b in zip(xs, floor, rnd):
            ax.text(x - w / 2 - 0.01, a + 0.4, num(a), ha="center", va="bottom", fontsize=6.5, color=INK)
            ax.text(x + w / 2 + 0.01, b + 0.4, num(b), ha="center", va="bottom", fontsize=6.5, color=INK)
        ax.set_xticks(xs)
        ax.set_xticklabels(["Conv1", "Conv2", "Conv3"], color=INK)
        ax.set_ylim(75, 103)
        ax.set_title(LABEL[key], fontsize=9.5, color=INK, loc="left")
    axes[0].set_ylabel("Output lệch ONNX Runtime ≤ 1 (%)", color=INK_2)
    fig.legend(handles=[Patch(facecolor=SURFACE, edgecolor=INK_2, hatch="////", label="làm tròn xuống (floor)"),
                        Patch(facecolor=INK_2, edgecolor=INK_2, label="làm tròn gần nhất")],
               ncol=2, loc="upper center", frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(FIG_ROUND, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_modes(runs):
    """Total cycles of each trained model on the sparse and on the dense hardware."""
    fig, ax = new_figure(9.2, 3.6)
    style_axes(ax, "y")
    w = 0.36
    top = max(runs[k][m]["total_cycles"] for k, _ in ACTS for m in ("sparse", "dense"))
    for i, (key, label) in enumerate(ACTS):
        s, d = runs[key]["sparse"]["total_cycles"], runs[key]["dense"]["total_cycles"]
        ax.bar(i - w / 2 - 0.01, s, w, color=COLOR[key], edgecolor=SURFACE, linewidth=1.0)
        ax.bar(i + w / 2 + 0.01, d, w, color=SURFACE, edgecolor=COLOR[key], hatch="////", linewidth=1.0)
        ax.text(i - w / 2 - 0.01, s + top * 0.012, f"{us(s)} µs", ha="center", va="bottom", fontsize=7.2, color=INK)
        ax.text(i + w / 2 + 0.01, d + top * 0.012, f"{us(d)} µs", ha="center", va="bottom", fontsize=7.2, color=INK)
        diff = (d - s) / s * 100
        ax.text(i, top * 1.10, f"dense {pct(diff, 1, True)}", ha="center", fontsize=7.6,
                color=INK if diff < 0 else INK_2, fontweight="bold" if diff < 0 else "normal")
    ax.set_xticks(range(len(ACTS)))
    ax.set_xticklabels([label for _, label in ACTS], color=INK)
    ax.set_ylim(0, top * 1.18)
    ax.set_ylabel("Chu kỳ cả mạng, ảnh test 0", color=INK_2)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(int(v))))
    ax.legend(handles=[Patch(facecolor=INK_2, edgecolor=INK_2, label="sparse (bỏ qua số 0, mặc định của fork)"),
                       Patch(facecolor=SURFACE, edgecolor=INK_2, hatch="////", label="dense (SPARSITY_EN = 0)")],
              ncol=2, loc="lower left", bbox_to_anchor=(0, 1.01), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_MODES, facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------- report
def build():
    params = load(os.path.join(DATA, "params.json"))
    runs = {key: {mode: load(os.path.join(DATA, f"trained_{key}_img0_{mode}.json")) for mode in ("sparse", "dense")}
            for key, _ in ACTS}
    sp = {key: runs[key]["sparse"]["total_cycles"] for key, _ in ACTS}
    dn = {key: runs[key]["dense"]["total_cycles"] for key, _ in ACTS}
    os.makedirs(OUT_DIR, exist_ok=True)
    figure_functions(params)
    figure_quantization()
    figure_chip()
    figure_rounding()
    figure_modes(runs)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    style.font.size = Pt(12)
    for section in doc.sections:
        section.left_margin = section.right_margin = Cm(2.2)
        section.top_margin = section.bottom_margin = Cm(2.0)

    title = doc.add_heading("BÁO CÁO TIẾN ĐỘ (LẦN 5)", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Hàm kích hoạt trên bộ tăng tốc OpenEye: thuật toán, lượng tử hoá và cách chạy trên chip")
    r.bold = True
    r.font.size = Pt(14)
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(f"Người thực hiện: Nguyễn Ngọc Trường Phi\nNgày: {DATE} (báo cáo trước: 05/11/2026)\n"
                 "Mã nguồn: github.com/DevFi-23/OpenEye (nhánh dev, private)").font.size = Pt(11)

    rel = {key: (sp[key] - sp["relu"]) / sp["relu"] * 100 for key, _ in ACTS}
    dd = {key: (dn[key] - sp[key]) / sp[key] * 100 for key, _ in ACTS}
    best_dense = min((dd[k], k) for k, _ in ACTS if k != "relu")
    # ---------------------------------------------------------------- 1
    doc.add_heading("1. Tóm tắt", level=1)
    bullets(doc, [
        "Bộ tăng tốc chạy 4 hàm kích hoạt trên chip: ReLU, Leaky ReLU, SiLU và hard-swish. Với mỗi hàm, một mạng MNIST đã "
        "huấn luyện đi trọn đường lượng tử của toolchain và chạy hết trên RTL, khớp từng bit với tham chiếu sau mọi layer.",
        "Thuật toán: ReLU là phép kẹp ở 0; Leaky ReLU dùng hai hệ số nhân, chọn theo dấu của tổng; SiLU và hard-swish tra "
        "một bảng 256 ô do máy tính tính sẵn cho từng layer. Mọi hàm dùng chung một phép nhân (mant / 2^shift) với bit "
        "làm tròn gần nhất, nằm trong 3 tầng sẵn có của bộ lượng tử: 0 chu kỳ thêm cho mỗi giá trị, 32 chu kỳ nạp bảng "
        "mỗi layer dùng bảng.",
        "Lượng tử hoá: int8 đối xứng (zero point 0), mỗi tensor một scale, hiệu chỉnh bằng 200 ảnh. Hàm kích hoạt được gộp "
        "với phép đổi scale về đúng scale input của layer tính kế tiếp, nên không cần bước lượng tử lại nào khác. Độ chính "
        "xác int8 trên 10.000 ảnh test: 99,27–99,35 %, cách model float tối đa 0,04 điểm.",
        f"Mới trong báo cáo này: vì phần cứng dense đã chạy đúng (sửa lỗi #46, #47 ngày 10/11), lần đầu đo được mỗi hàm "
        f"trên cả hai chế độ. Với ReLU sparse nhanh hơn (dense chậm hơn {pct(dd['relu'], 1)}), còn với Leaky ReLU, SiLU và "
        f"hard-swish dense nhanh hơn (chu kỳ {pct(dd['leaky_relu'], 1, True)}, {pct(dd['silu'], 1, True)}, "
        f"{pct(dd['hardswish'], 1, True)}): chế độ "
        "nên chọn theo hàm kích hoạt của model.",
        "Các việc khác từ 05/11: sửa Conv có stride (#41b, #41c, #41d) và dựng phần cứng có stride làm mặc định; thêm các "
        "phép kiểm tra để toolchain báo lỗi thay vì tính sai lặng lẽ (#7, #21, #27, #41, #42, #43, #48); rà soát 2 đợt "
        "commit của upstream (không lấy); đo dense so với sparse; sửa chế độ dense (#46, #47).",
        f"Tình trạng: {REGRESSION}; Bảng 3 của bài báo 16/16; Vivado đạt 250 MHz (59.548 LUT, 188 BRAM, 12 URAM, 4 DSP).",
    ])

    # ---------------------------------------------------------------- 2
    doc.add_heading("2. Bài toán", level=1)
    para(doc, "Trong mạng nơ-ron tích chập, sau mỗi layer Conv hay Dense là một hàm kích hoạt f áp lên từng giá trị đầu ra. "
              "ReLU (f(x) = max(x, 0)) là hàm đơn giản nhất và là hàm duy nhất RTL gốc của OpenEye làm được (module af_cluster.v "
              "có trong mã nguồn nhưng không nối vào đường dữ liệu). Các mạng nhúng hiện đại dùng hàm khác:")
    table(doc, ["Hàm", "Công thức (số thực)", "Đặc điểm", "Dùng trong"], [
        ["ReLU", "max(x, 0)", "Mọi số âm thành 0: nhiều số 0", "AlexNet, VGG, ResNet"],
        ["Leaky ReLU (α = 0,1)", "x nếu x ≥ 0; α·x nếu x < 0", "Hai đoạn thẳng, giữ số âm nhỏ", "YOLOv3, GAN"],
        ["SiLU (Swish)", "x · σ(x) = x / (1 + e^(−x))", "Đường cong trơn, có cực tiểu −0,28", "EfficientNet, YOLOv5–v8"],
        ["hard-swish", "x · kẹp(x + 3, 0, 6) / 6", "Xấp xỉ SiLU bằng các đoạn bậc hai", "MobileNetV3"],
    ], widths=[3.2, 4.8, 4.7, 4.0])
    para(doc, "Yêu cầu đặt ra: (1) kết quả trên chip khớp từng bit với tham chiếu Python của toolchain và gần ONNX Runtime "
              "(công cụ lượng tử model) trong giới hạn làm tròn; (2) không thêm chu kỳ cho mỗi giá trị và không làm chậm model "
              "chỉ dùng ReLU; (3) đo được cái giá thật của mỗi hàm. Công việc chia 4 bước: A (toolchain, chỉ Python), B (RTL, "
              "sau khi thiết kế được duyệt), C (profiler), D (đo trên model đã huấn luyện); cả 4 bước đã xong.")

    # ---------------------------------------------------------------- 3
    doc.add_heading("3. Lượng tử hoá: số thực thành số nguyên", level=1)
    para(doc, "Chip chỉ tính số nguyên (input và weight 8 bit, tổng 20 bit). Toàn bộ phần số thực được làm một lần trên máy "
              "tính khi chuẩn bị model; Hình 1 tóm tắt ai làm gì.")
    doc.add_picture(FIG_QUANT, width=Cm(16.5))
    caption(doc, "Hình 1. Đường lượng tử: trên máy tính (một lần cho mỗi model) và trên chip (mỗi ảnh).")

    doc.add_heading("3.1. Biểu diễn int8 đối xứng", level=2)
    para(doc, "Mỗi tensor (ảnh input, output của mỗi layer, weight của mỗi layer) có một scale s > 0; số thực x được biểu "
              "diễn bằng số nguyên q:")
    formula(doc, "q = kẹp(làm_tròn(x / s), −128, 127),     x ≈ s · q")
    bullets(doc, [
        "Đối xứng, zero point 0: số 0 thực là số 0 nguyên. Nhờ vậy một input bằng 0 cho tích bằng 0 và PE bỏ qua được nó "
        "(chế độ sparse), và ReLU chỉ là phép kẹp ở 0.",
        "Scale của activation do ONNX Runtime đo (lượng tử tĩnh, quantize_static, QOperator) khi cho 200 ảnh huấn luyện "
        "chạy qua model: s ≈ giá trị lớn nhất gặp được / 127. Weight: một scale cho cả layer (per_channel = False).",
        "Bias: số nguyên 32 bit ở scale của tổng, q_b = làm_tròn(b / (s_in · s_w)), để cộng thẳng vào tổng nguyên.",
    ])
    doc.add_heading("3.2. Phép tính trong một layer", level=2)
    para(doc, "Mảng PE tính tổng nguyên của mỗi output (psum, 20 bit):")
    formula(doc, "psum = Σ q_x · q_w + q_b,     giá trị thật ≈ psum · s_in · s_w")
    para(doc, "Để có input int8 cho layer sau (scale s_đích), cần nhân psum với hệ số thực M = s_in · s_w / s_đích rồi làm tròn "
              "và kẹp về int8. Đây là phép lượng tử lại (requantization); hàm kích hoạt được làm ngay tại đây.")
    doc.add_heading("3.3. Hệ số thực thành phép nhân và phép dịch", level=2)
    para(doc, "Chip không có số thực: M được thay bằng một số nguyên mant và một số bit dịch shift, M ≈ mant / 2^shift. "
              "Thuật toán (onnx2model.hardware_multiplier): tăng shift đến khi mant = làm_tròn(M · 2^shift) chạm giới hạn "
              "24 bit; lấy shift lớn nhất còn vừa. Khi đó 2^23 ≤ mant < 2^24 nên sai số tương đối của M nhỏ hơn 2^−24 "
              "(khoảng 6·10^−8), không đáng kể so với một đơn vị int8. Mỗi filter có một word lượng tử 40 bit (offset 8 bit, "
              "shift 7 bit, mant 25 bit); lỗi cắt sai mantissa (#38) đã sửa ở báo cáo trước.")
    rows = []
    for key, label in ACTS:
        for layer in params[key][:3]:
            mant, shift = layer["quantize"]
            target = "s_out (int8 trước bảng)" if layer["act_mode"] == "table" else "s_đích (input layer sau)"
            rows.append([label, layer["name"], fmt(mant), str(shift), f"{mant / 2 ** shift:.4e}".replace(".", ","), target])
    table(doc, ["Model", "Layer", "mant", "shift", "M = mant / 2^shift", "Scale đích"], rows,
          widths=[2.6, 1.6, 2.6, 1.3, 3.2, 5.2], align_right=(2, 3, 4))
    doc.add_heading("3.4. Làm tròn và kẹp", level=2)
    para(doc, "Dịch phải số học (>>) là làm tròn xuống (floor): mọi kết quả lệch trung bình −0,5 đơn vị int8, và độ lệch "
              "cộng dồn qua các layer. Phần cứng thêm bit làm tròn gần nhất (round half up):")
    formula(doc, "q = kẹp((mant · psum + 2^(shift − 1)) >> shift,  act_min, 127)")
    para(doc, "Hằng 2^(shift−1) được cộng bằng bộ cộng sau của DSP48E2 (phép A·B + C trong cùng tầng nhân), nên không tốn "
              "logic hay chu kỳ thêm. Kẹp (bão hoà) thay cho cắt bit: 130 thành 127 chứ không thành −126 (lỗi #30). "
              "Toolchain bật làm tròn cho Leaky ReLU, SiLU, hard-swish; ReLU giữ floor (làm tròn không tăng độ chính xác của "
              "ReLU mà làm mất một ít số 0). Hình 2: tỉ lệ output lệch ONNX Runtime không quá 1 đơn vị.")
    doc.add_picture(FIG_ROUND, width=Cm(16.5))
    caption(doc, "Hình 2. Tỉ lệ output lệch ONNX Runtime ≤ 1 đơn vị int8 (ảnh test 0–3), floor so với làm tròn gần nhất. "
                 "Không làm tròn, sai lệch tăng theo độ sâu (Conv3).")
    doc.add_heading("3.5. Gộp hàm kích hoạt với phép đổi scale", level=2)
    para(doc, "ONNX Runtime lượng tử lại nhiều lần quanh một hàm kích hoạt (ví dụ SiLU thành QLinearSigmoid rồi QLinearMul, và "
              "một lần nữa quanh Flatten trước Dense). Phần cứng ghi output của layer thẳng vào bộ đệm input của layer sau, nên "
              "toolchain gộp tất cả thành một bước: hàm kích hoạt nhắm thẳng tới scale input của layer tính kế tiếp (s_đích). "
              "Với Leaky ReLU, hai hệ số đã chứa sẵn tỉ lệ đổi scale; với SiLU và hard-swish, bảng nhận int8 ở scale output "
              "của conv (s_out) và trả int8 ở s_đích.")

    # ---------------------------------------------------------------- 4
    doc.add_heading("4. Thuật toán của từng hàm", level=1)
    lr = params["leaky_relu"][1]
    si = params["silu"][1]
    doc.add_heading("4.1. ReLU: kẹp ở 0", level=2)
    para(doc, "Với zero point 0, ReLU chỉ là đổi cận dưới của phép kẹp: act_min = 0 thay cho −128. Không cần phần cứng thêm "
              "ngoài phép kẹp đã có (lỗi #30).")
    formula(doc, "q = kẹp(⌊mant · psum / 2^shift⌋,  0, 127)")
    doc.add_heading("4.2. Leaky ReLU: hai hệ số chọn theo dấu", level=2)
    para(doc, "Leaky ReLU là hai đoạn thẳng qua gốc toạ độ, nên chỉ cần hai hệ số nhân: M₊ = s_in·s_w / s_đích cho psum ≥ 0 "
              "và M₋ = α · M₊ cho psum < 0. Dấu của psum có ngay ở tầng 1 (bit dấu của bộ cộng), tầng 1 chọn cặp (mant, shift) "
              "tương ứng và đưa sang tầng nhân. Hệ số âm chiếm 8 bit mant + 7 bit shift trong các bit còn trống của word trạng "
              "thái của layer, không tốn word DMA nào.")
    formula(doc, "q = kẹp(⌊(mant · psum + 2^(shift−1)) / 2^shift⌋, −128, 127),  (mant, shift) = psum ≥ 0 ? (mant₊, shift₊) : (mant₋, shift₋)")
    para(doc, f"Ví dụ Conv2 của model Leaky ReLU: (mant₊, shift₊) = ({fmt(lr['quantize'][0])}, {lr['quantize'][1]}), "
              f"(mant₋, shift₋) = ({lr['act_negative'][0]}, {lr['act_negative'][1]}); tỉ số "
              f"{num((lr['act_negative'][0] / 2 ** lr['act_negative'][1]) / (lr['quantize'][0] / 2 ** lr['quantize'][1]), 4)} "
              "≈ α = 0,1 (mant của hệ số âm chỉ có 8 bit nên sai số tương đối tối đa 0,4 %).")
    doc.add_heading("4.3. SiLU và hard-swish: bảng tra 256 ô", level=2)
    para(doc, "SiLU cần hàm mũ và phép chia; tính trực tiếp trên chip cần nhiều DSP và nhiều tầng. Nhưng sau phép lượng tử "
              "lại, input của hàm chỉ còn 256 giá trị int8 khả dĩ, nên chỉ cần tra bảng. Hàm được tách làm hai bước:")
    bullets(doc, [
        "Bộ lượng tử đưa psum về int8 tiền kích hoạt q ở scale s_out của conv (một cặp mant, shift, có làm tròn).",
        "Bảng: ra = T[q + 128], với T[i] = kẹp(làm_tròn(f((i − 128) · s_out) / s_đích), −128, 127). Máy tính tính bảng "
        "bằng số thực (onnx2model.activation_table) cho từng layer và gửi xuống cùng các word lượng tử.",
    ])
    tbl = si["act_table"]
    para(doc, f"Ví dụ Conv2 của model SiLU (s_out = {num(si['output_scale'], 5)}, s_đích = "
              f"{num(si['activation_output_scale'], 5)}): T quanh 0, i = 120…136 (q = −8…8): "
              f"{', '.join(str(v).replace('-', '−') for v in tbl[120:137])}. Phần âm nhỏ dần về 0 nhưng hiếm khi bằng 0, nên SiLU giữ rất ít "
              "số 0 (mục 7). Cách làm bảng đúng cho mọi hàm một biến (GELU, sigmoid, tanh, Mish…) mà không đổi phần cứng.")
    doc.add_picture(FIG_FUNCS, width=Cm(16.5))
    caption(doc, "Hình 3. Hàm thực (xám) và output của chip (màu), Conv2 của từng model đã huấn luyện. Bậc thang là độ phân "
                 "giải int8; với SiLU, hard-swish mỗi bậc là một ô của bảng. Đoạn nằm ngang bên phải là phép kẹp ở 127: "
                 "scale đích (input của Conv3) nhỏ hơn scale output của Conv2, giá trị lớn hơn bị bão hoà.")
    doc.add_heading("4.4. Ví dụ tính tay qua 3 tầng", level=2)
    para(doc, "Cùng một psum của Conv2, đi qua các tầng như chip tính (số liệu thật của 4 model, không làm tròn ở ReLU):")
    rows = []
    for key, label in ACTS:
        layer = params[key][1]
        for psum in (-20000, 20000):
            mant, shift, rc, product, shifted, q, out = stages(layer, psum)
            m = lambda v: str(v).replace("-", "−") if isinstance(v, int) and abs(v) < 1000 else fmt(v).replace("-", "−")
            rows.append([label, m(psum), f"({fmt(mant)}, {shift})", fmt(rc) if rc else "0", m(product), m(shifted),
                         m(q), m(out)])
    table(doc, ["Model", "psum", "Tầng 1: (mant, shift)", "Hằng làm tròn", "Tầng 2: tích", "Tầng 3: >> shift", "Kẹp",
                "Ra (bảng)"], rows, widths=[2.2, 1.5, 3.0, 2.3, 3.4, 1.6, 1.1, 1.4], align_right=(1, 3, 4, 5, 6, 7))

    # ---------------------------------------------------------------- 5
    doc.add_heading("5. Cách hàm kích hoạt chạy trên chip", level=1)
    para(doc, "Hàm kích hoạt nằm trên đường ghi ngược (write-back): sau khi mảng PE tính xong một lượt, các psum trong bộ đệm "
              "psum đi qua bộ lượng tử rồi được ghi vào bộ đệm iact trên chip làm input của layer sau, không ra bộ nhớ ngoài. "
              "Hình 4 là đường dữ liệu và đường cấu hình.")
    doc.add_picture(FIG_CHIP, width=Cm(16.5))
    caption(doc, "Hình 4. Vị trí của hàm kích hoạt trong chip: 3 tầng của bộ lượng tử, bảng tra, và nguồn cấu hình của chúng.")
    doc.add_heading("5.1. Bộ lượng tử 3 tầng (quantization_unit.v)", level=2)
    table(doc, ["Tầng", "Việc làm", "Thêm cho hàm kích hoạt"], [
        ["1", "sum = psum + offset; ghi thanh ghi sum, mant, shift", "Lấy bit dấu của sum; Leaky: chọn (mant₋, shift₋) khi âm; "
         "ghi cờ làm tròn"],
        ["2", "tích = mant × sum (1 DSP48E2, mant 25 bit)", "+ 2^(shift−1) khi làm tròn, bằng bộ cộng sau của DSP"],
        ["3", "tích >> shift, kẹp [act_min, 127]", "Không đổi"],
    ], widths=[1.3, 7.0, 8.4])
    para(doc, "Độ trễ vẫn 3 chu kỳ như trước, nên không chuỗi trễ nào của trạng thái ghi ngược (RECEIVE_PSUMS_TO_IACT) phải "
              "đổi. 4 lane chạy song song (WRITEBACK_WORDS = 4), mỗi chu kỳ 4 giá trị, như trước khi có hàm kích hoạt.")
    doc.add_heading("5.2. Bảng tra (activation_table.v)", level=2)
    bullets(doc, [
        "256 ô × 8 bit, chia thành 8 bank × 32 ô (với DMA 64 bit: E = 64 / 8 = 8 ô mỗi word). Ô i nằm ở bank i mod 8, địa "
        "chỉ i / 8. Word DMA thứ w mang ô 8w … 8w + 7: byte b ghi vào bank b ở địa chỉ w, cả 8 bank ghi cùng lúc, nên nạp "
        "bảng mất đúng 32 chu kỳ (16 với DMA 128 bit, 64 với 32 bit).",
        "Đọc không cần xung nhịp (LUTRAM phân tán): chỉ số = q + 128 = {¬q[7], q[6:0]} (đảo bit dấu), bank = 3 bit thấp, "
        "địa chỉ = 5 bit cao, rồi một bộ chọn 8:1. Vì đọc trong cùng chu kỳ, bảng không thêm tầng trễ nào.",
        "Mỗi lane ghi ngược có một bản bảng (4 bản), cùng được ghi từ một luồng DMA. Bộ chọn theo act_mode lấy output của "
        "bảng (chế độ 2) hoặc của bộ lượng tử (chế độ 0, 1).",
    ])
    doc.add_heading("5.3. Cấu hình và nạp mỗi layer", level=2)
    table(doc, ["Trường (word trạng thái)", "Bit", "Ý nghĩa"], [
        ["act_mode", "2", "0 kẹp (không hàm hoặc ReLU), 1 Leaky ReLU, 2 bảng"],
        ["act_round", "1", "0 floor, 1 làm tròn gần nhất (mọi chế độ)"],
        ["act_neg_mant / act_neg_shift", "8 / 7", "Hệ số của nửa âm (Leaky ReLU)"],
        ["act_keep_table", "1", "Giữ bảng của layer trước, không nạp lại"],
    ], widths=[5.2, 1.6, 9.9])
    para(doc, "19 bit này nằm trong các khe còn trống của word trạng thái, nên số word trạng thái không đổi ở DMA 32/64/128 "
              "bit (28/14/7 word). Máy trạng thái chính có thêm trạng thái GET_ACTIVATION (mã 15, mã cuối còn trống): sau khi "
              "nhận các word lượng tử, một layer ở chế độ bảng (và không giữ bảng cũ) nhận tiếp 2048 / DMA_BITWIDTH word vào "
              "bảng rồi mới bắt đầu tính. Lớp cuối của mạng đưa psum thô ra ngoài nên không có hàm kích hoạt.")
    doc.add_heading("5.4. Thời gian và tài nguyên", level=2)
    load_act = {key: phase(runs[key]["sparse"], "load_act") for key, _ in ACTS}
    table(doc, ["", "ReLU", "Leaky ReLU", "SiLU / hard-swish"], [
        ["Chu kỳ thêm mỗi giá trị", "0", "0", "0 (bảng đọc không xung nhịp)"],
        ["Chu kỳ thêm mỗi layer", "0", "0", "32 (nạp bảng, DMA 64 bit), 0 khi giữ bảng"],
        ["Đo trên mạng MNIST (pha load_act)", fmt(load_act["relu"]), fmt(load_act["leaky_relu"]),
         f"{fmt(load_act['silu'])} / {fmt(load_act['hardswish'])} (3 layer × 32)"],
        ["Word DMA thêm", "0", "0", "32 mỗi layer"],
    ], widths=[5.6, 2.0, 2.4, 6.7])
    para(doc, "Tài nguyên (Vivado, xczu7ev, 4 ns, đo khi thêm vào ở bước B): khoảng +550 LUT (+0,9 %) và +60 FF quy được cho "
              "hàm kích hoạt (4 bảng 354 LUT, trong đó 256 LUTRAM; 4 bộ lượng tử +193 LUT vì hằng làm tròn giữ đủ 46 bit của "
              "tích), 0 BRAM, 0 URAM, 0 DSP thêm; vẫn đạt 250 MHz. Mốc hiện tại của cả chip: 59.548 LUT, 39.449 FF, 188 BRAM, "
              "12 URAM, 4 DSP, WNS +0,042 ns.")

    # ---------------------------------------------------------------- 6
    doc.add_heading("6. Kiểm chứng và độ chính xác", level=1)
    table(doc, ["Kiểm tra", "Kết quả"], [
        ["Testbench riêng quantization_unit (Leaky, làm tròn, mọi shift, psum 20 và 32 bit)", "2/2 PASS, 30.470 output mỗi "
         "test khớp từng bit với mô hình Python (khoảng 6.100 trên nửa âm)"],
        ["Testbench riêng activation_table (nạp, đọc đủ 256 ô, nạp lại; word 32/64/128 bit)", "3/3 PASS"],
        ["test_activation_rtl: model ngẫu nhiên, mọi chế độ × làm tròn, Conv → Conv, Conv → Pool → Conv, chuỗi Dense, "
         "NUM_GLB_PSUM 2, DMA 32 bit, mạng 7 layer của bài báo", "12/12 PASS, mọi lần kiểm bộ đệm iact khớp từng bit"],
        ["Đối chứng âm (cố ý báo sai chế độ, lệch một ô bảng, tắt làm tròn)", "6/6 FAIL đúng như phải thế"],
        ["Model đã huấn luyện, ảnh test 0 và 1, cả 4 hàm (test_real_model)", "8/8 PASS, cả mạng khớp từng bit, DUT đoán đúng "
         "chữ số"],
        ["Model đã huấn luyện ở phần cứng dense (mới, 10/11)", "4/4 PASS, khớp từng bit"],
    ], widths=[9.6, 7.1])
    para(doc, "Độ chính xác trên 10.000 ảnh test MNIST (phép tính int8 đúng như chip, tuỳ chọn mặc định của toolchain):")
    table(doc, ["Hàm", "Float (PyTorch)", "ONNX Runtime int8", "Chip int8", "Làm tròn"], [
        ["ReLU", "99,35 %", "99,33 %", "99,35 %", "floor"],
        ["Leaky ReLU", "99,33 %", "99,34 %", "99,34 %", "gần nhất"],
        ["SiLU", "99,29 %", "99,29 %", "99,27 %", "gần nhất"],
        ["hard-swish", "99,36 %", "99,29 %", "99,35 %", "gần nhất"],
    ], widths=[3.4, 3.2, 3.6, 3.0, 2.6], align_right=(1, 2, 3))

    # ---------------------------------------------------------------- 7
    doc.add_heading("7. Hiệu năng: hàm kích hoạt trên phần cứng sparse và dense", level=1)
    para(doc, "Chip có hai chế độ dựng (tham số SPARSITY_EN). Sparse (mặc định của fork, kiến trúc Eyeriss v2) lưu input và "
              "weight kèm 4 bit đánh dấu số 0 và bỏ qua mọi phép nhân với 0. Dense truyền giá trị 8 bit trần và nhân hết. Hàm "
              "kích hoạt quyết định có bao nhiêu số 0 trong input của layer sau, nên quyết định chế độ nào nhanh hơn. Số liệu: "
              "mạng MNIST đã huấn luyện, ảnh test 0, đo bằng profiler, 250 MHz.")
    rows = []
    for key, label in ACTS:
        L = runs[key]["sparse"]["layers"]
        rows.append([label, f"{num(zeros(L[2]), 0)} / {num(zeros(L[4]), 0)} / {num(zeros(L[5]), 0)} %",
                     f"{fmt(sp[key])} ({us(sp[key])} µs)", f"{fmt(dn[key])} ({us(dn[key])} µs)", pct(dd[key], 1, True)])
    table(doc, ["Hàm", "Số 0 trong input Conv2 / Conv3 / Dense", "Sparse", "Dense", "Dense so với sparse"], rows,
          widths=[2.6, 4.4, 3.7, 3.7, 2.3], align_right=(2, 3, 4))
    doc.add_picture(FIG_MODES, width=Cm(16.0))
    caption(doc, "Hình 5. Chu kỳ cả mạng của 4 model trên phần cứng sparse (đặc) và dense (gạch chéo).")
    comp = {key: {mode: sum(phase(l, "compute") for l in runs[key][mode]["layers"]) for mode in ("sparse", "dense")}
            for key, _ in ACTS}
    wl = {key: {mode: phase(runs[key][mode], "load_wght") for mode in ("sparse", "dense")} for key, _ in ACTS}
    other_zeros = [zeros(runs[key]["sparse"]["layers"][li]) for key, _ in ACTS[1:] for li in (2, 4, 5)]
    zero_lo, zero_hi = round(min(other_zeros)), round(max(other_zeros))
    bullets(doc, [
        f"Ở sparse, ReLU nhanh nhất: input của Conv2, Conv3, Dense có 44–87 % số 0 được bỏ qua. Leaky ReLU, SiLU, "
        f"hard-swish giữ các số âm nhỏ, chỉ còn {zero_lo}–{zero_hi} % số 0, nên chậm hơn ReLU {pct(rel['leaky_relu'], 1)}, "
        f"{pct(rel['silu'], 1)}, {pct(rel['hardswish'], 1)}.",
        f"Ở dense, thời gian gần như không phụ thuộc hàm kích hoạt (FSM dense nhân hết, không nhìn giá trị): pha tính toán "
        f"{fmt(comp['relu']['dense'])} chu kỳ cho cả 4 model; chênh lệch còn lại là 96 chu kỳ nạp 3 bảng.",
        f"Dense nạp weight nhanh hơn 40 % ({fmt(wl['relu']['dense'])} so với {fmt(wl['relu']['sparse'])} chu kỳ): weight đã "
        "huấn luyện gần như không có số 0, nên 4 bit đánh dấu của sparse chỉ là phần thừa.",
        f"Kết quả: với ReLU dense chậm hơn {pct(dd['relu'], 1)}; với các hàm còn lại dense nhanh hơn "
        f"{pct(-dd['leaky_relu'], 1)} (Leaky ReLU) đến {pct(-best_dense[0], 1)}, và dense nhỏ hơn 26,9 % LUT. Chọn chế độ "
        "theo hàm kích hoạt của model; hướng tốt hơn cả hai là chế độ trộn (input sparse, weight 8 bit trần, mục 9).",
    ])

    # ---------------------------------------------------------------- 8
    doc.add_heading("8. Các việc khác đã làm (05/11 – 10/11/2026)", level=1)
    table(doc, ["Ngày", "Việc", "Kết quả"], [
        ["05/11", "Lỗi #40 (lượt weight cuối không đủ filter làm mất output); điều tra treo của upstream b10db82",
         "Thêm phép kiểm tra check_full_passes; treo là do upstream thiếu bản sửa #22 của fork"],
        ["06/11", "Rà soát upstream e8b3c3e…b1e02a0 (depthwise, PAGU)", "Không lấy: depthwise vẫn sai ngay trong test của "
         "upstream, chỉ có ở FSM dense"],
        ["07/11", "Lỗi làm model thật sai lặng lẽ (nhóm A)", "Toolchain báo lỗi thay vì tính sai: stride khi phần cứng không "
         "có stride (#41), padding khác \"same\" (#42), op ONNX không hỗ trợ (#43), số channel lẻ (#7), pooling rộng ≤ 4 (#27), "
         "Dense cuối nhiều lượt (#21); 56 test"],
        ["08/11", "Conv có stride (#41b, #41c, #41d)", "Sửa thứ tự output, ảnh rộng / cao lẻ (Python) và ghi ngược theo kích "
         "thước output (RTL 2 dòng); 12 test RTL stride 2"],
        ["09/11", "Dựng phần cứng có stride làm mặc định (STRIDE_ENABLED = 1)", "+155 LUT (+0,25 %), vẫn 250 MHz, mọi số đo "
         "cũ giữ nguyên"],
        ["09/11", "Rà soát upstream 302d330…9a742fb", "Không lấy: phá chế độ sparse (13/13 ca sai), mọi chuỗi layer sai ở "
         "2×2 cluster; tìm ra lỗi #45 của fork (6, 10 channel)"],
        ["09/11", "Đo dense so với sparse trên cùng model", "Dense +3,0 % chu kỳ với ReLU, −26,9 % LUT; sửa luồng weight dense "
         "(Python)"],
        ["10/11", "Lỗi chế độ dense #46, #47; #48", "#47: word weight toàn 0 bị bỏ; #46: thiếu chuyển tiếp psum ở FSM dense; "
         "sửa theo mẫu của upstream (RTL 26 dòng); #48 (số filter mỗi PE lẻ) được chặn; chế độ dense nay đúng"],
    ], widths=[1.5, 6.2, 9.0])
    para(doc, "Tình trạng sau các việc trên:")
    bullets(doc, [
        f"{REGRESSION}; {UNIT_TESTS}.",
        "12 ca mốc đo chu kỳ và Bảng 3 của bài báo (16/16 cấu hình) giống hệt từng chu kỳ sau mọi thay đổi của đợt này.",
        "Vivado (xczu7ev, 4 ns): 0 cảnh báo nghiêm trọng, 59.548 LUT, 188 BRAM, 12 URAM, 4 DSP, WNS +0,042 ns; bản dense "
        "43.523 LUT.",
        "Lỗi còn mở khi chạy model khác MNIST: số channel lẻ (#7), Dense cuối nhiều lượt (#21), pooling input hẹp (#27), số "
        "filter lẻ mỗi PE ở dense (#48): toolchain đã báo lỗi cho các trường hợp này; số channel lớn hơn 4 không chia hết "
        "cho 4 (#45) chưa có phép kiểm tra.",
    ])

    # ---------------------------------------------------------------- 9
    doc.add_heading("9. Định hướng tiếp theo", level=1)
    bullets(doc, [
        "Chế độ trộn: input sparse (giữ việc bỏ qua số 0 sau ReLU) và weight 8 bit trần (bỏ 4 bit đánh dấu): ước lượng "
        "khoảng −7 % chu kỳ so với sparse trên MNIST ReLU. Cần sửa đường weight trong PE (RTL, chờ duyệt).",
        "Nạp bias: chiếm 10,7 % tổng chu kỳ vì bias được gửi thành nguyên bản đồ psum ban đầu (14.336 word cho 32 bias của "
        "Conv1). Gửi mỗi filter một giá trị và để chip tự điền là chỗ tiết kiệm lớn nhất hiện thấy.",
        "Bảng tra như một nút chỉnh độ trễ: đặt các ô ±1 của bảng SiLU, hard-swish về 0 tăng số 0 lên 20–27 % mà không mất "
        "độ chính xác (99,30 / 99,32 %), khoảng −2 % chu kỳ ở sparse; chỉ cần đổi toolchain.",
        "Thêm hàm dạng bảng khác (GELU, sigmoid, tanh) chỉ bằng toolchain; chọn sparse / dense theo hàm kích hoạt của model.",
        "Sửa các lỗi còn mở để chạy được model lớn hơn MNIST (#7, #45, #21, #27, #48), rồi đo trên mạng thật (MobileNet).",
    ])

    doc.save(OUT)
    print("written", OUT)


if __name__ == "__main__":
    build()
