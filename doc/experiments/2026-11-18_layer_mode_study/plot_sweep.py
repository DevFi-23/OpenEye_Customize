"""plot_sweep.py SPARSE_DIR DENSE_DIR OUT.png: the zero-share sweep as small multiples (rows: cluster configurations,
columns: layer shapes), each panel the whole-layer cycles of sparse hardware, dense hardware and the P1 estimate
(sparse minus the load_wght difference) against the zero share of the layer input, as a share of the dense cycles
(dense = 1). Colors: the first three categorical slots of the reference palette, in order; line style and marker
differ too, so the series do not depend on color alone."""
import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SHAPES = [("conv1", "Conv 28x28x1 -> 16"), ("conv2", "Conv 14x14x16 -> 32"), ("conv3", "Conv 7x7x32 -> 32"),
          ("fc", "Dense 1568 -> 32")]
CONFIGS = [("cr1x2", "CR 1, X 2"), ("cr2x4", "CR 2, X 4"), ("cr8x4", "CR 8, X 4")]
SERIES = [("sparse", "#2a78d6", "-", "o"), ("dense", "#eb6834", "--", "s"), ("P1 (est.)", "#1baf7a", ":", "^")]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def ph(layer, name):
    return layer["phases"].get(name, {}).get("cycles", 0)


def main():
    sdir, ddir, out = sys.argv[1:4]
    data = {}
    for f in glob.glob(os.path.join(sdir, "*_z*_*.json")):
        case = os.path.basename(f)[:-5]
        g = os.path.join(ddir, case + ".json")
        if os.path.exists(g):
            data[case] = (json.load(open(f)), json.load(open(g)))
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                         "ytick.color": MUTED, "text.color": INK})
    fig, axes = plt.subplots(len(CONFIGS), len(SHAPES), figsize=(12, 7.2), sharex=True, facecolor=SURFACE)
    for r, (config, ctitle) in enumerate(CONFIGS):
        for c, (shape, stitle) in enumerate(SHAPES):
            ax = axes[r][c]
            ax.set_facecolor(SURFACE)
            pts = []
            for case, (s, d) in data.items():
                sh, rest = case.split("_z", 1)
                z, cf = rest.split("_", 1)
                if sh == shape and cf == config:
                    ls, ld = s["layers"][0], d["layers"][0]
                    ts, td = s["total_cycles"], d["total_cycles"]
                    p1 = ts - (ph(ls, "load_wght") - ph(ld, "load_wght"))
                    pts.append((float(z) * 100, ts / td, 1.0, p1 / td))
            pts.sort()
            if pts:
                xs = [p[0] for p in pts]
                for i, (name, color, style, marker) in enumerate(SERIES):
                    ax.plot(xs, [p[i + 1] for p in pts], color=color, linestyle=style, linewidth=2, marker=marker,
                            markersize=5, label=name)
            ax.grid(True, color=GRID, linewidth=0.6)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            if r == 0:
                ax.set_title(stitle, fontsize=9, color=INK)
            if c == 0:
                ax.set_ylabel(f"{ctitle}\ncycles / dense", color=INK)
            if r == len(CONFIGS) - 1:
                ax.set_xlabel("zeros in the layer input (%)")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("One layer of the Table 2 network: cycles of the whole layer relative to dense hardware "
                 "(each panel has its own y scale)", y=1.03, fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print("wrote", out)


if __name__ == "__main__":
    main()
