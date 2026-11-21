"""plot.py <act_wzero dir> [<grid dir>] <out dir>: figures of doc/experiments/2026-11-20_act_wzero.
  phases_wzero.png   whole networks, cycles split into weight load / compute / other per weight zero share, sparse (S)
                     and dense (D) side by side (trained MNIST, Table 2 network)
  act_delta.png      Table 2 network, change of the total cycles against no activation, split into the direct cost
                     (table load) and the change of compute (the zeros the function leaves), sparse and dense
  grid_ratio.png     (with the grid dir) one layer: total cycles sparse / dense over weight zeros x input zeros
Colors: the reference categorical slots, in order; neutral gray for 'other'; a diverging blue / orange map around 100 %."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

SURFACE, INK, INK_2, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e8e7e2", "#d6d5cf"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
OTHER = "#9b9a95"
ZEROS = ["0", "0.2", "0.4", "0.6", "0.8"]


def fmt(n):
    return f"{int(round(n)):,}".replace(",", ".").replace("-", "−")


def ph(x, name):
    return x["phases"].get(name, {}).get("cycles", 0)


def load(d, case):
    p = os.path.join(d, case + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def new_figure(w, h, rows=1, cols=1):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, axes = plt.subplots(rows, cols, figsize=(w, h), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    return fig, axes


def style(ax, grid_axis="y"):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=INK_2, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    getattr(ax, grid_axis + "axis").grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def phases_wzero(d, out):
    groups = [("load_wght", "nạp weight", SLOTS[0]), ("compute", "tính toán", SLOTS[1]), (None, "các pha khác", OTHER)]
    fig, axes = new_figure(10.5, 4.2, 1, 2)
    for ax, (model, title) in zip(axes, [("mnist", "MNIST đã huấn luyện (ReLU)"), ("t2", "Mạng Bảng 2 (không hàm)")]):
        style(ax)
        top = 0
        ticks, labels = [], []
        for j, z in enumerate(ZEROS):
            for m, (mode, tag) in enumerate((("sparse", "S"), ("dense", "D"))):
                r = load(d, f"wz_{model}_z{z}_{mode}")
                x = j * 3 + m
                bottom = 0
                for key, _, color in groups:
                    v = ph(r, key) if key else r["total_cycles"] - ph(r, "load_wght") - ph(r, "compute")
                    ax.bar(x, v, bottom=bottom, width=0.86, color=color, edgecolor=SURFACE, linewidth=1.2)
                    bottom += v
                top = max(top, bottom)
                ax.text(x, bottom * 1.01, f"{bottom / 1000:.0f}k".replace(".", ","), ha="center", va="bottom",
                        fontsize=6.4, color=INK)
                ticks.append(x)
                labels.append(tag)
            ax.text(j * 3 + 0.5, -0.1, f"{float(z) * 100:.0f} %", transform=ax.get_xaxis_transform(), ha="center",
                    va="top", fontsize=8.5, color=INK)
        ax.set_ylim(0, top * 1.1)
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontsize=7, color=INK_2)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt(v)))
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel("tỉ lệ weight bằng 0", fontsize=8, color=INK_2, labelpad=26)
    axes[0].set_ylabel("chu kỳ cả mạng", fontsize=8, color=INK_2)
    fig.legend(handles=[Patch(facecolor=c, label=lab) for _, lab, c in groups], loc="upper center", ncol=3,
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.0))
    fig.text(0.5, 0.005, "S = sparse, D = dense. CR 2 X 4 Y 3 (48 PE).", ha="center", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    fig.savefig(os.path.join(out, "phases_wzero.png"), facecolor=fig.get_facecolor())
    plt.close(fig)


def act_delta(d, out):
    acts = [("relu", "ReLU"), ("leaky", "Leaky ReLU"), ("silu", "SiLU"), ("hardswish", "hard-swish")]
    fig, axes = new_figure(10.5, 3.6, 1, 2)
    lo, hi = 0, 0
    for ax, (mode, title) in zip(axes, [("sparse", "Phần cứng sparse"), ("dense", "Phần cứng dense")]):
        style(ax, "y")
        base = load(d, f"act_none_{mode}")
        for i, (a, lab) in enumerate(acts):
            r = load(d, f"act_{a}_{mode}")
            direct = ph(r, "load_act") - ph(base, "load_act") + ph(r, "writeback") - ph(base, "writeback")
            comp = ph(r, "compute") - ph(base, "compute")
            ax.bar(i - 0.2, direct, width=0.38, color=SLOTS[0], edgecolor=SURFACE, linewidth=1.0,
                   label="trực tiếp: nạp bảng + ghi ngược" if i == 0 else None)
            ax.bar(i + 0.2, comp, width=0.38, color=SLOTS[1], edgecolor=SURFACE, linewidth=1.0,
                   label="gián tiếp: tính toán (do số 0)" if i == 0 else None)
            for x, v in ((i - 0.2, direct), (i + 0.2, comp)):
                ax.text(x, v + (40 if v >= 0 else -40), ("+" if v > 0 else "") + fmt(v), ha="center",
                        va="bottom" if v >= 0 else "top", fontsize=7, color=INK)
            lo, hi = min(lo, direct, comp), max(hi, direct, comp)
        ax.axhline(0, color=AXIS, linewidth=1)
        ax.set_xticks(range(len(acts)))
        ax.set_xticklabels([lab for _, lab in acts], fontsize=8.5, color=INK)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
    for ax in axes:
        ax.set_ylim(lo - 600, hi + 600)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: fmt(v)))
    axes[0].set_ylabel("Δ chu kỳ so với không hàm kích hoạt", fontsize=8, color=INK_2)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.0))
    fig.text(0.5, 0.005, "Mạng Bảng 2, CR 2 X 4 Y 3. Âm: ít chu kỳ hơn so với khi không có hàm kích hoạt.", ha="center",
             fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.9))
    fig.savefig(os.path.join(out, "act_delta.png"), facecolor=fig.get_facecolor())
    plt.close(fig)


def grid_ratio(g, out):
    shapes = [("conv1", "Conv 28×28×1→16 (ảnh)"), ("conv2", "Conv 14×14×16→32"), ("conv3", "Conv 7×7×32→32"),
              ("fc", "Dense 1568→32")]
    vals = {}
    for s, _ in shapes:
        for w in ZEROS:
            for a in ZEROS:
                sp, dn = load(g, f"grid_{s}_w{w}_a{a}_sparse"), load(g, f"grid_{s}_w{w}_a{a}_dense")
                vals[(s, w, a)] = 100.0 * sp["total_cycles"] / dn["total_cycles"] if sp and dn else None
    present = [v for v in vals.values() if v is not None]
    lo, hi = min(present + [99.0]), max(present + [101.0])
    cmap = LinearSegmentedColormap.from_list("div", [SLOTS[0], "#efeee9", SLOTS[1]])
    norm = TwoSlopeNorm(vmin=lo, vcenter=100.0, vmax=hi)
    fig, axes = new_figure(11.5, 3.5, 1, 4)
    for ax, (s, title) in zip(axes, shapes):
        ax.set_facecolor(SURFACE)
        for i, w in enumerate(ZEROS):
            for j, a in enumerate(ZEROS):
                v = vals[(s, w, a)]
                color = cmap(norm(v)) if v is not None else "#ffffff"
                ax.add_patch(plt.Rectangle((j, i), 0.96, 0.96, facecolor=color, edgecolor=SURFACE, linewidth=0))
                if v is not None:
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
    fig.text(0.5, 0.01, "Số trong ô: chu kỳ sparse / dense của cả layer (%). Xanh (< 100): sparse nhanh hơn; cam (> 100): "
             "dense nhanh hơn. CR 2 X 4 Y 3.", ha="center", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(os.path.join(out, "grid_ratio.png"), facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    d, out = sys.argv[1], sys.argv[-1]
    phases_wzero(d, out)
    act_delta(d, out)
    if len(sys.argv) > 3:
        grid_ratio(sys.argv[2], out)
    print("wrote figures to", out)


if __name__ == "__main__":
    main()
