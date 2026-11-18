#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Build the sixth Word progress report (weekly, Vietnamese, 2026-11-18). Main topic: choosing sparse / dense per layer,
checked against the user's four-phase plan (profiling, cost model, RTL, verification): an assessment of the phases,
where the project stands, the cycles of every phase in the measured cases, why the direction is worth it, the work of
the week and the next steps.

Inputs (all measured, nothing typed in except the Vivado / Yosys resource numbers, quoted with their source):
  doc/perf/activation_2026-11-18/trained_<act>_img0_<sparse|dense>.json      trained MNIST, step 0
  doc/perf/wght_layout_2026-11-18_mnist/trained_<act>_img0_sparse.json        the same, dense weight layout (step 2)
  doc/perf/paper_table3_2026-11-18{,_dense,_relu_sparse,_wlayout,_relu_wlayout}/paper_<cfg>.json   Table 2 network
  doc/perf/layer_sweep_2026-11-18_{sparse,dense}/<shape>_z<zeros>_<cfg>.json  one layer, step 1c
  doc/perf/wght_layout_2026-11-18/<case>.json                                 one layer, both weight layouts, step 2

    ~/tools/docenv/bin/python tools/report/make_progress_report_2026-11-18.py
Output: doc/reports/2026-11-18_TienDo/BaoCao_TienDo_OpenEye_2026-11-18.docx (+ three figure PNGs next to it)
"""

import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_progress_report as base_report  # noqa: E402
from make_progress_report import bullets, fmt, para, table  # noqa: E402

REPO = base_report.REPO
PERF = os.path.join(REPO, "doc", "perf")
OUT_DIR = os.path.join(REPO, "doc", "reports", "2026-11-18_TienDo")
OUT = os.path.join(OUT_DIR, "BaoCao_TienDo_OpenEye_2026-11-18.docx")
FIG_PHASES = os.path.join(OUT_DIR, "chu_ky_theo_pha_2026-11-18.png")
FIG_SWEEP = os.path.join(OUT_DIR, "nguong_so_0_2026-11-18.png")
FIG_WZERO = os.path.join(OUT_DIR, "chi_phi_weight_0_2026-11-18.png")
DATE = "18/11/2026"
CLOCK_NS = 4.0     # 250 MHz, met after place and route (doc/synth/2026-11-18_route4ns_default_zu7ev)

# Chart tokens: the validated reference palette of the dataviz method, as in the earlier reports; one fixed
# categorical slot per option (sparse, dense, P1) and per phase group in every figure
SURFACE, INK, INK_2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e8e7e2", "#d6d5cf"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
OPTIONS = [("sparse", "Sparse (hôm nay)"), ("dense", "Dense HW"), ("p1", "P1 (weight theo layer)")]
OPT_COLOR = {"sparse": SLOTS[0], "dense": SLOTS[1], "p1": SLOTS[2]}
ACTS = [("relu", "ReLU"), ("leaky_relu", "Leaky ReLU"), ("silu", "SiLU"), ("hardswish", "hard-swish")]
PHASE_ORDER = ["load_config", "load_iact", "load_wght", "load_bias", "load_quant", "load_act", "convert_iact",
               "compute", "writeback", "pooling", "readout"]
PHASE_VI = {"load_config": "nạp cấu hình", "load_iact": "nạp activation", "load_wght": "nạp weight",
            "load_bias": "nạp bias", "load_quant": "nạp bảng lượng tử", "load_act": "nạp bảng hàm kích hoạt",
            "convert_iact": "chuyển activation", "compute": "tính toán", "writeback": "ghi ngược",
            "pooling": "pooling", "readout": "đọc kết quả"}
T2 = [("cr1_x2_y3", "CR 1 X 2"), ("cr2_x4_y3", "CR 2 X 4"), ("cr8_x4_y3", "CR 8 X 4")]


# ---------------------------------------------------------------- data
def load(path):
    with open(path) as f:
        return json.load(f)


def ph(p, name):
    return p["phases"].get(name, {}).get("cycles", 0)


def num(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",")


def pct(x, digits=1, sign=True):
    s = f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"
    return s.replace(".", ",").replace("-", "−") + " %"


def rel(a, b):
    return 100.0 * (a - b) / b


def us(cycles):
    return num(cycles * CLOCK_NS / 1000.0, 1)


def p1_of(sparse, dense, layout):
    """P1 = the sparse run with the dense weight layout (step 2, measured), load_wght of dense hardware. Whole profile and
    per layer: {"phases": {name: cycles}, "total": cycles, "layers": [...]}."""
    def one(s, d, l):
        phases = {k: v.get("cycles", 0) for k, v in l["phases"].items()}
        phases["load_wght"] = min(ph(s, "load_wght"), ph(d, "load_wght"))
        return {"phases": phases, "total": l["total_cycles"] - (ph(l, "load_wght") - phases["load_wght"])}
    whole = one(sparse, dense, layout)
    whole["layers"] = [one(s, d, l) for s, d, l in zip(sparse["layers"], dense["layers"], layout["layers"])]
    return whole


def flat(p):
    """A profile as {"phases": {name: cycles}, "total": cycles} like p1_of."""
    return {"phases": {k: v.get("cycles", 0) for k, v in p["phases"].items()}, "total": p["total_cycles"]}


def macs(layer):
    i = layer["info"]
    if i["name"].startswith("Conv"):
        stride = i.get("stride") or 1
        kx, ky = i["kernel"]
        return math.ceil(i["iact_size_x"] / stride) * math.ceil(i["iact_size_y"] / stride) * i["filters"] * \
            i["channels"] * kx * ky
    if i["name"].startswith("Dense"):
        return i["iact_size_x"] * i["filters"]
    return 0


def gops(profile, cycles):
    """Effective throughput: 2 x dense-equivalent MACs (zero products included) over the run time at 250 MHz."""
    return 2.0 * sum(macs(l) for l in profile["layers"]) / (cycles * CLOCK_NS)


def zshare(layer, key):
    d = layer["info"].get(key) or {}
    return 100.0 * d.get("zeros", 0) / d["values"] if d.get("values") else None


def data():
    mn = {}
    for act, _ in ACTS:
        s = load(os.path.join(PERF, "activation_2026-11-18", f"trained_{act}_img0_sparse.json"))
        d = load(os.path.join(PERF, "activation_2026-11-18", f"trained_{act}_img0_dense.json"))
        lay = load(os.path.join(PERF, "wght_layout_2026-11-18_mnist", f"trained_{act}_img0_sparse.json"))
        mn[act] = {"raw": (s, d, lay), "sparse": flat(s), "dense": flat(d), "p1": p1_of(s, d, lay)}
    t2 = {}
    for relu in (True, False):
        for cfg, _ in T2 + [(c, c) for c in ("cr1_x2_y4", "cr1_x4_y3", "cr1_x4_y4", "cr2_x2_y3", "cr2_x2_y4",
                                             "cr2_x4_y4", "cr4_x2_y3", "cr4_x2_y4", "cr4_x4_y3", "cr4_x4_y4",
                                             "cr8_x2_y3", "cr8_x2_y4", "cr8_x4_y4")]:
            sdir = "paper_table3_2026-11-18_relu_sparse" if relu else "paper_table3_2026-11-18"
            ldir = "paper_table3_2026-11-18_relu_wlayout" if relu else "paper_table3_2026-11-18_wlayout"
            s = load(os.path.join(PERF, sdir, f"paper_{cfg}.json"))
            d = load(os.path.join(PERF, "paper_table3_2026-11-18_dense", f"paper_{cfg}.json"))
            lay = load(os.path.join(PERF, ldir, f"paper_{cfg}.json"))
            t2[(cfg, relu)] = {"raw": (s, d, lay), "sparse": flat(s), "dense": flat(d), "p1": p1_of(s, d, lay)}
    return mn, t2


def sweep(shape, zero, cfg):
    s = load(os.path.join(PERF, "layer_sweep_2026-11-18_sparse", f"{shape}_z{zero}_{cfg}.json"))
    d = load(os.path.join(PERF, "layer_sweep_2026-11-18_dense", f"{shape}_z{zero}_{cfg}.json"))
    return s, d


# ---------------------------------------------------------------- figures
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


def figure_phases(mn, t2):
    """Small multiples: for four runs, the three options as horizontal bars split into weight load, compute and the
    other phases (identical in all options)."""
    runs = [("MNIST ReLU (CR 2 X 4)", mn["relu"]), ("MNIST SiLU (CR 2 X 4)", mn["silu"]),
            ("Mạng Bảng 2, ReLU, CR 2 X 4", t2[("cr2_x4_y3", True)]),
            ("Mạng Bảng 2, không hàm kích hoạt, CR 8 X 4", t2[("cr8_x4_y3", False)])]
    groups = [("load_wght", "nạp weight", SLOTS[0]), ("compute", "tính toán", SLOTS[1]), (None, "các pha khác", "#9b9a95")]
    fig, axes = new_figure(10.5, 5.6, 2, 2)
    for ax, (title, run) in zip(axes.flat, runs):
        style_axes(ax)
        for y, (key, label) in enumerate(OPTIONS):
            p = run[key]
            left = 0
            for gk, _, color in groups:
                if gk:
                    v = p["phases"].get(gk, 0)
                else:
                    v = p["total"] - p["phases"].get("load_wght", 0) - p["phases"].get("compute", 0)
                ax.barh(y, v, left=left, height=0.62, color=color, edgecolor=SURFACE, linewidth=1.5)
                left += v
            ax.text(left * 1.01, y, f"{fmt(p['total'])}", va="center", ha="left", fontsize=8, color=INK)
        ax.set_yticks(range(len(OPTIONS)))
        ax.set_yticklabels([lab for _, lab in OPTIONS], fontsize=8, color=INK)
        ax.invert_yaxis()
        ax.set_xlim(0, max(run[k]["total"] for k, _ in OPTIONS) * 1.18)
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt(int(v))))
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel("chu kỳ", fontsize=8, color=INK_2)
    handles = [Patch(facecolor=c, label=lab) for _, lab, c in groups]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIG_PHASES, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_sweep():
    """One layer at CR 2 X 4: whole-layer cycles relative to dense hardware against the zero share of its input."""
    shapes = [("conv2", "Conv 14×14×16 → 32"), ("conv3", "Conv 7×7×32 → 32"), ("fc", "Dense 1568 → 32")]
    zeros = ["0", "0.25", "0.5", "0.75", "0.9"]
    styles = {"sparse": ("-", "o"), "dense": ("--", "s"), "p1": (":", "^")}
    fig, axes = new_figure(10.5, 3.4, 1, 3)
    for ax, (shape, title) in zip(axes, shapes):
        style_axes(ax, "y")
        ax.spines["left"].set_visible(True)
        ax.spines["left"].set_color(AXIS)
        xs, ys = [], {k: [] for k, _ in OPTIONS}
        for z in zeros:
            s, d = sweep(shape, z, "cr2x4")
            ts, td = s["total_cycles"], d["total_cycles"]
            p1 = ts - (ph(s, "load_wght") - ph(d, "load_wght"))
            xs.append(float(z) * 100)
            ys["sparse"].append(ts / td)
            ys["dense"].append(1.0)
            ys["p1"].append(p1 / td)
        for key, label in OPTIONS:
            ls, mk = styles[key]
            ax.plot(xs, ys[key], color=OPT_COLOR[key], linestyle=ls, marker=mk, markersize=5, linewidth=2, label=label)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel("số 0 trong input của layer (%)", fontsize=8, color=INK_2)
    axes[0].set_ylabel("chu kỳ cả layer / dense HW", fontsize=8, color=INK_2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(FIG_SWEEP, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_weight_zeros():
    """Compute increase of the dense weight layout over today's zero-compressed one (same data, input without zeros)."""
    shapes = [("conv1", "Conv 28×28×1 → 16"), ("conv2", "Conv 14×14×16 → 32"), ("conv3", "Conv 7×7×32 → 32")]
    cfgs = [("cr1x2", "CR 1 X 2", SLOTS[0], "-", "o"), ("cr2x4", "CR 2 X 4", SLOTS[1], "--", "s"),
            ("cr8x4", "CR 8 X 4", SLOTS[2], ":", "^")]
    fig, axes = new_figure(10.5, 3.4, 1, 3)
    for ax, (shape, title) in zip(axes, shapes):
        style_axes(ax, "y")
        ax.spines["left"].set_visible(True)
        ax.spines["left"].set_color(AXIS)
        ax.plot([0, 50], [0, 50], color=INK_2, linewidth=1, linestyle=(0, (4, 3)), label="cận trên của bước 1 (tỉ lệ thuận)")
        for cfg, label, color, ls, mk in cfgs:
            xs, ys = [], []
            for w in ("0", "0.05", "0.25", "0.5"):
                c = load(os.path.join(PERF, "wght_layout_2026-11-18", f"{shape}_i0_w{w}_csc_{cfg}.json"))
                dpath = os.path.join(PERF, "wght_layout_2026-11-18", f"{shape}_i0_w{w}_dense_{cfg}.json")
                dl = load(dpath) if w != "0" else c
                xs.append(float(w) * 100)
                ys.append(rel(ph(dl, "compute"), ph(c, "compute")))
            ax.plot(xs, ys, color=color, linestyle=ls, marker=mk, markersize=5, linewidth=2, label=label)
        ax.set_ylim(-3, 52)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel("weight bằng 0 (%)", fontsize=8, color=INK_2)
    axes[0].set_ylabel("tính toán tăng thêm (%)", fontsize=8, color=INK_2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(FIG_WZERO, facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------- docx helpers
def caption(doc, text):
    cap = doc.add_paragraph(text)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True
    cap.runs[0].font.size = Pt(10)


def best(values):
    """Name of the smallest of {key: cycles}."""
    names = dict(OPTIONS)
    if len(set(values.values())) == 1:
        return "như nhau"
    k = min(values, key=values.get)
    return names[k].split(" (")[0]


# ---------------------------------------------------------------- report
def build():
    mn, t2 = data()
    os.makedirs(OUT_DIR, exist_ok=True)
    figure_phases(mn, t2)
    figure_sweep()
    figure_weight_zeros()

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    style.font.size = Pt(12)
    for section in doc.sections:
        section.left_margin = section.right_margin = Cm(2.2)
        section.top_margin = section.bottom_margin = Cm(2.0)

    title = doc.add_heading("BÁO CÁO TIẾN ĐỘ HẰNG TUẦN (LẦN 6)", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Chọn sparse / dense theo từng layer trên OpenEye: đánh giá 4 giai đoạn, số chu kỳ theo pha và kết quả đo")
    r.bold = True
    r.font.size = Pt(14)
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(f"Người thực hiện: Nguyễn Ngọc Trường Phi\nNgày: {DATE} (tuần 11/11 – 18/11/2026; báo cáo trước: 10/11/2026, "
                 "cập nhật 12/11/2026)\nMã nguồn: github.com/DevFi-23/OpenEye (nhánh dev, private)").font.size = Pt(11)

    m_s, m_d, m_p = (mn["relu"][k]["total"] for k in ("sparse", "dense", "p1"))
    t2_all = {relu: [rel(v["p1"]["total"], v["sparse"]["total"]) for (c, r_), v in t2.items() if r_ == relu]
              for relu in (True, False)}
    t2_vs_d = {relu: [rel(v["p1"]["total"], v["dense"]["total"]) for (c, r_), v in t2.items() if r_ == relu]
               for relu in (True, False)}
    mn_rng = [rel(mn[a]["p1"]["total"], mn[a]["sparse"]["total"]) for a, _ in ACTS]

    # ---------------------------------------------------------------- 1
    doc.add_heading("1. Tóm tắt", level=1)
    bullets(doc, [
        "Chủ đề tuần này: có nên chạy mỗi layer ở chế độ sparse hay dense hợp với nó, thay vì một chế độ cho cả mạng. Đề xuất "
        "4 giai đoạn (profiling → mô hình chi phí → RTL → kiểm chứng) được đánh giá ở mục 2: thứ tự đúng và project đang "
        "đi đúng thứ tự đó; nội dung giai đoạn 3 nên thu hẹp theo số đo.",
        "Số đo cho thấy trên chip này sparse và dense chỉ khác nhau ở 2 pha: nạp weight (dense ít hơn 33–40 % vì weight 8 bit "
        "thay vì 12 bit) và tính toán (sparse bỏ qua activation bằng 0). Mọi pha khác giống hệt từng chu kỳ.",
        f"Vì vậy phương án đáng làm là P1: giữ FSM sparse (bỏ qua activation 0), chọn định dạng weight theo layer (8 bit trần "
        f"hoặc nén như hôm nay). Đo trên RTL (mô phỏng, chưa sửa RTL): MNIST ReLU {fmt(m_s)} → {fmt(m_p)} chu kỳ "
        f"({pct(rel(m_p, m_s))}; dense HW {fmt(m_d)}), MNIST 4 hàm {pct(max(mn_rng))} đến {pct(min(mn_rng))}, mạng Bảng 2 "
        f"{pct(max(t2_all[False] + t2_all[True]))} đến {pct(min(t2_all[False] + t2_all[True]))}, khớp từng bit, chi phí ước lượng "
        "+281 LUT (+0,5 %). Chọn cả FSM theo layer (P2) chỉ thêm ≤ 0,4 % cho +8–16 % LUT: dừng.",
        "Project đang ở cuối giai đoạn 2 (đã xong bước 0, 1, 2 của kế hoạch chi tiết), sẵn sàng vào giai đoạn 3 với một thay đổi "
        "RTL nhỏ (bước 3), sẽ làm sau khi được duyệt (chưa sửa RTL trước khi có số đo và được duyệt).",
        "Các việc khác trong tuần: gửi bias một lần mỗi filter (MNIST −9,3 %, Bảng 3 −10 %), sửa lỗi #49, rà soát upstream, "
        "đo hàm kích hoạt × cách làm tròn × chế độ, nghiên cứu bão hoà. Tình trạng: hồi quy 225 test = 221 PASS + 4 xfail đã biết; "
        "Vivado đạt 250 MHz (60.113 LUT, 188 BRAM, 12 URAM, 4 DSP).",
    ])

    # ---------------------------------------------------------------- 2
    doc.add_heading("2. Bốn giai đoạn của đề xuất: đánh giá và đối chiếu", level=1)
    doc.add_heading("2.1. Đánh giá từng giai đoạn", level=2)
    para(doc, "Nhìn chung 4 giai đoạn là cách làm tốt: đo trước, mô hình hoá sau, chỉ sửa RTL khi số đo cho thấy đáng, rồi "
              "kiểm chứng và benchmark. Cách chia này tránh được việc sửa RTL quá sớm, đúng mục tiêu đặt ra. Số đo của tuần "
              "này cho phép chỉnh lại vài điểm trong nội dung:")
    table(doc, ["Giai đoạn", "Điểm tốt", "Cần chỉnh theo số đo"], [
        ["1. Profiling", "Đo số 0 của weight và activation theo layer, kích thước dữ liệu, overhead: đúng thứ cần biết trước khi "
         "quyết định.",
         "Đo theo định dạng thực của chip, không theo CSC lý thuyết: khối weight mỗi PE có độ dài cố định, nên weight 0 không "
         "làm luồng truyền ngắn đi; overhead là 4 bit cho mỗi giá trị 8 bit (+50 %). Cần đo chu kỳ từng pha (profiler), không "
         "chỉ tỉ lệ số 0. Số 0 của activation phụ thuộc ảnh: đo trên ảnh hiệu chỉnh. Hiện mới có 2 mạng (MNIST đã huấn luyện, "
         "mạng Bảng 2): cần thêm một model lớn hơn."],
        ["2. Cost model", "Ước lượng chu kỳ cả hai chế độ và ngưỡng hoà vốn: cần để chọn tự động.",
         "Không cần đếm MAC lý thuyết: chỉ nạp weight và tính toán khác nhau, nạp activation giống hệt ở hai chế độ. Ngưỡng hoà "
         "vốn phụ thuộc cấu hình cluster nhiều hơn mật độ số 0 (cùng một layer: 4 % ở CR 1 X 2, 73 % ở CR 8 X 4), nên mô hình "
         "phải có tham số cấu hình. Chi phí điều khiển PE (FSM sparse) đo được: 1–3 % khi input không có số 0."],
        ["3. RTL", "Thanh ghi cấu hình theo layer; giữ đúng địa chỉ psum khi chuyển layer.",
         "Không cần hai datapath / hai FSM: chọn FSM theo layer (P2) chỉ lợi ≤ 0,4 % sau P1, tốn +8–16 % LUT. Thứ đáng tách là "
         "định dạng weight (một bit mỗi layer), activation luôn sparse. Không cần Scheduler phần cứng: lựa chọn là tĩnh, "
         "toolchain Python quyết định lúc biên dịch (như scale lượng tử) và ghi vào thanh ghi cấu hình layer. Với P1, PE và "
         "địa chỉ psum không đổi (bước 2 đã chứng minh)."],
        ["4. Verification & Benchmark", "Cocotb so với tham chiếu, đo latency từng layer, chu kỳ nạp, throughput, so sánh "
         "Dense / Sparse / Adaptive: đúng thước đo cần có.",
         "Hạ tầng đã có (profiler theo pha / layer, đếm word DMA, so khớp từng bit, so với ONNX Runtime ở model thật). Cần thêm: "
         "throughput (GOPS) trong báo cáo (mục 4.7 là bản đầu), Vivado cho mỗi bản dựng (tài nguyên đi kèm chu kỳ)."],
    ], widths=[2.6, 5.4, 8.6])

    doc.add_heading("2.2. Đối chiếu với các bước đã làm", level=2)
    para(doc, "Kế hoạch chi tiết đang dùng (README_FI mục 2, bước 0–5) khớp với 4 giai đoạn như sau:")
    table(doc, ["Giai đoạn", "Bước của kế hoạch", "Đã làm", "Trạng thái"], [
        ["1. Profiling", "Bước 0, bước 1a–1c",
         "Mốc mới trên trạng thái đã commit; profiler ghi số 0 của input và (mới) của weight mỗi layer; MNIST 4 hàm và mạng "
         "Bảng 2 (32 lần) theo layer và pha ở cả hai chế độ; quét 4 dạng layer × 5 tỉ lệ số 0 × 3 cấu hình × 2 chế độ "
         "(120 lần)", "Xong (2 mạng)"],
        ["2. Cost model", "Bước 1d, bước 2, bước 5",
         "Mô hình chi phí từ phép quét chọn đúng chế độ 28/28 layer (26/28 khi có P1); bước 2 đo chi phí nhân weight 0 và ngưỡng "
         "hoà vốn của định dạng weight; bước 5 (đưa mô hình vào toolchain) chưa làm", "Gần xong"],
        ["3. RTL", "Bước 3 (P1), bước 4 (P2)",
         "Thiết kế xong; bước 2 chứng minh PE không cần sửa; ước lượng diện tích (Yosys) +281 LUT; P2 dừng theo số đo",
         "Chờ duyệt"],
        ["4. Verification", "Trong mỗi bước + sau bước 3",
         "Khớp từng bit ở mọi lần chạy của bước 0–2 (bước 2: 99 lần với layout mới); Vivado mốc; benchmark Dense / Sparse / "
         "Adaptive đầy đủ chờ bước 3", "Một phần"],
    ], widths=[2.6, 3.2, 8.2, 2.6])
    para(doc, "Có đi theo 4 giai đoạn không: ", None)
    bullets(doc, [
        "Có, về thứ tự và nguyên tắc: chưa sửa một dòng RTL nào cho hướng này; mọi quyết định dựa trên số đo của bước trước.",
        "Khác ở nội dung giai đoạn 3: thay vì \"Adaptive\" hai datapath, số đo thu hẹp thành chọn định dạng weight theo layer "
        "(P1), rẻ hơn 17–34 lần về LUT (281 so với 4.800–9.600 LUT) và đạt gần hết lợi ích. Giai đoạn 4 không chờ đến cuối: mỗi bước đã có kiểm chứng "
        "riêng.",
    ])
    doc.add_heading("2.3. Project đang ở giai đoạn nào", level=2)
    para(doc, "Cuối giai đoạn 2. Giai đoạn 1 xong trên 2 mạng; giai đoạn 2 đã có mô hình chi phí đúng 28/28 layer và ngưỡng hoà "
              "vốn đã đo, còn lại việc đưa mô hình vào toolchain (bước 5, Python). Bước tiếp theo là giai đoạn 3 (bước 3: sửa "
              "RTL cho P1), sẽ làm sau khi được duyệt.")

    # ---------------------------------------------------------------- 3
    doc.add_heading("3. Vì sao nên đi theo hướng này", level=1)
    bullets(doc, [
        f"Sparse không phải lúc nào cũng nhanh hơn: trên MNIST đã huấn luyện, dense HW nhanh hơn sparse với Leaky ReLU, SiLU, "
        f"hard-swish ({pct(rel(mn['leaky_relu']['dense']['total'], mn['leaky_relu']['sparse']['total']))} đến "
        f"{pct(rel(mn['hardswish']['dense']['total'], mn['hardswish']['sparse']['total']))}) vì các hàm này để lại ít số 0; "
        f"với ReLU thì sparse nhanh hơn ({pct(rel(m_d, m_s))} nếu dùng dense). Layer Dense (fully connected) luôn nhanh hơn ở "
        "dense HW kể cả khi 74–85 % input bằng 0, vì thời gian của nó gần như toàn là nạp weight.",
        "Nguyên nhân nằm ở định dạng weight, không ở việc giải mã activation: sparse gửi mỗi weight 12 bit (8 bit giá trị + 4 bit "
        "overhead), dense gửi 8 bit. P1 lấy cả hai cái lợi: weight 8 bit như dense, bỏ qua activation 0 như sparse.",
        f"Lợi lớn, chi phí nhỏ: P1 giảm {num(-max(mn_rng + t2_all[True] + t2_all[False]))}–"
        f"{num(-min(mn_rng + t2_all[True] + t2_all[False]))} % chu kỳ trên 36 lần chạy cả mạng, cho khoảng +281 LUT (+0,5 % chip), "
        "0 FF, không đổi BRAM. P1 nhanh hơn dense HW trên mọi mạng có ReLU "
        f"({pct(max(t2_vs_d[True]))} đến {pct(rel(m_p, m_d))}) và ngang dense HW khi input ít số 0.",
        "Rủi ro thấp: bước 2 đã chạy layout weight của P1 trên RTL hiện tại (chỉ ép một bit trong mô phỏng) và khớp từng bit ở "
        "99/99 lần chạy; PE, bộ đệm, router và địa chỉ psum không đổi. Phần RTL còn lại chỉ ở GET_WGHT (gom 3 word DMA mỗi hàng "
        "thay vì 5) và một bit trong thanh ghi cấu hình layer.",
        "Phương án đắt hơn đã được đo và loại: hai FSM trong mỗi PE (P2) chỉ thêm ≤ 0,4 % sau P1, tốn +8–16 % LUT. Đi theo hướng "
        "P1 tránh được việc sửa RTL lớn mà không có lợi tương xứng.",
    ])

    # ---------------------------------------------------------------- 4
    doc.add_heading("4. Số chu kỳ theo pha trong các trường hợp", level=1)
    doc.add_heading("4.1. Cách đo và các phương án", level=2)
    bullets(doc, [
        "Profiler của testbench (OPENEYE_PROFILE=1) gán mỗi chu kỳ của top-level vào một pha theo trạng thái FSM chính: nạp cấu "
        "hình, nạp activation, nạp weight, nạp bias, nạp bảng lượng tử, chuyển activation (từ bộ đệm vào cluster), tính toán, "
        "ghi ngược, pooling, đọc kết quả. Bộ nhớ lý tưởng; thời gian tính ở 250 MHz (đã đạt sau place & route).",
        "Sparse (hôm nay): bản dựng mặc định (SPARSITY_EN = 1). Dense HW: bản dựng SPARSITY_EN = 0. P1: FSM sparse với weight gửi "
        "8 bit; số liệu = lần chạy RTL với layout weight của P1 (bước 2, đo thật) cộng thời gian nạp weight của dense HW (phần "
        "GET_WGHT của bước 3, chưa có trong RTL).",
        "Mọi lần chạy đều khớp từng bit với tham chiếu Python. MNIST: model đã huấn luyện, ảnh test 0, cấu hình CR 2 X 4 "
        "(2 hàng cluster, 4 GLB psum). Mạng Bảng 2: Conv 28×28×1→16, Conv 14×14×16→32, Conv 7×7×32→32, Dense 1568→32, "
        "Dense 32→10, weight ngẫu nhiên int8.",
    ])

    doc.add_heading("4.2. MNIST ReLU, cả mạng, từng pha", level=2)
    s, d, p = mn["relu"]["sparse"], mn["relu"]["dense"], mn["relu"]["p1"]
    rows = []
    for k in PHASE_ORDER:
        vs, vd, vp = s["phases"].get(k, 0), d["phases"].get(k, 0), p["phases"].get(k, 0)
        if vs or vd or vp:
            rows.append([PHASE_VI[k], fmt(vs), fmt(vd), fmt(vp), pct(rel(vp, vs)) if vs else "—"])
    rows.append(["Tổng", fmt(s["total"]), fmt(d["total"]), fmt(p["total"]), pct(rel(p["total"], s["total"]))])
    rows.append(["Thời gian ở 250 MHz (µs)", us(s["total"]), us(d["total"]), us(p["total"]), ""])
    table(doc, ["Pha", "Sparse", "Dense HW", "P1", "P1 so với sparse"], rows, widths=[5.2, 2.8, 2.8, 2.8, 3.0],
          align_right=(1, 2, 3, 4))
    bullets(doc, [
        f"Chỉ 2 pha khác nhau. Nạp weight: dense HW và P1 {fmt(d['phases']['load_wght'])} chu kỳ, sparse "
        f"{fmt(s['phases']['load_wght'])} ({pct(rel(d['phases']['load_wght'], s['phases']['load_wght']))}). Tính toán: sparse "
        f"và P1 {fmt(s['phases']['compute'])}, dense HW {fmt(d['phases']['compute'])} "
        f"({pct(rel(d['phases']['compute'], s['phases']['compute']))}) vì không bỏ qua được activation 0.",
        "Ở P1, weight bằng 0 được nhân (không bỏ qua như hôm nay) nhưng không tốn thêm chu kỳ nào trên model này: weight 0 chỉ "
        "chiếm 0,3–1,6 % ở các layer Conv (mục 4.6).",
    ])
    doc.add_picture(FIG_PHASES, width=Cm(16.5))
    caption(doc, "Hình 1. Chu kỳ cả mạng chia theo nạp weight, tính toán và các pha khác (các pha khác giống hệt ở cả ba phương án).")

    doc.add_heading("4.3. Các mạng khác: hai pha khác nhau và tổng", level=2)
    rows = []
    entries = [(f"MNIST {lab}", mn[a]) for a, lab in ACTS] + \
              [(f"Bảng 2, {'ReLU' if relu else 'không hàm kích hoạt'}, {lab}", t2[(c, relu)])
               for relu in (True, False) for c, lab in T2]
    for name, run in entries:
        s, d, p = run["sparse"], run["dense"], run["p1"]
        other = s["total"] - s["phases"]["load_wght"] - s["phases"]["compute"]
        rows.append([name, f"{fmt(s['phases']['load_wght'])} / {fmt(d['phases']['load_wght'])}",
                     f"{fmt(s['phases']['compute'])} / {fmt(d['phases']['compute'])} / {fmt(p['phases']['compute'])}",
                     fmt(other), f"{fmt(s['total'])} / {fmt(d['total'])} / {fmt(p['total'])}",
                     pct(rel(p["total"], s["total"])), pct(rel(p["total"], d["total"]))])
    table(doc, ["Mạng", "Nạp weight: sparse / dense HW (= P1)", "Tính toán: sparse / dense HW / P1", "Các pha khác",
                "Tổng: sparse / dense HW / P1", "P1 so với sparse", "P1 so với dense HW"], rows,
          widths=[3.4, 2.6, 3.2, 1.6, 3.6, 1.6, 1.6], align_right=(1, 2, 3, 4, 5, 6))
    bullets(doc, [
        "Nạp weight luôn ít hơn 33–40 % ở dense HW / P1, ở mọi mạng và cấu hình. Tính toán: dense HW chậm hơn sparse khi có "
        "ReLU (MNIST +17,7 %, Bảng 2 CR 1 / CR 2 khoảng +9 %), gần bằng khi ít số 0 (+0,2–2,1 %), nhanh hơn 1,9 % ở Bảng 2 "
        "không hàm kích hoạt, CR 8 (chi phí riêng của FSM sparse).",
        "P1 lấy phần nạp weight của dense và phần tính toán của sparse; tính toán của P1 bằng sparse trong 0,3 % (weight 0 bị "
        "nhân). Đầy đủ 16 cấu hình mỗi loại: ReLU "
        f"{pct(max(t2_all[True]))} đến {pct(min(t2_all[True]))}, không hàm kích hoạt {pct(max(t2_all[False]))} đến "
        f"{pct(min(t2_all[False]))} so với sparse.",
    ])

    doc.add_heading("4.4. Từng layer (MNIST ReLU)", level=2)
    s_raw, d_raw, _ = mn["relu"]["raw"]
    rows = []
    for k, (ls, ld, lp) in enumerate(zip(s_raw["layers"], d_raw["layers"], mn["relu"]["p1"]["layers"])):
        i = ls["info"]
        name = {"Convolution2D": f"Conv {i['iact_size_x']}×{i['iact_size_y']}×{i['channels']}→{i['filters']}",
                "Pooling": f"Pooling {i['iact_size_x']}×{i['iact_size_y']}",
                "Dense": f"Dense {i['iact_size_x']}→{i['filters']}"}.get(i["name"], i["name"])
        z = zshare(ls, "input")
        tot = {"sparse": ls["total_cycles"], "dense": ld["total_cycles"], "p1": lp["total"]}
        rows.append([f"{k} {name}", pct(z, 1, False) if z is not None else "—",
                     f"{fmt(ph(ls, 'load_wght'))} / {fmt(ph(ld, 'load_wght'))}",
                     f"{fmt(ph(ls, 'compute'))} / {fmt(ph(ld, 'compute'))} / {fmt(lp['phases'].get('compute', 0))}",
                     f"{fmt(tot['sparse'])} / {fmt(tot['dense'])} / {fmt(tot['p1'])}", best(tot)])
    table(doc, ["Layer", "Số 0 ở input", "Nạp weight: sparse / dense HW", "Tính toán: sparse / dense HW / P1",
                "Tổng: sparse / dense HW / P1", "Nhanh nhất"], rows,
          widths=[3.6, 1.6, 2.8, 3.6, 3.6, 1.6], align_right=(1, 2, 3, 4))
    bullets(doc, [
        "Hôm nay mỗi layer có chế độ hợp riêng: Conv 1 (ảnh, 0 % số 0) và Dense nhanh hơn ở dense HW, Conv 2 và Conv 3 nhanh hơn "
        "ở sparse. Với P1, mọi layer có weight đều nhanh nhất ở P1, trừ Conv 1 (chậm hơn dense HW 1,5 %: FSM sparse trên input không có số 0). Pooling giống hệt ở cả ba phương án.",
        "Dense 3136 → 10 đổi chiều rõ nhất: hôm nay sparse 13.107 chu kỳ, dense HW 10.733; P1 9.939 (74 % input bằng 0 vẫn "
        "được bỏ qua, weight chỉ còn 8 bit).",
    ])

    doc.add_heading("4.5. Một layer theo tỉ lệ số 0 của input", level=2)
    para(doc, "Các layer của mạng Bảng 2 chạy riêng, tỉ lệ số 0 của input đặt chính xác bằng móc testbench (bước 1). Cấu hình "
              "CR 2 X 4 (như MNIST):")
    rows = []
    for shape, label, zs in (("conv1", "Conv 28×28×1→16", ["0", "0.5"]), ("conv2", "Conv 14×14×16→32", ["0", "0.5", "0.9"]),
                             ("conv3", "Conv 7×7×32→32", ["0", "0.5", "0.9"]), ("fc", "Dense 1568→32", ["0", "0.5", "0.9"])):
        for z in zs:
            s, d = sweep(shape, z, "cr2x4")
            ls, ld = s["layers"][0], d["layers"][0]
            ts, td = s["total_cycles"], d["total_cycles"]
            p1 = ts - (ph(ls, "load_wght") - ph(ld, "load_wght"))
            other = ts - ph(ls, "load_wght") - ph(ls, "compute")
            rows.append([label, pct(float(z) * 100, 0, False), f"{fmt(ph(ls, 'load_wght'))} / {fmt(ph(ld, 'load_wght'))}",
                         f"{fmt(ph(ls, 'compute'))} / {fmt(ph(ld, 'compute'))}", fmt(other),
                         f"{fmt(ts)} / {fmt(td)} / {fmt(p1)}", best({"sparse": ts, "dense": td, "p1": p1})])
    table(doc, ["Layer", "Số 0 ở input", "Nạp weight: sparse / dense HW", "Tính toán: sparse / dense HW",
                "Các pha khác", "Tổng: sparse / dense HW / P1", "Nhanh nhất"], rows,
          widths=[3.0, 1.5, 2.7, 2.7, 1.6, 3.6, 1.6], align_right=(1, 2, 3, 4, 5))
    doc.add_picture(FIG_SWEEP, width=Cm(16.5))
    caption(doc, "Hình 2. Chu kỳ cả layer so với dense HW theo tỉ lệ số 0 của input (CR 2 X 4). Dưới 1 là nhanh hơn dense HW.")
    para(doc, "Ngưỡng số 0 (dưới ngưỡng thì dense HW nhanh hơn cả layer):")
    table(doc, ["Layer", "CR 1 X 2: hôm nay → P1", "CR 2 X 4: hôm nay → P1", "CR 8 X 4: hôm nay → P1"], [
        ["Conv 28×28×1→16 (ảnh)", "42 % → 41 %", "60 % → 57 %", "dense luôn nhanh hơn → 76 %"],
        ["Conv 14×14×16→32", "4 % → 0 %", "36 % → 1 %", "73 % → 18 %"],
        ["Conv 7×7×32→32", "6 % → P1 luôn nhanh hơn", "48 % → P1 luôn nhanh hơn", "dense luôn nhanh hơn → 29 %"],
        ["Dense 1568→32", "dense luôn nhanh hơn → 8 %", "dense luôn nhanh hơn → 12 %", "dense luôn nhanh hơn → 9 %"],
    ], widths=[4.0, 4.2, 4.2, 4.2])
    bullets(doc, [
        "Ngưỡng phụ thuộc cấu hình cluster hơn là dạng layer: càng nhiều hàng cluster, tính toán càng ngắn, phần nạp weight càng "
        "nặng, dense HW càng có lợi. Không có một mật độ \"hoà vốn\" chung, nên mô hình chi phí phải tính theo cấu hình.",
        "P1 kéo ngưỡng xuống còn 0–30 % ở các layer giữa mạng (input sau ReLU: MNIST 43–87 % số 0, mạng Bảng 2 với weight ngẫu nhiên 11–85 %); layer đầu (ảnh, 1 channel) "
        "vẫn hợp dense HW nếu ảnh không có số 0. Mô hình chi phí dựng từ phép quét chọn đúng chế độ cho 28/28 layer của các "
        "mạng đã chạy (26/28 khi có P1; 2 ca sai lệch tổng 110 chu kỳ).",
    ])

    doc.add_heading("4.6. Chi phí của weight bằng 0 ở P1 (bước 2)", level=2)
    para(doc, "Ở P1 mọi weight đều có ô, nên FSM sparse nhân cả weight 0 (hôm nay bỏ qua). Bước 1 giả định tính toán tăng tỉ lệ "
              "thuận với số weight 0 (cận trên). Bước 2 đo thật trên RTL, cùng dữ liệu ở hai layout:")
    doc.add_picture(FIG_WZERO, width=Cm(16.5))
    caption(doc, "Hình 3. Tính toán tăng thêm khi weight 0 cũng được nhân, so với layout nén hôm nay (input không có số 0).")
    bullets(doc, [
        "Thấp hơn nhiều so với cận trên: 0–0,5 % ở 5 % weight 0 (khoảng của mạng thật: MNIST 0,3–2,9 %, weight ngẫu nhiên "
        "1–5 %), tối đa 8,4 % ở 25 %, 22,5 % ở 50 %. PE đọc 2 weight mỗi word; layout nén chỉ đỡ tốn khi số 0 bỏ bớt được "
        "cả word, còn khi ít số 0 nó lại thêm ô đệm. Cột ngắn (4 filter mỗi PE) thì layout của P1 còn nhanh hơn 0,5–0,8 %.",
        "Trên cả mạng: MNIST 0–26 chu kỳ, mạng Bảng 2 tối đa 376 chu kỳ (0,2 %). P1 đo được khớp ước lượng của bước 1 trong "
        "0,2 điểm.",
        "Layout nén chỉ còn tốt hơn khi weight 0 nhiều (weight đã prune): trên 5–18 % ở CR 1 X 2, trên 22–50 % ở CR 2 X 4, "
        "trên 46–50 % ở CR 8 X 4. Toolchain sẽ chọn theo layer (bước 3 / 5).",
    ])

    doc.add_heading("4.7. Throughput hiệu dụng", level=2)
    rows = []
    for name, run in [(f"MNIST {lab}", mn[a]) for a, lab in ACTS] + \
                     [(f"Bảng 2 ReLU, {lab}", t2[(c, True)]) for c, lab in T2]:
        prof = run["raw"][0]
        g = [gops(prof, run[k]["total"]) for k in ("sparse", "dense", "p1")]
        rows.append([name, fmt(sum(macs(l) for l in prof["layers"])), num(g[0], 2), num(g[1], 2), num(g[2], 2)])
    table(doc, ["Mạng", "Số MAC (dense, tính cả số 0)", "Sparse (GOPS)", "Dense HW (GOPS)", "P1 (GOPS)"], rows,
          widths=[4.2, 3.4, 2.8, 2.8, 2.8], align_right=(1, 2, 3, 4))
    para(doc, "GOPS hiệu dụng = 2 × số MAC của phép tính dense tương đương (kể cả phép nhân với 0) / thời gian cả mạng ở 250 MHz, "
              "gồm mọi pha nạp và ghi ngược. Đây là bản đầu của thước đo throughput mà giai đoạn 4 yêu cầu.")

    doc.add_heading("4.8. Tài nguyên: có đáng không", level=2)
    table(doc, ["Phương án", "Tài nguyên (ZU7EV, LUT sau route)", "Chu kỳ so với sparse hôm nay", "Chu kỳ × LUT", "Đáng không"], [
        ["Sparse (hôm nay)", "60.113 LUT, 39.556 FF, 188 BRAM, 12 URAM, 4 DSP; 250 MHz (WNS +0,096 ns)", "0", "0", "Mốc"],
        ["Dense HW", "khoảng 43.960 LUT (−26,9 %), −4 BRAM, −2 URAM", "ReLU −12,0 đến +3,7 %; hàm khác −13,4 đến −2,4 %",
         "−24,2 đến −36,7 %", "Tốt nhất theo diện tích, khi LUT là giới hạn"],
        ["P1 (weight theo layer)", "+281 LUT, +0 FF (ước lượng Yosys), BRAM không đổi", "−2,6 đến −13,5 %",
         "−2,3 đến −13,1 %", "Có: làm (bước 3)"],
        ["P2 (FSM theo layer)", "+8–16 % LUT (hai FSM mỗi PE)", "sau P1 chỉ thêm 0,1–0,4 %", "kém P1", "Không: dừng"],
    ], widths=[2.8, 4.6, 3.4, 2.4, 3.2])
    para(doc, "Trên ZU7EV thiết kế dùng 26 % LUT nhưng 60 % BRAM, nên LUT tiết kiệm của dense HW không đổi được thành thêm PE "
              "(thêm PE cần thêm BRAM). Muốn độ trễ thấp trên mạng có ReLU: sparse + P1. Chip mà LUT là giới hạn: bản dựng dense HW.")

    # ---------------------------------------------------------------- 5
    doc.add_heading("5. Những việc đã làm trong tuần (11/11 – 18/11/2026)", level=1)
    table(doc, ["Ngày", "Việc", "Kết quả"], [
        ["11/11", "Đề xuất chế độ trộn (activation sparse + weight 8 bit cho mọi layer)",
         "Ước lượng MNIST ReLU −4,5 đến −7 %; ước lượng diện tích PE bằng Yosys. Sau đó hoãn theo quyết định (17/11)"],
        ["12/11", "Hàm kích hoạt × cách làm tròn × sparse / dense (16 trường hợp)",
         "16/16 khớp từng bit; dense: làm tròn không đổi chu kỳ; sparse: ReLU floor nhanh hơn 0,5 %, Leaky ReLU làm tròn nhanh hơn 1,1 %"],
        ["12/11", "Sửa báo cáo lần 5; nghiên cứu bão hoà của hàm kích hoạt",
         "Tối đa 0,0003 % output bị kẹp; độ chính xác có / không giới hạn trên như nhau ở cả 4 model"],
        ["17/11", "Phân tích chọn sparse / dense theo layer; đánh giá đề xuất Adaptive Sparsity",
         "Với định dạng hôm nay chỉ lợi −1,26 % (MNIST ReLU); khác biệt chủ yếu ở định dạng weight → đề xuất đo trước"],
        ["17/11", "Rà soát upstream 3e2e027 (9 commit)", "Không lấy: upstream sparse 0/13, dense 8/13 ca; fork 11/13 cả hai chế độ"],
        ["17/11", "Mạng Bảng 2 của paper ở sparse và dense", "Dense 16/16, nhanh hơn sparse 6,4 % (2,7 % khi có ReLU); phát hiện lỗi #49"],
        ["17/11", "Gửi bias một lần mỗi filter (phương án A, chạy nền), bật mặc định",
         "MNIST −9,3 %, Bảng 3 −10 % chu kỳ (nạp bias 23.308 → 92); +434 LUT; 250 MHz"],
        ["17/11", "Điều tra và sửa lỗi #49 (Conv2 ở CR 2, điều kiện ready chỉ xét GLB chẵn); thêm kiểm tra Conv trước pooling",
         "Bảng 2 ReLU sparse 16/16 (trước 14/16); bản sửa không tốn logic đo được"],
        ["18/11", "Kế hoạch từng bước sparse / dense theo layer (bước 0–5, có điểm dừng)", "Lưu README_FI mục 2"],
        ["18/11", "Bước 0: kiểm chứng trạng thái đã commit, lập mốc mới",
         "Unit test 504 PASS; hồi quy 225 = 221 PASS + 4 xfail; Bảng 3 sparse / dense / ReLU 16/16; MNIST 8/8; Vivado 250 MHz, 60.113 LUT"],
        ["18/11", "Bước 1: đo theo layer và pha, quét tỉ lệ số 0 (120 lần), mô hình chi phí, đánh giá tài nguyên",
         "Chỉ nạp weight và tính toán khác nhau; P1 đáng làm, P2 dừng; mô hình đúng 28/28 layer"],
        ["18/11", "Bước 2: FSM sparse với layout weight của P1 trên RTL hiện tại (không sửa RTL)",
         "Khớp từng bit 99/99 lần; PE không cần sửa; chi phí weight 0 nhỏ; P1 đo được = ước lượng"],
    ], widths=[1.4, 7.4, 7.8])
    para(doc, "Tình trạng cuối tuần: ", None)
    bullets(doc, [
        "Hồi quy RTL 225 test = 221 PASS + 4 xfail đã biết, 0 FAIL; unit test Python 578 PASS + 11 lỗi cũ đã biết "
        "(test_dense_output.py, có từ upstream).",
        "Bảng 3 của bài báo 16/16 ở sparse, dense và sparse có ReLU; với layout weight của P1 32/32.",
        "Vivado (xczu7ev, 4 ns): đạt 250 MHz, WNS +0,096 ns, 60.113 LUT, 39.556 FF, 188 BRAM, 12 URAM, 4 DSP.",
        "Commit trên nhánh dev: c711703, ae5665f (bias theo filter, #49), 728827f (bước 0–1), 6cd2084 (bước 2).",
    ])

    # ---------------------------------------------------------------- 6
    doc.add_heading("6. Các bước sắp tới", level=1)
    table(doc, ["Bước", "Giai đoạn", "Nội dung", "Loại"], [
        ["3", "3. RTL", "P1: bit wght_raw trong thanh ghi cấu hình layer (regmap); raw_wght_i = FC | GEMM | wght_raw; GET_WGHT "
         "gom 3 word DMA mỗi hàng thay vì 5 và giãn weight 8 → 12 bit; Python chọn định dạng theo layer (mặc định 8 bit; nén khi "
         "weight 0 nhiều hoặc số filter lẻ mỗi PE) và đóng gói 8 bit; test mới test_wght_raw.py (mạng có layer xen kẽ hai định "
         "dạng, kiểm tra địa chỉ psum khi chuyển layer); lint; hồi quy 225; Vivado",
         "Sửa RTL + Python, cần duyệt"],
        ["4a", "4. Verification", "Benchmark Dense HW / Sparse / P1 đo thật: MNIST 4 hàm, mạng Bảng 2 (32 lần), các layer đơn; "
         "so với ONNX Runtime; latency từng layer, chu kỳ nạp, word DMA, GOPS; tài nguyên Vivado của từng bản dựng",
         "Chạy, sau bước 3"],
        ["5", "2. Cost model", "Toolchain: onnx2model đo số 0 trên ảnh hiệu chỉnh, mô hình chi phí chọn định dạng weight mỗi "
         "layer, profiler ghi định dạng đã chọn", "Python"],
        ["4b", "1 + 4", "Thêm một model thật lớn hơn (nhiều layer, input RGB hoặc weight đã prune) để thử quy tắc chọn ở nơi "
         "ngưỡng có ý nghĩa", "Python + chạy"],
        ["(4)", "3. RTL", "P2 (FSM theo layer): dừng. Chỉ xem lại nếu model lớn có layer lớn không có số 0 ở input bị FSM sparse "
         "làm chậm nhiều; khi đó cách rẻ hơn là giảm chi phí FSM sparse", "Không làm"],
    ], widths=[1.2, 2.4, 9.8, 3.2])
    para(doc, "Rủi ro cần theo dõi ở bước 3: ", None)
    bullets(doc, [
        "Thời gian của GET_WGHT: hàng weight được ghi khi tới word DMA thứ 3 thay vì thứ 5, phép giãn 8 → 12 bit phải vừa trong "
        "một chu kỳ ở 250 MHz (mô hình Yosys p1_wght_row.v: một bộ chọn 2 đầu vào cho mỗi bit của hàng và điều kiện kết thúc khác của bộ đếm, +281 LUT, không thêm FF).",
        "Số filter lẻ mỗi PE (#48): giữ layout nén cho các layer này.",
        "Kết luận hiện dựa trên 2 mạng; model lớn hơn (bước 4b) sẽ kiểm tra lại ngưỡng và mô hình chi phí.",
    ])

    doc.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    build()
