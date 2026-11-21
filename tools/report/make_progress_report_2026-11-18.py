#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Build the sixth Word progress report (weekly, Vietnamese, 2026-11-18): the per-layer sparse / dense direction
("Adaptive OpenEye"), reported along the user's four phases (1 profiling, 2 cost model, 3 RTL, 4 verification and
benchmark). The tables and figures compare only measured sparse and dense runs and the per-layer choice derived from
them, on the cases of the report of 2026-11-10 (trained MNIST, 4 activations x 2 roundings x 2 modes = 16 runs, on
today's RTL) and on the Table 2 network of the paper. The per-layer weight format P1 appears only as an experiment of
phase 3 (section 5.2) and in the comparison of directions (section 7).

Inputs (measured; only the Vivado / Yosys resource numbers are typed in, with their source):
  doc/perf/activation_2026-11-18_rounding/trained_<act>_img0_<sparse|dense>_<floor|round>.json   16 MNIST runs
  doc/perf/wght_layout_2026-11-18_mnist/trained_<act>_img0_sparse.json   weight zeros per layer; the step 2 experiment
  doc/perf/paper_table3_2026-11-18{,_dense,_relu_sparse,_wlayout,_relu_wlayout}/paper_<cfg>.json   Table 2 network
  doc/perf/layer_sweep_2026-11-18_{sparse,dense}/<shape>_z<zeros>_<cfg>.json   one layer against the zero share

    ~/tools/docenv/bin/python tools/report/make_progress_report_2026-11-18.py
Output: doc/reports/2026-11-18_TienDo/BaoCao_TienDo_OpenEye_2026-11-18.docx, four figure PNGs and the per-layer profiling
dataset dataset_theo_layer_2026-11-18.csv next to it.
"""

import csv
import glob
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.table import WD_ALIGN_VERTICAL  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_progress_report as base_report  # noqa: E402
from make_progress_report import bullets, fmt, para, table  # noqa: E402

REPO = base_report.REPO
PERF = os.path.join(REPO, "doc", "perf")
R16 = os.path.join(PERF, "activation_2026-11-18_rounding")
WLAYOUT = os.path.join(PERF, "wght_layout_2026-11-18_mnist")
OUT_DIR = os.path.join(REPO, "doc", "reports", "2026-11-18_TienDo")
OUT = os.path.join(OUT_DIR, "BaoCao_TienDo_OpenEye_2026-11-18.docx")
CSV_OUT = os.path.join(OUT_DIR, "dataset_theo_layer_2026-11-18.csv")
FIG_PHASES = os.path.join(OUT_DIR, "pha_theo_layer_2026-11-18.png")
FIG_CASES = os.path.join(OUT_DIR, "tong_16_truong_hop_2026-11-18.png")
FIG_WINNER = os.path.join(OUT_DIR, "che_do_tot_theo_layer_2026-11-18.png")
FIG_SWEEP = os.path.join(OUT_DIR, "nguong_hoa_von_2026-11-18.png")
FIG_PACK = os.path.join(OUT_DIR, "dong_goi_weight_2026-11-18.png")
OLD_FIGS = ["chu_ky_theo_pha_2026-11-18.png", "nguong_so_0_2026-11-18.png", "chi_phi_weight_0_2026-11-18.png"]
DATE = "18/11/2026"
CLOCK_NS = 4.0     # 250 MHz, met after place and route (doc/synth/2026-11-18_route4ns_default_zu7ev)

SURFACE, INK, INK_2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e8e7e2", "#d6d5cf"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
MODE_COLOR = {"sparse": SLOTS[0], "dense": SLOTS[1], "layer": SLOTS[2]}
MODE_VI = {"sparse": "Sparse", "dense": "Dense", "layer": "Theo layer (S/D)"}
ACTS = [("relu", "ReLU"), ("leaky_relu", "Leaky ReLU"), ("silu", "SiLU"), ("hardswish", "hard-swish")]
ROUNDS = [("floor", "floor"), ("round", "làm tròn")]
DEFAULT_ROUND = {"relu": "floor", "leaky_relu": "round", "silu": "round", "hardswish": "round"}
CASES = [(a, r) for a, _ in ACTS for r, _ in ROUNDS]
LAYERS = [(0, "Conv1"), (2, "Conv2"), (4, "Conv3"), (5, "Dense")]
T2_CFGS = [f"cr{r}_x{x}_y{y}" for y in (3, 4) for x in (2, 4) for r in (1, 2, 4, 8)]
T2_SHOW = [("cr1_x2_y3", "CR 1 X 2", "cr1x2"), ("cr2_x4_y3", "CR 2 X 4", "cr2x4"), ("cr8_x4_y3", "CR 8 X 4", "cr8x4")]
# resources (Vivado 2026-11-18 default build; dense build 2026-11-10 + bias table; Yosys estimates of 2026-11-11 / 11-18)
LUT_SPARSE, LUT_DENSE = 60113, 43957
LUT_WSPLIT = 281                      # GET_WGHT 8 -> 12 bit row assembly (p1_wght_row.v)
LUT_DUAL_FSM = (4800, 9600)           # second FSM in each of the 48 PEs, +100-200 LUT per PE (2026-11-11_mixed_mode)


# ---------------------------------------------------------------- data
def load(path):
    with open(path) as f:
        return json.load(f)


def ph(p, name, key="cycles"):
    return (p["phases"].get(name) or {}).get(key) or 0


def num(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",")


def pct(x, digits=1, sign=True):
    if round(x, digits) == 0:
        return "0 %"
    s = f"{x:+.{digits}f}" if sign else f"{x:.{digits}f}"
    return s.replace(".", ",").replace("-", "−") + " %"


def rel(a, b):
    return 100.0 * (a - b) / b


def us(cycles):
    return num(cycles * CLOCK_NS / 1000.0, 1)


def kb(bits):
    return num(bits / 8 / 1024, 1)


def zshare(layer, key="input"):
    d = layer["info"].get(key) or {}
    return 100.0 * d.get("zeros", 0) / d["values"] if d.get("values") else 0.0


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


def layer_name(layer):
    i = layer["info"]
    if i["name"].startswith("Conv"):
        return f"Conv {i['iact_size_x']}×{i['iact_size_y']}×{i['channels']}→{i['filters']}"
    if i["name"].startswith("Dense"):
        return f"Dense {i['iact_size_x']}→{i['filters']}"
    return f"Pooling {i['iact_size_x']}×{i['iact_size_y']}"


def w8_layers(s, d, layout=None):
    """Weight 8 bit + activation sparse per layer: measured (the step 2 run with the dense weight layout, with the
    weight load of dense hardware) when the layout run is given, else estimated as sparse minus the weight-load
    difference (step 2: within 0.2 points of the measured value)."""
    src = layout or s
    return [l["total_cycles"] - max(0, ph(l, "load_wght") - ph(ld, "load_wght")) for l, ld in zip(src["layers"],
                                                                                                  d["layers"])]


def choices(s, d, w8):
    """Per-layer best of the measured sparse and dense layers (the per-layer direction with today's formats), and the
    best of the three when the weight and activation configurations are separate."""
    sd = sum(min(ls["total_cycles"], ld["total_cycles"]) for ls, ld in zip(s["layers"], d["layers"]))
    full = sum(min(ls["total_cycles"], ld["total_cycles"], w) for ls, ld, w in zip(s["layers"], d["layers"], w8))
    return sd, full


def data():
    mn = {}
    for act, rnd in CASES:
        s = load(os.path.join(R16, f"trained_{act}_img0_sparse_{rnd}.json"))
        d = load(os.path.join(R16, f"trained_{act}_img0_dense_{rnd}.json"))
        layout = load(os.path.join(WLAYOUT, f"trained_{act}_img0_sparse.json")) if rnd == DEFAULT_ROUND[act] else None
        w8 = w8_layers(s, d, layout)
        sd, full = choices(s, d, w8)
        mn[(act, rnd)] = {"s": s, "d": d, "layer": sd, "full": full, "w8": w8, "measured_w8": layout is not None}
    weights = {act: load(os.path.join(WLAYOUT, f"trained_{act}_img0_sparse.json")) for act, _ in ACTS}
    t2 = {}
    for relu in (True, False):
        for cfg in T2_CFGS:
            s = load(os.path.join(PERF, "paper_table3_2026-11-18_relu_sparse" if relu else "paper_table3_2026-11-18",
                                  f"paper_{cfg}.json"))
            d = load(os.path.join(PERF, "paper_table3_2026-11-18_dense", f"paper_{cfg}.json"))
            lay = load(os.path.join(PERF, "paper_table3_2026-11-18_relu_wlayout" if relu else
                                    "paper_table3_2026-11-18_wlayout", f"paper_{cfg}.json"))
            w8 = w8_layers(s, d, lay)
            sd, full = choices(s, d, w8)
            t2[(cfg, relu)] = {"s": s, "d": d, "layer": sd, "full": full, "w8": w8, "lay": lay}
    return mn, weights, t2


def sweep(shape, zero, cfg):
    s = load(os.path.join(PERF, "layer_sweep_2026-11-18_sparse", f"{shape}_z{zero}_{cfg}.json"))
    d = load(os.path.join(PERF, "layer_sweep_2026-11-18_dense", f"{shape}_z{zero}_{cfg}.json"))
    return s, d


def shape_class(layer):
    i = layer["info"]
    if i["name"] == "Dense":
        return "fc" if i.get("iact_size_x", 0) > 256 else None
    if i["name"] != "Convolution2D":
        return None
    if i.get("channels") == 1:
        return "conv1"
    return "conv2" if i.get("iact_size_x", 0) >= 14 else "conv3"


def sweep_curves():
    """compute(sparse) / compute(dense) of one layer against its input zero share, per (shape class, configuration)."""
    curves = {}
    for f in glob.glob(os.path.join(PERF, "layer_sweep_2026-11-18_sparse", "*_z*_*.json")):
        case = os.path.basename(f)[:-5]
        g = os.path.join(PERF, "layer_sweep_2026-11-18_dense", case + ".json")
        if not os.path.exists(g):
            continue
        shape, rest = case.split("_z", 1)
        zero, cfg = rest.split("_", 1)
        cs, cd = ph(load(f)["layers"][0], "compute"), ph(load(g)["layers"][0], "compute")
        curves.setdefault((shape, cfg), []).append((float(zero), cs / cd))
    for k in curves:
        curves[k].sort()
    return curves


def sweep_fit(shape, cfg):
    """Least-squares fit of the swept sparse compute cycles as a + b x (1 - input zero share): a the fixed part, b the
    part that shrinks with the zeros; with the dense compute cycles of the same layer (the same at every zero share)."""
    pts = []
    for z in ("0", "0.25", "0.5", "0.75", "0.9"):
        s, d = sweep(shape, z, cfg)
        pts.append((1 - float(z), ph(s["layers"][0], "compute")))
    mx, my = sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)
    b = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)
    return my - b * mx, b, ph(d["layers"][0], "compute")


def predict(curves, shape, cfg, z, cd, dw):
    """Phase 2 cost model: cycles(sparse) - cycles(dense) of a layer = weight-load difference (transfer sizes) +
    (ratio(z) - 1) x dense compute, the ratio interpolated in the sweep. Negative: sparse is faster."""
    pts = curves[(shape, cfg)]
    if z <= pts[0][0]:
        r = pts[0][1]
    elif z >= pts[-1][0]:
        r = pts[-1][1]
    else:
        r = next(r0 + (r1 - r0) * (z - z0) / (z1 - z0) for (z0, r0), (z1, r1) in zip(pts, pts[1:]) if z <= z1)
    return dw + (r - 1.0) * cd


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


def figure_packing():
    """One row of the weight buffer (24 weights at CR 2 X 4 Y 3) on the 64-bit DMA: sparse 12-bit fields (8-bit value +
    4-bit overhead) packed back to back, the row padded to a whole word; dense 8-bit values."""
    fig, ax = new_figure(10.5, 2.5)
    ax.set_facecolor(SURFACE)
    n, word = 24, 64
    lanes = [(1.0, "Sparse", [(8, SLOTS[0]), (4, "#9fc3ee")], 5), (0.0, "Dense", [(8, SLOTS[1])], 3)]
    for y, label, parts, words in lanes:
        x = 0
        for _ in range(n):
            for width, color in parts:
                ax.add_patch(plt.Rectangle((x, y), width, 0.62, facecolor=color, edgecolor=SURFACE, linewidth=0.6))
                x += width
        pad = words * word - x
        if pad:
            ax.add_patch(plt.Rectangle((x, y), pad, 0.62, facecolor="#e2e1dc", edgecolor="#9b9a95", hatch="////",
                                       linewidth=0.6))
        for w in range(words + 1):
            ax.plot([w * word, w * word], [y - 0.08, y + 0.70], color=INK, linewidth=1.6)
        for w in range(words):
            ax.text(w * word + word / 2, y - 0.2, f"word {w + 1}", ha="center", va="center", fontsize=7.5, color=INK_2)
        bits = sum(wd for wd, _ in parts) * n
        ax.text(-6, y + 0.31, label, ha="right", va="center", fontsize=9.5, color=INK, fontweight="bold")
        note = (f"{n} × {sum(wd for wd, _ in parts)} bit = {bits} bit → {words} word"
                + (f" ({pad} bit đệm)" if pad else " (vừa đủ)") + f" = {words} chu kỳ")
        ax.text(words * word + 6, y + 0.31, note, ha="left", va="center", fontsize=8, color=INK)
    ax.set_xlim(-40, 5 * word + 175)
    ax.set_ylim(-0.4, 1.8)
    ax.axis("off")
    handles = [Patch(facecolor=SLOTS[0], label="giá trị 8 bit (sparse)"), Patch(facecolor="#9fc3ee", label="overhead 4 bit"),
               Patch(facecolor=SLOTS[1], label="giá trị 8 bit (dense)"),
               Patch(facecolor="#e2e1dc", edgecolor="#9b9a95", hatch="////", label="đệm")]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, fontsize=8, bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(FIG_PACK, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_phases(mn):
    """Per compute layer, sparse and dense side by side, split into weight load, compute and the other phases, for the
    two extremes of the cases: ReLU floor (many zeros) and SiLU round (few zeros)."""
    groups = [("load_wght", "nạp weight", SLOTS[0]), ("compute", "tính toán", SLOTS[1]), (None, "các pha khác", "#9b9a95")]
    fig, axes = new_figure(10.5, 4.0, 1, 2)
    for ax, (case, title) in zip(axes, [(("relu", "floor"), "ReLU, floor (nhiều số 0)"),
                                        (("silu", "round"), "SiLU, làm tròn (ít số 0)")]):
        style_axes(ax, "y")
        s, d = mn[case]["s"], mn[case]["d"]
        ticks, labels = [], []
        top = max(max(s["layers"][k]["total_cycles"], d["layers"][k]["total_cycles"]) for k, _ in LAYERS)
        for j, (k, name) in enumerate(LAYERS):
            for m, (mode, prof) in enumerate((("S", s), ("D", d))):
                x = j * 3 + m
                layer = prof["layers"][k]
                bottom = 0
                for gk, _, color in groups:
                    v = ph(layer, gk) if gk else layer["total_cycles"] - ph(layer, "load_wght") - ph(layer, "compute")
                    ax.bar(x, v, bottom=bottom, width=0.86, color=color, edgecolor=SURFACE, linewidth=1.2)
                    bottom += v
                ax.text(x, bottom + top * 0.01, f"{num(bottom / 1000, 1)}k", ha="center", va="bottom", fontsize=6.6,
                        color=INK)
                ticks.append(x)
                labels.append(mode)
            ax.text(j * 3 + 0.5, -0.1, name, transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=8.5,
                    color=INK)
        ax.set_ylim(0, top * 1.1)
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=7.5, color=INK_2)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt(int(v))))
        ax.set_title(title, fontsize=9, color=INK, loc="left")
    axes[0].set_ylabel("chu kỳ của layer", fontsize=8, color=INK_2)
    handles = [Patch(facecolor=c, label=lab) for _, lab, c in groups]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.0))
    fig.text(0.5, 0.005, "S = sparse, D = dense. Pooling giống hệt ở hai chế độ (không vẽ).", ha="center", fontsize=7.5,
             color=INK_2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    fig.savefig(FIG_PHASES, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_cases(mn):
    """Total cycles of the 16 runs: sparse, dense and the per-layer choice of the two, per model and rounding."""
    fig, ax = new_figure(10.0, 4.8)
    style_axes(ax)
    rows = [(f"{lab}, {rl}" + (" *" if DEFAULT_ROUND[a] == r else ""), mn[(a, r)]) for a, lab in ACTS for r, rl in ROUNDS]
    h = 0.26
    for i, (_, run) in enumerate(rows):
        vals = {"sparse": run["s"]["total_cycles"], "dense": run["d"]["total_cycles"], "layer": run["layer"]}
        for j, mode in enumerate(("sparse", "dense", "layer")):
            y = i + (j - 1) * h
            ax.barh(y, vals[mode], height=h * 0.9, color=MODE_COLOR[mode], edgecolor=SURFACE, linewidth=0.8,
                    label=MODE_VI[mode] if i == 0 else None)
            ax.text(vals[mode] + 500, y, f"{us(vals[mode])} µs", va="center", fontsize=6.4, color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=8, color=INK)
    ax.invert_yaxis()
    hi = max(max(r["s"]["total_cycles"], r["d"]["total_cycles"]) for _, r in rows)
    lo = 150000
    ax.set_xlim(lo, hi * 1.06)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt(int(v))))
    ax.set_xlabel(f"chu kỳ cả mạng (trục bắt đầu ở {fmt(lo)} để thấy rõ chênh lệch)", fontsize=8, color=INK_2)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.09), ncol=3, frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIG_CASES, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_winner(mn):
    """Per compute layer and case, how much slower dense is than sparse (diverging: blue = sparse faster, orange =
    dense faster, neutral gray at 0)."""
    fig, ax = new_figure(8.6, 4.6)
    ax.set_facecolor(SURFACE)
    cmap = LinearSegmentedColormap.from_list("div", [SLOTS[1], "#efeee9", SLOTS[0]])
    rows = [(a, lab, r, rl) for a, lab in ACTS for r, rl in ROUNDS]
    vals = [[rel(mn[(a, r)]["d"]["layers"][k]["total_cycles"], mn[(a, r)]["s"]["layers"][k]["total_cycles"])
             for k, _ in LAYERS] for a, _, r, _ in rows]
    lim = max(abs(v) for row in vals for v in row)
    for i, row in enumerate(vals):
        for j, v in enumerate(row):
            color = cmap(0.5 + v / (2 * lim))
            ax.add_patch(plt.Rectangle((j, i), 0.96, 0.9, facecolor=color, edgecolor=SURFACE, linewidth=0))
            ink = "white" if abs(v) / lim > 0.55 else INK
            ax.text(j + 0.48, i + 0.3, "sparse" if v > 0 else "dense", ha="center", va="center", fontsize=7.6,
                    color=ink, fontweight="bold")
            ax.text(j + 0.48, i + 0.64, f"dense {pct(v, 1)}", ha="center", va="center", fontsize=7.2, color=ink)
    ax.set_xlim(0, len(LAYERS))
    ax.set_ylim(len(rows), 0)
    ax.set_xticks([j + 0.48 for j in range(len(LAYERS))])
    ax.set_xticklabels([n for _, n in LAYERS], fontsize=9, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.45 for i in range(len(rows))])
    ax.set_yticklabels([f"{lab}, {rl}" for _, lab, _, rl in rows], fontsize=8.5, color=INK)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    fig.text(0.01, 0.01, "Chữ đậm: chế độ nhanh hơn cho layer đó. \"dense ±x %\": chu kỳ của layer ở dense so với sparse. "
             "Xanh: sparse nhanh hơn, cam: dense nhanh hơn.", fontsize=7.0, color=INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG_WINNER, facecolor=fig.get_facecolor())
    plt.close(fig)


def figure_sweep():
    """Break-even: whole-layer cycles sparse / dense against the input zero share, one line per configuration."""
    shapes = [("conv2", "Conv 14×14×16 → 32"), ("conv3", "Conv 7×7×32 → 32"), ("fc", "Dense 1568 → 32")]
    cfgs = [("cr1x2", "CR 1 X 2", SLOTS[0], "-", "o"), ("cr2x4", "CR 2 X 4", SLOTS[1], "--", "s"),
            ("cr8x4", "CR 8 X 4", SLOTS[2], ":", "^")]
    fig, axes = new_figure(10.5, 3.6, 1, 3)
    for ax, (shape, title) in zip(axes, shapes):
        style_axes(ax, "y")
        ax.spines["left"].set_visible(True)
        ax.spines["left"].set_color(AXIS)
        ax.axhline(1.0, color=INK_2, linewidth=1, linestyle=(0, (4, 3)))
        for cfg, label, color, ls, mk in cfgs:
            xs, ys = [], []
            for z in ("0", "0.25", "0.5", "0.75", "0.9"):
                s, d = sweep(shape, z, cfg)
                xs.append(float(z) * 100)
                ys.append(s["total_cycles"] / d["total_cycles"])
            ax.plot(xs, ys, color=color, linestyle=ls, marker=mk, markersize=5, linewidth=2, label=label)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel("số 0 trong input của layer (%)", fontsize=8, color=INK_2)
    axes[0].set_ylabel("chu kỳ sparse / dense (cả layer)", fontsize=8, color=INK_2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.02))
    fig.text(0.5, 0.015, "Dưới đường 1: sparse nhanh hơn; trên: dense nhanh hơn. Chỗ cắt đường 1 là ngưỡng hoà vốn.",
             ha="center", va="bottom", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.08, 1, 0.9))
    fig.savefig(FIG_SWEEP, facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------- docx helpers
def caption(doc, text):
    cap = doc.add_paragraph(text)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True
    cap.runs[0].font.size = Pt(10)


def write_dataset(mn, weights, t2):
    """Phase 1 deliverable: one row per (run, layer) with shape, zero shares, data sizes and the cycles of every phase
    in both modes."""
    phases = ["load_config", "load_iact", "load_wght", "load_bias", "load_quant", "load_act", "convert_iact", "compute",
              "writeback", "pooling", "readout"]
    head = ["model", "case", "layer", "name", "macs", "weights", "weight_zeros", "input_values", "input_zeros",
            "wght_bits_dense", "wght_bits_csc_nonzero", "wght_bits_chip_sparse", "wght_dma_words_sparse",
            "wght_dma_words_dense"] + [f"{p}_{m}" for m in ("sparse", "dense") for p in phases] + \
        ["total_sparse", "total_dense", "best"]
    rows = []

    def add(model, case, s, d, wsrc):
        for k, (ls, ld) in enumerate(zip(s["layers"], d["layers"])):
            w = (wsrc["layers"][k]["info"].get("weights") or {}) if wsrc else {}
            nw, zw = w.get("values", 0), w.get("zeros", 0)
            inp = ls["info"].get("input") or {}
            row = [model, case, k, layer_name(ls), macs(ls), nw, zw, inp.get("values", 0), inp.get("zeros", 0),
                   nw * 8, (nw - zw) * 12, nw * 12, ph(ls, "load_wght", "in_accepted"), ph(ld, "load_wght", "in_accepted")]
            row += [ph(ls, p) for p in phases] + [ph(ld, p) for p in phases]
            row += [ls["total_cycles"], ld["total_cycles"],
                    "equal" if ls["total_cycles"] == ld["total_cycles"] else
                    ("sparse" if ls["total_cycles"] < ld["total_cycles"] else "dense")]
            rows.append(row)
    for (act, rnd), run in mn.items():
        add("mnist_trained", f"{act}_{rnd}", run["s"], run["d"], weights[act])
    for (cfg, relu), run in t2.items():
        add("paper_table2", f"{cfg}_{'relu' if relu else 'noact'}", run["s"], run["d"], run["lay"])
    with open(CSV_OUT, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(head)
        wr.writerows(rows)
    return len(rows)


def rng(vals):
    a, b = pct(max(vals)), pct(min(vals))
    return a if a == b else f"{a} đến {b}"


# ---------------------------------------------------------------- report
def build():
    mn, weights, t2 = data()
    os.makedirs(OUT_DIR, exist_ok=True)
    for old in OLD_FIGS:                     # figures of the first version of this report
        if os.path.exists(os.path.join(OUT_DIR, old)):
            os.remove(os.path.join(OUT_DIR, old))
    n_rows = write_dataset(mn, weights, t2)
    figure_phases(mn)
    figure_cases(mn)
    figure_winner(mn)
    figure_sweep()
    figure_packing()
    curves = sweep_curves()

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
    r = sub.add_run("Chọn sparse / dense theo từng layer (Adaptive OpenEye): tiến độ theo 4 giai đoạn")
    r.bold = True
    r.font.size = Pt(14)
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.add_run(f"Người thực hiện: Nguyễn Ngọc Trường Phi\nNgày: {DATE} (tuần 11/11 – 18/11/2026; báo cáo trước: 10/11/2026, "
                 "cập nhật 12/11/2026)\nMã nguồn: github.com/DevFi-23/OpenEye (nhánh dev, private)").font.size = Pt(11)

    # numbers used in the text
    tot = {c: {"s": mn[c]["s"]["total_cycles"], "d": mn[c]["d"]["total_cycles"], "l": mn[c]["layer"],
               "f": mn[c]["full"]} for c in CASES}
    best_single = {c: min(tot[c]["s"], tot[c]["d"]) for c in CASES}
    gain_layer = {c: rel(tot[c]["l"], best_single[c]) for c in CASES}
    gain_full = {c: rel(tot[c]["f"], best_single[c]) for c in CASES}
    relu = mn[("relu", "floor")]
    t2tot = {k: {"s": v["s"]["total_cycles"], "d": v["d"]["total_cycles"], "l": v["layer"], "f": v["full"]}
             for k, v in t2.items()}
    t2_gain_layer = {r_: [rel(t2tot[(c, r_)]["l"], min(t2tot[(c, r_)]["s"], t2tot[(c, r_)]["d"])) for c in T2_CFGS]
                     for r_ in (True, False)}
    t2_gain_full = {r_: [rel(t2tot[(c, r_)]["f"], min(t2tot[(c, r_)]["s"], t2tot[(c, r_)]["d"])) for c in T2_CFGS]
                    for r_ in (True, False)}
    dvs = {c: rel(tot[c]["d"], tot[c]["s"]) for c in CASES}
    other_acts = [c for c in CASES if c[0] != "relu"]
    l0s, l0d = relu["s"]["layers"][0], relu["d"]["layers"][0]
    l4s, l4d = relu["s"]["layers"][4], relu["d"]["layers"][4]
    l5s, l5d = relu["s"]["layers"][5], relu["d"]["layers"][5]
    zr = [zshare(mn[("relu", r_)]["s"]["layers"][k]) for r_, _ in ROUNDS for k, _ in LAYERS[1:]]
    zo = [zshare(mn[(a, r_)]["s"]["layers"][k]) for a, _ in ACTS[1:] for r_, _ in ROUNDS for k, _ in LAYERS[1:]]

    # cost model check (phase 2)
    checks = [(f"MNIST {a} {rnd}", "cr2x4", run["s"], run["d"]) for (a, rnd), run in mn.items()]
    for cfg, _, key in T2_SHOW:
        for r_ in (True, False):
            checks.append((f"T2 {cfg} {r_}", key, t2[(cfg, r_)]["s"], t2[(cfg, r_)]["d"]))
    right = total = lost = 0
    for name, cfg, s_, d_ in checks:
        for ls, ld in zip(s_["layers"], d_["layers"]):
            shape = shape_class(ls)
            if shape is None or (shape, cfg) not in curves:
                continue
            pred = predict(curves, shape, cfg, zshare(ls) / 100.0, ph(ld, "compute"),
                           ph(ls, "load_wght") - ph(ld, "load_wght"))
            meas = ls["total_cycles"] - ld["total_cycles"]
            total += 1
            if (pred < 0) == (meas < 0) or meas == 0:
                right += 1
            else:
                lost += abs(meas)

    # ---------------------------------------------------------------- 1
    doc.add_heading("1. Tóm tắt", level=1)
    bullets(doc, [
        "Hướng phát triển: chọn sparse hay dense cho từng layer theo dữ liệu của layer đó (Adaptive OpenEye), làm theo 4 giai "
        "đoạn: (1) profiling, (2) mô hình chi phí, (3) RTL, (4) kiểm chứng và benchmark. Tuần này xong giai đoạn 1 và phần "
        "lớn giai đoạn 2, chưa sửa RTL: project đang ở cuối giai đoạn 2.",
        f"Giai đoạn 1 (16 lần chạy MNIST của báo cáo 10/11, chạy lại trên RTL hiện tại, và mạng Bảng 2 ở 16 cấu hình × có / "
        f"không ReLU): không chế độ nào thắng ở mọi layer. Cả mạng, dense nhanh hơn sparse ở Leaky ReLU / SiLU / hard-swish "
        f"(dense {rng([dvs[c] for c in other_acts])}), sparse nhanh hơn ở ReLU (dense {pct(dvs[('relu', 'floor')])} với "
        "floor). Trong cùng một mạng, Conv1 và layer Dense hợp dense, Conv2 / Conv3 sau ReLU hợp sparse. Hai chế độ chỉ khác "
        f"nhau ở 2 pha: nạp weight (sparse chậm hơn 67 %) và tính toán (dense chậm hơn khi input có nhiều số 0). Dataset theo "
        f"layer: {n_rows} dòng.",
        f"Giai đoạn 2: mô hình chi phí chọn đúng chế độ cho {right}/{total} layer đã kiểm. Chọn sparse / dense theo layer "
        f"(tính từ các lần chạy đo được), chu kỳ so với chế độ tốt hơn của cả mạng: {rng(list(gain_layer.values()))} trên MNIST, "
        f"{rng(t2_gain_layer[True] + t2_gain_layer[False])} trên mạng Bảng 2. Khi tách cấu hình Weight / Activation như đề "
        f"xuất: {rng(list(gain_full.values()))} trên MNIST, {rng(t2_gain_full[True] + t2_gain_full[False])} trên mạng Bảng 2.",
        "Giai đoạn 3: thiết kế Adaptive theo đúng các mục của đề xuất (tách SPARSITY_EN thành Weight / Activation, chọn chế độ "
        "lúc chạy, Scheduler, thanh ghi cấu hình layer, giữ đúng psum khi chuyển layer), chi phí ước lượng +8–17 % LUT. Đã thử "
        "nghiệm mục \"tách Weight / Activation\" trên RTL hiện tại bằng mô phỏng (không sửa RTL): khớp từng bit ở 99/99 lần "
        "chạy. Phần sửa RTL sẽ làm theo thứ tự 3a → 3d sau khi được duyệt.",
        "Các việc khác trong tuần: gửi bias một lần mỗi filter (MNIST −9,3 %, Bảng 3 −10 %), sửa lỗi #49, rà soát upstream, "
        "nghiên cứu bão hoà. Hồi quy 225 test = 221 PASS + 4 xfail đã biết; Vivado 250 MHz (60.113 LUT, 188 BRAM, 12 URAM, "
        "4 DSP).",
    ])

    # ---------------------------------------------------------------- 2
    doc.add_heading("2. Hướng phát triển và 4 giai đoạn", level=1)
    para(doc, "Hướng phát triển: một bộ tăng tốc Adaptive, mỗi layer chạy ở chế độ hợp với nó (dense cho layer ít số 0, "
              "sparse cho layer nhiều số 0), chọn bằng cấu hình theo layer. Để tránh sửa RTL quá sớm, việc chia thành 4 giai "
              "đoạn:")
    table(doc, ["Giai đoạn", "Nội dung", "Kết quả cần có"], [
        ["1. Profiling (không sửa RTL)", "Model CNN/DNN int8; tỉ lệ số 0 của weight và activation theo layer; kích thước dữ "
         "liệu dense / sparse; overhead metadata", "Dataset profiling cho từng layer"],
        ["2. Cost model", "Số MAC dense / sparse; chu kỳ nạp weight; chu kỳ nạp activation; decode và điều khiển PE; ngưỡng "
         "hoà vốn", "Mô hình dự đoán chế độ tối ưu"],
        ["3. RTL", "Tách SPARSITY_EN thành cấu hình Weight và Activation; chọn dense / sparse lúc chạy; Scheduler; thanh ghi "
         "cấu hình layer; chuyển layer không sai địa chỉ psum và dữ liệu", "Adaptive OpenEye Accelerator"],
        ["4. Verification và Benchmark", "Cocotb: so với ONNX Runtime, latency từng layer, chu kỳ nạp dữ liệu, "
         "throughput / MOPS, so sánh Dense / Sparse / Adaptive", "Chứng minh Adaptive cải thiện hiệu suất"],
    ], widths=[3.4, 8.6, 4.6])
    doc.add_heading("2.1. Đánh giá 4 giai đoạn", level=2)
    bullets(doc, [
        "Cách chia tốt: đo trước, mô hình hoá sau, chỉ sửa RTL khi đã biết sửa gì và lợi bao nhiêu, rồi chứng minh bằng "
        "benchmark. Thứ tự này đúng mục tiêu tránh sửa RTL quá sớm, và mỗi giai đoạn có một sản phẩm kiểm tra được (dataset, "
        "mô hình, bản dựng, bảng benchmark).",
        "Giai đoạn 1: cần đo theo định dạng thật của chip, không theo CSC lý thuyết. Trên OpenEye khối weight của mỗi PE có "
        "độ dài cố định nên weight 0 không làm luồng truyền ngắn đi, và overhead là 4 bit cho mỗi giá trị 8 bit. Ngoài tỉ lệ "
        "số 0 nên đo chu kỳ từng pha (profiler đã có), vì quyết định nằm ở pha nạp weight và pha tính toán.",
        "Giai đoạn 2: ngưỡng hoà vốn phụ thuộc cấu hình cluster nhiều hơn tỉ lệ số 0 (mục 4.4), nên mô hình có tham số cấu "
        "hình. Chu kỳ nạp activation giống hệt ở hai chế độ, nên không ảnh hưởng lựa chọn.",
        "Giai đoạn 3: mục \"tách Weight / Activation\" mang lại phần lớn lợi ích đo được (mục 4.6) và rẻ nhất, nên làm trước; "
        "mục \"chọn chế độ lúc chạy\" cho FSM của PE tốn nhiều tài nguyên nhất (hai FSM trong mỗi PE). Scheduler có thể nằm "
        "trong toolchain (lựa chọn tĩnh, biết lúc biên dịch như scale lượng tử) và ghi vào thanh ghi cấu hình layer.",
        "Giai đoạn 4: hạ tầng đã có (so khớp từng bit, profiler theo pha / layer, đếm word DMA, so với ONNX Runtime ở model "
        "thật). Nên đo thêm tài nguyên Vivado của mỗi bản dựng để so chu kỳ cùng với diện tích.",
    ])
    doc.add_heading("2.2. Có đang đi theo 4 giai đoạn không, đang ở đâu", level=2)
    table(doc, ["Giai đoạn", "Đã làm", "Trạng thái"], [
        ["1. Profiling", "Profiler ghi số 0 của input và weight mỗi layer; 16 trường hợp MNIST + 64 lần mạng Bảng 2 ở cả hai "
         "chế độ; quét một layer 0–90 % số 0 × 4 dạng × 3 cấu hình × 2 chế độ (120 lần); dataset theo layer (CSV)",
         "Xong (2 mạng)"],
        ["2. Cost model", "Chu kỳ theo pha; ngưỡng hoà vốn theo dạng layer và cấu hình; mô hình dự đoán chế độ, kiểm trên mọi "
         "layer tính của các mạng đã đo", "Gần xong: còn đưa vào toolchain"],
        ["3. RTL", "Thiết kế theo từng mục của đề xuất, ước lượng chi phí; thử nghiệm mục tách Weight / Activation trên RTL "
         "hiện tại bằng mô phỏng (không sửa RTL)", "Chờ duyệt để sửa RTL"],
        ["4. Verification", "Mọi lần chạy khớp từng bit; latency theo layer, chu kỳ nạp, MOPS của Dense / Sparse (mục 6); "
         "Vivado mốc", "Một phần; Adaptive chờ giai đoạn 3"],
    ], widths=[2.8, 10.6, 3.2])
    para(doc, "Project đi đúng thứ tự 4 giai đoạn: chưa sửa một dòng RTL nào cho hướng này, mọi quyết định dựa trên số đo của "
              "giai đoạn trước. Hiện ở cuối giai đoạn 2; bước kế tiếp là giai đoạn 3.")

    # ---------------------------------------------------------------- 3
    doc.add_heading("3. Giai đoạn 1: Profiling", level=1)
    doc.add_heading("3.1. Model và các trường hợp", level=2)
    bullets(doc, [
        "MNIST đã huấn luyện (các trường hợp của báo cáo 10/11): Conv 28×28×1→32, MaxPool, Conv 14×14×32→64, MaxPool, Conv "
        "7×7×64→64, Dense 3136→10; lượng tử int8 tĩnh bằng toolchain (onnx2model). 4 hàm kích hoạt (ReLU, Leaky ReLU, SiLU, "
        "hard-swish) × 2 cách làm tròn (floor, làm tròn gần nhất) × 2 chế độ (sparse, dense) = 16 lần chạy, ảnh test 0, cấu "
        "hình CR 2 X 4 Y 3 (48 PE). Cả 16 lần chạy lại trên RTL hiện tại (bias theo filter, #49 đã sửa), 16/16 khớp từng bit.",
        "Mạng Bảng 2 của bài báo: Conv 28×28×1→16, Conv 14×14×16→32, Conv 7×7×32→32, Dense 1568→32, Dense 32→10, weight int8 "
        "ngẫu nhiên (seed 1); 16 cấu hình (CR 1 / 2 / 4 / 8 × X 2 / 4 × Y 3 / 4) × (có ReLU, không hàm kích hoạt) × 2 chế độ = 64 lần, tất cả khớp từng bit.",
        "Phần cứng, giống nhau ở hai chế độ trừ SPARSITY_EN: lưới CR × 2 cluster (CR = số hàng cluster, 2 cột "
        "cluster), mỗi cluster X × Y PE (X = số cột PE, Y = số hàng PE), mỗi PE 2 MAC song song, DMA 64 bit. CR 1 X 2 Y 3 "
        "= 2 cluster × 6 PE = 12 PE; CR 2 X 4 Y 3 = 4 cluster × 12 PE = 48 PE (cấu hình của các lần chạy MNIST); "
        "CR 8 X 4 Y 3 = 16 cluster × 12 PE = 192 PE. Mô phỏng RTL bằng Icarus qua cocotb.",
        "Profiler gán mỗi chu kỳ vào một pha theo trạng thái FSM chính: nạp cấu hình, nạp activation, nạp weight, nạp bias, "
        "nạp bảng lượng tử / hàm kích hoạt, chuyển activation vào cluster, tính toán, ghi ngược, pooling, đọc kết quả. Bộ nhớ "
        "lý tưởng; thời gian ở 250 MHz (đạt sau place and route).",
    ])

    doc.add_heading("3.2. Tỉ lệ số 0 theo layer", level=2)
    rows = []
    for k, name in LAYERS:
        nw = weights["relu"]["layers"][k]["info"]["weights"]["values"]
        wz = [zshare(weights[a]["layers"][k], "weights") for a, _ in ACTS]
        cells = [f"{num(zshare(mn[(a, 'floor')]['s']['layers'][k]), 0)} / {num(zshare(mn[(a, 'round')]['s']['layers'][k]), 0)} %"
                 for a, _ in ACTS]
        rows.append([f"{name} ({layer_name(relu['s']['layers'][k])})", fmt(nw), f"{num(min(wz), 1)}–{num(max(wz), 1)} %"]
                    + cells)
    table(doc, ["Layer", "Số weight", "Weight 0 (4 model)", "Activation 0 ở input: ReLU (floor / tròn)", "Leaky ReLU",
                "SiLU", "hard-swish"], rows, widths=[3.6, 1.6, 2.0, 2.6, 2.2, 2.2, 2.2], align_right=(1, 2, 3, 4, 5, 6))
    bullets(doc, [
        f"Weight đã huấn luyện gần như không có số 0 (0,3–2,9 %). Số 0 của activation do hàm kích hoạt quyết định: ReLU "
        f"{num(min(zr), 0)}–{num(max(zr), 0)} % ở input của Conv2 / Conv3 / Dense, Leaky ReLU / SiLU / hard-swish chỉ "
        f"{num(min(zo), 0)}–{num(max(zo), 0)} %; cách làm tròn đổi thêm vài điểm (Leaky ReLU: floor biến số âm nhỏ thành −1 "
        "nên gần như không còn số 0). Input của Conv1 là ảnh đã chuẩn hoá: 0 % số 0.",
    ])

    doc.add_heading("3.3. Kích thước dữ liệu dense / sparse và overhead metadata", level=2)
    rows = []
    s, d = relu["s"], relu["d"]
    for k, name in LAYERS:
        w = weights["relu"]["layers"][k]["info"]["weights"]
        nw, zw = w["values"], w["zeros"]
        ls, ld = s["layers"][k], d["layers"][k]
        ws_, wd_ = ph(ls, "load_wght", "in_accepted"), ph(ld, "load_wght", "in_accepted")
        rows.append([name, fmt(nw), kb(nw * 8), kb((nw - zw) * 12), kb(nw * 12), f"{fmt(ws_)} ({kb(ws_ * 64)} KB)",
                     f"{fmt(wd_)} ({kb(wd_ * 64)} KB)", pct(rel(wd_, ws_))])
    table(doc, ["Layer", "Số weight", "Weight 8 bit trần (KB)", "CSC lý thuyết: weight ≠ 0 × 12 bit (KB)",
                "Định dạng sparse trên chip: mọi weight × 12 bit (KB)", "Thực truyền, sparse: word DMA (KB)", "dense",
                "Dense so với sparse"], rows, widths=[1.5, 1.6, 1.7, 2.3, 2.3, 2.8, 2.6, 1.8],
          align_right=(1, 2, 3, 4, 5, 6, 7))
    c2 = weights["relu"]["layers"][2]["info"]["weights"]
    w2s, w2d = ph(s["layers"][2], "load_wght", "in_accepted"), ph(d["layers"][2], "load_wght", "in_accepted")
    caption(doc, f"KB = bit / 8 / 1024. Ba cột KB đầu là một bản weight của layer: số weight × 8 bit, số weight khác 0 × 12 "
                 f"bit, số weight × 12 bit (ví dụ Conv2: {fmt(c2['values'])} × 8 = {fmt(c2['values'] * 8)} bit = "
                 f"{kb(c2['values'] * 8)} KB; ({fmt(c2['values'])} − {c2['zeros']}) × 12 = "
                 f"{fmt((c2['values'] - c2['zeros']) * 12)} bit = {kb((c2['values'] - c2['zeros']) * 12)} KB; "
                 f"{fmt(c2['values'])} × 12 = {fmt(c2['values'] * 12)} bit = {kb(c2['values'] * 12)} KB). Cột thực truyền = "
                 f"số word DMA 64 bit đo được trong pha nạp weight × 64 bit, gồm các lần nạp lại weight cho mỗi lượt tính và "
                 f"phần đệm của mỗi hàng (Conv2: {fmt(w2s)} word = {fmt(w2s // 5)} hàng × 5 word ở sparse, {fmt(w2d)} word = "
                 f"{fmt(w2d // 3)} hàng × 3 word ở dense; {fmt(w2s // 5)} hàng × 24 weight = {fmt(w2s // 5 * 24)} ô = "
                 f"{w2s // 5 * 24 // c2['values']} lần {fmt(c2['values'])} weight).")
    bullets(doc, [
        "Overhead metadata: mỗi giá trị 8 bit đi kèm 4 bit overhead (số vị trí 0 đứng trước), tức +50 %. Định dạng nén chỉ nhỏ "
        "hơn 8 bit trần khi tỉ lệ số 0 trên 1/3 (12 × (1 − z) < 8). Với weight đã huấn luyện (≤ 3 % số 0) định dạng nén luôn "
        f"lớn hơn; với activation sau ReLU ({num(min(zr), 0)}–{num(max(zr), 0)} %) nó nhỏ hơn. Đây là lý do nên tách cấu hình "
        "Weight và Activation.",
        "Trên chip, khối weight của mỗi PE có độ dài cố định (vị trí của weight 0 được lấp bằng ô đệm), nên ở chế độ sparse "
        "kích thước truyền không giảm theo số weight 0. Word DMA nạp weight gồm cả các lần nạp lại cho mỗi lượt tính (Conv2, "
        "Conv3 nạp lại weight nhiều lần): dense luôn ít hơn 40 % (3 word thay vì 5 cho mỗi hàng 24 weight, DMA 64 bit).",
        "Activation qua DMA và trong bộ đệm activation là giá trị 8 bit trần ở cả hai chế độ (8 giá trị mỗi word 64 bit); "
        "4 bit overhead chỉ được thêm trên chip, khi bộ dựng luồng chuyển activation vào cluster ở chế độ sparse (ô 12 bit), "
        "còn ở dense ô vẫn 8 bit. Vì vậy dữ liệu activation trên DMA giống hệt ở hai chế độ (mục 3.4).",
    ])

    doc.add_heading("3.4. Chu kỳ theo pha: sparse và dense", level=2)
    para(doc, "MNIST ReLU floor, cả mạng:")
    phase_vi = [("load_config", "nạp cấu hình"), ("load_iact", "nạp activation"), ("load_wght", "nạp weight"),
                ("load_bias", "nạp bias"), ("load_quant", "nạp bảng lượng tử"), ("convert_iact", "chuyển activation"),
                ("compute", "tính toán"), ("writeback", "ghi ngược"), ("pooling", "pooling"), ("readout", "đọc kết quả")]
    rows = [[lab, fmt(ph(s, k)), fmt(ph(d, k)), pct(rel(ph(d, k), ph(s, k))) if ph(s, k) else "—"] for k, lab in phase_vi]
    rows.append(["Tổng", fmt(s["total_cycles"]), fmt(d["total_cycles"]), pct(rel(d["total_cycles"], s["total_cycles"]))])
    rows.append(["Thời gian ở 250 MHz (µs)", us(s["total_cycles"]), us(d["total_cycles"]), ""])
    table(doc, ["Pha", "Sparse", "Dense", "Dense so với sparse"], rows, widths=[5.4, 3.2, 3.2, 3.4], align_right=(1, 2, 3))
    inp0 = s["layers"][0]["info"]["input"]["values"]
    bullets(doc, [
        f"Nạp activation bằng nhau ({fmt(ph(s, 'load_iact'))} chu kỳ ở cả hai chế độ) vì: (1) chỉ input của layer đầu (ảnh "
        f"{fmt(inp0)} giá trị) đi qua DMA, input của các layer sau do chip tự ghi ngược vào bộ đệm activation (pha ghi ngược); "
        f"(2) activation trên DMA là giá trị 8 bit trần ở cả hai chế độ: {fmt(inp0)} × 8 bit / 64 bit = {fmt(inp0 // 8)} word, "
        f"cộng {fmt(ph(s, 'load_iact', 'in_accepted') - inp0 // 8)} word đệm cho đủ nhóm ô của bộ đệm = "
        f"{fmt(ph(s, 'load_iact', 'in_accepted'))} word, 1 word mỗi chu kỳ; luồng DMA của hai lần chạy giống hệt từng word. "
        "Overhead 4 bit của sparse được thêm sau, trên chip.",
        f"Chuyển activation vào cluster cũng bằng nhau ({fmt(ph(s, 'convert_iact'))} chu kỳ): bộ dựng luồng đọc mọi ô của bộ "
        "đệm ở cả hai chế độ; việc bỏ qua số 0 nằm trong PE, ở pha tính toán.",
    ])
    doc.add_picture(FIG_PHASES, width=Cm(16.5))
    caption(doc, "Hình 1. Chu kỳ từng layer tính, sparse (S) và dense (D), chia theo nạp weight, tính toán và các pha khác. "
                 "MNIST ReLU floor và SiLU làm tròn, ảnh test 0, CR 2 X 4 Y 3 (48 PE).")
    para(doc, "16 trường hợp, cả mạng:")
    rows, shade_cells = [], []
    for a, lab in ACTS:
        for rnd, rl in ROUNDS:
            run = mn[(a, rnd)]
            ts, td = run["s"]["total_cycles"], run["d"]["total_cycles"]
            cs, cd = ph(run["s"], "compute"), ph(run["d"], "compute")
            rows.append([lab if rnd == "floor" else "", rl + (" *" if DEFAULT_ROUND[a] == rnd else ""),
                         f"{fmt(ph(run['s'], 'load_wght'))} / {fmt(ph(run['d'], 'load_wght'))}", f"{fmt(cs)} / {fmt(cd)}",
                         fmt(ts - ph(run["s"], "load_wght") - cs), f"{fmt(ts)} ({us(ts)} µs)", f"{fmt(td)} ({us(td)} µs)",
                         pct(rel(td, ts))])
            shade_cells.append((len(rows), 5 if ts <= td else 6))
    t = table(doc, ["Hàm", "Làm tròn", "Nạp weight: S / D", "Tính toán: S / D", "Các pha khác (như nhau)", "Sparse: tổng",
                    "Dense: tổng", "Dense so với sparse"], rows, widths=[1.8, 1.6, 2.4, 2.8, 1.8, 2.6, 2.6, 1.6],
              align_right=(2, 3, 4, 5, 6, 7))
    for r_, c_ in shade_cells:
        base_report.shade(t.rows[r_].cells[c_], "D7F0E3")
    caption(doc, "Ô xanh: chế độ nhanh hơn của trường hợp đó. * cách làm tròn mặc định của toolchain.")

    doc.add_heading("3.5. Nhược điểm của từng chế độ", level=2)
    table(doc, ["Chế độ", "Nhược điểm (số đo)"], [
        ["Sparse", f"Nạp weight chậm hơn 67 % ({fmt(ph(s, 'load_wght'))} so với {fmt(ph(d, 'load_wght'))} chu kỳ trên "
         "MNIST) vì 4 bit overhead cho mỗi weight, dù weight gần như không có số 0. FSM sparse chậm hơn khi input không có "
         f"số 0 (Conv1: tính toán {fmt(ph(l0s, 'compute'))} so với {fmt(ph(l0d, 'compute'))}, "
         f"{pct(rel(ph(l0s, 'compute'), ph(l0d, 'compute')))}). Layer Dense chậm hơn "
         f"{pct(rel(l5s['total_cycles'], l5d['total_cycles']))} dù {num(zshare(l5s), 0)} % input bằng 0, vì thời gian của "
         f"nó gần như toàn là nạp weight. Với hàm kích hoạt để lại ít số 0 (Leaky ReLU, SiLU, hard-swish) chậm hơn dense "
         f"{num(-max(dvs[c] for c in other_acts), 1)}–{num(-min(dvs[c] for c in other_acts), 1)} % cả mạng. Tốn nhiều tài "
         f"nguyên hơn: {fmt(LUT_SPARSE)} LUT so với khoảng {fmt(LUT_DENSE)} LUT của bản dense (+37 %)."],
        ["Dense", f"Không bỏ qua được số 0: tính toán của Conv3 sau ReLU ({num(zshare(l4s), 0)} % số 0) "
         f"{fmt(ph(l4d, 'compute'))} so với {fmt(ph(l4s, 'compute'))} chu kỳ ở sparse "
         f"({pct(rel(ph(l4d, 'compute'), ph(l4s, 'compute')))}); cả mạng ReLU chậm hơn {pct(dvs[('relu', 'floor')])} (floor). "
         "Lợi thế của dense mất dần khi mạng có nhiều số 0 hơn (model lớn có ReLU, weight đã prune)."],
    ], widths=[2.2, 14.4])
    para(doc, "Mỗi chế độ thua ở một loại layer khác nhau, nên chọn một chế độ cho cả mạng luôn mất phần lợi ở các layer còn "
              "lại. Đây là cơ sở của hướng chọn theo layer (mục 4.6).")

    # ---------------------------------------------------------------- 4
    doc.add_heading("4. Giai đoạn 2: Cost model", level=1)
    doc.add_heading("4.1. Số MAC dense / sparse", level=2)
    silu = mn[("silu", DEFAULT_ROUND["silu"])]
    models41 = [("ReLU floor", "relu", relu), ("SiLU làm tròn", "silu", silu)]
    peak = 2 * 2 * 4 * 3 * 2                               # CR 2 x 2 clusters, X 4 x Y 3 PEs, 2 MACs per PE
    para(doc, "So số phép nhân (MAC) với số chu kỳ tính toán đo được, ở hai mô hình hai đầu: ReLU floor (nhiều số 0) và "
              "SiLU làm tròn (ít số 0). MNIST, ảnh test 0, CR 2 X 4 Y 3 (48 PE).")

    def merge_rows(t, col, r0, r1):
        cell = t.cell(r0, col).merge(t.cell(r1, col))
        for p in cell.paragraphs[1:]:
            if not p.text.strip():
                p._element.getparent().remove(p._element)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    def formula(layer):
        i = layer["info"]
        if i["name"].startswith("Conv"):
            kx, ky = i["kernel"]
            return f"{i['iact_size_x']} × {i['iact_size_y']} × {i['filters']} × {i['channels']} × {kx} × {ky}"
        return f"{fmt(i['iact_size_x'])} × {i['filters']}"

    left = {}
    rows_a, rows_b = [], []
    for k, name in LAYERS:
        mac = macs(relu["s"]["layers"][k])
        cd = ph(relu["d"]["layers"][k], "compute")
        for j, (mlab, act, run) in enumerate(models41):
            za = zshare(run["s"]["layers"][k]) / 100.0
            zw = zshare(weights[act]["layers"][k], "weights") / 100.0
            mac_s = mac * (1 - za) * (1 - zw)
            left[(act, k)] = mac_s / mac
            cs = ph(run["s"]["layers"][k], "compute")
            first = j == 0
            rows_a.append([name if first else "", formula(relu["s"]["layers"][k]) if first else "",
                           fmt(mac) if first else "", mlab, f"{num(za * 100, 1)} %", f"{num(zw * 100, 1)} %",
                           fmt(int(round(mac_s))), f"{num(100 * mac_s / mac, 1)} %"])
            rows_b.append([name if first else "", fmt(cd) if first else "",
                           f"{num(mac / cd, 0)}" if first else "", mlab, fmt(cs), f"{num(100 * cs / cd, 1)} %",
                           f"{num(100 * mac_s / mac, 1)} %"])
    t = table(doc, ["Layer", "Cách tính MAC dense", "MAC dense", "Model", "Input = 0", "Weight = 0", "MAC sparse",
                    "Còn lại so với dense"], rows_a,
              widths=[1.4, 3.4, 2.0, 1.9, 1.6, 1.6, 2.0, 1.9], align_right=(2, 4, 5, 6, 7))
    for j in range(len(LAYERS)):
        for col in (0, 1, 2):
            merge_rows(t, col, 1 + 2 * j, 2 + 2 * j)
    caption(doc, "Bảng a. Số MAC. MAC dense: Conv = cao × rộng output × số filter × số channel × 3 × 3, Dense = số input × "
                 "số output. MAC sparse = MAC dense × (1 − tỉ lệ input = 0) × (1 − tỉ lệ weight = 0).")
    t = table(doc, ["Layer", "Chu kỳ dense", f"MAC mỗi chu kỳ, dense (đỉnh {peak})", "Model", "Chu kỳ sparse",
                    "Thời gian còn lại", "Phép nhân còn lại"], rows_b,
              widths=[1.4, 2.0, 2.8, 1.9, 2.0, 2.2, 2.2], align_right=(1, 2, 4, 5, 6))
    for j in range(len(LAYERS)):
        for col in (0, 1, 2):
            merge_rows(t, col, 1 + 2 * j, 2 + 2 * j)
    caption(doc, "Bảng b. Chu kỳ tính toán đo được. Thời gian còn lại = chu kỳ sparse / chu kỳ dense; phép nhân còn lại "
                 f"lấy từ bảng a. Đỉnh {peak} = 48 PE × 2 MAC.")

    l4s, l4d = relu["s"]["layers"][4], relu["d"]["layers"][4]
    shares = [a / (a + b) for a, b, _ in (sweep_fit(sh, "cr2x4") for sh in ("conv2", "conv3", "fc"))]
    bullets(doc, [
        f"Sparse bớt phép nhân nhiều hơn bớt thời gian: Conv3 ReLU còn {num(100 * left[('relu', 4)], 1)} % phép nhân nhưng "
        f"còn {num(100 * ph(l4s, 'compute') / ph(l4d, 'compute'), 1)} % thời gian ({fmt(ph(l4d, 'compute'))} → "
        f"{fmt(ph(l4s, 'compute'))} chu kỳ).",
        f"Lý do: khoảng {num(min(shares) * 100, 0)}–{num(max(shares) * 100, 0)} % chu kỳ tính toán sparse là phần cố "
        "định, không giảm theo số 0 (đo trên phép quét mục 4.4). Weight bằng 0 gần như không bớt chu kỳ vì PE đọc 2 weight mỗi "
        "word. Input không có số 0 (Conv1) thì sparse chậm hơn 3 % vì giải mã (mục 4.3).",
        "Vì vậy cost model (mục 4.5) dùng tỉ số chu kỳ sparse / dense đo được, không đếm MAC.",
    ])

    doc.add_heading("4.2. Chu kỳ nạp weight và nạp activation", level=2)
    para(doc, "Nạp weight: mỗi word DMA 64 bit mất 1 chu kỳ (bộ nhớ lý tưởng). Weight được gửi theo hàng; mỗi hàng có "
              "số cluster × Y × 2 ô weight (CR 2 X 4 Y 3: 4 × 3 × 2 = 24 ô). Mỗi ô 12 bit ở sparse, 8 bit ở dense; một hàng "
              "được làm tròn lên số word nguyên:")
    doc.add_picture(FIG_PACK, width=Cm(16.5))
    caption(doc, "Hình 2. Một hàng 24 weight trên DMA 64 bit. Sparse 5 word, dense 3 word; weight bằng 0 vẫn chiếm một ô.")
    rows = []
    for k, name in LAYERS:
        ls, ld = relu["s"]["layers"][k], relu["d"]["layers"][k]
        nw = weights["relu"]["layers"][k]["info"]["weights"]["values"]
        ws, wd = ph(ls, "load_wght"), ph(ld, "load_wght")
        rows.append([name, fmt(nw), fmt(ws // 5), num(ws // 5 * 24 / nw, 2), fmt(ws), fmt(wd), f"{num(100 * wd / ws, 0)} %",
                     fmt(ph(ls, "load_iact")) if ph(ls, "load_iact") == ph(ld, "load_iact") else "≠",
                     fmt(ph(ls, "convert_iact")) if ph(ls, "convert_iact") == ph(ld, "convert_iact") else "≠"])
    table(doc, ["Layer", "Số weight", "Số hàng (24 ô)", "Số ô ÷ số weight", "Nạp weight sparse (hàng × 5)",
                "Nạp weight dense (hàng × 3)", "Dense so với sparse", "Nạp activation (S = D)",
                "Chuyển activation (S = D)"], rows,
          widths=[1.4, 1.6, 1.6, 1.6, 2.0, 2.0, 1.6, 1.9, 1.9], align_right=(1, 2, 3, 4, 5, 6, 7, 8))
    caption(doc, "Chu kỳ các pha nạp, MNIST ReLU floor, CR 2 X 4 Y 3. Số ô ÷ số weight > 1: weight được gửi nhiều lần (Conv) "
                 "hoặc có ô đệm (Dense). S = D: hai chế độ bằng nhau đúng từng chu kỳ.")

    rows = []
    for cr in (1, 2, 4, 8):
        for y in (3, 4):
            per = cr * 2 * y * 2
            s_w, d_w = math.ceil(per * 12 / 64), math.ceil(per * 8 / 64)
            rows.append([f"CR {cr}, Y {y}", f"{cr * 2} × {y} × 2 = {per}", f"{per * 12} bit → {s_w}",
                         f"{per * 8} bit → {d_w}", f"{num(100 * d_w / s_w, 0)} %"])
    table(doc, ["Cấu hình", "Ô mỗi hàng (cluster × Y × 2)", "Word sparse (× 12 bit)", "Word dense (× 8 bit)",
                "Dense so với sparse"], rows, widths=[2.4, 4.0, 3.4, 3.4, 2.6], align_right=(2, 3, 4))
    caption(doc, "Word mỗi hàng theo cấu hình (X không ảnh hưởng). Khớp số đo ở mọi layer của 16 cấu hình mạng Bảng 2.")
    bullets(doc, [
        "Dense luôn nạp weight ít hơn sparse 33 %, riêng CR 2 Y 3 ít hơn 40 % (hàng sparse 288 bit phải làm tròn lên 320). Số "
        "weight 0 không làm ngắn pha này.",
        "Nạp activation và chuyển activation vào cluster bằng nhau đúng từng chu kỳ ở mọi layer của mọi lần chạy (MNIST và "
        "16 cấu hình mạng Bảng 2), nên không tham gia lựa chọn chế độ.",
    ])

    doc.add_heading("4.3. Decode và điều khiển PE", level=2)
    para(doc, "Khi input không có số 0 thì sparse không có gì để bỏ qua; phần chênh chu kỳ tính toán so với dense cho thấy chi "
              "phí riêng của FSM sparse (giải mã overhead, điều khiển PE):")
    rows = []
    sweep_rows = [("conv1", "Conv 28×28×1→16"), ("conv2", "Conv 14×14×16→32"), ("conv3", "Conv 7×7×32→32"),
                  ("fc", "Dense 1568→32")]
    dec = []
    for shape, title in sweep_rows:
        cells = []
        for cfg in ("cr1x2", "cr2x4", "cr8x4"):
            s, d = sweep(shape, "0", cfg)
            cs, cd = ph(s["layers"][0], "compute"), ph(d["layers"][0], "compute")
            dec.append(rel(cs, cd))
            cells.append(f"{fmt(cs)} / {fmt(cd)} ({pct(rel(cs, cd))})")
        rows.append([title] + cells)
    cs0, cd0 = ph(l0s, "compute"), ph(l0d, "compute")
    rows.append(["MNIST Conv1 (ảnh)", "–", f"{fmt(cs0)} / {fmt(cd0)} ({pct(rel(cs0, cd0))})", "–"])
    table(doc, ["Layer", "CR 1 X 2", "CR 2 X 4", "CR 8 X 4"], rows, widths=[4.0, 4.0, 4.0, 4.0], align_right=(1, 2, 3))
    caption(doc, "Chu kỳ tính toán sparse / dense khi input không có số 0. Bốn dòng đầu: từng layer của mạng Bảng 2 chạy "
                 "riêng (phép quét mục 4.4).")
    bullets(doc, [
        f"Chi phí FSM sparse nhỏ: từ {pct(min(dec))} đến {pct(max(dec))} chu kỳ tính toán. Lớn nhất ở layer đầu 1 channel "
        "(Conv1: +2,6 đến +4,2 %).",
        "Conv 7×7 ở CR 1 và CR 2: sparse nhanh hơn khoảng 2 % dù input không có số 0; chưa rõ nguyên nhân, chưa phân tích.",
        "Chi phí này cộng với nạp weight dài hơn (mục 4.2) nên sparse cần đủ số 0 mới bù được: đó là ngưỡng hoà vốn ở mục 4.4.",
    ])

    doc.add_heading("4.4. Ngưỡng hoà vốn", level=2)
    para(doc, "Mỗi layer của mạng Bảng 2 chạy riêng ở cả hai chế độ, tỉ lệ số 0 của input đặt chính xác bằng móc testbench "
              "(0 / 25 / 50 / 75 / 90 %), 3 cấu hình cluster:")
    doc.add_picture(FIG_SWEEP, width=Cm(16.5))
    caption(doc, "Hình 3. Chu kỳ sparse / dense của cả layer theo tỉ lệ số 0 của input. Chỗ cắt đường 1 là ngưỡng hoà vốn. "
                 "Từng layer của mạng Bảng 2 chạy riêng, weight int8 ngẫu nhiên (seed 1), không hàm kích hoạt; Y 3 ở cả 3 "
                 "cấu hình (12, 48 và 192 PE).")
    table(doc, ["Layer", "CR 1 X 2", "CR 2 X 4", "CR 8 X 4"], [
        ["Conv 28×28×1→16 (ảnh, 1 channel)", "42 %", "60 %", "dense luôn nhanh hơn"],
        ["Conv 14×14×16→32", "4 %", "36 %", "73 %"],
        ["Conv 7×7×32→32", "6 %", "48 %", "dense luôn nhanh hơn"],
        ["Dense 1568→32", "dense luôn nhanh hơn", "dense luôn nhanh hơn", "dense luôn nhanh hơn"],
    ], widths=[5.0, 3.8, 3.8, 3.8])
    caption(doc, "Ngưỡng: tỉ lệ số 0 của input mà trên đó sparse nhanh hơn dense (cả layer).")
    bullets(doc, [
        "Không có một mật độ hoà vốn chung: cùng Conv 14×14×16→32 cần 4 % số 0 ở CR 1 X 2 nhưng 73 % ở CR 8 X 4. Càng nhiều "
        "hàng cluster, tính toán càng ngắn, phần nạp weight (nơi dense thắng) càng nặng.",
        "Layer Dense (fully connected) luôn hợp dense với định dạng hôm nay, kể cả 90 % số 0: mỗi weight chỉ dùng một lần nên "
        "thời gian là nạp weight. Nhận định \"FC nhiều số 0 → sparse\" vì vậy chỉ đúng khi tách cấu hình Weight / Activation "
        "(weight 8 bit, activation sparse; mục 5.2).",
    ])

    doc.add_heading("4.5. Mô hình dự đoán chế độ tối ưu và kiểm tra", level=2)
    para(doc, "Mô hình cho mỗi layer: chu kỳ sparse − dense = chênh lệch nạp weight (mục 4.2) + (r(z) − 1) × chu kỳ tính toán "
              "dense, với r(z) là tỉ số tính toán sparse / dense nội suy theo tỉ lệ số 0 z của input, lấy từ phép quét cùng dạng "
              "layer và cùng cấu hình. Âm thì chọn sparse.")
    para(doc, f"Kiểm tra trên mọi layer tính của 16 trường hợp MNIST và mạng Bảng 2 có / không ReLU ở 3 cấu hình: chọn đúng "
              f"{right}/{total} layer" + (f"; các layer chọn sai mất tổng cộng {fmt(lost)} chu kỳ." if lost else ".") +
              " Mô hình chỉ cần kích thước layer, cấu hình và tỉ lệ số 0 đo trên ảnh hiệu chỉnh, nên đưa được vào toolchain "
              "(onnx2model) làm Scheduler tính lịch chế độ cho từng layer.")

    doc.add_heading("4.6. Lợi ích của chọn theo layer", level=2)
    doc.add_picture(FIG_WINNER, width=Cm(15.0))
    caption(doc, "Hình 4. Chế độ nhanh hơn cho từng layer tính trong 8 trường hợp (hàm × cách làm tròn), đo được. "
                 "MNIST, ảnh test 0, CR 2 X 4 Y 3 (48 PE).")
    doc.add_picture(FIG_CASES, width=Cm(16.0))
    caption(doc, "Hình 5. Chu kỳ cả mạng của 16 lần chạy và của lựa chọn theo layer (S/D: mỗi layer lấy chế độ nhanh hơn "
                 "trong hai lần chạy đo được). * cách làm tròn mặc định. MNIST, ảnh test 0, "
                 "CR 2 X 4 Y 3 (48 PE).")
    rows = []
    for a, lab in ACTS:
        for rnd, rl in ROUNDS:
            c = (a, rnd)
            picks = " ".join("S" if mn[c]["s"]["layers"][k]["total_cycles"] < mn[c]["d"]["layers"][k]["total_cycles"]
                             else "D" for k, _ in LAYERS)
            rows.append([f"{lab}, {rl}", fmt(tot[c]["s"]), fmt(tot[c]["d"]), fmt(tot[c]["l"]), picks,
                         pct(gain_layer[c]), fmt(tot[c]["f"]) + ("" if mn[c]["measured_w8"] else " (ư.l.)"),
                         pct(gain_full[c])])
    table(doc, ["Trường hợp", "Sparse", "Dense", "Theo layer (S/D)", "Chế độ Conv1, Conv2, Conv3, Dense",
                "so với chế độ tốt hơn", "Theo layer, tách W / A", "so với chế độ tốt hơn"], rows,
          widths=[2.8, 1.8, 1.8, 2.0, 2.2, 1.8, 2.4, 1.8], align_right=(1, 2, 3, 5, 6, 7))
    rows = []
    for r_ in (True, False):
        for cfg, lab, _ in T2_SHOW:
            v = t2tot[(cfg, r_)]
            rows.append([f"Bảng 2, {'ReLU' if r_ else 'không hàm kích hoạt'}, {lab}", fmt(v["s"]), fmt(v["d"]), fmt(v["l"]),
                         pct(rel(v["l"], min(v["s"], v["d"]))), fmt(v["f"]), pct(rel(v["f"], min(v["s"], v["d"])))])
    table(doc, ["Mạng", "Sparse", "Dense", "Theo layer (S/D)", "so với chế độ tốt hơn", "Theo layer, tách W / A",
                "so với chế độ tốt hơn"], rows, widths=[4.6, 1.8, 1.8, 2.0, 2.0, 2.2, 2.0], align_right=(1, 2, 3, 4, 5, 6))
    bullets(doc, [
        f"Chọn sparse / dense theo layer với định dạng hôm nay (cột \"Theo layer (S/D)\", tính thẳng từ các lần chạy đo được) "
        f"cho chu kỳ so với chế độ tốt hơn của cả mạng: {rng(list(gain_layer.values()))} trên MNIST, {rng(t2_gain_layer[True])} "
        f"trên mạng Bảng 2 có ReLU và {rng(t2_gain_layer[False])} không hàm kích hoạt (16 cấu hình). Lợi lớn nhất khi mạng có cả "
        "layer nhiều số 0 lẫn layer ít số 0 (ReLU); khi mọi layer cùng hợp một chế độ thì kết quả bằng chế độ đó.",
        f"Khi tách cấu hình Weight / Activation (mục 1 của giai đoạn 3: một layer có thể nhận weight 8 bit mà vẫn bỏ qua "
        f"activation 0), chu kỳ so với chế độ tốt hơn: {rng(list(gain_full.values()))} trên MNIST và "
        f"{rng(t2_gain_full[True] + t2_gain_full[False])} trên mạng Bảng 2: phần lớn lợi ích của hướng Adaptive đến từ việc "
        "tách này. Chu kỳ của tổ hợp \"weight 8 bit + activation sparse\" lấy từ thử nghiệm ở mục 5.2 (đo trên RTL) với "
        "cách làm tròn mặc định, ước lượng (ư.l.) với cách còn lại.",
    ])

    # ---------------------------------------------------------------- 5
    doc.add_heading("5. Giai đoạn 3: RTL (thiết kế Adaptive theo đề xuất)", level=1)
    doc.add_heading("5.1. Thiết kế theo từng mục", level=2)
    table(doc, ["Mục của đề xuất", "Thay đổi dự kiến", "Chi phí ước lượng"], [
        ["Tách SPARSITY_EN thành cấu hình Weight và Activation",
         "Tham số dựng WGHT_SPARSITY_EN / IACT_SPARSITY_EN; bit wght_sparse / iact_sparse cho mỗi layer. Weight: GET_WGHT "
         "(OpenEye_FPGA.v) nhận 5 word (12 bit) hoặc 3 word (8 bit, giãn thành ô 12 bit overhead 0); raw_wght_i = FC | GEMM | "
         "weight không nén. Activation: iact_stream_constructor / data_pipeline_iact mã hoá overhead lúc chạy",
         f"Weight: +{LUT_WSPLIT} LUT, 0 FF (Yosys); activation: nhỏ, chưa ước lượng"],
        ["Chọn dense / sparse lúc chạy", "PE chứa cả FSM sparse và FSM dense (hôm nay generate chỉ giữ một), chọn bằng bit "
         "của layer; mux trên đường địa chỉ SPad và psum", f"+100–200 LUT mỗi PE, khoảng +{fmt(LUT_DUAL_FSM[0])} đến "
         f"+{fmt(LUT_DUAL_FSM[1])} LUT (+8–16 %); rủi ro timing trên đường địa chỉ"],
        ["Scheduler", "Lịch chế độ của từng layer do toolchain tính (mô hình mục 4.5, số 0 đo trên ảnh hiệu chỉnh), ghi vào "
         "cấu hình layer trong DRAM; FSM chính nạp như các trường cấu hình khác. Phương án phần cứng (đếm số 0 trên chip trước "
         "mỗi layer) cần thêm một lượt đọc bộ đệm activation", "Toolchain: 0 LUT; phần cứng: bộ đếm + một lượt đọc mỗi layer"],
        ["Thanh ghi cấu hình layer", "Trường mới trong regmap (status word của layer), dùng chỗ trống sẵn có; nạp trong "
         "GET_PARAMETERS", "Gần 0 LUT; số word trạng thái không đổi"],
        ["Chuyển layer không sai psum / dữ liệu", "Hai chế độ hôm nay để lại bộ đệm psum và activation giống hệt nhau (mọi pha "
         "ngoài nạp weight và tính toán giống từng chu kỳ, kết quả khớp từng bit), nên chuyển chế độ giữa hai layer không đổi "
         "địa chỉ. Test mới: mạng có layer xen kẽ chế độ, kiểm bộ đệm sau mỗi layer", "Test"],
    ], widths=[3.6, 9.0, 4.0])
    para(doc, f"Tổng chi phí ước lượng của Adaptive đầy đủ: khoảng +{fmt(LUT_DUAL_FSM[0] + LUT_WSPLIT)} đến "
              f"+{fmt(LUT_DUAL_FSM[1] + LUT_WSPLIT)} LUT (+8–17 % so với {fmt(LUT_SPARSE)} LUT), BRAM không đổi. Phần đắt "
              "nhất là hai FSM trong mỗi PE.")

    doc.add_heading("5.2. Thử nghiệm đã làm: tách Weight / Activation (đề xuất P1), không sửa RTL", level=2)
    para(doc, "P1 là bước đầu của mục \"tách cấu hình Weight và Activation\": giữ FSM sparse (bỏ qua activation 0), cho từng "
              "layer chọn gửi weight 8 bit trần hay nén như hôm nay. Thử nghiệm kiểm tra trên RTL hiện tại xem PE có tính đúng "
              "khi weight không nén không, và nhân thêm weight 0 tốn bao nhiêu:")
    bullets(doc, [
        "Cách làm: toolchain gửi weight Conv theo layout mọi weight có ô (overhead 0); testbench giữ raw_wght_i = 1 trong mô "
        "phỏng (như RTL sẽ làm); không sửa dòng RTL nào. 140 lần chạy một layer (3 dạng Conv × 3 cấu hình × 2 tỉ lệ số 0 của "
        "input × 4 tỉ lệ weight 0 × 2 layout, kèm đối chứng) + mạng Bảng 2 32 lần + MNIST 4 hàm.",
        "Khớp từng bit ở 99/99 lần chạy dùng layout mới (kể cả hai weight 0 trong một word); không bật raw_wght_i thì layer "
        "treo (đối chứng). PE, router, bộ đệm, địa chỉ psum không cần sửa: chỉ cần phần nạp weight (GET_WGHT) và một bit "
        "cấu hình.",
        "Chi phí nhân weight 0: tính toán tăng 0–0,5 % ở 5 % weight 0, tối đa 8,4 % ở 25 %, 22,5 % ở 50 %; trên MNIST đã "
        "huấn luyện 0–26 chu kỳ cả mạng. Layout nén chỉ còn tốt hơn khi weight đã prune (trên 5–50 % weight 0 tuỳ cấu hình).",
    ])
    rows = []
    for a, lab in ACTS:
        c = (a, DEFAULT_ROUND[a])
        w8 = sum(mn[c]["w8"])
        rows.append([f"MNIST {lab}", fmt(tot[c]["s"]), fmt(tot[c]["d"]), fmt(w8), pct(rel(w8, tot[c]["s"])),
                     pct(rel(w8, tot[c]["d"]))])
    table(doc, ["Thử nghiệm (cả mạng)", "Sparse", "Dense", "Weight 8 bit + activation sparse (đo)", "so với sparse",
                "so với dense"], rows, widths=[3.4, 2.2, 2.2, 3.6, 2.4, 2.4], align_right=(1, 2, 3, 4, 5))
    para(doc, "Đây là số đo của tổ hợp \"Weight dense + Activation sparse\" trong thiết kế Adaptive. Nó cho thấy mục tách "
              "Weight / Activation làm được trước và riêng (rẻ, ít rủi ro), rồi đến mục chọn FSM lúc chạy.")
    doc.add_heading("5.3. Thứ tự thực hiện giai đoạn 3", level=2)
    table(doc, ["Bước", "Nội dung", "Đo sau bước"], [
        ["3a", "Tách cấu hình Weight: bit wght_sparse mỗi layer, GET_WGHT 3 / 5 word, raw_wght_i; toolchain chọn theo layer",
         "Chu kỳ 16 trường hợp + mạng Bảng 2, Vivado"],
        ["3b", "Tách cấu hình Activation + chọn FSM lúc chạy: hai FSM trong PE, bit iact_sparse, mã hoá overhead lúc chạy",
         "Chu kỳ, LUT, timing; so với 3a"],
        ["3c", "Thanh ghi cấu hình layer + Scheduler trong toolchain (mô hình mục 4.5)", "Lịch chọn so với lựa chọn đo được"],
        ["3d", "Test chuyển layer xen kẽ chế độ (psum, activation), hồi quy 225 test ở các bản dựng", "Khớp từng bit"],
    ], widths=[1.2, 10.4, 5.0])

    # ---------------------------------------------------------------- 6
    doc.add_heading("6. Giai đoạn 4: Verification và Benchmark (hiện trạng)", level=1)
    rows = []
    for k, name in LAYERS:
        ls, ld = relu["s"]["layers"][k], relu["d"]["layers"][k]
        rows.append([f"{name} ({layer_name(ls)})", us(ls["total_cycles"]), us(ld["total_cycles"]),
                     us(min(ls["total_cycles"], ld["total_cycles"])), fmt(ph(ls, "load_wght", "in_accepted")),
                     fmt(ph(ld, "load_wght", "in_accepted"))])
    rows.append(["Cả mạng (gồm pooling)", us(relu["s"]["total_cycles"]), us(relu["d"]["total_cycles"]), us(relu["layer"]),
                 fmt(ph(relu["s"], "load_wght", "in_accepted")), fmt(ph(relu["d"], "load_wght", "in_accepted"))])
    table(doc, ["Layer (MNIST ReLU floor)", "Latency sparse (µs)", "Latency dense (µs)", "Theo layer S/D (µs)",
                "Word DMA weight: sparse", "dense"], rows, widths=[4.6, 2.4, 2.4, 2.4, 2.6, 2.2], align_right=(1, 2, 3, 4, 5))
    rows = []
    for a, lab in ACTS:
        for rnd, rl in ROUNDS:
            c = (a, rnd)
            m = sum(macs(l) for l in mn[c]["s"]["layers"])
            g = [2.0 * m / (v * CLOCK_NS) * 1000 for v in (tot[c]["s"], tot[c]["d"], tot[c]["l"])]
            rows.append([f"{lab}, {rl}", fmt(int(round(g[0]))), fmt(int(round(g[1]))), fmt(int(round(g[2])))])
    table(doc, ["Trường hợp", "Sparse (MOPS)", "Dense (MOPS)", "Theo layer S/D (MOPS)"], rows, widths=[4.6, 3.6, 3.6, 4.0],
          align_right=(1, 2, 3))
    bullets(doc, [
        "MOPS hiệu dụng = 2 × số MAC của phép tính dense tương đương (5.676.160 MAC, kể cả phép nhân với 0) / thời gian cả "
        "mạng ở 250 MHz, gồm mọi pha nạp và ghi ngược.",
        "Đã có: so khớp từng bit với tham chiếu Python sau mọi layer ở mọi lần chạy; so với ONNX Runtime ở model thật (báo cáo "
        "10/11: ReLU làm tròn khớp 100 %); latency từng layer; số word DMA từng pha; Vivado mốc.",
        "Còn lại sau giai đoạn 3: chạy Adaptive trên cùng các trường hợp, so Dense / Sparse / Adaptive theo latency, chu kỳ "
        "nạp, MOPS và tài nguyên Vivado của từng bản dựng.",
    ])

    # ---------------------------------------------------------------- 7
    doc.add_heading("7. So sánh và đánh giá các hướng", level=1)
    mnist_def = [(a, DEFAULT_ROUND[a]) for a, _ in ACTS]
    p1_only = [rel(sum(min(ls["total_cycles"], w) for ls, w in zip(mn[c]["s"]["layers"], mn[c]["w8"])), tot[c]["s"])
               for c in mnist_def]
    mixed = [rel(sum(mn[c]["w8"]), tot[c]["s"]) for c in mnist_def]
    table(doc, ["Hướng", "Thay đổi", "Tài nguyên (LUT)", "Chu kỳ so với sparse hôm nay (MNIST, 4 hàm, làm tròn mặc định)",
                "Đánh giá"], [
        ["Chỉ sparse (hôm nay)", "—", fmt(LUT_SPARSE), "0", "Thua ở layer ít số 0, layer Dense và mạng không dùng ReLU"],
        ["Chỉ dense (bản dựng SPARSITY_EN = 0)", "Không (đã có)", f"khoảng {fmt(LUT_DENSE)} (−27 %)",
         rng([rel(tot[c]["d"], tot[c]["s"]) for c in mnist_def]), "Rẻ nhất; thua ở mạng ReLU, mất lợi khi model có nhiều số 0"],
        ["Adaptive theo đề xuất, đầy đủ (tách W / A + FSM lúc chạy + Scheduler)", "RTL lớn: PE, nạp weight, activation, "
         "regmap; toolchain", f"+{fmt(LUT_DUAL_FSM[0] + LUT_WSPLIT)} đến +{fmt(LUT_DUAL_FSM[1] + LUT_WSPLIT)} (+8–17 %)",
         rng([rel(tot[c]["f"], tot[c]["s"]) for c in mnist_def]),
         "Nhanh nhất ở mọi trường hợp; đắt nhất; là hướng sẽ thực hiện (giai đoạn 3, bước 3a → 3d)"],
        ["Adaptive chưa tách W / A (chọn FSM + định dạng hôm nay theo layer)", "PE (hai FSM), regmap",
         f"+{fmt(LUT_DUAL_FSM[0])} đến +{fmt(LUT_DUAL_FSM[1])}", rng([rel(tot[c]["l"], tot[c]["s"]) for c in mnist_def]),
         "Lợi nhỏ so với chế độ tốt hơn (mục 4.6) vì layer sparse vẫn nhận weight 12 bit"],
        ["Chỉ tách Weight (P1, bước 3a đứng riêng)", "GET_WGHT + một bit; PE không đổi", f"+{LUT_WSPLIT}", rng(p1_only),
         "Gần bằng Adaptive đầy đủ với chi phí nhỏ nhất; thiếu FSM dense cho layer không có số 0 (Conv1)"],
        ["Chế độ trộn cố định (mọi layer weight 8 bit + activation sparse, chọn lúc dựng)", "Thu hẹp đường weight trong PE",
         "ít hơn sparse (ước lượng)", rng(mixed), "Không chọn được theo layer; mất layout nén cho weight đã prune; đã hoãn"],
    ], widths=[3.6, 3.0, 2.6, 3.4, 4.0])
    bullets(doc, [
        "Hướng Adaptive đầy đủ cho chu kỳ thấp nhất trên mọi trường hợp đã đo và giữ được cả hai lựa chọn cho mọi loại layer "
        "(kể cả model lớn hoặc weight đã prune, nơi FSM dense và layout nén có lợi hơn), đổi lại tốn +8–17 % LUT, chủ yếu do "
        "hai FSM trong mỗi PE.",
        "Trên hai mạng đã đo, phần lớn lợi ích đến từ việc tách Weight / Activation; phần chọn FSM lúc chạy thêm ít (chủ yếu ở "
        "Conv1). Vì vậy giai đoạn 3 làm theo thứ tự 3a (tách Weight) → 3b (Activation + FSM lúc chạy) → 3c → 3d và đo sau mỗi "
        "bước: đi đủ hướng đề xuất, đồng thời biết mỗi mục đóng góp bao nhiêu so với chi phí của nó.",
        "Với chip mà LUT là giới hạn, bản dựng dense vẫn là lựa chọn rẻ nhất; Adaptive phù hợp khi ưu tiên độ trễ.",
    ])

    # ---------------------------------------------------------------- 8
    doc.add_heading("8. Những việc đã làm trong tuần (11/11 – 18/11/2026)", level=1)
    table(doc, ["Ngày", "Việc", "Giai đoạn", "Kết quả"], [
        ["11/11", "Đề xuất chế độ trộn (activation sparse + weight 8 bit cho mọi layer)", "—",
         "Ước lượng MNIST ReLU −4,5 đến −7 %; sau đó hoãn"],
        ["12/11", "Hàm kích hoạt × cách làm tròn × sparse / dense (16 trường hợp)", "1",
         "16/16 khớp từng bit; các trường hợp của báo cáo này"],
        ["12/11", "Sửa báo cáo lần 5; nghiên cứu bão hoà của hàm kích hoạt", "—",
         "Tối đa 0,0003 % output bị kẹp; độ chính xác như nhau"],
        ["17/11", "Phân tích chọn sparse / dense theo layer; đánh giá đề xuất Adaptive", "1, 2",
         "Khác biệt chủ yếu ở định dạng weight; cần đo trước khi sửa RTL"],
        ["17/11", "Rà soát upstream 3e2e027 (9 commit)", "—", "Không lấy: upstream sparse 0/13, dense 8/13 ca"],
        ["17/11", "Mạng Bảng 2 của bài báo ở sparse và dense", "1", "Dense 16/16; phát hiện lỗi #49"],
        ["17/11", "Gửi bias một lần mỗi filter, bật mặc định", "—", "MNIST −9,3 %, Bảng 3 −10 % chu kỳ; +434 LUT; 250 MHz"],
        ["17/11", "Điều tra và sửa lỗi #49; kiểm tra Conv trước pooling", "—", "Bảng 2 ReLU sparse 16/16 (trước 14/16)"],
        ["18/11", "Kiểm chứng trạng thái đã commit, mốc mới", "1",
         "Unit test 504 PASS; hồi quy 225 = 221 PASS + 4 xfail; Vivado 250 MHz, 60.113 LUT"],
        ["18/11", "Đo theo layer và pha, quét tỉ lệ số 0 (120 lần), mô hình chi phí, tài nguyên", "1, 2",
         f"Ngưỡng hoà vốn theo cấu hình; mô hình chọn đúng {right}/{total} layer"],
        ["18/11", "Thử nghiệm tách Weight / Activation trên RTL hiện tại", "3 (thử nghiệm)",
         "Khớp từng bit 99/99; PE không cần sửa; chi phí weight 0 nhỏ"],
        ["18/11", "Chạy lại 8 trường hợp làm tròn của báo cáo 10/11 trên RTL hiện tại; dataset theo layer", "1",
         f"16/16 khớp từng bit; {n_rows} dòng dữ liệu"],
    ], widths=[1.4, 6.6, 2.0, 6.6])
    para(doc, "Tình trạng cuối tuần: ", None)
    bullets(doc, [
        "Hồi quy RTL 225 test = 221 PASS + 4 xfail đã biết, 0 FAIL; unit test Python 578 PASS + 11 lỗi cũ đã biết.",
        "Bảng 3 của bài báo 16/16 ở sparse, dense và sparse có ReLU.",
        "Vivado (xczu7ev, 4 ns): đạt 250 MHz, WNS +0,096 ns, 60.113 LUT, 39.556 FF, 188 BRAM, 12 URAM, 4 DSP.",
    ])

    # ---------------------------------------------------------------- 9
    doc.add_heading("9. Các bước tiếp theo", level=1)
    table(doc, ["Bước", "Giai đoạn", "Nội dung", "Loại"], [
        ["1", "2", "Đưa mô hình chi phí vào toolchain: onnx2model đo số 0 trên ảnh hiệu chỉnh, tính lịch chế độ cho từng "
         "layer; profiler ghi chế độ đã chọn", "Python"],
        ["2", "3 (3a)", "Tách cấu hình Weight trong RTL (GET_WGHT, bit cấu hình layer, raw_wght_i), toolchain chọn theo layer",
         "RTL + Python, cần duyệt"],
        ["3", "3 (3b–3d)", "Tách cấu hình Activation, hai FSM trong PE chọn lúc chạy, thanh ghi cấu hình layer, test chuyển "
         "layer xen kẽ chế độ", "RTL + Python, cần duyệt"],
        ["4", "4", "Benchmark Dense / Sparse / Adaptive trên 16 trường hợp MNIST và mạng Bảng 2: latency từng layer, chu kỳ "
         "nạp, MOPS, so với ONNX Runtime, Vivado mỗi bản dựng", "Chạy"],
        ["5", "1 + 4", "Thêm một model thật lớn hơn (nhiều layer, input RGB hoặc weight đã prune) để kiểm lại ngưỡng và lợi "
         "ích của Adaptive", "Python + chạy"],
    ], widths=[1.2, 2.0, 10.2, 3.2])
    para(doc, "Rủi ro cần theo dõi: timing của mux địa chỉ khi PE có hai FSM; thời gian của GET_WGHT khi ghi hàng ở word thứ "
              "3; số filter lẻ mỗi PE (#48) giữ layout nén; kết luận hiện dựa trên 2 mạng.")

    doc.save(OUT)
    print("wrote", OUT, f"({n_rows} dataset rows, cost model {right}/{total})")


if __name__ == "__main__":
    build()
