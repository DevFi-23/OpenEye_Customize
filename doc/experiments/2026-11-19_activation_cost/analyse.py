"""analyse.py <dir with trained_<act>_img<N>_<mode>.json> [more dirs]: cost of the activation function from the profiles of the
trained MNIST model (4 functions). Per phase and per layer, difference against ReLU on the same hardware mode, split into
the direct cost (load_act + writeback + activation clocks) and the indirect cost (compute of the next layer, from lost zeros)."""
import glob
import json
import os
import re
import sys

ACTS = ["relu", "leaky_relu", "silu", "hardswish"]
NAMES = {"relu": "ReLU", "leaky_relu": "Leaky ReLU", "silu": "SiLU", "hardswish": "hard-swish"}
PHASES = ["load_config", "load_iact", "load_wght", "load_bias", "load_quant", "load_act", "convert_iact", "compute",
          "writeback", "pooling", "readout"]
SHORT = ["Conv1", "Pool1", "Conv2", "Pool2", "Conv3", "Dense"]


def load(path):
    d = json.load(open(path))
    layers = d["layers"]
    ph = [{p: l["phases"].get(p, {}).get("cycles", 0) for p in PHASES} for l in layers]
    return d["total_cycles"], ph, layers


def table(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def f(n):
    return f"{n:,}".replace(",", ".")


def sf(n):
    return ("+" if n > 0 else "") + f(n) if n else "0"


def report(directory, image, mode, out):
    data = {}
    for a in ACTS:
        p = os.path.join(directory, f"trained_{a}_img{image}_{mode}.json")
        if os.path.exists(p):
            data[a] = load(p)
    if "relu" not in data:
        return
    out.append(f"\n### Ảnh {image}, phần cứng {mode}\n")
    # end to end
    base = data["relu"][0]
    rows = []
    for a in ACTS:
        if a not in data:
            continue
        tot, ph, _ = data[a]
        per = {p: sum(l[p] for l in ph) for p in PHASES}
        rel = {p: per[p] - sum(l[p] for l in data["relu"][1]) for p in PHASES}
        direct = rel["load_act"] + rel["writeback"]
        rows.append([NAMES[a], f(tot), f"{tot / 250:.1f}", sf(tot - base), f"{(tot - base) / base * 100:+.2f} %",
                     sf(rel["load_act"]), sf(rel["writeback"]), sf(rel["compute"]),
                     sf(tot - base - direct - rel["compute"])])
    out.append(table(rows, ["hàm", "tổng chu kỳ", "µs @250 MHz", "so với ReLU", "%", "Δ load_act", "Δ writeback", "Δ compute",
                            "Δ pha khác"]))
    # per phase absolute
    out.append("\nSố chu kỳ từng pha (cả mạng):\n")
    rows = []
    for p in PHASES:
        rows.append([p] + [f(sum(l[p] for l in data[a][1])) for a in ACTS if a in data])
    rows.append(["**tổng**"] + [f(data[a][0]) for a in ACTS if a in data])
    out.append(table(rows, ["pha"] + [NAMES[a] for a in ACTS if a in data]))
    # per layer total and compute
    out.append("\nTổng chu kỳ và `compute` từng layer (Δ so với ReLU):\n")
    rows = []
    for i, s in enumerate(SHORT):
        r = [s]
        for a in ACTS:
            if a not in data:
                continue
            ph = data[a][1][i]
            tot = data[a][2][i]["total_cycles"]
            if a == "relu":
                r.append(f"{f(tot)} (compute {f(ph['compute'])})")
            else:
                bp = data["relu"][1][i]
                bt = data["relu"][2][i]["total_cycles"]
                r.append(f"{sf(tot - bt)} (compute {sf(ph['compute'] - bp['compute'])})")
        rows.append(r)
    out.append(table(rows, ["layer"] + [NAMES[a] for a in ACTS if a in data]))
    # activation table of the layers
    out.append("\nHàm kích hoạt chạy ở layer nào, số 0 ở input từng layer, chu kỳ khối kích hoạt (nằm trong writeback):\n")
    rows = []
    for i, s in enumerate(SHORT):
        r = [s]
        for a in ACTS:
            if a not in data:
                continue
            l = data[a][2][i]
            inp = l["info"].get("input", {})
            z = inp.get("zeros", 0) / inp["values"] * 100 if inp.get("values") else 0
            act = l["info"].get("activation", {}).get("mode", "none") if l["info"].get("activation") else "none"
            r.append(f"{act}; input 0 = {z:.1f} %; act {f(l.get('activation_cycles', 0))}/wb {f(l['phases'].get('writeback', {}).get('cycles', 0))}")
        rows.append(r)
    out.append(table(rows, ["layer"] + [NAMES[a] for a in ACTS if a in data]))


def main():
    out = []
    for d in sys.argv[1:]:
        imgs = sorted({int(m.group(1)) for p in glob.glob(os.path.join(d, "trained_*_img*_*.json"))
                       for m in [re.search(r"_img(\d+)_", p)] if m})
        for im in imgs:
            for mode in ("sparse", "dense"):
                report(d, im, mode, out)
    print("\n".join(out))


main()
