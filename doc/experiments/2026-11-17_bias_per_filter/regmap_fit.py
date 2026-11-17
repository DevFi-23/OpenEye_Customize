"""regmap_fit.py: where the bias-per-filter fields can go in test/cocotb_fpga/regmap.yaml without changing the number
of status words. For every configuration (DMA 32 / 64 / 128, CLUSTER_ROWS 1-8, CLUSTER_COLUMNS 1-4, BRANCHES 1-2) it
packs the register list as generator.layout_registers does (sequential, a field never straddles two words) and prints
the word count; with candidate insert positions for the new fields it reports the positions that keep every count.
Run from the repository root: venv/bin/python doc/experiments/2026-11-17_bias_per_filter/regmap_fit.py"""
import copy
import itertools
import os
import sys

import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "src"))
from open_eye import generator  # noqa: E402
from open_eye import open_eye_parameters as oep_mod  # noqa: E402

NEW = [("bias_groups", "11"), ("bias_per_filter", "1")]
CONFIGS = [(dma, cr, cc, br) for dma in (32, 64, 128) for cr in (1, 2, 4, 8) for cc in (1, 2, 3, 4) for br in (1, 2)]


def widths(registers, env):
    os.environ.update(env)
    p = oep_mod.get_oep(serial=False)
    ctx = {k: v for k, v in vars(p).items() if isinstance(v, int) and not isinstance(v, bool)}
    ctx["CLUSTER_ROWS"], ctx["CLUSTER_COLUMNS"] = p.Clusters_Y, p.Clusters_X
    ctx = generator.context | ctx | dict(os.environ)
    return [(r["name"], int(generator.eval_width(r["width"], ctx))) for r in registers]


def count(ws, dma):
    words, pos = 1, 0
    for _, w in ws:
        if pos + w > dma:
            words, pos = words + 1, 0
        pos += w
    return words


def main():
    base = yaml.safe_load(open(os.path.join(REPO, "test", "cocotb_fpga", "regmap.yaml")))["registers"]
    table = {}
    for dma, cr, cc, br in CONFIGS:
        env = {"DMA_BITWIDTH": str(dma), "CLUSTER_ROWS": str(cr), "CLUSTER_COLUMNS": str(cc), "BRANCHES": str(br)}
        table[(dma, cr, cc, br)] = (widths(base, env), dma)
    ref = {k: count(ws, dma) for k, (ws, dma) in table.items()}
    print("word counts today:", sorted(set((k[0], v) for k, v in ref.items())))
    # place each new field (in order) at some index; greedy: for each field, list indices that keep every count
    placed = []
    for name, width in NEW:
        good = []
        for idx in range(len(base) + 1):
            ok = True
            for k, (ws, dma) in table.items():
                trial = list(ws)
                for (n2, w2, i2) in placed:
                    trial.insert(i2, (n2, int(w2)))
                trial.insert(idx, (name, int(width)))
                if count(trial, dma) != ref[k]:
                    ok = False
                    break
            if ok:
                good.append(idx)
        names = [base[i]["name"] if i < len(base) else "<end>" for i in good]
        print(f"{name} ({width} bits): fits before {list(zip(good, names))[:12]}")
        if not good:
            return
        placed.append((name, width, good[-1]))
        print(f"  chosen: before index {good[-1]} ({names[-1]})")


if __name__ == "__main__":
    main()
