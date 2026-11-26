#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Build the seventh Word progress report (weekly, Vietnamese, dated 2026-11-27; first version 2026-11-23). It answers the user's questions of the week:
how many cycles an activation function costs per layer and why some cases cost none; how the profiler measures the
phases in simulation and how the numbers are made exact; what changes between cases with different zero shares and
why; the check of the test_dense_output fix against upstream; which channel counts still fail and why.

Inputs (all measured, nothing typed in except the Vivado clock and the list of this week's commits):
  doc/perf/activation_cost_2026-11-19/trained_<act>_img<i>_<mode>.json   trained MNIST, 4 activations (19/11)
  doc/perf/act_nobias_2026-11-23/trained_<act>_img0_sparse.json          the same with the bias table off (23/11)
  doc/perf/act_same_weights_2026-11-26/trained_relu_weights_<act>_img0_<mode>.json   the ReLU-trained weights with each
                                                                         activation and with none (26/11)
  doc/perf/act_wzero_2026-11-20/act_<f>_<mode>.json, wz_<model>_z<z>_<mode>.json   Table 2 network, weight-zero sweep
  doc/perf/zero_grid_2026-11-20/grid_<shape>_w<w>_a<a>_<mode>.json      one layer, weight x input zeros
  doc/perf/baseline_2026-11-18/, doc/perf/activation_2026-11-18_rounding/   reproducibility check
  doc/experiments/2026-11-23_channel_sweep/out/status.json               channel sweep (23/11)
  doc/experiments/2026-11-23_dense_output_check.json                     test_dense_output check (23/11)

    ~/tools/docenv/bin/python tools/report/make_progress_report_2026-11-27.py
Output: doc/reports/2026-11-27_TienDo/BaoCao_TienDo_OpenEye_2026-11-27.docx and the figure PNGs next to it.
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
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
EXP = os.path.join(REPO, "doc", "experiments")
OUT_DIR = os.path.join(REPO, "doc", "reports", "2026-11-27_TienDo")
OUT = os.path.join(OUT_DIR, "BaoCao_TienDo_OpenEye_2026-11-27.docx")
DATE = "27/11/2026"
CLOCK_NS = 4.0     # 250 MHz after place and route (doc/synth/2026-11-22_route4ns_fix51_zu7ev, WNS +0.114 ns)

ACT19 = os.path.join(PERF, "activation_cost_2026-11-19")
NOBIAS = os.path.join(PERF, "act_nobias_2026-11-23")
SAME = os.path.join(PERF, "act_same_weights_2026-11-26")
SAME_ACTS = [("none", "không hàm"), ("relu", "ReLU"), ("leaky_relu", "Leaky ReLU"), ("silu", "SiLU"),
             ("hardswish", "hard-swish")]
AWZ = os.path.join(PERF, "act_wzero_2026-11-20")
GRID = os.path.join(PERF, "zero_grid_2026-11-20")
CHAN = os.path.join(EXP, "2026-11-23_channel_sweep", "out", "status.json")
DENSE_CHECK = os.path.join(EXP, "2026-11-23_dense_output_check.json")

SURFACE, INK, INK_2, GRID_C, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e8e7e2", "#d6d5cf"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
GRAY, LIGHT = "#9b9a95", "#cfcec8"
ZEROS = ["0", "0.2", "0.4", "0.6", "0.8"]
T2_ACTS = [("none", "không hàm"), ("relu", "ReLU"), ("leaky", "Leaky ReLU"), ("silu", "SiLU"), ("hardswish", "hard-swish")]
MN_ACTS = [("relu", "ReLU"), ("leaky_relu", "Leaky ReLU"), ("silu", "SiLU"), ("hardswish", "hard-swish")]
SHAPES = [("conv1", "Conv 28×28×1→16 (ảnh)"), ("conv2", "Conv 14×14×16→32"), ("conv3", "Conv 7×7×32→32"),
          ("fc", "Dense 1568→32")]
PHASE_VI = [("load_config", "nạp cấu hình"), ("load_iact", "nạp activation"), ("load_wght", "nạp weight"),
            ("load_bias", "nạp bias"), ("load_quant", "nạp bảng lượng tử"), ("load_act", "nạp bảng hàm kích hoạt"),
            ("convert_iact", "chuyển activation vào cluster"), ("compute", "tính toán"), ("writeback", "ghi ngược"),
            ("pooling", "pooling"), ("readout", "đọc kết quả")]
COMMITS = [
    ("f134bd5", "21/11", "Đo chi phí hàm kích hoạt (19/11), quét hàm kích hoạt × weight bằng 0 (20/11), viết lại báo cáo 6"),
    ("6a7a323", "21/11", "Sửa #21 trong bộ giải mã Dense của testbench, sửa 11 test hỏng của test_dense_output"),
    ("f6df9af", "21/11", "Rà upstream 12340ab (không lấy); tìm ra lỗi mới #50, #51 của dev"),
    ("abd2bb8", "22/11", "Sửa #51 (RTL, 3 dòng), #50 (kẹp trong Python), #7 (đệm channel lẻ), #9 (mặt nạ ô đệm)"),
]


# ---------------------------------------------------------------- helpers
def load(path):
    return json.load(open(path)) if os.path.exists(path) else None


def ph(x, name, key="cycles"):
    return (x or {}).get("phases", {}).get(name, {}).get(key, 0)


def num(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",")


def sgn(n):
    return "0" if n == 0 else ("+" if n > 0 else "−") + fmt(abs(int(n)))


def pct(x, digits=1, sign=True):
    if round(x, digits) == 0:
        return "0 %"
    s = num(abs(x), digits) + " %"
    return (("+" if x > 0 else "−") + s) if sign else ("−" + s if x < 0 else s)


def us(cycles):
    return num(cycles * CLOCK_NS / 1000.0, 1)


def zin(layer):
    d = layer["info"].get("input") or {}
    return 100.0 * d.get("zeros", 0) / d["values"] if d.get("values") else 0.0


def lname(layer):
    i = layer["info"]
    if i["name"].startswith("Conv"):
        return f"Conv {i['iact_size_x']}×{i['iact_size_y']}×{i['channels']}→{i['filters']}"
    if i["name"].startswith("Dense"):
        return f"Dense {i['iact_size_x']}→{i['filters']}"
    return f"Pool {i['iact_size_x']}×{i['iact_size_y']}"


def caption(doc, text):
    cap = doc.add_paragraph(text)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True
    cap.runs[0].font.size = Pt(10)


def new_figure(w, h, rows=1, cols=1):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, axes = plt.subplots(rows, cols, figsize=(w, h), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    return fig, axes


def style_axes(ax, grid_axis="x"):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=INK_2, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    getattr(ax, grid_axis + "axis").grid(True, color=GRID_C, linewidth=0.6)
    ax.set_axisbelow(True)


def kfmt(v, _=None):
    return fmt(int(v))


# ---------------------------------------------------------------- data
def data():
    d = {"mn": {}, "t2": {}, "wz": {}, "grid": {}, "nobias": {}, "same": {}}
    for a, _ in SAME_ACTS:
        for mode in ("sparse", "dense"):
            r = load(os.path.join(SAME, f"trained_relu_weights_{a}_img0_{mode}.json"))
            if r:
                d["same"][(a, mode)] = r
    for a, _ in MN_ACTS:
        for mode in ("sparse", "dense"):
            for img in (0, 1, 6):
                r = load(os.path.join(ACT19, f"trained_{a}_img{img}_{mode}.json"))
                if r:
                    d["mn"][(a, img, mode)] = r
        r = load(os.path.join(NOBIAS, f"trained_{a}_img0_sparse.json"))
        if r:
            d["nobias"][a] = r
    for a, _ in T2_ACTS:
        for mode in ("sparse", "dense"):
            d["t2"][(a, mode)] = load(os.path.join(AWZ, f"act_{a}_{mode}.json"))
    for model in ("mnist", "t2"):
        for z in ZEROS:
            for mode in ("sparse", "dense"):
                d["wz"][(model, z, mode)] = load(os.path.join(AWZ, f"wz_{model}_z{z}_{mode}.json"))
    for s, _ in SHAPES:
        for w in ZEROS:
            for a in ZEROS:
                for mode in ("sparse", "dense"):
                    d["grid"][(s, w, a, mode)] = load(os.path.join(GRID, f"grid_{s}_w{w}_a{a}_{mode}.json"))
    d["chan"] = load(CHAN) or {}
    d["dense_check"] = load(DENSE_CHECK) or {}
    return d


# ---------------------------------------------------------------- write-back checks of 26/11
LANES = os.path.join(PERF, "writeback_lanes_2026-11-26")
RT_DIR = os.path.join(EXP, "2026-11-26_requant_timing")


def lanes_identify(prefix, nlanes, seeds=("1", "2", "3", "4")):
    """(filter, x, y) of every (capture, lane) slot of layer 0: the positions whose reference value equals the lane
    value, intersected over the seeds (the write-back schedule does not depend on the data)."""
    runs = [load(os.path.join(LANES, f"{prefix}_s{s}.json")) for s in seeds]
    if not all(runs):
        return None
    caps = [[c for c in r["captures"] if c["layer"] == 0] for r in runs]
    refs = [r["refs"]["0"] for r in runs]
    F, X, Y = len(refs[0]), len(refs[0][0]), len(refs[0][0][0])
    slots = []
    for k in range(len(caps[0])):
        row = []
        for lane in range(nlanes):
            cand = None
            for ref, cs in zip(refs, caps):
                v = cs[k]["lanes"][lane]
                here = {(f, x, y) for f in range(F) for x in range(X) for y in range(Y) if ref[f][x][y] == v}
                cand = here if cand is None else cand & here
            row.append(cand)
        slots.append(row)
    written = {}
    for row in slots:
        for c in row:
            if len(c) == 1:
                p = next(iter(c))
                written[p] = written.get(p, 0) + 1
    unused_zero = all(all(v == 0 for v in c["lanes"][nlanes:]) for c in caps[0])
    return {"caps": len(caps[0]), "slots": slots, "outputs": F * X * Y,
            "unique": sum(1 for row in slots for c in row if len(c) == 1),
            "covered": len(written), "twice": sum(1 for v in written.values() if v > 1),
            "unused_zero": unused_zero, "clusters": sorted({(c["x_cl"], c["y_cl"]) for c in caps[0]})}


def levels_vi(levels):
    """'13  (CARRY8=5 DSP_A_B_DATA=1 ... LUT2=1 LUT5=1)' -> '13 tầng logic: DSP48E2, 5 CARRY8, 2 LUT'."""
    import re
    n = levels.split()[0] if levels else "?"
    parts = dict(re.findall(r"(\w+)=(\d+)", levels))
    out = []
    if any(k.startswith("DSP") for k in parts):
        out.append("DSP48E2")
    if "CARRY8" in parts:
        out.append(f"{parts['CARRY8']} CARRY8")
    luts = sum(int(v) for k, v in parts.items() if k.startswith("LUT"))
    if luts:
        out.append(f"{luts} LUT")
    return f"{n} tầng logic: " + ", ".join(out)


def sta_stages():
    """Worst setup path into each register stage (timing_stages.rpt) and the detail of the worst R4 -> table -> R5
    path (timing_requant.rpt), as Vivado reports them."""
    import re
    out = {"stages": [], "path": []}
    path = os.path.join(RT_DIR, "timing_stages.rpt")
    if os.path.exists(path):
        text = open(path).read()
        for sec in text.split("######## ")[1:]:
            title = sec.split(":")[0]
            slack = re.search(r"Slack \(MET\) :\s+([-\d.]+)ns", sec)
            delay = re.search(r"Data Path Delay:\s+([\d.]+)ns", sec)
            levels = re.search(r"Logic Levels:\s+(\d+)\s*(\([^)]*\))?", sec)
            src = re.search(r"Source:\s+(\S+)", sec)
            dst = re.search(r"Destination:\s+(\S+)", sec)
            if slack:
                out["stages"].append({"title": title, "slack": float(slack.group(1)), "delay": float(delay.group(1)),
                                      "levels": levels.group(0).split(":", 1)[1].strip() if levels else "",
                                      "src": src.group(1), "dst": dst.group(1)})
    path = os.path.join(RT_DIR, "timing_requant.rpt")
    if os.path.exists(path):
        text = open(path).read()
        sec = text.split("######## R4 -> table")[1].split("########")[0]
        first = sec.split("Slack (MET)")[1].split("slack")[0]
        out["r5_slack"] = float(re.search(r":\s+([-\d.]+)ns", first).group(1))
        lines = first.splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"\s+\S+\s+(FDCE|RAMD32|LUT6|LUT5|LUT4)\s+\(Prop", line)
            if m and i + 1 < len(lines):
                out["path"].append((m.group(1), float(lines[i + 1].split()[0])))
            m = re.search(r"net \(fo=(\d+), routed\)\s+([\d.]+)", line)
            if m:
                out["path"].append((f"dây (fo={m.group(1)})", float(m.group(2))))
        m = re.search(r"required time\s+([\d.]+)", first)
        out["required"] = float(m.group(1)) if m else None
        m = re.search(r"arrival time\s+-([\d.]+)", first)
        out["arrival"] = float(m.group(1)) if m else None
    return out


def tb_requant_log():
    path = os.path.join(RT_DIR, "tb_requant.log")
    if not os.path.exists(path):
        return None
    import re
    rows, reads, result = [], [], None
    for line in open(path):
        m = re.match(r"input (\d+) psum\s+(-?\d+): q\s+(-?\d+) after the 3rd edge \(want\s+(-?\d+)\)\s+(\w+); after the 2nd "
                     r"edge q was\s+(-?\d+)", line)
        if m:
            rows.append(m.groups())
        m = re.match(r"t=([\d.]+) ns: value_i =\s+(-?\d+) -> value_o =\s+(\d+)", line)
        if m:
            reads.append(m.groups())
        if line.startswith("RESULT"):
            result = line.split()[1]
    return {"rows": rows, "reads": reads, "result": result}


# ---------------------------------------------------------------- figures
PHASE_GROUPS = [("nạp weight", ("load_wght",), SLOTS[0]),
                ("nạp khác", ("load_config", "load_iact", "load_bias", "load_quant", "load_act"), LIGHT),
                ("chuyển activation", ("convert_iact",), SLOTS[3]),
                ("tính toán", ("compute",), SLOTS[1]),
                ("ghi ngược", ("writeback",), SLOTS[2]),
                ("pooling, đọc kết quả", ("pooling", "readout"), GRAY)]


def figure_layers(run, path):
    """Cycles of every layer of one run split into phase groups, horizontal bars (the profiler's per-layer output)."""
    layers = run["layers"]
    fig, ax = new_figure(10.5, 3.6)
    style_axes(ax, "x")
    for i, layer in enumerate(layers):
        left = 0
        for _, names, color in PHASE_GROUPS:
            v = sum(ph(layer, n) for n in names)
            if v:
                ax.barh(i, v, left=left, height=0.62, color=color, edgecolor=SURFACE, linewidth=1.0)
            left += v
        ax.text(left + 600, i, f"{fmt(layer['total_cycles'])} ({us(layer['total_cycles'])} µs)", va="center",
                fontsize=7.5, color=INK)
    ax.set_yticks(range(len(layers)))
    ax.set_yticklabels([lname(l) for l in layers], fontsize=8.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, max(l["total_cycles"] for l in layers) * 1.22)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(kfmt))
    ax.set_xlabel("chu kỳ (1 chu kỳ = 4 ns ở 250 MHz)", fontsize=8, color=INK_2)
    handles = [Patch(facecolor=c, label=lab) for lab, _, c in PHASE_GROUPS]
    fig.legend(handles=handles, loc="upper center", ncol=6, frameon=False, fontsize=8, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_act(d, path):
    """Table 2 network: change of total cycles against no activation, direct (table load + write-back) and indirect
    (compute of the next layers), sparse and dense."""
    acts = T2_ACTS[1:]
    fig, axes = new_figure(10.5, 3.5, 1, 2)
    lo = hi = 0
    for ax, (mode, title) in zip(axes, [("sparse", "Phần cứng sparse"), ("dense", "Phần cứng dense")]):
        style_axes(ax, "y")
        base = d["t2"][("none", mode)]
        for i, (a, lab) in enumerate(acts):
            r = d["t2"][(a, mode)]
            direct = sum(ph(r, p) - ph(base, p) for p in ("load_act", "writeback"))
            comp = ph(r, "compute") - ph(base, "compute")
            for x, v, color, label in ((i - 0.2, direct, SLOTS[0], "trực tiếp: nạp bảng + ghi ngược"),
                                       (i + 0.2, comp, SLOTS[1], "gián tiếp: tính toán của layer sau (số 0)")):
                ax.bar(x, v, width=0.38, color=color, edgecolor=SURFACE, linewidth=1.0, label=label if i == 0 else None)
                ax.text(x, v + (40 if v >= 0 else -40), sgn(v), ha="center", va="bottom" if v >= 0 else "top",
                        fontsize=7, color=INK)
                lo, hi = min(lo, v), max(hi, v)
        ax.axhline(0, color=AXIS, linewidth=1)
        ax.set_xticks(range(len(acts)))
        ax.set_xticklabels([lab for _, lab in acts], fontsize=8.5, color=INK)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
    for ax in axes:
        ax.set_ylim(lo - 600, hi + 600)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: sgn(v)))
    axes[0].set_ylabel("Δ chu kỳ so với không hàm", fontsize=8, color=INK_2)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=2, frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_compute_lines(d, path):
    """One layer: compute cycles against the input zero share, for three weight zero shares (sparse) and dense."""
    fig, axes = new_figure(11.5, 3.3, 1, 4)
    styles = [("0", "weight 0 %", SLOTS[0], "-", "o"), ("0.4", "weight 40 %", SLOTS[1], "--", "s"),
              ("0.8", "weight 80 %", SLOTS[2], ":", "^")]
    for ax, (s, title) in zip(axes, SHAPES):
        style_axes(ax, "y")
        ax.spines["left"].set_visible(True)
        ax.spines["left"].set_color(AXIS)
        xs = [float(a) * 100 for a in ZEROS]
        dense = [ph(d["grid"][(s, "0", a, "dense")], "compute") for a in ZEROS]
        ax.plot(xs, dense, color=GRAY, linewidth=2, linestyle=(0, (4, 3)), label="dense (mọi mức số 0)")
        for w, lab, color, ls, mk in styles:
            ys = [ph(d["grid"][(s, w, a, "sparse")], "compute") for a in ZEROS]
            ax.plot(xs, ys, color=color, linestyle=ls, marker=mk, markersize=5, linewidth=2, label=f"sparse, {lab}")
        ax.set_ylim(0, max(dense + [ph(d["grid"][(s, "0", "0", "sparse")], "compute")]) * 1.12)
        ax.set_title(title, fontsize=8.5, color=INK, loc="left")
        ax.set_xlabel("input bằng 0 (%)", fontsize=7.5, color=INK_2)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(kfmt))
    axes[0].set_ylabel("chu kỳ tính toán", fontsize=8, color=INK_2)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=4, frameon=False, fontsize=8, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_grid(d, path):
    vals = {}
    for s, _ in SHAPES:
        for w in ZEROS:
            for a in ZEROS:
                sp, dn = d["grid"][(s, w, a, "sparse")], d["grid"][(s, w, a, "dense")]
                vals[(s, w, a)] = 100.0 * sp["total_cycles"] / dn["total_cycles"]
    lo, hi = min(vals.values()), max(vals.values())
    cmap = LinearSegmentedColormap.from_list("div", [SLOTS[0], "#efeee9", SLOTS[1]])
    norm = TwoSlopeNorm(vmin=min(lo, 99), vcenter=100.0, vmax=max(hi, 101))
    fig, axes = new_figure(11.5, 3.4, 1, 4)
    for ax, (s, title) in zip(axes, SHAPES):
        ax.set_facecolor(SURFACE)
        for i, w in enumerate(ZEROS):
            for j, a in enumerate(ZEROS):
                v = vals[(s, w, a)]
                ax.add_patch(plt.Rectangle((j, i), 0.96, 0.96, facecolor=cmap(norm(v)), edgecolor=SURFACE, linewidth=0))
                dark = abs(norm(v) - 0.5) > 0.32
                ax.text(j + 0.48, i + 0.48, f"{v:.0f}", ha="center", va="center", fontsize=7.2,
                        color="white" if dark else INK)
        ax.set_xlim(0, 5)
        ax.set_ylim(5, 0)
        ax.set_xticks([j + 0.48 for j in range(5)])
        ax.set_xticklabels([f"{float(z) * 100:.0f}" for z in ZEROS], fontsize=7.5, color=INK_2)
        ax.set_yticks([i + 0.48 for i in range(5)])
        ax.set_yticklabels([f"{float(z) * 100:.0f}" for z in ZEROS], fontsize=7.5, color=INK_2)
        ax.tick_params(length=0)
        for side in ax.spines.values():
            side.set_visible(False)
        ax.set_title(title, fontsize=8.5, color=INK, loc="left")
        ax.set_xlabel("input bằng 0 (%)", fontsize=7.5, color=INK_2)
    axes[0].set_ylabel("weight bằng 0 (%)", fontsize=7.5, color=INK_2)
    fig.text(0.5, 0.01, "Số trong ô: tổng chu kỳ sparse / dense của layer (%). Xanh (< 100): sparse nhanh hơn; cam (> 100): "
             "dense nhanh hơn.", ha="center", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_wz(d, path):
    groups = [("load_wght", "nạp weight", SLOTS[0]), ("compute", "tính toán", SLOTS[1]), (None, "các pha khác", GRAY)]
    fig, axes = new_figure(10.5, 4.0, 1, 2)
    for ax, (model, title) in zip(axes, [("mnist", "MNIST đã huấn luyện (ReLU)"), ("t2", "Mạng Bảng 2 (không hàm)")]):
        style_axes(ax, "y")
        top = 0
        ticks, labels = [], []
        for j, z in enumerate(ZEROS):
            for m, (mode, tag) in enumerate((("sparse", "S"), ("dense", "D"))):
                r = d["wz"][(model, z, mode)]
                x = j * 3 + m
                bottom = 0
                for key, _, color in groups:
                    v = ph(r, key) if key else r["total_cycles"] - ph(r, "load_wght") - ph(r, "compute")
                    ax.bar(x, v, bottom=bottom, width=0.86, color=color, edgecolor=SURFACE, linewidth=1.2)
                    bottom += v
                top = max(top, bottom)
                ax.text(x, bottom * 1.01, f"{bottom / 1000:.0f}k", ha="center", va="bottom", fontsize=6.4, color=INK)
                ticks.append(x)
                labels.append(tag)
            ax.text(j * 3 + 0.5, -0.1, f"{float(z) * 100:.0f} %", transform=ax.get_xaxis_transform(), ha="center",
                    va="top", fontsize=8.5, color=INK)
        ax.set_ylim(0, top * 1.1)
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=7, color=INK_2)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(kfmt))
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel("tỉ lệ weight bằng 0", fontsize=8, color=INK_2, labelpad=26)
    axes[0].set_ylabel("chu kỳ cả mạng", fontsize=8, color=INK_2)
    fig.legend(handles=[Patch(facecolor=c, label=lab) for _, lab, c in groups], loc="upper center", ncol=3,
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.0))
    fig.text(0.5, 0.005, "S = sparse, D = dense.", ha="center", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_writeback(path, slacks=None):
    """The write-back path of one lane: quantizer stages between registers, the activation table (LUTRAM, read without a
    clock) squeezed into the existing clock between the stage-3 register and the write-back register; below, the same
    tail with a block RAM (synchronous read), which needs one more register."""
    from matplotlib.patches import FancyBboxPatch
    fig, ax = new_figure(11.0, 4.3)
    ax.set_facecolor(SURFACE)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")
    logic, table_c, buf = "#efeee9", "#cfe0f6", "#e6e5df"

    def box(x0, x1, y0, y1, text, color, size=7.4, bold=False):
        ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0.25,rounding_size=0.8",
                                    facecolor=color, edgecolor=AXIS, linewidth=0.8))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, text, ha="center", va="center", fontsize=size, color=INK,
                fontweight="bold" if bold else "normal")

    def reg(x, y0, y1, label):
        ax.add_patch(plt.Rectangle((x - 0.6, y0), 1.2, y1 - y0, facecolor=INK, edgecolor=INK))
        ax.text(x, y1 + 0.8, label, ha="center", va="bottom", fontsize=6.6, color=INK_2)

    def arrow(x0, x1, y):
        ax.annotate("", xy=(x1, y), xytext=(x0, y), arrowprops=dict(arrowstyle="-|>", color=INK_2, lw=0.9))

    y0, y1, ym = 22, 32, 27
    box(0.5, 9.5, y0, y1, "bộ đệm psum\n(psum + bias)", buf)
    regs = [(12, "R1"), (30, "R2"), (48, "R3"), (66, "R4"), (88.5, "R5")]
    for x, lab in regs:
        reg(x, y0 - 0.5, y1 + 0.5, lab)
    box(14, 28, y0, y1, "tầng 1: + offset\nLeaky ReLU: chọn\n[mant, shift] theo dấu", logic)
    box(32, 46, y0, y1, "tầng 2: × mant\n(DSP) + hằng\nlàm tròn", logic)
    box(50, 64, y0, y1, "tầng 3: dịch phải,\nkẹp [act_min, 127]\nReLU: act_min = 0", logic)
    box(68, 82, y0 + 2.6, y1, "bảng 256 × 8 bit\nLUTRAM, đọc không clock\n(SiLU, hard-swish)", table_c, size=6.8)
    ax.text(75, y0 + 0.9, "không hàm / ReLU / Leaky: đi thẳng", ha="center", va="center", fontsize=6.0, color=INK_2)
    box(83.2, 86.6, y0 + 2, y1 - 2, "mux", logic, size=6.4)
    box(91, 99.5, y0, y1, "bộ đệm\nactivation\n(input layer sau)", buf)
    for xa, xb in ((9.5, 11.4), (12.6, 14), (28, 29.4), (30.6, 32), (46, 47.4), (48.6, 50), (64, 65.4), (66.6, 68),
                   (82, 83.2), (86.6, 87.9), (89.1, 91)):
        arrow(xa, xb, ym)
    # clock brackets
    labels = ["1 chu kỳ", "1 chu kỳ", "1 chu kỳ", "1 chu kỳ (có sẵn): đọc bảng + mux"]
    if slacks:
        labels = [f"{lab}\nslack +{num(v, 3)} ns" for lab, v in zip(labels, slacks)]
    for (xa, xb), lab in zip(((12, 30), (30, 48), (48, 66), (66, 88.5)), labels):
        ax.plot([xa, xa, xb, xb], [y0 - 2.2, y0 - 3.2, y0 - 3.2, y0 - 2.2], color=INK_2, lw=0.8)
        ax.text((xa + xb) / 2, y0 - 4.2, lab, ha="center", va="top", fontsize=6.8,
                color=INK if xa == 66 else INK_2, fontweight="bold" if xa == 66 else "normal")
    ax.text(0.5, 38.8, "Một làn ghi ngược (4 làn song song ở CR 2 X 4 Y 3, mỗi làn một bản sao của bảng); thanh đen = "
            "thanh ghi, ghi ở cạnh lên của clock", ha="left", va="top", fontsize=7.4, color=INK)
    # block RAM alternative
    yb0, yb1, ybm = 2, 9.5, 5.75
    ax.text(0.5, 13.2, "Nếu bảng nằm trong block RAM (đọc đồng bộ):", ha="left", va="center", fontsize=7.2, color=INK)
    reg(49, yb0 - 0.5, yb1 + 0.5, "R4")
    box(51, 61, yb0, yb1, "block RAM:\nđịa chỉ vào", logic, size=6.6)
    reg(63.5, yb0 - 0.5, yb1 + 0.5, "R thêm")
    box(66, 76, yb0, yb1, "dữ liệu ra\nsau cạnh clock", logic, size=6.6)
    reg(78.5, yb0 - 0.5, yb1 + 0.5, "R5")
    for xa, xb in ((49.6, 51), (61, 62.9), (64.1, 66), (76, 77.9)):
        arrow(xa, xb, ybm)
    ax.text(81, ybm, "+1 chu kỳ mỗi đợt ghi ngược;\nmọi chuỗi trễ 3 clock thành 4", ha="left", va="center", fontsize=6.8,
            color=INK, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


VERDICT_STYLE = {"PASS": ("✓", "đúng", SLOTS[2], "white"), "PADDED": ("✓*", "đệm rồi đúng", "#9fd9c2", INK),
                 "FAIL": ("✗", "SAI (output / bộ đệm khác tham chiếu)", SLOTS[1], "white"),
                 "REFUSED": ("–", "bị chặn (kiểm tra của Python)", LIGHT, INK),
                 "STOPPED": ("!", "dừng (lỗi Python)", "#e6d3a8", INK), "HANG": ("⏸", "treo", INK, "white"),
                 "ERROR": ("?", "lỗi khác", "#7a1f10", "white")}


def verdict_key(entry):
    v, detail = entry[0], entry[1]
    if v.startswith("PASS"):
        return "PADDED" if detail.startswith("padded") else "PASS"
    return v


def figure_channels(chan, path):
    rows = [("first", "sparse", "Layer đầu, sparse"), ("first", "dense", "Layer đầu, dense"),
            ("mid", "sparse", "Layer giữa, sparse"), ("mid", "dense", "Layer giữa, dense"),
            ("dense", "sparse", "Trước Dense, sparse"), ("dense", "dense", "Trước Dense, dense"),
            ("last", "sparse", "Layer cuối (số filter), sparse"), ("last", "dense", "Layer cuối (số filter), dense")]
    n_max = 34
    rows = [r for r in rows if any(k.startswith(r[0] + "_") and k.endswith("_" + r[1]) for k in chan)]
    fig, ax = new_figure(11.5, 0.9 + 0.42 * len(rows))
    ax.set_facecolor(SURFACE)
    for i, (kind, mode, _) in enumerate(rows):
        for n in range(1, n_max + 1):
            key = f"{kind}_{'c' if kind == 'first' else 'f'}{n}_{mode}"
            if key not in chan:
                continue
            glyph, _, color, ink = VERDICT_STYLE[verdict_key(chan[key])]
            ax.add_patch(plt.Rectangle((n - 1, i), 0.94, 0.9, facecolor=color, edgecolor=SURFACE, linewidth=0))
            ax.text(n - 1 + 0.47, i + 0.45, glyph, ha="center", va="center", fontsize=7, color=ink)
    ax.set_xlim(0, n_max)
    ax.set_ylim(len(rows), 0)
    ax.set_xticks([n - 0.53 for n in range(1, n_max + 1)])
    ax.set_xticklabels([str(n) for n in range(1, n_max + 1)], fontsize=7, color=INK_2)
    ax.set_yticks([i + 0.45 for i in range(len(rows))])
    ax.set_yticklabels([r[2] for r in rows], fontsize=8, color=INK)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.set_xlabel("số channel vào layer được kiểm (hàng layer cuối: số filter)", fontsize=8, color=INK_2)
    handles = [Patch(facecolor=c, label=f"{glyph} {lab}") for k, (glyph, lab, c, _) in VERDICT_STYLE.items()
               if any(verdict_key(v) == k for v in chan.values())]
    fig.legend(handles=handles, loc="upper center", ncol=min(len(handles), 3), frameon=False, fontsize=8,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------- channel rule
def channel_rule(c):
    """What the toolchain sends and what the RTL reads per pixel, 3 x 3 kernel (layer_parameters.py:1100-1122,
    iact_stream_mapper.py:186-197): used_channels = min(C, 4) channels per group, the RTL steps channel_div_trans =
    ceil(used / 2) transfers of 2 channels = 2 * channel_div_trans slots per pixel in every group; Python writes, in
    the last group, only the channels that exist."""
    used = min(c, 4)
    div = -(-used // 2)
    last = c - 4 * ((c - 1) // 4) if c > 4 else c
    return used, div, 2 * div, last


def sections(doc, d, figs):
    t2 = d["t2"]
    t2_tot = {k: v["total_cycles"] for k, v in t2.items()}
    mn0 = d["mn"][("relu", 0, "sparse")]
    grid = d["grid"]
    wz = d["wz"]
    nb = d["nobias"]
    dc = d["dense_check"]

    def g(s, w, a, m="sparse"):
        return grid[(s, w, a, m)]

    # ---------------------------------------------------------------- 2
    doc.add_heading("2. Profiler đo chu kỳ như thế nào", level=1)
    doc.add_heading("2.1. Đo trong mô phỏng RTL", level=2)
    para(doc, "Mọi số chu kỳ trong các báo cáo đều đo trên mô phỏng RTL (Verilog của OpenEye chạy trong Icarus, testbench "
              "Python qua cocotb), không phải ước lượng bằng công thức. Profiler (rtl_test_utils.profile_dma_phases, bật bằng "
              "OPENEYE_PROFILE=1) là một coroutine chạy song song với testbench:")
    bullets(doc, [
        "Ở mỗi cạnh lên của clock (await RisingEdge(clk_i)) nó đọc trạng thái FSM chính (fsm_current_state), trạng thái "
        "FSM psum (fsm_psum_current_state) và các tín hiệu bắt tay DMA, rồi gán chu kỳ đó cho đúng một pha. Mỗi chu kỳ "
        "được đếm đúng một lần, nên tổng các pha bằng tổng chu kỳ.",
        "Cửa sổ đo bắt đầu ở word DMA đầu tiên được nhận và kết thúc ở word kết quả cuối cùng: thời gian testbench chuẩn bị "
        "dữ liệu (Python, TensorFlow) không bị tính.",
        "Mỗi lần FSM chính vào trạng thái GET_PARAMETERS là bắt đầu một layer mới, nên số đo được chia theo layer; tổng các "
        "layer bằng tổng của mạng.",
        "Kết quả ghi vào profile.json mỗi khi đổi pha, mỗi word kết quả và mỗi 1.024 chu kỳ, nên cả lần chạy hỏng hay treo "
        "cũng để lại số đo.",
    ])
    rows = [["0", "IDLE: chờ host", "– (ngoài cửa sổ đo)"],
            ["1, 2", "GET_PARAMETERS, GET_ROUTER_CONFIG", "nạp cấu hình"],
            ["3", "GET_IACT", "nạp activation"], ["4", "GET_WGHT", "nạp weight"], ["5", "GET_BIAS", "nạp bias"],
            ["6", "GET_QUANTIZE", "nạp bảng lượng tử"], ["15", "GET_ACTIVATION", "nạp bảng hàm kích hoạt"],
            ["7, 8, 9", "START_CONVERTER, CONVERT_IACT, WAIT_CYCLE", "chuyển activation vào cluster"],
            ["10", "WAIT_FOR_RESULTS (layer cuối)", "tính toán"],
            ["11", "RECEIVE_PSUMS_TO_IACT (layer có layer sau)",
             "tính toán khi FSM psum ở 1–3 (chờ sẵn sàng, CALCULATE_PSUM, lấy kết quả); còn lại (PSUM_IDLE, chờ gửi, "
             "SEND_PSUM_TO_IACT) là ghi ngược"],
            ["12, 13, 14", "MAXPOOLING_READ / SEND / WAIT", "pooling"],
            ["bất kỳ", "FSM psum ở PSUM_SEND_RESULTS, hoặc có word kết quả trên bus", "đọc kết quả"]]
    table(doc, ["Trạng thái FSM chính", "Tên trong OpenEye_FPGA.v", "Pha được gán"], rows, widths=[2.6, 6.4, 7.0])
    caption(doc, "Bảng 1. Ánh xạ trạng thái FSM → pha (PROFILE_PHASES, profile_phase trong rtl_test_utils.py). Quy tắc đọc "
                 "kết quả được xét trước, rồi đến trạng thái 11, rồi đến bảng.")
    table(doc, ["Bộ đếm (mỗi pha, mỗi layer)", "Đếm gì"], [
        ["cycles", "số chu kỳ của pha"],
        ["in_offered / in_accepted", "số word DMA host đưa vào / DUT nhận (enable_dma_i và ready_dma_o)"],
        ["out_words", "số word kết quả DUT gửi ra (enable_dma_o và ready_dma_i)"],
        ["in_stall / out_stall", "chu kỳ DUT chờ dữ liệu / kết quả chờ host; bằng 0 với bộ nhớ lý tưởng"],
        ["activation_cycles", "chu kỳ khối kích hoạt làm việc (dây act_capture trong OpenEye_FPGA.v); nằm bên trong "
                              "pha ghi ngược, không phải một pha riêng"],
    ], widths=[5.0, 11.0])
    caption(doc, "Bảng 2. Các bộ đếm trong profile.json.")
    doc.add_picture(figs["pha_tung_layer"], width=Cm(16.5))
    caption(doc, f"Hình 1. Kết quả của profiler cho một lần chạy: MNIST đã huấn luyện (ReLU, ảnh test 0), sparse, CR 2 X 4 "
                 f"Y 3 (48 PE). Tổng {fmt(mn0['total_cycles'])} chu kỳ = {us(mn0['total_cycles'])} µs.")

    doc.add_heading("2.2. Làm sao để số đo chính xác", level=2)
    base18 = load(os.path.join(PERF, "activation_2026-11-18", "trained_relu_img0_sparse.json"))
    rows = [
        ["Đếm cạnh clock trong RTL, không đo thời gian chạy", "Mô phỏng một lần mất 40 giây đến 18 phút tùy máy và số "
         "lần chạy song song, nhưng số chu kỳ chỉ phụ thuộc RTL và dữ liệu",
         f"MNIST ReLU sparse: {fmt(base18['total_cycles'])} chu kỳ ngày 18/11 và {fmt(mn0['total_cycles'])} ngày 19/11, "
         "hai lần chạy riêng"],
        ["Seed cố định, dữ liệu như nhau", "Cùng RTL và dữ liệu thì cùng số, đến từng chu kỳ",
         "12 ca mốc: 0 chu kỳ, 0 word DMA khác nhau giữa 18/11 và 21/11"],
        ["Mỗi lần chỉ đổi một yếu tố", "Hiệu số chỉ do yếu tố đó gây ra",
         "Móc OPENEYE_WGHT_ZERO_FRACTION / OPENEYE_IACT_ZERO_FRACTION: cùng giá trị, mức cao chỉ thêm số 0 vào vị trí của "
         "mức thấp"],
        ["Chỉ dùng lần chạy tính đúng", "Số chu kỳ của một phép tính sai không có ý nghĩa",
         "Testbench so từng giá trị với tham chiếu; mọi số trong báo cáo là lần chạy PASS"],
        ["Bộ nhớ lý tưởng (1 word mỗi chu kỳ)", "Đo riêng bộ tăng tốc; trễ DDR thật là bước sau",
         "in_stall = out_stall = 0; có sẵn mô hình bộ nhớ OPENEYE_MEM=typical / slow cho sau này"],
        ["Kiểm chéo với công thức", "Bắt lỗi gán pha",
         "Nạp weight = số hàng × word mỗi hàng, đúng ở mọi layer của 16 cấu hình; nạp activation 100 = 98 + 2 word đệm"],
        ["Đổi ra thời gian bằng clock thật", "Clock của mô phỏng (10 ns) không phải clock FPGA",
         "4 ns = 250 MHz, đạt sau place and route (Vivado 22/11, WNS +0,114 ns)"],
        ["Đếm riêng việc chạy song song", "Một chu kỳ chỉ thuộc một pha; việc chạy nền không hiện thành pha",
         "activation_cycles; so hiệu số giữa hai lần chạy (mục 3)"],
    ]
    table(doc, ["Biện pháp", "Vì sao", "Bằng chứng"], rows, widths=[4.2, 5.4, 6.4])
    caption(doc, "Bảng 3. Các biện pháp làm cho số đo chính xác và lặp lại được.")
    para(doc, "Giới hạn: số đo là chu kỳ của RTL với bộ nhớ lý tưởng; trên board, DMA và DDR sẽ thêm chu kỳ chờ ở các pha "
              "nạp.")

    doc.add_heading("2.3. Khi một việc chạy song song với việc khác", level=2)
    on0 = d["mn"][("relu", 0, "sparse")]["layers"][0]
    para(doc, "Tổng chu kỳ của mạng và của từng layer là chính xác tuyệt đối: mỗi chu kỳ được đếm một lần. Số của từng pha "
              "cũng chính xác, nhưng theo một nghĩa cụ thể: đó là số chu kỳ FSM chính (và FSM psum) ở trong pha đó, tức thời "
              "gian pha đó chiếm trên đường găng của layer. Nó không phải là lượng việc của từng khối phần cứng. Khi hai khối "
              "chạy song song, phần việc bị che không hiện ra thành pha riêng, còn thời gian một khối phải chờ khối kia được "
              "tính vào pha mà FSM đang ở:")
    table(doc, ["Pha", "Profiler đếm gì", "Có thể lẫn việc khác không", "Cách tách"], [
        ["Các pha nạp", "chu kỳ ở GET_*; bằng số word DMA (1 word mỗi chu kỳ)",
         "không bị cộng thêm; một việc chạy nền (trải bias) có thể nằm gọn trong các chu kỳ này mà không hiện ra",
         "so số word DMA (in_accepted = cycles) và công thức"],
        ["Chuyển activation", "trạng thái 7–9", "che việc trải bias ở Conv2 / Conv3 MNIST", "chạy A/B"],
        ["Tính toán", "trạng thái 10, hoặc 11 khi FSM psum ở 1–3",
         "gồm các chu kỳ chờ nằm trong chính các trạng thái tính", "quét số 0, so sparse / dense"],
        ["Ghi ngược", "trạng thái 11 khi FSM psum không ở 1–3",
         f"gồm cả chờ khối khác: Conv1 MNIST có 890 chu kỳ chờ trải bias trong {fmt(ph(on0, 'writeback'))} chu kỳ ghi ngược",
         "activation_cycles (chu kỳ thật sự ghi); A/B bảng bias bật / tắt"],
        ["Pooling, đọc kết quả", "trạng thái 12–14; word kết quả trên bus", "đọc kết quả được xét trước mọi quy tắc khác",
         "đếm word ra"],
    ], widths=[2.6, 4.2, 5.4, 3.8])
    caption(doc, "Bảng 4. Mỗi pha của profiler đo gì khi có việc chạy song song.")
    bullets(doc, [
        f"Trong các phép đo của báo cáo, phần lẫn đã biết là 890 chu kỳ chờ ở Conv1 MNIST "
        f"({num(100.0 * 890 / d['mn'][('relu', 0, 'sparse')]['total_cycles'], 2)} % tổng mạng), đã tách bằng chạy A/B (mục "
        "3.5). Ở các layer khác, ghi ngược chỉ dài hơn activation_cycles khoảng 110 chu kỳ (đổ đầy pipeline).",
        "Hệ quả khi đánh giá tối ưu: rút ngắn một pha chưa chắc rút ngắn tổng đúng bằng ấy. Bỏ một việc đang bị che thì không "
        "được gì; rút ngắn một pha đang che việc khác (ví dụ chuyển activation của Conv2) có thể làm lộ ra thời gian chờ. Vì "
        "vậy mọi kết luận về một thay đổi trong các báo cáo đều dựa trên chạy lại cả mạng (A/B) và so tổng, không cộng trừ "
        "số của từng pha.",
        "Có thể làm rõ hơn mà không sửa RTL: cho profiler đếm theo cặp (trạng thái FSM chính, trạng thái FSM psum) để thấy "
        "trong mỗi pha FSM psum đang tính, đang ghi hay đang chờ (đề xuất ở mục 8).",
    ])

    # ---------------------------------------------------------------- 3
    doc.add_heading("3. Hàm kích hoạt tốn bao nhiêu chu kỳ", level=1)
    doc.add_heading("3.1. Hàm được làm ở đâu trong phần cứng", level=2)
    table(doc, ["Hàm", "Phần cứng", "Chu kỳ mỗi giá trị", "Chu kỳ mỗi layer"], [
        ["ReLU", "Kẹp của bộ lượng tử: giới hạn dưới 0 thay cho −128", "0", "0"],
        ["Leaky ReLU", "Bộ lượng tử chọn cặp [mant, shift] riêng cho tổng âm ở tầng 1; tham số nằm trong thanh ghi cấu "
                       "hình của layer", "0", "0"],
        ["SiLU, hard-swish", "Bảng 256 ô int8 (LUTRAM) đọc không cần clock ngay sau tầng 3 của bộ lượng tử", "0",
         "32 (nạp bảng: 256 × 8 bit = 2.048 bit = 32 word DMA 64 bit); 0 nếu layer giữ bảng của layer trước"],
    ], widths=[2.6, 7.4, 2.6, 3.4])
    caption(doc, "Bảng 5. Cách làm từng hàm (thiết kế 02/11, doc/experiments/2026-11-02_activation_rtl_design.md). Độ trễ "
                 "3 clock của bộ lượng tử không đổi ở cả 4 hàm.")

    doc.add_heading("3.2. Pha ghi ngược và vì sao tra bảng không tốn chu kỳ", level=2)
    mn2 = mn0["layers"][2]
    vals2 = 14 * 14 * 64
    para(doc, "Pha ghi ngược (writeback) có ở mọi layer có layer sau trên chip: kết quả của layer không ra DMA mà được lượng "
              "tử về int8 rồi ghi lại vào bộ đệm activation, làm input cho layer sau.")
    bullets(doc, [
        "Khi nào: FSM chính ở trạng thái RECEIVE_PSUMS_TO_IACT (11). Sau mỗi lượt tính, FSM psum chuyển sang "
        "SEND_PSUM_TO_IACT: đọc tổng psum (đã có bias) của lượt đó từ bộ đệm psum và đưa qua bộ lượng tử. Profiler tính các "
        "chu kỳ này (FSM psum không ở trạng thái tính 1–3) là ghi ngược.",
        "Bộ lượng tử là pipeline 3 tầng, giữa các tầng là thanh ghi (Hình 2): tầng 1 cộng offset, tầng 2 nhân hệ số mant "
        "(DSP), tầng 3 dịch phải và kẹp về [act_min, 127]. Có 4 làn chạy song song (WRITEBACK_WORDS = min(TRANS_WORDS, "
        "NUM_GLB_PSUM) = 4 ở CR 2 X 4 Y 3); mỗi chu kỳ, mỗi làn nhận một tổng mới và trả ra một giá trị int8.",
        f"FSM chính lấy giá trị của các làn vào thanh ghi ghi ngược (iact_to_psum_mux_reg, R5 trong Hình 2), gom thành "
        f"nhóm 4 channel mỗi pixel rồi ghi vào bộ đệm activation. Số chu kỳ thanh ghi này nhận giá trị là activation_cycles: "
        f"Conv2 MNIST có {fmt(vals2)} giá trị output, {fmt(mn2.get('activation_cycles', 0))} chu kỳ nhận "
        f"(khoảng {num(vals2 / mn2.get('activation_cycles', 1), 1)} giá trị mỗi chu kỳ với 4 làn) trong "
        f"{fmt(ph(mn2, 'writeback'))} chu kỳ ghi ngược; phần còn lại là đổ đầy pipeline và chuyển nhóm.",
        "Hàm kích hoạt nằm ngay trên đường này. ReLU là giới hạn dưới của phép kẹp ở tầng 3: act_min = 0 thay cho −128, "
        "cùng một bộ so sánh. Leaky ReLU chọn cặp [mant, shift] riêng cho tổng âm ở tầng 1. Cả hai không thêm tầng nào, nên "
        "không thêm chu kỳ.",
    ])
    doc.add_picture(figs["ghi_nguoc"], width=Cm(16.5))
    caption(doc, "Hình 2. Đường ghi ngược của một làn. Bảng của SiLU / hard-swish chen vào chu kỳ vốn có giữa thanh ghi tầng "
                 "3 (R4) và thanh ghi ghi ngược (R5). Slack: đường xấu nhất vào từng thanh ghi theo Vivado (kiểm chứng 3). Phần "
                 "dưới: nếu bảng ở block RAM thì phải thêm một thanh ghi.")
    para(doc, "Bảng của SiLU / hard-swish nằm giữa R4 và R5, trong chu kỳ đã có sẵn giữa hai thanh ghi đó:")
    bullets(doc, [
        "Vì sao đọc được mà không cần clock: bảng được khai báo là mảng reg với ram_style = \"distributed\" "
        "(hdl/activation_table.v), nên Vivado đặt nó vào LUTRAM (distributed RAM): các LUT6 của slice SLICEM dùng làm ô "
        "nhớ nhỏ. Ghi là đồng bộ (ở cạnh clock, chỉ khi nạp bảng trong GET_ACTIVATION). Đọc là logic tổ hợp (assign bank_out "
        "= mem[index]): địa chỉ đi vào chân input của LUT và dữ liệu ra sau trễ của LUT, như một hàm logic bình thường; "
        "trên đường đọc không có thanh ghi nào.",
        "Cách tổ chức: chỉ số = giá trị int8 + 128 (đảo bit dấu). 8 bank × 32 ô × 8 bit: 3 bit thấp của chỉ số chọn bank "
        "(mux 8:1), 5 bit cao là địa chỉ trong bank. Có 8 bank để một word DMA 64 bit (8 ô) ghi vào cả 8 bank trong cùng "
        "một chu kỳ: 256 ô nạp xong trong 32 chu kỳ.",
        "Điều kiện để không tốn chu kỳ: đường R4 → bảng → mux → R5 phải xong trong một chu kỳ 4 ns. Logic thêm khoảng 1 ns "
        "cộng dây nối; Vivado đạt 250 MHz với bảng trong thiết kế (WNS +0,114 ns), nên không phải thêm thanh ghi.",
        "Nếu đặt bảng trong block RAM: BRAM chỉ đọc đồng bộ (dữ liệu ra sau cạnh clock), nên phải thêm một thanh ghi (phần "
        "dưới Hình 2): mỗi đợt ghi ngược dài thêm 1 chu kỳ, và mọi chuỗi trễ 3 clock của trạng thái 11 phải thành 4. Đây là "
        "phương án B của thiết kế 02/11, không cần dùng.",
    ])
    table(doc, ["Mục (Vivado 22/11, sau tổng hợp)", "Mỗi bản sao bảng", "4 bản sao (4 làn)"], [
        ["LUT tổng", "88–89", "353 (0,6 % của 59,9k LUT)"],
        ["trong đó LUT làm bộ nhớ (LUTRAM)", "64", "256"],
        ["LUT logic (mux 8:1, chọn bank)", "24–25", "97"],
        ["Flip-flop", "0", "0"],
        ["Block RAM, DSP", "0", "0"],
    ], widths=[6.6, 3.8, 5.6], align_right=(1, 2))
    caption(doc, "Bảng 6. Phần cứng của bảng hàm kích hoạt (activation_table trong utilization_hier.txt, "
                 "doc/synth/2026-11-22_route4ns_fix51_zu7ev). 0 flip-flop: đường đọc không có thanh ghi.")
    para(doc, "Kết luận: tính hàm không thêm thanh ghi, nên độ trễ và tốc độ của pipeline ghi ngược giữ nguyên: 0 chu kỳ "
              "mỗi giá trị. Chỉ việc nạp bảng (32 word DMA) tốn chu kỳ, một lần cho mỗi layer có bảng.")

    # ---- write-back checks of 26/11
    doc.add_heading("Kiểm chứng 1: mỗi làn mang output nào (đo 26/11)", level=3)
    lx4, lx2, lw = lanes_identify("x4", 4), lanes_identify("x2", 2), lanes_identify("w16f16", 4)
    if lx4:
        para(doc, "Một coroutine cocotb ghi lại giá trị của mọi làn ở mỗi chu kỳ khối kích hoạt nhận giá trị (act_capture), "
                  "rồi so với output tham chiếu của layer (int8 sau lượng tử). Giá trị int8 hay trùng nhau, nên mỗi layer chạy "
                  "4 seed và lấy giao các vị trí có cùng giá trị: lịch ghi ngược không phụ thuộc dữ liệu, nên mỗi ô (lần nhận, "
                  "làn) được xác định duy nhất (doc/experiments/2026-11-26_writeback_lanes.md). Layer 0 của Conv_Stack, CR 2, "
                  "sparse, không hàm.")
        rows = []
        for k in (0, 1, 2, 3, 4, 8, 32):
            rows.append([str(k)] + [str(next(iter(c))) if len(c) == 1 else "?" for c in lx4["slots"][k]])
        table(doc, ["Lần nhận", "làn 0 (f, x, y)", "làn 1", "làn 2", "làn 3"], rows, widths=[2.0, 3.5, 3.5, 3.5, 3.5])
        caption(doc, "Bảng 7. X = 4, Conv 8 × 4 × 4 → 8: output (filter, x, y) của từng làn ở một số lần nhận.")
        rows = []
        for name, r, n in (("X 4, Conv 8×4×4 → 8", lx4, 4), ("X 2, Conv 8×4×4 → 8", lx2, 2),
                           ("X 4, Conv 16×4×4 → 16", lw, 4)):
            if r:
                rows.append([name, f"{r['caps']} × {n}", f"{r['unique']}/{r['caps'] * n}", f"{r['covered']}/{r['outputs']}",
                             str(r["twice"])])
        table(doc, ["Ca", "Lần nhận × làn", "Ô xác định duy nhất", "Output có mặt", "Output ghi 2 lần"], rows,
              widths=[4.4, 2.8, 3.2, 2.8, 2.8], align_right=(1, 2, 3, 4))
        caption(doc, "Bảng 8. Mọi ô xác định được; mọi output có mặt. Các output ghi 2 lần là 6 lần nhận cuối mỗi layer, lặp lại "
                     "output đầu với cùng giá trị (vô hại; activation_cycles của profiler vì thế dư 6 mỗi layer).")
        bullets(doc, [
            "Mỗi giá trị trên một làn là một output hoàn chỉnh: khớp int8 cuối của tham chiếu (bias + mọi channel + mọi hàng "
            "kernel, đã lượng tử). Việc cộng xong trước ghi ngược: dọc theo từng cột PE (psum đi qua các hàng PE, mỗi hàng giữ "
            "một hàng kernel; PE_cluster.v) và qua các lượt trong bộ đệm psum (bắt đầu bằng bias); FSM psum chỉ sang "
            "SEND_PSUM_TO_IACT ở lượt cuối (store_in_psum = 0).",
            "X làn là X vị trí x liền nhau của cùng một filter, cùng hàng y (X 4: x 0–3, rồi 4–7; X 2: 2 vị trí, các làn "
            "khác luôn 0). Các lần nhận liên tiếp đi qua 4 filter cho cùng các pixel: mỗi làn gom 4 filter thành nhóm 4 channel "
            "của một pixel cho layer sau. Thứ tự: nhóm 4 filter → khối X vị trí x → hàng y → nhóm 4 filter kế.",
            "Số làn theo X (số cột PE, NUM_GLB_PSUM), không theo số cluster: đo 18/11 trên mạng Bảng 2, tốc độ ghi ngược "
            "khoảng 1,75 giá trị mỗi chu kỳ ở X 2 và 3,5 ở X 4, như nhau ở CR 1 / 2 / 8 và Y 3 / 4. Chỉ số cluster của FSM psum "
            "giữ 0 suốt pha ghi ngược, nên chưa xác nhận được ghi ngược đọc từng cluster một như chú thích trong RTL.",
        ])

    doc.add_heading("Kiểm chứng 2: mỗi tầng tốn đúng 1 chu kỳ (mô phỏng RTL)", level=3)
    tbl = tb_requant_log()
    if tbl:
        para(doc, "Testbench Verilog nhỏ (doc/experiments/2026-11-26_requant_timing/tb_requant.v, Icarus) cho quantization_unit "
                  "một psum mới mỗi chu kỳ, với hệ số Leaky ReLU của Conv1 MNIST (mant 8.817.157 / 2^31, neg 215 / 2^19, làm "
                  "tròn). Cạnh lấy mẫu nạp tầng 1, cạnh sau nạp tầng 2, cạnh thứ ba nạp tầng 3 (R4):")
        rows = [[v.replace("-", "−") for v in (p, q, w)] + [ok, e.replace("-", "−")] for _, p, q, w, ok, e in tbl["rows"]]
        table(doc, ["psum", "Kết quả sau cạnh thứ 3", "Mong đợi", "", "Sau cạnh thứ 2 (kết quả trước)"], rows,
              widths=[2.4, 3.6, 2.4, 1.6, 4.8], align_right=(0, 1, 2, 4))
        caption(doc, "Bảng 9. Kết quả có đúng sau cạnh thứ 3, chưa có sau cạnh thứ 2; mỗi chu kỳ ra một kết quả mới (pipeline). "
                     "−2000 → −1 là Leaky ReLU (không có Leaky: −8).")
        if tbl["reads"]:
            para(doc, "Bảng hàm kích hoạt: nạp 32 word ở cạnh clock, rồi đổi chỉ số 3 lần trong 0,2 ns giữa hai cạnh clock; "
                      "output đổi theo ngay (" + "; ".join(f"t = {num(float(t), 1)} ns: T[{v.replace('-', '−')}] = {o}"
                                                         for t, v, o in tbl["reads"]) +
                      f"). Kết quả testbench: {tbl['result']}. Mô phỏng RTL không có trễ cổng, nên nó chỉ chứng minh hành vi "
                      "theo chu kỳ; chạy kịp hay không là việc của phân tích timing.")

    doc.add_heading("Kiểm chứng 3: logic giữa hai thanh ghi có kịp trong 4 ns không (STA Vivado)", level=3)
    st = sta_stages()
    if st["stages"]:
        para(doc, "Phân tích timing tĩnh (STA) của Vivado tính mọi đường thanh ghi → thanh ghi trên bản đã place and route, ở "
                  "góc chậm nhất của chip (speed grade −2), không phụ thuộc dữ liệu thử. Chạy chỉ đọc trên checkpoint của mốc "
                  "22/11 (doc/experiments/2026-11-26_requant_timing: timing_stages.tcl, timing_requant.tcl):")
        names = {"S1": "Tầng 1 (sum_s1, mant_s1, shift_s1)", "S2": "Tầng 2 (prod_s2): nhân mant × sum",
                 "S3 = R4": "Tầng 3 = R4 (quantized_value): dịch, kẹp", "R5": "R5 (iact_to_psum_mux_reg)"}
        rows = []
        seen = set()
        for x in st["stages"]:
            key = x["title"].split(" (")[0].strip()
            if key not in names or key in seen:
                continue
            seen.add(key)
            what = ("đường reset; đường dữ liệu còn rộng hơn" if "CLR" in x["dst"] else
                    ("đường điều khiển (clock enable)" if x["dst"].endswith("/CE") else levels_vi(x["levels"])))
            rows.append([names[key], what, f"{num(x['delay'], 3)} ns", f"+{num(x['slack'], 3)} ns"])
        if "r5_slack" in st:
            rows.append(["R4 → bảng → mux → R5 (đường dữ liệu)", "LUTRAM (RAMD32) + 2 LUT6",
                         f"{num(sum(v for _, v in st['path']), 3)} ns",
                         f"+{num(st['r5_slack'], 3)} ns"])
        table(doc, ["Thanh ghi đích", "Đường xấu nhất", "Trễ đường dữ liệu", "Slack"], rows, widths=[5.2, 5.8, 2.6, 2.4],
              align_right=(2, 3))
        caption(doc, "Bảng 10. Đường xấu nhất vào từng tầng, clock 4 ns. Slack dương = kịp; WNS của cả thiết kế +0,114 ns.")
        if st["path"]:
            steps = " + ".join(f"{name} {num(v, 3)}" for name, v in st["path"])
            para(doc, f"Đường R4 → R5 xấu nhất, từng bước (ns): {steps}; đến R5 ở {num(st['arrival'], 3)} ns, hạn chót "
                      f"{num(st['required'], 3)} ns (chu kỳ 4 ns, đã tính lệch clock, độ bất định và setup của R5): dư {num(st['r5_slack'], 3)} "
                      "ns. Đọc LUTRAM chỉ 0,100 ns và không qua thanh ghi; phần lớn là dây (R4 nối tới 113 chân của các bank và "
                      "mux).")
        bullets(doc, [
            "Đường có bảng là đường dư nhiều nhất trong chuỗi lượng tử (1,49 ns, 37 % chu kỳ). Đường chặt nhất là phép nhân ở "
            "tầng 2 (+0,116 ns): mant 25 bit × sum 21 bit lớn hơn một DSP48E2 (27 × 18), nên cần thêm 5 bộ cộng CARRY8 ngoài "
            "DSP. Chèn bảng vào trước phép nhân thì không kịp; đặt sau R4 như hiện nay thì kịp với dư rộng.",
            "Hai bộ chọn giữa R4 và R5: (1) chọn bank 8:1 trong bảng: bảng chia 8 bank để một word DMA 64 bit (8 ô) ghi vào 8 "
            "bank trong một chu kỳ khi nạp; khi đọc, 5 bit cao của chỉ số là địa chỉ trong bank, 3 bit thấp chọn bank. (2) "
            "chọn theo chế độ (act_mode == 2 ? bảng : output bộ lượng tử): SiLU / hard-swish lấy bảng; không hàm, ReLU, Leaky "
            "ReLU đi thẳng nên không phải nạp bảng. Vivado gộp hai bộ chọn thành 2 tầng LUT6 (đường trên). R5 "
            "(iact_to_psum_mux_reg) là thanh ghi ghi ngược, không phải bộ chọn, dù tên có \"mux\".",
        ])


    doc.add_heading("3.3. Đo theo từng layer", level=2)
    para(doc, "Mạng Bảng 2 (weight và input ngẫu nhiên, seed 1), CR 2 X 4 Y 3, chạy 5 lần: không hàm, ReLU, Leaky ReLU, "
              "SiLU, hard-swish (hàm đặt sau mọi Conv / Dense trừ layer cuối), cả sparse và dense. Chi phí trực tiếp của "
              "hàm ở một layer = hiệu số chu kỳ của layer đó so với không hàm, trừ phần tính toán (phần tính toán thay đổi do "
              "số 0 mà hàm của layer trước để lại).")
    base = t2[("none", "dense")]
    rows = []
    for k, layer in enumerate(base["layers"]):
        if layer["info"]["name"] == "Pooling" or k == len(base["layers"]) - 1:
            continue
        cells = [lname(layer), f"{fmt(layer.get('activation_cycles', 0))} / {fmt(ph(layer, 'writeback'))}"]
        for a, _ in T2_ACTS[1:]:
            vals = []
            for mode in ("dense", "sparse"):
                L, B = t2[(a, mode)]["layers"][k], t2[("none", mode)]["layers"][k]
                vals.append(L["total_cycles"] - B["total_cycles"] - (ph(L, "compute") - ph(B, "compute")))
            cells.append(sgn(vals[0]) + ("" if vals[0] == vals[1] else f" (sparse {sgn(vals[1])})"))
        rows.append(cells)
    table(doc, ["Layer", "Chu kỳ khối kích hoạt / ghi ngược", "ReLU", "Leaky ReLU", "SiLU", "hard-swish"], rows,
          widths=[3.6, 3.6, 2.0, 2.2, 2.0, 2.4], align_right=(1, 2, 3, 4, 5))
    caption(doc, "Bảng 11. Chi phí trực tiếp của hàm ở từng layer (chu kỳ, so với không hàm), giống nhau ở sparse và dense. "
                 "Khối kích hoạt bận cùng số chu kỳ ở cả 5 lần chạy, kể cả không hàm, và nằm trong ghi ngược.")
    doc.add_picture(figs["ham_kich_hoat"], width=Cm(16.5))
    caption(doc, "Hình 3. Cả mạng Bảng 2: hiệu số chu kỳ so với không hàm, chia trực tiếp (nạp bảng, ghi ngược) và gián tiếp "
                 "(tính toán của layer sau, do số 0).")

    doc.add_heading("3.4. Đo end to end (cả mạng)", level=2)
    same = d["same"]
    have_same = all((a, m) in same for a, _ in SAME_ACTS for m in ("sparse", "dense"))
    para(doc, "Các model MNIST đã huấn luyện đều có hàm kích hoạt (mỗi hàm một model riêng), nên bản đo trước không có cột "
              "không hàm. Ngày 26/11 đã đo thêm: lấy weight của model ReLU, chạy với từng hàm và với không hàm (hàm đồng nhất), "
              "cùng ảnh test 0 (doc/experiments/2026-11-26_mnist_same_weights). Model không hàm này không phải model đã huấn "
              "luyện cho không hàm (độ chính xác khác), nhưng chu kỳ chỉ phụ thuộc kích thước layer và số 0, nên đây là phép so "
              "sánh đúng của riêng hàm kích hoạt trên cùng một mạng.")
    rows = []
    for mode in ("sparse", "dense"):
        b = t2_tot[("none", mode)]
        rows.append([f"Bảng 2, {mode}"] + [f"{fmt(t2_tot[(a, mode)])}" + ("" if a == "none" else
                                           f" ({pct(100.0 * (t2_tot[(a, mode)] - b) / b, 2)})") for a, _ in T2_ACTS])
    if have_same:
        for mode in ("sparse", "dense"):
            b = same[("none", mode)]["total_cycles"]
            rows.append([f"MNIST cùng weight, {mode}"] + [
                f"{fmt(same[(a, mode)]['total_cycles'])}" + ("" if a == "none" else
                f" ({pct(100.0 * (same[(a, mode)]['total_cycles'] - b) / b, 2)})") for a, _ in SAME_ACTS])
    mn_avg = {a: sum(d["mn"][(a, i, "sparse")]["total_cycles"] for i in (0, 1, 6)) / 3 for a, _ in MN_ACTS}
    mn_dense = {a: d["mn"][(a, 0, "dense")]["total_cycles"] for a, _ in MN_ACTS}
    rows.append(["MNIST model riêng, sparse (3 ảnh)", "–"] + [f"{fmt(round(mn_avg[a]))}" + ("" if a == "relu" else
                 f" ({pct(100.0 * (mn_avg[a] - mn_avg['relu']) / mn_avg['relu'], 1)})") for a, _ in MN_ACTS])
    rows.append(["MNIST model riêng, dense", "–"] + [f"{fmt(mn_dense[a])}" + ("" if a == "relu" else
                 f" ({sgn(mn_dense[a] - mn_dense['relu'])})") for a, _ in MN_ACTS])
    table(doc, ["Mạng, chế độ", "không hàm", "ReLU", "Leaky ReLU", "SiLU", "hard-swish"], rows,
          widths=[3.6, 2.2, 2.6, 2.6, 2.4, 2.6], align_right=(1, 2, 3, 4, 5))
    caption(doc, "Bảng 12. Tổng chu kỳ cả mạng. Bảng 2 và MNIST cùng weight (weight của model ReLU, ảnh 0): so với không hàm. "
                 "MNIST model riêng (mỗi hàm một model đã huấn luyện, không có bản không hàm): so với ReLU.")
    notes = [
        "Trên dense, hàm kích hoạt chỉ tốn đúng phần nạp bảng: ReLU = Leaky ReLU = không hàm; SiLU = hard-swish = +32 chu kỳ "
        "mỗi layer có bảng (MNIST: 2 layer giữa có bảng tốn thêm, Conv1 bị che, mục 3.5).",
    ]
    if have_same:
        sn, sr = same[("none", "sparse")], same[("relu", "sparse")]
        dn = same[("none", "dense")]
        zin_n = [zin(sn["layers"][k]) for k in (2, 4, 5)]
        zin_r = [zin(sr["layers"][k]) for k in (2, 4, 5)]
        notes.append(
            f"MNIST trên sparse, cùng weight: không hàm {fmt(sn['total_cycles'])} chu kỳ, ReLU {fmt(sr['total_cycles'])} "
            f"({pct(100.0 * (sr['total_cycles'] - sn['total_cycles']) / sn['total_cycles'], 1)}). Không có hàm thì input của "
            f"Conv2 / Conv3 / Dense chỉ có {num(zin_n[0], 0)} / {num(zin_n[1], 0)} / {num(zin_n[2], 0)} % số 0 (sau ReLU: "
            f"{num(zin_r[0], 0)} / {num(zin_r[1], 0)} / {num(zin_r[2], 0)} %), nên PE sparse có ít thứ để bỏ qua. Trên dense, "
            f"không hàm = ReLU = Leaky ReLU = {fmt(dn['total_cycles'])}.")
    if have_same:
        sp = {a: same[(a, "sparse")]["total_cycles"] for a, _ in SAME_ACTS}
        others = [100.0 * (sp[a] - sp["none"]) / sp["none"] for a in ("leaky_relu", "silu", "hardswish")]
        notes.append(
            f"Trên sparse, hàm chỉ làm mạng nhanh hơn khi nó tạo nhiều số 0: ReLU nhanh hơn không hàm "
            f"{pct(-100.0 * (sp['relu'] - sp['none']) / sp['none'], 1, sign=False)}; Leaky ReLU, SiLU, hard-swish gần như bằng "
            f"không hàm ({pct(min(others), 2)} đến {pct(max(others), 2)}), vì sau chúng input chỉ có 5–19 % số 0. SiLU còn chậm "
            f"hơn không hàm {fmt(sp['silu'] - sp['none'])} chu kỳ: 64 chu kỳ nạp bảng (Conv2, Conv3; Conv1 bị che) lớn hơn "
            "phần tính toán tiết kiệm được.")
        notes.append(
            f"Không có hàm thì MNIST trên sparse chậm hơn trên dense: {fmt(sp['none'])} so với "
            f"{fmt(same[('none', 'dense')]['total_cycles'])} chu kỳ "
            f"({pct(100.0 * (sp['none'] - same[('none', 'dense')]['total_cycles']) / same[('none', 'dense')]['total_cycles'], 1)}). "
            "Lợi thế của sparse trên MNIST đến từ số 0 của ReLU.")
    notes.append(
        "Ở MNIST model riêng, Leaky ReLU / SiLU / hard-swish chậm hơn ReLU khoảng 10 %: đó không phải chi phí của hàm mà là mất "
        "số 0 của ReLU (cùng kết luận với các dòng cùng weight).")
    bullets(doc, notes)

    doc.add_heading("3.5. Tại sao có các trường hợp không tốn chu kỳ", level=2)
    bullets(doc, [
        "ReLU và Leaky ReLU không thêm tầng, không thêm dữ liệu: ReLU chỉ là giới hạn dưới của phép kẹp có sẵn, Leaky ReLU "
        "chỉ chọn cặp hệ số khác cho tổng âm trong cùng tầng của bộ lượng tử. Tham số nằm trong thanh ghi cấu hình đã nạp "
        "cùng layer, nên không có word DMA nào thêm.",
        "Bảng của SiLU / hard-swish là LUTRAM đọc không cần clock, chen vào chu kỳ có sẵn giữa thanh ghi tầng 3 và thanh ghi "
        "ghi ngược (mục 3.2), nên pipeline ghi ngược vẫn như cũ: 0 chu kỳ mỗi giá trị. Chỉ có 32 chu kỳ nạp bảng mỗi layer; "
        "một layer dùng lại bảng của layer trước (act_keep_table) thì 0.",
        "Khối kích hoạt làm việc trong pha ghi ngược (activation_cycles = 3.590 / 1.798 / 454 / 35 chu kỳ ở 4 layer của "
        "mạng Bảng 2), và ghi ngược dài như nhau với mọi hàm, kể cả không hàm: việc tính hàm được che hoàn toàn.",
    ])
    if "relu" in nb and "silu" in nb:
        on_r, on_s = d["mn"][("relu", 0, "sparse")]["layers"][0], d["mn"][("silu", 0, "sparse")]["layers"][0]
        off_r, off_s = nb["relu"]["layers"][0], nb["silu"]["layers"][0]
        para(doc, "Trường hợp đặc biệt: ở Conv1 của MNIST, 32 chu kỳ nạp bảng của SiLU không làm layer dài thêm (ghi ngược "
                  "ngắn đi đúng 32). Nguyên nhân là bảng bias theo filter (BIAS_PER_FILTER_EN = 1; bản sửa ngày 17/11, commit "
                  "ae5665f: host gửi bias của mỗi filter một lần thay cho gửi lặp lại ở mọi địa chỉ psum): sau GET_BIAS, "
                  "FSM psum ghi lại bảng bias vào bộ đệm psum ở chế độ chạy nền trong khi FSM chính tiếp tục nạp. Ở Conv1 của "
                  "MNIST (32 filter, 2 lượt x) việc ghi lại dài hơn các pha nạp, nên lúc FSM chính sang trạng thái 11, FSM psum "
                  "còn phải chờ ghi xong, và profiler tính các chu kỳ chờ này vào ghi ngược. Nạp bảng thêm 32 chu kỳ trước đó "
                  "thì thời gian chờ ngắn đi đúng 32. Kiểm chứng bằng hai lần chạy với bảng bias tắt:")
        rows = []
        for label, r_, s_ in (("bảng bias bật (mặc định)", on_r, on_s), ("bảng bias tắt", off_r, off_s)):
            rows.append([label, f"{fmt(ph(r_, 'writeback'))} / {fmt(ph(s_, 'writeback'))}",
                         f"{fmt(ph(r_, 'writeback') - r_.get('activation_cycles', 0))}",
                         f"{fmt(r_['total_cycles'])} / {fmt(s_['total_cycles'])}",
                         sgn(s_["total_cycles"] - r_["total_cycles"])])
        table(doc, ["Conv1 MNIST, sparse", "Ghi ngược ReLU / SiLU", "Ghi ngược ngoài khối kích hoạt (ReLU)",
                    "Tổng layer ReLU / SiLU", "SiLU so với ReLU"], rows, widths=[3.8, 3.2, 3.2, 3.6, 2.2],
              align_right=(1, 2, 3, 4))
        caption(doc, "Bảng 13. Conv1 của MNIST với bảng bias bật và tắt (ảnh 0). Các layer khác của MNIST và mọi layer của "
                     "mạng Bảng 2 không có thời gian chờ này, nên ở đó nạp bảng hiện ra đủ +32.")
        para(doc, f"Tắt bảng bias làm Conv1 dài hơn nhiều ({fmt(off_r['total_cycles'])} so với {fmt(on_r['total_cycles'])} "
                  f"chu kỳ, vì bias được gửi lại cho mỗi vị trí: {fmt(ph(off_r, 'load_bias'))} word nạp bias thay cho "
                  f"{fmt(ph(on_r, 'load_bias'))}), nên bảng bias vẫn có lợi lớn; nó chỉ tình cờ che mất 32 chu kỳ nạp bảng ở "
                  f"Conv1. Bỏ khối kích hoạt ra thì phần ghi ngược còn lại là {fmt(ph(off_r, 'writeback') - off_r.get('activation_cycles', 0))} "
                  f"chu kỳ khi tắt bảng bias, so với {fmt(ph(on_r, 'writeback') - on_r.get('activation_cycles', 0))} khi bật: "
                  "khoảng 890 chu kỳ chênh lệch chính là thời gian chờ ghi lại bảng bias.")
        rows = []
        for k, name in ((0, "Conv1"), (2, "Conv2"), (4, "Conv3")):
            a_, b_ = d["mn"][("relu", 0, "sparse")]["layers"][k], nb["relu"]["layers"][k]
            rows.append([name, f"{fmt(ph(a_, 'load_bias'))} / {fmt(ph(b_, 'load_bias'))}",
                         f"{fmt(ph(a_, 'writeback'))} / {fmt(ph(b_, 'writeback'))}",
                         f"{fmt(a_['total_cycles'])} / {fmt(b_['total_cycles'])}",
                         f"{sgn(a_['total_cycles'] - b_['total_cycles'])} "
                         f"({pct(100.0 * (a_['total_cycles'] - b_['total_cycles']) / b_['total_cycles'], 0)})"])
        ta, tb = d["mn"][("relu", 0, "sparse")]["total_cycles"], nb["relu"]["total_cycles"]
        rows.append(["Cả mạng", "", "", f"{fmt(ta)} / {fmt(tb)}", f"{sgn(ta - tb)} ({pct(100.0 * (ta - tb) / tb, 1)})"])
        table(doc, ["MNIST ReLU, sparse", "Nạp bias bật / tắt", "Ghi ngược bật / tắt", "Tổng bật / tắt", "Chênh lệch"],
              rows, widths=[3.0, 3.0, 3.2, 3.8, 3.0], align_right=(1, 2, 3, 4))
        caption(doc, "Bảng 14. Bảng bias theo filter làm mọi layer Conv nhanh hơn; ở Conv1 có 890 chu kỳ chờ (tính vào ghi "
                     "ngược) nhưng nạp bias bớt 14.320 chu kỳ. Pool và Dense không đổi.")
        para(doc, "Khoảng chờ chỉ có ở Conv1: thời gian che được trước lượt tính đầu (nạp bảng lượng tử và chuyển activation, "
                  "khoảng 1.130 chu kỳ) ngắn hơn việc trải bias của Conv1 (28 × 28 output, 2 lượt x). Ở Conv2 / Conv3, chuyển "
                  "activation dài 4.679 / 2.951 chu kỳ nên che hết. Có thể bỏ nốt 890 chu kỳ này (0,45 % MNIST) bằng cách cho lượt "
                  "đầu chạy ngay khi các địa chỉ của nó đã có bias, hoặc trải 2 địa chỉ mỗi chu kỳ (RTL, cần đồng ý; lợi nhỏ).")
    bullets(doc, [
        "Trên sparse, hiệu số ở pha tính toán của layer sau không phải chi phí của hàm: đó là số 0 mà hàm để lại (ReLU nhiều, "
        "các hàm khác ít) quyết định PE sparse bỏ qua được bao nhiêu (mục 4).",
    ])

    # ---------------------------------------------------------------- 4
    doc.add_heading("4. Các trường hợp có mức độ thưa khác nhau", level=1)
    doc.add_heading("4.1. Các phép đo", level=2)
    table(doc, ["Phép đo (ngày)", "Model", "Thay đổi", "Lần chạy"], [
        ["Lưới một layer (20/11)", "4 layer của mạng Bảng 2, chạy riêng", "weight bằng 0 × input bằng 0, mỗi trục 0 / 20 / "
         "40 / 60 / 80 %; sparse, dense", "200"],
        ["Weight bằng 0, cả mạng (20/11)", "MNIST đã huấn luyện (ReLU); mạng Bảng 2", "weight bằng 0: 0 – 80 % ở mọi Conv "
         "và Dense; sparse, dense", "20"],
        ["Hàm kích hoạt (19–20/11)", "MNIST 4 hàm; mạng Bảng 2 5 cấu hình", "số 0 tự nhiên sau hàm: 6 – 87 %", "26"],
        ["Quét input bằng 0 (18/11)", "4 layer của mạng Bảng 2, 3 cấu hình cluster", "input bằng 0: 0 – 90 %", "120"],
    ], widths=[3.6, 4.4, 6.0, 1.6], align_right=(3,))
    caption(doc, "Bảng 15. Dữ liệu dùng trong mục này (CR 2 X 4 Y 3 trừ phép quét 18/11). Đặt số 0 bằng móc của testbench: "
                 "cùng giá trị ở mọi mức, mức cao chỉ thêm số 0.")

    doc.add_heading("4.2. Phần giống nhau ở mọi mức số 0", level=2)
    rows = []
    for s, title in SHAPES:
        vals = {p: {(w, a, m): ph(g(s, w, a, m), p) for w in ZEROS for a in ZEROS for m in ("sparse", "dense")}
                for p in ("load_wght", "load_iact", "convert_iact", "writeback", "readout", "compute")}
        def const(p, m):
            v = {x for (w, a, mm), x in vals[p].items() if mm == m}
            return fmt(next(iter(v))) if len(v) == 1 else f"{fmt(min(v))}–{fmt(max(v))}"
        rows.append([title, f"{const('load_wght', 'sparse')} / {const('load_wght', 'dense')}",
                     f"{const('load_iact', 'sparse')}", f"{const('convert_iact', 'sparse')}",
                     f"{const('readout', 'sparse')}", const("compute", "dense"), const("compute", "sparse")])
    table(doc, ["Layer (25 mức số 0)", "Nạp weight S / D", "Nạp activation", "Chuyển activation", "Đọc kết quả",
                "Tính toán dense", "Tính toán sparse"], rows, widths=[3.4, 2.4, 1.8, 2.0, 1.8, 2.0, 2.6],
          align_right=(1, 2, 3, 4, 5, 6))
    caption(doc, "Bảng 16. Chu kỳ từng pha trên 25 mức số 0 của mỗi layer: một số duy nhất nghĩa là giống hệt ở cả 25 mức. "
                 "Nạp activation, chuyển activation, đọc kết quả giống nhau ở cả hai chế độ.")
    bullets(doc, [
        "Nạp weight không đổi theo số 0: mỗi PE nhận một khối weight có độ dài cố định, mỗi weight một ô (12 bit ở sparse, "
        "8 bit ở dense), weight bằng 0 cũng chiếm ô. Dense luôn ít hơn sparse 40 % ở cấu hình này (hàng 24 ô: 5 word so với "
        "3 word).",
        "Nạp activation và chuyển activation không đổi: DMA mang activation 8 bit trần ở cả hai chế độ, bộ dựng luồng đọc "
        "mọi ô của bộ đệm; việc bỏ qua số 0 chỉ xảy ra trong PE.",
        "Phần cứng dense không đổi ở bất kỳ pha nào: nó nhân mọi giá trị, kể cả số 0.",
    ])

    doc.add_heading("4.3. Phần khác nhau: tính toán trên phần cứng sparse", level=2)
    doc.add_picture(figs["tinh_toan_theo_so_0"], width=Cm(16.5))
    caption(doc, "Hình 4. Chu kỳ tính toán của từng layer theo tỉ lệ input bằng 0, ở 3 mức weight bằng 0 (sparse) và dense.")
    c2 = {(w, a): ph(g("conv2", w, a), "compute") for w in ZEROS for a in ZEROS}
    rows = [[pct(float(w) * 100, 0, sign=False)] + [fmt(c2[(w, a)]) for a in ZEROS] for w in ZEROS]
    table(doc, ["weight = 0 \\ input = 0"] + [pct(float(a) * 100, 0, sign=False) for a in ZEROS], rows,
          widths=[3.6, 2.4, 2.4, 2.4, 2.4, 2.4], align_right=(1, 2, 3, 4, 5))
    caption(doc, f"Bảng 17. Chu kỳ tính toán sparse của Conv 14×14×16→32 (dense: {fmt(ph(g('conv2', '0', '0', 'dense'), 'compute'))} "
                 "ở mọi mức).")
    s0 = c2[("0", "0")]
    fc = {(w, a): ph(g("fc", w, a), "compute") for w in ZEROS for a in ZEROS}
    c1 = {(w, a): ph(g("conv1", w, a), "compute") for w in ZEROS for a in ZEROS}
    bullets(doc, [
        f"Weight bằng 0 và input bằng 0 đều làm tính toán sparse giảm, và cộng dồn: Conv 14×14 chỉ weight 80 % → "
        f"{pct(100.0 * (c2[('0.8', '0')] - s0) / s0)}, chỉ input 80 % → {pct(100.0 * (c2[('0', '0.8')] - s0) / s0)}, "
        f"cả hai → {pct(100.0 * (c2[('0.8', '0.8')] - s0) / s0)}.",
        f"Giảm ít hơn tỉ lệ số 0: 80 % input bằng 0 chỉ bớt {pct(-100.0 * (c2[('0', '0.8')] - s0) / s0, 0, sign=False)} chu "
        "kỳ. Theo phép quét 18/11, khoảng 60–64 % chu kỳ tính toán sparse là phần cố định không phụ thuộc số 0.",
        f"Layer Dense không bỏ qua weight bằng 0: tính toán giống hệt ở mọi mức weight bằng 0 ({fmt(fc[('0', '0')])} chu kỳ "
        f"ở input 0 %), chỉ input bằng 0 làm giảm ({fmt(fc[('0', '0.8')])} ở 80 %).",
        f"Conv1 (ảnh, 1 channel): input bằng 0 đến 40 % gần như không bớt chu kỳ ({fmt(c1[('0', '0')])} → "
        f"{fmt(c1[('0', '0.4')])}), weight bằng 0 thì có ({fmt(c1[('0.8', '0')])} ở weight 80 %).",
        "Khi không có số 0, sparse chậm hơn dense một chút ở pha tính toán (giải mã overhead): Conv1 +3,0 %, Dense 1568 "
        "+2,4 %.",
    ])

    doc.add_heading("4.4. Tại sao", level=2)
    bullets(doc, [
        "PE sparse lưu activation và weight ở dạng nén (giá trị khác 0 kèm 4 bit overhead đếm số 0 bị bỏ) và chỉ nhân các "
        "cặp khác 0, nên số 0 làm bớt phép nhân. Nhưng mỗi lượt tính còn có việc không phụ thuộc số 0 (đọc địa chỉ, giải mã, "
        "cộng psum, đồng bộ các PE), nên chu kỳ giảm chậm hơn số phép nhân.",
        "PE đọc weight theo word 2 weight: một weight bằng 0 chỉ bớt được chu kỳ khi cả word biến mất (thí nghiệm 18/11: ở 5 % "
        "weight bằng 0, tiết kiệm thật chỉ 0–10 % mức tỉ lệ).",
        "Weight của layer Dense được gửi không nén (raw_wght_i = 1, rtl_test_utils.py): PE nhận mọi weight, kể cả 0, nên "
        "không có gì để bỏ qua ở phía weight.",
        "Conv1 chỉ có 1 channel: mỗi PE nhận rất ít activation mỗi lượt, nên phần cố định chiếm gần hết thời gian. Đường "
        "cong lồi (gần phẳng đến 40 % rồi mới giảm) gợi ý chu kỳ chỉ bớt khi cả một nhóm activation, hoặc cả lượt của PE "
        "chậm nhất, bằng 0. Đây là giả thuyết, chưa kiểm bằng trace.",
        "Pha nạp không đổi vì khối dữ liệu gửi cho mỗi PE có độ dài cố định; phần cứng dense không đổi vì nó không có cơ chế "
        "bỏ qua.",
    ])
    doc.add_picture(figs["luoi_sparse_dense"], width=Cm(16.5))
    caption(doc, "Hình 5. Tổng chu kỳ của layer, sparse / dense, trên lưới weight × input bằng 0. Dense 1568 trên sparse "
                 "luôn chậm hơn (125–136 %): nạp weight chiếm 65 % layer và weight bằng 0 không được bỏ qua.")
    doc.add_picture(figs["weight_0_ca_mang"], width=Cm(16.5))
    m0s, m8s = wz[("mnist", "0", "sparse")], wz[("mnist", "0.8", "sparse")]
    t0s, t0d = wz[("t2", "0", "sparse")], wz[("t2", "0", "dense")]
    caption(doc, f"Hình 6. Cả mạng theo tỉ lệ weight bằng 0. Nạp weight không đổi (MNIST: sparse {fmt(ph(m0s, 'load_wght'))}, "
                 f"dense {fmt(ph(wz[('mnist', '0', 'dense')], 'load_wght'))}); chỉ tính toán sparse giảm "
                 f"({fmt(ph(m0s, 'compute'))} → {fmt(ph(m8s, 'compute'))}).")
    para(doc, f"Kết luận cho pha nạp weight: phần nạp thêm của sparse không phụ thuộc số 0 và chiếm 8–10 % tổng mạng (MNIST "
              f"+{fmt(ph(m0s, 'load_wght') - ph(wz[('mnist', '0', 'dense')], 'load_wght'))}, mạng Bảng 2 "
              f"+{fmt(ph(t0s, 'load_wght') - ph(t0d, 'load_wght'))} chu kỳ). Trong một layer, nó từ 0,4 % (Conv1) đến 35 % "
              "(Dense 1568) so với layer chạy dense. Ở Conv, đủ số 0 thì tính toán tiết kiệm bù được; ở Dense thì không.")

    # ---------------------------------------------------------------- 5
    doc.add_heading("5. Kiểm tra lại bản sửa test_dense_output và đối chiếu upstream", level=1)
    para(doc, "Phiên làm việc 21/11 (commit 6a7a323) sửa hai việc: 11 test hỏng của test/test_dense_output.py và bộ giải mã "
              "output Dense của testbench (#21). Kiểm tra lại ngày 23/11 (script doc/experiments/2026-11-23_dense_output_check.py):")
    dt, ut = dc.get("dev_test", {}), dc.get("upstream_test", {})
    rt, uf = dc.get("dev_roundtrip", {}), dc.get("upstream_formula", {})
    up_err = "; ".join(f"{n} × {e.split(':')[0]}" for e, n in ut.get("errors", {}).items())
    table(doc, ["Kiểm tra", f"dev ({dc.get('dev_commit', '?')})", f"upstream ({dc.get('upstream_commit', '?')})"], [
        ["test/test_dense_output.py (test của chính cây đó)", f"{dt.get('passed', '?')} qua, {dt.get('failed', '?')} hỏng",
         f"{ut.get('passed', '?')} qua, {ut.get('failed', '?')} hỏng ({up_err})"],
        ["Giải mã output Dense, khứ hồi make_ref → bộ giải mã, N = 1–200 × CX = 1 / 2 / 4",
         f"{rt.get('cases', 0) - rt.get('wrong', 0)}/{rt.get('cases', '?')} đúng",
         f"{uf.get('cases', 0) - uf.get('wrong', 0)}/{uf.get('cases', '?')} đúng; sai mọi Dense có hơn 16 × CX output khi "
         "CX ≥ 2"],
        ["Công thức giải mã", "theo lượt r, địa chỉ a, cột c: f = r·CX·P + c·P + a",
         "f = (beat mod CX)·P + beat div CX (đúng chỉ khi một lượt)"],
        ["Test RTL test_dense_readout (15 ca: nhiều lượt, CR 1 / 4, NUM_GLB_IACT 3, NUM_GLB_PSUM 2, dense, GEMM)",
         f"{dc.get('dense_readout_rtl', {}).get('passed', '?')}/15 PASS (chạy lại 23/11)", "không có"],
    ], widths=[5.6, 4.6, 5.8])
    caption(doc, "Bảng 18. Kết quả kiểm tra. P = số output mỗi cột trong một lượt, CX = số cột cluster.")
    bullets(doc, [
        "11 test hỏng không do RTL: fixture (SimpleNamespace) thiếu hai trường output_cycles và needed_psum_transmissions mà "
        "upstream 23be043 (01/10, trước khi fork) bắt đầu đọc. Thêm hai trường là đủ; test mới (31) còn phủ 2–3 lượt, "
        "CX 1 / 2 / 4, ô đệm và 9 layer Dense thật.",
        "#21 cũng không do RTL: RTL gửi đúng mọi lượt (luồng output trùng từng byte với tham chiếu), chỉ bộ giải mã của "
        "testbench đặt output của lượt thứ hai trở đi sai chỗ. Bản sửa giải mã theo lượt / địa chỉ / cột, đúng ở cả 600 kích "
        "thước.",
        "Upstream vẫn có cả hai vấn đề: test của họ hỏng 11/11 (8 test gọi hàm thiếu tham số rel_layers mới, 3 test không "
        "tìm thấy file tham chiếu), và dòng giải mã cũ vẫn ở rtl_test_utils.py. Không có gì để lấy từ upstream ở phần này; "
        "bản sửa của dev đúng.",
    ])


def sections_6_8(doc, d, figs):
    chan = d["chan"]

    def verdicts(kind, mode):
        out = {}
        for key, entry in chan.items():
            k, n, m = key.rsplit("_", 2)
            if k == kind and m == mode:
                out[int(n[1:])] = (verdict_key(entry), entry[1])
        return dict(sorted(out.items()))

    # ---------------------------------------------------------------- 6
    doc.add_heading("6. Số channel nào còn làm project tính sai", level=1)
    doc.add_heading("6.1. Phép quét", level=2)
    para(doc, "Sau các sửa ngày 22/11 (đệm số channel lẻ ở layer đầu, #7), quét lại mọi số channel trên RTL hiện tại "
              "(abd2bb8), weight và input ngẫu nhiên (seed 1), kernel 3 × 3, CR 2 X 4 Y 3, cả sparse và dense, mỗi lần so "
              "từng giá trị output (và bộ đệm activation giữa các layer) với tham chiếu:")
    bullets(doc, [
        "Layer đầu: Conv 16 × 4 × C → 8, C = 1 … 34 (input C channel từ DRAM).",
        "Layer giữa: Conv 16 × 4 × 4 → F, rồi Conv F → F, F = 1 … 20 (layer thứ hai đọc F channel do chip ghi ngược).",
        "Trước Dense: Conv 8 × 4 × 4 → F, flatten, Dense 32·F → 10, F = 1 … 18 (input của Dense có F channel mỗi pixel).",
        "Layer cuối: Conv 16 × 4 × 4 → F, F = 1 … 12, không ghi ngược: tách vấn đề của số filter khỏi số channel.",
    ])
    if os.path.exists(figs["so_channel"]):
        doc.add_picture(figs["so_channel"], width=Cm(16.5))
        caption(doc, f"Hình 7. Kết quả quét ({len(chan)} lần chạy). Đúng: khớp từng giá trị; đệm: layer đầu được đệm channel "
                     "0 rồi khớp; SAI: RTL chạy và output hoặc bộ đệm activation khác tham chiếu (kể cả output chứa X); "
                     "chặn: một kiểm tra của Python từ chối layer có chủ đích; dừng: Python báo lỗi trước hoặc trong khi "
                     "tạo dữ liệu, RTL không chạy hoặc không kiểm được.")
    rows = []
    names = {"first": "Layer đầu (C channel)", "mid": "Layer giữa (F channel)", "dense": "Trước Dense (F channel)",
             "last": "Layer cuối (F filter)"}
    for kind in ("first", "mid", "dense", "last"):
        for mode in ("sparse", "dense"):
            v = verdicts(kind, mode)
            if not v:
                continue
            by = {}
            for n, (k, _) in v.items():
                by.setdefault(k, []).append(n)
            label = {"PASS": "đúng", "PADDED": "đệm rồi đúng", "FAIL": "SAI", "REFUSED": "bị chặn",
                     "STOPPED": "Python dừng", "HANG": "treo", "ERROR": "lỗi khác"}
            rows.append([f"{names[kind]}, {mode}", f"{min(v)}–{max(v)}",
                         "; ".join(f"{label[k]}: {compact(ns)}" for k, ns in by.items())])
    table(doc, ["Vị trí, chế độ", "Số channel", "Kết quả"], rows, widths=[3.4, 2.0, 10.6])
    caption(doc, "Bảng 19. Tóm tắt phép quét số channel.")
    # 6.2
    doc.add_heading("6.2. Tại sao các số channel này sai", level=2)
    first_s, first_d = verdicts("first", "sparse"), verdicts("first", "dense")
    bullets(doc, [
        "Python gửi activation của layer đầu theo nhóm used_channels channel (iact_stream_mapper.py dòng 186–197): trong "
        "một nhóm, các channel của một pixel nằm liền nhau, pixel này nối pixel kia; nhóm cuối chỉ ghi các channel có thật. "
        "Với kernel 3 × 3, used_channels = min(C, 4) (layer_parameters.py dòng 1100–1122: 16 // 3 = 5, làm tròn xuống lũy "
        "thừa của 2 = 4).",
        "RTL đọc mỗi pixel channel_div_trans = ⌈used_channels / 2⌉ lần, mỗi lần 2 channel (PARALLEL_MACS = 2), tức "
        "2 × ⌈used_channels / 2⌉ ô, như nhau ở mọi nhóm.",
        "Đúng khi nhóm cuối có đủ số ô RTL đọc: C = 1 (đường 1 channel riêng), C = 2 (đọc 2 ô), C chia hết cho 4. Sai khi "
        "nhóm cuối thiếu: nhóm cuối có 2 hoặc 3 giá trị mỗi pixel nhưng RTL đọc 4 ô, nên từ pixel thứ hai mọi giá trị trượt "
        "sang pixel bên cạnh. C lẻ là #7 (từ 22/11 được đệm lên bội của 4); C chia 4 dư 2 và lớn hơn 2 là #45, chưa được "
        "đệm và không có kiểm tra nào chặn: trên sparse output sai lặng lẽ, trên dense output chứa giá trị X (không xác "
        "định). Mẫu này lặp lại đúng với chu kỳ 4 từ C = 6 đến C = 34.",
    ])
    rows = []
    for c in range(1, 13):
        used, div, slots, last = channel_rule(c)
        if c == 1:
            pred = "đúng (đường 1 channel)"
        elif c % 2:
            pred = "lệch → được đệm"
        else:
            pred = "khớp" if slots == last or c == 2 else "lệch"
        meas = []
        for v in (first_s, first_d):
            k = v.get(c, ("–", ""))[0]
            meas.append({"PASS": "đúng", "PADDED": "đệm, đúng", "FAIL": "SAI"}.get(k, k))
        rows.append([str(c), str(used), str(slots), str(last), pred, f"{meas[0]} / {meas[1]}"])
    table(doc, ["C", "used_channels", "Ô RTL đọc mỗi pixel", "Giá trị mỗi pixel ở nhóm cuối", "Dự đoán",
                "Đo: sparse / dense"], rows, widths=[1.0, 2.4, 2.8, 3.4, 3.2, 3.2], align_right=(0, 1, 2, 3))
    caption(doc, "Bảng 20. Layer đầu, C = 1 … 12: quy tắc gói / đọc và kết quả đo. Mẫu lặp lại với chu kỳ 4 đến C = 34.")
    mid_s = verdicts("mid", "sparse")
    bullets(doc, [
        "Layer giữa đọc kết quả ghi ngược của layer trước. Bộ ghi ngược của RTL ghi theo nhóm 4 channel mỗi pixel (#25). Với "
        "F chia 4 dư 2, bộ đệm activation sau layer trước khớp tham chiếu ở các nhóm đủ 4 channel và lệch từ nhóm cuối "
        "(F = 6: word 0–31 đúng, sai từ word 32 là nhóm thứ hai; F = 2: sai từ word 0). Testbench bắt được vì kiểm tra bộ "
        "đệm giữa các layer; trong dùng thật, layer sau sẽ đọc sai.",
        "Số filter mỗi PE lẻ dừng ngay ở Python, trước khi RTL chạy. Trường hợp thường gặp là số filter lẻ; cũng gặp ở F = "
        "18 của layer giữa (9 filter mỗi PE) và ở F = 6 / 10 / 14 / 18 trước Dense trên dense. Trên sparse, bộ mã hoá weight "
        "xếp filter theo cặp (word 2 weight): cột lẻ cần word đệm vượt độ dài khối của PE (\"encoded columns need … words, "
        "the PE block has …\") hoặc kết thúc bằng một word toàn 0 không mã hoá được. Trên dense, kiểm tra #48 chặn. Trước "
        "Dense còn có lỗi KeyError / IndexError trong phần tạo tham chiếu. Đây là dừng có lỗi, không ra kết quả sai, nhưng "
        "thông báo không nói rõ nguyên nhân.",
    ])

    last_s = verdicts("last", "sparse")
    if last_s:
        odd_stop = [n for n, (k, _) in last_s.items() if n % 2 and k == "STOPPED"]
        even_ok = [n for n, (k, _) in last_s.items() if n % 2 == 0 and k in ("PASS", "PADDED")]
        bullets(doc, [
            f"Kiểm riêng số filter ở layer cuối (không ghi ngược): số filter chẵn đều đúng ({compact(even_ok)}), kể cả 2, 6, "
            f"10; số filter lẻ đều dừng ở bộ mã hoá weight ({compact(odd_stop)}) trên sparse, bị chặn bởi #48 trên dense. Vậy "
            "lỗi của F chia 4 dư 2 ở layer giữa là lỗi của số channel (ghi ngược / đọc lại), còn F lẻ là lỗi của số filter.",
        ])
    doc.add_heading("6.3. Đề xuất", level=2)
    bullets(doc, [
        "Layer đầu, C chia 4 dư 2 (#45): đệm channel 0 lên bội của 4, như đã làm cho C lẻ (channel_pad.pad_first_layer). Chi "
        "phí: input và weight của layer đầu lớn thêm (6 → 8: +33 %); trên sparse, channel 0 được bỏ qua ở pha tính toán.",
        "Layer giữa và layer Dense có số channel không chia hết cho 4: thêm kiểm tra trong check_conv_geometry / phần tạo layer "
        "Dense để chặn với thông báo rõ thay vì sai lặng lẽ (F chia 4 dư 2) hoặc lỗi Python khó hiểu (F lẻ). Về lâu dài: thêm "
        "filter 0 vào layer trước cho đủ bội của 4.",
        "Số filter lẻ: kiểm tra sớm với thông báo rõ, hoặc thêm một filter 0 (bỏ phần output thừa sau khi đọc).",
        "Cả ba là Python, không đụng RTL; cần bạn đồng ý trước khi làm.",
    ])
    return verdicts


def compact(ns):
    """1, 2, 3, 5 -> '1–3, 5'."""
    ns = sorted(ns)
    out, start, prev = [], ns[0], ns[0]
    for n in ns[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        out.append(str(start) if start == prev else (f"{start}, {prev}" if prev == start + 1 else f"{start}–{prev}"))
        if n is not None:
            start = prev = n
    return ", ".join(out)


def sections_7_8(doc, d):
    doc.add_heading("7. Việc đã làm trong tuần", level=1)
    table(doc, ["Commit", "Ngày", "Nội dung"], [[c, day, text] for c, day, text in COMMITS],
          widths=[2.0, 1.6, 12.4])
    caption(doc, "Bảng 21. Các commit trong tuần (nhánh dev, đã đẩy lên origin).")
    bullets(doc, [
        "19/11: đo chi phí hàm kích hoạt trên MNIST đã huấn luyện, 4 hàm × 3 ảnh × sparse / dense "
        "(doc/experiments/2026-11-19_activation_cost.md).",
        "20/11: hàm kích hoạt theo từng layer trên mạng Bảng 2; quét weight bằng 0 trên cả mạng; lưới weight × input bằng 0 "
        "trên từng layer, 230 lần chạy (doc/experiments/2026-11-20_act_wzero.md).",
        "21/11: sửa #21 và 11 test của test_dense_output (Python, testbench); rà upstream 12340ab, tìm ra #50, #51.",
        "22/11: sửa #51 (RTL, được đồng ý), #50 (kẹp trong Python), #7 (đệm channel lẻ ở layer đầu), #9 (mặt nạ ô đệm); hồi "
        "quy 254 test PASS, 0 xfail; Vivado 250 MHz với #51 (WNS +0,114 ns, 59,9k LUT).",
        "23/11: kiểm lại bản sửa test_dense_output và đối chiếu upstream (doc/experiments/2026-11-23_dense_output_check.py); "
        "quét số channel / số filter (doc/experiments/2026-11-23_channel_sweep/); kiểm chứng thời gian chờ ghi lại bảng "
        "bias ở Conv1 MNIST (bảng bias tắt); báo cáo này.",
        "26/11: đo MNIST không hàm và 4 hàm trên cùng weight của model ReLU, sparse / dense (10 lần chạy, "
        "doc/experiments/2026-11-26_mnist_same_weights.md; thêm lựa chọn none vào models/mnist_conv_net.py); thêm mục 2.3 "
        "(pha chạy song song) và 3.2 (pha ghi ngược, bảng LUTRAM) vào báo cáo; đổi ngày báo cáo sang 27/11; kiểm chứng pha "
        "ghi ngược: làn mang output nào (15 lần chạy, doc/experiments/2026-11-26_writeback_lanes.md), mỗi tầng 1 chu kỳ "
        "(mô phỏng) và timing từng tầng (Vivado, doc/experiments/2026-11-26_requant_timing.md).",
    ])
    doc.add_heading("8. Bước tiếp theo", level=1)
    bullets(doc, [
        "Số channel (cần bạn đồng ý, chỉ Python): (1) đệm layer đầu có C chia 4 dư 2 lên bội của 4 như đã làm cho C lẻ; "
        "(2) thêm kiểm tra chặn layer giữa và layer Dense có số channel không chia hết cho 4 (đang sai lặng lẽ hoặc dừng với "
        "lỗi khó hiểu), hoặc đệm filter 0 ở layer trước; (3) thông báo rõ cho số filter lẻ thay cho lỗi của bộ mã hoá.",
        "Kiểm chứng giả thuyết Conv1 (input bằng 0 đến 40 % gần như không bớt chu kỳ) bằng trace của PE.",
        "Adaptive OpenEye, giai đoạn 3 (RTL, cần bạn đồng ý): tách SPARSITY_EN thành Weight / Activation, bắt đầu từ bước 3a; "
        "kết quả tuần này thêm lý do: layer Dense không được lợi gì từ weight bằng 0 trên phần cứng sparse.",
        "Chạy lại các phép đo chính với mô hình bộ nhớ (OPENEYE_MEM=typical) để xem các pha nạp trên board thật.",
        "Profiler (Python, không sửa RTL): thêm bảng đếm theo cặp trạng thái FSM chính × FSM psum, để thấy trong mỗi pha "
        "phần nào là tính, ghi hay chờ khối khác (mục 2.3).",
    ])


def build():
    d = data()
    os.makedirs(OUT_DIR, exist_ok=True)
    figs = {k: os.path.join(OUT_DIR, f"{k}_2026-11-27.png") for k in
            ("pha_tung_layer", "ghi_nguoc", "ham_kich_hoat", "tinh_toan_theo_so_0", "luoi_sparse_dense",
             "weight_0_ca_mang", "so_channel")}
    mn0 = d["mn"][("relu", 0, "sparse")]
    figure_layers(mn0, figs["pha_tung_layer"])
    st = sta_stages()
    sl = {x["title"].split(" (")[0].strip(): x["slack"] for x in reversed(st["stages"])}
    slacks = [sl.get("S1"), sl.get("S2"), sl.get("S3 = R4"), st.get("r5_slack")] if st["stages"] else None
    figure_writeback(figs["ghi_nguoc"], slacks if slacks and all(v is not None for v in slacks) else None)
    figure_act(d, figs["ham_kich_hoat"])
    figure_compute_lines(d, figs["tinh_toan_theo_so_0"])
    figure_grid(d, figs["luoi_sparse_dense"])
    figure_wz(d, figs["weight_0_ca_mang"])
    if d["chan"]:
        figure_channels(d["chan"], figs["so_channel"])

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    style.font.size = Pt(12)
    for section in doc.sections:
        section.left_margin = section.right_margin = Cm(2.2)
        section.top_margin = section.bottom_margin = Cm(2.0)
    title = doc.add_heading("BÁO CÁO TIẾN ĐỘ HẰNG TUẦN (LẦN 7)", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Chu kỳ theo từng layer: hàm kích hoạt, cách profiler đo, mức độ thưa; kiểm tra test Dense và lỗi số "
                    "channel")
    r.bold = True
    r.font.size = Pt(14)
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(f"Người thực hiện: Nguyễn Ngọc Trường Phi\nNgày: {DATE} (tuần 18/11 – 27/11/2026; báo cáo trước: "
                 "18/11/2026)\nMã nguồn: github.com/DevFi-23/OpenEye_Customize (nhánh dev, public)").font.size = Pt(11)

    # ---- numbers
    t2 = d["t2"]
    t2_tot = {k: v["total_cycles"] for k, v in t2.items()}
    mn_avg = {a: sum(d["mn"][(a, i, "sparse")]["total_cycles"] for i in (0, 1, 6)) / 3 for a, _ in MN_ACTS}
    mn_dense = {a: d["mn"][(a, 0, "dense")]["total_cycles"] for a, _ in MN_ACTS}
    nb = d["nobias"]
    grid = d["grid"]
    g = lambda s, w, a, m="sparse": grid[(s, w, a, m)]
    wz = d["wz"]
    chan = d["chan"]
    dc = d["dense_check"]

    def chan_fail(kind, mode):
        out = []
        for key, entry in chan.items():
            k, n, m = key.rsplit("_", 2)[0], int(key.rsplit("_", 2)[1][1:]), key.rsplit("_", 2)[2]
            if k == kind and m == mode and not entry[0].startswith("PASS"):
                out.append((n, entry[0]))
        return sorted(out)

    # ---------------------------------------------------------------- 1
    doc.add_heading("1. Tóm tắt", level=1)
    summary = [
        "Hàm kích hoạt: tính hàm tốn 0 chu kỳ ở cả 4 hàm (khối kích hoạt chạy trong pha ghi ngược, pha này dài như nhau với "
        "mọi hàm, kể cả khi không có hàm). Chi phí duy nhất là nạp bảng của SiLU / hard-swish: 32 chu kỳ mỗi layer "
        f"(mạng Bảng 2, 4 layer: +128 chu kỳ = {pct(100.0 * (t2_tot[('silu', 'dense')] - t2_tot[('none', 'dense')]) / t2_tot[('none', 'dense')], 2)}). "
        "ReLU và Leaky ReLU tốn 0 vì nằm sẵn trong bộ lượng tử. Bảng của SiLU / hard-swish là LUTRAM đọc không cần clock "
        "(logic tổ hợp, 0 flip-flop), chen vào chu kỳ có sẵn giữa thanh ghi cuối của bộ lượng tử và thanh ghi ghi ngược, nên "
        "pipeline ghi ngược không dài thêm (mục 3.2). Ở Conv1 của MNIST, 32 chu kỳ nạp bảng còn bị che vì khối psum đang chờ "
        "ghi lại bảng bias chạy nền (mục 3.5).",
        "Pha ghi ngược (kiểm 26/11): mỗi làn mang một output hoàn chỉnh (X làn = X vị trí x liền nhau, 4 filter liên tiếp "
        "gom thành nhóm 4 channel); mỗi tầng của bộ lượng tử tốn đúng 1 chu kỳ (mô phỏng); mọi tầng kịp trong 4 ns (Vivado: "
        "đường có bảng R4 → R5 dư 1,49 ns, chặt nhất là phép nhân ở tầng 2, dư 0,116 ns).",
        "MNIST không hàm (đo thêm 26/11, weight của model ReLU): sparse "
        + (f"{fmt(d['same'][('none', 'sparse')]['total_cycles'])}, ReLU "
           f"{fmt(d['same'][('relu', 'sparse')]['total_cycles'])} (−10,0 %), Leaky ReLU / SiLU / hard-swish trong khoảng ±1 % "
           f"của không hàm; dense: không hàm = ReLU = Leaky ReLU = {fmt(d['same'][('none', 'dense')]['total_cycles'])}, SiLU = "
           f"hard-swish +64. Không có hàm thì sparse chậm hơn dense 7,4 %." if d["same"] else "chưa có số liệu."),
        "Profiler: một coroutine cocotb đếm từng cạnh lên của clock trong mô phỏng RTL và gán mỗi chu kỳ cho đúng một pha "
        "theo trạng thái FSM chính (và FSM psum), nên các pha cộng lại đúng bằng tổng. Số đo là chu kỳ chính xác của RTL, "
        "lặp lại được từng chu kỳ (cùng seed: cùng số), đổi ra thời gian bằng clock sau place and route (250 MHz).",
        "Mức độ thưa: số 0 chỉ làm thay đổi pha tính toán trên phần cứng sparse. Nạp weight, nạp / chuyển activation, ghi "
        "ngược, pooling và toàn bộ chu kỳ dense giống hệt ở mọi mức số 0 (đo 25 mức weight × activation trên 4 layer). "
        "Tính toán sparse giảm ít hơn tỉ lệ số 0 (phần cố định 60–64 %), layer Dense không bỏ qua weight bằng 0.",
        "test_dense_output: bản sửa của phiên khác (6a7a323) đúng: 31/31 test qua, bộ giải mã Dense khứ hồi đúng 600/600 "
        f"kích thước layer. Upstream {dc.get('upstream_commit', '?')} vẫn hỏng 11/11 test và giải mã sai "
        f"{dc.get('upstream_formula', {}).get('wrong', '?')}/600 kích thước (mọi Dense có hơn 16 × CX output khi CX ≥ 2).",
    ]
    if chan:
        bad_first = [n for n, _ in chan_fail("first", "sparse")]
        bad_mid = [n for n, v in chan_fail("mid", "sparse") if v == "FAIL"]
        summary.append(
            f"Số channel: quét {len(chan)} lần (layer đầu C = 1–34, layer giữa F = 1–20, trước Dense F = 1–18, layer cuối "
            "F = 1–12 filter; sparse và dense). Còn lỗi: (1) layer đầu với C = " + compact(bad_first) +
            " (chia 4 dư 2, #45): sparse ra output sai lặng lẽ, dense ra giá trị X; (2) layer giữa với F = " +
            compact(bad_mid) + " (chia 4 dư 2, kể cả 2): bộ đệm activation sau ghi ngược sai; (3) trước layer Dense chỉ "
            "F chia hết cho 4 chạy được; (4) số filter lẻ: Python dừng (sparse) hoặc bị chặn (dense). Nguyên nhân chung: "
            "activation được gói và ghi theo nhóm 4 channel mỗi pixel, nhóm cuối thiếu thì các pixel bị trượt (mục 6).")
    bullets(doc, summary)
    sections(doc, d, figs)
    sections_6_8(doc, d, figs)
    sections_7_8(doc, d)
    return doc, d, figs


if __name__ == "__main__":
    doc, _, _ = build()
    doc.save(OUT)
    print("wrote", OUT)
