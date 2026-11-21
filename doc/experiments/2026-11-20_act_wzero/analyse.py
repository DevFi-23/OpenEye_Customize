"""analyse.py <profile dir> [--grid <grid dir>] [out.md]: tables of doc/experiments/2026-11-20_act_wzero from the
profiles of run.py. Part A: cycles of the activation function per layer (Table 2 network, 5 settings, sparse and
dense). Part B: weight load and compute against the weight zero share (trained MNIST and Table 2 network, sparse and
dense). Part C (--grid): one layer at 5 x 5 weight / input zero shares, sparse and dense."""
import json
import os
import sys

ACTS = [("none", "không hàm"), ("relu", "ReLU"), ("leaky", "Leaky ReLU"), ("silu", "SiLU"), ("hardswish", "hard-swish")]
ZEROS = ["0", "0.2", "0.4", "0.6", "0.8"]
MODES = [("sparse", "sparse"), ("dense", "dense")]
PHASES = ["load_config", "load_iact", "load_wght", "load_bias", "load_quant", "load_act", "convert_iact", "compute",
          "writeback", "pooling", "readout"]
CLOCK_NS = 4.0


def fmt(n):
    return f"{int(n):,}".replace(",", ".")


def sfmt(n):
    return "0" if n == 0 else ("+" if n > 0 else "−") + fmt(abs(n))


def pc(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",") + " %"


def ph(x, name):
    return x["phases"].get(name, {}).get("cycles", 0)


def lname(layer):
    i = layer["info"]
    if i["name"].startswith("Conv"):
        return f"Conv {i['iact_size_x']}×{i['iact_size_y']}×{i['channels']}→{i['filters']}"
    if i["name"].startswith("Dense"):
        return f"Dense {i['iact_size_x']}→{i['filters']}"
    return f"Pool {i['iact_size_x']}×{i['iact_size_y']}"


def zin(layer):
    d = layer["info"].get("input") or {}
    return 100.0 * d.get("zeros", 0) / d["values"] if d.get("values") else 0.0


def load(d, case):
    p = os.path.join(d, case + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def part_a(d, out, status):
    out.append("## A. Chu kỳ của hàm kích hoạt theo từng layer (mạng Bảng 2, CR 2 X 4 Y 3)\n")
    for mode, mlab in MODES:
        runs = {a: load(d, f"act_{a}_{mode}") for a, _ in ACTS}
        if not runs["none"]:
            out.append(f"(thiếu act_none_{mode})\n")
            continue
        base = runs["none"]
        out.append(f"### Phần cứng {mlab}\n")
        out.append("| hàm | trạng thái | tổng chu kỳ | so với không hàm | Δ load_act | Δ writeback | Δ compute | Δ pha khác |")
        out.append("|---|---|---:|---:|---:|---:|---:|---:|")
        for a, lab in ACTS:
            r = runs[a]
            if not r:
                out.append(f"| {lab} | {status.get(f'act_{a}_{mode}', 'chưa chạy')} | | | | | | |")
                continue
            dt = r["total_cycles"] - base["total_cycles"]
            dl, dw, dc = (ph(r, p) - ph(base, p) for p in ("load_act", "writeback", "compute"))
            out.append(f"| {lab} | {status.get(f'act_{a}_{mode}', '?')} | {fmt(r['total_cycles'])} | {sfmt(dt)} "
                       f"({pc(100.0 * dt / base['total_cycles'], 2)}) | {sfmt(dl)} | {sfmt(dw)} | {sfmt(dc)} | "
                       f"{sfmt(dt - dl - dw - dc)} |")
        out.append("")
        out.append("Từng layer: chi phí trực tiếp = Δ chu kỳ của layer trừ Δ compute (nạp bảng, ghi ngược qua khối kích "
                   "hoạt); chu kỳ khối kích hoạt = số chu kỳ khối này làm việc, nằm trong writeback; số 0 ở input layer "
                   "sau và Δ compute của layer tính sau = ảnh hưởng gián tiếp.\n")
        out.append("| layer | hàm | tổng | Δ tổng | Δ trực tiếp (load_act / writeback) | chu kỳ khối kích hoạt / writeback "
                   "| số 0 ở input layer sau | Δ compute layer tính sau |")
        out.append("|---|---|---:|---:|---:|---:|---:|---:|")
        layers = base["layers"]
        weighted = [k for k, l in enumerate(layers) if l["info"]["name"] != "Pooling"]
        for k in weighted[:-1]:
            nxt = k + 1
            nxt_w = next(j for j in weighted if j > k)
            for a, lab in ACTS:
                r = runs[a]
                if not r:
                    continue
                L, B = r["layers"][k], layers[k]
                dt = L["total_cycles"] - B["total_cycles"]
                dc = ph(L, "compute") - ph(B, "compute")
                dl = ph(L, "load_act") - ph(B, "load_act")
                dw = ph(L, "writeback") - ph(B, "writeback")
                dnc = ph(r["layers"][nxt_w], "compute") - ph(layers[nxt_w], "compute")
                out.append(f"| {lname(B) if a == 'none' else ''} | {lab} | {fmt(L['total_cycles'])} | {sfmt(dt)} | "
                           f"{sfmt(dt - dc)} ({sfmt(dl)} / {sfmt(dw)}) | {fmt(L.get('activation_cycles', 0))} / "
                           f"{fmt(ph(L, 'writeback'))} | {pc(zin(r['layers'][nxt]))} | {sfmt(dnc)} |")
        out.append("")


def part_b(d, out, status):
    out.append("## B. Nạp weight theo tỉ lệ weight bằng 0 (CR 2 X 4 Y 3)\n")
    for model, title in (("mnist", "MNIST đã huấn luyện (ReLU, ảnh test 0)"), ("t2", "Mạng Bảng 2 (không hàm kích hoạt)")):
        out.append(f"### {title}\n")
        out.append("| weight = 0 | chế độ | trạng thái | nạp weight | tính toán | tổng | nạp weight / tổng | µs @250 MHz |")
        out.append("|---|---|---|---:|---:|---:|---:|---:|")
        rows = {}
        for z in ZEROS:
            for mode, mlab in MODES:
                case = f"wz_{model}_z{z}_{mode}"
                r = load(d, case)
                rows[(z, mode)] = r
                if not r:
                    out.append(f"| {pc(float(z) * 100, 0)} | {mlab} | {status.get(case, 'chưa chạy')} | | | | | |")
                    continue
                out.append(f"| {pc(float(z) * 100, 0)} | {mlab} | {status.get(case, '?')} | {fmt(ph(r, 'load_wght'))} | "
                           f"{fmt(ph(r, 'compute'))} | {fmt(r['total_cycles'])} | "
                           f"{pc(100.0 * ph(r, 'load_wght') / r['total_cycles'])} | "
                           f"{r['total_cycles'] * CLOCK_NS / 1000:.1f} |".replace(".", ",", 0))
        out.append("")
        out.append("Dense so với sparse ở từng mức (âm: dense ít chu kỳ hơn):\n")
        out.append("| weight = 0 | nạp weight | tính toán | tổng |")
        out.append("|---|---:|---:|---:|")
        for z in ZEROS:
            s, dd = rows[(z, "sparse")], rows[(z, "dense")]
            if not (s and dd):
                continue
            cells = []
            for get in (lambda x: ph(x, "load_wght"), lambda x: ph(x, "compute"), lambda x: x["total_cycles"]):
                a, b = get(s), get(dd)
                cells.append(f"{sfmt(b - a)} ({pc(100.0 * (b - a) / a)})")
            out.append(f"| {pc(float(z) * 100, 0)} | " + " | ".join(cells) + " |")
        out.append("")
        out.append("Nạp weight từng layer (chu kỳ) theo tỉ lệ weight bằng 0:\n")
        ref = rows.get(("0", "sparse")) or rows.get(("0", "dense"))
        if ref:
            idx = [k for k, l in enumerate(ref["layers"]) if l["info"]["name"] != "Pooling"]
            out.append("| layer | chế độ | " + " | ".join(pc(float(z) * 100, 0) for z in ZEROS) + " |")
            out.append("|---|---|" + "---:|" * len(ZEROS))
            for k in idx:
                for mode, mlab in MODES:
                    vals = [fmt(ph(rows[(z, mode)]["layers"][k], "load_wght")) if rows[(z, mode)] else "–"
                            for z in ZEROS]
                    out.append(f"| {lname(ref['layers'][k]) if mode == 'sparse' else ''} | {mlab} | "
                               + " | ".join(vals) + " |")
            out.append("")
            out.append("Tính toán từng layer (chu kỳ):\n")
            out.append("| layer | chế độ | " + " | ".join(pc(float(z) * 100, 0) for z in ZEROS) + " |")
            out.append("|---|---|" + "---:|" * len(ZEROS))
            for k in idx:
                for mode, mlab in MODES:
                    vals = [fmt(ph(rows[(z, mode)]["layers"][k], "compute")) if rows[(z, mode)] else "–"
                            for z in ZEROS]
                    out.append(f"| {lname(ref['layers'][k]) if mode == 'sparse' else ''} | {mlab} | "
                               + " | ".join(vals) + " |")
            out.append("")


GRID_SHAPES = [("conv1", "Conv 28×28×1→16 (ảnh)"), ("conv2", "Conv 14×14×16→32"), ("conv3", "Conv 7×7×32→32"),
               ("fc", "Dense 1568→32")]


def part_c(d, out):
    sp = os.path.join(d, "status.json")
    status = json.load(open(sp)) if os.path.exists(sp) else {}
    bad = sorted(c for c, v in status.items() if not v.startswith("PASS"))
    out.append("## C. Một layer, lưới tỉ lệ số 0 của weight × activation (CR 2 X 4 Y 3)\n")
    out.append(f"{sum(1 for v in status.values() if v.startswith('PASS'))}/{len(status)} PASS"
               + (f"; lỗi: {', '.join(bad)}" if bad else "") + ".\n")
    head = "| weight = 0 \\ input = 0 | " + " | ".join(pc(float(a) * 100, 0) for a in ZEROS) + " |"
    sep = "|---|" + "---:|" * len(ZEROS)
    for shape, title in GRID_SHAPES:
        g = {(w, a, m): load(d, f"grid_{shape}_w{w}_a{a}_{m}") for w in ZEROS for a in ZEROS for m, _ in MODES}
        out.append(f"### {title}\n")
        for name, label in (("load_wght", "nạp weight"), ("compute", "tính toán")):
            for m, mlab in MODES:
                vals = {(w, a): ph(g[(w, a, m)], name) for w in ZEROS for a in ZEROS if g[(w, a, m)]}
                if vals and len(set(vals.values())) == 1:
                    out.append(f"- {label}, {mlab}: {fmt(next(iter(vals.values())))} chu kỳ ở cả {len(vals)} điểm "
                               "(không phụ thuộc số 0).")
                    continue
                out.append(f"\n{label.capitalize()}, {mlab} (chu kỳ):\n")
                out.append(head)
                out.append(sep)
                for w in ZEROS:
                    out.append(f"| {pc(float(w) * 100, 0)} | " + " | ".join(
                        fmt(vals[(w, a)]) if (w, a) in vals else "–" for a in ZEROS) + " |")
        out.append("\nTổng chu kỳ của layer, sparse / dense (dưới 100 %: sparse nhanh hơn):\n")
        out.append(head)
        out.append(sep)
        for w in ZEROS:
            cells = []
            for a in ZEROS:
                s_, d_ = g[(w, a, "sparse")], g[(w, a, "dense")]
                cells.append(pc(100.0 * s_["total_cycles"] / d_["total_cycles"]) if s_ and d_ else "–")
            out.append(f"| {pc(float(w) * 100, 0)} | " + " | ".join(cells) + " |")
        s0 = g[("0", "0", "sparse")]
        d0 = g[("0", "0", "dense")]
        if s0 and d0:
            out.append(f"\nNạp weight / tổng ở 0 % số 0: sparse {pc(100.0 * ph(s0, 'load_wght') / s0['total_cycles'])}, "
                       f"dense {pc(100.0 * ph(d0, 'load_wght') / d0['total_cycles'])}.\n")


def main():
    args = sys.argv[1:]
    grid = None
    if "--grid" in args:
        i = args.index("--grid")
        grid = args[i + 1]
        del args[i:i + 2]
    d = args[0]
    sp = os.path.join(d, "status.json")
    status = json.load(open(sp)) if os.path.exists(sp) else {}
    out = []
    part_a(d, out, status)
    part_b(d, out, status)
    if grid:
        part_c(grid, out)
    text = "\n".join(out) + "\n"
    if len(args) > 1:
        open(args[1], "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
