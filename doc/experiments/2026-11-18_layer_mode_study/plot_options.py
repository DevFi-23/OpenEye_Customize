"""plot_options.py MNIST_DIR T3_SPARSE T3_DENSE T3_RELU OUT.png LUT_SPARSE LUT_DENSE LUT_P1 LUT_P2

Whole-network options against today's sparse hardware, one bar group per run (trained MNIST, 4 activations; the Table 2
network at CR1 X2, CR2 X4, CR8 X4 (Y3), with ReLU and without activation):
  left   change in total cycles (%)
  right  change in cycles x LUT (%), the area-normalised cost (lower is better), with the given LUT counts
Options: dense hardware; best FSM per layer (P2); per-layer weight format (P1, estimate); P1 + P2 (estimate).
Colors: the first four categorical slots of the reference palette, in order; each series also has its own hatch."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SERIES = [("dense hardware", "#2a78d6", ""), ("FSM per layer (P2)", "#eb6834", "//"),
          ("weight format per layer (P1, est.)", "#1baf7a", ".."), ("P1 + P2 (est.)", "#eda100", "xx")]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def ph(layer, name):
    return layer["phases"].get(name, {}).get("cycles", 0)


def options(sparse, dense):
    ts, td = sparse["total_cycles"], dense["total_cycles"]
    p2 = p1 = p12 = 0
    for ls, ld in zip(sparse["layers"], dense["layers"]):
        s, d = ls["total_cycles"], ld["total_cycles"]
        q = min(s, s - (ph(ls, "load_wght") - ph(ld, "load_wght")))
        p2 += min(s, d)
        p1 += q
        p12 += min(q, d)
    return ts, [td, p2, p1, p12]


def main():
    mdir, sdir, ddir, rdir, out = sys.argv[1:6]
    lut_s, lut_d, lut_p1, lut_p2 = (float(v) for v in sys.argv[6:10])
    luts = [lut_d, lut_p2, lut_p1, lut_p1 + lut_p2 - lut_s]
    runs = []
    for act, title in (("relu", "MNIST ReLU"), ("leaky_relu", "MNIST Leaky ReLU"), ("silu", "MNIST SiLU"),
                       ("hardswish", "MNIST hard-swish")):
        runs.append((title, json.load(open(os.path.join(mdir, f"trained_{act}_img0_sparse.json"))),
                     json.load(open(os.path.join(mdir, f"trained_{act}_img0_dense.json")))))
    for name, title in (("cr1_x2_y3", "CR1 X2"), ("cr2_x4_y3", "CR2 X4"), ("cr8_x4_y3", "CR8 X4")):
        dense = json.load(open(os.path.join(ddir, f"paper_{name}.json")))
        runs.append((f"Table 2 {title} ReLU", json.load(open(os.path.join(rdir, f"paper_{name}.json"))), dense))
    for name, title in (("cr1_x2_y3", "CR1 X2"), ("cr2_x4_y3", "CR2 X4"), ("cr8_x4_y3", "CR8 X4")):
        runs.append((f"Table 2 {title} no act.", json.load(open(os.path.join(sdir, f"paper_{name}.json"))),
                     json.load(open(os.path.join(ddir, f"paper_{name}.json")))))
    rows = []
    for title, s, d in runs:
        ts, vals = options(s, d)
        rows.append((title, [100.0 * (v - ts) / ts for v in vals],
                     [100.0 * (v * l - ts * lut_s) / (ts * lut_s) for v, l in zip(vals, luts)]))
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                         "ytick.color": INK, "text.color": INK, "hatch.color": SURFACE, "hatch.linewidth": 0.8})
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.4), sharey=True, facecolor=SURFACE)
    n = len(SERIES)
    height = 0.8 / n
    for ax, idx, xlabel in ((axes[0], 1, "change in total cycles vs today's sparse hardware (%)"),
                            (axes[1], 2, "change in cycles x LUT vs today's sparse hardware (%)")):
        ax.set_facecolor(SURFACE)
        for k, (name, color, hatch) in enumerate(SERIES):
            ys = [i + (k - (n - 1) / 2) * height for i in range(len(rows))]
            ax.barh(ys, [r[idx][k] for r in rows], height=height * 0.85, color=color, hatch=hatch,
                    edgecolor=SURFACE, linewidth=0.6, label=name)
        ax.axvline(0, color=INK, linewidth=0.8)
        ax.grid(True, axis="x", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.set_xlabel(xlabel)
        for i in range(1, len(rows)):
            if rows[i][0].split()[0:2] != rows[i - 1][0].split()[0:2] or ("ReLU" in rows[i - 1][0]) != ("ReLU" in rows[i][0]):
                ax.axhline(i - 0.5, color=GRID, linewidth=1.0)
    axes[0].set_yticks(range(len(rows)))
    axes[0].set_yticklabels([r[0] for r in rows])
    axes[0].invert_yaxis()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("Per-layer mode options against today's sparse hardware (negative = better)", y=1.04, fontsize=10)
    fig.text(0.5, -0.02, f"LUT: sparse {lut_s:,.0f}, dense {lut_d:,.0f}, P1 {lut_p1:,.0f}, P2 {lut_p2:,.0f} "
             f"(P1 and P2 estimates; P1 + P2 = both additions)", ha="center", color=MUTED, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print("wrote", out)
    for title, cyc, area in rows:
        print(f"{title:28s} cycles " + " ".join(f"{v:+6.1f}" for v in cyc) + "   cycles x LUT "
              + " ".join(f"{v:+6.1f}" for v in area))


if __name__ == "__main__":
    main()
