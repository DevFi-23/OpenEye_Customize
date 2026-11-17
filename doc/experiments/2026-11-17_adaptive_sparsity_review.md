# 2026-11-17: "Adaptive Sparsity" (choose sparse or dense per layer from its zero density), evaluation only

Proposal (user, 2026-11-17): measure the zero share of the weights and activations of each layer, estimate the cycles of
both modes including the load and decode overhead, pick the faster one, configure the accelerator per layer; research
point: the density at which sparse really beats dense. Example: Conv1 10 % zeros -> dense, Conv2 65 % -> sparse, Conv3
35 % -> depends, FC1 80 % -> sparse. No RTL or Python was changed for this note.

It is the per-layer mode of `2026-11-17_per_layer_mode.md` with an automatic rule. The measurements now cover two
networks in both modes: the trained MNIST net (`doc/perf/activation_2026-11-12_rounding`) and the Table 2 network on 16
configurations with and without ReLU (`2026-11-17_paper_dense_sparse.md`).

## 1. What decides sparse against dense on this hardware

| Layer (zeros in its input) | Sparse / dense, cycles of the layer | Winner |
|---|---|---|
| MNIST Conv1 (image, 0 %) | 32,619 / 32,246 | dense (−1.1 %) |
| MNIST Conv2 (43.5 %) | 112,010 / 114,380 | sparse (−2.1 %) |
| MNIST Conv3 (87.3 %) | 52,754 / 59,788 | sparse (−11.8 %) |
| MNIST Dense 3136 -> 10 (74.3 %) | 13,107 / 10,733 | **dense** (−18 %) |
| Table 2 Conv2, ReLU (10.7 %), 16 configurations | 718,165 / 696,587 | dense |
| Table 2 Conv3, ReLU (53.3 %), CR 1-2 / CR 4-8 | sparse wins / dense wins | **depends on the configuration** |
| Table 2 Dense 1568 -> 32, ReLU (85.4 %) | 222,729 / 185,159 | **dense** (−17 %) |

* The difference between the modes is mostly the **weight format**, not the decoding of activations: sparse sends
  12-bit weights (24 bits per router and MAC pair, 5 DMA words per weight row at 12 routers) where dense sends 8 bits
  (3 words): `load_wght` −33 to −40 % in dense, in every layer. Sparse gains only in `compute`, in proportion to the
  activation zeros (Table 2 ReLU: Conv3 −19 %, Dense −32 % compute).
* A fully connected layer uses every weight once, so its time is weight load: it prefers dense even with 74-85 % zero
  activations. The example "FC1 80 % -> sparse" is the wrong way round here.
* The crossover is not one density. It moves with the share of compute in the layer: the same Conv3 (53 %) prefers
  sparse at CR 1-2 and dense at CR 4-8, because more cluster rows shorten the compute and leave the weight load.
  Weight zeros barely matter: trained weights have 1-5 %.

## 2. What it would gain

| Network | Best single mode | Best mode per layer | Gain |
|---|---|---|---:|
| MNIST, ReLU | sparse 218,564 | 215,817 | −1.26 % |
| MNIST, Leaky ReLU / SiLU / hard-swish | dense | = dense | 0 |
| Table 2, no activation (16 configurations) | dense | = dense | 0 |
| Table 2, ReLU, CR 1-2 | dense or sparse | | −0.8 to −1.5 % |
| Table 2, ReLU, CR 4-8 | dense | = dense | 0 |

## 3. What it would cost

* A per-layer status bit, and a PE that runs both datapaths: today a generate keeps one FSM; both in each of the 48
  PEs is about +100-200 LUT per PE, +8-16 % of the chip (Yosys, `2026-11-11_mixed_mode/pe_area.sh`), plus muxes on the
  SPad and psum address paths. Dense hardware is 26.9 % smaller than sparse, so a dual build gives up most of that.
* The weight path must carry the wide sparse format for the sparse layers, so the dense layers would not get their
  bandwidth saving unless the weight packing is also switched per layer (the postponed mixed mode, per layer).
* Measuring the zeros on chip before a layer costs a pass over the iact buffer; the decision belongs in the toolchain
  (calibration images, as the quantization scales) with a cost model, not in the hardware.

## 4. Assessment

The premise (sparse is not always faster) is right and the measurements confirm it, but on this accelerator the deciding
quantity is the weight-load share of the layer, not the activation density alone, and the possible gain on the two
networks measured is 0-1.5 % for +8-16 % LUT. Not worth the hardware now.

The research point is worth doing as a measurement study, without RTL changes:
1. a test hook for a controlled zero share of the activations (`DRAMContents` today only zeros a fixed checkerboard,
   `USE_SPARSE_IACTS`), a small Python change in the testbench data generator (needs approval);
2. sweep the zero share 0-90 % for a few layer shapes (3 x 3 conv with few / many channels, 1 x 1, fully connected) at
   CR 1 / 2 / 4 / 8 in both modes, cycles per phase from the profiler -> crossover curves;
3. a cost model in Python (load words of both formats, compute ~ non-zero MACs, measured overheads) checked against the
   64 Table 2 profiles and the 16 MNIST profiles; it would also tell when a larger network would make per-layer modes pay.
