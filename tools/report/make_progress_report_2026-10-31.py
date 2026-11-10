#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Build the third Word progress report (Vietnamese, 2026-10-31).

Numbers come from the measured profiles: doc/perf/baseline_2026-10-24/ (the model cases with random data),
doc/perf/trained_mnist_2026-10-31/ (the trained MNIST model on real test images, after the fixes of bugs #31 and #32)
and doc/perf/paper_table3_2026-10-26_fix25/ (the network of Table 3 of the OpenEye paper on 16 hardware
configurations), and from doc/synth/2026-10-30_route4ns_fix31_zu7ev/ (Vivado). Formatting helpers are shared with
make_progress_report.py (the 2026-10-10 report).

    ~/tools/docenv/bin/python tools/report/make_progress_report_2026-10-31.py
Output: doc/reports/2026-10-31_TienDo/BaoCao_TienDo_OpenEye_2026-10-31.docx (+ five figure PNGs next to it)
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_progress_report as base_report  # noqa: E402
from make_progress_report import bullets, fmt, para, table  # noqa: E402

REPO = base_report.REPO
PERF = os.path.join(REPO, "doc", "perf")
BASELINE = os.path.join(PERF, "baseline_2026-10-24")
TRAINED = os.path.join(PERF, "trained_mnist_2026-10-31")
PAPER = os.path.join(PERF, "paper_table3_2026-10-26_fix25")
OUT_DIR = os.path.join(REPO, "doc", "reports", "2026-10-31_TienDo")   # one folder per report (2026-11-10)
DATE = "31/10/2026"
OUT = os.path.join(OUT_DIR, "BaoCao_TienDo_OpenEye_2026-10-31.docx")
FIG_FLOW = os.path.join(OUT_DIR, "luong_model_that_2026-10-31.png")
FIG_MODELS = os.path.join(OUT_DIR, "chu_ky_model_2026-10-31.png")
FIG_PHASES = os.path.join(OUT_DIR, "pha_theo_layer_2026-10-31.png")
FIG_ZEROS = os.path.join(OUT_DIR, "bo_qua_so_0_2026-10-31.png")
FIG_PAPER = os.path.join(OUT_DIR, "mang_paper_2026-10-31.png")
CLOCK_NS = 4.0     # 250 MHz, met after place and route (doc/synth/2026-10-30_route4ns_fix31_zu7ev)

# Chart tokens: the validated reference palette of the dataviz method, categorical slots in fixed order
SURFACE, INK, INK_2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e8e7e2", "#d6d5cf"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
ON_SLOT = ["white", "black", "black", "black", "black", "white", "white", "white"]
NEUTRAL = "#a3a29c"     # the reference (random data) series, as "before" in the 2026-10-15 report

LAYER_LABELS = ["Conv1", "Pool1", "Conv2", "Pool2", "Conv3", "Dense"]
MODEL_CASES = [   # (file, label)
    (os.path.join(BASELINE, "model_mnist16_c2.json"), "Mạng MNIST nhỏ (16 filter), ngẫu nhiên"),
    (os.path.join(BASELINE, "model_mnist_real_c2.json"), "Kiến trúc MNIST thật, ngẫu nhiên, 2 ch"),
    (os.path.join(BASELINE, "model_mnist_real_c1.json"), "Kiến trúc MNIST thật, ngẫu nhiên, 1 ch"),
    (os.path.join(TRAINED, "trained_mnist_img0.json"), "Đã huấn luyện, ảnh test 0 (số 7)"),
    (os.path.join(TRAINED, "trained_mnist_img1.json"), "Đã huấn luyện, ảnh test 1 (số 2)"),
    (os.path.join(TRAINED, "trained_mnist_img2.json"), "Đã huấn luyện, ảnh test 2 (số 1)"),
    (os.path.join(TRAINED, "trained_mnist_img7.json"), "Đã huấn luyện, ảnh test 7 (số 9)"),
]
PHASE_GROUPS = [   # (label, phases), slot order
    ("Tính toán", ["compute"]),
    ("Nạp weight", ["load_wght"]),
    ("Nạp bias", ["load_bias"]),
    ("Ghi ngược", ["writeback"]),
    ("Chuyển đổi iact", ["convert_iact"]),
    ("Pooling", ["pooling"]),
    ("Khác (cấu hình, iact, lượng tử, đọc ra)", ["load_config", "load_iact", "load_quant", "readout"]),
]
# Share of zero activations in each layer's input (the image channel for Conv1): the trained model on image 0 (measured
# on the RTL run, doc/perf/trained_mnist_2026-10-31.md) and the random-data case (testbench reference of MNIST_REAL, seed 1)
ZEROS_IMG0 = {0: 0, 2: 44, 4: 87, 5: 74}
ZEROS_RANDOM = {0: 0, 2: 6, 4: 11, 5: 10}


def load(path):
    with open(path) as f:
        return json.load(f)


def kfmt(v):
    return f"{v / 1000:.0f}k" if v >= 10000 else f"{v / 1000:.1f}k".replace(".", ",")


def us(cycles):
    return f"{cycles * CLOCK_NS / 1000:.0f}"


def pct(x, digits=0):
    return f"{x * 100:.{digits}f} %".replace(".", ",")


def phase_cycles(layer, parts):
    return sum(layer["phases"].get(p, {}).get("cycles", 0) for p in parts)


def style_axes(ax, grid_axis="x"):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=INK_2, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    getattr(ax, grid_axis + "axis").grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def new_figure(w, h):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    return fig, ax


# ---------------------------------------------------------------- figures
def figure_flow():
    """The toolchain's real-model path, as boxes and arrows."""
    fig, ax = new_figure(9.2, 3.3)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 36)
    ax.axis("off")
    sw, hw = ("#e9f1fb", "#2a78d6"), ("#fdece4", "#eb6834")
    boxes = [
        (1, 21, 18, 13, sw, "Model PyTorch\nđã huấn luyện\n(99,35 %)"),
        (21, 21, 18, 13, sw, "onnx2model\nxuất ONNX, lượng tử\ntĩnh int8 (zp 0)"),
        (41, 21, 18, 13, sw, "LayerParameters\nánh xạ, thanh ghi,\nmant/shift, ReLU"),
        (61, 21, 18, 13, sw, "DRAMContents\n+ mapper\nstream DMA"),
        (81, 21, 18, 13, hw, "RTL OpenEye\nConv, ReLU, MaxPool,\nDense trên chip"),
        (21, 2, 28, 12, sw, "Tham chiếu testbench\n= ONNX Runtime\n(chỉ lệch do làm tròn)"),
        (61, 2, 38, 12, hw, "So từng word bộ đệm sau mỗi layer\nvà psum của Dense:\nkhớp từng bit, ảnh test 0–7"),
    ]
    for x, y, w, h, (fill, edge), text in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2", linewidth=1.2,
                                    facecolor=fill, edgecolor=edge))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8, color=INK)
    for x0, x1 in ((19.6, 20.8), (39.6, 40.8), (59.6, 60.8), (79.6, 80.8)):
        ax.add_patch(FancyArrowPatch((x0, 27.5), (x1, 27.5), arrowstyle="-|>", mutation_scale=10, color=INK_2,
                                     linewidth=1.2))
    for (xa, ya), (xb, yb) in (((50, 20.6), (37, 14.4)), ((90, 20.6), (82, 14.4)), ((49.4, 8), (60.6, 8))):
        ax.add_patch(FancyArrowPatch((xa, ya), (xb, yb), arrowstyle="-|>", mutation_scale=10, color=INK_2,
                                     linewidth=1.0))
    ax.add_patch(FancyBboxPatch((1, 4.5), 3, 2.5, boxstyle="round,pad=0.2", facecolor=sw[0], edgecolor=sw[1]))
    ax.text(5.5, 5.7, "phần mềm", fontsize=8, color=INK_2, va="center")
    ax.add_patch(FancyBboxPatch((1, 0.5), 3, 2.5, boxstyle="round,pad=0.2", facecolor=hw[0], edgecolor=hw[1]))
    ax.text(5.5, 1.7, "phần cứng", fontsize=8, color=INK_2, va="center")
    fig.tight_layout()
    fig.savefig(FIG_FLOW, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_models(models):
    """Horizontal stacked bars: total cycles of each model case, one segment per layer."""
    fig, ax = new_figure(9.4, 4.4)
    style_axes(ax)
    y = list(range(len(models)))[::-1]
    top = max(m["total_cycles"] for _, m in models)
    left = [0] * len(models)
    for i, name in enumerate(LAYER_LABELS):
        vals = [m["layers"][i]["total_cycles"] for _, m in models]
        ax.barh(y, vals, left=left, height=0.62, color=SLOTS[i], edgecolor=SURFACE, linewidth=1.5, label=name)
        for yi, v, l in zip(y, vals, left):
            if v >= 0.07 * top:
                ax.text(l + v / 2, yi, kfmt(v), ha="center", va="center", color=ON_SLOT[i], fontsize=7.5)
        left = [l + v for l, v in zip(left, vals)]
    for yi, (_, m) in zip(y, models):
        ax.text(m["total_cycles"] + top * 0.01, yi, f"{fmt(m['total_cycles'])}  ({us(m['total_cycles'])} µs)",
                va="center", ha="left", fontsize=8, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([label for label, _ in models], color=INK)
    ax.set_xlim(0, top * 1.28)
    ax.set_xlabel("Số chu kỳ (µs ở 250 MHz trong ngoặc)", color=INK_2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(int(v))))
    ax.legend(ncol=6, loc="lower left", bbox_to_anchor=(0, 1.01), frameon=False, fontsize=8, handlelength=1.2,
              columnspacing=1.2)
    fig.tight_layout()
    fig.savefig(FIG_MODELS, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_phases(profile):
    """Horizontal stacked bars: cycles of each layer of the trained model (image 0) by phase."""
    fig, ax = new_figure(9.4, 3.9)
    style_axes(ax)
    layers = profile["layers"]
    y = list(range(len(layers)))[::-1]
    top = max(l["total_cycles"] for l in layers)
    left = [0] * len(layers)
    for g, (name, parts) in enumerate(PHASE_GROUPS):
        vals = [phase_cycles(l, parts) for l in layers]
        ax.barh(y, vals, left=left, height=0.62, color=SLOTS[g], edgecolor=SURFACE, linewidth=1.5, label=name)
        for yi, v, l in zip(y, vals, left):
            if v >= 0.06 * top:
                ax.text(l + v / 2, yi, kfmt(v), ha="center", va="center", color=ON_SLOT[g], fontsize=7.5)
        left = [l + v for l, v in zip(left, vals)]
    for yi, l in zip(y, layers):
        ax.text(l["total_cycles"] + top * 0.01, yi, fmt(l["total_cycles"]), va="center", ha="left", fontsize=8,
                color=INK)
    names = []
    for i, l in enumerate(layers):
        info = l["info"]
        if info["name"] == "Pooling":
            names.append(f"{LAYER_LABELS[i]}: MaxPool {info['iact_size_x']}×{info['iact_size_y']}×{info['channels']}")
        elif info["name"] == "Dense":
            names.append(f"{LAYER_LABELS[i]}: {info['iact_size_x'] * info['iact_size_y'] * info['channels']} → {info['filters']}")
        else:
            names.append(f"{LAYER_LABELS[i]}: {info['iact_size_x']}×{info['iact_size_y']}, {info['channels'] - info.get('pad_channels', 0)} → {info['filters']}")
    ax.set_yticks(y)
    ax.set_yticklabels(names, color=INK)
    ax.set_xlim(0, top * 1.12)
    ax.set_xlabel("Số chu kỳ", color=INK_2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(int(v))))
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.01), frameon=False, fontsize=8, handlelength=1.2,
              columnspacing=1.2)
    fig.tight_layout()
    fig.savefig(FIG_PHASES, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_zeros(random, trained):
    """Grouped bars: compute cycles per compute layer, random data vs the trained model on image 0."""
    fig, ax = new_figure(8.4, 3.8)
    style_axes(ax, "y")
    idx = [0, 2, 4, 5]
    xs = list(range(len(idx)))
    w = 0.36
    a = [random["layers"][i]["phases"]["compute"]["cycles"] for i in idx]
    b = [trained["layers"][i]["phases"]["compute"]["cycles"] for i in idx]
    ax.bar([x - w / 2 - 0.01 for x in xs], a, w, color=NEUTRAL, label="Weight và dữ liệu ngẫu nhiên (mốc model_mnist_real_c1)")
    bars = ax.bar([x + w / 2 + 0.01 for x in xs], b, w, color=SLOTS[0], label="Model đã huấn luyện, ảnh test 0")
    for x, va, vb in zip(xs, a, b):
        ax.text(x - w / 2 - 0.01, va, fmt(va), ha="center", va="bottom", fontsize=7.5, color=INK)
        ax.text(x + w / 2 + 0.01, vb, f"{fmt(vb)}\n{(vb - va) / va * 100:+.0f} %".replace("+0 %", "0 %"),
                ha="center", va="bottom", fontsize=7.5, color=INK)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{LAYER_LABELS[i]}\nsố 0 trong input:\n{ZEROS_RANDOM[i]} % / {ZEROS_IMG0[i]} %" for i in idx], color=INK)
    ax.set_ylabel("Chu kỳ pha tính toán", color=INK_2)
    ax.set_ylim(0, max(a) * 1.25)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(int(v))))
    ax.legend(loc="upper right", frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_ZEROS, facecolor=fig.get_facecolor())
    plt.close(fig)


def paper_runs():
    status = load(os.path.join(PAPER, "status.json"))
    runs = {}
    for cr in (1, 2, 4, 8):
        for x in (2, 4):
            for yy in (3, 4):
                name = f"paper_cr{cr}_x{x}_y{yy}"
                runs[(cr, x, yy)] = (load(os.path.join(PAPER, name + ".json"))["total_cycles"], status[name])
    return runs


def figure_paper(runs):
    """Lines: total cycles of the paper's network against the cluster rows, one line per PE array."""
    fig, ax = new_figure(8.4, 3.7)
    style_axes(ax, "y")
    crs = [1, 2, 4, 8]
    xs = list(range(len(crs)))
    ends = []
    for s, (x, yy) in enumerate(((2, 3), (4, 3), (2, 4), (4, 4))):
        vals = [runs[(cr, x, yy)][0] for cr in crs]
        ok = [runs[(cr, x, yy)][1].startswith("PASS") for cr in crs]
        ax.plot(xs, vals, color=SLOTS[s], linewidth=2, label=f"PE {x}×{yy} mỗi cluster")
        for xi, v, good in zip(xs, vals, ok):
            ax.plot([xi], [v], marker="o", markersize=6, color=SLOTS[s], markerfacecolor=SLOTS[s] if good else SURFACE,
                    markeredgewidth=1.8, linestyle="none")
        ends.append((vals[-1], f"{x}×{yy}: {fmt(vals[-1])}"))
    # End labels, pushed apart so that close lines stay readable
    top = max(v for (cr, x, yy), (v, _) in runs.items())
    gap = top * 0.075
    placed = []
    for v, text in sorted(ends):
        y_text = max(v, placed[-1] + gap) if placed else v
        placed.append(y_text)
        ax.text(xs[-1] + 0.1, y_text, text, va="center", fontsize=7.5, color=INK)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{cr} hàng cluster\n({cr * 2} cluster)" for cr in crs], color=INK)
    ax.set_xlim(-0.2, len(crs) - 0.2)
    ax.set_ylim(0, None)
    ax.set_ylabel("Tổng chu kỳ của mạng (7 layer)", color=INK_2)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(int(v))))
    ax.legend(loc="upper right", frameon=False, fontsize=8)
    ax.text(0, -0.30, "Điểm rỗng: cấu hình còn tính sai (lỗi #19b, #28); số chu kỳ vẫn đo được.", transform=ax.transAxes,
            fontsize=7.5, color=INK_2)
    fig.tight_layout()
    fig.savefig(FIG_PAPER, facecolor=fig.get_facecolor())
    plt.close(fig)


def caption(doc, text):
    cap = doc.add_paragraph(text)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True


# ---------------------------------------------------------------- report
def build():
    models = [(label, load(path)) for path, label in MODEL_CASES]
    random_c1 = models[2][1]
    trained0 = models[3][1]
    trained = [m for label, m in models if label.startswith("Đã huấn luyện")]
    runs = paper_runs()
    os.makedirs(OUT_DIR, exist_ok=True)
    figure_flow()
    figure_models(models)
    figure_phases(trained0)
    figure_zeros(random_c1, trained0)
    figure_paper(runs)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    style.font.size = Pt(12)
    for section in doc.sections:
        section.left_margin = section.right_margin = Cm(2.2)
        section.top_margin = section.bottom_margin = Cm(2.0)

    title = doc.add_heading("BÁO CÁO TIẾN ĐỘ (LẦN 3)", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Tối ưu bộ tăng tốc mạng nơ-ron OpenEye theo băng thông và độ trễ")
    r.bold = True
    r.font.size = Pt(14)
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(f"Người thực hiện: Nguyễn Ngọc Trường Phi\nNgày: {DATE} (báo cáo trước: 15/10/2026)\n"
                 "Mã nguồn: github.com/DevFi-23/OpenEye (nhánh dev, private)").font.size = Pt(11)

    t_min = min(m["total_cycles"] for m in trained)
    t_max = max(m["total_cycles"] for m in trained)
    # ---------------------------------------------------------------- 1
    doc.add_heading("1. Tóm tắt", level=1)
    bullets(doc, [
        "Mạng MNIST đã huấn luyện (PyTorch, 99,35 %) chạy trọn trên bộ tăng tốc ở mức RTL: 3 Conv + ReLU, 2 MaxPool và Dense "
        "3136 → 10, dữ liệu giữa các layer được ghi ngược và pooling ngay trên chip. Với 8 ảnh test MNIST (0–7), kết quả sau mỗi "
        "layer khớp từng bit với tham chiếu và bộ tăng tốc đoán đúng chữ số ở cả 8 ảnh.",
        f"Độ trễ đo bằng profiler theo từng layer: {fmt(t_min)}–{fmt(t_max)} chu kỳ một ảnh, tức {us(t_min)}–{us(t_max)} µs ở "
        "250 MHz (bộ nhớ lý tưởng). Conv2 chiếm khoảng 51 %; pha tính toán chiếm 56–58 %.",
        "Toolchain Python của dự án được mở rộng để chở model thật: lượng tử tĩnh int8 (zero point 0, một scale mỗi layer) "
        "thay cho lượng tử động của mã nguồn gốc, vốn không đưa xuống phần cứng được. Tham chiếu của toolchain trùng ONNX "
        "Runtime (chỉ lệch do làm tròn) và đúng 99,5 % trên 1000 ảnh test đầu.",
        "Thêm bộ kẹp int8 và ReLU gộp vào bộ lượng tử (trước đây kết quả tràn bị quấn vòng và không có hàm kích hoạt).",
        "Từ báo cáo trước đã sửa 10 lỗi làm sai kết quả (6 sửa RTL, 4 chỉ Python) và xác định 1 báo động giả của testbench; 3 lỗi "
        "chỉ lộ ra khi chạy model thật: thứ tự bias khi nhiều filter tính cùng lúc, một lượt tính không có activation khác 0 làm "
        "mất mọi lượt sau, MaxPool bị cấu hình thành average pooling.",
        "Phần cứng sau các bản sửa vẫn đạt 250 MHz sau place & route (Vivado, ZU7EV), 0 cảnh báo nghiêm trọng; mốc 12 ca đo chu kỳ "
        "không đổi qua các bản sửa cuối; hồi quy RTL 162 test: 157 đạt, 5 lỗi đã biết, 0 thất bại mới.",
    ])

    # ---------------------------------------------------------------- 2
    doc.add_heading("2. Mục tiêu và bối cảnh", level=1)
    para(doc, "OpenEye là bộ tăng tốc suy luận mạng nơ-ron tích chập mã nguồn mở (INT8, dataflow kiểu Eyeriss v2, mảng PE tham số "
              "hoá), giao tiếp với bộ nhớ ngoài qua AXI DMA. Dự án phát triển nhánh riêng dựa trên mã nguồn gốc (Learning-Chips-Lab/OpenEye), "
              "theo dõi định kỳ thay đổi của nhóm gốc. Mục tiêu: tối ưu theo băng thông (lưu lượng DMA) và độ trễ.")
    para(doc, "Giai đoạn 0 (đo lường, kiểm tra tính đúng) đã đi tới mốc quan trọng: một mạng đã huấn luyện chạy đúng trên phần cứng với "
              "ảnh thật. Từ đây các tối ưu có thể được đo trên dữ liệu thật thay vì chỉ dữ liệu ngẫu nhiên.")

    # ---------------------------------------------------------------- 3
    doc.add_heading("3. Công việc đã hoàn thành (16/10 – 31/10)", level=1)
    doc.add_heading("3.1. Chạy cả model trên chip và đo theo từng layer", level=2)
    bullets(doc, [
        "Chạy nối tiếp nhiều layer trên chip (kết quả layer trước ghi ngược vào bộ đệm làm input layer sau, pooling trên chip), kiểm "
        "tra bộ đệm sau mỗi layer.",
        "Profiler theo từng layer: mỗi layer có bảng pha riêng (nạp cấu hình, iact, weight, bias, bảng lượng tử, chuyển đổi iact, tính "
        "toán, ghi ngược, pooling, đọc ra) và số word DMA. Đã đưa vào bộ đo mốc 12 ca (3 ca model).",
        "Đo lại Bảng 3 của bài báo OpenEye (mạng 7 layer trên 16 cấu hình phần cứng) bằng profiler, theo từng layer và từng pha.",
        "Đệm input 1 channel thành 2 channel bằng Python (tránh lỗi #17 của RTL), chi phí +472 chu kỳ ở Conv1.",
    ])
    doc.add_heading("3.2. Đường model thật của toolchain", level=2)
    para(doc, "Trước đây đường model thật của toolchain chỉ mang cấu trúc model: weight bị nhân 127 lần nữa (tràn int8), bias bị thay bằng "
              "hằng số, Dense và input ngẫu nhiên, không có hệ số lượng tử và ReLU. Toolchain đã được mở rộng (không thêm công cụ song "
              "song) để chở model đã huấn luyện tới RTL:")
    doc.add_picture(FIG_FLOW, width=Cm(16.5))
    caption(doc, "Hình 1. Đường đi của model đã huấn luyện qua toolchain tới RTL và cách kiểm chứng.")
    table(doc, ["Bước", "Thay đổi"], [
        ["onnx2model", "Lượng tử tĩnh int8 với ảnh hiệu chỉnh (ONNX Runtime quantize_static): zero point 0 cho activation và weight, "
         "một scale weight mỗi layer; đọc QLinearConv / QGemm; tính mant/shift của bộ lượng tử từ scale; đặt đúng tên MaxPool"],
        ["LayerParameters", "Đọc cờ ReLU của model (act_min = 0 cho bộ kẹp)"],
        ["DRAMContents", "Giữ nguyên weight int8 và bias int32 của model; hoán vị weight Dense theo thứ tự input của phần cứng"],
        ["Testbench", "Nạp checkpoint đã huấn luyện, ảnh test MNIST thật, báo chữ số mà bộ tăng tốc đoán"],
    ], widths=[3.4, 13.2])
    para(doc, "Vì sao lượng tử tĩnh: mã nguồn gốc dùng lượng tử động, trong đó scale và zero point của activation được tính lúc chạy từ "
              "min/max của từng tensor (activation uint8, zero point khác 0, đổi theo từng ảnh). Phần cứng chỉ có một hệ số cố định mỗi "
              "layer, nạp trước khi chạy, activation int8 có dấu với zero point 0, và lượng tử từng output ngay khi ghi ngược nên không "
              "thể biết min/max của cả tensor. Ngoài ra model int8 động mà đường cũ tạo ra ONNX Runtime không chạy được, kernel Conv bị "
              "chuyển vị sai chiều và Dense bị đảo kích thước.")
    table(doc, ["Model (1000 ảnh test đầu)", "Độ chính xác"], [
        ["Float (PyTorch xuất ONNX)", "99,5 %"],
        ["ONNX Runtime, lượng tử động (weight uint8)", "99,5 %"],
        ["ONNX Runtime, lượng tử tĩnh int8 (đường mới)", "99,4 %"],
        ["Tham chiếu của toolchain = phép tính của phần cứng", "99,5 %"],
        ["RTL, ảnh test 0–7", "8 / 8 đúng, khớp từng bit"],
    ], widths=[10.0, 6.6], align_right=(1,))

    doc.add_heading("3.3. Kẹp int8 và ReLU gộp trong bộ lượng tử (RTL)", level=2)
    para(doc, "Bộ lượng tử trước đây lấy 8 bit thấp của kết quả, nên giá trị vượt int8 bị quấn vòng (ví dụ 130 thành −126) và không "
              "có hàm kích hoạt (af_cluster.v không được dùng). Nay bộ lượng tử kẹp về [act_min, 127]: act_min = −128 là bão hoà int8 "
              "thường, act_min = 0 là ReLU gộp, chọn theo từng layer qua một trường cấu hình. Không thêm word DMA, không đổi máy trạng "
              "thái chính; +1,3 % LUT, vẫn 250 MHz. Mô phỏng độ chính xác: không kẹp int8 thì mạng MNIST còn khoảng 9 %.")

    doc.add_heading("3.4. Các lỗi đã sửa", level=2)
    table(doc, ["Lỗi", "Biểu hiện", "Nguyên nhân và cách sửa"], [
        ["#14 (RTL)", "results_ready gán vừa blocking vừa non-blocking; Yosys và Vivado tổng hợp khác nhau",
         "Tách phần tổ hợp ra khỏi khối FSM"],
        ["#19 (RTL)", "Dense K > 512 input sai", "Bộ đếm vị trí 8 bit tràn ở cặp 256; mở rộng 12 bit. Dense tới K = 4032 đúng"],
        ["#22 (Python)", "Weight Conv bằng 0 thật làm sai cả layer", "Mã hoá weight nén của mapper khác RTL; bộ mã hoá mới"],
        ["#26 (RTL, 1 dòng)", "Dense nối tiếp Dense không ghi ngược", "Bộ ghi ngược chỉ cho Conv; thêm nhánh Dense"],
        ["#25 (RTL)", "NUM_GLB_PSUM = 2 ghi ngược Conv sai", "Nhóm ghi ngược luôn 4 channel/pixel"],
        ["#30 (RTL)", "Tràn int8 bị quấn vòng, không có ReLU", "Kẹp int8 và ReLU gộp (mục 3.3)"],
        ["#34 (Python)", "MaxPool của model thật thành average pooling", "Đặt tên layer max_pooling2d"],
        ["#32 (Python)", "Bias của cặp filter bị đổi chỗ khi tính 2 filter cùng lúc",
         "RTL nạp word bias từ cluster cuối; gửi nhóm filter theo thứ tự ngược"],
        ["#31 (RTL, gồm #33, #35)", "Một lượt tính không có activation khác 0 làm mất mọi lượt sau; 86 % ảnh MNIST bị",
         "PE rỗng vẫn đi trọn giao thức một lượt (trạng thái EMPTY_PASS); 0 chu kỳ thay đổi"],
        ["#17 (Python)", "Input 1 channel rộng hơn một lượt sai", "Đệm thành 2 channel"],
        ["#5", "23 test Dense báo sai", "Báo động giả của bộ kiểm tra trong testbench"],
    ], widths=[3.0, 6.4, 7.2])
    para(doc, "Ngoài ra đã lấy 3 commit sửa lỗi của nhóm gốc và kiểm tra rằng nhóm gốc cũng có lỗi #31 (chạy trên mã của họ). Mọi thay "
              "đổi RTL chỉ thực hiện sau khi được đồng ý, kèm test hồi quy, so mốc chu kỳ, lint và Vivado.")

    # ---------------------------------------------------------------- 4
    doc.add_heading("4. Kết quả đo chu kỳ của các model", level=1)
    para(doc, "Cấu hình: 2×2 cluster, mỗi cluster 12 PE (48 PE), psum 20 bit, DMA 64 bit, bảng lượng tử 64 entry, bộ nhớ lý tưởng (một "
              "word DMA mỗi chu kỳ). Thời gian quy đổi ở 250 MHz, tần số đạt được sau place & route.")
    para(doc, "Cấu hình các ca model:").runs[0].bold = True
    table(doc, ["Ca", "Model", "Weight, bias, lượng tử", "Input"], [
        ["Mạng MNIST nhỏ (16 filter), ngẫu nhiên (model_mnist16_c2)",
         "Mạng thử của mã nguồn gốc (LAYER=MNIST): Conv 3×3 2→16 (28×28), MaxPool, Conv 16→16 (14×14), MaxPool, Conv 16→16 (7×7), "
         "Dense 784→10",
         "Model Keras khởi tạo ngẫu nhiên, chưa huấn luyện: weight = floor(127·w), bias Conv = 1, bias Dense = 1, 2, 3, …; "
         "mant/shift mặc định 1/7 (Conv), 1/9 (Dense); không ReLU",
         "28×28×2 số nguyên ngẫu nhiên −32…31, mọi số 0 thay bằng ±1; seed 1"],
        ["Kiến trúc MNIST thật, ngẫu nhiên, 2 ch / 1 ch (model_mnist_real_c2 / _c1)",
         "Kiến trúc của models/mnist_conv_net.py (LAYER=MNIST_REAL): Conv 1→32 (28×28), MaxPool, Conv 32→64 (14×14), MaxPool, "
         "Conv 64→64 (7×7), Dense 3136→10",
         "Như trên (ngẫu nhiên, chưa huấn luyện)",
         "_c2: 2 channel ngẫu nhiên; _c1: 1 channel ngẫu nhiên (đúng model thật), đệm thêm 1 channel 0 (lỗi #17)"],
        ["Đã huấn luyện, ảnh test i",
         "SimpleMNISTConvNet (cùng kiến trúc), checkpoint mnist_unquantized_model.pth: huấn luyện 5 epoch, 99,35 % trên tập test",
         "Lượng tử tĩnh int8 qua onnx2model: weight int8 và bias int32 thật, mant/shift tính từ scale, ReLU sau 3 Conv",
         "Ảnh thứ i (đếm từ 0) của tập test MNIST 10.000 ảnh; chữ số trong ngoặc là nhãn của ảnh (ảnh 7 là chữ số 9); "
         "chuẩn hoá như lúc huấn luyện, lượng tử int8, đệm 1 channel 0"],
    ], widths=[3.6, 4.6, 4.6, 3.8])
    para(doc, "Phần cứng chung: 2×2 cluster, mỗi cluster 4×3 PE (48 PE, mỗi PE 2 phép nhân/chu kỳ), NUM_GLB_IACT = 1, psum 20 bit, "
              "DMA 64 bit, bảng lượng tử 64 entry (32 với mạng nhỏ), bộ nhớ lý tưởng; µs quy đổi ở 250 MHz.")
    doc.add_heading("4.1. Tổng chu kỳ theo layer", level=2)
    rows = []
    for label, m in models:
        rows.append([label] + [fmt(l["total_cycles"]) for l in m["layers"]] + [fmt(m["total_cycles"]), us(m["total_cycles"])])
    table(doc, ["Ca", "Conv1", "Pool1", "Conv2", "Pool2", "Conv3", "Dense", "Tổng", "µs"], rows,
          widths=[4.6, 1.5, 1.3, 1.6, 1.3, 1.5, 1.4, 1.7, 1.0], align_right=range(1, 9))
    doc.add_picture(FIG_MODELS, width=Cm(16.5))
    caption(doc, "Hình 2. Số chu kỳ của các ca model, chia theo layer (bộ nhớ lý tưởng).")
    bullets(doc, [
        "Mạng MNIST nhỏ (16 filter mỗi Conv, Dense 784 → 10) là mạng thử của mã nguồn gốc; ba ca dưới là kiến trúc của model "
        "thật (32/64/64 filter, Dense 3136 → 10).",
        "Với model đã huấn luyện, chỉ Conv2, Conv3 và Dense nhanh hơn so với dữ liệu ngẫu nhiên; Conv1, Pool1, Pool2 giống hệt "
        "vì không phụ thuộc dữ liệu (input sau chuẩn hoá không có số 0).",
        "Conv2 (14×14, 32 → 64) chiếm khoảng một nửa thời gian của cả mạng.",
    ])

    doc.add_heading("4.2. Pha theo layer (model đã huấn luyện, ảnh test 0)", level=2)
    rows = []
    for i, l in enumerate(trained0["layers"]):
        rows.append([LAYER_LABELS[i]] + [fmt(phase_cycles(l, parts)) for _, parts in PHASE_GROUPS] + [fmt(l["total_cycles"])])
    total = [fmt(phase_cycles(trained0, parts)) for _, parts in PHASE_GROUPS]
    rows.append(["Cả mạng"] + total + [fmt(trained0["total_cycles"])])
    shares = [phase_cycles(trained0, parts) / trained0["total_cycles"] for _, parts in PHASE_GROUPS]
    rows.append(["Tỉ lệ"] + [pct(s, 1) for s in shares] + ["100 %"])
    table(doc, ["Layer", "Tính toán", "Nạp weight", "Nạp bias", "Ghi ngược", "Chuyển đổi iact", "Pooling", "Khác", "Tổng"], rows,
          widths=[1.8, 1.9, 1.9, 1.8, 1.8, 2.0, 1.7, 1.5, 1.9], align_right=range(1, 9))
    doc.add_picture(FIG_PHASES, width=Cm(16.5))
    caption(doc, "Hình 3. Số chu kỳ của từng layer theo pha, model đã huấn luyện, ảnh test 0.")
    bullets(doc, [
        f"Ngoài tính toán, phần lớn thời gian là nạp weight ({pct(shares[1], 1)}) và nạp bias ({pct(shares[2], 1)}). Bias của "
        "Conv1 là 14.336 word DMA cho 32 giá trị khác nhau: đúng chỗ tối ưu 'gửi bias theo filter' có lợi nhất.",
        "Pha nạp weight, bias, chuyển đổi, ghi ngược và pooling chỉ phụ thuộc kích thước layer, giống hệt với dữ liệu ngẫu nhiên.",
    ])

    doc.add_heading("4.3. Bỏ qua số 0 với dữ liệu thật", level=2)
    doc.add_picture(FIG_ZEROS, width=Cm(15.0))
    caption(doc, "Hình 4. Chu kỳ pha tính toán: dữ liệu ngẫu nhiên và model đã huấn luyện (ảnh test 0); dưới mỗi layer là tỉ lệ "
                 "số 0 trong input (ngẫu nhiên / ảnh thật).")
    para(doc, "Với model đã huấn luyện, sau ReLU và pooling input của Conv2 có khoảng 44 % số 0, Conv3 82–91 %, Dense 74–78 % "
              "(ảnh 0–7); với dữ liệu ngẫu nhiên chỉ 6–11 % (giá trị nhỏ sau phép dịch, không có ReLU). Thiết kế bỏ qua các activation "
              "bằng 0 (phụ lục A), nhưng mức giảm chu kỳ nhỏ hơn nhiều so với chênh lệch tỉ lệ số 0 (Conv3: 11 % → 87 % số 0, chỉ "
              "giảm 27 %): mỗi lượt tính vẫn tốn một phần cố định (bắt tay lượt, đưa psum vào và đọc psum ra) và phải chờ PE bận nhất. "
              "Đây là một hướng tối ưu độ trễ mới thấy được nhờ chạy dữ liệu thật.")

    doc.add_heading("4.4. Mạng của bài báo OpenEye trên 16 cấu hình", level=2)
    doc.add_picture(FIG_PAPER, width=Cm(15.0))
    caption(doc, "Hình 5. Tổng chu kỳ của mạng 7 layer trong Bảng 3 của bài báo theo số cluster và kích thước mảng PE "
                 "(dữ liệu ngẫu nhiên, đo 26/10).")
    n_pass = sum(1 for v in runs.values() if v[1].startswith("PASS"))
    fails = ", ".join(f"PE {x}×{yy}" for (cr, x, yy), (_, st) in sorted(runs.items()) if not st.startswith("PASS"))
    para(doc, f"{n_pass}/16 cấu hình cho kết quả đúng; với 1 hàng cluster còn sai {fails} (lỗi #28 với PE 2×…, #19b với PE 4×3; "
              "chưa sửa). Khi tăng số "
              "cluster, pha tính toán giảm gần tỉ lệ, nhưng nạp bias không giảm và nạp weight còn tăng (weight được gửi tới nhiều cluster "
              "hơn), nên với 8 hàng cluster phần nạp dữ liệu chiếm 42–53 % thời gian của Conv1 và đường cong chững lại.")

    # ---------------------------------------------------------------- 5
    doc.add_heading("5. Phần cứng (Vivado 2024.2, ZU7EV, 4 ns)", level=1)
    table(doc, ["Chỉ số (sau place & route)", "Báo cáo 15/10", "Hiện tại (31/10)", "Ghi chú"], [
        ["Slack setup ở 4 ns", "+0,048 ns", "+0,074 ns", "Đạt 250 MHz"],
        ["LUT", "64.162", "60.840", "FSM của PE được Vivado mã hoá one-hot"],
        ["Flip-flop", "39.192", "39.796", "+10 FF mỗi PE (bản sửa #31)"],
        ["Block RAM tile / URAM / DSP", "192 / 8 / 4", "192 / 8 / 4", "Không đổi"],
        ["Lỗi / cảnh báo nghiêm trọng", "0 / 0", "0 / 0", ""],
    ], widths=[4.6, 3.0, 3.2, 5.8], align_right=(1, 2))
    para(doc, "Kẹp int8 (#30) thêm 1,3 % LUT ở 8 bộ lượng tử. Bản sửa #31 thêm 1 trạng thái và một bộ đếm 5 bit mỗi PE; LUT giảm vì với "
              "10 trạng thái Vivado tự chuyển cách mã hoá FSM của PE sang one-hot, không phải nhờ bản sửa.")

    # ---------------------------------------------------------------- 6
    doc.add_heading("6. Kiểm thử", level=1)
    table(doc, ["Bộ test", "Kết quả"], [
        ["Test RTL (Conv, MNIST, GEMM/Dense, Dense nối tiếp, NUM_GLB_PSUM = 2, kẹp int8, pooling, mạng, lượt rỗng, model thật)",
         "162 test: 157 đạt, 5 lỗi đã biết (đánh dấu xfail), 0 thất bại"],
        ["Unit test Python", "290 đạt, 11 lỗi có từ trước trong một file test của mã nguồn gốc"],
        ["Mốc chu kỳ 12 ca", "0 chu kỳ, 0 word DMA thay đổi sau bản sửa #31 và #32"],
        ["Lint Verilator theo baseline", "0 cảnh báo mới"],
        ["Model đã huấn luyện trên RTL, ảnh test 0–7", "8 / 8 khớp từng bit, đoán đúng chữ số"],
        ["Tham chiếu toolchain so với ONNX Runtime", "Chỉ lệch do làm tròn; cùng chữ số trên 100 / 100 ảnh"],
    ], widths=[9.0, 7.6])
    para(doc, "Bài học: dữ liệu test ngẫu nhiên của mã nguồn gốc không có số 0 (mọi 0 bị thay bằng ±1) và cho mọi filter cùng bias, nên "
              "đã che 3 lỗi phần cứng. Các test mới dùng số 0 thật, bias khác nhau và model thật.")

    # ---------------------------------------------------------------- 7
    doc.add_heading("7. Lỗi còn mở", level=1)
    table(doc, ["Lỗi", "Ảnh hưởng"], [
        ["#12: bộ lượng tử dùng hệ số của filter 0 cho mọi filter", "Chưa lượng tử theo từng filter; model hiện dùng một scale mỗi layer"],
        ["Mantissa của bộ lượng tử bị cắt 8 bit", "Sai số làm tròn nhỏ; đã tính vào tham chiếu"],
        ["#29: Dense 3136 → ≥ 32 output sai", "Chặn model có lớp FC lớn (MNIST hiện tại dùng 3136 → 10, không bị)"],
        ["#19b, #21, #28: Dense N = 32 ở 1 hàng cluster, Dense > 32 output, Conv 1 hàng cluster với NUM_GLB_PSUM = 2",
         "Một số cấu hình phần cứng / kích thước layer"],
        ["#9: ảnh rộng 7, ô đệm khác 0 khi đọc thẳng ra", "Chỉ kiểm tra luồng DMA; giá trị đúng, không ảnh hưởng khi nối layer"],
        ["#23, #27, #18b, #7", "Conv thưa dạng bàn cờ, pooling 4×4, 40/48 filter, 3 channel"],
        ["Lượt tính có dữ liệu nhưng ngắn hơn 16 chu kỳ", "Về lý thuyết còn race ở điều khiển; chưa gặp với dữ liệu nào"],
    ], widths=[8.0, 8.6])

    # ---------------------------------------------------------------- 8
    doc.add_heading("8. Định hướng tiếp theo", level=1)
    table(doc, ["#", "Việc", "Lý do và kết quả mong đợi"], [
        ["1", "Đưa model đã huấn luyện vào bộ đo mốc", "Đo mọi tối ưu trên dữ liệu thật (chỉ Python)"],
        ["2", "Gửi bias theo filter (Giai đoạn 1.1)", "Nạp bias 10,6 % độ trễ cả mạng, 43 % của Conv1, hiệu suất bus khoảng 1 %"],
        ["3", "Giảm phần cố định của mỗi lượt tính", "Bỏ qua số 0 chỉ được 9–27 % dù 44–87 % input bằng 0 (mục 4.3)"],
        ["4", "Đóng gói weight (Giai đoạn 1.3)", "Nạp weight 17,8 % độ trễ cả mạng"],
        ["5", "Sửa #12 (lượng tử theo filter) và #29", "Độ chính xác cao hơn với scale theo filter; model có FC lớn"],
        ["6", "Chạy chồng pha nạp và tính toán (Giai đoạn 2)", "Che độ trễ nạp sau khi đã giảm lưu lượng"],
        ["7", "Đo trên board thật", "Hiệu chỉnh mô hình bộ nhớ, độ trễ có cả DDR và phần mềm"],
    ], widths=[0.8, 5.4, 10.4])

    # ---------------------------------------------------------------- 9
    doc.add_heading("9. Hạn chế", level=1)
    bullets(doc, [
        "Số chu kỳ lấy từ mô phỏng RTL với bộ nhớ lý tưởng; trên board, DDR, AXI DMA và phần mềm điều khiển sẽ thêm độ trễ.",
        "Tổng hợp là out-of-context (chỉ khối bộ tăng tốc); 250 MHz là tần số của khối này.",
        "Model thật mới được kiểm trên RTL với 8 ảnh (mỗi ảnh mô phỏng 10–20 phút); độ chính xác 99,5 % trên 1000 ảnh là của tham "
        "chiếu phần mềm, vốn khớp từng bit với RTL ở mọi ảnh đã chạy.",
    ])

    # ---------------------------------------------------------------- appendices
    doc.add_heading("Phụ lục A. Bộ tăng tốc bỏ qua activation bằng 0 như thế nào", level=1)
    bullets(doc, [
        "Mỗi PE nhận activation của lượt tính qua bộ nạp iact (data_pipeline_iact.v). Bộ nạp xét từng giá trị 8 bit: chỉ giá trị "
        "khác 0 được ghi vào SPad dữ liệu iact, kèm một nhãn vị trí 4 bit (giá trị đó ở vị trí nào trong cửa sổ của PE); SPad địa "
        "chỉ ghi số giá trị khác 0 cộng dồn theo nhóm. Giá trị 0 không được lưu và không bao giờ đi vào bộ nhân.",
        "Khi tính (trạng thái CALCULATING của PE.v), PE chỉ duyệt các activation khác 0. Với mỗi activation, nhãn vị trí chọn dãy "
        "weight tương ứng (SPad địa chỉ weight cho điểm bắt đầu), rồi mỗi chu kỳ nhân activation đó với weight của 2 filter "
        "(PARALLEL_MACS = 2) và cộng vào psum của 2 filter trong SPad psum. Weight bằng 0 cũng được nén và bỏ qua.",
        "Số chu kỳ nhân của một PE trong một lượt ≈ Σ (activation khác 0) ⌈số weight khác 0 của nó / 2⌉ ≈ N_khác0 × F / 2, với F là "
        "số filter PE giữ trong lượt (16 ở các Conv của model này). Ví dụ Conv3: mỗi PE giữ 12 activation và 192 weight; không có "
        "số 0 thì 12 × 16 / 2 = 96 chu kỳ nhân, với 87 % số 0 trung bình chỉ khoảng 12.",
        "Thời gian một lượt = chu kỳ nhân của PE bận nhất trong 48 PE (các PE chạy đồng bộ theo lượt) + phần cố định (nạp lượt, chờ "
        "16 chu kỳ, đưa psum vào và đọc psum ra theo số filter). Đo được (ngẫu nhiên → ảnh thật): Conv2 200 → 182 chu kỳ/lượt (448 lượt), "
        "Conv3 195 → 142 (224 lượt). Phần cố định và PE bận nhất làm lợi ích nhỏ hơn tỉ lệ số 0.",
        "Lượt mà không PE nào có activation khác 0 trước đây làm mất mọi lượt sau (lỗi #31); nay PE rỗng đi trạng thái EMPTY_PASS.",
    ])
    doc.add_heading("Phụ lục B. Bộ lượng tử: mant, shift, offset và ReLU", level=1)
    para(doc, "Sau mỗi Conv/Dense, psum 20 bit (bias + Σ weight·activation, số nguyên) được đổi về activation int8 của layer sau ngay "
              "trên chip (quantization_unit.v, 8 bộ chạy song song):")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("q = kẹp( ⌊ mant × (psum + offset) / 2^shift ⌋ , act_min , 127 )").bold = True
    bullets(doc, [
        "Toán học: giá trị thực r = s·q (zero point 0). Psum = Σ w_q·x_q + b_q, với b_q = round(b / (s_x·s_w)), biểu diễn y ≈ s_x·s_w·psum. "
        "Activation int8 của layer sau: q_y = y / s_y = M·psum với M = s_x·s_w / s_y. Phần cứng xấp xỉ M bằng mant / 2^shift.",
        "Python (onnx2model.hardware_multiplier) chọn shift lớn nhất sao cho mant = round(M·2^shift) vẫn nhỏ hơn 256 (RTL chỉ "
        "dùng 8 bit thấp của trường mant 25 bit), nên mant luôn ở 128…255 và sai số tương đối ≤ 0,4 %. Ví dụ Conv1: s_x = 0,0222164, "
        "s_w = 0,00358664, s_y = 0,0241571 → M = 0,00329851 → 0,00329851 × 2^16 = 216,2 → mant 216, shift 16 (2^17 cho 432, quá 8 "
        "bit); sai số 0,08 %. Conv2 190/17, Conv3 211/17, Dense 130/17.",
        "LayerParameters ghi [mant, shift] cho từng filter; conv_mapper.write_quant_and_offset đóng gói mỗi filter thành 40 bit "
        "(offset 8 | shift 7 | mant 25) và gửi xuống ở pha nạp bảng lượng tử (20–40 chu kỳ mỗi layer). Do lỗi #12 phần cứng dùng "
        "hệ số của filter 0 cho mọi filter, nên model dùng một scale weight cho cả layer.",
        "Kẹp và ReLU: act_min là −128 (bão hoà int8) hoặc 0 khi layer có ReLU. Vì zero point bằng 0, ReLU sau lượng tử chính là "
        "max(q, 0), nên chỉ cần đặt cận dưới của phép kẹp bằng 0, không cần khối kích hoạt riêng. Python gửi act_min + 128 trong "
        "một trường 8 bit của từ trạng thái; RTL lấy lại act_min bằng cách đảo bit cao.",
        "Offset: số 8 bit có dấu cho từng filter, cộng vào psum trước phép nhân. Trong RTL nó được ghi là “zero-point offset”, "
        "nhưng zero point của output phải cộng sau phép nhân (q = z + M·psum); cộng trước thì cần offset = z / M, ví dụ −128 / 0,0033 "
        "≈ −39.000, không vừa 8 bit. Zero point của input cần −z_x·Σw cho mỗi filter, cũng không vừa và đã có chỗ trong bias. Làm "
        "tròn gần nhất cần 2^(shift−1) / mant = 32.768 / 216 ≈ 152, cũng không vừa. Vì vậy toolchain (cả mã nguồn gốc) luôn gửi "
        "offset = 0: lượng tử đối xứng (zero point 0) không cần nó, và bias đã nằm sẵn trong psum. Nó chỉ có thể dùng như một hiệu "
        "chỉnh nhỏ (±127 đơn vị psum) theo filter.",
    ])

    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
