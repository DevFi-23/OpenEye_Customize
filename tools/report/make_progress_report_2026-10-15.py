#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Build the second Word progress report (Vietnamese, 2026-10-15).

Numbers come from doc/perf/baseline_2026-10-15/ (after the bug #18 fix),
doc/perf/baseline_2026-10-10/ (before) and the Vivado reports in
doc/synth/2026-10-15_route4ns_fix67_zu7ev/. Formatting helpers are shared with
make_progress_report.py (the 2026-10-10 report).

    ~/tools/docenv/bin/python tools/report/make_progress_report_2026-10-15.py
Output: doc/reports/2026-10-15_TienDo/BaoCao_TienDo_OpenEye_2026-10-15.docx (+ two chart PNGs next to it)
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_progress_report as base_report  # noqa: E402
from make_progress_report import CASE_LABEL, CASE_ORDER, bullets, fmt, load, para, shares, table  # noqa: E402

REPO = base_report.REPO
NEW = os.path.join(REPO, "doc", "perf", "baseline_2026-10-15")
OLD = os.path.join(REPO, "doc", "perf", "baseline_2026-10-10")
OUT_DIR = os.path.join(REPO, "doc", "reports", "2026-10-15_TienDo")   # one folder per report (2026-11-10)
DATE = "15/10/2026"
OUT = os.path.join(OUT_DIR, "BaoCao_TienDo_OpenEye_2026-10-15.docx")
CHART_PHASES = os.path.join(OUT_DIR, "phan_bo_do_tre_2026-10-15.png")
CHART_COMPARE = os.path.join(OUT_DIR, "so_sanh_chu_ky_2026-10-15.png")
CLOCK_NS = 4.0     # 250 MHz, met after place and route (doc/synth/2026-10-15_route4ns_fix67_zu7ev)

MNIST = ["mnist1_28x28_c4_f32_q32_dma64", "mnist2_14x14_c32_f32_q32_dma64", "mnist3_8x8_c32_f32_q32_dma64"]


def pct(x):
    return f"{x * 100:.1f}%".replace(".", ",")


def compare_chart(old, new):
    """Grouped bars: total cycles before/after the bug #18 fix for the three MNIST-like layers."""
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(8.0, 3.4), dpi=200)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    labels = [CASE_LABEL[c] for c in MNIST]
    xs = list(range(len(MNIST)))
    w = 0.36
    before = [old[c]["total_cycles"] for c in MNIST]
    after = [new[c]["total_cycles"] for c in MNIST]
    b1 = ax.bar([x - w / 2 - 0.01 for x in xs], before, w, color="#a3a29c", label="Trước bản sửa lỗi #18 (10/10)")
    b2 = ax.bar([x + w / 2 + 0.01 for x in xs], after, w, color="#2a78d6", label="Sau bản sửa lỗi #18 (15/10)")
    for bars, vals in ((b1, before), (b2, after)):
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, v, fmt(v), ha="center", va="bottom", fontsize=8, color="#0b0b0b")
    for x, b, a in zip(xs, before, after):
        ax.text(x + w / 2 + 0.01, a / 2, f"{(a - b) / b * 100:+.1f}%".replace(".", ","), ha="center", va="center",
                fontsize=8, color="white")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, color="#0b0b0b")
    ax.set_ylabel("Tổng số chu kỳ của layer", color="#52514e")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(int(v))))
    ax.tick_params(colors="#52514e", length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#d6d5cf")
    ax.yaxis.grid(True, color="#e8e7e2", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_COMPARE, facecolor=fig.get_facecolor())
    plt.close(fig)


def build():
    new = load(NEW)
    old = load(OLD)
    os.makedirs(OUT_DIR, exist_ok=True)
    base_report.CHART = CHART_PHASES
    base_report.make_chart(new)
    compare_chart(old, new)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    style.font.size = Pt(12)
    for section in doc.sections:
        section.left_margin = section.right_margin = Cm(2.2)
        section.top_margin = section.bottom_margin = Cm(2.0)

    title = doc.add_heading("BÁO CÁO TIẾN ĐỘ (LẦN 2)", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Tối ưu bộ tăng tốc mạng nơ-ron OpenEye theo băng thông và độ trễ")
    r.bold = True
    r.font.size = Pt(14)
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(f"Người thực hiện: Nguyễn Ngọc Trường Phi\nNgày: {DATE} (báo cáo trước: 10/10/2026)\n"
                 "Mã nguồn: github.com/DevFi-23/OpenEye (nhánh dev, private)").font.size = Pt(11)

    # ---------------------------------------------------------------- 1
    doc.add_heading("1. Tóm tắt", level=1)
    m1o, m1n = old[MNIST[0]]["total_cycles"], new[MNIST[0]]["total_cycles"]
    m2o, m2n = old[MNIST[1]]["total_cycles"], new[MNIST[1]]["total_cycles"]
    m3o, m3n = old[MNIST[2]]["total_cycles"], new[MNIST[2]]["total_cycles"]
    bullets(doc, [
        "Đã tổng hợp và place & route toàn bộ bộ tăng tốc bằng Vivado 2024.2 trên Zynq UltraScale+ ZU7EV: đạt tần số 250 MHz, "
        "dùng 28% LUT, 8,5% flip-flop, 62% Block RAM. Đây là mốc phần cứng để đánh giá mọi tối ưu (độ trễ thật = số chu kỳ ÷ tần số).",
        "Phát hiện và sửa 4 lỗi làm bộ tăng tốc tính sai: (1) bộ đếm bị điều khiển từ hai nơi, mô phỏng đúng nhưng phần cứng sau "
        "tổng hợp sai; (2) đầu vào 1 channel chỉ ra bias; (3) cấu hình NUM_GLB_IACT = 3 sai; (4) mỗi lần gửi weight đọc gấp đôi số "
        "địa chỉ nên mọi layer có hơn 4 channel tính sai với weight thật. Lỗi (2), (3) là hồi quy của một commit trong mã nguồn gốc.",
        "Xây dựng phép kiểm tra độc lập từng word: tính lại layer bằng numpy từ chính dữ liệu bộ tăng tốc nhận và so từng giá trị "
        "đầu ra. Toàn bộ bản sửa được xác nhận theo cách này với dữ liệu ngẫu nhiên.",
        f"Bản sửa lỗi (4) đồng thời giảm độ trễ: layer kiểu Conv1 {fmt(m1o)} → {fmt(m1n)} chu kỳ ({pct((m1n - m1o) / m1o)}), "
        f"Conv2 {fmt(m2o)} → {fmt(m2n)} ({pct((m2n - m2o) / m2o)}), Conv3 {fmt(m3o)} → {fmt(m3n)} ({pct((m3n - m3o) / m3o)}). "
        f"Ở 250 MHz: {m1n * CLOCK_NS / 1000:.0f} / {m2n * CLOCK_NS / 1000:.0f} / {m3n * CLOCK_NS / 1000:.0f} µs.",
        "Layer Conv2 của MNIST (14×14, 32 → 64, đúng kích thước thật) đã chạy đúng hoàn toàn; Conv3 (7×7, 64 → 64) đúng mọi giá trị.",
    ])

    # ---------------------------------------------------------------- 2
    doc.add_heading("2. Mục tiêu và bối cảnh", level=1)
    para(doc, "OpenEye là bộ tăng tốc suy luận mạng nơ-ron tích chập mã nguồn mở (INT8, dataflow kiểu Eyeriss v2, kích thước mảng PE "
              "tham số hoá), giao tiếp với bộ nhớ ngoài qua AXI DMA. Dự án phát triển nhánh riêng dựa trên mã nguồn gốc "
              "(Learning-Chips-Lab/OpenEye), theo dõi định kỳ thay đổi của nhóm gốc nhưng không gửi thay đổi ngược lại.")
    para(doc, "Mục tiêu nghiên cứu: tối ưu bộ tăng tốc theo (1) băng thông, tức lưu lượng DMA giữa DDR và bộ tăng tốc, và (2) độ trễ, "
              "tức thời gian xử lý một layer. Giai đoạn 0 (đo lường và kiểm tra tính đúng) gần hoàn thành; trong quá trình này phát sinh "
              "việc sửa các lỗi làm sai kết quả, vì không thể tối ưu một thiết kế tính sai.")

    # ---------------------------------------------------------------- 3
    doc.add_heading("3. Công việc đã hoàn thành", level=1)
    doc.add_heading("3.1. Công cụ đo, kiểm thử và tổng hợp", level=2)
    table(doc, ["Công cụ", "Chức năng", "Trạng thái"], [
        ["Profiler chu kỳ / DMA", "Đếm số chu kỳ và số word DMA theo từng pha của layer trong mô phỏng RTL", "Từ 10/10"],
        ["Báo cáo, so sánh, bộ chạy đo", "Hiệu suất bus theo pha; so sánh trước/sau tự động; chạy song song 9 cấu hình", "Từ 10/10"],
        ["Mô hình bộ nhớ ngoài", "Mô phỏng DDR + AXI DMA (độ trễ burst, băng thông, FIFO)", "Từ 10/10"],
        ["Lint theo baseline (CI)", "Chỉ báo lỗi khi xuất hiện cảnh báo Verilator mới", "Từ 10/10; baseline hạ 478 → 477"],
        ["Xuất dự án Vivado (export_vivado.py)", "Sinh đồng bộ 4 file header tham số và bộ giải mã cấu hình từ một cấu hình duy nhất, "
         "chép RTL và script Tcl tổng hợp + place & route out-of-context", "Mới"],
        ["Kiểm tra độc lập từng word (verify_conv_output.py)", "Tính lại layer Conv bằng numpy từ dữ liệu bộ tăng tốc nhận; so từng "
         "giá trị đầu ra; kiểm tra không thiếu/không trùng vị trí, không có X", "Mới"],
        ["Bộ test MNIST và dữ liệu ngẫu nhiên (test_mnist_layers.py)", "Quét số channel × NUM_GLB_IACT; 3 layer Conv MNIST đúng kích "
         "thước thật; 6 layer với dữ liệu ngẫu nhiên, mỗi test tự chạy kiểm tra độc lập", "Mới (19 test)"],
        ["Giải mã thanh ghi cấu hình", "Đọc lại các thanh ghi vòng lặp mà phần mềm gửi xuống bộ tăng tốc", "Mới"],
    ], widths=[4.4, 8.8, 3.4])

    doc.add_heading("3.2. Tổng hợp phần cứng (Vivado 2024.2, ZU7EV)", level=2)
    para(doc, "Cấu hình tổng hợp trùng với cấu hình đo chu kỳ: 2×2 cluster, mỗi cluster 12 PE (tổng 48 PE, 96 phép nhân INT8 mỗi chu kỳ), "
              "chế độ sparse, psum 20 bit, DMA 64 bit, bảng lượng tử 32 entry. Tổng hợp out-of-context module OpenEye_FPGA, ràng buộc "
              "clock 4 ns (250 MHz), sau đó place & route.")
    table(doc, ["Chỉ số", "Sau tổng hợp", "Sau place & route", "Tỉ lệ chip ZU7EV"], [
        ["Slack setup (WNS) ở 4 ns", "+0,192 ns", "+0,048 ns", "Đạt 250 MHz"],
        ["Tần số tối đa ước tính", "≈ 263 MHz", "≈ 253 MHz", ""],
        ["LUT", "65.909", "64.162", "27,8%"],
        ["Flip-flop", "38.868", "39.192", "8,5%"],
        ["Block RAM tile", "192", "192", "61,5%"],
        ["URAM / DSP", "8 / 4", "8 / 4", "8,3% / 0,2%"],
        ["Lỗi / cảnh báo nghiêm trọng", "0 / 0", "0 / 0", ""],
    ], widths=[5.0, 3.6, 3.8, 4.2], align_right=(1, 2, 3))
    bullets(doc, [
        "Mảng 48 PE chiếm khoảng 84% LUT và 85% flip-flop; bộ nhân của PE đang dùng LUT, chưa dùng DSP.",
        "8 bộ đệm psum (16.384 × 40 bit) chiếm 144/168 RAMB36, tức 46% Block RAM của chip, trong khi layer lớn nhất chỉ dùng khoảng "
        "11% dung lượng. Đường găng thời gian sau route cũng là dây nối tới các BRAM này. Đây là một hướng tối ưu tài nguyên và tần số.",
        "Qua các lần tổng hợp đã phát hiện lỗi 'bộ đếm bị điều khiển từ hai nơi' (mục 4) nhờ cảnh báo CRITICAL WARNING của Vivado; "
        "sau khi sửa, không còn cảnh báo nghiêm trọng nào.",
    ])

    doc.add_heading("3.3. Kết quả đo mốc mới (bộ nhớ lý tưởng, sau các bản sửa)", level=2)
    rows = []
    for c in CASE_ORDER:
        if c not in new:
            continue
        p = new[c]
        s = shares(p)
        t_old = old[c]["total_cycles"] if c in old else None
        rows.append([CASE_LABEL[c], fmt(p["total_cycles"]),
                     pct((p["total_cycles"] - t_old) / t_old) if t_old else "",
                     f"{p['total_cycles'] * CLOCK_NS / 1000:.1f}".replace(".", ","),
                     f"{s[0]*100:.0f}%", f"{s[1]*100:.0f}%", f"{s[2]*100:.0f}%", f"{s[3]*100:.0f}%"])
    table(doc, ["Layer", "Tổng chu kỳ", "So với 10/10", "µs @250 MHz", "Tính toán", "Bias", "Readout", "Weight"],
          rows, widths=[4.8, 1.9, 1.9, 1.9, 1.6, 1.3, 1.6, 1.5], align_right=range(1, 8))
    doc.add_picture(CHART_PHASES, width=Cm(16.5))
    cap = doc.add_paragraph("Hình 1. Phân bổ độ trễ của một layer theo pha (bộ nhớ lý tưởng, mốc 15/10).")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True
    doc.add_picture(CHART_COMPARE, width=Cm(15.0))
    cap = doc.add_paragraph("Hình 2. Tổng số chu kỳ của 3 layer kiểu MNIST trước và sau bản sửa lỗi gửi weight (lỗi #18).")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True
    para(doc, "Nhận xét:").runs[0].bold = True
    bullets(doc, [
        "Toàn bộ phần giảm chu kỳ nằm ở pha tính toán (khoảng −32%): mỗi lần gửi weight vào PE giờ mất 96 thay vì 192 chu kỳ. "
        "Số word DMA không thay đổi.",
        "Sau bản sửa, với layer đầu (ảnh lớn, ít channel), nạp bias và đọc kết quả mỗi phần chiếm khoảng 26% độ trễ, nên hai tối ưu "
        "'bias theo filter' và 'đọc kết quả INT8' càng quan trọng.",
        "Với layer sâu, tính toán vẫn chiếm 62–69%; phần nạp weight tăng lên 12–19% (hiệu suất bus weight 15–30%).",
        "Mốc 10/10 được đo khi lỗi gửi weight còn tồn tại, nên không dùng để so sánh tối ưu nữa; mốc mới là baseline_2026-10-15.",
    ])

    doc.add_heading("3.4. Kiểm tra độc lập từng word", level=2)
    para(doc, "Testbench so kết quả bộ tăng tốc với tham chiếu do chính bộ phần mềm sinh dữ liệu tạo ra, và các test cũ dùng weight hằng số "
              "(mọi channel, mọi filter giống nhau). Hai điều này đã che lỗi gửi weight suốt nhiều tuần. Vì vậy mọi bản sửa đều được kiểm tra "
              "thêm bằng cách tính lại layer bằng numpy và so từng giá trị đầu ra (mỗi word DMA 64 bit chứa 2 giá trị psum 20 bit), với dữ "
              "liệu ngẫu nhiên để không thể trùng khớp ngẫu nhiên.")
    table(doc, ["Layer (W×H, channel → filter)", "Dữ liệu", "Giá trị đúng / tổng", "Ghi chú"], [
        ["8×4, 8 → 4", "ngẫu nhiên", "128 / 128", ""],
        ["8×4, 32 → 32", "ngẫu nhiên", "1.024 / 1.024", ""],
        ["8×4, 8 → 64", "ngẫu nhiên", "2.048 / 2.048", ""],
        ["8×4, 64 → 64", "ngẫu nhiên", "2.048 / 2.048", "Cấu hình trước đây sai filter 32–63"],
        ["14×14, 32 → 32", "ngẫu nhiên", "6.272 / 6.272", "= layer kiểu Conv2 của mốc đo"],
        ["28×28, 4 → 32", "ngẫu nhiên", "25.088 / 25.088", "= layer kiểu Conv1 của mốc đo"],
        ["MNIST Conv2 thật 14×14, 32 → 64", "ngẫu nhiên và dạng dốc", "12.544 / 12.544", "Trước đây sai một nửa số filter"],
        ["MNIST Conv3 thật 7×7, 64 → 64", "ngẫu nhiên", "3.136 / 3.136", "Ô đệm còn khác 0 (lỗi #9)"],
    ], widths=[5.2, 2.8, 3.2, 5.4], align_right=(2,))
    para(doc, "Ở mọi trường hợp: không thiếu, không trùng vị trí đầu ra, không có giá trị X, không vượt 20 bit; đối chứng với kernel chuyển vị "
              "cho kết quả sai hoàn toàn, chứng tỏ phép kiểm tra có khả năng phân biệt. Tham chiếu của testbench cũng khớp numpy.")

    doc.add_heading("3.5. Kiểm thử hồi quy sau các bản sửa", level=2)
    table(doc, ["Bộ test", "Trước các bản sửa", "Sau các bản sửa"], [
        ["34 test Conv (test_conv_const.py)", "19 PASS / 15 FAIL", "34 / 34 PASS"],
        ["63 test GEMM/Dense (test_gemm_layer.py)", "40 PASS / 23 FAIL", "40 / 23, giống hệt từng test (23 test là lỗi Dense có sẵn)"],
        ["19 test mới (test_mnist_layers.py)", "—", "Tất cả đạt kết quả mong đợi (2 trường hợp lỗi đã biết được đánh dấu)"],
        ["9 layer của mốc đo", "—", "9 / 9 PASS"],
        ["Lint Verilator", "478 cảnh báo", "477 (1 cảnh báo biến mất nhờ bản sửa), 0 cảnh báo mới"],
    ], widths=[5.6, 4.0, 7.0])

    # ---------------------------------------------------------------- 4
    doc.add_heading("4. Các lỗi đã sửa", level=1)
    table(doc, ["Lỗi", "Nguyên nhân", "Cách sửa và kiểm chứng"], [
        ["Bộ đếm vòng lặp đọc iact bị điều khiển từ 2 khối always (RTL). Mô phỏng đúng, phần cứng sau tổng hợp sai",
         "Bộ đếm reset ở một khối, đếm ở khối khác. Simulator cho phép; Vivado giữ giá trị reset và bỏ logic đếm, nên trên FPGA bộ đếm luôn "
         "bằng 0. Phát hiện từ CRITICAL WARNING của Vivado",
         "Chuyển 4 lệnh reset về khối đang đếm. Thí nghiệm giả lập phần cứng: trước sửa 6/9 layer mốc tính sai. Sau sửa: 0 chu kỳ thay đổi, "
         "+128 flip-flop, hết cảnh báo nghiêm trọng, vẫn 250 MHz"],
        ["Đầu vào 1 channel chỉ ra bias (RTL)",
         "Hồi quy của commit 23be043 (mã nguồn gốc): địa chỉ ghi dành cho chế độ 1 channel được tính nhưng không được dùng",
         "Dùng lại địa chỉ này cho chế độ 1 channel. Xác định bằng so sánh hai phiên bản mã nguồn gốc (trước commit: đúng; sau: sai)"],
        ["NUM_GLB_IACT = 3 cho kết quả sai (RTL)",
         "Cùng commit trên: cách ghi xoay vòng giữa các bank (dành cho layer Dense) bị áp cho cả layer Conv",
         "Chỉ xoay vòng với Dense; Conv ghi mọi bank như trước. 34/34 test Conv PASS (trước 19/34); Dense không đổi; +103 FF"],
        ["Mỗi lần gửi weight đọc gấp đôi số địa chỉ: mọi layer có hơn 4 channel tính sai với weight thật (phần mềm)",
         "Khoá used_wght_per_PE bị lặp trong cùng một dict Python; giá trị chưa đóng gói ghi đè giá trị đóng gói mà RTL cần. Weight "
         "hằng số trong test che lỗi",
         "Xoá dòng lặp (không sửa RTL). Kiểm tra độc lập từng word (mục 3.4). Giảm 16–25% chu kỳ ở các layer kiểu MNIST"],
        ["FSM GET_BIAS treo khi DMA có một chu kỳ trống trước word bias cuối (RTL, báo cáo 10/10)",
         "Điều kiện chuyển trạng thái không kiểm tra tín hiệu valid", "Thêm 1 điều kiện; 0 chu kỳ, 0 tài nguyên"],
        ["Lỗi testbench giải mã kết quả, bộ sinh tài liệu, CI lint (báo cáo 10/10)", "—", "Đã sửa từ trước"],
    ], widths=[4.4, 6.0, 6.2])
    para(doc, "Ngoài ra, lỗi 'IndexError với 64 filter' được xác định là giới hạn cấu hình chứ không phải lỗi mã: số filter của một layer "
              "phải không vượt quá QUANT_AMOUNT (layer 64 filter cần QUANT_AMOUNT = 64).")

    doc.add_heading("4.1. Lỗi chưa sửa", level=2)
    table(doc, ["Lỗi", "Ảnh hưởng", "Hướng xử lý"], [
        ["1 channel với ảnh rộng hơn một lượt x (#17)", "MNIST Conv1 thật (28×28, 1 channel) sai",
         "Phần mềm đệm thêm 1 channel 0 (không sửa RTL), hoặc sửa bộ ghi 1 channel trong RTL"],
        ["Ảnh rộng 7: ô đệm khác 0 (#9)", "MNIST Conv3: giá trị đúng nhưng kiểm tra luồng DMA thất bại; tốn băng thông", "Cần điều tra"],
        ["Layer Dense/FC ghi activation sai (#5)", "23/63 test Dense; chưa chạy được layer FC của MNIST", "Cần điều tra (có sẵn ở mã gốc)"],
        ["3 channel đầu vào (#7)", "Python xếp 3 byte mỗi pixel, RTL truyền theo cặp", "Phần mềm đệm số channel lẻ lên chẵn"],
        ["40/48 filter (#18b)", "Sai; MNIST không dùng", "Phần mềm báo 768 word nhưng tạo tham chiếu 1.024 dòng; cần điều tra"],
        ["Chỉ số filter của bộ lượng tử không tăng (#12)", "Lượng tử theo từng filter chưa hoạt động", "Phát hiện qua đọc mã, cần test"],
        ["Cảnh báo có thể gây sai khác mô phỏng/phần cứng (#11, #14, #15)",
         "Cắt bit địa chỉ weight; gán blocking/non-blocking lẫn lộn; set/reset cùng mức ưu tiên", "Phân tích như đã làm với lỗi bộ đếm"],
        ["Wrapper AXI không biên dịch (#16)", "Cần khi đóng gói IP chạy trên board", "Sửa khi chuẩn bị chạy board"],
    ], widths=[5.0, 5.6, 6.0])

    # ---------------------------------------------------------------- 5
    doc.add_heading("5. Định hướng và kế hoạch sắp tới", level=1)
    table(doc, ["#", "Việc", "Lý do và kết quả mong đợi"], [
        ["1", "Gửi bias theo filter (Giai đoạn 1.1)",
         "Bias chiếm 26% độ trễ layer kiểu Conv1 với hiệu suất bus gần 0%. Thiết kế: bảng bias trên chip, phần cứng tự sinh lại chuỗi ghi "
         "bộ đệm. Ước tính −23% chu kỳ layer này, lưu lượng DMA pha bias giảm khoảng 900 lần, chi phí khoảng +2% flip-flop"],
        ["2", "Chạy đủ mạng MNIST", "Sửa #17 (đệm channel), #9 và #5 để chạy cả mạng thật và đo độ trễ đầu cuối"],
        ["3", "Đọc kết quả dạng INT8 (Giai đoạn 1.2)", "Readout chiếm 26% ở layer kiểu Conv1; giảm khoảng 4 lần số word ra"],
        ["4", "Thu nhỏ bộ đệm psum", "Giải phóng khoảng 100 BRAM36 (1/3 chip) để thêm cluster hoặc bộ đệm; có thể tăng tần số"],
        ["5", "Đóng gói weight (Giai đoạn 1.3)", "Hiệu suất bus weight 15–30%, weight chiếm 12–19% ở layer sâu"],
        ["6", "Chạy chồng pha nạp và tính toán (Giai đoạn 2)", "Che độ trễ nạp dữ liệu sau khi đã giảm lưu lượng"],
        ["7", "Đo trên board thật (khi có board)", "Hiệu chỉnh mô hình bộ nhớ, đo độ trễ tổng có phần mềm"],
    ], widths=[0.8, 5.0, 10.8])
    para(doc, "Phương pháp đánh giá mỗi bước: test chức năng và kiểm tra độc lập từng word; so sánh chu kỳ và word DMA tự động với mốc "
              "baseline_2026-10-15 (bộ nhớ lý tưởng và bộ nhớ mô hình hoá); Yosys để so nhanh tài nguyên; Vivado ở các mốc quan trọng. "
              "Mọi thay đổi RTL chỉ thực hiện sau khi được đồng ý.")

    # ---------------------------------------------------------------- 6
    doc.add_heading("6. Hạn chế hiện tại", level=1)
    bullets(doc, [
        "Số liệu chu kỳ lấy từ mô phỏng RTL; độ trễ thật trên board sẽ lớn hơn do DDR, AXI DMA và phần mềm điều khiển.",
        "Tổng hợp là out-of-context (chỉ khối bộ tăng tốc, chưa có hệ thống ARM + AXI DMA); tần số 250 MHz là của khối bộ tăng tốc.",
        "Chưa chạy được mạng MNIST đầy đủ (các lỗi #17, #9, #5).",
        "Mô hình bộ nhớ chưa được hiệu chỉnh theo board thật.",
    ])

    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
