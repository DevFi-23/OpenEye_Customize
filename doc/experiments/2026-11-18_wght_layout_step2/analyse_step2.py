"""analyse_step2.py: tables of step 2 of the per-layer weight format P1 (README_FI section 2).

  single STEP2_DIR SWEEP_DENSE_DIR      the single-layer runs of test_step2.py (controls, bit-exactness, compute cost of
                                        zero weights, P1 with the measured cost; dense hardware from the step 1 sweep)
  networks SPARSE DENSE LAYOUT [...]    whole networks: today's sparse profile, the dense hardware profile and the sparse
                                        profile with the dense weight layout (forced raw mode); groups of three dirs or
                                        files, see main()
Markdown on stdout. From the repository root."""
import json
import os
import sys

from test_step2 import CASES, CONFIGS, IACT_ZEROS, SHAPES, WGHT_ZEROS

PHASES = ("load_wght", "compute")


def fmt(v):
    return f"{v:,}"


def pct(a, b):
    return f"{100.0 * (a - b) / b:+.1f} %".replace(".", ",") if b else "-"


def ph(layer_or_profile, name):
    return layer_or_profile["phases"].get(name, {}).get("cycles", 0)


def load(path):
    return json.load(open(path)) if os.path.exists(path) else None


def single(step2, sweep_dense):
    status = json.load(open(os.path.join(step2, "status.json")))
    prof = {case: load(os.path.join(step2, f"{case}.json")) for case in CASES}

    print("## Controls (conv2 14x14x16 -> 32, CR 2 X 4, 50 % input zeros, 25 % weight zeros)\n")
    print("| Run | Result | total | load_wght | compute | other phases |")
    print("|---|---|---:|---:|---:|---:|")
    controls = ["csc", "cscraw", "dense", "cscpar", "densepar", "denseparraw", "densebad"]
    for layout in controls:
        case = f"conv2_i0.5_w0.25_{layout}_cr2x4"
        p = prof.get(case)
        if p:
            t, lw, cp = p["total_cycles"], ph(p, "load_wght"), ph(p, "compute")
            print(f"| `{layout}` | {status.get(case, '?')} | {fmt(t)} | {fmt(lw)} | {fmt(cp)} | {fmt(t - lw - cp)} |")
        else:
            print(f"| `{layout}` | {status.get(case, 'not run')} | | | | |")
    print()

    dense_cases = [c for c, v in CASES.items() if v[3] == "dense"]
    ok = [c for c in dense_cases if status.get(c, "").startswith("PASS")]
    print(f"Dense layout (raw forced), all runs: {len(ok)} / {len(dense_cases)} PASS; "
          f"zero-compressed: {sum(status.get(c, '').startswith('PASS') for c, v in CASES.items() if v[3] == 'csc')} / "
          f"{sum(1 for v in CASES.values() if v[3] == 'csc')} PASS.\n")

    same = []
    for s in SHAPES:
        for c in CONFIGS:
            a, b = prof.get(f"{s}_i0_w0_csc_{c}"), prof.get(f"{s}_i0_w0_dense_{c}")
            if a and b:
                same.append(a["total_cycles"] == b["total_cycles"])
    print(f"No zero weights (both layouts are the same stream): equal total cycles in {sum(same)} / {len(same)} runs.\n")

    print("## Compute cost of zero weights (dense layout against zero-compressed, same data)\n")
    print("`compute` increase, and as a share of the proportional bound of step 1 (compute x weight zero share); "
          "`load_wght` equal in both layouts unless noted.\n")
    head = " | ".join(f"w {float(w) * 100:.0f} %" for w in WGHT_ZEROS[1:])
    print(f"| Layer | Config | input zeros | {head} |")
    print("|---|---|---:|" + "---:|" * (len(WGHT_ZEROS) - 1))
    lw_diff = []
    for s, (_, x, y, ch, f) in SHAPES.items():
        for c in CONFIGS:
            for i in IACT_ZEROS:
                cells = []
                for w in WGHT_ZEROS[1:]:
                    a, b = prof.get(f"{s}_i{i}_w{w}_csc_{c}"), prof.get(f"{s}_i{i}_w{w}_dense_{c}")
                    if not (a and b):
                        cells.append("-")
                        continue
                    ca, cb = ph(a, "compute"), ph(b, "compute")
                    bound = ca * float(w)
                    share = f"{100.0 * (cb - ca) / bound:.0f}" if bound else "-"
                    cells.append(f"{pct(cb, ca)} ({share} %)")
                    if ph(a, "load_wght") != ph(b, "load_wght"):
                        lw_diff.append((s, c, i, w, ph(a, "load_wght"), ph(b, "load_wght")))
                print(f"| {s} {x}x{y}x{ch} -> {f} | {c} | {float(i) * 100:.0f} % | " + " | ".join(cells) + " |")
    print()
    print("load_wght differs in: " + (", ".join(f"{d[:4]} {d[4]} / {d[5]}" for d in lw_diff) or "no run") + ".\n")

    print("## P1 with the measured cost (whole layer, cycles)\n")
    print("P1 = dense-layout run minus the `load_wght` difference sparse - dense hardware (step 1 sweep); step 1 "
          "estimate = zero-compressed run minus the same difference (zero weights still skipped).\n")
    print("| Layer | Config | input zeros | weight zeros | sparse today | dense HW | P1 step 1 | **P1 measured** | "
          "P1 vs sparse | P1 vs dense HW | load_wght saved | compute added | raw worth it |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    breakeven = []
    for s, (_, x, y, ch, f) in SHAPES.items():
        for c in CONFIGS:
            for i in IACT_ZEROS:
                d = load(os.path.join(sweep_dense, f"{s}_z{i}_{c}.json"))
                if not d:
                    continue
                td, lwd = d["total_cycles"], ph(d["layers"][0], "load_wght")
                prev = None
                for w in WGHT_ZEROS:
                    a = prof.get(f"{s}_i{i}_w{w}_csc_{c}")
                    b = prof.get(f"{s}_i{i}_w{w}_dense_{c}") or (a if w == "0" else None)
                    if not (a and b):
                        continue
                    ts, lws = a["total_cycles"], ph(a, "load_wght")
                    saved = lws - lwd
                    added = ph(b, "compute") - ph(a, "compute")
                    p1_est, p1 = ts - saved, b["total_cycles"] - saved
                    worth = "yes" if saved > added else "**no**"
                    print(f"| {s} | {c} | {float(i) * 100:.0f} % | {float(w) * 100:.0f} % | {fmt(ts)} | {fmt(td)} | "
                          f"{fmt(p1_est)} | **{fmt(p1)}** | {pct(p1, ts)} | {pct(p1, td)} | {fmt(saved)} | "
                          f"{fmt(added)} | {worth} |")
                    margin = saved - added
                    if prev is not None and prev[1] > 0 >= margin:
                        w0, m0 = prev
                        breakeven.append((s, c, i, w0 + (float(w) - w0) * m0 / (m0 - margin)))
                    elif prev is None and margin <= 0:
                        breakeven.append((s, c, i, 0.0))
                    prev = (float(w), margin)
                if prev is not None and prev[1] > 0 and not any(b[:3] == (s, c, i) for b in breakeven):
                    breakeven.append((s, c, i, None))
    print()
    print("## Weight zero share above which the zero-compressed layout is better (load_wght saved = compute added)\n")
    print("| Layer | Config | input zeros | break-even weight zeros |")
    print("|---|---|---:|---:|")
    for s, c, i, w in breakeven:
        print(f"| {s} | {c} | {float(i) * 100:.0f} % | "
              f"{'above ' + str(int(float(WGHT_ZEROS[-1]) * 100)) + ' % (raw always better)' if w is None else f'{w * 100:.0f} %'} |")
    print()


def networks(groups):
    """groups: (title, sparse profile, dense HW profile, dense-layout sparse profile)."""
    print("## Whole networks: dense weight layout on the sparse PE (raw forced) against today\n")
    print("| Network | sparse today | dense HW | P1 step 1 estimate | dense layout run | **P1 measured** | "
          "P1 with the per-layer rule | P1 vs sparse | P1 vs dense HW | bit-exact |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    per_layer = []
    for title, sp, dp, lp, verdict in groups:
        s, d, l = load(sp), load(dp), load(lp)
        if not (s and d and l):
            print(f"| {title} | missing profile | | | | | | | | {verdict} |")
            continue
        ts, td, tl = s["total_cycles"], d["total_cycles"], l["total_cycles"]
        est = meas = rule = 0
        for k, (ls, ld, ll) in enumerate(zip(s["layers"], d["layers"], l["layers"])):
            saved = max(0, ph(ls, "load_wght") - ph(ld, "load_wght"))
            added = ph(ll, "compute") - ph(ls, "compute")
            est += saved
            meas += saved - added
            rule += max(saved - added, 0)
            info = ls.get("info", {})
            wz = ll.get("info", {}).get("weights", {})
            per_layer.append((title, k, info.get("name", "?"), wz, saved, added, ph(ls, "compute"),
                              ls["total_cycles"]))
        print(f"| {title} | {fmt(ts)} | {fmt(td)} | {fmt(ts - est)} | {fmt(tl)} | **{fmt(ts - meas)}** | "
              f"{fmt(ts - rule)} | {pct(ts - meas, ts)} | {pct(ts - meas, td)} | {verdict} |")
    print()
    print("## Per layer (layers with a weight load difference)\n")
    print("| Network | Layer | weight zeros | load_wght saved | compute added (dense layout) | added / compute | "
          "raw worth it |")
    print("|---|---|---:|---:|---:|---:|---|")
    for title, k, name, wz, saved, added, comp, total in per_layer:
        if not saved and not added:
            continue
        share = f"{100.0 * wz['zeros'] / wz['values']:.1f} %".replace(".", ",") if wz.get("values") else "-"
        rel = f"{100.0 * added / comp:+.1f} %".replace(".", ",") if comp else "-"
        print(f"| {title} | {k} {name} | {share} | {fmt(saved)} | {fmt(added)} | {rel} | "
              f"{'yes' if saved > added else '**no**'} |")
    print()


def main():
    mode = sys.argv[1]
    if mode == "single":
        single(sys.argv[2], sys.argv[3])
    elif mode == "networks":
        # networks MNIST_SPARSE_DIR MNIST_DENSE_DIR MNIST_LAYOUT_DIR T2_SPARSE T2_DENSE T2_LAYOUT T2R_SPARSE T2R_LAYOUT
        ms, md, ml, ts, td, tl, rs, rl = sys.argv[2:10]
        groups = []
        for act, title in (("relu", "MNIST ReLU"), ("leaky_relu", "MNIST Leaky ReLU"), ("silu", "MNIST SiLU"),
                           ("hardswish", "MNIST hard-swish")):
            st = load(os.path.join(ml, "status.json")) or {}
            groups.append((title, os.path.join(ms, f"trained_{act}_img0_sparse.json"),
                           os.path.join(md, f"trained_{act}_img0_dense.json"),
                           os.path.join(ml, f"trained_{act}_img0_sparse.json"), st.get(act, "?")))
        for sdir, ldir, tag in ((rs, rl, "ReLU"), (ts, tl, "no act.")):
            st = load(os.path.join(ldir, "status.json")) or {}
            names = sorted(f[:-5] for f in os.listdir(ldir) if f.startswith("paper_") and f.endswith(".json"))
            for name in names:
                groups.append((f"Table 2 {name[6:]} {tag}", os.path.join(sdir, f"{name}.json"),
                               os.path.join(td, f"{name}.json"), os.path.join(ldir, f"{name}.json"),
                               st.get(name, st.get(name[6:], "?"))))
        networks(groups)


if __name__ == "__main__":
    main()
