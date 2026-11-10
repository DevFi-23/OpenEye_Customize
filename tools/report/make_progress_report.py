#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Build the Word progress report (Vietnamese) from the measured profiles.

Numbers come from doc/perf/baseline_2026-10-10/ and doc/perf/mem_typical_2026-10-10/,
so rerunning the script after new measurements updates tables and chart.

Needs python-docx and matplotlib (not in the project venv; a separate env is used):
    ~/tools/docenv/bin/python tools/report/make_progress_report.py
Output: doc/reports/2026-10-10_TienDo/BaoCao_TienDo_OpenEye_2026-10-10.docx (+ the chart PNG next to it)
"""

import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(REPO, "doc", "perf", "baseline_2026-10-10")
TYPICAL = os.path.join(REPO, "doc", "perf", "mem_typical_2026-10-10")
OUT_DIR = os.path.join(REPO, "doc", "reports", "2026-10-10_TienDo")   # one folder per report (2026-11-10)
DATE = "10/10/2026"
OUT = os.path.join(OUT_DIR, "BaoCao_TienDo_OpenEye_2026-10-10.docx")
CHART = os.path.join(OUT_DIR, "phan_bo_do_tre_2026-10-10.png")

CASE_ORDER = ["8x1_f4_q32_dma64", "16x3_f4_q32_dma64", "32x3_f4_q32_dma64", "32x3_f16_q32_dma64",
              "32x3_f4_q32_dma32", "8x1_f4_q1024_dma64", "mnist1_28x28_c4_f32_q32_dma64",
              "mnist2_14x14_c32_f32_q32_dma64", "mnist3_8x8_c32_f32_q32_dma64"]
CASE_LABEL = {
    "8x1_f4_q32_dma64": "8×1×4, 4 filter",
    "16x3_f4_q32_dma64": "16×3×4, 4 filter",
    "32x3_f4_q32_dma64": "32×3×4, 4 filter",
    "32x3_f16_q32_dma64": "32×3×4, 16 filter",
    "32x3_f4_q32_dma32": "32×3×4, 4 filter, DMA 32 bit",
    "8x1_f4_q1024_dma64": "8×1×4, 4 filter, QUANT 1024",
    "mnist1_28x28_c4_f32_q32_dma64": "Kiểu Conv1: 28×28×4 → 32",
    "mnist2_14x14_c32_f32_q32_dma64": "Kiểu Conv2: 14×14×32 → 32",
    "mnist3_8x8_c32_f32_q32_dma64": "Kiểu Conv3: 8×8×32 → 32",
}
# Phase groups for the chart, in the fixed categorical order of the palette
GROUPS = [
    ("Tính toán (compute)", ["compute"], "#2a78d6", "white"),
    ("Nạp bias", ["load_bias"], "#eb6834", "black"),
    ("Đọc kết quả (readout)", ["readout"], "#1baf7a", "black"),
    ("Nạp weight", ["load_wght"], "#eda100", "black"),
    ("Chuyển đổi iact", ["convert_iact"], "#e87ba4", "black"),
    ("Nạp khác (cấu hình, iact, bảng lượng tử)", ["load_config", "load_iact", "load_quant"], "#008300", "white"),
]


def load(directory):
    out = {}
    for path in glob.glob(os.path.join(directory, "*.json")):
        with open(path) as f:
            out[os.path.splitext(os.path.basename(path))[0]] = json.load(f)
    return out


def shares(profile):
    total = profile["total_cycles"]
    ph = profile["phases"]
    return [sum(ph.get(p, {}).get("cycles", 0) for p in parts) / total for _, parts, _, _ in GROUPS]


def make_chart(base):
    cases = [c for c in CASE_ORDER if c in base]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(9.2, 4.6), dpi=200)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    y = list(range(len(cases)))[::-1]
    left = [0.0] * len(cases)
    for g, (name, _, color, ink) in enumerate(GROUPS):
        vals = [shares(base[c])[g] * 100 for c in cases]
        ax.barh(y, vals, left=left, height=0.62, color=color, edgecolor="#fcfcfb", linewidth=1.5, label=name)
        for yi, v, l in zip(y, vals, left):
            if v >= 8:
                ax.text(l + v / 2, yi, f"{v:.0f}%", ha="center", va="center", color=ink, fontsize=8)
        left = [l + v for l, v in zip(left, vals)]
    ax.set_yticks(y)
    ax.set_yticklabels([CASE_LABEL[c] for c in cases], color="#0b0b0b")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Tỉ lệ trên tổng số chu kỳ của layer (%)", color="#52514e")
    ax.tick_params(colors="#52514e", length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#d6d5cf")
    ax.xaxis.grid(True, color="#e8e7e2", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.01), frameon=False, fontsize=8,
              handlelength=1.2, columnspacing=1.2)
    fig.tight_layout()
    fig.savefig(CHART, facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------- docx helpers
def shade(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def table(doc, header, rows, widths=None, align_right=()):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(10)
        shade(cell, "DCE6F2")
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            run = p.add_run(str(value))
            run.font.size = Pt(10)
            if i in align_right:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return t


def bullets(doc, items):
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def para(doc, text, bold_prefix=None):
    p = doc.add_paragraph()
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    p.add_run(text)
    return p


def fmt(n):
    return f"{n:,}".replace(",", ".")


def build():
    base = load(BASE)
    typical = load(TYPICAL)
    os.makedirs(OUT_DIR, exist_ok=True)
    make_chart(base)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    style.font.size = Pt(12)
    for section in doc.sections:
        section.left_margin = section.right_margin = Cm(2.2)
        section.top_margin = section.bottom_margin = Cm(2.0)

    title = doc.add_heading("BÁO CÁO TIẾN ĐỘ", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Tối ưu bộ tăng tốc mạng nơ-ron OpenEye theo băng thông và độ trễ")
    r.bold = True
    r.font.size = Pt(14)
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(f"Người thực hiện: Nguyễn Ngọc Trường Phi\nNgày: {DATE}\n"
                 "Mã nguồn: github.com/DevFi-23/OpenEye (nhánh dev, private)").font.size = Pt(11)

    # 1
    doc.add_heading("1. Mục tiêu và bối cảnh", level=1)
    para(doc, "OpenEye là bộ tăng tốc suy luận mạng nơ-ron tích chập mã nguồn mở (INT8, dataflow kiểu Eyeriss v2, "
              "có thể tham số hoá kích thước mảng PE), chạy trên FPGA qua giao tiếp AXI DMA. Dự án phát triển một nhánh "
              "riêng dựa trên mã nguồn gốc (Learning-Chips-Lab/OpenEye), theo dõi định kỳ các thay đổi của nhóm phát triển gốc.")
    para(doc, "Mục tiêu nghiên cứu: phân tích và tối ưu bộ tăng tốc theo hai tiêu chí: (1) băng thông, tức lưu lượng dữ liệu "
              "qua DMA giữa bộ nhớ ngoài (DDR) và bộ tăng tốc; (2) độ trễ, tức số chu kỳ để xử lý một layer.")
    para(doc, "Giai đoạn hiện tại (Giai đoạn 0) tập trung xây dựng công cụ đo, lập số liệu mốc (baseline) và kiểm tra tính đúng "
              "của thiết kế trước khi tối ưu.")

    # 2
    doc.add_heading("2. Công việc đã hoàn thành", level=1)
    doc.add_heading("2.1. Công cụ đo và kiểm thử đã xây dựng", level=2)
    table(doc, ["Công cụ", "Chức năng", "Kết quả kiểm chứng"], [
        ["Profiler chu kỳ / DMA", "Lấy mẫu mỗi chu kỳ clock trong mô phỏng RTL; đếm số chu kỳ và số word DMA vào/ra theo từng "
         "pha của layer (nạp cấu hình, iact, weight, bias, bảng lượng tử, chuyển đổi iact, tính toán, đọc kết quả)",
         "Kết quả trùng với phân tích log FSM"],
        ["Báo cáo và so sánh", "Tính hiệu suất bus = byte tối thiểu cần thiết / byte thực sự truyền; so sánh trước/sau theo từng pha",
         "10 unit test"],
        ["Bộ chạy đo một lệnh", "Chạy song song các cấu hình đo, loại case lỗi, so với baseline, lưu snapshot",
         "Mô phỏng tất định: chạy lại cho kết quả trùng 100%"],
        ["Mô hình bộ nhớ ngoài", "Mô phỏng DDR + AXI DMA trong testbench: độ trễ burst, độ dài burst, số burst chờ, băng thông, "
         "FIFO, jitter; driver AXI-Stream đúng giao thức valid/ready", "16 unit test; với bộ nhớ lý tưởng trùng 100% baseline"],
        ["Ghi vết DMA", "Ghi mọi word bộ tăng tốc nhận được và mọi lần chuyển trạng thái FSM; so với stream do testbench sinh ra",
         "Dùng để chứng minh nguyên nhân lỗi GET_BIAS"],
        ["Lint theo baseline (CI)", "Verilator 5.020 trên GitHub Actions; chỉ báo lỗi khi xuất hiện cảnh báo mới; thêm lint cho "
         "top-level FPGA", "38 + 478 cảnh báo có sẵn được ghi nhận và phân loại"],
    ], widths=[3.4, 8.6, 4.6])

    doc.add_heading("2.2. Cấu hình đo", level=2)
    para(doc, "Mỗi cấu hình là một layer tích chập 3×3 trên top-level OpenEye_FPGA (2×2 cluster, psum 20 bit, DMA 64 bit như phần "
              "cứng thật). Gồm 6 layer nhỏ để kiểm tra nhanh và 3 layer mô phỏng các lớp tích chập của mạng MNIST, được thu nhỏ "
              "trong giới hạn mà RTL hiện tại xử lý đúng (tối đa 32 filter, không dùng 1 hoặc 3 channel đầu vào).")

    doc.add_heading("2.3. Kết quả đo mốc (baseline, bộ nhớ lý tưởng)", level=2)
    rows = []
    for c in CASE_ORDER:
        if c not in base:
            continue
        p = base[c]
        s = shares(p)
        words = sum(v["in_accepted"] + v["out_words"] for v in p["phases"].values())
        rows.append([CASE_LABEL[c], fmt(p["total_cycles"]), fmt(words), f"{s[0]*100:.0f}%", f"{s[1]*100:.0f}%",
                     f"{s[2]*100:.0f}%", f"{s[3]*100:.0f}%", f"{s[4]*100:.0f}%", f"{s[5]*100:.0f}%"])
    table(doc, ["Layer", "Tổng chu kỳ", "Word DMA", "Tính toán", "Bias", "Readout", "Weight", "Chuyển đổi", "Nạp khác"],
          rows, widths=[4.6, 1.8, 1.6, 1.4, 1.2, 1.4, 1.4, 1.6, 1.4], align_right=range(1, 9))
    doc.add_picture(CHART, width=Cm(16.5))
    cap = doc.add_paragraph("Hình 1. Phân bổ độ trễ của một layer theo pha (bộ nhớ lý tưởng). Số liệu đầy đủ ở bảng trên.")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True

    para(doc, "Nhận xét chính:", bold_prefix=None).runs[0].bold = True
    bullets(doc, [
        "Các pha chạy hoàn toàn tuần tự (nạp → chuyển đổi → tính toán → đọc kết quả), không có chồng lấp.",
        "Layer đầu (ảnh lớn, ít channel, kiểu Conv1): phần tính toán chỉ chiếm khoảng 51%; nạp bias và đọc kết quả chiếm khoảng 44%.",
        "Layer sâu (nhiều channel, kiểu Conv2/Conv3): tính toán chiếm 71–77%; weight chiếm 9–14%.",
        "Bias được gửi theo từng pixel output thay vì theo filter: hiệu suất bus gần 0% (14.336 word cho 96 byte thông tin cần thiết ở layer kiểu Conv1).",
        "Weight chỉ đạt hiệu suất bus 15–30%; kết quả đọc ra dạng psum 20 bit trong ô 32 bit (66–75%), chưa lượng tử về INT8.",
        "Bảng lượng tử luôn được gửi đủ QUANT_AMOUNT entry bất kể số filter (640 word khi QUANT_AMOUNT = 1024).",
        "DMA 32 bit chậm hơn 64 bit khoảng 34% ở cùng layer.",
    ])

    doc.add_heading("2.4. Ảnh hưởng của bộ nhớ ngoài (mô hình bộ nhớ)", level=2)
    rows = []
    for c in CASE_ORDER:
        if c in base and c in typical:
            b, t = base[c]["total_cycles"], typical[c]["total_cycles"]
            rows.append([CASE_LABEL[c], fmt(b), fmt(t), f"+{(t - b) / b * 100:.1f}%".replace(".", ",")])
    table(doc, ["Layer", "Bộ nhớ lý tưởng (chu kỳ)", "Bộ nhớ 'typical' (chu kỳ)", "Tăng"], rows,
          widths=[6.0, 3.6, 3.8, 2.0], align_right=(1, 2, 3))
    para(doc, "Cấu hình 'typical' (minh hoạ, chưa hiệu chỉnh theo board): độ trễ đầu burst 30 chu kỳ, burst 16 word, 2 burst chờ đồng thời. "
              "Mỗi word DMA thực tế tốn khoảng 1,44 chu kỳ thay vì 1, phần tính toán không đổi. Với cấu hình chậm hơn ('slow'), độ trễ tăng "
              "112–350%. Điều này cho thấy giảm số word DMA mang lại lợi ích lớn hơn con số đo trên bộ nhớ lý tưởng.")

    # 3
    doc.add_heading("3. Lỗi phát hiện được", level=1)
    doc.add_heading("3.1. Đã sửa", level=2)
    table(doc, ["Lỗi", "Nguyên nhân", "Cách sửa và kiểm chứng"], [
        ["FSM GET_BIAS (RTL, OpenEye_FPGA.v) treo khi DMA có một chu kỳ trống ngay trước word bias cuối",
         "Điều kiện chuyển trạng thái không kiểm tra tín hiệu valid (enable_dma_i_reg), khác với 5 trạng thái nạp còn lại. "
         "Đã chứng minh bằng ghi vết: dữ liệu luôn đúng số lượng và thứ tự; chỉ 1 chu kỳ trống ở đúng vị trí là gây lỗi",
         "Thêm 1 điều kiện '& enable_dma_i_reg'. Sau sửa: 15/15 kịch bản khoảng trống và 8/8 layer với bộ nhớ chậm đều PASS; "
         "0 chu kỳ thay đổi trên 9 layer baseline; không thêm flip-flop, LUT không tăng (Yosys synth_xilinx); "
         "không có hồi quy ở 16 test Conv và 63 test GEMM/Dense"],
        ["Testbench giải mã sai thứ tự kết quả Conv (chế độ serial)",
         "Testbench tự đoán toạ độ output bằng bộ đếm riêng, không khớp với thứ tự thật ở cấu hình 1×1 cluster",
         "Giải mã theo đúng thứ tự của bộ sinh tham chiếu: 124/128 giá trị sai → 0"],
        ["Bộ sinh tài liệu Verilog", "Không xử lý comment và giá trị tham số dạng biểu thức",
         "Warning Sphinx 125 → 0; đọc đủ tham số (ví dụ OpenEye_FPGA: 0 → 95)"],
        ["CI lint luôn báo lỗi", "38 cảnh báo có sẵn trong RTL gốc", "Lint theo baseline, không sửa RTL; thêm lint cho top-level FPGA"],
    ], widths=[4.4, 6.0, 6.2])

    doc.add_heading("3.2. Chưa sửa (có sẵn trong mã nguồn gốc)", level=2)
    table(doc, ["Lỗi", "Ảnh hưởng", "Ghi chú"], [
        ["Layer Dense/FC: ghi activation sai (bank=1, addr=0)", "23/63 test GEMM/Dense thất bại", "Cản trở đo layer Dense (việc 0.2)"],
        ["Đầu vào 1 channel chỉ cho ra bias", "Chưa chạy được Conv1 thật của MNIST", "Đường xử lý iact"],
        ["Đầu vào 3 channel và cấu hình NUM_GLB_IACT = 3 cho kết quả sai", "Giới hạn cấu hình đo", "Đường xử lý iact"],
        ["64 filter: lỗi trong bộ sinh dữ liệu Python", "Giới hạn tối đa 32 filter khi đo", "Phần mềm"],
        ["Ảnh rộng 7: ghi giá trị khác 0 vào ô đệm", "Kiểm tra chuỗi DMA thất bại dù giá trị đúng", "RTL hoặc testbench"],
        ["Một số cảnh báo lint đáng ngờ (cắt bit địa chỉ weight 7 → 5 bit; overhead cố định 4 bit; gán blocking/non-blocking lẫn lộn)",
         "Có thể gây sai ở chế độ sparse hoặc PARALLEL_MACS > 1", "Cần test trước khi kết luận"],
    ], widths=[6.2, 5.2, 5.2])
    para(doc, "Nguyên tắc làm việc: mọi thay đổi RTL đều được kiểm chứng (test chức năng, baseline hiệu năng, lint, tài nguyên) "
              "và chỉ thực hiện sau khi được đồng ý.")

    # 4
    doc.add_heading("4. Kế hoạch gần", level=1)
    table(doc, ["#", "Việc", "Lý do và kết quả mong đợi"], [
        ["1", "Gửi bias theo filter (Giai đoạn 1.1)", "Bias đang chiếm khoảng 22% độ trễ layer kiểu Conv1 với hiệu suất bus gần 0%. "
         "Kỳ vọng giảm khoảng 20% độ trễ layer này"],
        ["2", "Đọc kết quả dạng INT8 (Giai đoạn 1.2)", "Readout chiếm khoảng 22% ở layer kiểu Conv1; giảm khoảng 4 lần số word ra"],
        ["3", "Phân tích định dạng weight (Giai đoạn 1.3)", "Hiệu suất bus weight 15–30%; phân tích trước, sau đó đề xuất cách đóng gói"],
        ["4", "Mở rộng đo cho layer Dense và chuỗi nhiều layer (việc 0.2)", "Cần quyết định xử lý lỗi Dense có sẵn"],
        ["5", "Chạy chồng pha nạp và pha tính toán (Giai đoạn 2)", "Che độ trễ nạp dữ liệu sau khi đã giảm lưu lượng ở Giai đoạn 1"],
    ], widths=[0.8, 5.4, 10.4])
    para(doc, "Mỗi bước được đánh giá bằng so sánh tự động với baseline (số chu kỳ, số word DMA, hiệu suất bus theo từng pha), "
              "cả với bộ nhớ lý tưởng và bộ nhớ mô hình hoá.")

    # 5
    doc.add_heading("5. Hạn chế hiện tại", level=1)
    bullets(doc, [
        "Số liệu lấy từ mô phỏng RTL (Icarus Verilog). Số word DMA và số chu kỳ của các pha nội bộ trùng với phần cứng; "
        "tổng độ trễ trên FPGA sẽ lớn hơn do độ trễ DDR, AXI DMA và phần mềm điều khiển.",
        "Tham số mô hình bộ nhớ chưa được hiệu chỉnh theo board thật; kết quả dùng để so sánh tương đối giữa các phương án.",
        "Chưa chạy được mạng MNIST đầy đủ trên RTL vì các lỗi có sẵn nêu ở mục 3.2.",
        "Tài nguyên được ước lượng bằng Yosys cho module top-level; chưa tổng hợp toàn thiết kế bằng Vivado.",
    ])

    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
