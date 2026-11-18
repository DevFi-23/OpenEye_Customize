"""plot_step2.py STEP2_DIR OUT.png: compute cost of zero weights on the sparse PE. One panel per layer shape of the Table 2
network; x the weight zero share, y the compute increase of the dense weight layout over today's zero-compressed one
(same data, input without zeros); one line per cluster configuration, and in gray the proportional bound that step 1
assumed (compute grows by the weight zero share). Colors: the first three categorical slots of the reference palette,
in order; line style and marker differ too."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SHAPES = [("conv1", "Conv 28x28x1 -> 16"), ("conv2", "Conv 14x14x16 -> 32"), ("conv3", "Conv 7x7x32 -> 32")]
CONFIGS = [("cr1x2", "CR 1, X 2", "#2a78d6", "-", "o"), ("cr2x4", "CR 2, X 4", "#eb6834", "--", "s"),
           ("cr8x4", "CR 8, X 4", "#1baf7a", ":", "^")]
WGHT_ZEROS = ["0", "0.05", "0.25", "0.5"]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def compute(path):
    d = json.load(open(path)) if os.path.exists(path) else None
    return d["phases"].get("compute", {}).get("cycles", 0) if d else None


def main():
    sdir, out = sys.argv[1:3]
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                         "ytick.color": MUTED, "text.color": INK})
    fig, axes = plt.subplots(1, len(SHAPES), figsize=(12, 4.2), sharey=True, facecolor=SURFACE)
    for ax, (shape, title) in zip(axes, SHAPES):
        ax.set_facecolor(SURFACE)
        ax.plot([0, 50], [0, 50], color=MUTED, linewidth=1, linestyle=(0, (4, 3)),
                label="step 1 bound (proportional)")
        for config, ctitle, color, style, marker in CONFIGS:
            xs, ys = [], []
            for w in WGHT_ZEROS:
                csc = compute(os.path.join(sdir, f"{shape}_i0_w{w}_csc_{config}.json"))
                dense = compute(os.path.join(sdir, f"{shape}_i0_w{w}_dense_{config}.json")) if w != "0" else csc
                if csc and dense:
                    xs.append(float(w) * 100)
                    ys.append(100.0 * (dense - csc) / csc)
            ax.plot(xs, ys, color=color, linestyle=style, linewidth=2, marker=marker, markersize=6, label=ctitle)
        ax.set_title(title, fontsize=9, color=INK)
        ax.set_xlabel("zero weights (%)")
        ax.set_xlim(-2, 52)
        ax.set_ylim(-3, 52)
        ax.grid(True, color=GRID, linewidth=0.6)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0].set_ylabel("compute increase, dense layout vs zero-compressed (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle("Cost of multiplying zero weights on the sparse PE (input without zeros; one layer of the Table 2 network)",
                 y=1.08, fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print("wrote", out)


if __name__ == "__main__":
    main()
