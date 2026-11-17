"""compare.py <sparse_dir> <dense_dir> [label]: the Table 2 network of the OpenEye paper on the 16 configurations of
Table 3, sparse against dense hardware, from two directories of saved profiles (tools/paper_table3.py --save layout).
Prints markdown: per configuration the whole-network time of both modes, the difference, the paper's total, and the
phases that differ; then per layer the cycles of both modes summed over the 16 configurations. Times in ns at 200 MHz
(cycles x 5), the clock of the paper. Run from the repository root:
  venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/compare.py doc/perf/paper_table3_2026-11-04 doc/perf/paper_table3_2026-11-17_dense"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "tools"))
import paper_table3 as t3  # noqa: E402

NS = 5.0
PHASES = ["load_iact", "load_wght", "load_bias", "convert_iact", "compute", "writeback", "pooling", "readout"]


def fmt(v):
    return f"{v:,.0f}".replace(",", ".")


def pct(new, old):
    return f"{100.0 * (new - old) / old:+.1f} %".replace(".", ",") if old else ""


def ratio(a, b):
    return f"{a / b:.2f}".replace(".", ",")


def main():
    sdir, ddir = sys.argv[1], sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else ""
    sparse, dense = t3.load_dir(sdir), t3.load_dir(ddir)
    configs = [c for c in t3.ordered(sparse) if c in dense]
    print(f"## {label or 'Table 2 network'}: sparse ({os.path.relpath(sdir, REPO)}) against dense ({os.path.relpath(ddir, REPO)})\n")
    print("ns at 200 MHz. Phase columns: dense minus sparse, ns.\n")
    print("| CR | X | Y | status sparse / dense | sparse | dense | dense − sparse | paper Total | sparse / paper | dense / paper | "
          + " | ".join(PHASES) + " |")
    print("|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|" + "---:|" * len(PHASES))
    tot_s = tot_d = 0
    for cfg in configs:
        (_, ps, ss), (_, pd, sd) = sparse[cfg], dense[cfg]
        ts, td = ps["total_cycles"] * NS, pd["total_cycles"] * NS
        tot_s, tot_d = tot_s + ts, tot_d + td
        paper = t3.PAPER[cfg][2]
        diffs = []
        for p in PHASES:
            a = ps["phases"].get(p, {}).get("cycles", 0)
            b = pd["phases"].get(p, {}).get("cycles", 0)
            diffs.append(fmt((b - a) * NS) if a or b else "")
        print(f"| {cfg[0]} | {cfg[1]} | {cfg[2]} | {ss} / {sd} | {fmt(ts)} | {fmt(td)} | {pct(td, ts)} | {fmt(paper)} | "
              f"{ratio(ts, paper)} | {ratio(td, paper)} | " + " | ".join(diffs) + " |")
    print(f"| | | | sum | {fmt(tot_s)} | {fmt(tot_d)} | {pct(tot_d, tot_s)} | | | | " + " | " * (len(PHASES) - 1) + " |")

    print("\n### Per layer, summed over the configurations (cycles)\n")
    n = max(len(sparse[c][1]["layers"]) for c in configs)
    print("| # | layer | input zeros (sparse run) | sparse | dense | dense − sparse | load_wght s / d | compute s / d |")
    print("|---:|---|---:|---:|---:|---:|---:|---:|")
    for i in range(n):
        s = d = ws = wd = cs = cd = 0
        zeros = values = 0
        name = ""
        for cfg in configs:
            ls, ld = sparse[cfg][1]["layers"][i], dense[cfg][1]["layers"][i]
            info = ls.get("info") or {}
            name = f"{info.get('name')} {info.get('iact_size_x')}x{info.get('iact_size_y')}x{info.get('channels')}"
            if info.get("name") != "Pooling":
                name += f" -> {info.get('filters')}"
            inp = info.get("input") or {}
            zeros, values = zeros + (inp.get("zeros") or 0), values + (inp.get("values") or 0)
            s, d = s + ls["total_cycles"], d + ld["total_cycles"]
            ws += ls["phases"].get("load_wght", {}).get("cycles", 0)
            wd += ld["phases"].get("load_wght", {}).get("cycles", 0)
            cs += ls["phases"].get("compute", {}).get("cycles", 0)
            cd += ld["phases"].get("compute", {}).get("cycles", 0)
        z = f"{100.0 * zeros / values:.1f} %".replace(".", ",") if values else ""
        print(f"| {i} | {name} | {z} | {fmt(s)} | {fmt(d)} | {pct(d, s)} | {fmt(ws)} / {fmt(wd)} | {fmt(cs)} / {fmt(cd)} |")


if __name__ == "__main__":
    main()
