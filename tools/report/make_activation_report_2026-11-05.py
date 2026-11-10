#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Build the fourth Word progress report (Vietnamese, 2026-11-05): the activation functions of the project.

Numbers come from the measured profiles doc/perf/activation_2026-11-04_rowO/ (the four trained MNIST models on test
image 0 after the fixes of bugs #38, #37, #17 and #39), from the step documents doc/experiments/2026-11-02_activation*.md
(accuracy on the 10,000 test images, ONNX Runtime comparison, RTL verification) and from doc/synth/ (Vivado).
Formatting helpers are shared with make_progress_report.py (the 2026-10-10 report).

    ~/tools/docenv/bin/python tools/report/make_activation_report_2026-11-05.py
Output: doc/reports/2026-11-05_HamKichHoat/BaoCao_HamKichHoat_OpenEye_2026-11-05.docx (+ four figure PNGs next to it)
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
ACT = os.path.join(REPO, "doc", "perf", "activation_2026-11-04_rowO")
OUT_DIR = os.path.join(REPO, "doc", "reports", "2026-11-05_HamKichHoat")   # one folder per report (2026-11-10)
DATE = "05/11/2026"
OUT = os.path.join(OUT_DIR, "BaoCao_HamKichHoat_OpenEye_2026-11-05.docx")
FIG_PATH = os.path.join(OUT_DIR, "duong_ham_kich_hoat_2026-11-05.png")
FIG_TOTAL = os.path.join(OUT_DIR, "chu_ky_ham_kich_hoat_2026-11-05.png")
FIG_ZEROS = os.path.join(OUT_DIR, "so_0_ham_kich_hoat_2026-11-05.png")
FIG_COMPUTE = os.path.join(OUT_DIR, "tinh_toan_ham_kich_hoat_2026-11-05.png")
CLOCK_NS = 4.0     # 250 MHz, met after place and route (doc/synth/2026-11-04_route4ns_rowO_zu7ev)

# Chart tokens: the validated reference palette of the dataviz method (as in the 2026-10-31 report); one fixed
# categorical slot per activation, the same in every figure
SURFACE, INK, INK_2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e8e7e2", "#d6d5cf"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
ACTS = [("relu", "ReLU"), ("leaky_relu", "Leaky ReLU"), ("silu", "SiLU"), ("hardswish", "hard-swish")]
COMPUTE_LAYERS = [(0, "Conv1"), (2, "Conv2"), (4, "Conv3"), (5, "Dense")]

# Regression and unit tests of the state committed with this report (README_FI.md, section 3c and the log)
REGRESSION = "189 test RTL: 185 PASS + 4 xfail đã biết, 0 FAIL"
UNIT_TESTS = "403 unit test Python pass (11 lỗi cũ của test_dense_output.py, không liên quan)"


def load(path):
    with open(path) as f:
        return json.load(f)


def us(cycles):
    return f"{cycles * CLOCK_NS / 1000:.1f}".replace(".", ",")


def pct(x, digits=1, sign=False):
    s = f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"
    return s.replace(".", ",") + " %"


def zeros(layer):
    inp = layer["info"]["input"]
    return 100.0 * inp["zeros"] / inp["values"]


def compute(layer):
    return layer["phases"].get("compute", {}).get("cycles", 0)


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


def caption(doc, text):
    cap = doc.add_paragraph(text)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True


# ---------------------------------------------------------------- figures
def figure_path():
    """The write-back path of one lane: three quantizer stages and the table, with what configures them."""
    fig, ax = new_figure(9.6, 3.6)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")
    hw, cfg, new = ("#fdece4", "#eb6834"), ("#e9f1fb", "#2a78d6"), ("#e3f5ee", "#1baf7a")
    boxes = [
        (0.5, 20, 12.5, 14, cfg, "psum 20 bit\ntừ bộ đệm psum\n(4 lane / chu kỳ)"),
        (15.5, 20, 16, 14, new, "Tầng 1\nsum = psum + offset\nLeaky: dấu chọn\n(mant, shift) / (neg_…)"),
        (34, 20, 15, 14, new, "Tầng 2 (1 DSP)\nmant × sum\n+ 2^(shift−1)\nkhi làm tròn"),
        (51.5, 20, 15, 14, hw, "Tầng 3\n>> shift, kẹp\n[act_min, 127]\nReLU: act_min = 0"),
        (69, 20, 14, 14, new, "Bảng 256 ô\nLUTRAM, đọc\nkhông clock\n(SiLU, hard-swish)"),
        (85.5, 20, 14, 14, cfg, "Bộ đệm iact\ncủa layer sau\n(int8)"),
        (15.5, 1.5, 34, 11, cfg, "5 trường trong word trạng thái của layer:\nact_mode, act_round, act_neg_mant,\n"
                                 "act_neg_shift, act_keep_table (0 word thêm)"),
        (57, 1.5, 26, 11, cfg, "GET_ACTIVATION (trạng thái 15):\n32 word DMA mỗi layer có bảng\n(0 khi giữ bảng cũ)"),
    ]
    for x, y, w, h, (fill, edge), text in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2", linewidth=1.2,
                                    facecolor=fill, edgecolor=edge))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.4, color=INK)
    for x0, x1 in ((13.3, 15.2), (31.8, 33.7), (49.3, 51.2), (66.8, 68.7), (83.3, 85.2)):
        ax.add_patch(FancyArrowPatch((x0, 27), (x1, 27), arrowstyle="-|>", mutation_scale=10, color=INK_2, linewidth=1.2))
    for (xa, ya), (xb, yb) in (((26, 12.8), (23.5, 19.7)), ((40, 12.8), (41.5, 19.7)), ((76, 12.8), (76, 19.7))):
        ax.add_patch(FancyArrowPatch((xa, ya), (xb, yb), arrowstyle="-|>", mutation_scale=9, color=INK_2, linewidth=1.0))
    ax.text(50, 38.2, "3 chu kỳ trễ như trước khi có hàm kích hoạt, vẫn 4 giá trị mỗi chu kỳ", ha="center", fontsize=8,
            color=INK_2)
    for i, (label, (fill, edge)) in enumerate((("có từ trước (kẹp, ReLU #30)", hw), ("thêm cho hàm kích hoạt", new),
                                               ("dữ liệu, cấu hình", cfg))):
        ax.add_patch(FancyBboxPatch((86, 9.5 - 4 * i), 2.2, 2.2, boxstyle="round,pad=0.15", facecolor=fill, edgecolor=edge))
        ax.text(89.2, 10.6 - 4 * i, label, fontsize=6.8, color=INK_2, va="center")
    fig.tight_layout()
    fig.savefig(FIG_PATH, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_total(runs):
    """Horizontal bars: total cycles of the trained model, image 0, per activation."""
    fig, ax = new_figure(9.0, 2.9)
    style_axes(ax)
    base = runs["relu"]["total_cycles"]
    y = list(range(len(ACTS)))[::-1]
    top = max(r["total_cycles"] for r in runs.values())
    for yi, (key, label), color in zip(y, ACTS, SLOTS):
        t = runs[key]["total_cycles"]
        ax.barh(yi, t, height=0.6, color=color, edgecolor=SURFACE, linewidth=1.5)
        note = f"{fmt(t)} chu kỳ, {us(t)} µs" + ("" if key == "relu" else f"   +{fmt(t - base)} ({pct((t - base) / base * 100, 2, True)})")
        ax.text(t + top * 0.01, yi, note, va="center", ha="left", fontsize=8, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([label for _, label in ACTS], color=INK)
    ax.set_xlim(0, top * 1.45)
    ax.set_xlabel("Tổng số chu kỳ của mạng MNIST đã huấn luyện, ảnh test 0 (µs ở 250 MHz)", color=INK_2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(int(v))))
    fig.tight_layout()
    fig.savefig(FIG_TOTAL, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_zeros(runs):
    """Grouped bars: share of zeros in the inputs of Conv2, Conv3 and Dense, per activation."""
    fig, ax = new_figure(8.6, 3.5)
    style_axes(ax, "y")
    layers = [(2, "Input của Conv2"), (4, "Input của Conv3"), (5, "Input của Dense")]
    w = 0.2
    for a, ((key, label), color) in enumerate(zip(ACTS, SLOTS)):
        xs = [i + (a - 1.5) * (w + 0.02) for i in range(len(layers))]
        vals = [zeros(runs[key]["layers"][li]) for li, _ in layers]
        ax.bar(xs, vals, w, color=color, label=label, edgecolor=SURFACE, linewidth=1.0)
        for x, v in zip(xs, vals):
            ax.text(x, v + 1, f"{v:.0f}", ha="center", va="bottom", fontsize=7.2, color=INK)
    ax.set_xticks(range(len(layers)))
    ax.set_xticklabels([name for _, name in layers], color=INK)
    ax.set_ylabel("Số 0 trong input (%)", color=INK_2)
    ax.set_ylim(0, 100)
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.01), frameon=False, fontsize=8, handlelength=1.2)
    fig.tight_layout()
    fig.savefig(FIG_ZEROS, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_compute(runs):
    """Grouped bars: change of the compute cycles of each layer against ReLU (Leaky ReLU, SiLU, hard-swish)."""
    fig, ax = new_figure(8.6, 3.3)
    style_axes(ax, "y")
    w = 0.25
    for a, ((key, label), color) in enumerate(zip(ACTS[1:], SLOTS[1:])):
        xs = [i + (a - 1) * (w + 0.02) for i in range(len(COMPUTE_LAYERS))]
        vals = []
        for li, _ in COMPUTE_LAYERS:
            r, o = compute(runs["relu"]["layers"][li]), compute(runs[key]["layers"][li])
            vals.append((o - r) / r * 100)
        ax.bar(xs, vals, w, color=color, label=label, edgecolor=SURFACE, linewidth=1.0)
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.8, f"{v:+.0f}".replace("+0", "0"), ha="center", va="bottom", fontsize=7.2, color=INK)
    ax.set_xticks(range(len(COMPUTE_LAYERS)))
    labels = []
    for li, name in COMPUTE_LAYERS:
        labels.append(f"{name}\nReLU: {fmt(compute(runs['relu']['layers'][li]))} chu kỳ")
    ax.set_xticklabels(labels, color=INK)
    ax.set_ylabel("Chu kỳ tính toán so với ReLU (%)", color=INK_2)
    ax.set_ylim(0, 48)
    ax.legend(ncol=3, loc="upper left", frameon=False, fontsize=8, handlelength=1.2)
    fig.tight_layout()
    fig.savefig(FIG_COMPUTE, facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------- report
def build():
    runs = {key: load(os.path.join(ACT, f"trained_{key}_img0.json")) for key, _ in ACTS}
    base = runs["relu"]["total_cycles"]
    extra = {key: runs[key]["total_cycles"] - base for key, _ in ACTS}
    os.makedirs(OUT_DIR, exist_ok=True)
    figure_path()
    figure_total(runs)
    figure_zeros(runs)
    figure_compute(runs)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    style.font.size = Pt(12)
    for section in doc.sections:
        section.left_margin = section.right_margin = Cm(2.2)
        section.top_margin = section.bottom_margin = Cm(2.0)

    title = doc.add_heading("BÁO CÁO TIẾN ĐỘ (LẦN 4)", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Hàm kích hoạt trên bộ tăng tốc OpenEye: Leaky ReLU, SiLU, hard-swish")
    r.bold = True
    r.font.size = Pt(14)
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(f"Người thực hiện: Nguyễn Ngọc Trường Phi\nNgày: {DATE} (báo cáo trước: 31/10/2026)\n"
                 "Mã nguồn: github.com/DevFi-23/OpenEye (nhánh dev, private)").font.size = Pt(11)

    p = {key: extra[key] / base * 100 for key, _ in ACTS}
    # ---------------------------------------------------------------- 1
    doc.add_heading("1. Tóm tắt", level=1)
    bullets(doc, [
        "Bộ tăng tốc nay có 4 hàm kích hoạt: ReLU (kẹp int8, từ báo cáo trước), Leaky ReLU (hai hệ số theo dấu), SiLU và "
        "hard-swish (bảng tra 256 ô). Với mỗi hàm, một mạng MNIST đã huấn luyện chạy trọn trên RTL qua đường model thật của "
        "toolchain, khớp từng bit với tham chiếu sau mọi layer và đoán đúng chữ số của các ảnh test đã chạy.",
        "Độ chính xác int8 theo đúng phép tính của phần cứng, trên 10.000 ảnh test: 99,25–99,36 %, cách model float tối đa "
        "0,04 điểm. Sai khác so với ONNX Runtime còn 1–4 đơn vị int8 nhờ bit làm tròn.",
        "Khối hàm kích hoạt không thêm chu kỳ nào cho mỗi giá trị: nó chen vào 3 tầng sẵn có của bộ lượng tử. Hàm dạng bảng "
        "tốn 32 word DMA (32 chu kỳ) mỗi layer để nạp bảng, Leaky ReLU tốn 0.",
        f"Chi phí đo được trên cả mạng (ảnh test 0): Leaky ReLU {pct(p['leaky_relu'], 2, True)}, SiLU "
        f"{pct(p['silu'], 2, True)}, hard-swish {pct(p['hardswish'], 2, True)} so với ReLU. Gần như toàn bộ là pha tính "
        "toán: ReLU biến mọi số âm thành 0 nên bộ tăng tốc bỏ qua được 44–87 % input, các hàm mới giữ lại số âm.",
        "Phần cứng: khoảng +550 LUT (+0,9 %), +60 FF, không thêm DSP, BRAM hay URAM; vẫn đạt 250 MHz sau place & route.",
        f"Song song: sửa thêm các lỗi giúp Bảng 3 của bài báo đạt 16/16 cấu hình, sửa lỗi cắt mantissa (#38), lấy 2 bản sửa của "
        f"upstream (#37, #17), sửa #39 và thêm 2 phép kiểm tra cho #39b, #40. Hiện tại: {REGRESSION}.",
    ])

    # ---------------------------------------------------------------- 2
    doc.add_heading("2. Bối cảnh và mục tiêu", level=1)
    para(doc, "Các mạng hiện đại cho thiết bị nhúng (MobileNetV3, EfficientNet, YOLO) dùng Leaky ReLU, SiLU hoặc hard-swish "
              "thay cho ReLU. RTL gốc của OpenEye có module af_cluster.v nhưng không nối vào đường dữ liệu; trong báo cáo trước, "
              "ReLU mới được thêm vào bộ lượng tử dưới dạng kẹp int8 (lỗi #30). Mục tiêu của phần việc này:")
    bullets(doc, [
        "Chạy các hàm kích hoạt phổ biến trên chip, khớp từng bit với tham chiếu Python của toolchain, và gần ONNX Runtime "
        "(công cụ dùng để lượng tử model) trong giới hạn làm tròn.",
        "Không thêm chu kỳ cho mỗi giá trị và không làm chậm các model chỉ dùng ReLU (0 chu kỳ thay đổi ở 12 ca mốc).",
        "Đo đúng cái giá của mỗi hàm bằng profiler, để biết chi phí nằm ở đâu và tối ưu tiếp theo hướng nào.",
    ])
    para(doc, "Công việc chia 4 bước: A, toolchain và tham chiếu (chỉ Python); B, RTL (sau khi bản thiết kế được duyệt); "
              "C, profiler; D, đo trên model đã huấn luyện.")

    # ---------------------------------------------------------------- 3
    doc.add_heading("3. Cách mỗi hàm được tính", level=1)
    para(doc, "psum = Σ x·w + bias là số nguyên 20 bit; giá trị thật = psum × s_in × s_w. s_out là scale đầu ra của layer, "
              "s_next là scale input của layer tính kế tiếp; cả hai lấy từ lượng tử tĩnh của ONNX Runtime. Mỗi hệ số thực M "
              "được đưa xuống phần cứng dưới dạng (mant 24 bit, shift) với mant / 2^shift ≈ M.")
    table(doc, ["Hàm", "Python tính (onnx2model)", "Gửi xuống chip mỗi layer", "Phần cứng làm"], [
        ["ReLU", "(mant, shift) = M(s_in·s_w / s_out); làm tròn xuống", "Word lượng tử; act_min = 0; act_mode 0",
         "q = kẹp(⌊mant·psum / 2^shift⌋, 0, 127)"],
        ["Leaky ReLU (α = 0,1)", "(mant, shift) = M(s_in·s_w / s_next) cho psum ≥ 0; (neg_mant, neg_shift) = "
         "M(α·s_in·s_w / s_next) cho psum < 0; làm tròn gần nhất", "Word lượng tử; act_mode 1, act_neg_mant (8 bit), "
         "act_neg_shift (7 bit), act_round 1", "Tầng 1 chọn cặp hệ số theo dấu; q = kẹp(⌊(mant·psum + 2^(shift−1)) / "
         "2^shift⌋, −128, 127)"],
        ["SiLU", "(mant, shift) = M(s_in·s_w / s_out); bảng T[i] = làm_tròn(f((i − 128)·s_out) / s_next), f(x) = x·σ(x)",
         "Word lượng tử; act_mode 2, act_round 1; 32 word bảng (DMA 64 bit)", "q như trên (một cặp), ra = T[q + 128]"],
        ["hard-swish", "Như SiLU, f(x) = x·clip(x + 3, 0, 6) / 6", "Như SiLU", "Như SiLU"],
    ], widths=[2.4, 5.6, 4.4, 4.2])
    para(doc, "Vì sao Leaky ReLU không cần bảng: bộ lượng tử vốn đã nhân psum với một hệ số. Leaky ReLU là hai đoạn thẳng, nên chỉ "
              "cần thêm cặp hệ số thứ hai cho psum âm; cặp này nằm trong các bit còn trống của word cấu hình, không tốn word DMA "
              "nào. SiLU và hard-swish là đường cong (sigmoid cần hàm mũ và phép chia). Tính trực tiếp sẽ cần nhiều DSP và nhiều "
              "tầng; nhưng sau lượng tử input chỉ có 256 giá trị int8, nên tra một bảng 256 ô cho kết quả chính xác và rẻ hơn.")
    doc.add_picture(FIG_PATH, width=Cm(16.5))
    caption(doc, "Hình 1. Đường ghi ngược của một lane: 3 tầng của bộ lượng tử và bảng tra, cùng nguồn cấu hình của chúng.")
    para(doc, "Ví dụ với psum = −5000 ở Conv1 của các model đã huấn luyện:", bold_prefix=None)
    table(doc, ["", "Tầng 1", "Tầng 2", "Tầng 3", "Bảng", "Ra"], [
        ["ReLU", "(14.166.994, 32), không làm tròn", "14.166.994·(−5000) = −70.834.970.000", ">>32 = −16,49 → −17 → kẹp 0", "—", "0"],
        ["Leaky ReLU", "dấu âm → (215, 19), làm tròn", "−1.075.000 + 2^18 = −812.856", ">>19 = −1,55 → −2", "—", "−2"],
        ["SiLU", "(9.899.939, 32), làm tròn", "−49.499.695.000 + 2^31", ">>32 = −11,03 → −12", "ô 116 = −8", "−8"],
    ], widths=[2.0, 3.6, 4.2, 3.6, 1.8, 1.0], align_right=(5,))

    # ---------------------------------------------------------------- 4
    doc.add_heading("4. Bước A: toolchain và tham chiếu (chỉ Python)", level=1)
    para(doc, "Toolchain của dự án đi theo đường PyTorch → ONNX (opset 18) → lượng tử tĩnh int8 của ONNX Runtime → onnx2model → "
              "LayerParameters → stream DMA. Bước A dạy toolchain nhận ra từng hàm trong đồ thị ONNX đã lượng tử và tính sẵn các "
              "tham số phần cứng; tham chiếu của testbench tính đúng như phần cứng sẽ tính, và chính nó là đặc tả cho RTL.")
    table(doc, ["Hàm (PyTorch)", "ONNX Runtime tạo ra sau Conv", "Điều toolchain phải xử lý"], [
        ["F.relu", "Dequantize → Relu (float) → MaxPool → Quantize", "Scale đầu ra = scale của Conv: một hệ số là đủ"],
        ["nn.LeakyReLU(0.1)", "QLinearLeakyRelu (com.microsoft)", "Phải đổi scale sang scale input của layer tính kế tiếp"],
        ["nn.SiLU", "QLinearSigmoid + QLinearMul(x, σ(x))", "Như trên; ONNX không suy ra được shape sau toán tử com.microsoft"],
        ["nn.Hardswish", "Dequantize → HardSigmoid (float) → Quantize → QLinearMul", "ONNX Runtime không có HardSwish lượng tử"],
    ], widths=[3.2, 6.4, 7.0])
    bullets(doc, [
        "onnx2model: find_activation nhận diện các mẫu trên, finish_activations tính hệ số theo scale của layer tính kế tiếp "
        "(gộp luôn bước lượng tử lại của Flatten trước Dense), activation_table tính bảng, fill_missing_shapes bù shape.",
        "LayerParameters: activation_config với act_mode none / relu / leaky / table, độ dốc âm, bảng, bit làm tròn.",
        "Tham chiếu (simple_layer_operations.batchnorm_output) tính cả 3 chế độ và tuỳ chọn làm tròn; đường cũ (ReLU, làm tròn "
        "xuống) giữ nguyên từng dòng.",
        "Ba biến thể model MNIST được huấn luyện theo đúng cách của model gốc (models/train_mnist.py, 5 epoch): float 99,33 % "
        "(Leaky ReLU), 99,29 % (SiLU), 99,36 % (hard-swish); ReLU gốc 99,35 %.",
    ])
    para(doc, "Độ chính xác và tỉ lệ số 0 trên 10.000 ảnh test (int8 phần cứng = đúng phép tính của phần cứng, mô hình numpy đã "
              "kiểm tra trùng với tham chiếu testbench):")
    table(doc, ["Hàm", "Làm tròn", "Float", "ONNX Runtime int8", "Phần cứng int8", "Số 0 input Conv2 / Conv3 / Dense"], [
        ["ReLU", "xuống (mặc định)", "99,35 %", "99,33 %", "99,35 %", "44 / 83 / 78 %"],
        ["Leaky ReLU", "gần nhất (chọn)", "99,33 %", "99,34 %", "99,34 %", "23 / 15 / 17 %"],
        ["SiLU", "gần nhất (chọn)", "99,29 %", "99,29 %", "99,27 %", "10 / 7 / 7 %"],
        ["hard-swish", "gần nhất (chọn)", "99,36 %", "99,29 %", "99,35 %", "7 / 14 / 13 %"],
    ], widths=[2.4, 2.8, 1.8, 2.8, 2.6, 4.2], align_right=(2, 3, 4))
    bullets(doc, [
        "Độ chính xác không phải vấn đề: mọi hàm cách model float tối đa 0,04 điểm.",
        "Cần bit làm tròn: làm tròn xuống làm mỗi layer lệch khoảng −0,5 LSB, lệch tích luỹ theo độ sâu (tới 7 đơn vị so với "
        "ONNX Runtime ở Conv3). Làm tròn gần nhất giữ sai khác trong 1–4 đơn vị. Với Leaky ReLU, làm tròn xuống còn biến mọi số âm nhỏ "
        "thành −1 (chỉ 1–3 % số 0); làm tròn gần nhất giữ 15–23 %. ReLU giữ làm tròn xuống: làm tròn không tăng độ chính xác mà "
        "tốn thêm 0,5 % chu kỳ.",
        "Bảng là một núm chỉnh độ trễ: đặt các ô ±1 của bảng về 0 (band1) đưa số 0 của SiLU / hard-swish lên 20–27 % mà không "
        "giảm độ chính xác (99,30 / 99,32 %), lấy lại khoảng 2 % chu kỳ. Đưa cả phần âm về 0 (neg0) gần như trả lại độ thưa "
        "của ReLU nhưng mất 0,6–0,9 điểm.",
        "31 unit test (test_activation.py): tham chiếu so với công thức số nguyên, bảng so với hàm float, toolchain trên các "
        "biến thể, các model đã huấn luyện so với ONNX Runtime.",
    ])

    # ---------------------------------------------------------------- 5
    doc.add_heading("5. Bước B: phần cứng (RTL)", level=1)
    para(doc, "Bản thiết kế được viết và duyệt trước khi sửa RTL (doc/experiments/2026-11-02_activation_rtl_design.md). Hàm kích "
              "hoạt nằm trong bộ lượng tử của pha ghi ngược: sau khi một layer tính xong, psum được lượng tử về int8 và ghi vào "
              "bộ đệm iact làm input cho layer sau. Đây là chỗ duy nhất mọi giá trị đều đi qua.")
    table(doc, ["File", "Thay đổi"], [
        ["quantization_unit.v", "Tầng 1 lấy dấu của tổng và chọn cặp hệ số của độ dốc âm (Leaky); tầng 2 cộng 2^(shift−1) khi "
         "làm tròn bằng bộ cộng có sẵn của DSP (A·B + C); tầng 3 không đổi. Khi hai tuỳ chọn bằng 0, mọi thanh ghi giữ giá trị như cũ"],
        ["activation_table.v (mới)", "Bảng 256 ô chia 8 bank LUTRAM (ở DMA 64 bit): mỗi word DMA ghi 8 ô trong 1 chu kỳ; đọc "
         "không đồng bộ ở chỉ số = giá trị + 128. Một bảng cho mỗi lane ghi ngược (4 lane)"],
        ["psum_pipeline.v", "Cổng cấu hình hàm kích hoạt tới mọi bộ lượng tử; lane ra = bảng ở chế độ 2"],
        ["OpenEye_FPGA.v", "Trạng thái GET_ACTIVATION = 15 (mã còn trống) nạp bảng sau GET_QUANTIZE, giữ ready_dma_o cao nên "
         "stream không có bong bóng; dây trace act_capture cho profiler"],
        ["regmap.yaml", "5 trường mới đặt vào các bit trống: số word trạng thái giữ nguyên 28 / 14 / 7 ở DMA 32 / 64 / 128 bit"],
    ], widths=[4.0, 12.6])
    para(doc, "Vì sao không tốn thêm chu kỳ: mỗi tầng của bộ lượng tử là một thanh ghi; mỗi chu kỳ 4 psum mới vào tầng 1 trong khi "
              "các psum trước ở tầng 2 và tầng 3. Bộ chọn hệ số của Leaky nằm trước thanh ghi tầng 1, phép cộng làm tròn dùng bộ "
              "cộng của DSP ở tầng 2, tra bảng là đọc LUTRAM không clock trước thanh ghi nhận của FSM chính. Vẫn 3 chu kỳ trễ và "
              "4 giá trị mỗi chu kỳ như trước, nên pha ghi ngược giữ nguyên số chu kỳ; điều kiện duy nhất là logic thêm phải kịp "
              "trong một chu kỳ 4 ns, và Vivado xác nhận là kịp.")
    table(doc, ["Kiểm chứng", "Kết quả"], [
        ["Testbench bộ lượng tử (10 khối act_min × leaky × làm tròn, psum ngẫu nhiên, mọi shift)",
         "2/2 PASS (psum 20 và 32 bit), mỗi lần 30.470 đầu ra khớp mô hình Python"],
        ["Testbench activation_table (nạp, đọc đủ 256 ô, nạp lại, ghi khi we = 0)", "3/3 PASS ở word 32 / 64 / 128 bit"],
        ["test_activation_rtl.py: model ngẫu nhiên với Leaky, bảng ngẫu nhiên / SiLU / hard-swish, làm tròn, giữ bảng; Conv, "
         "Conv → Pool → Conv, chuỗi Dense, MLP, NUM_GLB_PSUM = 2, DMA 32 bit, mạng 7 layer của bài báo", "12/12 PASS"],
        ["Đối chứng âm: sửa riêng stream (báo RTL chế độ 0, bảng lệch 1 ô, tắt làm tròn)", "6/6 FAIL như phải thế"],
        ["Model đã huấn luyện Leaky ReLU / SiLU / hard-swish, ảnh test 0 và 1", "6/6 PASS, trọn mạng khớp từng bit, lớp đoán = nhãn"],
        ["12 ca mốc chu kỳ (chỉ ReLU hoặc không hàm kích hoạt)", "0 chu kỳ, 0 word DMA thay đổi"],
    ], widths=[10.4, 6.2])
    table(doc, ["Tài nguyên (Vivado 2024.2, ZU7EV, 4 ns)", "Trước bước B", "Sau bước B", "Thay đổi"], [
        ["CLB LUT sau route", "60.641", "61.419", "+778 (khoảng +550 do bước B)"],
        ["trong đó LUT dùng làm bộ nhớ (4 bảng)", "2.279", "2.535", "+256"],
        ["FF", "", "", "khoảng +60"],
        ["DSP / BRAM / URAM", "", "", "0 / 0 / 0"],
        ["WNS sau route ở 4 ns", "+0,020 ns", "+0,045 ns", "vẫn đạt 250 MHz"],
    ], widths=[6.2, 2.8, 2.8, 4.8], align_right=(1, 2))
    para(doc, "Các bộ lượng tử tốn hơn ước tính (300 LUT): hằng số làm tròn 2^(shift−1), với shift tới 45, giữ lại mọi bit của tích "
              "46 bit, trong khi trước đó Vivado bỏ được các bit cao. Thu hẹp dải shift của bit làm tròn (toolchain chỉ dùng 13–20) "
              "sẽ lấy lại một phần; chưa làm. Mốc phần cứng hiện tại, sau các bản sửa sau đó: 59.389 LUT, 39.398 FF, 188 BRAM, "
              "12 URAM, 4 DSP, WNS +0,077 ns.")

    # ---------------------------------------------------------------- 6
    doc.add_heading("6. Bước C và D: đo bằng profiler", level=1)
    para(doc, "Profiler được mở rộng để đo đúng phần của hàm kích hoạt: pha load_act (nạp bảng, trạng thái 15), số chu kỳ ghi "
              "ngược có hàm kích hoạt (từ dây act_capture, nằm trong pha writeback chứ không phải chu kỳ thêm), và tỉ lệ số 0 / "
              "số âm trong input của từng layer (từ tham chiếu, vốn trùng từng bit với RTL). Chi phí của một hàm được đo bằng hiệu "
              "giữa cùng một model với ReLU và với hàm đó, theo từng pha và từng layer.")
    rows = []
    for key, label in ACTS:
        run = runs[key]
        ph = run["phases"]
        ls = run["layers"]
        rows.append([label, fmt(run["total_cycles"]), "" if key == "relu" else f"+{fmt(extra[key])} ({pct(p[key], 2, True)})",
                     fmt(ph.get("load_act", {}).get("cycles", 0)), fmt(ph["compute"]["cycles"]), fmt(ph["writeback"]["cycles"]),
                     " / ".join(f"{zeros(ls[i]):.0f}" for i in (2, 4, 5)) + " %", us(run["total_cycles"])])
    table(doc, ["Hàm", "Tổng chu kỳ", "So với ReLU", "load_act", "compute", "writeback", "Số 0 input Conv2 / Conv3 / Dense",
                "µs ở 250 MHz"], rows, widths=[2.2, 1.9, 2.6, 1.5, 1.9, 1.8, 3.0, 1.7], align_right=(1, 2, 3, 4, 5, 7))
    para(doc, "Mạng MNIST đã huấn luyện (Conv 28×28×1 → 32, MaxPool, Conv 14×14×32 → 64, MaxPool, Conv 7×7×64 → 64, Dense 3136 → 10), "
              "ảnh test 0, nền tảng 2×2 cluster, DMA 64 bit, bộ nhớ lý tưởng; số đo sau các bản sửa #38, #37, #17, #39 "
              "(doc/perf/activation_2026-11-04_rowO). Cả 4 lần chạy PASS, khớp từng bit, bộ tăng tốc đoán đúng số 7.")
    doc.add_picture(FIG_TOTAL, width=Cm(16.0))
    caption(doc, "Hình 2. Tổng chu kỳ của mạng với mỗi hàm kích hoạt (ảnh test 0).")
    doc.add_picture(FIG_ZEROS, width=Cm(15.0))
    caption(doc, "Hình 3. Tỉ lệ số 0 trong input của các layer sau hàm kích hoạt: số 0 là thứ bộ tăng tốc bỏ qua được.")
    doc.add_picture(FIG_COMPUTE, width=Cm(15.0))
    caption(doc, "Hình 4. Chu kỳ pha tính toán của từng layer so với ReLU. Conv1 nhận ảnh gốc nên không đổi.")
    bullets(doc, [
        "Khối hàm kích hoạt gần như miễn phí về thời gian: pha ghi ngược giống hệt nhau ở cả 4 hàm (11.924 chu kỳ); bảng tốn 32 "
        "chu kỳ cho mỗi layer có bảng, tức 96 chu kỳ cho 3 layer (0,04 % của mạng); Leaky ReLU 0.",
        "Toàn bộ phần còn lại là pha tính toán, vì bộ tăng tốc bỏ qua ít số 0 hơn. Conv3 chịu nặng nhất (+36–38 %): với ReLU, input "
        "của nó có 87 % số 0, với các hàm khác chỉ 7–15 %.",
        "Bảng SiLU chỉ có đúng một ô bằng 0 (x = 0), mọi giá trị âm thành số âm khác 0; bảng hard-swish đưa x ≤ −3 về 0 nên giữ "
        "khoảng 14 % số 0 ở input Conv3; ReLU đưa mọi số âm về 0.",
        "Chi phí thuộc về hàm, không phải weight: chạy weight của model ReLU với từng hàm khác cho +9,1 / +10,0 / +9,9 %, cách "
        "các model tự huấn luyện tối đa 0,4 điểm.",
        "Bước A dự đoán +7,4 / +9,2 / +9,0 % (trung bình 10.000 ảnh, tuyến tính theo số 0); đo thật trên ảnh 0 được +8,7 / +9,7 / "
        "+9,8 %.",
    ])

    # ---------------------------------------------------------------- 7
    doc.add_heading("7. Các thay đổi sau đó có liên quan tới hàm kích hoạt", level=1)
    table(doc, ["Thay đổi", "Ảnh hưởng tới hàm kích hoạt"], [
        ["Sửa #38: OpenEye_FPGA.v cắt mantissa của bảng lượng tử còn 8 bit; nay hệ số 24 bit (bằng đúng scale float32 của "
         "ONNX Runtime), độ dốc âm của Leaky giữ 8 bit",
         "Các layer gần ONNX Runtime hơn (sai khác lớn nhất 3 → 2, 2 → 1, 3 → 1 ở vài layer); chu kỳ chỉ đổi −6 … +1 ở Dense"],
        ["Hàng O (lấy #37, #17 từ upstream) và sửa #39: Conv1 chạy với đúng 1 channel input thay vì đệm lên 2",
         "−360 chu kỳ cho cả 4 model (ReLU 218.924 → 218.564), toàn bộ ở Conv1; chi phí tương đối của các hàm không đổi"],
    ], widths=[8.6, 8.0])

    # ---------------------------------------------------------------- 8
    doc.add_heading("8. Các việc khác đã làm từ báo cáo trước", level=1)
    table(doc, ["Việc", "Kết quả"], [
        ["Sửa #28, #29, #36 (điều kiện ready ở CLUSTER_ROWS = 1, tràn bộ đệm weight, độ rộng đọc ra Dense)",
         "Bảng 3 của bài báo đạt 16/16 cấu hình lần đầu tiên"],
        ["Sửa #38 (mantissa 8 bit)", "Hệ số lượng tử chính xác tới < 1e−7; test mới test_quant_mantissa.py"],
        ["Hàng O: lấy bản sửa #37 (trường bộ đệm iact 13 bit) và #17 (đường 1 channel) từ upstream 36395dd",
         "Conv1 MNIST không cần đệm channel nữa; LUT −1.547, FF −525, BRAM 192 → 188, WNS +0,077 ns"],
        ["Phát hiện và sửa #39 (Python: thiếu bộ weight khi 1 channel và nhiều lượt)", "Layer 1 channel từ 2 lượt weight trở lên tính đúng"],
        ["Phép kiểm tra check_wght_sets (#39b) và check_full_passes (#40)",
         "Toolchain từ chối layer sẽ tính sai hoặc mất output, thay vì cho kết quả sai không báo lỗi; không chặn layer nào đang chạy được"],
        ["Rà soát upstream: 36395dd, b10db82", "Upstream vẫn có #39; lỗi treo của b10db82 do thiếu bản sửa #22 (mã hoá weight 0)"],
        ["Kiểm thử hiện tại", f"{REGRESSION}; {UNIT_TESTS}"],
    ], widths=[8.6, 8.0])

    # ---------------------------------------------------------------- 9
    doc.add_heading("9. Định hướng tiếp theo", level=1)
    table(doc, ["#", "Việc", "Lý do và kết quả mong đợi"], [
        ["1", "Bảng band1 cho SiLU / hard-swish (ô ±1 → 0, chọn theo layer)", "Bước A: số 0 lên 20–27 %, lấy lại khoảng 2 % "
         "chu kỳ, không mất độ chính xác; chỉ sửa toolchain"],
        ["2", "Chia đều số psum mỗi PE giữa các lượt weight (#40, hướng 2)", "Bỏ phần tính thừa trên ô filter đệm (25 % ở 16 + 8) "
         "và cho phép số filter như 24, 48, 96"],
        ["3", "Thu hẹp dải shift của bit làm tròn", "Lấy lại một phần LUT của bước B (bộ lượng tử)"],
        ["4", "Thử hàm kích hoạt trên mạng lớn hơn (nhiều layer, có hàm sau Dense)", "Kiểm tra chi phí khi tỉ lệ số 0 của ReLU khác MNIST"],
    ], widths=[0.8, 6.4, 9.4])

    # ---------------------------------------------------------------- 10
    doc.add_heading("10. Hạn chế", level=1)
    bullets(doc, [
        "Số chu kỳ lấy từ mô phỏng RTL với bộ nhớ lý tưởng; trên FPGA tổng độ trễ lớn hơn do DDR, AXI DMA và phần mềm điều khiển.",
        "Chi phí đo trên một ảnh (ảnh test 0) và một mạng (MNIST); vì chi phí nằm ở số 0 của dữ liệu, nó sẽ khác với ảnh và mạng khác. "
        "Độ chính xác thì tính trên 10.000 ảnh.",
        "Bảng chỉ biểu diễn được hàm một biến từ int8 sang int8; các phép cần hai tensor, ví dụ phép nhân từng phần tử của khối "
        "squeeze-and-excitation trong MobileNetV3, chưa được hỗ trợ. Module af_cluster.v của mã nguồn gốc vẫn không được dùng.",
    ])

    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
