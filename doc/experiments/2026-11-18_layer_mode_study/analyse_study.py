"""analyse_study.py: step 1 of the per-layer mode plan (README_FI section 2), from saved profiles.

  networks  per layer and per phase, sparse against dense hardware, for the trained MNIST net (4 activations, image 0)
            and the Table 2 network (16 configurations, no activation and ReLU); per layer the better mode, the gain
            of choosing per layer (P2) and of the per-layer weight format (P1 estimate: the sparse layer minus the
            load_wght difference of the two modes)
  sweep     one layer at 0-90 % input zeros (test_sweep.py), both modes: total and phases, the crossover zero share
            (today and with P1), a linear fit of the sparse compute against the non-zero share and its check on the
            network layers
  model     step 1d: the per-layer choice predicted from the sweep (compute ratio interpolated in the zero share,
            load_wght from the transfer sizes) against the measured choice on the networks

Usage (repository root):
  venv/bin/python doc/experiments/2026-11-18_layer_mode_study/analyse_study.py networks [--mnist DIR] [--t3 SPARSE DENSE RELU]
  venv/bin/python doc/experiments/2026-11-18_layer_mode_study/analyse_study.py sweep SPARSE_DIR DENSE_DIR [--t3relu DIR]
  venv/bin/python doc/experiments/2026-11-18_layer_mode_study/analyse_study.py model SPARSE_DIR DENSE_DIR [--mnist DIR]
      [--t3relu DIR --t3dense DIR]
Prints markdown."""
import argparse
import glob
import json
import os

PHASES = ["load_config", "load_iact", "load_wght", "load_bias", "load_quant", "load_act", "convert_iact", "compute",
          "writeback", "pooling", "readout"]
SHOW = ["load_iact", "load_wght", "load_bias", "convert_iact", "compute", "writeback", "readout"]


def fmt(v):
    return f"{v:,.0f}".replace(",", ".")


def pct(new, old):
    return (f"{100.0 * (new - old) / old:+.1f} %").replace(".", ",") if old else ""


def ph(layer, name):
    return layer["phases"].get(name, {}).get("cycles", 0)


def label(layer):
    info = layer.get("info") or {}
    name = info.get("name", "?")
    if name == "Pooling":
        return f"Pool {info.get('iact_size_x')}x{info.get('iact_size_y')}x{info.get('channels')}"
    if name == "Dense":
        return f"Dense {info.get('iact_size_x')} -> {info.get('filters')}"
    return f"Conv {info.get('iact_size_x')}x{info.get('iact_size_y')}x{info.get('channels')} -> {info.get('filters')}"


def zeros(layer):
    inp = (layer.get("info") or {}).get("input") or {}
    return 100.0 * inp["zeros"] / inp["values"] if inp.get("values") else None


def layer_rows(sparse, dense):
    """Per layer: (label, zeros %, sparse, dense, best, p1, phases sparse, phases dense)."""
    rows = []
    for ls, ld in zip(sparse["layers"], dense["layers"]):
        s, d = ls["total_cycles"], ld["total_cycles"]
        p1 = s - (ph(ls, "load_wght") - ph(ld, "load_wght"))
        rows.append((label(ls), zeros(ls), s, d, min(s, d), min(p1, s),
                     {p: ph(ls, p) for p in PHASES}, {p: ph(ld, p) for p in PHASES}))
    return rows


def network_table(title, sparse, dense):
    rows = layer_rows(sparse, dense)
    ts, td = sparse["total_cycles"], dense["total_cycles"]
    best_single = min(ts, td)
    other = ts - sum(r[2] for r in rows)          # cycles outside the layers (none today)
    p2 = sum(r[4] for r in rows) + other
    p1 = sum(r[5] for r in rows) + other
    p12 = sum(min(r[5], r[3]) for r in rows) + other   # P1 and the FSM per layer as well
    out = [f"\n#### {title}\n",
           "| # | layer | input zeros | sparse | dense | better | P1 (est.) | " + " | ".join(f"{p} s / d" for p in SHOW) + " |",
           "|---:|---|---:|---:|---:|---|---:|" + "---:|" * len(SHOW)]
    for i, (lab, z, s, d, b, q, ps, pd) in enumerate(rows):
        better = "=" if s == d else ("sparse" if s < d else "dense")
        out.append(f"| {i} | {lab} | {'' if z is None else f'{z:.1f} %'.replace('.', ',')} | {fmt(s)} | {fmt(d)} | {better} "
                   f"({pct(min(s, d), max(s, d))}) | {fmt(q)} | " + " | ".join(f"{fmt(ps[p])} / {fmt(pd[p])}" for p in SHOW) + " |")
    out.append(f"| | **network** | | **{fmt(ts)}** | **{fmt(td)}** | best per layer (P2) **{fmt(p2)}** "
               f"({pct(p2, best_single)} vs the better mode) | **{fmt(p1)}** ({pct(p1, best_single)}) | |")
    return "\n".join(out), (ts, td, p2, p1, p12)


def load(path):
    return json.load(open(path))


def networks(args):
    out = ["## Networks: per layer and phase, sparse / dense (cycles)\n"]
    summary = []
    phase_runs = []
    if args.mnist:
        for act in ("relu", "leaky_relu", "silu", "hardswish"):
            fs = glob.glob(os.path.join(args.mnist, f"trained_{act}_img0_sparse*.json"))
            fd = glob.glob(os.path.join(args.mnist, f"trained_{act}_img0_dense*.json"))
            if not fs or not fd:
                continue
            s, d = load(sorted(fs)[0]), load(sorted(fd)[0])
            text, tot = network_table(f"MNIST, {act}, image 0", s, d)
            out.append(text)
            summary.append((f"MNIST {act}",) + tot)
            phase_runs.append((f"MNIST {act}", s, d))
    if args.t3:
        sdir, ddir, rdir = args.t3
        for name in sorted(os.listdir(sdir)):
            if not name.startswith("paper_cr"):
                continue
            s, d = load(os.path.join(sdir, name)), load(os.path.join(ddir, name))
            tot = network_table(f"Table 2 network, {name[6:-5]}, no activation", s, d)[1]
            summary.append((f"T2 {name[6:-5]}",) + tot)
            if rdir and os.path.exists(os.path.join(rdir, name)):
                r = load(os.path.join(rdir, name))
                text, tot = network_table(f"Table 2 network, {name[6:-5]}, ReLU (dense = dense without activation: the "
                                          f"dense datapath does not depend on the data)", r, d)
                if name[6:-5] in ("cr1_x2_y3", "cr2_x4_y3", "cr8_x4_y3"):
                    out.append(text)
                    phase_runs.append((f"T2 {name[6:-5]} ReLU", r, d))
                summary.append((f"T2 {name[6:-5]} ReLU",) + tot)
            if name[6:-5] in ("cr1_x2_y3", "cr2_x4_y3", "cr8_x4_y3"):
                phase_runs.append((f"T2 {name[6:-5]} no act.", s, d))
    out.append("\n## Phases: whole network, sum over the layers (cycles; P1 = sparse with the dense load_wght where it is "
               "smaller)\n")
    out.append("Only load_wght and compute differ between the modes; the other phases (load_config, load_iact, "
               "load_bias, load_quant, load_act, convert_iact, writeback, pooling, readout) are cycle-identical in "
               "every run and are shown as one row.\n")
    out.append("| run | phase | sparse (today) | dense HW | P1 (est.) | dense - sparse | P1 - sparse |")
    out.append("|---|---|---:|---:|---:|---:|---:|")
    for name, sparse, dense in phase_runs:
        rest = [0, 0, 0]
        for p in PHASES:
            s = sum(ph(l, p) for l in sparse["layers"])
            d = sum(ph(l, p) for l in dense["layers"])
            q = sum(min(ph(ls, p), ph(ld, p)) if p == "load_wght" else ph(ls, p)
                    for ls, ld in zip(sparse["layers"], dense["layers"]))
            if p in ("load_wght", "compute") or s != d:
                out.append(f"| {name} | {p} | {fmt(s)} | {fmt(d)} | {fmt(q)} | {fmt(d - s)} ({pct(d, s)}) | "
                           f"{fmt(q - s)} ({pct(q, s)}) |")
            else:
                rest = [rest[0] + s, rest[1] + d, rest[2] + q]
        ts, td = sparse["total_cycles"], dense["total_cycles"]
        tq = ts - sum(max(0, ph(ls, "load_wght") - ph(ld, "load_wght"))
                      for ls, ld in zip(sparse["layers"], dense["layers"]))
        out.append(f"| {name} | other phases | {fmt(rest[0])} | {fmt(rest[1])} | {fmt(rest[2])} | 0 | 0 |")
        out.append(f"| {name} | **total** | **{fmt(ts)}** | **{fmt(td)}** | **{fmt(tq)}** | {fmt(td - ts)} ({pct(td, ts)}) | "
                   f"{fmt(tq - ts)} ({pct(tq, ts)}) |")
    out.append("\n## Per layer: cycles each option saves against today's sparse hardware (share of the network)\n")
    out.append("P1 = the dense load_wght (weight format per layer); FSM = the better FSM per layer (P2) alone; FSM after P1 "
               "= what P2 still saves once P1 is in. Pooling layers are equal in both modes and left out.\n")
    out.append("| run | layer | input zeros | P1 saves | FSM alone saves | FSM after P1 saves |")
    out.append("|---|---|---:|---:|---:|---:|")
    for name, sparse, dense in phase_runs:
        ts = sparse["total_cycles"]
        for ls, ld in zip(sparse["layers"], dense["layers"]):
            if (ls.get("info") or {}).get("name") == "Pooling":
                continue
            s, d = ls["total_cycles"], ld["total_cycles"]
            g1 = max(0, ph(ls, "load_wght") - ph(ld, "load_wght"))
            g2 = max(0, s - d)
            g21 = max(0, (s - g1) - d)
            z = zeros(ls)
            share = lambda g: f"{fmt(g)} ({f'{100.0 * g / ts:.1f}'.replace('.', ',')} %)" if g else "0"
            out.append(f"| {name} | {label(ls)} | {'' if z is None else f'{z:.1f} %'.replace('.', ',')} | {share(g1)} | "
                       f"{share(g2)} | {share(g21)} |")
    out.append("\n## Summary: whole network\n")
    out.append("| run | sparse | dense | best per layer (P2) | P1 (est.) | P1 + P2 (est.) | P2 vs better mode | "
               "P1 vs better mode | P1 + P2 vs better mode | P1 vs sparse |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, ts, td, p2, p1, p12 in summary:
        b = min(ts, td)
        out.append(f"| {name} | {fmt(ts)} | {fmt(td)} | {fmt(p2)} | {fmt(p1)} | {fmt(p12)} | {pct(p2, b)} | {pct(p1, b)} | "
                   f"{pct(p12, b)} | {pct(p1, ts)} |")
    if args.lut:
        ls_, ld_, l1, l2 = args.lut
        l12 = l1 + l2 - ls_
        out.append(f"\n## Against today's sparse hardware: cycles and cycles x LUT (LUT sparse {fmt(ls_)}, dense {fmt(ld_)}, "
                   f"P1 {fmt(l1)}, P2 {fmt(l2)}, P1 + P2 {fmt(l12)})\n")
        out.append("| run | dense HW cycles | P2 | P1 | P1 + P2 | dense HW cycles x LUT | P2 | P1 | P1 + P2 |")
        out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        ranges = {}
        for name, ts, td, p2, p1, p12 in summary:
            vals = [td, p2, p1, p12]
            area = [v * l for v, l in zip(vals, (ld_, l2, l1, l12))]
            out.append(f"| {name} | " + " | ".join(pct(v, ts) for v in vals) + " | "
                       + " | ".join(pct(a, ts * ls_) for a in area) + " |")
            group = "ReLU" if ("relu" in name.lower() and "leaky" not in name.lower()) else "other"
            for k, (v, a) in enumerate(zip(vals, area)):
                ranges.setdefault((group, k), []).append((100.0 * (v - ts) / ts, 100.0 * (a - ts * ls_) / (ts * ls_)))
        out.append("\n| inputs | option | cycles min .. max | cycles x LUT min .. max |")
        out.append("|---|---|---|---|")
        for (group, k), vs in sorted(ranges.items()):
            c = sorted(v[0] for v in vs)
            a = sorted(v[1] for v in vs)
            out.append(f"| {group} ({len(vs)} runs) | {['dense HW', 'P2', 'P1', 'P1 + P2'][k]} | "
                       f"{c[0]:+.1f} .. {c[-1]:+.1f} % | {a[0]:+.1f} .. {a[-1]:+.1f} % |".replace(".", ",").replace(",,", ".."))
    print("\n".join(out))


def sweep(args):
    from collections import defaultdict
    S, D = {}, {}
    for d, store in ((args.sparse, S), (args.dense, D)):
        for f in glob.glob(os.path.join(d, "*_z*_*.json")):
            store[os.path.basename(f)[:-5]] = load(f)
    grid = defaultdict(dict)
    for case in S:
        if case not in D:
            continue
        shape, rest = case.split("_z", 1)
        zero, config = rest.split("_", 1)
        grid[(shape, config)][float(zero)] = (S[case], D[case])
    out = ["## Sweep: one layer, input zero share 0-90 %, sparse / dense (cycles)\n"]
    fits = {}
    crossovers = {}
    for (shape, config) in sorted(grid):
        pts = grid[(shape, config)]
        out.append(f"\n#### {shape}, {config}\n")
        out.append("| zeros | sparse | dense | sparse - dense | P1 (est.) | " + " | ".join(f"{p} s / d" for p in SHOW) + " |")
        out.append("|---:|---:|---:|---:|---:|" + "---:|" * len(SHOW))
        xs, ys = [], []
        cross = None
        prev = None
        cross1, prev1 = None, None
        for z in sorted(pts):
            s, d = pts[z]
            ls, ld = s["layers"][0], d["layers"][0]
            ts, td = s["total_cycles"], d["total_cycles"]
            p1 = ts - (ph(ls, "load_wght") - ph(ld, "load_wght"))
            out.append(f"| {z:.2f} | {fmt(ts)} | {fmt(td)} | {pct(ts, td)} | {fmt(p1)} | "
                       + " | ".join(f"{fmt(ph(ls, p))} / {fmt(ph(ld, p))}" for p in SHOW) + " |")
            xs.append(1.0 - z)
            ys.append(ph(ls, "compute"))
            diff = ts - td
            if prev is not None and cross is None and (prev[1] > 0) != (diff > 0):
                z0, d0 = prev
                cross = z0 + (z - z0) * d0 / (d0 - diff)       # linear interpolation of sparse - dense = 0
            prev = (z, diff)
            diff1 = p1 - td
            if prev1 is not None and cross1 is None and (prev1[1] > 0) != (diff1 > 0):
                z0, d0 = prev1
                cross1 = z0 + (z - z0) * d0 / (d0 - diff1)
            prev1 = (z, diff1)
        if cross1 is None:
            cross1 = "P1 always faster" if prev1[1] <= 0 and all(
                pts[z][0]["total_cycles"] - ph(pts[z][0]["layers"][0], "load_wght") + ph(pts[z][1]["layers"][0], "load_wght")
                <= pts[z][1]["total_cycles"] for z in pts) else "dense always faster"
        if prev is not None and cross is None:
            cross = "sparse always faster" if prev[1] <= 0 and all(
                pts[z][0]["total_cycles"] <= pts[z][1]["total_cycles"] for z in pts) else "dense always faster" \
                if all(pts[z][0]["total_cycles"] > pts[z][1]["total_cycles"] for z in pts) else "?"
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
        a = my - b * mx
        ss = sum((y - my) ** 2 for y in ys)
        r2 = 1 - sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / ss if ss else 1.0
        fits[(shape, config)] = (a, b)
        dense_compute = ph(pts[min(pts)][1]["layers"][0], "compute")
        crossovers[(shape, config)] = (cross, cross1)
        out.append(f"\nCrossover (sparse = dense, total): "
                   f"{cross if isinstance(cross, str) else f'{100 * cross:.0f} % zeros'}; with P1 (P1 = dense): "
                   f"{cross1 if isinstance(cross1, str) else f'{100 * cross1:.0f} % zeros'}; sparse compute ~ "
                   f"{fmt(a)} + {fmt(b)} x non-zero share (R2 {r2:.3f}); dense compute {fmt(dense_compute)}.")
    if args.t3relu:
        out.append("\n## Fit check on the Table 2 network with ReLU (same layer shapes, measured input zeros)\n")
        out.append("| layer | config | input zeros | compute measured | compute from the sweep fit | error |")
        out.append("|---|---|---:|---:|---:|---:|")
        shapes = {0: "conv1", 2: "conv2", 4: "conv3", 5: "fc"}
        names = {"cr1x2": "paper_cr1_x2_y3", "cr2x4": "paper_cr2_x4_y3", "cr8x4": "paper_cr8_x4_y3"}
        for config, name in names.items():
            path = os.path.join(args.t3relu, name + ".json")
            if not os.path.exists(path):
                continue
            prof = load(path)
            for idx, shape in shapes.items():
                if (shape, config) not in fits:
                    continue
                layer = prof["layers"][idx]
                z = zeros(layer) or 0.0
                a, b = fits[(shape, config)]
                pred = a + b * (1 - z / 100)
                meas = ph(layer, "compute")
                out.append(f"| {shape} | {config} | {z:.1f} % | {fmt(meas)} | {fmt(pred)} | {pct(pred, meas)} |".replace(".", ",", 1))
    out.append("\n## Crossover zero share of the layer input (whole layer: below it dense hardware is faster)\n")
    out.append("| shape | config | today (sparse = dense) | with P1 (P1 = dense) |")
    out.append("|---|---|---:|---:|")
    for (shape, config), (c0, c1) in sorted(crossovers.items()):
        show = [c if isinstance(c, str) else f"{100 * c:.0f} %" for c in (c0, c1)]
        out.append(f"| {shape} | {config} | {show[0]} | {show[1]} |")
    print("\n".join(out))


def shape_class(layer):
    info = layer.get("info") or {}
    if info.get("name") == "Dense":
        return "fc" if info.get("iact_size_x", 0) > 256 else None
    if info.get("name") != "Convolution2D":
        return None
    if info.get("channels") == 1:
        return "conv1"
    return "conv2" if info.get("iact_size_x", 0) >= 14 else "conv3"


def model(args):
    """Step 1d: predict per layer from the sweep (ratio sparse / dense compute, interpolated in the input zero share)
    and the transfer sizes; compare the predicted choice with the measured one on the networks."""
    S, D = {}, {}
    for d, store in ((args.sparse, S), (args.dense, D)):
        for f in glob.glob(os.path.join(d, "*_z*_*.json")):
            store[os.path.basename(f)[:-5]] = load(f)
    curves = {}
    for case in S:
        if case not in D:
            continue
        shape, rest = case.split("_z", 1)
        zero, config = rest.split("_", 1)
        cs, cd = ph(S[case]["layers"][0], "compute"), ph(D[case]["layers"][0], "compute")
        curves.setdefault((shape, config), []).append((float(zero), cs / cd))
    for k in curves:
        curves[k].sort()

    def ratio(shape, config, z):
        pts = curves[(shape, config)]
        if z <= pts[0][0]:
            return pts[0][1]
        for (z0, r0), (z1, r1) in zip(pts, pts[1:]):
            if z <= z1:
                return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
        return pts[-1][1]

    runs = []
    for act in ("relu", "leaky_relu", "silu", "hardswish"):
        fs = glob.glob(os.path.join(args.mnist, f"trained_{act}_img0_sparse*.json")) if args.mnist else []
        fd = glob.glob(os.path.join(args.mnist, f"trained_{act}_img0_dense*.json")) if args.mnist else []
        if fs and fd:
            runs.append((f"MNIST {act}", "cr2x4", load(sorted(fs)[0]), load(sorted(fd)[0])))
    for name, config in (("paper_cr1_x2_y3", "cr1x2"), ("paper_cr2_x4_y3", "cr2x4"), ("paper_cr8_x4_y3", "cr8x4")):
        if args.t3relu and args.t3dense and os.path.exists(os.path.join(args.t3relu, name + ".json")):
            runs.append((f"T2 {name[6:]} ReLU", config, load(os.path.join(args.t3relu, name + ".json")),
                         load(os.path.join(args.t3dense, name + ".json"))))
    out = ["## Cost model check (step 1d): per layer, predicted from the sweep against measured\n",
           "Prediction: sparse compute = dense compute x the sweep ratio at the layer's input zero share (same shape "
           "class and cluster configuration; MNIST runs at CR 2 X 4); load_wght from the transfer sizes. Differences "
           "as a share of the dense layer.\n",
           "| run | layer | class | input zeros | sparse - dense measured | predicted | choice today measured / "
           "predicted | P1 - dense measured | predicted | choice with P1 measured / predicted |",
           "|---|---|---|---:|---:|---:|---|---:|---:|---|"]
    total = right0 = right1 = 0
    lost0 = lost1 = 0
    for name, config, s, d in runs:
        for ls, ld in zip(s["layers"], d["layers"]):
            shape = shape_class(ls)
            if shape is None or (shape, config) not in curves:
                continue
            z = zeros(ls) or 0.0
            cd, ts, td = ph(ld, "compute"), ls["total_cycles"], ld["total_cycles"]
            dw = ph(ls, "load_wght") - ph(ld, "load_wght")
            dc_pred = (ratio(shape, config, z / 100) - 1) * cd
            m0, p0 = ts - td, dw + dc_pred
            m1, p1 = ts - dw - td, dc_pred
            pick = lambda v: "sparse" if v < 0 else "dense"
            total += 1
            right0 += pick(m0) == pick(p0)
            right1 += pick(m1) == pick(p1)
            lost0 += abs(m0) if pick(m0) != pick(p0) else 0
            lost1 += abs(m1) if pick(m1) != pick(p1) else 0
            out.append(f"| {name} | {label(ls)} | {shape} | {z:.1f} % | {pct(td + m0, td)} | {pct(td + p0, td)} | "
                       f"{pick(m0)} / {pick(p0)} | {pct(td + m1, td)} | {pct(td + p1, td)} | {pick(m1)} / {pick(p1)} |")
    out.append(f"\nRight choices: today {right0} of {total} (cycles lost by the wrong ones {fmt(lost0)}), with P1 "
               f"{right1} of {total} (lost {fmt(lost1)}).")
    print("\n".join(out))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("networks")
    n.add_argument("--mnist")
    n.add_argument("--t3", nargs=3, metavar=("SPARSE", "DENSE", "RELU"))
    n.add_argument("--lut", nargs=4, type=float, metavar=("SPARSE", "DENSE", "P1", "P2"),
                   help="LUT counts for the area-normalised table")
    w = sub.add_parser("sweep")
    w.add_argument("sparse")
    w.add_argument("dense")
    w.add_argument("--t3relu")
    m = sub.add_parser("model")
    m.add_argument("sparse")
    m.add_argument("dense")
    m.add_argument("--mnist")
    m.add_argument("--t3relu")
    m.add_argument("--t3dense")
    args = p.parse_args()
    {"networks": networks, "sweep": sweep, "model": model}[args.cmd](args)


if __name__ == "__main__":
    main()
