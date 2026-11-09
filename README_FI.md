# README_FI: Nhật ký và hướng dẫn cho dự án riêng (DevFi-23)

File này tóm tắt **mọi thứ đã làm** trên bản OpenEye riêng này, giải thích các khái niệm hay dùng,
và hướng dẫn cách làm việc. Mỗi lần thêm thay đổi lớn, hãy cập nhật mục **Nhật ký** ở cuối file.

README.md gốc của OpenEye vẫn giữ nguyên: đó là tài liệu của nhóm phát triển gốc.

---

## 1. Mục tiêu

- Phát triển **dự án riêng** dựa trên [OpenEye](https://github.com/Learning-Chips-Lab/OpenEye),
  một bộ tăng tốc DNN mã nguồn mở (INT8, dataflow kiểu Eyeriss v2, chạy trên FPGA và ASIC).
- Hướng nghiên cứu: **tối ưu bộ tăng tốc theo băng thông (DMA) và độ trễ (latency)**.
- Không gửi thay đổi ngược lên repo gốc. Chỉ định kỳ kiểm tra repo gốc để so sánh và lấy về những sửa đổi có ích.

## 2. Repo, remote và branch

| Tên | Trỏ tới | Vai trò |
|---|---|---|
| remote `upstream` | `github.com/Learning-Chips-Lab/OpenEye` | Repo gốc, **chỉ đọc** (fetch) |
| remote `origin` | [`github.com/DevFi-23/OpenEye`](https://github.com/DevFi-23/OpenEye) (private) | Repo của bạn, nơi push mọi thay đổi. Branch mặc định: `dev` |
| branch `main` | bản sao của `upstream/main` | Không commit vào đây; dùng để so sánh |
| branch `dev` | `main` cộng các thay đổi của bạn | **Branch làm việc chính** |

Định kỳ kiểm tra repo gốc:

```bash
git fetch upstream
git log --oneline dev..upstream/main          # upstream có commit gì mà dev chưa có
git diff dev upstream/main --stat             # khác nhau ở những file nào
git branch -f main upstream/main              # cập nhật main local (main không có commit riêng)
git push origin main                          # đồng bộ main lên GitHub của bạn
git checkout dev && git merge upstream/main   # lấy thay đổi của upstream vào dev (khi muốn)
```

Đưa thay đổi local lên GitHub:

```bash
git checkout dev
git add <file> && git commit -m "..."
git push origin dev
```

### Trạng thái các commit của upstream (cập nhật 2026-11-06, `upstream/main` = `b1e02a0`)

`dev` dựa trên upstream `c4bd562`. Từ đó upstream có 22 commit không phải merge (12–29/10/2026). Bảng dưới gộp mọi lần kiểm tra
(2026-10-19, 21, 24, 30, 31); chi tiết và cách chạy lại: `doc/experiments/2026-10-21_upstream_cherry_pick.md`,
`doc/experiments/2026-10-31_upstream_review.md` (chạy upstream nguyên bản trong worktree, so với `dev` cùng bộ chạy),
`doc/experiments/2026-10-31_upstream_551cf85_iact.md`, `doc/experiments/2026-10-31_wght_send_end.md`, `doc/experiments/2026-11-04_upstream_36395dd.md`
(2 commit mới ngày 03/11), `doc/experiments/2026-11-06_upstream_dw_review.md` (5 commit ngày 05/11, depthwise).

| Commit (ngày) | Nội dung | So với `dev` | Trạng thái |
|---|---|---|---|
| `b6fa369` (12/10) | Comment `TRANS_WORDS` trong `OpenEye_FPGA.v` | Chỉ comment | **Đã lấy** 2026-10-21 (`0cacda1`) |
| `2c8c324` (12/10) | `OpenEye_Parallel.v`: 4 khối generate của router psum đặt nhầm tên `gen_router_iact_*` → `gen_router_psum_*` | Chỉ đổi tên hierarchy | **Đã lấy** 2026-10-21 (`22614d2`) |
| `2bf497d` (15/10) | `PE.v`: `first_spad_words_wght` 5 → 7 bit, `filters_reg_M0` 6 → 8 bit | = lỗi #11 phần `PE.v:2210` (tiềm ẩn: giá trị lớn nhất đo được 13) | **Đã lấy** 2026-10-21 (`9c0c8dc`) + mở rộng 0 tường minh (`f337693`) |
| `fc9ace3` (12/10) | `test/cocotb_fpga/Makefile`: đổi cấu hình mặc định khi chạy bằng `make` | Fork chạy test qua pytest, không dùng Makefile | Không lấy (không ảnh hưởng) |
| `18772d6` (15/10) | `rtl_test_utils.py`: tắt các `assert` của bộ kiểm tra ghi FC "live" ("For Claude to rewrite") | Đúng nguyên nhân của #5 (báo động giả); `dev` tắt bằng `OPENEYE_SKIP_FC_WRITE_CHECK=1` và giữ bộ kiểm tra | Không lấy. Ý tưởng đáng giữ: viết lại bộ kiểm tra để so RAM sau khi ghi xong |
| `240bc35`, `28415e5` (16/10) | Giá trị test (`test_nets` CR 8 → 4; `test_conv_input_mapping` thêm 2 và 3 channel) | Chỉ test; 3 channel sai trên cả hai cây (#7) | Không lấy |
| `81173dc` (20/10), merge `4daa41e` | `hdl/config/regmap.yaml` giống `test/cocotb_fpga/regmap.yaml` | Toolchain không đọc bản `hdl/config`; bản `test/` của `dev` có thêm trường (`quant_clamp_low`) | Không lấy (vô hại) |
| `c48899f` (21/10) | `psum_pipeline.v`: mọi phép gán `results_ready` thành blocking `=` | Cách sửa #14 của upstream, **ngược hướng** với `dev` (`3717d12`, xem dưới) | Không lấy |
| `e78e5b7` (21/10) | `OpenEye_FPGA.v`: xoá `temp_var = 0;` nằm ngoài `if (!rst_n) ... else` của một khối reset bất đồng bộ | Không đổi chức năng, làm sạch mẫu reset | **Đã lấy** 2026-10-31 (`5595d15`, được bạn đồng ý). Kiểm chứng: hồi quy 162 test 157 PASS + 5 xfail như cũ, 12 ca mốc và 16 cấu hình Bảng 3 0 chu kỳ lệch, lint `fpga` 462 → 461, Vivado: netlist giống hệt (mục 9) |
| `3ba44e3` (23/10) | Bỏ một kiểm tra cũ trong test của bộ sinh tài liệu | Không liên quan | Không lấy |
| `2dde2db` (26/10) | Unit testbench: bỏ cổng `fc_size_i`, tham số `TRANS_BITWIDTH_WGHT` của `hdl/debug/PE_IO_debug.v` | Fork không chạy các testbench này | Không lấy |
| `551cf85` (27/10) | `iact_stream_constructor.v` về đúng bản trước `23be043` (giống từng byte `f84f064`, có đường FC riêng) | Sửa #6, #7 như `dev`, nhưng **mang lại lỗi #13** (bộ đếm vòng đọc bị lái từ 2 khối, Vivado giữ 0), sai Conv 8 channel `NUM_GLB_IACT=3`, không nhanh hơn | **Không lấy**, đã so sánh chi tiết (mục dưới) |
| `c342d04` (27/10), merge `b4b643a` | DAG: `DRAMContents`, tham chiếu, testbench theo tên layer; ca `Residual_Block` | Viết lại `DRAM.py`, `test_utils_main.py`, testbench: xung đột lớn với mô hình DRAM, profiler, đường lượng tử của `dev` | Chưa lấy. **Đáng xem** khi làm mạng có nhánh (residual) |
| `3258813` (27/10) | Xếp weight conv nhiều channel/thưa: xoá khoá `used_wght_per_PE` lặp; giữ word weight 0 khi nhiều lượt gửi; `OpenEye_FPGA.v` kết thúc gửi weight ở `wghts_per_pe + 1` thay vì `+ 2` | Hai phần đầu = #18 và một phần #22 (đã có trong `dev`) | Hai phần đầu: không cần. Dòng `+ 1`: **đã thử 2026-10-31** (được bạn đồng ý, `doc/experiments/2026-10-31_wght_send_end.md`): đúng ở mọi kiểm tra (162 test, 12 ca mốc, model đã huấn luyện 4 ảnh, Bảng 3 13/16 như `dev`), −0,1 đến −0,3 % chu kỳ (−673 trên model MNIST), 0 tài nguyên. **Đã đưa vào `dev` 2026-11-01** (được bạn đồng ý, mục 9) |
| `80d6e67` (27/10), `d1da389` (28/10) | Luồng Verilator; `router_iact.v` bỏ đường e12 (cổng 1 → 2) để hết vòng tổ hợp của Verilator | Đổi cách định tuyến; `dev` mô phỏng bằng Icarus, Vivado không báo vòng | Không lấy. Xem lại nếu chuyển sang Verilator |
| `655a2ae` (28/10) | Nới độ rộng trường/bộ đếm cho mạng lớn (`iact_read/write_limit_*` 18 bit, vòng psum 12/24 bit), CC ≠ 2 | Không sửa lỗi nào của `dev`: không model nào của ta tràn trường (`field_overflow*.py`). 2026-11-03: không động tới bộ đệm weight, điều kiện ready hay thanh ghi đọc ra, nên **không sửa #28, #29, #36**; #37 cũng không (trường rộng `BUFFER_WIDTH_IACT` bit = 12 với bộ đệm iact 4.096) | Chưa lấy. **Đáng xem** khi một layer vượt độ rộng trường hiện tại |
| `57781cd`, `c2bf7a9`, `93f0e82` (28–29/10) | Flatten trong DAG; `make_stream` song song rồi lại tuần tự (bản song song làm mất cập nhật `layer_params`); stream bộ đệm layer | Chỉ cho DAG; `make_stream` của `dev` vẫn tuần tự, có bản sửa `trans_cycles` | Không lấy |
| `9498271` (03/11) | Tham số mới `CYCLE_WIDTH`, `LIMIT_SIZE_*`; nới trường trạng thái (`needed_cycles` 32 bit, `iact_glb_writing_cycles` 24, các bước tăng iact và `iact_buffer_words_per_write` `BUFFER_WIDTH_IACT + 5 − log2(CLUSTERS)` bit…); bỏ trường `wght_cycles_reg` | **Sửa #37** (cùng `36395dd`; kiểm chứng 2026-11-04: Conv 14×14×32 → 32 ở CR 1 X 2 PASS, upstream cũ FAIL). Dựa trên tham số hoá `BUFFER_WIDTH_IACT` của `655a2ae` | Không lấy nguyên; **đã chép phần nới trường 2026-11-04** (hàng O, mục 9 "Sửa #37, #17"): 10 trường bộ đệm iact 13 bit = độ rộng địa chỉ bộ đệm của `dev` |
| `36395dd` (03/11) | Bộ đếm và cổng rộng theo `CYCLE_WIDTH`; **1 channel**: bỏ mọi đường riêng cho 1 channel trong `iact_stream_constructor.v`, `data_pipeline_iact.v` của PE quay vòng bộ đếm sub-word khi 1 channel mỗi PE và bỏ logic "uneven ending"; Python theo cấu trúc DAG (thêm chỉ số cho layer nhiều input), công thức `iact_read_inc_2` mới | **Sửa #17 trong RTL** (2026-11-04: Conv 28×28×1 không đệm PASS, upstream cũ và `dev` FAIL; thời gian mô phỏng ít hơn khoảng 5 % so với đệm channel của `dev`; đo bằng profiler sau khi chép: Conv1 MNIST −1,1 % chu kỳ). Vẫn sai 1 channel nhiều lượt weight (#39, lỗi Python chung, `dev` đã sửa). Vẫn còn #29, #36 và sai Dense 3136 → 10 (đúng ở `dev`); #7, #9, #21, #27 vẫn sai như `dev` | **Không gộp** (phụ thuộc DAG, constructor dòng `551cf85`, mang lại các lỗi `dev` đã sửa). **Đã chép phần 1 channel 2026-11-04** vào constructor của ta và tắt `channel_pad` (hàng O, mục 9 "Sửa #37, #17"); không lấy công thức `iact_read_inc_2` mới và việc bỏ bước nhảy `NUM_GLB_IACT − 1` (`dev` cần cho `NUM_GLB_IACT` 3) |
| `b10db82` (04/11) | "Re-Enabled python interface for DW Conv": conv depthwise (RTL `PE`, `PE_cluster`, `OpenEye_Cluster`, Python `dw_mapper.py`, `layer_parameters.py`, `wght_stream_mapper.py` sửa nhiều); nhánh nhiều filter của `LayerParameters` nâng từ 16 lên **32 psum mỗi PE** | Chỉ kiểm tra phần liên quan #39 (2026-11-05, `doc/experiments/2026-11-05_bug39_detail.md` mục 8): công thức số bộ weight vẫn cũ, nên **vẫn có #39** khi hơn 32 filter mỗi lần tính (8×4×1 → 96, 28×28×1 → 48 FAIL toàn bộ map); MNIST Conv1 (32 filter) thoát vì chỉ còn 1 lượt; vá công thức thì các ca đó treo: **đã tìm ra 2026-11-05** (`doc/experiments/2026-11-05_b10db82_hang.md`), không do 1 channel hay 32 psum mà do lượt weight cuối thiếu filter (96 = 64 + 32): mapper upstream ghi weight của filter đệm thành số 0 tường minh, `data_pipeline_wght.v` coi word toàn 0 là phần đệm stream, PE nhận 2 thay vì 3 con trỏ cột weight và không thoát vòng MAC = cơ chế **#22** (fork đã sửa, upstream chưa); chia chẵn (64 + 64, 32 + 32) PASS. Không vá thì FAIL do #39 cộng **#40** (cả fork cũng có); #39b còn nguyên. Phần depthwise: đánh giá 2026-11-06 cùng 5 commit sau (hàng dưới): DW 4×1×4, 12×2×8, 8×8×4 **sai** cả ở cấu hình của chính upstream | Chưa lấy |
| `e8b3c3e`, `2abe8d4`, `0d5a0e3`, `7465852`, `b1e02a0` (05/11) | `e8b3c3e` "Reimplemented Depthwise Convolution": DW chuyển vào FSM **dense** của PE (`dw_mode`), viết lại `get_pagu_values` / `calculate_pe_transmissions`, tham số mới `CHANNEL_CYCLE_WIDTH` (RTL 12, Python 16) nới `iact_channel_max_cycles` và trường regmap, sửa chỉ số x/y của tham chiếu DW, công tắc `WAVES` trong Makefile; `2abe8d4`, `0d5a0e3`: `iact_buffer_addr`, `quantized_value_reg` khai báo `wire` thay `reg` (được lái bằng `assign`); `7465852`: đánh số lại các vòng của bộ sinh địa chỉ đọc iact; `b1e02a0`: testbench PE reset `dw_mode` | Kiểm tra 2026-11-06 (`doc/experiments/2026-11-06_upstream_dw_review.md`): luồng Makefile của upstream (PE dense, Verilator 5.044): Conv 8×8×4 → 16 và 12×6×1 → 8 PASS, **giống hệt từng ns** trước và sau (viết lại PAGU không nhanh hơn); **DW sai ở cả 3 ca, trước và sau** (bản mới ra chủ yếu 0). Lỗi trong code: `rd_cycle_loop_cnt_4 <= rd_cycle_loop_cnt_4` (vòng 4 không bao giờ đếm), `rd_addr_inc_4_next` bị `assign` 2 lần (Yosys: nhiều driver), nhánh Python của DW chưa theo cách đánh số mới; việc nới `CHANNEL_CYCLE_WIDTH` làm dở (bộ đếm trong `psum_pipeline.v`, `router_configurator.v` vẫn 8 bit). Lint `fpga` 464 → 458 (5 mới, 11 cũ hết). Hai dòng `reg` → `wire`: đúng chuẩn Verilog, `dev` có đúng 2 khai báo đó, công cụ của ta chấp nhận | **Không lấy** (phụ thuộc `b10db82`; DW chưa xong và chỉ có ở PE dense, `dev` chạy sparse; PAGU có lỗi và xung đột với bước nhảy `NUM_GLB_IACT − 1`, `iact_read_inc_2` của `dev`). Có thể lấy riêng (cần bạn đồng ý vì là RTL): 2 dòng `reg` → `wire`, công tắc `WAVES`. Theo dõi tiếp DW (mạng kiểu MobileNet) |

Lỗi còn mở của `dev` chạy trên upstream `93f0e82` (2026-10-31): #7 (3 channel), #9, #19b, #21, #23, #27, #28, #29 **sai y như trên `dev`**
(#27 sai còn sớm hơn); upstream còn sai Dense 3136 → 10/16 (Dense của model MNIST đã huấn luyện) mà `dev` đúng, do lỗi #19 phần 2 (`current_x`
có dấu trong `OpenEye_FPGA.v`, đã sửa ở `dev` `10bcaf7`): với `551cf85`, K = 2032 đúng, K = 2064 sai. Upstream `93f0e82` vẫn có lỗi #13.
2026-11-07, lỗi #41 (stride 2) trên upstream `b1e02a0` (`doc/experiments/2026-11-07_bug41_stride.md` mục 4): cùng mặc định `STRIDE_ENABLED = 0` (tham số có từ upstream `2e3b351`, 16/09, đã nằm trong nền của `dev`), cùng lỗi (16/16 feature map sai); với `STRIDE_ENABLED=1` stream ra của RTL khớp stream tham chiếu nhưng testbench upstream giải mã giá trị lệch một hàng (lỗi testbench của upstream, bộ giải mã của `dev` đúng).
**Không commit nào nhắm tới băng thông DMA, độ trễ, hay lượng tử hoá** (`DRAM.py` vẫn `floor(127·w)`, bộ lượng tử RTL vẫn lấy 8 bit thấp).

**Commit đáng xem sau này:** `36395dd` + `9498271` (#17, #37 đã chép 2026-11-04; phần còn lại: tham số `CYCLE_WIDTH`, `LIMIT_SIZE_*`, bộ đếm 32 bit), `655a2ae` (mạng lớn hơn MNIST), `c342d04` (mạng residual), `d1da389` (nếu dùng Verilator), ý tưởng của
`18772d6` (bộ kiểm tra ghi FC sau khi ghi xong), depthwise của `b10db82` / `e8b3c3e` (khi chính test DW của upstream PASS). Dòng `+ 1` của `3258813` đã thử và đã đưa vào `dev` (2026-11-01, bảng trên).

### Hướng đi của upstream (phân tích 2026-10-24, bổ sung 2026-10-31)

Số commit của upstream theo tháng (từ 05/2026): 7/2026: 66 (DenLeb 40, Hendrik Woehrle 26), 8/2026: 10, 9/2026: 124 (Hendrik 80, DenLeb 44),
10/2026: 23 (DenLeb 15, Hendrik Woehrle 7, Barsch32 1; 15 trong số đó từ 21/10). Bốn giai đoạn:

| Giai đoạn | Commit tiêu biểu | Mục tiêu |
|---|---|---|
| 7–8/2026: **giảm diện tích (LUT)** để vừa FPGA nhỏ **GateMate A1** và gắn với SoC RISC-V | `1320759` "Reduced logic for smaller designs" (14/7: bỏ `router_wght_3P.v`, **comment-out các bộ đóng gói ghi ngược**, gồm cả nhánh FC), `24057c8` "Reduced LUTs further" (tách FSM psum ra `psum_pipeline.v`, thêm `router_configurator.v`), `3fbb272` "Optimized WGHT Stream", `8350a00` "Optimized PSUM Flow for LUT Efficiency" (ghi ngược dùng vòng đếm tổng quát thay cho mẫu đọc viết tay, **mất nhánh FC**), `9926af4` PE thưa/SISD, `6318f8c` stream lượng tử gọn hơn, `204704b` (7/8) "Reduced Amount of LUTs under the threshold for GateMate A1", `9a900cc` giao tiếp 32 bit cho RISC-V | Diện tích, tích hợp hệ thống |
| 7–9/2026: **chạy đúng lại** sau các lần viết lại | Hendrik Woehrle: ánh xạ activation conv, ghi ngược, pooling (15 commit), Dense/FC/GEMM, kernel lớn, stride, móc debug/trace (`TRACE_*`), sửa lint; `e8f39ad` thêm ca `MLP` (Dense 6→32→16→4, mặc định của Makefile), `7bdebb7` testbench đơn vị cho `data_pipeline_wght` + `doc/sparse_weight_encoding.md` | Chức năng |
| 10/2026 (tới 23/10): sửa nhỏ | `2bf497d` độ rộng bit (#11), `c48899f` `results_ready` (#14), `e78e5b7` mẫu reset, test `240bc35`/`28415e5`, đồng bộ `regmap.yaml` | Dọn dẹp |
| 26–29/10: **mở rộng** | `c342d04` DAG (mạng residual), `655a2ae` trường/bộ đếm rộng hơn cho mạng lớn, `80d6e67`/`d1da389` Verilator, `551cf85` và `3258813` sửa lại conv nhiều channel/thưa | Mạng lớn hơn, mô phỏng nhanh hơn; vẫn không có tối ưu DMA/độ trễ |

**Không commit nào nhắm tới băng thông DMA hay độ trễ** (không burst, không DMA rộng hơn, không gửi bias theo filter, không chồng nạp với tính).
Tối ưu của họ là diện tích, đôi khi đánh đổi chức năng: bỏ ghi ngược FC để giảm LUT chính là nguyên nhân gốc của lỗi #26 (mục 9).
Những thứ tham khảo được: (1) cơ chế "vòng lặp phần cứng" cấu hình bằng Python (`psum_pagu_*`, `iact_read/write_*`): rẻ về LUT và linh hoạt, cách sửa #26
đề xuất dùng lại đúng cơ chế này; (2) `doc/sparse_weight_encoding.md` và `test/cocotb_data_pipeline/test_data_pipeline_wght.py` (testbench đơn vị của
`data_pipeline_wght`; có một ca `xfail` "hàng weight rỗng không tăng địa chỉ SPad" = cơ chế F1 của lỗi #22, upstream biết nhưng chưa sửa); (3) số liệu
diện tích hướng GateMate nếu sau này cần FPGA nhỏ; (4) các móc trace đã dùng nhiều trong điều tra.

**Lỗi #14: upstream sửa ngược hướng với `dev`.** Gốc lỗi: thanh ghi `results_ready` vừa được gán non-blocking (`<=`: reset, chuyển trạng thái) vừa
được tích luỹ blocking (`results_ready = results_ready & (...)` trong `CALCULATE_PSUM`/`PSUM_GET_RESULTS`); mô phỏng và Vivado cho phép gán `<=`
thắng, Yosys cho phép gán `=` sau cùng thắng (netlist treo), Verilator báo lỗi `BLKANDNBLK`. Upstream (`c48899f`) đổi **4 phép gán còn lại thành
blocking** `=`: các công cụ hết bất đồng, diff nhỏ, nhưng thanh ghi trong khối tuần tự gán blocking (kiểu `BLKSEQ`) và giá trị lưu sau
`PSUM_GET_RESULTS` thành phép AND thay vì 1 (sau đó không ai đọc, nên tương đương về chức năng). `dev` (2026-10-19) làm **ngược lại**: tách phần tổ
hợp ra các dây (`chain_ready_terms`, `all_psum_ready`, `all_psum_enable`, `results_ready_calc`) và chỉ gán thanh ghi bằng `<=`: đúng mẫu thiết kế đồng bộ,
lockstep 125 test không lệch, netlist Yosys chạy đúng, lint −4 lỗi −3 cảnh báo, Vivado hết cảnh báo 8-6090. Lấy `c48899f` sẽ xung đột với bản của
`dev` mà không thêm gì, nên **không lấy**.

### `551cf85` so với `dev`: hướng nào tốt hơn (phân tích 2026-10-31, `doc/experiments/2026-10-31_upstream_551cf85_iact.md`)

- **Bản chất:** `551cf85` chỉ đổi `iact_stream_constructor.v`, và file sau commit **giống từng byte** bản `f84f064` (ngay trước `23be043`):
  một bản revert, không có code mới. Các thay đổi khác của `23be043` (`OpenEye_FPGA.v`, `OpenEye_Parallel.v`, Python) vẫn giữ.
- **"Đường FC riêng"** là cấu trúc của bản cũ: mỗi khối `always` tách `if (fully_connected_i) ... else <FSM conv>`. Phía ghi: FPGA báo
  `fc_storage_valid_i` cho từng cặp activation; các bộ đếm hàng PE / cặp / hàng cluster đi theo thứ tự của `DenseWghtStreamMapper`; chỉ
  cluster có `CLUSTER_ROW_ID` khớp mới lưu, vào bank `hàng PE % NUM_GLB_IACT`, mỗi bank một bộ đếm địa chỉ khi ít bank hơn hàng PE.
  Phía đọc: FSM 2 trạng thái riêng, đọc `channels` word cho mỗi hàng PE (đọc trước từng cặp vì RAM có 2 tầng đọc), lần lượt từng hàng
  khi ít bank. `23be043` bỏ đường này, cho FC đi qua bộ ghi của conv (xoay bank); `dev` giữ cấu trúc đó và sửa 4 lỗi (#13, #6, #7, #19,
  khoảng 40 dòng). Ở `dev`, cổng `fc_storage_valid_i` vẫn còn nhưng không được đọc.
- **Kết quả** (cùng bộ chạy, mỗi cây dùng RTL/testbench/Python của nó): 8 ca, `dev` đúng 8/8; `551cf85` đúng 6/8 (sai Conv 14×4×8 → 8 với
  `NUM_GLB_IACT=3`, lỗi có từ cây trước `23be043`, và FC 3136 → 10 do #19 phần 2 nằm ở `OpenEye_FPGA.v`); cha `2dde2db` đúng 3/8. Chu kỳ
  bằng nhau ở mọi ca cùng đúng, trừ Conv 4 channel `NUM_GLB_IACT=3` (`dev` nhanh hơn 23 chu kỳ, 1,4 %); đường FC riêng không nhanh hơn
  (FC 256/512/1024 cùng tổng chu kỳ).
- **Lỗi #13 quay lại:** ở bản cũ, `rd_cycle_loop_cnt_0..3` được đếm ở khối đọc nhưng reset ở khối ghi; Yosys báo "multiple conflicting
  drivers"; Vivado sẽ giữ các bộ đếm ở 0 như trước bản sửa `5f1e66e` (6/9 ca mốc sai trên FPGA, mô phỏng không thấy). Upstream HEAD còn lỗi này.
- **Tài nguyên** (Yosys, module riêng, cấu hình mốc): bản cũ +5–11 % LUT, −3–6 % FF, nhưng netlist của nó không hợp lệ (bộ đếm nhiều nguồn
  lái) nên chỉ để tham khảo. Mỗi instance của `dev` trên Vivado: khoảng 540–565 LUT, 370 FF, 4 instance ≈ 3,7 % thiết kế.
- **Kết luận: hướng của `dev` tốt hơn** (đúng hơn, không có lỗi phần cứng ẩn, nhanh bằng hoặc hơn, thay đổi nhỏ có test cho từng lỗi).
  Không lấy `551cf85`. Ý tưởng tách FC khỏi conv tự nó hợp lý, nhưng ở đây không cho lợi chu kỳ.

## 3. Môi trường và cách chạy

- Python venv: `venv/` (Python 3.10, cocotb 2.0.1, TensorFlow). Kích hoạt bằng `source venv/bin/activate`.
- Simulator: Icarus Verilog 11.
- Chạy test cocotb trong `test/cocotb_fpga`. Luôn đặt `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` để tránh plugin
  `pytest-rerunfailures` mở socket không cần thiết.

```bash
cd test/cocotb_fpga
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../../venv/bin/python -m pytest test_profile.py -q -p no:cacheprovider
```

Mẹo:
- Khi phát triển, dùng `QUANT_AMOUNT=32`: mỗi test chỉ mất khoảng 15 giây, so với khoảng 4 phút khi `QUANT_AMOUNT=1024` (xem mục 5.6).
- Kết quả simulation nằm ở `test/.temp/<tên test>/` (log `cocotb_sim.log`, `profile.json`, file tham chiếu `demo/`).
- `/tmp` bị xoá khi WSL khởi động lại. Thứ gì cần giữ thì phải nằm trong repo.
- Verilator 5.020 (đúng phiên bản CI dùng) đã được build từ source vào `~/tools/verilator-5.020`
  (công cụ build lấy qua micromamba ở `~/tools/vbuild`, không cần sudo). Lint giống CI: `tools/lint_check.py` (mục 9c).
- Verilator 5.044 (micromamba, `~/tools/verilator-5.044`, 2026-11-06) chỉ để chạy luồng Makefile cocotb của upstream (cocotb 2.0.1 cần ≥ 5.036);
  lint vẫn dùng 5.020. Cách chạy: `doc/experiments/2026-11-06_upstream_dw_review/mkv.sh`.
- Yosys 0.69 (micromamba, `~/tools/yosys/bin/yosys`) để ước lượng tài nguyên nhanh; Vivado 2024.2 chạy trên Windows (mục 6d).

## 3b. Một lần mô phỏng chạy những gì (Python và RTL)

Một test (ví dụ một case của `test_profile.py`) chạy qua 3 giai đoạn. **Python làm phần lớn công việc**: đóng vai host (CPU + DDR + AXI DMA),
mô hình tham chiếu và dụng cụ đo. **Chỉ RTL là "phần cứng"**: mọi phép tính của bộ tăng tốc và mọi số chu kỳ đều do RTL tạo ra.
Không có bước "dạy" (huấn luyện) nào trong mô phỏng: OpenEye chỉ làm suy luận (inference). Weight là ngẫu nhiên, hằng số hoặc dạng dốc do testbench
tạo; hoặc weight Conv của model MNIST int8 đã huấn luyện có sẵn trong repo (`OPENEYE_TFLITE_CONV`, từ 2026-10-24); hoặc, từ 2026-10-30, **cả model PyTorch
MNIST đã huấn luyện sẵn** (`doc/demo_notebooks/mnist_unquantized_model.pth`) đi qua đường toolchain (`USE_RANDOM_VALUES=0`, `OPENEYE_MODEL_WEIGHTS`), với
input là ảnh test MNIST thật (`OPENEYE_INPUT_IMAGE`, mục 8d); từ 2026-11-02 cả các biến thể Leaky ReLU / SiLU / hard-swish
(`doc/demo_notebooks/mnist_<hàm>_model.pth`, tạo bằng `models/train_mnist.py`, mục 6.15).

```
A. Trước khi chạy simulator (pytest, Python thuần)
   test_profile.py → test_conv_const._run_conv_const
     ├─ đặt biến môi trường: cấu hình phần cứng (CLUSTER_ROWS, DMA_BITWIDTH, ...) và layer (kích thước, số filter, ...)
     ├─ vh_file_creator → parameters_FPGA.vh, parameters_PE.vh, parameters_PE_cluster.vh   (tham số RTL lúc biên dịch)
     ├─ generator (regmap.yaml) → regmap_params.vh, dma_storage.v
     └─ cocotb_test: iverilog biên dịch hdl/*.v + header → OpenEye_FPGA.vvp, rồi chạy vvp có nhúng Python (cocotb)

B. Trong lúc mô phỏng (Python và RTL chạy cùng một tiến trình, đồng bộ theo từng cạnh clock)
   OpenEye_FPGA_tb.py
     ├─ chuẩn bị dữ liệu (tốn 0 chu kỳ mô phỏng):
     │    TensorFlow tạo layer (data_create) → DRAM.py giữ input, weight, bias (có thể thay bằng hằng/ramp,
     │      hoặc weight Conv đã huấn luyện từ TFLite: OPENEYE_TFLITE_CONV;
     │      model thật: USE_RANDOM_VALUES=0 → onnx2model (lượng tử tĩnh) thay cho data_create)
     │    layer_parameters.py tính tham số layer → các word cấu hình
     │    channel_pad: chỉ khi OPENEYE_PAD_CHANNELS=1 (workaround cũ của lỗi #17, RTL đã sửa 2026-11-04)
     │    test_utils_main.collect_results / make_ref: MÔ HÌNH THAM CHIẾU tính kết quả đúng bằng Python
     │    test_utils_main.write_stream + *_mapper.py: đóng gói stream DMA (cấu hình → iact → weight → bias → quant
     │      → bảng hàm kích hoạt nếu layer dùng bảng);
     │      weight Conv mã hoá bỏ số 0 bằng conv_wght_encoding (lỗi #22)
     ├─ các coroutine chạy song song với RTL:
     │    Clock, reset
     │    send_stream (hoặc send_words_through_memory khi bật mô hình bộ nhớ): mỗi chu kỳ đặt data_dma_i / enable_dma_i, xem ready_dma_o
     │    profile_dma_phases: mỗi cạnh clock đọc trạng thái FSM (và dây act_capture), đếm chu kỳ/word → profile.json
     │      (chỉ quan sát, không làm đổi chu kỳ)
     │    probe_fsm_states: phát hiện treo;  trace_dma_input (tuỳ chọn)
     │    compare_stream_Conv/Dense/...: nhận data_dma_o (ready_dma_i do testbench hoặc WriteChannel quyết định), so với tham chiếu
     └─ assert → PASS/FAIL

C. Sau mô phỏng (Python thuần)
     run_profile.py gom profile.json → profile_report (bảng, --compare); check_dma_trace.py, decode_iact_read_loops.py khi cần
```

## 3c. Cách chạy các mô phỏng và test (tổng hợp, cập nhật 2026-11-02)

Mọi lệnh chạy từ **thư mục gốc repo** (`cd ~/OpenEye_orig`) với `venv/bin/python`; cần `iverilog` trong `PATH`. Mỗi test cocotb để kết quả ở
`test/.temp/<tên test>/`: `cocotb_sim.log`, `profile.json` (nếu bật profiler), `verify_layer0.pkl` (nếu bật kiểm tra độc lập), `demo/` (stream và tham chiếu).
Một test cocotb là một tiến trình; máy 12 nhân / 7 GB RAM chạy song song được khoảng 6–8 test.

### Unit test Python (không mô phỏng RTL, khoảng 15 giây)

```bash
venv/bin/python -m pytest -q test/test_*.py
```

Hiện tại (2026-11-08): **474 pass, 11 fail** (15 test tham số stride trong `test_stride_params.py` + 56 test phép kiểm tra nhóm A của mục 8e trong `test_model_guards.py` + 5 test bộ đệm weight / iact của #29 / #37, `test_wght_buffer.py` + 8 test số bộ weight và 32 test phép kiểm tra `check_wght_sets` của #39, 34 test phép kiểm tra `check_full_passes` của #40, `test_channel_pad.py` + 129 + 110 test mô hình ghi ngược FC của lỗi #26 + 12 test ghi ngược Conv của lỗi #25 + 11 test kẹp int8 + 6 test đường model thật so với ONNX Runtime + 22 test thứ tự stream bias của lỗi #32 + 31 test hàm kích hoạt, bước A và B + 3 test profiler hàm kích hoạt, bước C; 12 trong số đó cần checkpoint của `models/train_mnist.py`, không có thì skip). 11 fail đều ở `test/test_dense_output.py`, có từ trước (dùng `SimpleNamespace` thiếu `output_cycles`), không liên quan các
thay đổi của fork. Các file của fork: `test_profile_report.py`, `test_profile_phases.py`, `test_channel_pad.py`, `test_conv_wght_encoding.py`, `test_paper_table3.py`,
`test_memory_model.py`, `test_fc_writeback.py`, `test_conv_writeback.py`, `test_int8_clamp.py`, `test_onnx_model_flow.py` (cần `torch`, `onnxruntime`, file `.pth` đã huấn luyện),
`test_psum_bias_order.py`, `test_activation.py`, `test_model_guards.py` (56 test, các phép kiểm tra nhóm A của mục 8e, cần `torch`, `onnxruntime`), `test_stride_params.py` (15 test, #41b/#41d).

### Test mô phỏng RTL (cocotb qua pytest)

```bash
cd test/cocotb_fpga
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../../venv/bin/python -m pytest -q -p no:cacheprovider test_mnist_layers.py -k trained
```

| Bộ test | Chọn bằng | Nội dung | Thời gian mỗi test | Kết quả mong đợi (cập nhật 2026-11-03) |
|---|---|---|---:|---|
| `test_conv_const.py` | (cả file) | 36 layer Conv nhỏ, weight hằng số, nhiều cấu hình; `test_conv_bias_order`: 2 và 4 filter tính cùng lúc với bias khác nhau (#32) | 10 s – 6 phút | 36 PASS |
| `test_mnist_layers.py` | `-k mapping` | Quét 1/2/3/4/8 channel × `NUM_GLB_IACT` 1, 3 | ~30 s | 8 PASS, 2 xfail (3 channel, lỗi #7) |
| | `-k "test_mnist_conv"` | Conv1/2/3 MNIST thật (ramp) và Conv1 khi bật đệm channel cũ (`test_mnist_conv1_with_padding`) | 2–7 phút | Conv1 (1 channel thật, từ bản sửa #17), Conv1 có đệm, Conv2 PASS; Conv3 xfail (#9) |
| | `-k random` | 10 layer dữ liệu ngẫu nhiên (weight có 1–5 % số 0; 1 channel rộng 20/28/40 và 8×4×1 → 64 của #39) + kiểm tra độc lập từng word | 0,5–8 phút | 10 PASS |
| | `-k trained` | Conv1/2/3 MNIST với **weight int8 đã huấn luyện** (TFLite) + kiểm tra độc lập | 4–7 phút | Conv1, Conv2 PASS; Conv3 xfail (#9, mọi giá trị đúng) |
| `test_conv3x3_sparse.py` | id cụ thể | iact và weight thưa dạng bàn cờ, `NUM_GLB_IACT=3` (96 cấu hình, phần lớn chưa từng chạy) | ~6 phút | `[3-4-3-2-1-4-1-32-3-3-1-8]` PASS; `[3-4-3-2-1-8-4-32-3-3-1-16]` FAIL (#23) |
| `test_dense_chain.py` | (cả file) | 11 chuỗi Dense → Dense trên chip (lỗi #26): K 16–1568, N 8–64, MLP, `CLUSTER_ROWS` 1/2/4, `NUM_GLB_IACT` 3, `NUM_GLB_PSUM` 2 | 20 s – 1,5 phút | 11 PASS |
| `test_glb_psum2.py` | (cả file) | 7 mô hình nối layer với `NUM_GLB_PSUM=2` (lỗi #25): Conv đơn, Conv → Conv (4/16 channel, hàng 14 pixel), Conv → Pool → Conv (rộng 8, 6), Conv → Pool → Conv → Pool → Conv | 15–50 s | 7 PASS |
| `test_int8_clamp.py` | (cả file) | 9 mô hình kiểm kẹp int8 và ReLU gộp (#30): tràn (`OPENEYE_QUANT_SHIFT`), ReLU (hậu tố `_RELU`), cả hai; Conv → Conv, Conv → Pool → Conv, chuỗi Dense, MLP, `NUM_GLB_PSUM=2`, mạng paper có ReLU | 15 s – 3 phút | 9 PASS |
| `test_real_model.py` | (cả file) | Model PyTorch MNIST đã huấn luyện đi trọn đường toolchain (`onnx2model` lượng tử tĩnh → `LayerParameters` → `DRAMContents` → RTL), ảnh test 0 và 1 (mục 8d) | ~11 phút (~36 phút khi chạy 6 song song) | 2 PASS (trọn model khớp từng bit, lớp 7 và 2 = nhãn); `test_real_model_activation`: 3 biến thể Leaky ReLU / SiLU / hard-swish × ảnh 0, 1, 6 PASS (cần checkpoint của `models/train_mnist.py`) |
| `test_pooling.py` | (cả file) | Conv → max-pool 2×2 → Conv, input rộng 8 / 6, cao 2 / 4 (dốc) | ~6 phút | 4 PASS |
| `test_nets.py` | (cả file) | Model MNIST nhỏ (Keras ngẫu nhiên) qua `data_create` | ~40 s | 1 PASS |
| `test_stride.py` | (cả file) | Conv stride 2 với RTL dựng `STRIDE_ENABLED=1` (#41b–#41d): 6 layer đơn (rộng 4, 7, 8, 12, 24; `NUM_GLB_PSUM` 2), 2 Conv nối tiếp (8×8, 14×8, 16×14), Conv → Pool → Conv 28×28, Conv → Dense (8×8, 16×14) | 17–45 s | 12 PASS (trên `69320ba`: 10 FAIL) |
| `test_quant_mantissa.py` | (cả file) | Mantissa hệ số lượng tử 17 và 24 bit (#38): Conv → Conv, Dense → Dense (móc `OPENEYE_QUANT_MANT`) | 25–45 s | 3 PASS (trước bản sửa: 3 FAIL) |
| `test_cluster_rows1.py` | (cả file) | `CLUSTER_ROWS=1`: Dense 32 → 10 ở X 2 (#36), Dense 1568 → 32 → 10 ở X 4 và X 2 (#29, #36), mạng paper CR 1 X 2 Y 3 (#28, #29, #36), Conv 14×14×32 → 32 ở X 2 (#37, 4.096 word bộ đệm iact mỗi lượt) | 20 s – 4 phút | 5 PASS (trước các bản sửa: 5 FAIL) |
| `test_empty_pass.py` | (cả file) | Lượt không có activation khác 0 (lỗi #31): Conv lượt rỗng đầu, lượt rỗng giữa, Dense 1024 → 10 có khối input 0 (`OPENEYE_ZERO_BLOCK`) | ~40 s | 3 PASS (RTL trước bản sửa: 3 FAIL) |
| `test/cocotb_quantization/test_quantization_unit.py` | (cả file) | Testbench riêng của `quantization_unit` (30.470 output mỗi test so với mô hình Python, psum 20 và 32 bit; kẹp, Leaky ReLU, làm tròn) | ~3 s | 2 PASS |
| `test/cocotb_activation_table/test_activation_table.py` | (cả file) | Testbench riêng của `activation_table` (bảng 256 ô, nạp/đọc/nạp lại, word DMA 32/64/128 bit) | ~1 s | 3 PASS |
| `test_activation_rtl.py` | (cả file) | Hàm kích hoạt trên RTL (bước B): Leaky ReLU, bảng ngẫu nhiên / SiLU / hard-swish, làm tròn, giữ bảng; Conv → Conv, Conv → Pool → Conv, chuỗi Dense, MLP, `NUM_GLB_PSUM=2`, DMA 32 bit, mạng paper (móc `OPENEYE_ACTIVATION`) | 20 s – 4 phút | 12 PASS |
| `test_gemm_layer.py` | (cả file) | 63 test GEMM/Dense | vài phút | 40 PASS, 23 FAIL do bộ kiểm tra ghi FC "live" (#5, báo động giả); với `OPENEYE_SKIP_FC_WRITE_CHECK=1`: 63 PASS (đo 2026-10-19) |

Chạy nhiều test song song (mỗi test một tiến trình), ví dụ cả `test_conv_const.py`:

```bash
venv/bin/python -m pytest --collect-only -q test/cocotb_fpga/test_conv_const.py | grep "::" > ids.txt
xargs -P 8 -I{} sh -c 'venv/bin/python -m pytest -q "{}" | tail -1' < ids.txt
```

**Bộ hồi quy RTL đầy đủ hiện tại (2026-11-08): 201 test** = 189 test dưới đây + `test_stride` 12; chạy bằng `doc/experiments/2026-11-07_bug41_stride/regression.sh <thư mục>`; kết quả: **197 PASS + 4 xfail đã biết**. Trước đó (2026-11-04, sau hàng O): 189 test = `test_conv_const` 36, `test_mnist_layers` 27, `test_gemm_layer` 63 (với
`OPENEYE_SKIP_FC_WRITE_CHECK=1`), `test_pooling` 4, `test_nets` 1, `test_dense_chain` 11, `test_glb_psum2` 7, `test_int8_clamp` 9, `test_empty_pass` 3,
`test_activation_rtl` 12, `test_real_model` 8 (ReLU ảnh 0, 1 + 3 hàm × 2 ảnh), `test_cluster_rows1` 5, `test_quant_mantissa` 3: **185 PASS + 4 xfail đã biết** (3 channel ×2 #7,
Conv3 ×2 #9; xfail #17 cũ nay là `test_mnist_conv1_with_padding`, PASS); thêm 2 testbench riêng (bộ lượng tử 2, `activation_table` 3). Khoảng 1 giờ với 6–7 tiến trình song song.

Kiểm tra độc lập một lần chạy Conv (mọi output so với numpy, mục 6.12): `venv/bin/python tools/verify_conv_output.py test/.temp/<thư mục test>`.

### Đo hiệu suất (profiler)

```bash
venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-11-04 --clock-mhz 250   # 12 case mốc, khoảng 15–20 phút
venv/bin/python tools/run_profile.py -k "not model" --compare doc/perf/baseline_2026-11-04             # 9 case một layer, khoảng 5 phút
venv/bin/python tools/run_profile.py -k model --compare doc/perf/baseline_2026-11-04 --clock-mhz 250    # 3 model (4, 11, 11 phút)
venv/bin/python tools/run_profile.py -k q32 --mem typical                                               # bộ nhớ thực tế hơn (mục 6c)
venv/bin/python tools/paper_table3.py --run --jobs 6 --save doc/perf/paper_table3_<ngày> --report doc/perf/paper_table3_<ngày>.md   # Bảng 3, khoảng 1 giờ
venv/bin/python tools/paper_table3.py doc/perf/paper_table3_2026-11-04                                 # in lại Bảng 3 từ profile đã lưu (mốc hiện tại, 16/16)
OPENEYE_PROFILE=1 venv/bin/python -m pytest -q "test/cocotb_fpga/test_real_model.py::test_real_model_activation[silu-0]"   # đo một hàm kích hoạt (mục 6.15)
venv/bin/python -m open_eye.profile_report --clock-mhz 250 doc/perf/activation_2026-11-02/*.json        # in lại các profile hàm kích hoạt đã lưu
```

`run_profile.py` mặc định **không** chạy 16 case Bảng 3; chỉ chạy khi biểu thức `-k` có chữ `paper` (ví dụ `-k paper_cr2_x4_y3` để chạy một cấu hình).
Chi tiết: mục 6 (profiler), 6.13 (model nhiều layer), 6.14 (Bảng 3), 6.15 (hàm kích hoạt).

### Tái hiện các lỗi và thí nghiệm

| Lỗi / việc | Cách chạy | Nhìn vào đâu |
|---|---|---|
| #17 (1 channel, ảnh rộng; **đã sửa 2026-11-04**) | Trên commit trước bản sửa (`87f9bac`): `test_mnist_layers.py::test_random_data[20x8_c1_f8]` với `OPENEYE_PAD_CHANNELS=0` | `8 of 8 feature maps differ` trong log |
| #37 (trường bộ đệm iact 12 bit; **đã sửa 2026-11-04**) | Trên `87f9bac`: `test_cluster_rows1.py::test_cluster_rows1[conv14_c32_x2]` (chép file test từ `dev`) | `32 of 32 feature maps differ` |
| #22 (weight 0, trước bản sửa) | Các script trong `doc/experiments/2026-10-24_bug22/` mô tả mapper **cũ**; chạy trên commit `f83931e`: `git worktree add ../oe_old f83931e`, rồi chạy script với `PYTHONPATH=../oe_old/src` từ thư mục `../oe_old` | Tài liệu `doc/experiments/2026-10-24_bug22_weight_encoding.md` mục 7 |
| #22 (sau bản sửa) | `pytest test_mnist_layers.py -k trained`; `venv/bin/python -m pytest -q test/test_conv_wght_encoding.py` | `DUT vs numpy: ... equal, 0 differ` |
| #23 | `pytest "test_conv3x3_sparse.py::test_conv3x3_8ch_sparse50[3-4-3-2-1-8-4-32-3-3-1-16]"` | Output 0 ở các x lẻ của hàng 1 |
| #41 (stride 2, phần cứng mặc định) | `OPENEYE_ALLOW_UNSUPPORTED=1 venv/bin/python doc/experiments/2026-11-04_bug39/run39.py s2 8 8 4 16 STRIDE=2` (khoảng 4 phút), rồi `venv/bin/python doc/experiments/2026-11-07_bug41_stride/window_map.py test/.temp/b39_s2`; đối chứng: `STRIDE_ENABLED=1 OPENEYE_ALLOW_UNSUPPORTED=1 venv/bin/python doc/experiments/2026-11-04_bug39/run39.py s2e 8 8 4 16 STRIDE=2` (PASS); #41b: cùng lệnh với `s2w12 12 8 4 16 STRIDE=2` (FAIL) | `16 of 16 feature maps differ`; bảng cửa sổ tâm (x, 2y) thay vì (2x, 2y) |
| #41b–#41d (stride 2 khi bật stride, **đã sửa**) | Sau bản sửa: `venv/bin/python -m pytest -q test/cocotb_fpga/test_stride.py` (12 test). Lỗi cũ: trên commit `69320ba` (`git worktree add`), `STRIDE_ENABLED=1 OPENEYE_ALLOW_UNSUPPORTED=1 venv/bin/python doc/experiments/2026-11-04_bug39/run39.py w12 12 8 4 16 STRIDE=2` rồi `doc/experiments/2026-11-07_bug41_stride/slot_map.py test/.temp/b39_w12 0 20`; chuỗi: `run25.py st8 Convolution_Stack 2 CH=4 NF=4 W=8 H=8 STRIDE=2`; bộ đệm: thêm `DUMP_IACT_IMAGE=1` | Trên `69320ba`: `test_stride.py` 10/12 FAIL; bảng ô: DUT 6 giá trị + 2 ô đệm mỗi filter, host chờ 6 ô đệm |
| #27 (pooling rộng ≤ 4) | `OPENEYE_ALLOW_UNSUPPORTED=1 venv/bin/python doc/experiments/2026-10-26_bug25/run25.py p4x4 Conv_Pool_Conv 3 CH=4 NF=4 W=4 H=4` (khoảng 1 phút) | `Iact buffer check failed after layer 1` |
| #21 (Dense cuối > 32 output) | `OPENEYE_ALLOW_UNSUPPORTED=1 venv/bin/python doc/experiments/2026-11-07_bug41_stride/dense_run.py 64 40 1` | `FAIL` |
| #25 (`NUM_GLB_PSUM=2`, **đã sửa**) | Sau bản sửa: `venv/bin/python -m pytest -q test/cocotb_fpga/test_glb_psum2.py`. Lỗi cũ (trên commit `e062707` qua `git worktree`, như #26). Ca nhỏ nhất: `venv/bin/python doc/experiments/2026-10-26_bug25/run25.py k2 Convolution_Stack 2 GLBP=2 CH=4 H=4` (conv → conv; `GLBP=4` thì PASS). Mạng paper: `venv/bin/python tools/run_profile.py -k paper_cr2_x2_y3` | `test/.temp/b25_k2/cocotb_sim.log`: `Iact buffer check failed after layer 0`, mỗi word đổi chỗ 2 nhóm 2 byte ở giữa |
| #26 (Dense nối tiếp Dense, **đã sửa**) | Sau bản sửa: `venv/bin/python -m pytest -q test/cocotb_fpga/test_dense_chain.py` (11 test). Lỗi cũ chỉ tái hiện được trên commit trước bản sửa (`142ee6c`): `git worktree add ../oe_old 142ee6c`, rồi trong `../oe_old` chạy `PYTHONPATH=src ../OpenEye_orig/venv/bin/python doc/experiments/2026-10-24_bug26/run_dense.py x16 D_16_8_10 2` (thêm `TRACE_RAM_WRITES=1` để thấy pha ghi ngược không ghi RAM) | `test/.temp/.../cocotb_sim.log`: `Iact buffer check: first N activations only`; bản cũ: `DUT-Value` = input của layer 0 |
| #24 (hàm kích hoạt, **đã giải quyết**) | ReLU (kẹp, #30): `venv/bin/python -m pytest -q test/cocotb_fpga/test_int8_clamp.py`; Leaky ReLU / SiLU / hard-swish (bước B): `test_activation_rtl.py` (model ngẫu nhiên) và `test_real_model.py -k activation` (model đã huấn luyện); đo: mục 6.15. `hdl/af_cluster.v` vẫn không dùng | Kiểm tra bộ đệm iact sau mỗi layer khớp từng bit; mục 8b, 9 |
| #28, #29, #36 (Bảng 3, CR 1; **đã sửa** 2026-11-03) | Sau bản sửa: `venv/bin/python -m pytest -q test/cocotb_fpga/test_cluster_rows1.py`. Lỗi cũ: `R=doc/experiments/2026-11-03_table3_cr1/run.py`; #29: `venv/bin/python $R d1568 D_1568_32 1 CR=1 GLBP=4 GLBW=3 BWW=12` (nay bị toolchain từ chối ngay, có thông báo số hàng); #28 và #36 chỉ tái hiện được trên commit trước bản sửa (`31e2cdf`, `git worktree` như #26): `$R c2 PAPER_MNIST_FIRST3 3 CR=1 GLBP=2 GLBW=3` (pixel (7,1) sai), `$R d10 D_32_10 1 CR=1 GLBP=2 GLBW=3` (f 6–9 = 0) | Dòng `RESULT`; `test/.temp/t3_<tên>/wbuf.json` (số hàng, số lần quay vòng); `Difference found` trong `cocotb_sim.log` |
| #31 (lượt rỗng, không cần model thật) | `venv/bin/python doc/experiments/2026-10-30_bug31/run31.py s_zy02 zy:0:2` (Conv 8×4×4, hai hàng input đầu bằng 0, khoảng 40 s); ảnh MNIST: `run31.py img0 image:0 W=28 H=28 CH=1 NF=4`; Dense: `run31.py d_z0 zk:0:512 L=DENSE_CHAIN_3136_10 K=3136`; công tắc theo dõi `B31_WATCH`, `B31_CONV`, `B31_ENC` (docstring của `probe31.py`) | `RESULT ... DUT == bias at ...` |
| #31, #32, #33 (dữ liệu MNIST thật, **đã sửa**) | Model đã huấn luyện chạy thẳng trên `dev`: `venv/bin/python -m pytest -q test/cocotb_fpga/test_real_model.py` (ảnh 0 và 1, khoảng 11 phút mỗi ảnh), hoặc `run35.py` ở hàng dưới cho ảnh bất kỳ. Lỗi cũ chỉ tái hiện trên commit trước bản sửa (`git worktree add ../oe_old 903d5f9^` cho #32, `36b6a59^` cho #31). Bản PTQ thử nghiệm cũ (`440f36d`, đã revert, `test_ptq_mnist.py`) chỉ còn để tham khảo. #32 tái hiện không cần model thật: Conv 7×7×64 → 64 ngẫu nhiên với `OPENEYE_BIAS_STEP` | `DUT vs numpy: ... differ`; Conv1: DUT = bias; Conv3: lệch hằng số theo cặp filter |
| #32 (thứ tự bias) và #35 (= #31 ở Conv3) | Conv nhỏ có 2 nhóm kernel, bias khác nhau (khoảng 1 phút): `venv/bin/python doc/experiments/2026-10-30_bug32/run32.py w7f8 rand W=7 H=2 CH=4 NF=8 OPENEYE_BIAS_STEP=3 B32_BIAS=4` (thêm `B32_REVERSE=1` = giả lập bản sửa Python; 4 nhóm: `W=4 NF=16`); model thật trên RTL kèm dump mọi lần kiểm tra bộ đệm (khoảng 10 phút): `run35.py img0 0 [B32_REVERSE=1]`, rồi `analyze35.py test/.temp/b35_img0/dump` và `scan31.py check 0 both test/.temp/b35_img0/dump`; mức ảnh hưởng trên N ảnh (chỉ Python, khoảng 2 phút cho 1000 ảnh): `scan31.py 1000` | `RESULT ... DUT vs numpy 0/112 differ`; `model == RTL at 3136 of 3136` |
| Weight Conv đã huấn luyện cho test bất kỳ | `OPENEYE_TFLITE_CONV=$PWD/doc/demo_notebooks/mnist_quantized_model.tflite:sequential_1/conv2d_1_2/convolution` (tensor Conv2; Conv1 `sequential_1/conv2d_1/convolution`, Conv3 `sequential_1/conv2d_2_1/convolution`) | Log `OPENEYE_TFLITE_CONV: layer-0 weights from ... (N zero weights)` |

### Biến môi trường của testbench

| Biến | Tác dụng | Mặc định |
|---|---|---|
| `OPENEYE_PROFILE=1` | Bật profiler, ghi `profile.json` | tắt (`test_profile.py` tự bật) |
| `OPENEYE_SEED=<n>` | Cố định model Keras và dữ liệu ngẫu nhiên (`tf.keras.utils.set_random_seed`) | không cố định |
| `OPENEYE_DUMP_VERIFY=1` | Ghi `verify_layer0.pkl` cho `tools/verify_conv_output.py` | tắt |
| `OPENEYE_PAD_CHANNELS=1` | Bật lại đệm channel (workaround cũ của lỗi #17, để so với số đo trước bản sửa RTL 2026-11-04) | tắt (bật đến 2026-11-04) |
| `OPENEYE_TFLITE_CONV=<file>:<tensor>` | Weight Conv layer 0 lấy từ model TFLite int8 | tắt |
| `USE_RANDOM_VALUES=0` | Đường model thật của toolchain: `models/mnist_conv_net.SimpleMNISTConvNet` (PyTorch) → `onnx2model` → `LayerParameters` → `DRAMContents` | 1 (model Keras ngẫu nhiên của `data_create`) |
| `OPENEYE_MODEL_WEIGHTS=<file .pth>` | Với `USE_RANDOM_VALUES=0`: nạp trọng số đã huấn luyện và lượng tử tĩnh cho phần cứng (zero point 0, một scale weight mỗi layer); `OPENEYE_CALIBRATION_IMAGES=<n>` ảnh train để hiệu chỉnh | tắt (model chưa huấn luyện, lượng tử động); 200 |
| `OPENEYE_INPUT_IMAGE=<i>` | Input layer 0 = ảnh test MNIST i, chuẩn hoá như lúc huấn luyện, lượng tử bằng scale input của model; log lớp mà DUT dự đoán | tắt (input ngẫu nhiên) |
| `OPENEYE_ACTIVATION=<spec>` | Hàm kích hoạt trên mọi Conv/Dense trừ layer cuối của model ngẫu nhiên (bước B, mục 9): `leaky:<mant>:<shift>`, `table:random`, `table:<silu\|hardswish\|leaky_relu>:<s_in>:<s_out>`, thêm `:round` (làm tròn gần nhất), `:keep` (layer sau giữ bảng) | tắt |
| `OPENEYE_QUANT_SHIFT=<n>` | Ép shift của bộ lượng tử để kết quả tràn int8 (test kẹp, #30) | tắt |
| `OPENEYE_QUANT_MANT=<m>` | Cùng `OPENEYE_QUANT_SHIFT`: hệ số `[m, shift]` thay vì `[1, shift]` (mantissa rộng hơn 8 bit, #38) | 1 |
| `OPENEYE_ZERO_BLOCK=y:<a>:<b>` / `k:<a>:<b>` | Đặt 0 các hàng y = a…b−1 của input layer 0 (Conv) hoặc input a…b−1 (Dense), để có lượt không có activation khác 0 (lỗi #31). Khác `OPENEYE_ZERO_IACTS` (đặt 0 toàn bộ input) | tắt |
| `OPENEYE_KEEP_GOING=1` | Kiểm tra bộ đệm iact giữa các layer sai thì ghi log và chạy tiếp (test vẫn FAIL ở cuối); dùng để đo mọi layer | tắt (case Bảng 3 tự bật) |
| `OPENEYE_FAIL_ON_STALL=<N>` | Dừng khi FSM không tiến triển N chu kỳ | 100000 (case model: 400000) |
| `OPENEYE_EXPECT_LAYERS=<N>` | Model phải có đúng N layer | tuỳ test |
| `OPENEYE_CHECK_FC_WRITES=1` / `OPENEYE_SKIP_FC_WRITE_CHECK=1` | Bật / tắt bộ kiểm tra ghi FC "live" (lỗi #5) | `test_gemm_layer.py` bật |
| `OPENEYE_TRACE_DMA=1` | Ghi `dma_in_trace.csv` cho `tools/check_dma_trace.py` | tắt |
| `OPENEYE_MEM=ideal\|typical\|slow`, `OPENEYE_MEM_*` | Mô hình bộ nhớ ngoài (mục 6c) | driver lý tưởng cũ |
| `OPENEYE_LAYER_SEED=<n>` | Seed weight Keras của các layer đơn trong `data_create` | không |
| `OPENEYE_ZERO_IACTS`, `OPENEYE_CONST_IACTS=<c>`, `OPENEYE_CONST_WGHTS=<c>`, `OPENEYE_RAMP_IACTS`, `OPENEYE_ASYMMETRIC_KERNEL`, `OPENEYE_MIX_WEIGHTS`, `OPENEYE_BIAS_STEP=<s>` | Hook dữ liệu để gỡ lỗi (input 0/hằng/dốc, kernel bất đối xứng, ...) | tắt |
| `OPENEYE_ALLOW_UNSUPPORTED=1` | Các phép kiểm tra nhóm A của `LayerParameters` (#41 stride, #42 padding, #7 channel lẻ, #27 pooling, #21 Dense cuối; mục 8e) chỉ ghi cảnh báo, layer vẫn được tạo stream: để tái hiện lỗi trên RTL | tắt (báo lỗi) |
| `STRIDE_ENABLED=0/1` | Có stride trong RTL hay không (tham số `STRIDE_ENABLED` của `OpenEye_FPGA.v`, ghi vào `parameters_FPGA.vh`; mục 5.10). Bằng 0: mạch nhỏ hơn 155 LUT nhưng toolchain từ chối Conv stride > 1 (#41) | **1** (từ 2026-11-09; 0 trước đó) |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` | Tránh plugin pytest-rerunfailures mở socket | nên đặt khi chạy trực tiếp |

## 4. Cấu trúc project

Sơ đồ chỉ gồm những thư mục và file quan trọng (★ = do dự án riêng này thêm vào hoặc sửa; ☆ = sinh tự động, không có trong git).

```
OpenEye_orig/
├── README.md                     Tài liệu gốc của upstream (giữ nguyên)
├── README_FI.md               ★  File này: nhật ký, hướng dẫn, kết quả
├── hdl/                          RTL (Verilog) của bộ tăng tốc
│   ├── OpenEye_FPGA.v         ★  Top-level FPGA: cổng DMA, FSM chính (nạp → convert → tính → đọc ra), buffer iact/weight/psum
│   │                             (★ sửa GET_BIAS, lỗi #3; điều kiện lưu FC, lỗi #19; ghi ngược #25, #26; thanh ghi act_min, #30;
│   │                             mẫu reset, upstream `e78e5b7`; kết thúc gửi weight ở `wghts_per_pe + 1`, dòng của upstream `3258813`;
│   │                             trạng thái GET_ACTIVATION nạp bảng hàm kích hoạt)
│   ├── psum_pipeline.v        ★  FSM psum: nạp bias, thu kết quả, lượng tử hoá, gửi kết quả ra DMA (★ `results_ready`, lỗi #14; kẹp int8, #30;
│   │                             hàm kích hoạt: chế độ, bảng tra cho các lane ghi ngược; điều kiện ready ở CR 1, #28; độ rộng đọc ra Dense, #36)
│   ├── iact_stream_constructor.v ★ Đọc iact từ buffer và gửi tới các cluster (★ bộ đếm lỗi #13; ghi 1 channel và NUM_GLB_IACT=3, lỗi #6/#7;
│   │                             bộ đếm cặp FC 12 bit, lỗi #19)
│   ├── OpenEye_Parallel.v        Mảng tính toán: các cluster + router ("ASIC compute core", SERIAL=0/1)
│   ├── OpenEye_Cluster.v, PE_cluster.v, PE.v   Cluster → nhóm PE → PE (MAC INT8, sparse) (★ PE.v: độ rộng bit, upstream `2bf497d`;
│   │                             trạng thái `EMPTY_PASS`, lỗi #31)
│   ├── data_pipeline_wght.v      Giải mã weight nén vào 2 SPad của PE (định dạng mà lỗi #22 phải khớp)
│   ├── quantization_unit.v    ★  Lượng tử hoá kết quả khi ghi ngược cho layer sau (★ kẹp int8 về [act_min, 127], ReLU = act_min 0, lỗi #30;
│   │                             độ dốc âm của Leaky ReLU, làm tròn gần nhất)
│   ├── activation_table.v     ★  Bảng 256 ô int8 → int8 của hàm kích hoạt dạng bảng (SiLU, hard-swish), các bank LUTRAM
│   ├── af_cluster.v              Khối ReLU, **không được dùng ở đâu** và còn lỗi (lỗi #24)
│   ├── router_*.v, GLB_cluster.v Router iact/weight/psum giữa các cluster, GLB của cluster
│   ├── dma_storage.v             Bộ giải mã word cấu hình (BẢN CŨ: test và export luôn thay bằng bản sinh từ regmap.yaml)
│   ├── RAM_*.v, SPad_*.v         Mô hình RAM/scratchpad (Vivado suy luận thành BRAM/URAM/LUTRAM)
│   ├── include/regmap_params.vh ☆ Header sinh tự động (bản còn sót của lần chạy trước)
│   └── lint_waivers.vlt          Các warning Verilator được bỏ qua có chủ đích
├── fpga/
│   ├── hdl/open_eye_axi_v1_0.v   Wrapper AXI (AXI-Lite + AXI4-Stream) cho Vivado IP; hiện không biên dịch được (lỗi #16)
│   └── sw/                       Phần mềm chạy trên ARM: runtime AXI DMA (hal_xaxidma.c, openeye_runtime.c)
├── models/                       Model PyTorch: mnist_conv_net.py (★ tham số activation: relu, leaky_relu, silu, hardswish),
│                                 ★ train_mnist.py (huấn luyện các biến thể như notebook, checkpoint vào doc/demo_notebooks/, bị .gitignore bỏ qua)
├── src/open_eye/                 Thư viện Python (cài kiểu editable vào venv)
│   ├── open_eye_parameters.py    Cấu hình phần cứng (đọc từ biến môi trường: CLUSTER_ROWS, IACT_RAM_CELLS, ...)
│   ├── layer_parameters.py    ★  Tính tham số của từng layer (số chu kỳ, giới hạn vòng lặp, ...) (★ ghi ngược #25, #26; act_min #30; model thật;
│   │                             hàm kích hoạt: `activation_config`, `activation_registers`, `activation_table_words`; kiểm tra bộ đệm weight #29:
│   │                             `wght_buffer_rows`, `check_wght_buffer`)
│   ├── *_mapper.py               Sinh stream DMA: conv, dense, iact, weight, psum (bias), pooling (★ conv_mapper: lỗi #18;
│   │                             ★ wght_stream_mapper: weight Conv dùng conv_wght_encoding, lỗi #22; ★ psum_stream_mapper: thứ tự bias,
│   │                             lỗi #32; ★ dense_mapper: ghi ngược FC, lỗi #26;
│   │                             ★ conv/dense_mapper: 5 trường và các word bảng của hàm kích hoạt)
│   ├── DRAM.py                ★  Dữ liệu của layer (input, weight, bias); giữ weight Conv bằng 0 thật; nạp weight Conv từ TFLite;
│   │                             giữ nguyên weight/bias của model đã lượng tử (model thật)
│   ├── onnx2model.py          ★  Model PyTorch → ONNX → HardwareLayer (★ lượng tử tĩnh cho model đã huấn luyện; MaxPool đúng loại, lỗi #34;
│   │                             nhận diện Leaky ReLU / SiLU / hard-swish và tính tham số phần cứng, shape sau op com.microsoft)
│   ├── data_create.py         ★  Model Keras của test (thêm MNIST_REAL, PAPER_MNIST; ảnh MNIST; móc `OPENEYE_ACTIVATION`)
│   ├── simple_layer_operations.py ★ Tham chiếu của bộ lượng tử (`batchnorm_output`: kẹp #30, Leaky ReLU, bảng, làm tròn)
│   ├── generator.py              regmap.yaml → regmap_params.vh, dma_storage.v, đóng gói word cấu hình
│   ├── vh_file_creator.py        Sinh parameters_FPGA.vh / parameters_PE.vh / parameters_PE_cluster.vh
│   ├── test_utils_main.py     ★  Tính kết quả tham chiếu (golden model), tạo stream song song (★ báo lỗi của mapper trong process con)
│   ├── rtl_test_utils.py      ★  Hàm cocotb: gửi stream, so sánh kết quả, profiler (kể cả `load_act`, khối kích hoạt, số 0 ở input), trace DMA, driver bộ nhớ
│   ├── memory_model.py        ★  Mô hình DDR + AXI DMA (mục 6c)
│   ├── channel_pad.py         ★  Đệm input 1 channel thành 2 channel (workaround cũ của lỗi #17; từ bản sửa RTL 2026-11-04 chỉ khi OPENEYE_PAD_CHANNELS=1)
│   ├── conv_wght_encoding.py  ★  Mã hóa weight Conv có số 0 theo đúng cách RTL giải mã (sửa lỗi #22, mục 9)
│   ├── wght_pipeline_model.py ★  Mô hình chu kỳ của data_pipeline_wght.v (khớp RTL), dùng trong unit test
│   ├── writeback_model.py     ★  Mô hình chu kỳ của pha ghi ngược psum → iact (vòng đọc + bộ đóng gói), dùng trong unit test (#25, #26)
│   └── profile_report.py      ★  Báo cáo và so sánh profile (mục 6.5)
├── test/
│   ├── cocotb_fpga/              Testbench top-level FPGA và các bộ test (cách chạy: mục 3c)
│   │   ├── OpenEye_FPGA_tb.py ★  Testbench (★ seed, đệm channel, weight TFLite, KEEP_GOING, profiler, các hook dữ liệu)
│   │   ├── test_profile.py    ★  Case đo: 9 một layer + 3 cả model (mốc, mục 6.7) + 16 cấu hình Bảng 3 của paper (mục 6.14)
│   │   ├── test_conv_const.py ★  Test Conv (36 test dùng làm hồi quy; ★ thêm random_data, thứ tự bias #32)
│   │   ├── test_gemm_layer.py    Test GEMM/Dense (63 test dùng làm hồi quy)
│   │   ├── test_mnist_layers.py ★ 26 test: quét channel × NUM_GLB_IACT (lỗi #6/#7), 3 layer Conv MNIST thật, dữ liệu ngẫu nhiên + kiểm tra
│   │   │                         độc lập (lỗi #18), 1 channel rộng 20/28/40 (lỗi #17, nay chạy 1 channel thật), 3 Conv với weight MNIST đã huấn luyện (lỗi #22)
│   │   ├── test_conv3x3_sparse.py  iact và weight thưa dạng bàn cờ, NUM_GLB_IACT=3 (của upstream; một ca còn lỗi #23)
│   │   ├── test_dense_chain.py ★ 11 chuỗi Dense → Dense trên chip (ghi ngược FC, lỗi #26), MLP, nhiều cấu hình
│   │   ├── test_glb_psum2.py  ★  7 mô hình nối layer với NUM_GLB_PSUM=2 (ghi ngược Conv, lỗi #25)
│   │   ├── test_int8_clamp.py ★  9 mô hình kiểm kẹp int8 và ReLU gộp (#30)
│   │   ├── test_real_model.py ★  Model PyTorch MNIST đã huấn luyện qua đường toolchain trên RTL (ReLU và 3 biến thể hàm kích hoạt)
│   │   ├── test_activation_rtl.py ★ Hàm kích hoạt trên RTL với model ngẫu nhiên (móc OPENEYE_ACTIVATION): 12 test
│   │   ├── test_empty_pass.py ★  Lượt không có activation khác 0 (lỗi #31): 3 test
│   │   ├── test_cluster_rows1.py ★ CLUSTER_ROWS=1: lỗi #28, #29, #36 (Dense, mạng paper CR 1 X 2 Y 3), #37 (Conv 14×14×32): 5 test
│   │   ├── test_quant_mantissa.py ★ Mantissa 17/24 bit của hệ số lượng tử (#38): 3 test
│   │   ├── test_stride.py     ★  Conv stride 2 với RTL dựng `STRIDE_ENABLED=1` (#41b–#41d): 12 test
│   │   ├── test_pooling.py, test_nets.py   Conv → MaxPool → Conv và model MNIST nhỏ (của upstream, nằm trong bộ hồi quy)
│   │   └── regmap.yaml        ★  Định nghĩa các thanh ghi cấu hình gửi qua DMA (nguồn của dma_storage.v; ★ `quant_clamp_low` #30, 5 trường hàm kích hoạt)
│   ├── cocotb_parallel/          Test của OpenEye_Parallel (SERIAL=0), đã cũ (mục 5.7)
│   ├── test_model_guards.py   ★  Phép kiểm tra nhóm A (mục 8e): 56 unit test
│   ├── test_stride_params.py  ★  Tham số phía host của Conv có stride (#41b, #41d): 15 unit test
│   ├── test_memory_model.py   ★  16 unit test của mô hình bộ nhớ
│   ├── test_profile_report.py ★  Unit test của công cụ báo cáo (kể cả bảng hàm kích hoạt, bước C)
│   ├── test_profile_phases.py ★  Unit test quy tắc gán pha của profiler (kể cả `load_act`, input của layer)
│   ├── test_channel_pad.py    ★  Unit test đệm channel (workaround cũ của lỗi #17, nay tắt mặc định)
│   ├── test_conv_wght_encoding.py ★ Unit test mã hóa weight Conv có số 0 (lỗi #22)
│   ├── test_paper_table3.py   ★  Unit test của công cụ Bảng 3
│   ├── test_fc_writeback.py   ★  Mô hình chu kỳ của pha ghi ngược FC (lỗi #26): 110 test
│   ├── test_conv_writeback.py ★  Mô hình chu kỳ của pha ghi ngược Conv với 2/4 lane (lỗi #25): 12 test
│   ├── test_int8_clamp.py     ★  Unit test kẹp int8 / ReLU phía Python (#30): 11 test
│   ├── test_onnx_model_flow.py ★ Đường model thật của toolchain so với ONNX Runtime từng layer, không RTL: 6 test
│   ├── test_psum_bias_order.py ★ Thứ tự stream bias Conv so với mô hình nạp bias của RTL (lỗi #32): 22 test
│   ├── test_wght_buffer.py    ★  Số hàng bộ đệm weight và phép kiểm tra của #29, phép kiểm tra bộ đệm iact của #37: 5 test
│   ├── test_activation.py     ★  Hàm kích hoạt Leaky ReLU / SiLU / hard-swish trong toolchain và tham chiếu, so với ONNX Runtime (bước A), trường và word bảng gửi cho RTL (bước B): 31 test
│   ├── cocotb_quantization/   ★  Testbench riêng của quantization_unit (kẹp int8, #30; Leaky ReLU, làm tròn)
│   ├── cocotb_activation_table/ ★ Testbench riêng của activation_table
│   └── .temp/                 ☆  Thư mục chạy của từng test (log, header sinh ra, profile.json)
├── tools/                     ★  Công cụ của dự án riêng
│   ├── run_profile.py            Chạy các case đo song song, so sánh với baseline (mục 6)
│   ├── paper_table3.py        ★  Bảng 3 của paper OpenEye đo bằng profiler, theo từng layer và từng pha (mục 6.14)
│   ├── lint_check.py, lint_baseline/   Lint theo baseline (mục 9c)
│   ├── export_vivado.py          Xuất thư mục nguồn + Tcl cho Vivado (mục 6d)
│   ├── check_dma_trace.py        Kiểm tra DUT nhận đúng stream DMA (mục 9)
│   ├── decode_iact_read_loops.py Giải mã thanh ghi vòng lặp đọc iact từ stream DMA
│   ├── verify_conv_output.py     Kiểm tra độc lập từng word output của layer Conv (numpy)
│   └── report/make_progress_report*.py  Tạo báo cáo Word cho giáo viên hướng dẫn (2026-10-10, 2026-10-15, 2026-10-31);
│                                        make_activation_report_2026-11-05.py: báo cáo lần 4 về hàm kích hoạt
├── doc/
│   ├── perf/                  ★  Số liệu đo chu kỳ: baseline_2026-11-04/ (**mốc hiện tại**, 12 case, sau hàng O), baseline_2026-11-02/ (mốc trước), baseline_2026-10-24/, paper_table3_2026-11-04/ (Bảng 3 paper, mốc
│   │                             hiện tại, 16/16, layer 0 không đệm; 2026-11-03 trước hàng O, 2026-11-02 trước #28/#29/#36, fix25 trước dòng wghts_per_pe + 1, 2026-10-24 trước #25/#26), trained_mnist_2026-10-31/ (model đã huấn luyện, ảnh thật),
│   │                             activation_2026-11-02/ (4 hàm kích hoạt trên model đã huấn luyện + 3 ca bảng, mục 6.15), activation_2026-11-04_mant24/ (4 model đó sau bản sửa #38), activation_2026-11-04_rowO/ (sau hàng O, số hiện tại),
│   │                             baseline_2026-10-22/, baseline_2026-10-15/, baseline_2026-10-10/ (mốc cũ), mem_typical_2026-10-10/, ...
│   ├── synth/                 ★  Báo cáo Vivado theo từng lần chạy (mỗi thư mục có SUMMARY.md)
│   ├── experiments/           ★  Báo cáo thí nghiệm và điều tra lỗi (#13, #6/#7, #18, #14, #19, cherry-pick upstream, model nhiều layer,
│   │                             #17 đệm channel, #22 mã hoá weight, #26 Dense nối tiếp Dense, #25 NUM_GLB_PSUM=2, int8/kẹp/ReLU #30 + bộ giả lập model int8, #31 lượt rỗng, #32 thứ tự bias + #35, đường model thật của toolchain, rà soát upstream 2026-10-31, hàm kích hoạt A/B/C 2026-11-02, 3 cấu hình CR 1 của Bảng 3 #28/#29/#36 2026-11-03, mantissa #38, upstream `36395dd`, hàng O #37/#17 và #39 2026-11-04) kèm script probe/lockstep để chạy lại
│   ├── lint/                  ★  Output lint gốc
│   ├── reports/               ★  Báo cáo tiến độ (Word): BaoCao_TienDo_OpenEye_2026-10-10.docx, BaoCao_TienDo_OpenEye_2026-10-15.docx,
│   │                             BaoCao_TienDo_OpenEye_2026-10-31.docx (+ 5 hình PNG), BaoCao_HamKichHoat_OpenEye_2026-11-05.docx
│   │                             (hàm kích hoạt, + 4 hình PNG)
│   ├── OpenEye_FPGA_documentation.md, test_status_handover.md   Tài liệu của upstream
│   └── demo_notebooks/           Notebook demo của upstream
├── yosys/, nextpnr/              Flow tổng hợp mã nguồn mở của upstream (FPGA GateMate)
├── dse_scripts/                  Script Vivado của upstream (trỏ tới project trên máy tác giả gốc, không dùng được)
├── .github/workflows/lint.yml ★  CI lint theo baseline
├── vivado/                    ☆  Thư mục do export_vivado.py tạo (trong .gitignore)
└── venv/                      ☆  Python venv (cocotb, TensorFlow, open_eye)
```

## 5. Giải thích khái niệm

### 5.1 Pha (phase)

"Pha" là **một nhóm trạng thái của FSM chính** trong `hdl/OpenEye_FPGA.v`
(biến `fsm_current_state`). Mỗi layer lần lượt đi qua các pha theo thứ tự cố định.
Profiler gom các trạng thái như sau (`PROFILE_PHASES` trong `rtl_test_utils.py`):

| Pha | Trạng thái FSM chính | Việc đang làm |
|---|---|---|
| `load_config` | `GET_PARAMETERS` (1), `GET_ROUTER_CONFIG` (2) | Nhận cấu hình layer qua DMA |
| `load_iact` | `GET_IACT` (3) | Nhận activation đầu vào |
| `load_wght` | `GET_WGHT` (4) | Nhận weight |
| `load_bias` | `GET_BIAS` (5) | Nhận bias (giá trị psum ban đầu) |
| `load_quant` | `GET_QUANTIZE` (6) | Nhận bảng lượng tử hoá |
| `load_act` | `GET_ACTIVATION` (15) | Nhận bảng 256 ô của hàm kích hoạt dạng bảng (SiLU, hard-swish; từ 2026-11-02, mục 6.15); không có ở layer khác |
| `convert_iact` | `START_CONVERTER` (7), `CONVERT_IACT` (8), `WAIT_CYCLE` (9) | Sắp xếp iact cho các PE, không dùng DMA |
| `compute` | `WAIT_FOR_RESULTS` (10) | Mảng PE tính toán |
| `writeback` | `RECEIVE_PSUMS_TO_IACT` (11) | Ghi kết quả đã lượng tử làm input cho layer sau |
| `pooling` | `MAXPOOLING_*` (12–14) | Max-pooling trên chip |
| `readout` | **FSM psum** (`psum_pipeline.v`) ở `PSUM_SEND_RESULTS` (5) | Gửi kết quả ra DMA |

Ngoại lệ: `readout` được xác định theo **FSM psum**, vì lúc gửi kết quả thì FSM chính
không có trạng thái riêng cho việc này: FSM chính vẫn ở `WAIT_FOR_RESULTS` (10), nên `compute` = các chu kỳ ở trạng thái 10 **trừ** những chu kỳ readout.

**Vì sao 9 case đo chỉ thấy `... → compute → readout`, không thấy `writeback` và `pooling`:** đó là các layer `Convolution_Single`
(`send_data_out = 1`), kết quả được gửi ra DMA. Hai pha còn lại chỉ xuất hiện ở các layer khác:
- `writeback` (`RECEIVE_PSUMS_TO_IACT`): khi `send_data_out = 0`, ví dụ `Convolution_Stack` (2 layer nối tiếp). Kết quả được lượng tử hoá và ghi thẳng
  vào bộ đệm iact làm input của layer sau, không đi qua DMA.
- `pooling` (`MAXPOOLING_*`): layer max-pooling chạy trên chip. FSM đi `GET_ROUTER_CONFIG → GET_QUANTIZE → MAXPOOLING_READ ⇄ MAXPOOLING_SEND/WAIT`.
Profiler định nghĩa đủ các pha để đo được cả những layer này (việc 0.2).

**Các trạng thái của FSM chính** (`OpenEye_FPGA.v`, 16 giá trị 0–15): 0 `IDLE` (không dùng: sau reset FSM vào thẳng 1), 1 `GET_PARAMETERS`
(TRANSMISSIONS word cấu hình + mask PE), 2 `GET_ROUTER_CONFIG`, 3 `GET_IACT`, 4 `GET_WGHT`, 5 `GET_BIAS` (bỏ qua nếu `skipPsum`), 6 `GET_QUANTIZE`,
7 `START_CONVERTER`, 8 `CONVERT_IACT`, 9 `WAIT_CYCLE` (64 chu kỳ, phát lệnh gửi weight), 10 `WAIT_FOR_RESULTS` (mảng PE tính, FSM psum đọc kết quả ra;
rời trạng thái khi word cuối `last_data_o` được nhận), 11 `RECEIVE_PSUMS_TO_IACT`, 12 `MAXPOOLING_READ`, 13 `MAXPOOLING_SEND`, 14 `MAXPOOLING_WAIT`, 15 `GET_ACTIVATION` (từ 2026-11-02: nạp bảng hàm kích hoạt sau
`GET_QUANTIZE`).
FSM psum (`psum_pipeline.v`): 0 `PSUM_IDLE`, 1 `WAIT_TO_SEND_READY_SIGNAL`, 2 `CALCULATE_PSUM` (đưa bias/psum cũ vào PE), 3 `PSUM_GET_RESULTS`,
4 `WAIT_FOR_SENDING_RESULTS`, 5 `PSUM_SEND_RESULTS` (gửi ra DMA), 6 `SEND_PSUM_TO_IACT` (lượng tử, ghi lại làm iact).

### 5.2 Beat DMA và burst

- **DMA** (Direct Memory Access): đường truyền dữ liệu giữa bộ nhớ ngoài (DDR, do host điều khiển)
  và bộ tăng tốc, không cần CPU chép từng byte. OpenEye có **một cổng DMA vào**
  (`data_dma_i`, `enable_dma_i`, `ready_dma_o`) và **một cổng DMA ra**
  (`data_dma_o`, `enable_dma_o`, `ready_dma_i`), mỗi cổng rộng `DMA_BITWIDTH` bit (mặc định 64).
- **Beat** (hay "word DMA"): **một lần truyền một word rộng `DMA_BITWIDTH` bit trong một chu kỳ clock**.
  Beat xảy ra khi bên gửi báo có dữ liệu (`enable`/valid = 1) **và** bên nhận báo sẵn sàng (`ready` = 1)
  ở cùng một cạnh clock (handshake valid/ready). Với DMA 64 bit, mỗi beat chở 8 byte.
- **Burst**: **một chuỗi beat liên tiếp** sinh ra từ một yêu cầu đọc hoặc ghi bộ nhớ (ví dụ AXI burst: một
  địa chỉ, rồi tối đa 256 beat). Mỗi burst có chi phí khởi đầu (độ trễ DDR, thường hàng chục đến hàng trăm
  chu kỳ), nên burst dài và ít thì hiệu quả hơn burst ngắn và nhiều.
  Mặc định testbench **không mô phỏng burst hay độ trễ bộ nhớ** (host luôn sẵn sàng, gửi liên tục), nên baseline là trường hợp tốt nhất
  về phía bộ nhớ. Muốn có burst và độ trễ thì bật mô hình bộ nhớ (`run_profile.py --mem`, mục 6c).

**Một burst gồm nhiều beat liên tiếp.** Ví dụ: chuyển 100 beat trong 1 burst tốn khoảng 100 + 1 × độ trễ; chia thành 100 burst
thì tốn khoảng 100 + 100 × độ trễ.

**DMA trong project:**
- Trên FPGA thật (`fpga/`): dùng **Xilinx AXI DMA IP ở chế độ Simple** (không có Scatter-Gather), tắt ngắt và chờ bằng polling
  (`fpga/sw/runtime/hal_xaxidma.c`). Có 2 kênh: MM2S (DDR → bộ tăng tốc) và S2MM (bộ tăng tốc → DDR).
  Phía bộ tăng tốc là **AXI4-Stream** (`tvalid/tready/tdata/tlast`, không có địa chỉ); cấu hình qua AXI4-Lite
  (`fpga/hdl/open_eye_axi_v1_0.v`). Runtime gửi **toàn bộ stream của một layer bằng một lệnh `XAxiDma_SimpleTransfer`**
  (`openeye_runtime.c`). Chính IP AXI DMA mới chia lệnh đó thành các burst AXI4 tới DDR; độ dài burst do cấu hình IP
  trong Vivado quyết định, và cấu hình này không nằm trong repo. Input `tlast` bị bỏ qua; output `tlast` = `last_data_o`.
- Trong simulation (cocotb): **không có AXI DMA thật**. Mặc định testbench đẩy thẳng mỗi chu kỳ một word vào cổng stream và luôn sẵn sàng;
  mô hình bộ nhớ ở mục 6c thay phần này bằng một mô hình DDR + AXI DMA đơn giản.

### 5.3 Payload tối thiểu và hiệu suất bus

**Payload tối thiểu** là số byte **thực sự cần** chuyển trong một pha, tính từ hình dạng layer.
Hàm tính: `payload_bytes()` trong `src/open_eye/profile_report.py`.
Ký hiệu: X×Y là kích thước ảnh vào, C là số channel vào, F là số filter, Kx×Ky là kích thước kernel.

| Pha | Công thức | Ý nghĩa |
|---|---|---|
| `load_iact` | `X × Y × C` byte | Mỗi activation INT8 = 1 byte |
| `load_wght` | `F × C × Kx × Ky` byte | Mỗi weight INT8 = 1 byte |
| `load_bias` | `F × ceil(psum_bit / 8)` byte | Mỗi filter chỉ cần một bias |
| `load_quant` | `F × 40 bit` | Mỗi filter một entry lượng tử: offset 8 + exponent 7 + mantissa 25 bit |
| `load_act` | `256` byte | Bảng hàm kích hoạt (256 ô int8), chỉ layer dùng bảng và không giữ bảng cũ |
| `readout` | `số output × ceil(psum_bit / 8)` byte | Mỗi output một psum |

**Hiệu suất bus** = payload tối thiểu ÷ (số beat × `DMA_BITWIDTH`/8).
100% nghĩa là mọi bit trên bus đều là dữ liệu cần thiết; 15% nghĩa là 85% băng thông bị lãng phí
(do đệm, lặp lại dữ liệu, hoặc mã hoá kém).
Hiện chỉ tính được cho layer `Convolution_Single`.

### 5.4 Baseline

**Baseline** là **phép đo mốc trước khi tối ưu**. Mỗi lần sửa RTL để tối ưu, ta chạy lại đúng các cấu hình đó
và so sánh với baseline để biết thay đổi tốt hơn hay tệ hơn bao nhiêu. Không có baseline thì không chứng minh được
tối ưu có tác dụng. Có hai loại baseline:
- **Chu kỳ và DMA** (mô phỏng): **`doc/perf/baseline_2026-11-04/`** (12 case: 9 một layer + 3 cả model, sau hàng O: #37, #17, #39; khác `baseline_2026-11-02` chỉ ở `model_mnist_real_c1`). Mốc cũ: `baseline_2026-11-02` (sau dòng `wghts_per_pe + 1`), `baseline_2026-10-24` (sau bản sửa lỗi #22), `baseline_2026-10-22`
  (trước #22), `baseline_2026-10-15` (9 case, sau #18; 9 case này không đổi tới nay), `baseline_2026-10-10` (đo khi lỗi #18 còn: weight đọc gấp đôi,
  case > 4 channel tính sai với weight thật), `doc/perf/baseline.md` và `baseline_2026-10-09*`.
- **Phần cứng** (Vivado): `doc/synth/2026-11-04_route4ns_rowO_zu7ev/` (tài nguyên, fmax 250 MHz; sau hàng O #37, #17). Các thư mục `doc/synth` cũ hơn là lịch sử.

### 5.5 QUANT_AMOUNT

- Tham số phần cứng (`parameter QUANT_AMOUNT` trong `OpenEye_FPGA.v`) = **số entry tối đa của bảng lượng tử hoá**,
  tức số filter tối đa mà một layer có thể có hệ số lượng tử riêng.
- Lượng tử hoá theo filter: `q = kẹp((mantissa × (psum + offset)) >>> exponent, act_min, 127)`, dùng để đưa psum 20/32 bit về INT8.
  Kẹp có từ 2026-10-28 (trước đó lấy 8 bit thấp, quấn vòng); `act_min` theo layer: −128, hoặc 0 khi có ReLU (mục 9).
- Mỗi entry dài 40 bit, nên bảng chiếm `QUANT_AMOUNT × 40` bit:
  1.280 bit khi bằng 32, nhưng **40.960 bit khi bằng 1024**.
- Bảng được gửi **đủ `QUANT_AMOUNT` entry ở mỗi layer** (`QUANT_TRANS_CYCLES`, `OpenEye_FPGA.v:252`), bất kể layer
  có bao nhiêu filter: 20 beat khi bằng 32, 640 beat khi bằng 1024.

### 5.6 Vì sao QUANT_AMOUNT=1024 làm simulation chậm (khoảng 244 giây so với 15 giây)

Thời gian chạy một test: khoảng 15 giây khi `QUANT_AMOUNT=32`, khoảng 244 giây khi bằng 1024 (chênh khoảng 229 giây, tức chậm khoảng 16 lần).
Riêng phần simulation trong cocotb: 5 giây so với 185 giây (37 lần), trong khi số chu kỳ mô phỏng chỉ tăng khoảng 2 lần.

Nguyên nhân nằm ở cách RTL lưu bảng lượng tử:
1. Toàn bộ bảng là **một thanh ghi duy nhất** `quant_reg` rộng `QUANT_AMOUNT × 40` bit (40.960 bit).
2. Thanh ghi được nạp kiểu **thanh ghi dịch**: mỗi beat DMA dịch **toàn bộ** 40.960 bit
   (`OpenEye_FPGA.v`, khoảng dòng 2026–2028). 640 beat tạo ra 640 lần thay đổi của một vector khổng lồ.
3. Mỗi lần `quant_reg` thay đổi, Icarus phải tính lại **mọi lệnh `assign` đọc từ nó**: 3 × 1024 lệnh tách
   offset, exponent, mantissa trong `OpenEye_FPGA.v`, cộng thêm các bản "flat" và bản trong `psum_pipeline.v`.
   Tổng cộng hàng nghìn phép cắt bit trên vector 40 kbit, lặp lại sau mỗi beat.
4. Thêm thời gian biên dịch (`iverilog`) cho thiết kế lớn hơn, và 620 chu kỳ DMA thừa.

Trên FPGA thật, cách lưu này cũng tốn **khoảng 41.000 flip-flop**. Nếu lưu bảng trong BRAM và chỉ nạp `F` entry
thì vừa tiết kiệm tài nguyên, vừa giảm DMA, vừa giúp simulation nhanh hơn. Đây là một ứng viên tối ưu.

### 5.7 SERIAL=1 và SERIAL=0

`SERIAL` là tham số phần cứng chọn **cách dữ liệu đi vào và đi ra mảng tính toán** (`OpenEye_Parallel.v`, `GLB_cluster.v`, `PE.v`).

| | `SERIAL=1` (đang dùng) | `SERIAL=0` (chế độ song song) |
|---|---|---|
| Ai dùng | `OpenEye_FPGA.v` (mặc định `SERIAL=1`), toàn bộ luồng FPGA và các test `test/cocotb_fpga` | `OpenEye_Parallel.v` khi đứng một mình làm top-level (mặc định `SERIAL=0`), testbench `test/cocotb_parallel` |
| Dữ liệu vào | **Một luồng DMA** vào `OpenEye_FPGA`, được đệm ở buffer trung tâm (iact/weight/psum buffer), rồi phân phối qua router | **Nhiều cổng song song rộng**, mỗi GLB của mỗi cluster một cổng, do một bộ điều khiển bên ngoài cấp |
| Global buffer (GLB) trong cluster | **Không có RAM**, chỉ là đường dẫn thẳng | **Có RAM riêng** (iact GLB, psum GLB), truy cập độc lập và đồng thời, kiểu chip Eyeriss v2 |
| Đầu ra psum của PE (`PE.v:820`) | Qua adder tree | Đường kết hợp khác (đây là chỗ có warning SELRANGE) |
| Tình trạng | Chạy được (test FPGA pass ở các cấu hình hỗ trợ) | **Chưa hoàn thiện**: bộ sinh địa chỉ GLB chưa tồn tại (comment ở `OpenEye_Parallel.v:790`); testbench `cocotb_parallel` đã cũ và fail (`doc/test_status_handover.md` mục 4.3) |

- **Khi nào dùng `SERIAL=0`:** khi `OpenEye_Parallel` được dùng làm lõi tính toán độc lập, ví dụ trong ASIC hoặc một hệ thống
  tự cấp dữ liệu song song cho từng cluster.
- **Kiểm chứng (cập nhật 2026-10-13): `SERIAL=0` chưa được kiểm chứng là chạy đúng.**
  - Bộ sinh địa chỉ GLB chưa có: `OpenEye_Parallel.v:790` ghi rõ "needs an address generator that does not exist yet",
    và địa chỉ GLB để trống có chủ đích.
  - `test/cocotb_parallel` đã cũ: 5/6 test fail vì lỗi Python (TypeError, testbench viết trước đợt refactor `src/open_eye`), không phải do kiểm tra kết quả.
    Test duy nhất pass là `test_gemm_mode_plumbing` (chỉ kiểm tra đường nối). Upstream khuyên "do not use cocotb_parallel for system checks"
    (`doc/test_status_handover.md` mục 4.3).
  - Lint mục tiêu `parallel` (mặc định `SERIAL=0`) chỉ chứng minh RTL **biên dịch được**, không chứng minh tính đúng.
- **Có phải định hướng ASIC không? Đúng, theo tài liệu upstream.** README gọi `OpenEye_Parallel.v` là "ASIC compute core";
  `doc/OpenEye_FPGA_documentation.md` viết `OpenEye_FPGA` "adapts the core OpenEye_Parallel module, which was designed for ASIC".
  `RAM_SP.v` có sẵn chỗ cắm SRAM macro (`OPENEYE_RAM_SPECIFIC`, OpenRAM) dành cho ASIC. Lưu ý hai điểm:
  - Chính `OpenEye_FPGA` cũng chứa `OpenEye_Parallel`, nhưng với `SERIAL=1`. Vậy "lõi ASIC" là **module**; `SERIAL=0` là **chế độ dữ liệu song song**
    (GLB có RAM riêng, mỗi cluster một cổng) phù hợp với chip ASIC kiểu Eyeriss v2, nơi có thể nối nhiều cổng rộng.
  - Repo **không có** luồng ASIC (không có script OpenLane, thư viện cell hay SRAM macro). Chỉ có Yosys/nextpnr cho FPGA GateMate và Vivado.
- **Ảnh hưởng tới hướng nghiên cứu:** mọi số đo hiện tại (chu kỳ, DMA, Vivado) là của `SERIAL=1`. `SERIAL=0` giữ dữ liệu trong GLB của từng
  cluster (tái sử dụng trên chip nhiều hơn, ít DMA hơn), nên về lâu dài có thể là một hướng kiến trúc. Nhưng hoàn thiện nó (bộ sinh địa chỉ GLB,
  testbench mới) là một dự án riêng, lớn; chỉ nên cân nhắc khi mục tiêu chuyển sang kiến trúc ASIC.

### 5.8 Độ rộng DMA: 32 bit hay 64 bit

- **Phần cứng FPGA (`fpga/hdl/open_eye_axi_v1_0.v`): 64 bit.** `C_dma_i_TDATA_WIDTH = C_dma_o_TDATA_WIDTH = 64`; wrapper không truyền
  `DMA_BITWIDTH` vào `OpenEye_FPGA`, nên lõi lấy giá trị trong `parameters_FPGA.vh` (header sinh tự động; `export_vivado.py` ghi 64), hoặc
  `DMA_BITWIDTH = 64` (`OpenEye_FPGA.v:123`) khi định nghĩa `USE_INTERNAL_PARAMS`.
- **Mô phỏng/đo hiệu suất:** giá trị lấy từ biến môi trường `DMA_BITWIDTH` (nếu không có thì mặc định 64 trong `OpenEyeParameters`) và được ghi
  vào `parameters_FPGA.vh`. Các case đo dùng **64 bit** để khớp với phần cứng, trừ case `32x3_f4_q32_dma32` (32 bit, để so sánh: chậm hơn 34 %).
  Lưu ý: `test/cocotb_fpga/Makefile` của upstream đặt `DMA_BITWIDTH = 32`, và notebook MNIST cũng dùng 32.
- **Cố định hay thay đổi được?** `DMA_BITWIDTH` là **tham số lúc tổng hợp (elaboration)**: sau khi tổng hợp và nạp bitstream thì **cố định**; muốn đổi thì
  tổng hợp lại. Khi đổi phải đổi **đồng thời**: độ rộng stream của IP AXI DMA, `C_dma_*_TDATA_WIDTH` của wrapper (và thêm `.DMA_BITWIDTH(...)` vào
  wrapper, hiện chưa có), cùng bộ sinh stream Python và runtime (dữ liệu được đóng gói theo `DMA_BITWIDTH`).
- **Giá trị nào chạy được:** 32 và 64 đã chạy đúng trong mô phỏng. Logic đọc kết quả xếp psum vào các ô 32 bit (`DMA_BITWIDTH // 32` psum mỗi beat),
  nên độ rộng phải là bội của 32. 128 bit **chưa được kiểm chứng** (có các hằng số như `WORDS_PER_CYCLE = 2` và comment giả định beat 64 bit).

### 5.9 `IACT_RAM_CELLS`: số bank của bộ đệm iact (2026-10-14)

- **Là gì:** số bank RAM của **bộ đệm activation đầu vào cho cả layer** trong `OpenEye_FPGA.v` (`BUFFER_A`, mỗi bank là một `RAM_SP`
  64 bit × 2^`BUFFER_WIDTH` = 4.096 word; bit địa chỉ cao nhất chọn nửa ping/pong). Trong `GET_IACT` các word DMA được ghi lần lượt vào các bank
  (word 1 → bank 0, word 2 → bank 1, ...); trong `CONVERT_IACT` các bank được đọc **song song** theo một cửa sổ trượt để cấp dữ liệu cho 4 `iact_stream_constructor`.
- **Giá trị đang dùng: 4** (Makefile của upstream đặt `IACT_RAM_CELLS=4`; `open_eye_parameters.py` cũng mặc định 4). Dung lượng 4 × 4.096 × 8 byte = 128 KB
  (64 KB mỗi nửa ping/pong, tức 65.536 pixel INT8), đọc 4 × 64 = 256 bit mỗi chu kỳ. Trên ZU7EV mỗi bank là 1 URAM → 4 URAM.
- **Ba thứ cùng tên "RAM_CELLS", đừng nhầm:**
  1. Biến môi trường `RAM_CELLS=32` trong các test Python (`os.environ["RAM_CELLS"]`): **không có tác dụng**, không code nào đọc. Thứ được đọc là `IACT_RAM_CELLS`.
  2. Tham số Verilog `IACT_RAM_CELLS` của `OpenEye_FPGA` (= 4, từ `parameters_FPGA.vh`): **thật sự quyết định** số bank của `BUFFER_A`.
  3. Tham số Verilog `RAM_CELLS` của module `iact_stream_constructor` (mặc định 32 ở dòng 65): được gán lại bằng `.RAM_CELLS(IACT_RAM_CELLS)` = 4 khi
     khởi tạo trong `OpenEye_FPGA.v`, nhưng **bên trong module không dùng ở đâu** (lint `UNUSEDPARAM`). Giá trị 32 chỉ là mặc định khi không ai gán. Comment "32 RAM_SP cells" trong `OpenEye_FPGA.v` và bảng
  tham số trong `doc/OpenEye_FPGA_documentation.md` cũng là mô tả cũ của upstream.
- **Thí nghiệm `IACT_RAM_CELLS=32`** (chỉ đổi tham số, không sửa RTL; 6 case nhỏ, Yosys toàn thiết kế):

| | 4 bank (hiện tại) | 32 bank | Ghi chú |
|---|---:|---:|---|
| 6 case nhỏ | 6/6 PASS | **6/6 PASS** | Chức năng vẫn đúng |
| Tổng chu kỳ | mốc | **+0,4 % đến +4,9 %** (chậm hơn) | Chỉ pha `load_iact` tăng: stream iact được đệm cho đủ bội số của số bank (case `8x1`: 4 → 32 word, hiệu suất bus 100 % → 12 %). `convert` và `compute` không đổi |
| Yosys: LUT / FF | 61.456 / 45.402 | 66.220 / 51.125 | **+4.764 LUT (+7,8 %), +5.723 FF (+12,6 %)**: thanh ghi và bộ chọn rộng theo số bank (ví dụ `iact_to_psum_shift_reg` 2 × 64 × N bit) |
| Bộ nhớ | 4 URAM (Vivado) | 32 URAM (Vivado ước tính; Yosys: +224 RAMB36) | Dung lượng gấp 8 lần |

  **Kết luận:** tăng lên 32 **không có lợi** cho các layer đang đo (chậm hơn một chút, tốn thêm khoảng 8 % LUT, 13 % FF, 28 URAM). Chỉ nên tăng khi một layer
  có activation đầu vào **lớn hơn 64 KB** (ví dụ ảnh 224 × 224 × 3 = 150 KB), lúc đó 4 bank không chứa đủ.

### 5.10 Stride và tham số `STRIDE_ENABLED` (2026-11-08, mặc định 1 từ 2026-11-09)

**Stride** là bước trượt của cửa sổ kernel. Stride 1: cửa sổ đặt tại mọi pixel, output cùng kích thước input. Stride 2: cửa sổ đặt cách 2 pixel theo cả
hai chiều, output còn một nửa chiều rộng và một nửa chiều cao, tức 4 lần ít output (và ít phép nhân) hơn. Mạng hiện đại (ResNet, MobileNet...) dùng Conv
stride 2 để thu nhỏ ảnh thay cho pooling.

**`STRIDE_ENABLED`** là **tham số lúc dựng phần cứng** (Verilog `parameter` của `OpenEye_FPGA.v`, dòng 129; Python `OpenEyeParameters.STRIDE_ENABLED`,
đọc từ biến môi trường, ghi vào `parameters_FPGA.vh`), không phải thanh ghi đổi được lúc chạy. Mỗi layer luôn gửi stride của nó trong thanh ghi cấu hình
(`stride_x_reg`, `stride_y_reg`, 3 bit), nhưng:
- `STRIDE_ENABLED = 1`: `stride_x = stride_x_dma` (giá trị thanh ghi). Bộ dựng stream iact dùng nó để chọn cột input cho từng cột PE (`pec × stride_x`),
  điểm kết thúc vòng x; bộ chuyển đổi dùng nó cho giới hạn `x_bound`, `y_bound`; từ bản sửa #41c, pha ghi ngược dùng nó cho độ dài hàng output.
- `STRIDE_ENABLED = 0` (mặc định, từ upstream `2e3b351`): `stride_x = stride_y = 1` cố định (dòng 369–370). Công cụ tổng hợp coi đó là hằng số và bỏ
  hẳn các phép nhân / so sánh theo stride: mạch nhỏ hơn, nhưng **giá trị stride trong thanh ghi bị bỏ qua**, nên layer stride 2 tính sai (#41). Từ
  2026-11-07 toolchain từ chối layer stride > 1 khi tham số bằng 0.

**Từ 2026-11-09 mặc định là `STRIDE_ENABLED = 1`** (đề xuất 5 của mục 8e, được bạn đồng ý; Python `OpenEyeParameters` và tham số RTL; mục 9 "`STRIDE_ENABLED = 1` làm mặc định"). Đo bằng Vivado (`doc/synth/2026-11-09_route4ns_stride1_zu7ev`): **+155 LUT (+0,25 %), +7 FF**, BRAM / URAM / DSP như cũ, vẫn đạt 250 MHz (WNS +0,042 ns); phần tăng nằm ở `dma_storage` (các trường stride không còn bị lược bỏ), còn phép nhân `pec × stride` trong bộ dựng stream không tốn thêm (`pec` là hằng của từng cột PE, Vivado thay bằng dịch và cộng; ước lượng Yosys +300 LUT là quá cao). Layer stride 1 giữ nguyên số chu kỳ (hồi quy, 12 ca mốc, Bảng 3 đều giống hệt). Muốn mạch nhỏ nhất và chắc chắn không dùng stride thì dựng với `STRIDE_ENABLED=0` (biến môi trường hoặc `export_vivado.py --set STRIDE_ENABLED=0`); toolchain khi đó từ chối layer stride > 1.

## 6. Hướng dẫn chạy công cụ đo hiệu suất

### 6.1 Các công cụ

| Công cụ | File | Vai trò |
|---|---|---|
| Profiler | `src/open_eye/rtl_test_utils.py` → `profile_dma_phases` | Chạy bên trong simulation. Mỗi chu kỳ ghi lại pha, số word DMA vào/ra và chu kỳ chờ bộ nhớ; kết quả vào `profile.json`. Bật bằng `OPENEYE_PROFILE=1` |
| Các case đo | `test/cocotb_fpga/test_profile.py` | 9 layer Conv + 3 model (mốc, mục 6.7); 16 cấu hình Bảng 3 của paper (mục 6.14) |
| Bộ chạy | `tools/run_profile.py` | **Lệnh chính.** Chạy các case song song, so sánh, lưu snapshot |
| Báo cáo | `src/open_eye/profile_report.py` | In bảng từ các `profile.json`; `--compare` để so sánh trước/sau |
| Mô hình bộ nhớ | `src/open_eye/memory_model.py` | Giả lập DDR + AXI DMA (mục 6c). Bật bằng `--mem` |
| Baseline | `doc/perf/baseline_2026-11-04/` | Số liệu mốc của 12 case (bộ nhớ lý tưởng), đo sau hàng O (#37, #17, #39; mốc trước: `baseline_2026-11-02`, sau dòng `wghts_per_pe + 1`) |
| Bảng 3 | `tools/paper_table3.py` | Chạy 16 cấu hình của paper, in bảng theo từng layer và từng pha (mục 6.14) |
| Kiểm tra độc lập | `tools/verify_conv_output.py` | Tính lại layer Conv bằng numpy, kiểm tra từng word output của DUT (cần `OPENEYE_DUMP_VERIFY=1`) |

### 6.2 Chuẩn bị (một lần)

- Đứng ở thư mục gốc của repo: `cd ~/OpenEye_orig`.
- Dùng Python của venv: `venv/bin/python` (đã có cocotb, cocotb-test, tensorflow, open_eye).
- Cần `iverilog` (Icarus Verilog 11) trong `PATH`; máy này đã có sẵn.
- Không cần `source venv/bin/activate` nếu luôn gọi `venv/bin/python ...`.

### 6.3 Chạy nhanh

```bash
# Chạy 6 case nhỏ (khoảng 1–4 phút) và so với baseline:
venv/bin/python tools/run_profile.py -k "not mnist" --compare doc/perf/baseline_2026-11-04

# Chạy cả 12 case mốc (khoảng 15–20 phút; 3 case kiểu MNIST 4–9 phút, 3 model 4–11 phút mỗi case):
venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-11-04 --clock-mhz 250

# Chỉ in bảng, không so sánh:
venv/bin/python tools/run_profile.py -k "8x1_f4_q32"
```

Output gồm: dòng PASS/FAIL của từng case (kèm thời gian chạy), rồi bảng của từng case, rồi bảng tổng hợp (mục 6.5).
Mã thoát khác 0 nếu có case FAIL. 16 case Bảng 3 (`test_profile_paper`) không bao giờ được chọn trừ khi `-k` có chữ `paper` (mục 6.14).

### 6.4 Các tuỳ chọn của `tools/run_profile.py`

| Tuỳ chọn | Ý nghĩa | Ví dụ |
|---|---|---|
| `-k BIỂU_THỨC` | Chọn case theo tên (cú pháp `-k` của pytest); case Bảng 3 chỉ được chọn khi biểu thức có `paper` | `-k q32`, `-k "not mnist"`, `-k "mnist2 or 32x3"`, `-k model`, `-k paper_cr2_x4_y3` |
| `--jobs N` | Số case chạy song song (mặc định 3). Máy 12 nhân, 7 GB RAM: tối đa khoảng 4–6 | `--jobs 4` |
| `--compare DIR` | So với snapshot trong `DIR` (lặp lại được) | `--compare doc/perf/baseline_2026-11-04` |
| `--clock-mhz F` | Đổi chu kỳ ra µs ở clock F (bảng theo layer) | `--clock-mhz 250` |
| `--save DIR` | Lưu các `profile.json` mới thành `DIR/<case>.json` | `--save doc/perf/bias_fix_2026-10-12` |
| `--report FILE` | Ghi báo cáo markdown ra file | `--report doc/perf/bias_fix_2026-10-12.md` |
| `--mem PRESET` | Bật mô hình bộ nhớ: `ideal`, `typical`, `slow` (mục 6c) | `--mem typical` |
| `--mem-set K=V` | Đổi một tham số bộ nhớ (lặp lại được): `latency`, `burst_beats`, `outstanding`, `bandwidth`, `fifo_beats`, `setup`, `jitter`, `seed` | `--mem typical --mem-set latency=60` |

Log của từng case: `test/.temp/run_profile_logs/<case>.log`. Log chi tiết của simulation: `test/.temp/<thư mục case>/cocotb_sim.log`.

### 6.5 Đọc báo cáo

Bảng của một case (không so sánh):

| Cột | Ý nghĩa |
|---|---|
| `phase` | Pha của layer (mục 5.1) |
| `cycles`, `share` | Số chu kỳ ở pha đó và tỉ lệ trên tổng |
| `DMA in` / `DMA out` | Số word DMA vào/ra trong pha. `(N refused)`: word host đưa nhưng DUT không nhận |
| `mem stall` | Chu kỳ chờ bộ nhớ: DUT sẵn sàng nhận nhưng không có dữ liệu, hoặc có kết quả nhưng host chưa nhận. Bằng 0 khi bộ nhớ lý tưởng |
| `payload B` | Số byte tối thiểu cần chuyển (mục 5.3); chỉ có cho `Convolution_Single` |
| `bus eff.` | Hiệu suất bus = payload ÷ (số word × độ rộng bus) |

Dòng đầu của mỗi case: `total` (tổng chu kỳ và ns), `compute` (tỉ lệ tính toán), `DMA busy` (tỉ lệ chu kỳ bus có dữ liệu),
`waiting for memory` (tỉ lệ chu kỳ chờ bộ nhớ).

Bảng so sánh (`--compare`): mỗi pha có `cycles base → new`, `change` (tuyệt đối và %), số word DMA trước/sau, `mem stall` trước → sau,
hiệu suất bus trước → sau. Dòng **TOTAL** là tổng. Bảng **Summary** cuối cùng gồm mỗi case một dòng.
- `WARNING: configuration differs`: hai bên khác cấu hình (kích thước, DMA, `QUANT_AMOUNT`,…), nên so sánh không công bằng.
- `memory model: A -> B`: hai bên dùng mô hình bộ nhớ khác nhau. Đây là thông tin, không phải lỗi.
- `(not run)`: case có trong baseline nhưng không chạy lần này (ví dụ do `-k`). `(not in baseline)`: case mới.

Model nhiều layer có thêm **bảng theo layer** (mục 6.13) và, từ 2026-11-02, **bảng hàm kích hoạt** (mục 6.15: `load_act`, chu kỳ khối kích hoạt, % số 0 / số âm ở input).

### 6.6 Quy trình đánh giá một tối ưu

1. Tạo branch hoặc commit riêng cho thay đổi (RTL hoặc Python).
2. Kiểm tra đúng sai trước: các test chức năng liên quan (ví dụ `test_conv_const.py`) phải PASS.
3. Đo: `venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-11-04 --clock-mhz 250`.
   Mô phỏng là tất định, nên **mọi chênh lệch đều do thay đổi của bạn gây ra**.
4. (Tuỳ chọn) đo thêm với bộ nhớ thực tế hơn: thêm `--mem typical`, và so với `doc/perf/mem_typical_2026-10-10` (đo trước bản sửa lỗi #18; với 5 case `q32` chỉ `32x3_f16` khác, −96 chu kỳ).
5. Nếu giữ thay đổi: lưu snapshot và báo cáo, rồi commit:
   ```bash
   venv/bin/python tools/run_profile.py --jobs 4 --save doc/perf/<tên>_<ngày> \
       --report doc/perf/<tên>_<ngày>.md --compare doc/perf/baseline_2026-11-04
   git add -f doc/perf/<tên>_<ngày>/*.json doc/perf/<tên>_<ngày>.md
   ```
   (`-f` vì `.gitignore` của upstream bỏ qua `*.json`/`*.csv`/`*.txt`.)
6. Ghi kết quả vào mục Nhật ký của file này.
7. Nếu sửa RTL: chạy lint (mục 9c); warning mới thì sửa, hoặc chấp nhận bằng `--update` kèm lý do.

### 6.7 Các case đo

**9 case một layer** (`test_profile_conv`): một layer `Convolution_Single`, kernel 3×3, ramp activation, 2×2 cluster, `NUM_GLB_IACT=1`, psum 20 bit.
Thêm 3 case cả model (bên dưới) và 16 case Bảng 3 của paper (`test_profile_paper`, mục 6.14, không nằm trong mốc).

| Case | Input (X×Y×C) | Filter | QUANT_AMOUNT | DMA | Thời gian chạy | Nhóm |
|---|---|---:|---:|---:|---:|---|
| `8x1_f4_q1024_dma64` | 8×1×4 | 4 | 1024 | 64 | ~4 phút | nhỏ (2026-10-09) |
| `8x1_f4_q32_dma64` | 8×1×4 | 4 | 32 | 64 | ~15 s | nhỏ |
| `16x3_f4_q32_dma64` | 16×3×4 | 4 | 32 | 64 | ~15 s | nhỏ |
| `32x3_f4_q32_dma64` | 32×3×4 | 4 | 32 | 64 | ~15 s | nhỏ |
| `32x3_f16_q32_dma64` | 32×3×4 | 16 | 32 | 64 | ~20 s | nhỏ |
| `32x3_f4_q32_dma32` | 32×3×4 | 4 | 32 | 32 | ~15 s | nhỏ |
| `mnist1_28x28_c4_f32_q32_dma64` | 28×28×4 | 32 | 32 | 64 | ~7 phút | kiểu MNIST (0.3) |
| `mnist2_14x14_c32_f32_q32_dma64` | 14×14×32 | 32 | 32 | 64 | ~9 phút | kiểu MNIST |
| `mnist3_8x8_c32_f32_q32_dma64` | 8×8×32 | 32 | 32 | 64 | ~4 phút | kiểu MNIST |

**Vì sao giữ các case nhỏ cũ (không xoá):**
- Chúng là mốc của mọi so sánh đã làm; xoá đi thì mất tính liên tục của số liệu.
- Chạy rất nhanh (khoảng 15 giây), phù hợp để kiểm tra nhanh trong lúc sửa code (`-k "not mnist"`).
- Mỗi case nhỏ cô lập một yếu tố: `q1024` so với `q32` (bảng lượng tử), `dma32` so với `dma64` (độ rộng bus), `f16` so với `f4` (số filter).
- Các case kiểu MNIST cho **tỉ lệ thực tế** giữa các pha, nhưng chạy lâu; dùng chúng để xác nhận kết quả cuối.

**Vì sao các case MNIST bị "thu nhỏ" so với model thật:**

| Layer thật | Case dùng | Lý do khác |
|---|---|---|
| Conv1: 28×28, 1 → 32 | 28×28, **4** → 32 | Lúc lập mốc, 1 channel với ảnh rộng 28 còn lỗi #17 (từ 2026-10-22 có đệm channel bằng Python; giữ case cũ cho mốc liên tục) |
| Conv2: 14×14, 32 → **64** | 14×14, 32 → **32** | Ban đầu: `IndexError` với 64 filter. Thực ra là giới hạn cấu hình (#8): 64 filter cần `QUANT_AMOUNT=64`. Giữ 32 để không đổi mốc |
| Conv3: **7×7**, 64 → 64 | **8×8**, 32 → 32 | 7×7 có cột đệm; phần cứng ghi giá trị khác 0 vào ô đệm nên kiểm tra chuỗi DMA FAIL (giá trị thật vẫn đúng, lỗi #9). 64 → 32 như trên |

Khảo sát ngày 2026-10-10 (đều `QUANT_AMOUNT=32`, `NUM_GLB_IACT=1`): **PASS**: 8/16/32 channel, 32 filter, 14×14, 28×28, 8×8.
**FAIL**: 64 filter (lỗi Python), 7×7 (ô đệm).

**Cập nhật 2026-10-15:** 9 case vẫn giữ kích thước "thu nhỏ" để mốc so sánh liên tục. Các layer MNIST **đúng kích thước thật** được kiểm tra riêng trong
`test/cocotb_fpga/test_mnist_layers.py::test_mnist_conv`: Conv2 (14×14, 32 → 64, `QUANT_AMOUNT=64`) **PASS** từ sau bản sửa lỗi #18; Conv3 đúng mọi giá trị
nhưng còn lỗi #9; Conv1 PASS từ 2026-10-22 nhờ đệm channel (lỗi #17). Từ 2026-10-24 có thêm `test_trained_mnist_conv` (weight MNIST int8 đã huấn luyện).
Lưu ý: trước bản sửa lỗi #18, các case > 4 channel chỉ "PASS" vì weight hằng số che lỗi (mục 9).

**Cập nhật 2026-10-22: ba case "cả model"** (`test_profile_model`, chạy nối tiếp trên chip, dữ liệu ngẫu nhiên với seed cố định `OPENEYE_SEED=1`):

| Case | Model | QUANT_AMOUNT | Thời gian chạy |
|---|---|---:|---:|
| `model_mnist16_c2` | `LAYER=MNIST`: Conv 28×28×2→16, MaxPool, Conv 16→16, MaxPool, Conv 7×7 16→16, Dense 784→10 | 32 | ~4 phút |
| `model_mnist_real_c2` | `LAYER=MNIST_REAL` = kiến trúc `models/mnist_conv_net.py` (Conv 32, MaxPool, Conv 64, MaxPool, Conv 64, FC 3136→10), đầu vào 2 channel ngẫu nhiên | 64 | ~11 phút |
| `model_mnist_real_c1` | Như trên với **đầu vào 1 channel (đúng model thật)**; chạy 1 channel thật từ hàng O (2026-11-04; trước đó testbench đệm thành 2 channel, channel thêm toàn 0, lỗi #17) | 64 | ~11 phút |

`-k "not model"` chỉ chạy 9 case một layer; `-k model` chỉ chạy 3 case model. Mốc gồm cả 12 case: `doc/perf/baseline_2026-11-04/` (mục 6.13, 7; weight Conv ngẫu nhiên giữ số 0 thật từ bản sửa #22).

### 6.8 Thêm một case mới

Thêm một dòng vào `CASES` trong `test/cocotb_fpga/test_profile.py`:
`"tên_case": (width, height, channels, filters, QUANT_AMOUNT, DMA_BITWIDTH)`. Tên case không được chứa dấu `]`.
Chạy thử với `-k tên_case`; nếu PASS thì thêm vào snapshot bằng `--save` (một snapshot có thể được bổ sung từng case).

### 6.9 Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Case FAIL | Kết quả phần cứng sai, hoặc chuỗi DMA khác file tham chiếu | Xem `test/.temp/run_profile_logs/<case>.log` và `cocotb_sim.log` (tìm `Difference found`, `result check failed`) |
| Chạy rất lâu rồi FAIL với `No FSM progress for 100000 cycles` | FSM bị treo (ví dụ lỗi `GET_BIAS` với bộ nhớ có khoảng trống, mục 9) | Với layer nhỏ, đặt `OPENEYE_FAIL_ON_STALL=5000` để dừng sớm. `profile.json` có mục `pending` (ghi lại mỗi 1024 chu kỳ) cho biết pha đang kẹt và số word đã nhận |
| `No FSM progress for N cycles` ở một pha nạp (ví dụ `(4, 0, 0)` = `GET_WGHT`) với layer lớn | **Báo động giả**: bộ phát hiện treo không coi việc nhận từng word trong `GET_*` là tiến triển. Một pha nạp dài hơn N chu kỳ (ví dụ 3840 word weight × 1,44 chu kỳ với `typical`) sẽ bị coi là treo | Đừng đặt `OPENEYE_FAIL_ON_STALL` nhỏ hơn số word lớn nhất của một pha nhân hệ số chậm của bộ nhớ; mặc định 100000 là an toàn |
| `warning: ... passed but wrote no profile.json` | `OPENEYE_PROFILE` không tới được simulation | Chạy qua `tools/run_profile.py` hoặc `test_profile.py` (cả hai đều tự đặt biến này) |
| Mọi thứ chậm bất thường | Case `QUANT_AMOUNT=1024` (mục 5.6), hoặc chạy quá nhiều job song song | `-k q32`, giảm `--jobs` |
| Nghi ngờ DUT nhận sai dữ liệu (thừa, thiếu, lệch thứ tự) | — | Chạy với `OPENEYE_TRACE_DMA=1`, rồi `python3 tools/check_dma_trace.py test/.temp/<thư mục case>` |
| Số liệu lạ | Đọc nhầm `profile.json` cũ | `run_profile.py` luôn xoá file cũ trước khi chạy; nếu chạy pytest trực tiếp thì tự xoá |
| Muốn chắc kết quả đúng thật, không chỉ "PASS" | Testbench so với tham chiếu do cùng gói Python tạo ra; weight hằng số có thể che lỗi (lỗi #18) | Chạy với dữ liệu ngẫu nhiên (`random_data=True`) và `OPENEYE_DUMP_VERIFY=1`, rồi `tools/verify_conv_output.py` (mục 6.12) |

### 6.10 Profiler hoạt động thế nào

Coroutine cocotb lấy mẫu **mỗi cạnh lên của clock**. Với mỗi chu kỳ, nó xác định pha (hàm `profile_phase`: FSM chính; `readout` khi FSM psum
ở `PSUM_SEND_RESULTS`; ở trạng thái 11 `RECEIVE_PSUMS_TO_IACT` thì FSM psum tách `compute` với `writeback`, mục 6.13) và đếm: `cycles`, `in_offered` (host đưa word), `in_accepted` (`enable_dma_i_reg & ready_dma_o`),
`out_words` (`enable_dma_o & ready_dma_i`), `in_stall` (pha nạp, DUT sẵn sàng nhưng không có word), `out_stall` (có kết quả nhưng
`ready_dma_i` thấp). Cửa sổ đo bắt đầu từ word vào đầu tiên được nhận và kết thúc ở word ra cuối cùng. File `profile.json` được ghi lại
mỗi khi đổi pha và sau mỗi word ra, nên vẫn còn khi test FAIL hoặc treo.
Từ 2026-11-02 (mục 6.15) coroutine còn đọc dây trace `UNPACKED_TRACES.act_capture` mỗi chu kỳ (`activation_cycles` của layer), và testbench ghi số 0 / số âm
ở input của từng layer từ tham chiếu (`profile_set_layer_input`).

Cùng các bộ đếm đó được giữ **theo từng layer** (`layers` trong `profile.json`, mục 6.13). Payload và hiệu suất bus: cho `Convolution_Single` ở bảng pha,
và cho từng layer Conv/Dense của một model ở bảng layer. Từ 2026-10-22 đo được cả model MNIST (3 case `test_profile_model`), từ 2026-10-24 cả mạng
Bảng 2 của paper trên 16 cấu hình (mục 6.14).
**Lưu ý:** bộ đếm của một layer chỉ được "chốt" khi có word kết quả ra; nếu test dừng giữa chừng (kiểm tra bộ đệm sai, treo) thì các layer đều 0 trong
`layers` (số liệu nằm ở `pending`). Muốn đo đủ mọi layer khi có lỗi thì bật `OPENEYE_KEEP_GOING=1`.

### 6.11 Công thức tính (chi tiết)

Mỗi cạnh lên của `clk_i`, profiler đọc 4 tín hiệu bắt tay của RTL (giá trị tại cạnh clock, cũng là giá trị RTL dùng ở cạnh đó):
`v_in = enable_dma_i_reg` (bản đã qua thanh ghi của `enable_dma_i`), `r_in = ready_dma_o`, `v_out = enable_dma_o`, `r_out = ready_dma_i`.

| Đại lượng (mỗi chu kỳ, cộng dồn vào pha của chu kỳ đó) | Công thức |
|---|---|
| `cycles` | +1 |
| `in_offered` | `v_in` |
| `in_accepted` (word vào thật sự được nhận) | `v_in · r_in` (đúng điều kiện RTL dùng để nhận word) |
| `out_words` (word kết quả được gửi) | `v_out · r_out` |
| `in_stall` (chỉ ở pha `load_*`) | `r_in · (1 − v_in)`: DUT sẵn sàng nhưng bộ nhớ chưa có word |
| `out_stall` | `v_out · (1 − r_out)`: có kết quả nhưng phía ghi chưa nhận |

- **Pha của chu kỳ** (`profile_phase`): `readout` nếu FSM psum ở `PSUM_SEND_RESULTS` (5) hoặc đang có `out_word`; nếu FSM chính ở 11 (`RECEIVE_PSUMS_TO_IACT`,
  layer nối tiếp) thì `compute` khi FSM psum ở 1–3 (`WAIT_TO_SEND_READY_SIGNAL`, `CALCULATE_PSUM`, `PSUM_GET_RESULTS`) và `writeback` khi ở trạng thái khác
  (`SEND_PSUM_TO_IACT`, ...); ngược lại theo trạng thái FSM chính (bảng mục 5.1). Layer đơn không vào trạng thái 11 nên số liệu cũ không đổi.
- **Ranh giới layer:** một layer mới bắt đầu ở mỗi lần FSM chính vào `GET_PARAMETERS` (1), tức mỗi stream layer. Bộ đếm của mọi layer cộng lại đúng bằng `phases`.
- **Cửa sổ đo:** từ chu kỳ có `in_accepted` đầu tiên tới chu kỳ có `out_words` cuối cùng (cả hai đầu đều tính). Các chu kỳ sau word ra cuối nằm ở `pending`, không tính.
  Vì vậy **độ trễ layer** = `total_cycles` = Σ `cycles` của mọi pha = số chu kỳ từ khi DUT nhận word cấu hình đầu tiên tới khi gửi xong kết quả cuối.
  Không gồm: thời gian trước word đầu (reset, CPU cấu hình DMA), độ trễ của burst đầu tiên khi bật mô hình bộ nhớ, và overhead phần mềm.
- **Báo cáo** (`profile_report`), với `W = DMA_BITWIDTH/8` byte mỗi word:
  - `share` = `cycles(pha) / total_cycles`
  - `compute` = `cycles(compute) / total_cycles`
  - `DMA busy` = `Σ (in_accepted + out_words) / total_cycles` (tỉ lệ chu kỳ có word trên bus; tối đa có thể vượt 100 % nếu vào và ra cùng chu kỳ)
  - `waiting for memory` = `Σ (in_stall + out_stall) / total_cycles`
  - `bus eff.` = `payload(pha) / ((in_accepted + out_words) · W)`; payload theo mục 5.3 (cho `Convolution_Single`)
  - `bus eff.` của một layer trong model = `Σ payload(pha) / (Σ (in_accepted + out_words) · W)` trên các pha có payload; payload tính từ kích thước
    layer: Conv `X·Y·C` iact (chỉ layer đầu), `F·C·Kx·Ky` weight, `F·⌈psum/8⌉` bias, `⌈F·40/8⌉` bảng lượng tử, `⌈X/s⌉·⌈Y/s⌉·F·⌈psum/8⌉` readout
    (chỉ layer cuối); Dense `K` iact, `K·N` weight, `N·⌈psum/8⌉` bias và readout; Pooling không tính
  - `change` = `new − base`, phần trăm = `(new − base) / base`
  - `total ... ns` = `total_cycles × CLOCK_NS`. **Chú ý:** `CLOCK_NS` là chu kỳ clock **giả định của mô phỏng** (10 hoặc 20 ns), không phải clock thật.
- **Đổi ra thời gian thật:** `t = total_cycles / f_clk`, với `f_clk` lấy từ Vivado sau route (hiện 250 MHz, tức 4 ns/chu kỳ).
  Ví dụ `mnist1`: 55.048 × 4 ns = 220,2 µs. Báo cáo đổi sẵn khi chạy với `--clock-mhz 250`.
- **Ví dụ kiểm tra tay** (`8x1_f4_q32_dma64`, baseline): pha 18 + 4 + 120 + 32 + 20 + 179 + 161 + 34 = **568** chu kỳ; word vào 194, ra 32, tổng 226 →
  `DMA busy` = 226/568 = 39,8 %, `compute` = 161/568 = 28,3 %. Weight: payload 4 × 4 × 3 × 3 = 144 B, bus 120 × 8 = 960 B → 15 %.
  Bias: 4 × 3 = 12 B / (32 × 8) = 5 %. Readout: 8 × 1 × 4 = 32 output × 3 B = 96 B / (32 × 8) = 38 %.

### 6.12 Kiểm tra độc lập từng word (`tools/verify_conv_output.py`, 2026-10-15)

**Vì sao cần:** testbench so DUT với tham chiếu do cùng gói Python (`layer_parameters`, mapper) tạo ra, và các test cũ dùng weight hằng số, nên một lỗi chung của
hai bên hoặc một lỗi "đọc nhầm weight" (lỗi #18) vẫn PASS.

**Cách làm:**
1. Chạy layer Conv với `OPENEYE_DUMP_VERIFY=1`: testbench ghi `verify_layer0.pkl` vào thư mục mô phỏng (input, weight, bias đúng như DUT nhận; tham chiếu;
   `output_order` = (filter, x, y) của từng ô psum trong stream ra, `None` cho ô đệm).
2. `venv/bin/python tools/verify_conv_output.py test/.temp/<thư mục mô phỏng> [...]`. Công cụ:
   - tính lại cả layer bằng numpy (hướng kernel theo Keras: `dram.weights[c][f][ky][kx] = kernel[kx][ky][c][f]`), độc lập với code tham chiếu của OpenEye;
   - tách mỗi word 64 bit của DUT (`demo/layer_0_0/output.txt`) thành 2 psum 20 bit có dấu, đặt vào vị trí theo `output_order`, so **từng giá trị**;
   - kiểm tra mỗi (filter, x, y) xuất hiện **đúng một lần**, không có `X`, bit phía trên 2 psum bằng 0, tham chiếu của testbench cũng bằng numpy;
   - in thêm kết quả với kernel chuyển vị làm đối chứng (phải khác hẳn, chứng tỏ phép so sánh có khả năng phân biệt);
   - phân loại các dòng khác file tham chiếu: dòng đệm thuần (DUT gửi psum của ô PE không dùng) hay dòng có kết quả.
3. Mã thoát 0 khi mọi giá trị đúng và đủ vị trí.

Dữ liệu ngẫu nhiên: `_run_conv_const(..., random_data=True)` bỏ các hook hằng số/dốc. Các test `test_mnist_layers.py::test_random_data`, `test_mnist_conv` và
`test_trained_mnist_conv` tự chạy công cụ sau mô phỏng.

### 6.13 Đo pha khi chạy cả model (theo từng layer, 2026-10-22)

**Vấn đề trước đây:** profiler cộng dồn mọi layer vào một bảng pha, và với layer nối tiếp (kết quả ghi ngược vào bộ đệm iact cho layer sau) thì
FSM chính **tính toán ngay trong trạng thái 11** `RECEIVE_PSUMS_TO_IACT`, nên toàn bộ thời gian tính bị ghi thành `writeback` (`compute = 0`).

**Cách làm bây giờ** (chỉ Python, không đổi RTL):
1. `rtl_test_utils.profile_phase(main, psum, out_word)`: ở trạng thái 11, FSM psum ở 1–3 là `compute`, ở trạng thái khác là `writeback`.
2. `profile_dma_phases` mở một layer mới mỗi lần FSM chính vào `GET_PARAMETERS`; mỗi layer có bộ đếm riêng (cùng 6 đại lượng như mục 6.11), cùng quy
   tắc cửa sổ đo; tổng các layer = `phases`.
3. Testbench gọi `rtl_test_utils.profile_set_layer_info(layer_parameters)` (khi `OPENEYE_PROFILE=1`) để ghi tên và kích thước từng layer.
4. `OPENEYE_SEED=<n>` cố định dữ liệu ngẫu nhiên bằng `tf.keras.utils.set_random_seed` (Python `random`, numpy của `DRAMContents`, khởi tạo weight của
   Keras), vì phần sparse làm số chu kỳ phụ thuộc dữ liệu. `tf.random.set_seed` thôi là **không đủ**: Keras 3 có bộ sinh seed riêng, lần thử đầu cho 2 lần
   chạy lệch 5 chu kỳ ở layer Dense.
5. `profile_report` in thêm **bảng theo layer** và so sánh theo layer khi `--compare`; `--clock-mhz 250` đổi chu kỳ ra µs ở clock thật.

```bash
venv/bin/python tools/run_profile.py -k model --clock-mhz 250                                     # 3 case model
venv/bin/python tools/run_profile.py -k model --compare doc/perf/baseline_2026-11-04 --clock-mhz 250
venv/bin/python -m open_eye.profile_report --clock-mhz 250 doc/perf/baseline_2026-11-04/model_mnist_real_c2.json
```

Khi `--compare`, case có trong mốc được so từng pha và từng layer (`cycles base/new`, `DMA words base/new`); case chưa có trong mốc được in báo cáo đầy đủ
(kèm bảng layer).

`profile.json` có thêm `layers`: mỗi phần tử gồm `index`, `start_cycle`, `total_cycles`, `phases` (như `phases` tổng) và `info` (`name`, `iact_size_x/y`,
`channels`, `filters`, `kernel`, `stride`, `skip_iact`, `send_values_out`, `pad_channels` = số channel 0 thêm cho lỗi #17).

**Kết quả `model_mnist_real_c2` đo ngày 2026-10-22** (kiến trúc MNIST thật, đầu vào 2 channel, bộ nhớ lý tưởng, `OPENEYE_SEED=1`): **244.050 chu kỳ = 976 µs ở 250 MHz**.
Sau bản sửa #22 (`baseline_2026-10-24`, weight ngẫu nhiên giữ số 0 thật; mốc hiện tại `baseline_2026-11-02` ít hơn 673 / 673 / 77 chu kỳ): `_c2` 243.517, `_c1` 240.671, `model_mnist16_c2` 50.007 chu kỳ; Conv2
giảm 355, Conv3 giảm 237 chu kỳ, các layer khác gần như không đổi (mục 7).

| # | Layer | Chu kỳ | Tỉ lệ | µs @250 MHz | load (cấu hình, iact, lượng tử) | load_wght | load_bias | convert | compute | writeback | pooling | DMA vào | bus eff. |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | Conv 28×28×2→32 | 35.591 | 14,6 % | 142,4 | 254 | 480 | **14.336** | 1.091 | 12.193 | 7.237 | 0 | 15.070 | 2 % |
| 1 | Pool 28×28×32 | 5.213 | 2,1 % | 20,9 | 61 | 0 | 0 | 0 | 0 | 0 | 5.152 | 18 | |
| 2 | Conv 14×14×32→64 | 121.162 | **49,6 %** | 484,6 | 61 | 15.360 | 7.168 | 4.679 | **90.193** | 3.701 | 0 | 22.586 | 10 % |
| 3 | Pool 14×14×64 | 2.861 | 1,2 % | 11,4 | 61 | 0 | 0 | 0 | 0 | 0 | 2.800 | 18 | |
| 4 | Conv 7×7×64→64 | 65.210 | 26,7 % | 260,8 | 61 | 15.360 | 1.792 | 2.951 | 44.033 | 1.013 | 0 | 17.210 | 27 % |
| 5 | Dense 3136→10 | 14.013 | 5,7 % | 56,1 | 61 | 7.920 | 12 | 1.655 | 4.351 | 0 | 0 | 7.990 | 49 % |

Cả model: tính toán 61,8 %, nạp weight 16,0 %, nạp bias 9,6 % (40 % của Conv1), ghi ngược 4,9 %, chuyển đổi iact 4,3 %, pooling 3,3 %.
`model_mnist16_c2`: 50.020 chu kỳ = 200 µs (tính toán 44 %, nạp bias 19 %, nạp weight 10 %, ghi ngược 10 %, chuyển đổi iact 9 %).
**`model_mnist_real_c1`** (đúng model thật, đầu vào 1 channel được đệm thành 2, mục 9): **241.250 chu kỳ = 965 µs**; chỉ Conv1 khác (32.980 chu kỳ, 131,9 µs,
tính toán 9.582 thay vì 12.193 vì activation 0 của channel đệm được bỏ qua; số word DMA như `_c2`); 5 layer sau lệch `_c2` không quá 160 chu kỳ (dữ liệu khác).
Bảng theo layer ghi `Conv 28x28x1+1pad->32 k3x3`.
Layer có kích thước iact 7×7 dùng kernel 3×3 (nhãn `Conv 7x7x64->64 k3x3`).

**Model MNIST đã huấn luyện chạy thật trên chip (đo 2026-10-31, sau bản sửa #31, #32; `doc/perf/trained_mnist_2026-10-31.md`, file
`doc/perf/trained_mnist_2026-10-31/*.json`):** `SimpleMNISTConvNet` với checkpoint đã huấn luyện, qua toolchain (`onnx2model` lượng tử tĩnh int8), input là ảnh
test MNIST 0, 1, 2, 7 (chuẩn hoá như lúc huấn luyện, lượng tử bằng scale input 0,0222, đệm 2 channel), cấu hình như `model_mnist_real_c1`, bộ nhớ lý tưởng; mọi
kiểm tra khớp từng bit, lớp đúng cả 4 ảnh. Chạy: `doc/experiments/2026-10-30_bug32/run35.py prof_img0 0 OPENEYE_PROFILE=1`.

| Ảnh | Chu kỳ | µs @250 MHz | Conv1 | Pool1 | Conv2 | Pool2 | Conv3 | Dense |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 219.598 | 878,4 | 32.980 | 5.213 | 112.458 | 2.861 | 52.978 | 13.108 |
| 1 | 220.941 | 883,8 | 32.980 | 5.213 | 112.586 | 2.861 | 54.270 | 13.031 |
| 2 | 213.040 | 852,2 | 32.980 | 5.213 | 108.423 | 2.861 | 50.538 | 13.025 |
| 7 | 218.374 | 873,5 | 32.980 | 5.213 | 110.858 | 2.861 | 53.458 | 13.004 |
| `model_mnist_real_c1` (mốc, dữ liệu ngẫu nhiên) | 240.671 | 962,7 | 32.980 | 5.213 | 120.807 | 2.861 | 64.813 | 13.997 |

Ảnh 0 theo pha: tính toán 126.318 (57,5 %), nạp weight 39.120 (17,8 %), nạp bias 23.308 (10,6 %), ghi ngược 11.951 (5,4 %), chuyển đổi iact 10.376 (4,7 %),
pooling 7.952 (3,6 %). Mọi pha trừ tính toán giống hệt dữ liệu ngẫu nhiên (stream chỉ phụ thuộc kích thước). Tính toán phụ thuộc số 0 (bỏ qua số 0): input Conv1
0 % số 0 (nền −19) → không đổi; Conv2 44 % số 0 (ngẫu nhiên 6 %) → −9 %; Conv3 87 % (ngẫu nhiên 11 %) → −27 %; Dense 74 % (ngẫu nhiên 10 %) → −21 %. Dữ liệu ngẫu nhiên chỉ không có số 0
ở channel ảnh của layer đầu; sau đó giá trị nhỏ sau phép dịch 7 bit (không ReLU) cũng có số 0. **Lợi ích nhỏ hơn nhiều so với tỉ lệ số 0** vì mỗi lượt
vẫn tốn phần cố định (nạp, bắt tay lượt, đọc psum của từng lượt): ứng viên tối ưu độ trễ.

**Cách đọc:**
- `load` = `load_config + load_iact + load_quant` (+ `load_act` từ 2026-11-02). Chỉ layer đầu nạp iact (196 chu kỳ); các layer sau đọc iact từ bộ đệm (`skip_iact`).
- Layer cuối (Dense) không ở trạng thái 11 mà ở trạng thái 10 (chờ kết quả) nên `writeback = 0`, và chỉ layer cuối có `readout`.
- `bus eff.` thấp ở Conv1 (2 %) vì 14.336 word bias chỉ chứa 32 giá trị khác nhau: đúng chỗ tối ưu "bias theo filter" (mục 8c) có lợi nhất.
- Ở layer pooling, FSM vẫn ở pha nạp bảng lượng tử 40 chu kỳ (`QUANT_AMOUNT=64`; 20 với 32) nhưng **không nhận word nào** (driver đưa 40 word, chip
  từ chối cả 40): 80 chu kỳ phí trên cả model, ứng viên nhỏ cho Giai đoạn 1.
- Ngưỡng phát hiện treo của case model là 400.000 chu kỳ (`OPENEYE_FAIL_ON_STALL`), vì Conv2 tính 90.000 chu kỳ trong cùng một trạng thái.

**Kiểm chứng (2026-10-22):**
- 9 case một layer: mọi bộ đếm của mọi pha trùng với `baseline_2026-10-15` (tổng chu kỳ và số word ở bảng tóm tắt của `run_profile` lệch 0).
- 2 case model: tổng các layer = tổng `phases` (từng pha, từng bộ đếm); `start_cycle` trùng với chu kỳ bắt đầu layer mà testbench ghi; chạy 2 lần cùng
  `OPENEYE_SEED=1` cho file `profile.json` giống hệt nhau.
- Đối chiếu với bản thử `probe_model.py` (cùng seed, đo độc lập bằng probe riêng): 6/6 layer khớp `start_cycle`, số word DMA vào/ra và mọi pha, sau khi quy đổi
  cách gọi tên (bản thử tách thêm `wait_psum_idle` = FSM psum ở 0 trong trạng thái 11, ở đây tính vào `writeback`; với layer cuối, bản thử gọi phần trạng thái 10
  ngoài FSM psum 1–3 là `writeback`/`wait_psum_idle`, ở đây là `compute` như trước).
- Unit test: `test/test_profile_phases.py` (quy tắc gán pha, thông tin layer) và `test/test_profile_report.py` (bảng theo layer, so sánh, `--clock-mhz`): 34 test pass.
- Mốc mới gồm cả 12 case (thêm `model_mnist_real_c1` cùng ngày, sau bản đệm channel #17): `doc/perf/baseline_2026-10-22/`, báo cáo
  `doc/perf/baseline_2026-10-22.md` (so với `baseline_2026-10-15`, 250 MHz). Mốc sau #22 là `baseline_2026-10-24`; sau đó `baseline_2026-11-02` (dòng `wghts_per_pe + 1`); **mốc hiện tại là `baseline_2026-11-04`** (sau hàng O, mục 7).

### 6.14 Bảng 3 của paper OpenEye, đo bằng profiler theo từng layer (2026-10-24)

Paper: "OpenEye: A Scalable Open-Source Hardware Accelerator for DNNs" (arXiv 2606.01450). Bảng 3 của paper đo mạng ở Bảng 2 (MNIST 8 bit: Conv 16,
MaxPool, Conv 32, MaxPool, Conv 32, Dense 1568→32, Dense 32→10) trên 16 cấu hình: số hàng cluster `CLUSTER_ROWS` 1/2/4/8 × PE trục X (`NUM_GLB_PSUM`) 2/4 ×
PE trục Y (`NUM_GLB_WGHT`) 3/4, ở 200 MHz trên ZU19EG, chỉ với 2 cột "Data Send" và "Proc. Time" cho cả mạng. Paper **không** định nghĩa 2 cột này, không
nói đo bằng cách nào, số cột cluster, `QUANT_AMOUNT` hay độ thưa; repo không có công cụ tạo ra bảng đó.

**Cách đo ở đây** (chỉ Python, RTL của fork): `LAYER=PAPER_MNIST` (`data_create.py`), 16 case `test_profile.py::test_profile_paper` (`CLUSTER_COLUMNS = 2`,
DMA 64 bit, `QUANT_AMOUNT = 32`, `NUM_GLB_IACT = 1`, bộ nhớ lý tưởng, `OPENEYE_SEED=1`, weight ngẫu nhiên có số 0 thật, activation ngẫu nhiên không
thưa), profiler theo layer, thời gian = chu kỳ × 5 ns (200 MHz như paper). `OPENEYE_KEEP_GOING=1`: kiểm tra bộ đệm iact giữa các layer sai thì ghi log và
chạy tiếp, để layer nào cũng được đo; test vẫn FAIL ở cuối.

```bash
venv/bin/python tools/paper_table3.py --run --jobs 6 --save doc/perf/paper_table3_<ngày> --report doc/perf/paper_table3_<ngày>.md
venv/bin/python tools/paper_table3.py doc/perf/paper_table3_2026-10-24        # in lại bảng từ profile đã lưu
```

Kết quả: `doc/perf/paper_table3_2026-10-24.md` (7 bảng theo layer: hàng = cấu hình, cột = 10 pha của profiler; bảng tổng kèm số của paper).

**Tổng cả mạng so với paper** (ns ở 200 MHz; "nạp" = load_config + load_iact + load_wght + load_bias + load_quant (+ load_act nếu có bảng kích hoạt); "xử lý" = phần còn lại):

| CR | X | Y | Tổng (fork) | Nạp | Xử lý | Tỉ lệ nạp | Paper Total | Paper Data Send | Tỉ lệ Data Send (paper) | Tổng / paper |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 3 | 1.031.780 | 155.525 | 876.255 | 15 % | 299.315 | 70.680 | 24 % | 3,45 |
| 2 | 2 | 3 | 659.215 | 172.910 | 486.305 | 26 % | 231.265 | 106.720 | 46 % | 2,85 |
| 4 | 2 | 3 | 464.320 | 180.200 | 284.120 | 39 % | 202.710 | 131.235 | 65 % | 2,29 |
| 8 | 2 | 3 | 370.595 | 184.145 | 186.450 | 50 % | 177.520 | 132.995 | 75 % | 2,09 |
| 1 | 4 | 3 | 667.730 | 160.005 | 507.725 | 24 % | 199.230 | 71.960 | 36 % | 3,35 |
| 2 | 4 | 3 | 448.365 | 153.710 | 294.655 | 34 % | 154.005 | 83.680 | 54 % | 2,91 |
| 4 | 4 | 3 | 340.885 | 144.150 | 196.735 | 42 % | 128.010 | 85.225 | 67 % | 2,66 |
| 8 | 4 | 3 | 313.070 | 148.610 | 164.460 | 47 % | 115.340 | 85.580 | 74 % | 2,71 |
| 1 | 2 | 4 | 1.007.500 | 139.505 | 867.995 | 14 % | 306.095 | 82.785 | 27 % | 3,29 |
| 2 | 2 | 4 | 663.665 | 180.740 | 482.925 | 27 % | 252.680 | 130.660 | 52 % | 2,63 |
| 4 | 2 | 4 | 491.310 | 208.100 | 283.210 | 42 % | 232.535 | 162.355 | 70 % | 2,11 |
| 8 | 2 | 4 | 389.995 | 204.245 | 185.750 | 52 % | 211.880 | 163.135 | 77 % | 1,84 |
| 1 | 4 | 4 | 642.710 | 143.985 | 498.725 | 22 % | 205.105 | 84.045 | 41 % | 3,13 |
| 2 | 4 | 4 | 448.335 | 157.700 | 290.635 | 35 % | 167.460 | 99.920 | 60 % | 2,68 |
| 4 | 4 | 4 | 355.575 | 160.170 | 195.405 | 45 % | 142.365 | 100.985 | 71 % | 2,50 |
| 8 | 4 | 4 | 320.655 | 156.865 | 163.790 | 49 % | 129.165 | 99.915 | 77 % | 2,48 |

**Đọc kết quả:**
- Xu hướng giống paper: tăng cluster và PE trục X giảm thời gian xử lý (Conv2 tính 448.930 → 36.785 ns), lợi ích giảm dần; tỉ lệ nạp dữ liệu tăng theo số
  cluster (fork 15 % → 50 %, paper 24 % → 75 %); PE trục Y = 4 gần như không giúp (kernel 3×3 chỉ dùng 3 hàng PE) mà còn tăng weight phải gửi.
- Con số tuyệt đối gấp 1,8–3,5 lần paper. Phần nạp gấp 1,3–2,2 lần (riêng bias theo từng pixel output đã là 53.980–58.460 ns ở mọi cấu hình; weight 83.000–
  148.000 ns), phần xử lý gấp khoảng 4–5,6 lần. Lý do khả dĩ: phiên bản thiết kế khác, activation ngẫu nhiên không thưa (mạng ReLU thật có nhiều số 0 mà PE
  bỏ qua), paper không nói rõ định nghĩa cột. Tổng nạp đo được khớp ước lượng số word DMA từ bộ sinh stream (ví dụ 153.710 / 153.620 ns).
- Theo layer (CR=2 X=4 Y=3): Conv2 38 %, Conv3 20 %, Conv1 19 %, Dense 1568→32 18 % (nạp weight 66 % của layer), 2 pooling 4,5 %, Dense 32→10 0,4 %.
  Pooling, ghi ngược, chuyển đổi iact và nạp bias **không** nhanh lên khi thêm cluster/PE.

**Độ tin cậy:** số chu kỳ là của chính RTL trong mô phỏng (lặp lại được, cộng các layer = tổng). Kết quả tính: với X = 4, layer 0–4 qua kiểm tra bộ đệm,
layer 5 (Dense nối tiếp Dense) không ghi kết quả vào bộ đệm (lỗi mới #26) nên kết quả cuối sai; với X = 2, kiểm tra sau layer 1, 3, 4, 5 báo sai (lỗi mới #25; kiểm tra sau
layer 0 và 2, conv → pooling, thật ra **không được làm** vì testbench không có bố cục cho input của pooling, xem mục 9). Thời gian của các layer đó vẫn đo được (số word mỗi pha không phụ thuộc giá trị), nhưng đánh dấu FAIL trong bảng.

**Sau bản sửa #25 (2026-10-26, `doc/perf/paper_table3_2026-10-26_fix25.md`):** 13/16 cấu hình PASS cả 7 layer (sửa 31/10: trước đây ghi nhầm 14/16; 7 + 6 = 13, `status.json` có 3 cấu hình FAIL); X = 2 với CR 2/4/8 nay đúng và chậm hơn số đo cũ
4,4–7,8 % (pha ghi ngược Conv trước đây bị cắt nửa chừng); X = 4 không đổi; còn CR 1 X 4 Y 3 (#19b) và CR 1 X 2 (#28). Mốc Bảng 3 lúc đó: `paper_table3_2026-10-26_fix25`.

**Sau dòng `wghts_per_pe + 1` và bước B của hàm kích hoạt (2026-11-02, `doc/perf/paper_table3_2026-11-02.md`):** 13/16 như trước, chu kỳ đúng bằng
số của thí nghiệm `+1` ở cả 16 cấu hình (bước B: 0 lệch). Mốc Bảng 3 lúc đó: `paper_table3_2026-11-02`. Từ bước C, bảng tổng chỉ có thêm cột
`load_act` khi có cấu hình dùng bảng kích hoạt (các bảng cũ in lại y như trước).

**Nguyên nhân 3 cấu hình FAIL (điều tra 2026-11-03, mục 9, `doc/experiments/2026-11-03_table3_cr1.md`):** CR 1 X 4 Y 3 = #29 (tràn bộ đệm weight ở Dense 1568→32, trước đây ghi nhầm là #19b); CR 1 X 2 Y 4 = #28 (thu psum khi cột PE lẻ chưa xong) + #36 (Dense cuối mất output của cụm cột 1); CR 1 X 2 Y 3 = cả ba. Với các bản sửa giả lập/tham số: CR 1 X 4 Y 3 PASS đủ 7 layer; CR 1 X 2 Y 3/Y 4 qua mọi kiểm tra bộ đệm, chỉ còn #36 (cần sửa RTL).

**Sau hàng O (#37, #17, #39; 2026-11-04, `doc/perf/paper_table3_2026-11-04.md`, mốc hiện tại):** 16/16 PASS, layer 0 (Conv 28×28×1 → 16) chạy 1 channel thật ở mọi cấu hình (12 cấu hình trước là "PASS pad"). 12 cấu hình đó bớt 192–408 chu kỳ cả mạng (−0,09 đến −0,39 %; layer 0 −0,6 đến −1,9 %) và 168–384 word DMA, hết ở pha nạp của layer 0 (`load_iact` −96, `load_wght` −72 đến −288, `writeback` −24); `compute` và mọi layer khác giống hệt từng chu kỳ; 4 cấu hình không đệm (CR 4 X 4, CR 8) giống hệt.

**Sau bản sửa #28, #29, #36 (2026-11-03, `doc/perf/paper_table3_2026-11-03.md`): 16/16 cấu hình PASS cả 7 layer**, lần đầu tiên. 13 cấu hình vốn đúng giống hệt từng chu kỳ ở mọi layer; CR 1 X 2 Y 3 −16, CR 1 X 2 Y 4 +16, CR 1 X 4 Y 3 −3 chu kỳ (các layer sau giờ tính trên input đúng). **Mốc Bảng 3 hiện tại: `paper_table3_2026-11-03`.**

**Sau bản sửa #26 (2026-10-24, `doc/perf/paper_table3_2026-10-24_fix26.md`):** 7/8 cấu hình X = 4 **PASS cả 7 layer** (bộ đệm sau mỗi layer và kết quả cuối);
CR 1 X 4 Y 3 còn sai ở Dense 1568→32 (lỗi tính #19b); X = 2 vẫn như cũ (#25). Chu kỳ: layer 0–4 giữ nguyên, pha ghi ngược của layer 5 dài thêm 15–21 chu kỳ,
cả mạng +15 đến +28 chu kỳ (≤ 0,03 %); các bảng thời gian ở trên hầu như không đổi.

### 6.15 Đo hàm kích hoạt bằng profiler (bước C, 2026-11-02)

Chi tiết: `doc/experiments/2026-11-02_activation_profiler.md`; số đo và báo cáo: `doc/perf/activation_2026-11-02.md` (file `activation_2026-11-02/*.json`).
Chỉ Python (testbench và báo cáo); RTL là của bước B, dây trace `act_capture` đã có sẵn từ bước B cho việc này.

**Profiler đo gì:**

| Đại lượng | Lấy từ đâu | Ý nghĩa |
|---|---|---|
| Pha `load_act` (chu kỳ, word DMA) | FSM chính ở trạng thái 15 `GET_ACTIVATION` | Chi phí nạp bảng: 2048 / `DMA_BITWIDTH` word mỗi layer dùng bảng (32 ở DMA 64 bit), 0 nếu `act_keep_table` |
| `activation_cycles` của layer | dây `UNPACKED_TRACES.act_capture` đọc mỗi chu kỳ: pha ghi ngược lấy 4 giá trị lane đã qua hàm kích hoạt | Số chu kỳ khối kích hoạt làm việc; **nằm trong `writeback`**, không phải chu kỳ thêm |
| `info.activation` (mode, round, keep_table) | `LayerParameters` | Layer dùng hàm gì |
| `info.input` (values, zeros, negatives) | tham chiếu của testbench sau `batchnorm_output` (= đúng thứ RTL tính, các kiểm tra bộ đệm khớp từng bit) | Số 0 ở input = thứ mà bỏ-qua-số-0 bỏ qua: chi phí gián tiếp của hàm kích hoạt |
| Payload 256 byte | `layer_payload_bytes` | Hiệu suất bus của bảng trong bảng layer |

`profile_report` in thêm **bảng hàm kích hoạt** (mỗi layer: hàm, `load_act` chu kỳ / word, chu kỳ ghi ngược, chu kỳ kích hoạt, % số 0 và số âm ở input);
cột `load` của bảng layer gồm cả `load_act`; `--compare` so từng pha và từng layer (ví dụ SiLU so với ReLU, đặt 2 profile cùng tên case ở 2 thư mục).

**Kết quả (model MNIST đã huấn luyện, ảnh 0, 250 MHz):**

| | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Tổng chu kỳ | 218.925 (875,7 µs) | 238.049 (952,2 µs) | 240.229 (960,9 µs) | 240.293 (961,2 µs) |
| So với ReLU | | +19.124 (+8,7 %) | +21.304 (+9,7 %) | +21.368 (+9,8 %) |
| trong đó `load_act` | 0 | 0 | +96 (3 layer × 32) | +96 |
| trong đó `compute` | | +19.124 | +21.208 | +21.272 |
| Các pha khác (kể cả `writeback` 11.948) | | 0 | 0 | 0 |
| Số 0 ở input Conv2 / Conv3 / Dense | 43,5 / 87,3 / 74,3 % | 24,3 / 14,7 / 18,1 % | 11,0 / 7,2 / 6,6 % | 5,9 / 14,3 / 13,2 % |
| Compute Conv2 / Conv3 / Dense so với ReLU | | +8,5 / +36,1 / +23,9 % | +10,1 / +38,4 / +26,4 % | +10,4 / +37,8 / +25,5 % |
| **Sau bản sửa #38** (mantissa 24 bit, 2026-11-04) | 218.924 | 238.049 (+8,74 %) | 240.230 (+9,73 %) | 240.287 (+9,76 %) |
| **Sau hàng O** (#17: Conv1 1 channel thật, 2026-11-04) | 218.564 (874,3 µs) | 237.689 (+8,75 %) | 239.870 (+9,75 %) | 239.927 (+9,77 %) |

Bảng trên đo ngày 2026-11-02 với mantissa 8 bit; dòng cuối đo lại sau bản sửa #38 (`doc/perf/activation_2026-11-04_mant24.md`): chỉ `compute` của layer Dense
lệch −1 / 0 / +1 / −6 chu kỳ (vài output Conv3 làm tròn khác nên đổi giữa 0 và khác 0), mọi pha khác, mọi word DMA và 96 chu kỳ `load_act` giữ nguyên, nên các
kết luận dưới đây không đổi. Bảng "cùng một bộ trọng số" phía dưới chưa đo lại (cũng chỉ có thể lệch vài chu kỳ ở Dense).
Dòng "Sau hàng O" (`doc/perf/activation_2026-11-04_rowO.md`): Conv1 không còn đệm thành 2 channel, cả 4 model −360 chu kỳ, hết ở Conv1 (`load_iact` −96,
`load_wght` −240, `writeback` −24; `compute` không đổi vì PE vốn bỏ qua channel đệm toàn 0); chênh lệch giữa các hàm giữ nguyên từng chu kỳ.

- **Khối kích hoạt không tốn thời gian:** ghi ngược giống nhau từng chu kỳ ở cả 4 hàm (chu kỳ kích hoạt 7.174 / 3.590 / 902 ở Conv1/2/3), bảng chỉ tốn 32 chu kỳ
  và 32 word mỗi layer (0,04 % của model). Mục tiêu thiết kế của bước B đạt trên model thật.
- **Chi phí thật là mất số 0:** 99,5–100 % chu kỳ thêm nằm ở `compute`; Conv3 bị nặng nhất (+36–38 %) vì ReLU để lại 87 % số 0 ở input của nó, các hàm khác
  7–15 %. Bước A dự đoán +7,4 / +9,2 / +9,0 % (trung bình 10.000 ảnh); ảnh 0 đo được +8,7 / +9,7 / +9,8 %; tỉ lệ số 0 khớp bước A trong 2 điểm.
- Conv1 có 50 % số 0 ở input ở mọi model: channel 0 thêm cho lỗi #17 (channel ảnh không có số 0, nền là −19). Sau hàng O (RTL sửa #17, không đệm): 0 %.

**Cùng một bộ trọng số** (mỗi model trên có trọng số riêng, huấn luyện với hàm của nó): chạy trọng số ReLU đã huấn luyện với từng hàm thay cho ReLU
(`doc/experiments/2026-11-02_activation/run_same_weights.py <hàm> 0`; trọng số không được huấn luyện cho hàm đó nhưng DUT vẫn ra lớp 7, mọi kiểm tra khớp từng bit):

| Cùng trọng số ReLU, ảnh 0 | ReLU | Leaky ReLU | SiLU | hard-swish |
|---|---:|---:|---:|---:|
| Tổng chu kỳ | 218.925 (875,7 µs) | 238.786 (955,1 µs) | 240.728 (962,9 µs) | 240.560 (962,2 µs) |
| So với ReLU | | +19.861 (+9,1 %) | +21.803 (+10,0 %) | +21.635 (+9,9 %) |
| `load_act` / các pha khác (kể cả `writeback`) | 0 / 0 | 0 / 0 | 96 / 0 | 96 / 0 |
| Số 0 ở input Conv2 / Conv3 / Dense | 43,5 / 87,3 / 74,3 % | 7,5 / 19,5 / 13,7 % | 5,1 / 7,8 / 7,3 % | 5,3 / 13,8 / 14,0 % |

Lệch không quá 0,4 điểm so với bảng trên: chi phí là của hàm kích hoạt (giữ lại các giá trị âm mà ReLU đưa về 0), không phải của trọng số.
- Kiểm chứng thêm: `load_act` = 32 / 32 ở layer có bảng, **0** ở layer giữ bảng (`table_keep_mlp`), **64** ở DMA 32 bit (`table_conv_stack_dma32`), 32 ở
  4 layer Conv/Dense có bảng của mạng paper; 7/7 lần chạy PASS; ReLU ít hơn số ngày 31/10 đúng 673 chu kỳ (dòng `wghts_per_pe + 1`); unit test profiler 41/41;
  12 ca mốc với profiler mới: 12/12 PASS, 0 chu kỳ và 0 word DMA lệch so với `baseline_2026-11-02` (profiler chỉ quan sát).

## 6b. Đo trên mô phỏng so với chạy trên FPGA thật

**Đường dữ liệu thật:** CPU (ARM) → DDR → AXI DMA IP (MM2S) → AXI4-Stream 64 bit → `OpenEye_FPGA` → AXI4-Stream → AXI DMA (S2MM) → DDR.
**Trong cocotb:** testbench Python đóng vai trò "DDR + AXI DMA", đẩy thẳng mỗi chu kỳ một word vào cổng stream và luôn sẵn sàng nhận kết quả.
Phần nằm giữa (`OpenEye_FPGA` và toàn bộ RTL bên trong) **là cùng một RTL** ở cả hai nơi.

### Những gì đo được và mức độ tin cậy khi lên FPGA

| Đại lượng | Mô phỏng đo được? | Trên FPGA (cùng RTL, cùng tham số) |
|---|---|---|
| Số beat DMA vào/ra của mỗi pha | Có, **chính xác** | **Giống hệt.** Số word do giao thức stream quyết định, không phụ thuộc vào DMA |
| Hiệu suất bus (payload ÷ beat) | Có, **chính xác** | **Giống hệt** |
| Số chu kỳ của các pha nội bộ: `convert_iact`, `compute`, `writeback`, `pooling` | Có, **chính xác theo chu kỳ** | **Giống hệt về số chu kỳ.** Thời gian thực = chu kỳ ÷ tần số clock đạt được sau khi tổng hợp |
| Số chu kỳ của các pha nạp (`load_*`) và `readout` | Có, nhưng là **giới hạn dưới** | **Bằng hoặc lớn hơn.** Bằng nếu AXI DMA cấp đủ 1 beat mỗi chu kỳ; lớn hơn nếu DDR hoặc DMA bị ngắt quãng (độ trễ đầu burst, tranh chấp bus) |
| Thứ tự và độ chồng của các pha | Có | Giống hệt (do FSM quyết định) |
| Tổng độ trễ một layer | Giới hạn dưới | Lớn hơn: + thời gian chờ DMA + overhead phần mềm |
| Độ trễ DDR, burst, ngắt quãng `tvalid` | **Ước lượng** bằng mô hình bộ nhớ (mục 6c, tham số chưa hiệu chỉnh theo board) | Có ảnh hưởng thật |
| Overhead phần mềm (flush/invalidate cache, cấu hình DMA, polling, giữa các layer) | **Không** | Có; với layer nhỏ có thể lớn hơn cả thời gian tính |
| Tần số clock tối đa (fmax), tài nguyên, công suất | **Không** (lấy từ Vivado, mục 6d: hiện 250 MHz) | Phụ thuộc kết quả place & route |

**Kết luận:**
- Các tối ưu về **băng thông** (giảm số beat, tăng hiệu suất bus) đo trên mô phỏng là **chính xác** và giữ nguyên khi lên FPGA.
- Các tối ưu **độ trễ bên trong** RTL (giảm chu kỳ convert/compute, chạy chồng pha) cũng chính xác **về số chu kỳ**.
- Con số tổng độ trễ của mô phỏng là **trường hợp tốt nhất về phía bộ nhớ**; trên FPGA sẽ chậm hơn. Mức chậm hơn bao nhiêu
  phụ thuộc vào board, cấu hình AXI DMA (độ dài burst, độ rộng bus) và phần mềm, nên chưa thể ước lượng nếu không đo trên board.
- Giảm số beat thường còn **có lợi hơn** trên FPGA thật, vì mỗi beat bỏ bớt cũng tránh được thời gian chờ DDR tương ứng.

### Cách thu hẹp khoảng cách
1. **Mô hình bộ nhớ trong cocotb**: **đã làm** (mục 6c).
2. **Bộ đếm hiệu năng trong RTL**: đếm chu kỳ của mỗi pha và số beat, đọc qua AXI-Lite trên board. Đây là thay đổi RTL, cần bạn đồng ý.
3. **Tổng hợp bằng Vivado** để lấy fmax và tài nguyên: hướng dẫn ở mục 6d (`tools/export_vivado.py`). Script `dse_scripts/` của upstream trỏ tới project trên máy của tác giả gốc nên không dùng được.
4. Nếu có board: đo thời gian tổng bằng timer của CPU quanh `openeye_runtime`, rồi so với dự đoán từ mô phỏng.

## 6c. Mô hình bộ nhớ ngoài trong testbench (2026-10-10)

### Mục đích
Testbench gốc giả định **bộ nhớ lý tưởng**: mỗi chu kỳ đưa 1 word vào, luôn nhận kết quả ngay.
Mô hình bộ nhớ thay phía host bằng một mô hình đơn giản của **DDR + AXI DMA**, để đo xem độ trễ và burst ảnh hưởng tới
độ trễ của layer bao nhiêu, và RTL có xử lý đúng khi dữ liệu không tới liên tục hay không.

### Thành phần
| File | Nội dung |
|---|---|
| `src/open_eye/memory_model.py` | `MemoryConfig` (tham số và preset), `ReadChannel` (MM2S: DDR → bộ tăng tốc), `WriteChannel` (S2MM: bộ tăng tốc → DDR) |
| `rtl_test_utils.send_words_through_memory` | Driver mới: gửi **toàn bộ stream của một layer như một lần truyền DMA**, theo đúng handshake AXI-Stream |
| `rtl_test_utils.compare_stream_Conv` | Phía đọc kết quả: `ready_dma_i` do `WriteChannel` quyết định (chỉ với layer Conv) |
| `rtl_test_utils.trace_dma_input` + `tools/check_dma_trace.py` | `OPENEYE_TRACE_DMA=1`: ghi mọi word DUT nhận và mọi lần đổi trạng thái vào `dma_in_trace.csv`; script so với stream testbench sinh ra |
| `profile_dma_phases` | Thêm đếm `in_stall`/`out_stall` (cột `mem stall` trong báo cáo) và ghi cấu hình bộ nhớ vào `profile.json` (`config.MEMORY`) |
| `test/test_memory_model.py` | 16 unit test so với công thức tính tay |

### Mô hình hoạt động thế nào
**Đọc (MM2S):** stream của layer được chia thành các burst `burst_beats` word (không vượt ranh giới 4 KB).
DMA gửi yêu cầu cho một burst khi (a) số burst đang chờ dữ liệu ít hơn `outstanding`, và (b) FIFO của DMA (`fifo_beats`) còn đủ chỗ
cho cả burst. Dữ liệu của burst bắt đầu về sau `latency` (+ ngẫu nhiên 0..`jitter`) chu kỳ, tối đa `bandwidth` word mỗi chu kỳ,
và vào FIFO. Mỗi chu kỳ, host chỉ bật `valid` (`enable_dma_i`) khi FIFO có word; word chỉ được tính là đã gửi khi `valid` và
`ready_dma_o` cùng bằng 1 ở cạnh clock. Nếu chưa, host giữ nguyên word đó.

**Ghi (S2MM):** kết quả vào FIFO; khi FIFO có đủ một burst (hoặc rảnh lâu), DMA gửi burst đó ra bộ nhớ với tốc độ `bandwidth`.
Mỗi burst giữ một "slot" cho tới khi có phản hồi ghi (`latency` chu kỳ sau word cuối). Hết slot hoặc FIFO đầy thì `ready_dma_i = 0`.

### Tham số và preset
| Tham số | Biến môi trường | `ideal` | `typical` | `slow` |
|---|---|---:|---:|---:|
| `latency` (chu kỳ) | `OPENEYE_MEM_LATENCY` | 0 | 30 | 80 |
| `burst_beats` | `OPENEYE_MEM_BURST` | 256 | 16 | 16 |
| `outstanding` | `OPENEYE_MEM_OUTSTANDING` | 64 | 2 | 1 |
| `bandwidth` (word/chu kỳ) | `OPENEYE_MEM_BANDWIDTH` | 1.0 | 1.0 | 0.5 |
| `fifo_beats` | `OPENEYE_MEM_FIFO` | rất lớn | 64 | 32 |
| `setup` (chu kỳ, mỗi lần truyền) | `OPENEYE_MEM_SETUP` | 0 | 0 | 0 |
| `jitter` | `OPENEYE_MEM_JITTER` | 0 | 0 | 10 |
| `seed` | `OPENEYE_MEM_SEED` | 0 | 0 | 0 |
| `gap_before` (vị trí word, ví dụ `173,200`) | `OPENEYE_MEM_GAP_BEFORE` | – | – | – |

`gap_before` chèn **đúng 1 chu kỳ trống** trước các word chỉ định, dùng cho thí nghiệm có mục tiêu (ví dụ kiểm chứng lỗi `GET_BIAS`).

Chọn preset bằng `OPENEYE_MEM=<preset>` (hoặc `run_profile.py --mem`), đổi từng tham số bằng `OPENEYE_MEM_*` (`--mem-set`).
**Không đặt biến nào thì testbench chạy driver cũ** (để mọi test có sẵn không bị ảnh hưởng).
**Các giá trị `typical`/`slow` chỉ để minh hoạ, chưa được hiệu chỉnh theo board thật.**

### Kết quả kiểm chứng (5 case `q32`)
| Cấu hình bộ nhớ | Kết quả | Độ trễ so với baseline |
|---|---|---|
| `ideal` (driver mới) | 5/5 PASS | **Giống hệt 100%** (chênh lệch 0 ở mọi pha). Driver mới đúng |
| `typical` | 5/5 PASS | **+10 % đến +22 %**. Chỉ các pha có DMA chậm đi; `convert`/`compute` không đổi. Tổng chu kỳ chờ bộ nhớ **bằng đúng** phần tăng thêm |
| `slow` | trước khi sửa: 5/5 **FAIL (treo)**; sau khi sửa `GET_BIAS`: **8/8 PASS** | Phát hiện lỗi RTL `GET_BIAS` (mục 9); sau khi sửa độ trễ +112 % đến +350 % |
| `typical`, 3 case kiểu MNIST | 3/3 PASS | Conv1 **+19,2 %**, Conv2 +7,6 %, Conv3 +9,7 %. Layer nặng về DMA (Conv1) chịu ảnh hưởng nhiều nhất |

Chi tiết `typical` (8 case, so với `baseline_2026-10-10`): `doc/perf/mem_typical_2026-10-10.md`, số liệu gốc ở `doc/perf/mem_typical_2026-10-10/`. Ví dụ case `32x3_f16`: 3652 → 4451 chu kỳ. Ở mọi pha nạp, cứ 16 word thì
có thêm 7 chu kỳ chờ, tức **mỗi word thực tế tốn khoảng 1,44 chu kỳ**. Hệ quả: giảm số word DMA (Giai đoạn 1) có lợi khoảng 1,44 lần
so với khi đo trên bộ nhớ lý tưởng.

Khoanh vùng lỗi (case `8x1_f4_q32`): khoảng nghỉ **dài** giữa các burst (độ trễ 80, 1 burst mỗi lần, jitter) vẫn PASS; dữ liệu **xen kẽ
từng word** (`bandwidth=0.5`, hoặc burst 1 word) thì FAIL. `profile.json` (`pending`) cho thấy pha `load_bias` chỉ nhận **31/32** word.

### Giới hạn hiện tại
- Phía ghi chỉ mô hình hoá cho readout của layer Conv (`compare_stream_Conv`); Dense, Depthwise và Pooling vẫn luôn sẵn sàng (sẽ làm cùng việc 0.2).
- Cửa sổ đo của profiler bắt đầu từ word đầu tiên được nhận, nên `setup` và độ trễ trước burst đầu **không** nằm trong tổng chu kỳ.
- Một layer là một lần truyền; chưa mô hình hoá thời gian của CPU giữa các layer, chưa tranh chấp bus với CPU.
- Tham số chưa hiệu chỉnh: kết quả dùng để **so sánh tương đối** giữa các phương án.

## 6d. Tổng hợp bằng Vivado (2026-10-12)

### Repo đã đủ file để add vào Vivado chưa? **Chưa, nếu add thẳng thư mục `hdl/`.**

| Vấn đề | Chi tiết |
|---|---|
| Thiếu 4 header được sinh tự động | `OpenEye_FPGA.v` include `parameters_FPGA.vh`, `PE.v` include `parameters_PE.vh`, `PE_cluster.v` include `parameters_PE_cluster.vh`, `dma_storage.v` include `regmap_params.vh`. Các file này **không có trong git**: test runner sinh lại chúng cho mỗi cấu hình. Bản trong `test/cocotb_fpga/` và `hdl/include/` chỉ là kết quả của lần test chạy cuối, và **không cùng cấu hình với nhau** (ví dụ `TRANSMISSIONS` 27 và 26) |
| `hdl/dma_storage.v` đã cũ | Bản này cũ hơn `test/cocotb_fpga/regmap.yaml`. Test luôn thay bằng bản sinh ra từ `regmap.yaml`. Dùng bản cũ thì bộ giải mã word cấu hình bị lệch, RTL đọc sai tham số layer |
| `TRANSMISSIONS` phải khớp | Giá trị trong `parameters_FPGA.vh` phải bằng giá trị trong `regmap_params.vh`; cả hai phụ thuộc vào cấu hình mảng |
| Wrapper AXI `fpga/hdl/open_eye_axi_v1_0.v` **không biên dịch được** | (1) Gọi module `open_eye_mt_v1_0_cfg_reg` nhưng module này không có trong repo. (2) Gán `QUANT_AMOUNT` nhưng wrapper không khai báo tham số này. (3) Gán `BUFFER_WIDTH` hai lần. (4) Gán `RAM_CELLS`, trong khi `OpenEye_FPGA` chỉ có `IACT_RAM_CELLS`. **Chưa sửa** (là HDL, cần bạn đồng ý). Không ảnh hưởng tới tổng hợp out-of-context `OpenEye_FPGA` |
| Không có project Vivado và block design | `dse_scripts/run_impl.tcl` mở file `.xpr` và block design `.bd` trên máy của tác giả gốc; các file này không có trong repo |

**Cách giải quyết:** script `tools/export_vivado.py` (không sửa RTL). Script sinh **đồng bộ từ một cấu hình duy nhất** đủ 4 header và
`dma_storage.v`, chép RTL vào cùng một thư mục, rồi viết sẵn file Tcl. Cấu hình mặc định là **đúng cấu hình của baseline độ trễ**
(`test_profile.py`): 2×2 cluster, `NUM_GLB_IACT=1`, `NUM_GLB_PSUM=4`, `NUM_GLB_WGHT=3`, psum 20 bit, `QUANT_AMOUNT=32`, DMA 64 bit.
Vì vậy fmax đo được dùng trực tiếp để đổi số chu kỳ của baseline ra thời gian thật.
Đã kiểm chứng: 4 header và `dma_storage.v` xuất ra **giống hệt từng byte** với bản mà phép đo `mnist1` dùng.
Yosys đọc thư mục xuất ra với 0 lỗi, dựng đủ cây 30 module.

### Ước lượng trước bằng Yosys (cấu hình baseline, 2026-10-12)

Yosys 0.69 `synth_xilinx -flatten -family xc7` chạy trên đúng thư mục `vivado/baseline`: 0 lỗi, 8 phút 20 giây, RAM tối đa 3,2 GB (vừa với WSL 7 GB).
Đây là **ước lượng**. Vivado thường gói LUT tốt hơn và suy luận BRAM khác, nên số chính thức phải lấy từ Vivado.

| Tài nguyên | Yosys (baseline 2×2) | xc7z020 (PYNQ-Z2) | xczu7ev (ZCU104) |
|---|---:|---:|---:|
| LUT logic (LUT2–LUT6) | 61.277 | 53.200 → **115 %, không vừa** | 230.400 → 27 % |
| LUT dùng làm RAM (RAM32M, RAM64X1S) | ≈ 2.500 LUT | | |
| Flip-flop | 45.274 | 106.400 → 43 % | 460.800 → 10 % |
| BRAM (quy về BRAM36: 248 RAMB36 + 48 RAMB18) | 272 | 140 → **194 %, không vừa** | 312 → 87 % |
| DSP | 121 | 220 → 55 % | 1.728 → 7 % |

Vì vậy part mặc định của `export_vivado.py` là `xczu7ev-ffvc1156-2-e`. Muốn dùng board nhỏ kiểu PYNQ-Z2 thì phải giảm cấu hình
(1×1 cluster nhỏ hơn khoảng 4 lần), và khi đó phải đo lại baseline chu kỳ với cùng cấu hình.

### Cấu hình phần cứng đang tổng hợp (mặc định của `export_vivado.py`, = cấu hình baseline độ trễ)

| Tham số | Giá trị | Ý nghĩa |
|---|---:|---|
| `CLUSTER_ROWS` × `CLUSTER_COLUMNS` | 2 × 2 | 4 cluster |
| `NUM_GLB_PSUM` × `NUM_GLB_WGHT` | 4 × 3 | 12 PE mỗi cluster (4 cột × 3 hàng) → **48 PE** |
| `PARALLEL_MACS` | 2 (sinh tự động) | 2 phép nhân mỗi PE → **96 MAC/chu kỳ** (INT8) |
| `SPARSITY_EN` | 1 (sinh tự động) | Bỏ qua giá trị 0 (sparse) |
| `NUM_GLB_IACT` | 1 | 1 GLB iact mỗi cluster (`NUM_GLB_IACT=3` đang sai, lỗi #7) |
| `DATA_PSUM_BITWIDTH` | 20 | Độ rộng psum |
| `DMA_BITWIDTH` | 64 | Độ rộng stream AXI, khớp wrapper AXI |
| `QUANT_AMOUNT` | 32 | Bảng lượng tử 32 entry (1 entry mỗi filter, tối đa 32 filter) |
| `TRANS_WORDS`, `BUFFER_WIDTH`, `BRANCHES` | 8, 12, 1 | Số word truyền giữa các layer, độ sâu bộ đệm iact (2^12), 1 nhánh |
| `BUFFER_WIDTH_PSUM`, `BUFFER_WIDTH_WGHT` | 14, 13 (mặc định; weight 12 trước 2026-11-03, lỗi #29) | Bộ đệm psum 16.384 địa chỉ (144 RAMB36), bộ đệm weight 8.192 hàng |
| `STRIDE_ENABLED` | **1** (mặc định từ 2026-11-09; 0 trước đó, như upstream) | Phần cứng dùng stride của từng layer (mục 5.10); +155 LUT so với 0 |

Lý do chọn: (1) **giống hệt cấu hình đã đo chu kỳ** (`test_profile.py`), nên fmax đổi trực tiếp chu kỳ ra thời gian; (2) đây là vùng cấu hình mà RTL
**chạy đúng** trong test (`NUM_GLB_IACT=3` sai, `CLUSTER_ROWS=1` có thể treo, 1 channel sai); (3) 2×2 cluster là cấu hình nhỏ nhất vẫn có cả
router theo hàng lẫn theo cột, và vừa ZU7EV với khoảng 28 % LUT. Lưu ý: `RAM_CELLS=32` trong `config.json` không có tác dụng, vì tham số thật tên
`IACT_RAM_CELLS` (giá trị sinh ra là 4, giống trong mô phỏng).

### Bước 1: tạo thư mục nguồn (trong WSL)

```bash
cd ~/OpenEye_orig
venv/bin/python tools/export_vivado.py                                   # cấu hình baseline, part xczu7ev-ffvc1156-2-e (ZCU104), 100 MHz
venv/bin/python tools/export_vivado.py --part xc7z020clg400-1 --set CLUSTER_ROWS=1 --set CLUSTER_COLUMNS=1 --name z7020_1x1   # PYNQ-Z2, cấu hình nhỏ
venv/bin/python tools/export_vivado.py --set CLUSTER_ROWS=4 --name rows4                         # đổi một tham số
```

Kết quả nằm ở `vivado/<name>/` (không đưa lên git, vì sinh lại được bất cứ lúc nào):

```
vivado/baseline/
├── rtl/              39 file .v (hdl/*.v, thay dma_storage.v bằng bản sinh ra)
├── include/          parameters_FPGA.vh, parameters_PE.vh, parameters_PE_cluster.vh, regmap_params.vh
├── filelist.f        danh sách nguồn
├── constraints.xdc   ràng buộc clock (cổng clk_i)
├── synth_ooc.tcl     flow tổng hợp chạy batch
├── config.json       cấu hình đã dùng (để ghi vào báo cáo)
└── regmap_pack.py    cách đóng gói word cấu hình cho cấu hình này (tham khảo)
```

Vivado chạy trên Windows, nên chép thư mục này sang ổ Windows. Không nên mở trực tiếp qua `\\wsl.localhost`, vì Vivado chạy chậm và đôi khi lỗi đường dẫn:

```bash
mkdir -p /mnt/c/openeye_vivado && cp -r vivado/baseline /mnt/c/openeye_vivado/
```

### Bước 2a: chạy bằng Tcl (khuyên dùng, nhanh và lặp lại được)

Mở **Vivado Tcl Shell** (Start menu), rồi chạy:

```tcl
cd C:/openeye_vivado/baseline
source synth_ooc.tcl
```

hoặc từ cmd: `vivado -mode batch -source synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 10`. Hai tham số `-tclargs` là part và chu kỳ clock (ns), có thể bỏ qua.
Thêm tham số thứ ba `impl` (`-tclargs xczu7ev-ffvc1156-2-e 4 impl`) thì script chạy tiếp opt/place/route và ghi thêm `utilization_route.txt`,
`timing_summary_route.txt`, cùng dòng `OPENEYE_RESULT post-route`. Trong Tcl shell, gõ `set run_impl 1` trước `source synth_ooc.tcl` để làm tương tự.
Muốn biết fmax thật thì đặt clock **chặt** (ví dụ 4 ns = 250 MHz). Khi slack dư nhiều, công cụ không cố tối ưu, nên fmax suy ra chỉ là cận dưới.
Script đọc ràng buộc clock **trước** `synth_design`, nên tổng hợp có tính đến timing. Mỗi lần RTL đổi phải **xuất lại** thư mục (thư mục cũ trên ổ C
chứa bản chép RTL cũ và có thể cả bản `synth_ooc.tcl` cũ) và mở **một Vivado Tcl Shell mới**.
Kết quả nằm trong `reports/`: `utilization.txt`, `utilization_hier.txt` (tài nguyên theo từng module), `timing_summary.txt`,
`timing_paths.txt` (20 đường găng), `OpenEye_FPGA_synth.dcp` (checkpoint, mở lại bằng `open_checkpoint`).
Dòng cuối của log in ra `OPENEYE_RESULT ... WNS=... fmax~... MHz`.

### Bước 2b: làm bằng giao diện (GUI)

1. **Create Project** → RTL Project → tick **Do not specify sources at this time** → chọn part (ví dụ `xczu7ev-ffvc1156-2-e`; xem bảng ước lượng Yosys ở trên để chọn chip đủ lớn).
2. **Add Sources → Add or create design sources → Add Files**: chọn toàn bộ `rtl/*.v`. **Không** add `hdl/dma_storage.v` của repo; chỉ dùng bản trong `rtl/`.
   Tick **Copy sources into project** nếu muốn project độc lập với thư mục xuất.
3. Add thêm 4 file trong `include/`. Chuột phải từng file → **Set File Type → Verilog Header**. Hoặc:
   **Settings → General → Verilog options → Include Directories** → thêm thư mục `include/`.
4. Chọn tất cả file `.v` trong **Sources** → chuột phải → **Set File Type → SystemVerilog**. Simulator và Yosys đều đọc nguồn ở chế độ SystemVerilog.
5. **Settings → General → Verilog options → Defines**: thêm `SYNTHESIS` và `NO_TRACE`. Thiếu `NO_TRACE` thì Vivado báo lỗi ở `$value$plusargs`
   (đây là code trace chỉ dùng cho mô phỏng).
6. Chuột phải `OpenEye_FPGA` → **Set as Top**.
7. **Settings → Synthesis → More Options**: thêm `-mode out_of_context`. Lý do: thiết kế có khoảng 140 cổng (DMA 64 bit vào, 64 bit ra), không gán ra chân thật.
   Ở chế độ OOC, Vivado không chèn I/O buffer và không báo lỗi thiếu chân.
8. Add `constraints.xdc` (Add Sources → Add or create constraints).
9. **Run Synthesis** → **Open Synthesized Design** → **Report Utilization** và **Report Timing Summary**.

### Bước 3: đọc kết quả và ghi lại

| Số liệu | Đọc ở đâu | Dùng để làm gì |
|---|---|---|
| LUT, FF, BRAM, DSP | `utilization.txt` | Mốc tài nguyên; so với dung lượng của chip |
| Tài nguyên theo module | `utilization_hier.txt` | Biết PE, GLB, `psum_pipeline` hay bảng lượng tử chiếm bao nhiêu |
| WNS (Worst Negative Slack) | `timing_summary.txt` | WNS ≥ 0: đạt clock mục tiêu. WNS < 0: không đạt |
| fmax ≈ 1000 / (T − WNS) MHz | Dòng `OPENEYE_RESULT` | Đổi chu kỳ ra thời gian: `mnist1` 65.800 chu kỳ ở 100 MHz = 0,658 ms |
| Đường găng | `timing_paths.txt` | Biết khối nào giới hạn tần số |

Lưu ý:
- fmax sau tổng hợp là **ước lượng lạc quan** vì chưa có trễ đi dây; số chính thức lấy sau place & route (tuỳ chọn `impl`).
  Với thiết kế này, sau route chỉ thấp hơn sau tổng hợp khoảng 2–5 % (264 → 252–258 MHz).
- Nếu tài nguyên vượt quá chip (ví dụ cấu hình baseline trên xc7z020), tổng hợp **vẫn ra báo cáo**, chỉ place & route mới thất bại.
  Khi đó giảm cấu hình (`--set CLUSTER_ROWS=1`, `--set CLUSTER_COLUMNS=1`) hoặc chọn chip lớn hơn. Cần ghi rõ cấu hình đi kèm mọi số liệu.
- Bản Vivado miễn phí (ML Standard) hỗ trợ Zynq-7000 và một số Zynq UltraScale+ nhỏ. **ZU19EG** mà tác giả gốc dùng cần license trả phí.
  Kiểm tra danh sách thiết bị trước khi chọn part.
- Lưu báo cáo vào repo: chép `reports/utilization.txt`, `reports/timing_summary.txt` và `config.json` vào `doc/synth/<ngày>_<cấu hình>/`.

### Kết quả Vivado hiện tại: mốc phần cứng (sau các bản sửa #13, #6/#7, #14, 3 commit upstream, #19, #26, #25, #30, #31, upstream `e78e5b7`, dòng `wghts_per_pe + 1`, phần cứng hàm kích hoạt, các bản sửa #28, #29, #36, #38, hàng O #37, #17, #41c và `STRIDE_ENABLED = 1`; ngày 2026-11-09)

**Mới nhất: `doc/synth/2026-11-09_route4ns_stride1_zu7ev/SUMMARY.md`** (đề xuất 5: cùng RTL, dựng với `STRIDE_ENABLED = 1`, nay là mặc định): 0 CRITICAL, 311 cảnh báo y như cũ; WNS +0,171 / **+0,042 ns** sau route (đạt 250 MHz, ~252,7 MHz; đường găng `fsm_cycle` → `router_configurator`, như lần `wsend`); LUT 61.674 / **59.548** (+155 / +175 so với `fix41`, +0,25 %: gần hết ở `dma_storage` +220, các `iact_stream_constructor` không tăng), FF 39.406 / 39.449 (+7 / +13), CARRY8 +4, BRAM 188 / URAM 12 / DSP 4 như cũ.

Lần trước: `doc/synth/2026-11-08_route4ns_fix41_zu7ev/SUMMARY.md` (bản sửa #41c, 2 dòng ghi ngược; cấu hình như rowO, `STRIDE_ENABLED = 0`): 0 CRITICAL, 311 cảnh báo y như rowO; WNS +0,196 / **+0,009 ns** sau route (đạt 250 MHz, ~250,6 MHz; đường găng là dây giữa hai PE ở hai cluster, 95,5 % trễ do route, không qua logic vừa sửa: dao động vị trí như lần `wsend`); LUT 61.519 / 59.373 (+21 / −16), FF 39.399 / 39.436, BRAM 188 / URAM 12 / DSP 4 như cũ.

Lần trước: `doc/synth/2026-11-04_route4ns_rowO_zu7ev/SUMMARY.md` (hàng O: #37 trường bộ đệm iact 13 bit, #17 bỏ đường 1 channel cặp hàng): 0 CRITICAL, 311 cảnh báo (4 cảnh báo mới "cổng `iact_x_line_repetitions_i` không tải" của cổng giữ lại không dùng), WNS +0,169 / **+0,077 ns** (đạt 250 MHz, ~254,9 MHz), **LUT −1.547 (59.389), FF −525 (39.398), BRAM 192 → 188**, URAM 12, DSP 4 sau route. Mỗi PE −14 … −18 LUT, −7 FF (trạng thái "dòng lệch" đã xoá); mỗi constructor −37 FF, −25 … −58 LUT và **bớt 1 RAMB36** (bộ đệm iact 6 → 5 RAMB36 vì mặt nạ ghi theo byte nay là hằng số); `dma_storage` +17 LUT, +23 FF (10 trường rộng thêm 1 bit). Đường xấu nhất sau route vẫn là địa chỉ psum → BRAM psum (đi dây). Bảng dưới vẫn là lần `cr1fix`, hai cột cuối là `fix38` và `rowO`.

Lần trước (`fix38`, `doc/synth/2026-11-04_route4ns_fix38_zu7ev/SUMMARY.md`) (bản sửa #38, mantissa 25 bit vào bộ lượng tử): 0 CRITICAL, cảnh báo y như lần `cr1fix`, WNS +0,211 / **+0,044 ns** (đạt 250 MHz, ~252,8 MHz), BRAM / URAM / DSP **192 / 12 / 4 như cũ**; LUT +318 sau tổng hợp / +293 sau route (60.936), FF +85 (39.923). Mỗi bộ lượng tử (4 bộ) **+69 LUT, +17 FF, 0 DSP**: trước bản sửa bit 8–24 của mantissa luôn là 0 nên Vivado chỉ dựng bộ nhân 8 × 21 bit vừa một DSP48E2 (27 × 18); nay là 25 × 21 bit, cả hai toán hạng đều rộng hơn 18 bit, nên vẫn 1 DSP và phần tích riêng còn lại làm bằng LUT/CARRY8; thanh ghi `mant_s1` 8 → 25 bit (+17 FF). Sau tổng hợp timing giống hệt; sau route đường xấu nhất là địa chỉ bộ đệm psum → chân WE của BRAM psum (1 LUT, 95 % là dây), loại đường do đi dây quen thuộc, không có đường nào của bộ lượng tử trong 10 đường xấu nhất. Bảng dưới vẫn là lần `cr1fix`, cột cuối là lần `fix38`.

Lần trước (`cr1fix`, `doc/synth/2026-11-03_route4ns_cr1fix_zu7ev/SUMMARY.md`, bản sửa #28, #29, #36): 0 CRITICAL, cảnh báo y như lần `act`, WNS +0,211 / **+0,075 ns** (đạt 250 MHz, ~254,8 MHz), BRAM 192 như cũ, **URAM 8 → 12** (bộ đệm weight 8.192 hàng = 8 URAM, đặt bằng `RamStyle("ultra")`), FF +288 trong bộ đệm (thanh ghi ra của chuỗi URAM), LUT không tăng (60.643 sau route; −776 là dao động tổng hợp của `OpenEye_Parallel`). Ở cấu hình tổng hợp (CR 2 X 4) bản sửa #28, #36 sinh đúng mạch cũ. Lần chạy đầu không có thuộc tính: Vivado đặt bộ đệm vào 64 RAMB36 + 845 LUT (BRAM 192 → 256 = 82 %), nên mới thêm `RamStyle`. Bảng dưới là lần này.

Lần trước (`act`, `doc/synth/2026-11-02_route4ns_act_zu7ev/SUMMARY.md`, hàm kích hoạt bước B): 0 CRITICAL, WNS +0,203 / +0,045 ns, LUT 61.419 sau route
(+778; phần do bước B khoảng +550: 4 bảng tra 354 LUT gồm 256 LUTRAM, 4 bộ lượng tử +193), FF 39.849 (+59), BRAM/URAM/DSP như cũ; đường găng vẫn là chuỗi
so sánh `fsm_cycle` → `router_configurator` như lần `wsend`, logic kích hoạt không nằm trong các đường được báo cáo.
Lần trước (`wsend`): `doc/synth/2026-11-02_route4ns_wsend_zu7ev/SUMMARY.md` (trước nữa: `doc/synth/2026-10-31_route4ns_e78_zu7ev/`, giống từng dòng lần `fix31`). Vivado 2024.2, `xczu7ev-ffvc1156-2-e`, out-of-context, clock 4 ns (250 MHz),
cấu hình ở bảng trên; RTL của lần `act` = `dev` `f853b61` (bước B của hàm kích hoạt), của lần `wsend` = `dev` `659b8d3`: dòng `wghts_per_pe + 1` (mục 9) trên bản sửa #31 (trạng thái `EMPTY_PASS` trong PE; trước đó #30 kẹp int8 trong bộ lượng tử, #25, #26 ở bộ ghi ngược). Bản sửa lỗi #18 chỉ là Python, không đổi phần cứng. Vivado được chạy batch từ WSL
(`cmd.exe /c ... vivado.bat -mode batch -source synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`).

| Lần `cr1fix` | Sau tổng hợp | **Sau route** | Tỉ lệ ZU7EV (sau route) | Lần `act` (sau route) | Lần `fix38` (sau route) | **Lần `rowO` (mốc hiện tại, sau route)** |
|---|---:|---:|---:|---:|---:|---:|
| WNS ở 4 ns / hold | +0,211 ns | **+0,075 ns** / +0,005 ns | đạt 250 MHz | +0,045 / +0,007 ns | +0,044 / +0,007 ns | **+0,077** / +0,011 ns |
| fmax = 1000 / (4 − WNS) | ~264 MHz | **~255 MHz** | | ~253 MHz | ~253 MHz | **~255 MHz** |
| LUT (logic + LUTRAM/SRL) | 62.680 | 60.643 | 26,3 % | 61.419 | 60.936 (26,4 %) | **59.389** (25,8 %) |
| trong đó LUT làm bộ nhớ | | 2.537 | | 2.535 | 2.537 | 2.549 |
| Flip-flop | 39.801 | 39.838 | 8,6 % | 39.849 | 39.923 | **39.398** |
| Block RAM tile (RAMB36 168 + RAMB18 48) | 192 | 192 | **61,5 %** | 192 | 192 | **188** (RAMB36 164; 60,3 %) |
| URAM / DSP | 12 / 4 | 12 / 4 | 12,5 % / 0,2 % | 8 / 4 | 12 / 4 | 12 / 4 |

- **Dòng `wghts_per_pe + 1` (2026-11-02):** so với lần `e78`: LUT −260 sau tổng hợp / −199 sau route (−91 trong `OpenEye_Parallel`, khối không bị sửa: dao động
  tối ưu), FF −2 / −6, BRAM/URAM/DSP như cũ. Timing sau tổng hợp không đổi (+0,205 ns); sau route **WNS +0,074 → +0,020 ns**: đường găng nay là
  `fsm_cycle_reg[0]` → `router_configurator_inst/router_mode_psum_o_reg[19]/CE` (13 tầng logic, chuỗi so sánh của bộ đếm FSM chính khi cấu hình router),
  đường không chứa phép so sánh vừa sửa và ở lần `e78` không nằm trong 10 đường xấu nhất (≥ +0,104 ns): biên nhỏ đi do placement/routing, không do
  logic. Vẫn đạt 250 MHz, nhưng là biên nhỏ nhất từ trước tới nay; nếu cần biên, đường này là chỗ nên pipeline (tính trước so sánh của `fsm_cycle`).
- **Bản sửa #31:** FF +10 mỗi PE (bộ đếm giữ ready 5 bit + thanh ghi trạng thái). LUT **giảm** 3,7k (−5,6 %) nhưng không phải nhờ bản sửa: với 10 trạng thái,
  Vivado tự chuyển cách mã hoá FSM của PE từ `sequential` (4 bit) sang `one-hot` (10 bit), giải mã trạng thái rẻ hơn (khoảng −77 LUT mỗi PE); có thể đạt mức này
  mà không cần bản sửa bằng cách ép `fsm_encoding`, chưa làm.
- **0 ERROR, 0 CRITICAL WARNING**; danh sách cảnh báo giống hệt lần clamp, fix26 và fix19 (chỉ khác số dòng `DRC 23-814` chung của chế độ out-of-context) và lần up3 (lần đó hết 2 cảnh báo Synth 8-689, fix14 hết 10 cảnh báo 8-6090). Các cảnh báo còn lại:
  Synth 8-7137 (lỗi #15), 8-6057 (URAM không có thanh ghi pipeline), thanh ghi/cổng không dùng bị loại bỏ, và cảnh báo bình thường của chế độ out-of-context.
- Mỗi PE thêm **2 FF** (654 → 656): 2 bit cao của bộ đếm `first_spad_words_o` (7 bit) nay được dùng nên không bị loại bỏ.
- **Tài nguyên theo khối:** mảng PE (`OpenEye_Parallel`, 48 PE) chiếm khoảng 84 % LUT và 85 % FF, mỗi PE khoảng 1.100 LUT và 655 FF; bộ nhân của PE làm bằng
  LUT (`USE_DSP=0`); 4 DSP ở 4 bộ lượng tử. 8 bộ đệm psum (16.384 × 40 bit) chiếm **144/168 RAMB36** (46 % BRAM của chip); 4 `iact_stream_constructor` chiếm
  24 RAMB36 (mỗi khối 364 FF sau bản sửa #6/#7); 48 RAMB18 là SPad của 48 PE; 8 URAM là 4 bộ đệm iact và bộ đệm weight.
- **Đường găng sau route:** lần fix31 là dây từ `psum_pipeline` (`psum_buffer_addr_array`) tới BRAM bộ đệm psum; lần clamp (#30) là bộ đồng bộ reset, dữ liệu weight của PE, và dây từ `psum_pipeline` tới BRAM bộ đệm psum (không qua bộ lượng tử); lần fix25 là dây từ `psum_buffer_addr_array` tới BRAM của bộ đệm psum và đầu ra bộ cộng trong PE; lần fix26 cả 20 đường là dây từ URAM của bộ đệm weight (`wght_buffer`, không có thanh ghi đầu ra) tới đầu vào weight của PE; lần fix19
  là dây từ `psum_pipeline` (`psum_buffer_addr_array`) tới 144 BRAM của bộ đệm psum; lần up3 đa số nằm trong một PE. Đường găng đổi chỗ theo placement,
  các đường đều sát nhau quanh 4 ns, nên WNS dao động vài chục ps giữa các lần chạy (+0,020 đến +0,117 ns) dù RTL gần như không đổi; lần `wsend`
  (2026-11-02) là chuỗi so sánh `fsm_cycle` → `router_configurator`.
- **Thời gian thật ở 250 MHz** (bộ nhớ lý tưởng, `baseline_2026-11-04`): `mnist1` 54.936 chu kỳ = 220 µs, `mnist2` 261 µs, `mnist3` 82 µs, `model_mnist_real_c1` 959 µs (960 µs trước hàng O).

### Lịch sử các lần chạy Vivado

| Ngày | Thư mục `doc/synth/` | Chạy gì | Kết quả chính |
|---|---|---|---|
| 2026-10-12 | `2026-10-12_baseline_zu7ev` | Tổng hợp, clock 10 ns | 64,5k LUT, 38,7k FF, 192 BRAM tile; fmax sau tổng hợp ~257 MHz. Phát hiện CRITICAL WARNING của lỗi #13 |
| 2026-10-12 | `2026-10-12_synth4ns_zu7ev` | Tổng hợp lại ở 4 ns (place & route **không** chạy vì thư mục trên ổ C là bản cũ, chưa có tuỳ chọn `impl`) | Cùng netlist; danh sách cảnh báo đầy đủ, lỗi #13–#15 |
| 2026-10-13 | `2026-10-13_route4ns_zu7ev` | Tổng hợp + place & route, 4 ns, **trước** khi sửa lỗi #13 | Đạt 250 MHz (WNS +0,025 ns); 63,9k LUT. Không dùng làm mốc vì phần cứng này tính sai (lỗi #13) |
| 2026-10-14 | `2026-10-14_route4ns_fix13_zu7ev` | Tổng hợp + place & route, 4 ns, **sau** khi sửa lỗi #13 | CRITICAL WARNING 200 → 0; mỗi `iact_stream_constructor` +32 FF (đúng 4 bộ đếm × 8 bit); WNS +0,117 ns |
| 2026-10-15 | `2026-10-15_route4ns_fix67_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi sửa lỗi #6/#7 | +103 FF, +201 LUT (logic địa chỉ 1 channel); WNS +0,048 ns |
| 2026-10-19 | `2026-10-19_route4ns_fix14_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi sửa lỗi #14 (chạy batch từ WSL) | Synth 8-6090: 10 → 0; LUT −112, FF −8 (dao động công cụ); WNS +0,097 ns |
| 2026-10-21 | `2026-10-21_route4ns_up3_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi lấy 3 commit upstream | Synth 8-689: 2 → 0; FF +101 (+2/PE), LUT −80; WNS +0,070 ns |
| 2026-10-21 | `2026-10-21_route4ns_fix19_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi sửa lỗi #19 | Cảnh báo không đổi; FF +24, LUT −60; WNS +0,073 ns |
| 2026-10-26 | `2026-10-26_route4ns_fix26_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi sửa lỗi #26 (lần chạy ngày 25/10 bị ngắt khi tắt máy, đã chạy lại) | Cảnh báo không đổi; sau tổng hợp LUT −4, FF −4 (1 cổng OR, phần còn lại là dao động); WNS +0,028 ns |
| 2026-10-26 | `2026-10-26_route4ns_fix25_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi sửa lỗi #25 (lần 1 phép kiểm lane chưa được gấp hằng: LUT +92; lần 2 là RTL cuối) | Cảnh báo không đổi; sau tổng hợp LUT +113 (+0,17 %, phần lớn là dao động: các module không đổi cũng lệch ±30), FF −10; WNS +0,084 ns |
| 2026-10-28 | `2026-10-28_route4ns_clamp_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi thêm kẹp int8 (#30) | Cảnh báo không đổi; LUT +857 (+1,3 %, gần hết ở 8 bộ lượng tử), FF +22; WNS +0,076 ns |
| 2026-10-30 | `2026-10-30_route4ns_fix31_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi sửa lỗi #31 (chạy ngày 31/10) | Cảnh báo không đổi; FF +478 (+10/PE); LUT −3.726 (FSM của PE được mã hoá one-hot); WNS +0,074 ns |
| 2026-10-31 | `2026-10-31_route4ns_e78_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi lấy upstream `e78e5b7` | Mọi báo cáo giống từng dòng lần `fix31` (netlist không đổi); 0 CRITICAL, WNS +0,074 ns |
| 2026-11-02 | `2026-11-02_route4ns_wsend_zu7ev` | Tổng hợp + place & route, 4 ns, sau dòng `wghts_per_pe + 1` | 0 CRITICAL, cảnh báo như cũ; LUT −199, FF −6; WNS +0,020 ns (đường găng mới `fsm_cycle` → `router_configurator`, không qua phép so sánh vừa sửa) |
| 2026-11-03 | `2026-11-03_route4ns_cr1fix_zu7ev` | Tổng hợp + place & route, 4 ns, bản sửa #28, #29, #36 (bộ đệm weight 8.192 hàng trong URAM) | 0 CRITICAL, cảnh báo như cũ; URAM 8 → 12, FF +288 trong bộ đệm, BRAM/DSP/LUT như cũ; WNS +0,075 ns. Lần đầu không ép URAM: 64 RAMB36 + 845 LUT (BRAM 82 %) |
| 2026-11-04 | `2026-11-04_route4ns_fix38_zu7ev` | Tổng hợp + place & route, 4 ns, bản sửa #38 (lát cắt exponent/mantissa của bảng lượng tử) | 0 CRITICAL, cảnh báo như cũ; mỗi bộ lượng tử +69 LUT, +17 FF (bộ nhân 25 × 21 thay vì 8 × 21), DSP vẫn 4, BRAM/URAM như cũ; LUT +293, FF +85 sau route; WNS +0,044 ns (đường địa chỉ psum → BRAM, do đi dây) |
| 2026-11-09 | `2026-11-09_route4ns_stride1_zu7ev` | Tổng hợp + place & route, 4 ns, cùng RTL với `STRIDE_ENABLED = 1` (đề xuất 5, nay mặc định) | **Mốc hiện tại**: 0 CRITICAL, cảnh báo như cũ; LUT +155 / +175, FF +7 / +13, CARRY8 +4 so với `fix41`; BRAM/URAM/DSP như cũ; WNS +0,042 ns |
| 2026-11-08 | `2026-11-08_route4ns_fix41_zu7ev` | Tổng hợp + place & route, 4 ns, bản sửa #41c (ghi ngược theo kích thước output) | Mốc trước (`STRIDE_ENABLED = 0`): 0 CRITICAL, cảnh báo như cũ; LUT +21 / −16, FF +1 / +38; BRAM/URAM/DSP như cũ; WNS +0,009 ns (đường găng giữa hai PE, do route) |
| 2026-11-04 | `2026-11-04_route4ns_rowO_zu7ev` | Tổng hợp + place & route, 4 ns, hàng O (#37 trường bộ đệm iact 13 bit, #17 bỏ đường 1 channel cặp hàng) | Mốc trước. 0 CRITICAL, 311 cảnh báo; LUT −1.547, FF −525, BRAM 192 → 188 (bộ đệm iact 6 → 5 RAMB36 mỗi constructor), mỗi PE −7 FF; WNS +0,077 ns |
| 2026-11-02 | `2026-11-02_route4ns_act_zu7ev` | Tổng hợp + place & route, 4 ns, phần cứng hàm kích hoạt (bước B) | 0 CRITICAL; LUT +778 (+1,3 %, do bước B khoảng +550), FF +59, 256 LUTRAM cho 4 bảng tra; WNS +0,045 ns |

Ước lượng Yosys so với Vivado: LUT logic lệch dưới 1 %, nên Yosys dùng tốt để so sánh LUT tương đối. BRAM, URAM và DSP lệch nhiều (Yosys không dùng URAM
và đưa bộ nhân vào DSP), nên các số này phải lấy từ Vivado.

### Có phải tổng hợp lại sau mỗi lần sửa RTL hoặc tối ưu không? **Có, khi RTL hoặc cấu hình thay đổi.**

| Thay đổi | Mô phỏng (cocotb) | Tổng hợp lại? |
|---|---|---|
| Sửa RTL (`hdl/*.v`), ví dụ sửa lỗi hoặc gửi bias theo filter | Bắt buộc chạy lại test và `run_profile --compare` | **Có.** Tài nguyên và fmax có thể đổi. Sinh lại thư mục bằng `export_vivado.py`, vì `rtl/` là bản chép |
| Đổi tham số cấu hình (số cluster, `QUANT_AMOUNT`, `DMA_BITWIDTH`, ...) | Có | **Có**, với cùng `--set` như khi mô phỏng |
| Sửa `regmap.yaml` | Có | **Có** (đổi `dma_storage.v` và `TRANSMISSIONS`) |
| Chỉ sửa Python (bộ sinh stream, testbench, profiler, báo cáo) | Có | **Không**, phần cứng không đổi |
| Chỉ sửa phần mềm runtime (`fpga/sw`) | Không | **Không** (chỉ biên dịch lại phần mềm) |

Quy trình đề xuất cho mỗi thay đổi RTL:
1. Test và `run_profile --compare` (chu kỳ).
2. Yosys để so sánh nhanh, khoảng vài phút.
3. Vivado ở các mốc quan trọng (trước và sau một tối ưu lớn) để lấy số chính thức: tài nguyên và fmax.

Độ trễ thật = số chu kỳ ÷ fmax. Một tối ưu giảm 19 % số chu kỳ nhưng làm fmax giảm 25 % thì **chậm hơn**. Vì vậy mọi tối ưu cần cả hai con số.

## 7. Kết quả baseline chính (chi tiết: `doc/perf/baseline_2026-11-02.md`; trước đó `baseline_2026-10-24.md`; trước bản sửa #18: `baseline_2026-10-10.md`)

**Baseline hiện tại: `doc/perf/baseline_2026-11-04/`** (12 case, bộ nhớ lý tưởng; thời gian ở 250 MHz = chu kỳ × 4 ns; lưu 2026-11-04 sau hàng O,
`doc/perf/baseline_2026-11-04.md`): 11 case giống hệt `baseline_2026-11-02`, `model_mnist_real_c1` 239.998 → **239.638** chu kỳ (−360, chỉ ở Conv1: −1,1 %;
`load_iact` −96 vì không còn channel đệm, `load_wght` −240, `writeback` −24, `compute` không đổi) và −336 word DMA. Mốc trước `baseline_2026-11-02` (lưu
2026-11-02 sau dòng `wghts_per_pe + 1`, mục 9). So `baseline_2026-11-02` với mốc trước nó `baseline_2026-10-24`: 12/12 PASS, ít hơn 0–673 chu kỳ mỗi case, chỉ ở pha compute, số word DMA không
đổi (`doc/perf/baseline_2026-11-02.md` là bảng so sánh này). Thêm 3 case cả model có bảng theo layer (mục 6.13): **MNIST thật 1 channel
`model_mnist_real_c1` 239.998 chu kỳ (960 µs)**, Conv2 chiếm 50 %; `model_mnist_real_c2` 242.844 chu kỳ (971 µs); `model_mnist16_c2` 49.930 chu kỳ (200 µs).
Lịch sử: `baseline_2026-10-24` (sau #22: 240.671 / 243.517 / 50.007; so với `baseline_2026-10-22` các case model giảm 13–579 chu kỳ vì weight Conv ngẫu
nhiên giữ số 0 thật và PE bỏ qua chúng), trong đó 9 case một layer giống hệt `baseline_2026-10-15` (sau bản sửa lỗi #18).
**Bảng 3 của paper** (mạng Bảng 2, 16 cấu hình cluster/PE, theo từng layer và từng pha): mục 6.14, mốc hiện tại `doc/perf/paper_table3_2026-11-04.md`
(16/16, layer 0 không còn đệm channel: −192 đến −408 chu kỳ ở 12 cấu hình; trước đó `paper_table3_2026-11-03.md`, **16/16** cấu hình đúng cả mạng sau bản sửa #28, #29, #36; 13 cấu hình cũ giống hệt từng chu kỳ bản `paper_table3_2026-11-02.md` (13/16), bản đó −0,1 đến −0,3 %
chu kỳ so với `paper_table3_2026-10-26_fix25.md` nhờ dòng `wghts_per_pe + 1`; bản `paper_table3_2026-10-24.md` là trước #25/#26). **Model MNIST đã huấn luyện với ảnh thật** (2026-10-31, mục 6.13):
213.040–220.941 chu kỳ (852–884 µs) ở ảnh 0, 1, 2, 7, ít hơn 8,2–11,5 % so với `model_mnist_real_c1` vì activation thật có nhiều số 0 (`doc/perf/trained_mnist_2026-10-31.md`;
đo trước dòng `wghts_per_pe + 1`, sau đó −673 ở mọi ảnh: 212.367–220.268, đo trong worktree thí nghiệm; ảnh 0 đo lại trên `dev` 2026-11-02: 218.925).
**Hàm kích hoạt** (2026-11-02, mục 6.15): cùng kiến trúc, ảnh 0: ReLU 218.925, Leaky ReLU 238.049 (+8,7 %), SiLU 240.229 (+9,7 %), hard-swish 240.293
chu kỳ (+9,8 %); khối kích hoạt 0 chu kỳ mỗi giá trị, phần thêm là `compute` vì mất số 0. Sau bản sửa #38 (mantissa 24 bit, 2026-11-04,
`doc/perf/activation_2026-11-04_mant24.md`): 218.924 / 238.049 / 240.230 / 240.287 (chỉ Dense lệch −1 / 0 / +1 / −6). Sau hàng O (Conv1 không đệm channel,
`doc/perf/activation_2026-11-04_rowO.md`, **số hiện tại**): 218.564 / 237.689 / 239.870 / 239.927 (cả 4 −360, ở Conv1).

**Layer kiểu MNIST (0.3):**

| Case | Thay cho | Tổng chu kỳ | Compute | Pha không tính toán lớn nhất |
|---|---|---:|---:|---|
| `mnist1_28x28_c4_f32` | Conv1 | 54.936 (220 µs) | 42% | **bias 26%** (14.336 word cho 96 byte payload), readout 26% |
| `mnist2_14x14_c32_f32` | Conv2 | 65.304 (261 µs) | **69%** | weight 12% (hiệu suất 15%), convert 7% |
| `mnist3_8x8_c32_f32` | Conv3 | 20.520 (82 µs) | 62% | weight 19% (hiệu suất 30%), convert 8% |

Tổng chu kỳ theo `baseline_2026-11-02`; trước dòng `wghts_per_pe + 1` (`baseline_2026-10-15`/`10-24`): 55.048 / 65.528 / 20.584. Trước bản sửa lỗi #18
(`baseline_2026-10-10`): 65.800 / 87.032 / 26.728 chu kỳ; phần giảm tới `baseline_2026-10-15` (−16 % / −25 % / −23 %) nằm hết ở `compute`: mỗi lần gửi weight
dài 96 thay vì 192 chu kỳ.

**Layer nhỏ (2026-10-09):**
1. Phần tính toán chỉ chiếm **14–40%** độ trễ; mọi pha chạy **tuần tự**.
2. Bus DMA chỉ bận **35–58%** số chu kỳ.
3. **Bias gửi theo từng pixel output** (hiệu suất 1–5%).
4. **Weight**: hiệu suất 15%.
5. **Bảng lượng tử** luôn gửi đủ `QUANT_AMOUNT` entry.
6. **Readout** gửi psum 20 bit trong ô 32 bit.

**Rút ra cho Giai đoạn 1:**
- Layer đầu (ảnh lớn, ít channel): **bias theo filter** và **readout INT8** là quan trọng nhất (bias 26 % + readout 26 % độ trễ của `mnist1`).
- Layer sâu (nhiều channel): compute chiếm phần lớn; tối ưu DMA còn khoảng 10–15% (chủ yếu weight). Muốn giảm thêm thì phải
  chạy chồng pha (Giai đoạn 2) hoặc tăng hiệu suất tính toán.
- Với bộ nhớ thực tế hơn (`typical`), mỗi word DMA tốn khoảng 1,44 chu kỳ, nên lợi ích của việc giảm word còn lớn hơn (mục 6c).

## 8. Lộ trình

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 0. Đo lường | Profiler, báo cáo, so sánh, baseline 12 case, mô hình bộ nhớ, mốc phần cứng Vivado, kiểm tra độc lập từng word, đo theo từng layer, Bảng 3 của paper | **Xong** (2026-10-24); còn: hiệu chỉnh mô hình bộ nhớ theo board |
| 0b. Sửa lỗi tính đúng (phát sinh) | Lỗi làm phần cứng/mô phỏng tính sai | **Đã sửa:** #3, #13, #6, #7 (`NUM_GLB_IACT=3`), #14, #18, #19, #22, #25, #26, #30 (kẹp int8, ReLU gộp), #34 (MaxPool của `onnx2model` thành average, Python), #32 (thứ tự word bias khi nhiều filter chung một địa chỉ psum, Python), #31 (gồm #33, #35: lượt không có activation khác 0 làm mất mọi lượt sau; `PE.v`), #28, #29, #36, #38, #37 và #17 (2026-11-04, chép từ upstream `9498271` / `36395dd`, bỏ workaround Python), #39 (Python: số bộ weight của layer 1 channel nhiều lượt weight); #5 là báo động giả của testbench. **Còn mở:** #9, #12, #18b, #19b, #21, #23, #27, #28, #29, 3 channel (#7), hàm kích hoạt khác ReLU (#24); upstream `93f0e82` không sửa lỗi nào trong số này (mục 2) |
| 1. Giảm lưu lượng DMA | Bias theo filter, đóng gói weight, bảng quant theo F hoặc lưu BRAM, readout INT8 | Chưa làm. Đề xuất bắt đầu với bias |
| 2. Che độ trễ | Double-buffering (`BRANCHES=2`): nạp lượt sau trong lúc lượt hiện tại tính toán | Chưa làm (cần sửa lỗi chọn nửa buffer iact trước) |
| 3. Mô hình và DSE | Mô hình Python dự đoán chu kỳ và byte, roofline, quét cấu hình | Chưa làm |

**Giai đoạn 0: trạng thái chi tiết** (cập nhật 2026-11-02)

| Việc | Trạng thái |
|---|---|
| Profiler chu kỳ và beat DMA theo pha (`profile_dma_phases`) | Xong |
| Công cụ báo cáo + hiệu suất bus (`profile_report`) | Xong (pha của `Convolution_Single`; theo layer cho Conv/Dense của model, 2026-10-22) |
| Baseline 6 cấu hình Conv đơn (`doc/perf/baseline.md`) | Xong |
| CI lint theo baseline | Xong |
| **0.1 So sánh trước/sau**: `profile_report --compare`, `tools/run_profile.py` (mục 6.3–6.6) | **Xong** (2026-10-10) |
| **0.2 Mở rộng phạm vi đo**: payload/hiệu suất cho layer Dense (FC) và cho lượt nhiều layer (pha `writeback`), tách số liệu theo từng layer | **Xong** (2026-10-22, mục 6.13): bảng theo layer, tách `compute`/`writeback` ở trạng thái 11, 3 case model |
| **0.3 Cấu hình gần thực tế hơn**: 3 case kiểu MNIST (mục 6.7), baseline mới `baseline_2026-10-10` | **Xong** (2026-10-10) |
| Mô hình bộ nhớ ngoài (độ trễ burst, giới hạn băng thông) | **Xong** (2026-10-10, mục 6c); tham số chưa hiệu chỉnh theo board |
| Mốc phần cứng: tổng hợp + place & route Vivado (`tools/export_vivado.py`) | **Xong** (2026-10-12, cập nhật sau mỗi bản sửa RTL tới 2026-11-03, mục 6d): 250 MHz, 60,6k LUT, 39,8k FF, 192 BRAM tile, 12 URAM |
| Kiểm tra độc lập từng word + test dữ liệu ngẫu nhiên | **Xong** (2026-10-15, mục 6.12) |
| Baseline sau các bản sửa | **Xong**: `doc/perf/baseline_2026-11-04/` (12 case; trước đó `baseline_2026-11-02`, `baseline_2026-10-24`) |
| Đo hàm kích hoạt: pha `load_act`, chu kỳ khối kích hoạt, số 0 ở input từng layer | **Xong** (2026-11-02, mục 6.15) |
| Bảng 3 của paper đo bằng profiler (16 cấu hình, theo layer) | **Xong** (2026-10-24, mục 6.14); sau bản sửa #26 và #25: 13/16; **sau bản sửa #28, #29, #36 (2026-11-03): 16/16 cấu hình tính đúng cả mạng** |

### 8b. Tổng hợp lỗi phát hiện được (cập nhật 2026-11-07)

| # | Lỗi | Nơi | Trạng thái |
|---|---|---|---|
| 1 | Giải mã sai thứ tự output Conv ở chế độ SERIAL (124/128 giá trị sai ở 1×1 cluster, DMA 32 bit) | testbench Python | **Đã sửa** (`27aa75c`) |
| 2 | Bộ sinh tài liệu Verilog: 125 warning Sphinx, mất parameter | `doc/verilog_doc_parser` | **Đã sửa** (`83750e9`) |
| 3 | `GET_BIAS` rời trạng thái khi chưa nhận word bias cuối (treo khi DMA có khoảng trống) | `hdl/OpenEye_FPGA.v` | **Đã sửa** (`77f0477`), 0 chu kỳ, 0 tài nguyên |
| 4 | CI lint luôn fail (38 warning có sẵn) | `.github` | **Đã xử lý** bằng lint baseline (`4a26867`); RTL không đổi |
| 5 | Dense/FC: `FC activation write ... bank=1 addr=0` sai (23/63 test GEMM/Dense) | Testbench (`check_fc_activation_writes` trong `rtl_test_utils.py`) | **Không phải lỗi RTL** (kiểm chứng 2026-10-19, RTL có bản sửa #14): tắt bộ kiểm tra live (`OPENEYE_SKIP_FC_WRITE_CHECK=1`) thì **23/23 test PASS** (so với tham chiếu của testbench). Bộ kiểm tra so từng lần ghi RAM iact ngay khi xảy ra; theo upstream `18772d6`, với `NUM_GLB_IACT > 1` RAM được ghi tạm giá trị 0 rồi ghi đè ở các chu kỳ sau. **Cần viết lại bộ kiểm tra**: so nội dung RAM sau khi pha ghi kết thúc (mục 2, phần upstream) |
| 6 | Input 1 channel: chỉ ra bias | `hdl/iact_stream_constructor.v` | **Đã sửa** (2026-10-14, được bạn đồng ý): hồi quy do upstream `23be043`; RAM nay dùng lại địa chỉ 1-channel `ram_wr_addr_q`. Ảnh rộng một lượt x đã đúng; ảnh rộng hơn còn lỗi #17 |
| 7 | Input 3 channel và mọi `NUM_GLB_IACT=3`: giá trị sai | `iact_stream_constructor.v` (bank) + Python (3 channel) | **`NUM_GLB_IACT=3`: đã sửa** (2026-10-14, chỉ xoay bank khi Dense). **3 channel: chưa sửa** (lỗi cũ: Python đóng gói 3 byte/pixel, RTL đi theo cặp; đề xuất Python đệm số channel lẻ lên chẵn) **2026-11-07: phép kiểm tra `check_conv_geometry`** (Python) từ chối Conv có số channel lẻ lớn hơn 1 thay vì tính sai lặng lẽ; tài liệu (`doc/source/architecture/configuration.md` ví dụ đóng gói 3 channel, `tutorial/model_formats.rst` input RGB) coi 3 channel là được hỗ trợ, nên đây là lỗi thật (mục 8e). |
| 8 | 64 filter: `IndexError` trong `layer_parameters.read_data_from_layer` | Cấu hình | **Không phải lỗi code** (2026-10-14): bảng lượng tử có `QUANT_AMOUNT` entry, nên số filter phải ≤ `QUANT_AMOUNT`. Layer 64 filter cần `QUANT_AMOUNT=64` |
| 9 | Ảnh rộng 7 (có cột đệm): phần cứng ghi giá trị khác 0 vào ô đệm (giá trị thật vẫn đúng) | RTL/testbench | **Chưa sửa** |
| 10 | `CLUSTER_ROWS=1`: một số cấu hình treo FSM (theo tài liệu upstream) | RTL | **Chưa sửa**, chưa tự kiểm chứng đầy đủ. 2026-10-24: mạng Bảng 2 paper chạy hết cả 7 layer ở `CLUSTER_ROWS=1` (4 cấu hình), **không treo**; với X = 4 layer 0–4 tính đúng (sai còn lại là #25/#26) |
| 11 | Lint đáng ngờ: `PE.v:2210` (cắt 7→5 bit), `data_pipeline_wght.v:394/396/424` (overhead 4 bit). Cấu hình đang dùng có `SPARSITY_EN=1` nên các đường này **đang được dùng** | RTL | **`PE.v:2210`: đã sửa** (2026-10-21, lấy upstream `2bf497d` + mở rộng 0 tường minh; bộ đếm lên tới 64 ở Dense K = 512 nhưng lockstep cho thấy bản cũ vẫn cho cùng hành vi ở mọi trường hợp đã thử). **`data_pipeline_wght.v`: không sửa**; đã được mô hình hoá trong lỗi #22 (mục 9): tổng overhead 4 bit chỉ tràn khi 2 entry của một word cộng lại > 15, điều mà bộ mã hoá mới không tạo ra (2 entry một word luôn cùng một cột ≤ 16 filter) |
| 12 | `current_filter` (chỉ số filter của bộ lượng tử) chỉ được reset về 0, **không bao giờ tăng**, nên mọi filter dùng hệ số lượng tử của filter 0 (lượng tử theo filter chưa hoạt động) | `hdl/psum_pipeline.v` | **Chưa sửa**, phát hiện bằng đọc code (2026-10-10), chưa kiểm chứng bằng test. Test hiện tại dùng hệ số giống nhau cho mọi filter nên không phát hiện được |
| 13 | `rd_cycle_loop_cnt_0..3` bị lái từ 2 khối `always` (reset ở khối này, đếm ở khối kia). Vivado giữ giá trị reset nên trên FPGA các bộ đếm **luôn bằng 0**; mô phỏng không thấy | `hdl/iact_stream_constructor.v:233/437` | **Đã xác nhận bằng thí nghiệm** (2026-10-13, `doc/experiments/2026-10-13_bug13_stuck_counters.md`): giả lập phần cứng thì 6/9 case baseline FAIL (mọi case có `iact_read_limit_1..3` ≠ 0, gồm cả 3 layer MNIST), đối chứng PASS. **Đã sửa** (`5f1e66e`, 2026-10-13, được bạn đồng ý): 0 chu kỳ, 79 test hồi quy không đổi; Vivado 2026-10-14: CRITICAL WARNING 200 → 0, vẫn đạt 250 MHz (mục 9) |
| 14 | `results_ready` vừa gán blocking vừa non-blocking (lint `BLKANDNBLK`, 4 lỗi); Vivado Synth 8-6090: "entire logic could be removed" | `hdl/psum_pipeline.v` | **Đã sửa** (2026-10-19, được bạn đồng ý; phân tích 2026-10-16). Phần cứng Vivado trước đó vẫn đúng; lỗi thật là code không khả chuyển (netlist Yosys treo, Verilator từ chối). Tách phần AND tổ hợp ra khỏi thanh ghi, chỉ còn gán `<=`. Lockstep cũ/mới trên 125 test: 0 sai khác; netlist Yosys nay PASS; lint −4 lỗi −3 cảnh báo; Vivado hết 10 cảnh báo 8-6090, vẫn 250 MHz (mục 9) |
| 15 | 12 thanh ghi có set và reset cùng mức ưu tiên (Synth 8-7137, "may cause simulation mismatches") | `psum_pipeline.v:322/776`, `OpenEye_Parallel.v:443/448`, `PE.v:1113` | **Chưa phân tích** |
| 16 | Wrapper AXI `fpga/hdl/open_eye_axi_v1_0.v` không biên dịch được (thiếu module `cfg_reg`, `QUANT_AMOUNT` chưa khai báo, `BUFFER_WIDTH` gán 2 lần, `RAM_CELLS` không tồn tại) | `fpga/hdl` | **Chưa sửa**; chỉ cần khi đóng gói IP hoặc làm block design |
| 17 | 1 channel với ảnh rộng hơn một lượt x (ví dụ MNIST Conv1 28×28): các hàng output đi theo cặp giống nhau | `iact_stream_constructor.v` (bộ ghi 1 channel), `data_pipeline_iact.v` | **Đã sửa 2026-11-04** (được bạn đồng ý, hàng O, mục 9 "Sửa #37, #17", `doc/experiments/2026-11-04_rowO_bug17_bug37.md`), như upstream `36395dd`: bỏ cách gói 2 hàng ảnh vào 1 word (địa chỉ hàng + cột không tính các lượt x), mỗi pixel 1 word, PE lấy sub-word 0; `channel_pad` (workaround Python từ 2026-10-22) tắt mặc định. Rộng 20/40 và MNIST Conv1 28×28 1 channel PASS (trên RTL cũ: FAIL) |
| 18 | Filter 32–63 sai (MNIST Conv2/Conv3); thực chất **mọi layer > 4 channel tính sai với weight thật** | `src/open_eye/conv_mapper.py` (Python) | **Đã sửa** (2026-10-15, được bạn đồng ý; xoá khoá `used_wght_per_PE` bị lặp). Kiểm chứng từng word bằng tính toán numpy độc lập (mục 9). Conv2 MNIST thật PASS, Conv3 đúng mọi giá trị; baseline −16 % đến −25 % chu kỳ |
| 18b | Số filter > 32 và không chia hết cho 32 (40, 48): sai từ cả filter 0 | Python/psum address generator | **Chưa điều tra xong**: Python báo 768 word ra nhưng tạo tham chiếu 1.024 dòng. MNIST không dùng |
| 19 | Dense có K > 512 input sai (MNIST: Dense 784 → 10 của mạng trong repo, FC 3136 → 10) | `hdl/iact_stream_constructor.v:218`, `hdl/OpenEye_FPGA.v:2163` | **Đã sửa** (2026-10-21, được bạn đồng ý; `doc/experiments/2026-10-21_bug19_dense_k512.md`). Hai nguyên nhân: (1) bộ đếm vị trí cặp `x_pos_in_w_cycle` 8 bit quay vòng ở cặp 256 → activation ≥ 512 bị bỏ; (2) `current_x` có dấu 12 bit âm từ activation 2048 → activation ≥ 2048 bị bỏ. Sửa: bộ đếm 12 bit, điều kiện lưu của FC không dùng dấu của `current_x`. Loạt K 64 … 4032 (gồm 784 và 3136) đều đúng từng output so với numpy |
| 19b | Dense N = 32 output với từ 8 lượt K (K ≥ 508) | ? | **Chưa rõ nguyên nhân**: K ≤ 504 đúng, 508/512 sai; N = 16/24 ở K = 512 đúng. Sai ở phía weight hoặc psum, không phải kiểu mất activation. 2026-10-24: Dense 1568→32 (của paper) đúng ở `CLUSTER_ROWS=2` nhưng sai 32/32 ở `CLUSTER_ROWS=1` (giá trị gần đúng, lệch vài đơn vị), ghi khi đó là "cùng họ lỗi": **sai, 2026-11-03: đó là #29** (tràn bộ đệm weight, mục 9). Ở #19b con trỏ đọc bộ đệm weight chỉ tới 768 hàng, không tràn, nên #19b là cơ chế khác, vẫn chưa rõ và không dính tới Bảng 3. 2026-10-31: upstream `93f0e82` cũng sai y như vậy (mục 2) **2026-11-07: chưa tái hiện lại được**: Dense 512 → 32 và 508 → 32 ở đúng cấu hình gốc (CR 2, `NUM_GLB_IACT` 3, `doc/experiments/2026-11-07_bug41_stride/dense_run.py`, seed 1) PASS trên `dev` và **cả trên commit lúc phát hiện** (`10bcaf7`); script gốc `dense_k.py` chạy dữ liệu không cố định seed, nên lỗi có thể phụ thuộc dữ liệu, nhưng thêm seed 2–5 trên `dev` cũng PASS cả 4. Không thêm phép kiểm tra (chưa có điều kiện). |
| 20 | `PE.v:829–830`: tham chiếu "tiến" `gen_sparse_fsm.wght_addr_vec` / `wght_addr_use_vec` / `wght_data_use_vec` vào khối generate khai báo sau (dòng 978). Icarus, Verilator, Vivado hiểu đúng; **Yosys tạo dây 1 bit không ai lái** ("implicitly declared") | `hdl/PE.v` | **Chưa sửa** (phát hiện 2026-10-21). Cùng loại với #14 (nghĩa phụ thuộc công cụ). Đề xuất: khai báo 3 tín hiệu ở cấp module trước hai khối generate. |
| 21 | Dense N > 32 output (cần 2 lượt psum): sai với mọi K | Bước đọc kết quả cuối (`PSUM_SEND_RESULTS` hai lượt) hoặc cách testbench giải mã nó; **không** phải phép tính | **Chưa sửa** (phát hiện 2026-10-21): K = 64, N = 40 chỉ đúng 10 output đầu, N = 48 chỉ đúng 12 output đầu (= P output đầu); N = 32 đúng. 2026-10-24 (điều tra #26): Dense 16→64 làm layer cuối sai 48/64, nhưng cùng layer đó ghi ngược trên chip (cách sửa #26 giả lập) cho đủ 64 giá trị đúng, nên psum buffer đúng **2026-11-07: phép kiểm tra `check_dense_readout`** (Python) từ chối Dense làm layer cuối cần hơn một lượt psum (> 16 × `Clusters_X` output); Dense ghi ngược trên chip vẫn chạy. Tài liệu không ghi giới hạn này: lỗi thật. |
| 22 | Conv có **weight bằng 0** tính sai hoặc treo (mọi mẫu số 0 trừ "mỗi cột một số 0 ở đầu"; model MNIST int8 đã huấn luyện: Conv2 140/384, Conv3 116/384 lần nạp weight sai) | Định dạng nén weight: mapper Python không khớp cách `data_pipeline_wght.v` giải mã (cột rỗng, ô đệm, overhead 4 bit, reset địa chỉ ở word 0) và bộ ghép stream | **Đã sửa** (2026-10-24, được bạn đồng ý, **chỉ Python**): `conv_wght_encoding.py`; stream giống hệt khi không có số 0; MNIST Conv1/2/3 với weight đã huấn luyện tính đúng mọi output. Mục 9 |
| 23 | `test_conv3x3_sparse` 32×4×8 → 16 (iact và weight thưa dạng bàn cờ, `NUM_GLB_IACT=3`) sai: output 0 ở các x lẻ của hàng 1 | ? (phía activation thưa: weight của ca này giải mã đúng theo mô hình RTL) | **Chưa điều tra** (có từ trước bản sửa #22: code cũ cũng fail, kiểu sai khác). 2026-10-31: upstream `93f0e82` cũng sai y như vậy (mục 2) 2026-11-07: phụ thuộc dữ liệu (mẫu thưa), chưa rõ nguyên nhân nên chưa có điều kiện tĩnh để chặn. |
| 24 | **Không có hàm kích hoạt**: `af_cluster.v` (ReLU) không được dùng ở đâu, còn 2 lỗi (so sánh `< 0` trên dây không dấu, chọn bit `[a:+b]` sai), testbench riêng lỗi thời; `af_cluster_mode` chỉ reset về 0, không có trường cấu hình | RTL | **Giải quyết cho ReLU** (2026-10-28, được bạn đồng ý): ReLU đứng ngay sau Conv/Dense được thực hiện bằng cận dưới của bộ kẹp int8 trong `quantization_unit.v` (`act_min = 0`), đúng cách TFLite làm "fused ReLU", không cần `af_cluster`. `af_cluster.v` vẫn không dùng (giữ nguyên, 2 lỗi của nó không cần sửa). Hàm không phải dạng kẹp: **có từ 2026-11-02** (được bạn đồng ý, bước B, `doc/experiments/2026-11-02_activation_rtl.md`): Leaky ReLU bằng độ dốc thứ hai trong bộ lượng tử, SiLU / hard-swish (và mọi hàm int8 → int8 khác: sigmoid, tanh, GELU…) bằng bảng 256 ô sau bộ lượng tử. Mục 9 |
| 25 | `NUM_GLB_PSUM = 2` (PE trục X = 2): mọi model nối một Conv với layer khác trên chip tính sai (cả 8 hàng X = 2 của Bảng 3). Ghi chú cũ "sau Conv2 lại đúng" là sai: kiểm tra đó bị bỏ qua | **Pha ghi ngược của Conv**: RTL (`RECEIVE_PSUMS_TO_IACT` gom nhóm `WRITEBACK_WORDS` = 2 channel thay vì 4 channel/pixel, và đếm pixel đệm theo nhóm) + Python (`fsm_psum_limit` chia 4 thay vì `NUM_GLB_PSUM`) | **Đã sửa** (2026-10-26, được bạn đồng ý): RTL `RECEIVE_PSUMS_TO_IACT` gom nhóm 4 channel/pixel với mọi số lane (`WRITEBACK_CHANNELS`), chỉ phát W lane, `x_pos` đếm theo pixel; Python `fsm_psum_limit` chia theo số lane. Với `NUM_GLB_PSUM = 4` mạch như cũ. Test mới 7/7, hồi quy 146 test 0 FAIL, 12 case mốc 0 chu kỳ lệch, lint 0 mới, Bảng 3 13/16 cấu hình PASS (còn #19b, #28). Mục 9 |
| 26 | **Dense nối tiếp Dense trên chip** (MLP, Dense 1568→32 → Dense 32→10 của paper): Dense đầu tính psum **đúng** nhưng pha ghi ngược (`SEND_PSUM_TO_IACT` + `RECEIVE_PSUMS_TO_IACT`) **không ghi gì** vào bộ đệm iact, Dense sau đọc lại input của Dense đầu; mọi cấu hình, mọi K, N | Python (`fsm_psum_limit` quá ngắn, vòng đọc psum không cấu hình cho Dense) **và** RTL (bộ đóng gói chỉ biết bố cục conv; nhánh FC bị upstream bỏ ở `1320759`/`8350a00` để giảm LUT) | **Đã sửa** (2026-10-24, được bạn đồng ý): 1 dòng RTL (`x_pos` quay về 0 ở mỗi nhóm khi FC) + thanh ghi Python (`configure_fc_writeback`). 11/11 chuỗi Dense qua RTL, hồi quy 128 test không đổi, 12 case mốc 0 chu kỳ lệch, Bảng 3: 7/8 cấu hình X = 4 tính đúng cả mạng. Mục 9 |
| 27 | Pooling 4×4 → 2×2 (lần pooling thứ hai của `Conv_Pool_Conv_Pool_Conv` với input 8×8): bộ đệm sau pooling chứa −128 (giá trị khởi đầu của max-pool) và 2 ô không được ghi; xảy ra với cả `NUM_GLB_PSUM` 4 và 2; input 16×16 thì đúng | ? (pooling, kích thước nhỏ) | **Chưa điều tra** (phát hiện 2026-10-26 khi viết test cho #25). 2026-10-31: upstream `93f0e82` cũng sai, còn sớm hơn (ở lần kiểm tra bộ đệm iact đầu tiên, mục 2) **2026-11-07: đo điều kiện** (Conv_Pool_Conv, CR 2 × CC 2, `run25.py`): input pooling rộng 2 và 4 sai ở mọi chiều cao (cả 4 × 8), rộng 6 và 8 đúng (cả 8 × 4); 6 × 6 chỉ có một ô đệm khác 0 (#9), giá trị đúng. **Phép kiểm tra `check_pooling_geometry`** từ chối pooling có input rộng ≤ 4 và cửa sổ khác 2 × 2 / stride 2 / không đệm (tài liệu: "2×2 max-pooling on-chip"). |
| 28 | Conv ở `CLUSTER_ROWS=1` với `NUM_GLB_PSUM=2` tính sai một số output: conv2 của mạng paper sai đúng 1 pixel (x = 3 hoặc 7, mọi filter), đổi chỗ theo seed. (Ghi cũ "Conv 14×14 32 → 32 channel sai" là lỗi khác, #37.) Cùng với #36 là nguyên nhân của 2 hàng CR 1 X 2 còn FAIL trong Bảng 3 | `hdl/psum_pipeline.v`: `chain_ready_terms` → `all_psum_ready` chỉ xét GLB chẵn của mỗi cặp | **Đã tìm ra nguyên nhân** (điều tra 2026-11-03, mục 9, `doc/experiments/2026-11-03_table3_cr1.md`): ở `CLUSTER_ROWS=1` mọi cột PE là đầu chuỗi nhưng cột lẻ không được xét, nên FSM psum bắt đầu thu khi một cột lẻ còn đang tính; nếu cột đó trễ ≥ 3 chu kỳ, PE hàng 1 của nó bắt đầu cùng lúc với hàng 2 và bỏ mất psum của hàng 2. Phụ thuộc dữ liệu (bỏ qua số 0 làm thời gian tính khác nhau). Giả lập bản sửa (AND cả 4 bit ready) chữa được mọi ca lỗi, 0 đến ±16 chu kỳ. **Đã sửa 2026-11-03** (được bạn đồng ý, mục 9): ở CR 1 điều kiện xét cả hai GLB của mỗi cặp. Upstream `93f0e82` có cùng đoạn code |
| 29 | Dense K = 3136 với ≥ 32 output tính sai trên RTL (chuỗi 3136 → 64 → 10, 3136 → 32 → 10 sai từ kiểm tra bộ đệm sau Dense đầu; 2026-10-31: Dense 3136 → 32 **một layer** cũng sai 32/32, cả trên upstream); 2560 → 32, 2048 → 32, 1024/512/256 → 64, 3136 → 16, 3136 → 10 đúng. Chặn Dense 3136 → 64 của model MNIST int8 đã huấn luyện. **Cùng lỗi: Dense 1568 → 32 ở CR 1 Y 3 của Bảng 3** (trước đây ghi nhầm là #19b) | `hdl/OpenEye_FPGA.v` `GET_WGHT`: bộ đệm weight `2^BUFFER_WIDTH_WGHT` = 4.096 hàng, con trỏ ghi 12 bit quay vòng | **Đã tìm ra nguyên nhân** (2026-11-03, mục 9): Dense nạp weight của mọi lượt K một lần; 1568 → 32 ở CR 1 Y 3 và 3136 → 32 ở CR 2 X 4 Y 3 cần 4.224 hàng, 128 hàng cuối ghi đè lên weight của khoảng 48 input đầu. Ngưỡng đúng 4.096 hàng (4.032 PASS, 4.128 FAIL); `BUFFER_WIDTH_WGHT=13` (tham số, không sửa logic) cho cả mạng CR 1 X 4 Y 3 PASS. **Đã sửa 2026-11-03** (được bạn đồng ý, mục 9): `BUFFER_WIDTH_WGHT` mặc định 13 (8.192 hàng) và toolchain từ chối layer không vừa (`check_wght_buffer`). Dense 3136 → 64 (8.448 hàng) vẫn cần 14 bit hoặc tách layer. Không phải tràn trường thanh ghi |
| 30 | Bộ lượng tử **không kẹp int8**: lấy 8 bit thấp, giá trị tràn bị quấn vòng (130 → −126, −129 → 127); tham chiếu Python cũng không kẹp nên mọi test PASS (dữ liệu test chưa từng tràn). Đưa model MNIST int8 thật vào phần cứng: **9,3 %** thay vì 99,2 % (giả lập) | `quantization_unit.v` | **Đã sửa** (2026-10-28, được bạn đồng ý): kẹp về `[act_min, 127]`, `act_min` theo layer (thanh ghi `quant_clamp_low`). Test mới 9/9 RTL + 2/2 bộ lượng tử, đối chứng âm 9/9 FAIL trên RTL cũ, hồi quy 157 test 0 FAIL, 12 case mốc 0 chu kỳ lệch, lint 462. Mục 9 |
| 31 | Conv/Dense **mất mọi lượt tính từ một lượt rỗng trở đi**: lượt mà không PE nào có activation khác 0 (Conv 3×3: cửa sổ 3 hàng input toàn 0 trên phần hàng một lượt phủ; Dense: một khối K input của lượt toàn 0) và mọi lượt sau không được tính, output giữ bias (+ các lượt trước); layer vẫn chạy hết, không treo. Ảnh MNIST thật: Conv1 ra bias ở cả 25.088 output (hàng trên của ảnh trống), Conv2 ở 12.320/12.544. Dữ liệu test ngẫu nhiên không có số 0 (`DRAMContents` thay 0 bằng ±1) nên không lộ | RTL điều khiển: PE chỉ bắt đầu lượt khi có activation khác 0 (`PE.v:1135`); `OpenEye_FPGA.v` đếm lượt (Process 2) và khởi động lượt converter/weight kế tiếp (Process 5) khi bus iact ready của mảng PE rời trạng thái toàn 1, việc chỉ xảy ra khi có PE bắt đầu tính | **Đã sửa** (2026-10-30, được bạn đồng ý, hướng A, `PE.v`; mục 9, `doc/experiments/2026-10-30_bug31_fix.md`): trạng thái mới `EMPTY_PASS`: PE rỗng rời IDLE cùng nhịp PE có dữ liệu (lượt được đếm, lượt sau được nạp), giữ iact/wght ready thấp tới khi FSM psum đọc lượt đó, rồi chuyển psum đi qua như PE rảnh. Upstream `93f0e82` cũng bị |
| 32 | Conv3 7×7×64 → 64: **bias của cặp filter (2k, 2k+1) bị đổi chỗ** (output = đúng + b[2k+1] − b[2k] ở filter 2k và ngược lại, ở mọi vị trí; các tích đúng). Xảy ra khi một địa chỉ bộ đệm psum chứa nhiều filter (`different_kernels_per_calculation` = 2: cặp đổi chỗ; = 4: nhóm 4 filter đảo ngược); Conv1/Conv2 của model là 1 nên đúng. Mọi test trước đây cho mọi filter bias 1 nên không thấy. Upstream cùng code | Thứ tự word bias: `psum_stream_mapper` gửi filter theo thứ tự tăng, còn `psum_pipeline.v` (GET_BIAS) dịch word vào từ dưới nên word đầu nằm ở lane trên cùng (cluster row 1), trong khi tính toán và đọc ra đặt nhóm kernel 0 ở cluster 0 | **Đã sửa** (2026-10-30, được bạn đồng ý, chỉ Python, `doc/experiments/2026-10-30_bug32_bias_order.md`): `psum_stream_mapper` gửi các filter của mỗi địa chỉ bộ đệm psum theo thứ tự nhóm kernel ngược (`bias_stream_filter_order`); cùng số word, không đổi chu kỳ, không sửa RTL. Test `test_psum_bias_order.py` (22), `test_conv_bias_order` (RTL, 2 và 4 nhóm kernel); model thật ảnh 1 PASS trọn mạng |
| 33 | Dense 3136 → 10 (10 output đầu của fc1 đã huấn luyện) với input thật: ảnh test 0 sai cả 10 output, ảnh 1 đúng | **Cùng nguyên nhân #31**: kết quả của ảnh 0 bằng đúng bias + tích của input 0…2653; input 2654 mở đầu chuỗi 109 số 0 (một lượt rỗng); chuỗi 0 dài nhất của ảnh 1 là 75 | **Đã sửa** cùng #31 (Dense 3136 → 10 có khối 0: đúng) |
| 34 | Đường model thật (`USE_RANDOM_VALUES=0`): layer MaxPool của `onnx2model` bị cấu hình thành **average pooling** (`pooling_mode` 1, giới hạn vòng lặp 8/16 thay vì 112): `onnx2model.get_model` đặt tên mọi layer bằng loại (`pooling2d`), còn `LayerParameters.write_pooling_layer` chọn max khi tên chứa `max`. RTL sai từ bộ đệm sau pooling đầu (784/784 word). Upstream có cùng code | Python (`onnx2model`) | **Đã sửa** (2026-10-30, chỉ Python): layer MaxPool tên `max_pooling2d`; xác nhận trên RTL (đổi tên bằng probe → qua kiểm tra sau pool1, pool2). Mục 8d |
| 36 | Dense **đọc ra cuối** ở `CLUSTER_ROWS=1`, `NUM_GLB_PSUM=2`: các output nằm ở cụm cột 1 ra 0 (Dense 32 → 10: f 6–9 = 0; mạng paper CR 1 X 2: 4/10 output cuối) | `hdl/psum_pipeline.v`: `psum_readout_src`, `psum_buffer_data_temp_reg` rộng `20 × CLUSTERS × NUM_GLB_PSUM` = 80 bit | **Đã tìm ra nguyên nhân** (2026-11-03, mục 9): khi đọc Dense, kết quả của cụm cột cc đặt ở bit cc × 64; cc = 1 cần bit 64–83 > 80 nên bị điều kiện bảo vệ bỏ qua. Giá trị được ghi đúng vào bộ đệm psum (trace). CR 1 X 4, CR 2: thanh ghi 160 bit, đúng. **Đã sửa 2026-11-03** (được bạn đồng ý, mục 9): hai thanh ghi rộng `max(..., CLUSTER_COLUMNS × DMA_BITWIDTH)`. Upstream cùng code |
| 37 | Conv 14×14×32 → 32 ở CR 1 X 2: mọi output = bias | `regmap.yaml`: `iact_buffer_words_per_write`, `iact_write_inc_2` 12 bit | Phát hiện 2026-11-03 (mục 9): layer cần giá trị 4.096, không vừa 12 bit (đến nơi là 0); 24/28 channel (3.072/3.584) đúng. Không thuộc Bảng 3. **Đã sửa 2026-11-04** (được bạn đồng ý, hàng O, mục 9 "Sửa #37, #17"), như upstream `9498271`: 10 trường bộ đệm iact, dây và thanh ghi địa chỉ của constructor 13 bit (= địa chỉ bộ đệm 8.192 word); toolchain từ chối layer cần quá 8.191 word mỗi lượt (`check_iact_buffer`); số word trạng thái vẫn 28 / 14 / 7. Test `test_cluster_rows1[conv14_c32_x2]` PASS (RTL cũ: 32/32 feature map sai) |
| 38 | Mantissa của hệ số lượng tử lại bị cắt còn 8 bit: `OpenEye_FPGA.v` cắt trường mantissa (25 bit) và exponent bằng `+:OFFSET_WIDTH` (8), nên mantissa ≥ 256 thành `mant mod 256`. Toolchain né bằng cách chỉ dùng mantissa < 256 (ghi chú (F) mục 8d); Verilator đã cảnh báo hai dòng này từ trước (`WIDTHEXPAND`, `WIDTHTRUNC`) | `hdl/OpenEye_FPGA.v` (khối gán `quant_offset/exp/mant`) | **Đã sửa 2026-11-04** (được bạn đồng ý, mục 9, `doc/experiments/2026-11-04_bug38_mantissa.md`): lát cắt đúng độ rộng; `onnx2model.MANT_BITS` 8 → 24 (độ dốc âm Leaky vẫn 8 bit); test mới `test_quant_mantissa.py` (đối chứng âm 3/3 FAIL, sau sửa 3/3 PASS); kết quả gần ONNX Runtime hơn một chút |
| 39 | Input 1 channel với hơn 16 filter mỗi lần tính (từ 2 lượt weight, ví dụ MNIST Conv1 32 filter, 8×4×1 → 64): nhóm filter thứ hai (16–31) được tính bằng weight của nhóm đầu (0–15), bias đúng | `src/open_eye/layer_parameters.py` (Python: `wght_transmissions_pe` của nhánh nhiều filter = `ceil(channels / channel_div_trans)`, tức số lô channel, không phải số nhóm filter) | **Phát hiện và sửa 2026-11-04** khi bản sửa #17 thôi đệm MNIST Conv1 (mục 9 "Sửa #37, #17", `doc/experiments/2026-11-04_rowO_bug17_bug37.md` mục 3): có từ trước (RTL cũ 8×4×1 → 64: 64/64 feature map sai), upstream `36395dd` cũng có. Stream weight chỉ chứa 1 lượt trong khi RTL đọc `needed_wght_cycles` lượt; nay = số lô channel × số nhóm filter. Chỉ layer 1 channel nhiều lượt weight đổi tham số (315 cấu hình); test `test_weight_sets_cover_every_pass`, `test_random_data[8x4_c1_f64]`. **2026-11-05** (`doc/experiments/2026-11-05_bug39_detail.md`): điều kiện chính xác (kernel 3×3) = 1 channel và hơn 16 filter mỗi lần tính; RTL tính đúng (nhóm filter weight 0 ra bias) nhưng không kiểm tra độ dài stream, nên đọc hàng chưa ghi (X trong mô phỏng → SPAD giữ weight lượt trước; trên FPGA là 0 hoặc weight cũ); chưa từng làm sai kết quả đã commit. Thêm **`check_wght_sets`** (Python): từ chối layer có số bộ weight ≠ số lượt × số lô channel. Còn **#39b** (nhánh tile, số filter không chia hết hệ số chia, ví dụ 3 channel × 64 filter): bị từ chối, sửa sau cùng #7 / 1×1 / 7×7. Upstream `36395dd` và `b10db82` có cùng lỗi Python |
| 40 | Conv có **lượt weight cuối thiếu filter** (số filter mỗi lần tính không chia hết số psum mỗi PE, ví dụ 28×28×1 → 24 = 16 + 8, 8×4×1 → 48 = 32 + 16, cả 2 channel): FAIL toàn bộ feature map | Python: `src/open_eye/layer_parameters.py:1469` `psum_output_words` và :1274 `trans_cycles_psum` tính bằng số filter thật; `src/open_eye/test_utils_main.py:574` `filter_cycles` làm tròn xuống (dòng 620 chỉ sang khối x mới khi `filter >= filters`) | **Phát hiện 2026-11-05** khi điều tra lỗi treo của upstream `b10db82` (mục 9 "Lỗi treo của `b10db82`", `doc/experiments/2026-11-05_b10db82_hang.md` mục 4). RTL tính **đúng**: giải mã theo thứ tự đã đệm thì mọi giá trị DUT gửi ra bằng numpy (14.112/14.112), nhưng RTL tính và gửi đủ ô filter đệm (passes × psum/PE × kernel) còn host chỉ cho phép `psum_output_words` word, nên phần cuối (1/4 với 16 + 8) không bao giờ ra khỏi chip; tham chiếu của testbench cũng sai. Không ảnh hưởng kết quả đã commit (hồi quy, Bảng 3, MNIST đều chia chẵn). Lưới k3: 162/2.880 cấu hình lọt qua `check_wght_sets`. Upstream có cùng công thức. **Hướng 1 đã làm 2026-11-05** (được bạn đồng ý): phép kiểm tra **`check_full_passes`** (Python, `ConvMapper`) từ chối layer có số ô filter (lượt × psum/PE × kernel mỗi lần tính) ≠ số filter; quét tĩnh 78 layer Conv của Bảng 3, 12 ca mốc, 4 model hàm kích hoạt: 0 bị chặn. Còn để ngỏ: chia đều psum mỗi PE (hướng 2), đệm trong toolchain (hướng 3) |
| 35 | Conv3 7×7×64 → 64 của model thật khi ghi ngược cho Dense: ghi chép cũ là "cột cuối x = 6 sai" (đọc nhầm layout) | **Chính là #31**: các output sai nằm ở **hàng output cuối y = 6**; trong cửa sổ của hàng này nhóm channel 44–47 không có activation khác 0 → lượt đó và mọi lượt sau bị mất (mô hình khớp DUT 448/448 giá trị) | **Đã sửa** cùng #31 (`test_real_model[0]` PASS) |
| 41 | Conv **stride 2** tính sai: 8×8×4 → 16, stride 2 (CR 2 × CC 2, dữ liệu ngẫu nhiên, seed 1): 16/16 feature map sai, 207/256 giá trị; theo cửa sổ (`window_map.py`): DUT tính tâm (x, 2y) thay vì (2x, 2y), tức trục X không có stride, trục Y đúng ở 3/4 hàng, hàng output cuối thiếu hàng kernel cuối | **Cấu hình**: stride là phần tuỳ chọn của RTL, tham số `STRIDE_ENABLED` của `OpenEye_FPGA.v` (mặc định 0, từ upstream `2e3b351`, 16/09) buộc `stride_x/y = 1` (dòng 369–370), trong khi Python vẫn lập trình vòng đọc theo stride (trục Y) | **Điều tra 2026-11-07** (`doc/experiments/2026-11-07_bug41_stride.md`, không sửa RTL): dựng với `STRIDE_ENABLED=1` thì stride 2 **PASS** ở độ rộng 8, 16, 24, 28, 32 (mọi chiều cao) nhưng **vẫn FAIL** ở độ rộng 4, 6, 7, 9, 12 (`NUM_GLB_PSUM` 2: 4, 8 đúng, 6 sai) = **#41b**: các giá trị là cửa sổ đúng nhưng sai vị trí / thiếu (12×8: giải mã được 224/384 ô); **nguyên nhân tìm ra 2026-11-08** (2 lỗi Python, hàng #41b dưới); stride 1 PASS cùng số chu kỳ (33.150 ns). Tài liệu mô tả stride là tính năng (thanh ghi `stride_x/y_reg` 1–8, PE trượt C0 × U), mục "Test Coverage Gaps" ghi stride 2 chưa test, `STRIDE_ENABLED` không có mô tả: hai lỗi: #41 là lỗi cấu hình / toolchain (nhận stride khi phần cứng mặc định không có), #41b là lỗi thật của đường stride tuỳ chọn; không phải lỗi phép nhân-cộng. Upstream `b1e02a0`: cùng mặc định, cùng lỗi; với `STRIDE_ENABLED=1` stream ra khớp tham chiếu nhưng testbench upstream giải mã lệch một hàng. Thêm: "same" của TensorFlow với stride 2 trên ảnh chẵn đệm [0, 1], khác RTL [1, 1]. **Phép kiểm tra `check_conv_geometry`** từ chối mọi stride > 1 (với `STRIDE_ENABLED=0`: #41, với `STRIDE_ENABLED=1`: #41b) và padding kiểu TF lệch. **2026-11-08: #41b, #41c, #41d đã sửa** (hàng dưới, mục 9); phép kiểm tra nay chỉ từ chối stride khi `STRIDE_ENABLED=0`. **2026-11-09: `STRIDE_ENABLED = 1` là mặc định** (đề xuất 5, được bạn đồng ý; Vivado +155 LUT, đạt 250 MHz). Tái hiện: mục 3c "Tái hiện các lỗi" |
| 41b | Stride 2 với `STRIDE_ENABLED=1` sai ở độ rộng 4, 6, 7, 9, 12 (đúng ở 8, 16, 24, 28, 32) | Python: (A) `test_utils_main.py:593` `calculate_conv_serial` chuyển kernel khi `x_cor >= psum_size_x + add_up` (`add_up` = pixel input = `psum_add_up` × stride) thay vì `psum_add_up` (vị trí output): thứ tự giải mã / stream tham chiếu lệch 4 ô mỗi filter khi một lần tính có nhiều kernel; (B) `layer_parameters.py:842` `iact_x_add_up = iact_size_x + add_up` cho ảnh lẻ (7 → 7, 9 → 15) thay vì (số output + `psum_add_up`) × stride (8, 16): vòng x của constructor dừng sớm một cột | **Điều tra 2026-11-08** (`doc/experiments/2026-11-07_bug41_stride.md` mục 8, công cụ `slot_map.py`, bản vá thử `fix41b_scratch.patch`; không sửa file nào của `dev`): A + B trong worktree tạm → mọi layer stride 2 đơn lẻ đã thử (rộng 4–32, `NUM_GLB_PSUM` 2 và 4) đúng giá trị (chỉ ô đệm khác 0 = #9); stride 1 không đổi, cùng số chu kỳ. **Đã sửa 2026-11-08** (được bạn đồng ý, mục 9 "Sửa #41b, #41c, #41d") |
| 41c | Hai Conv stride 2 nối tiếp (ghi ngược trên chip): bộ đệm iact sau layer đầu sai (8×8: 4/8 word) | RTL `OpenEye_FPGA.v` `RECEIVE_PSUMS_TO_IACT`: đếm pixel output theo `iact_size_x` (dòng 2344) và quay vòng hàng ở `iact_x_add_up` (dòng 2384), tức kích thước input | **Phát hiện 2026-11-08**: bản vá thử (chỉ worktree) dùng `psum_size_x` (Dense giữ `iact_size_x`) và `iact_x_add_up / stride_x` → chuỗi 8×8, 16×16, 14×8 PASS, 12×8 đúng giá trị; chuỗi stride 1 và Conv → Pool → Conv giống hệt, cùng số chu kỳ. **Đã sửa 2026-11-08** (được bạn đồng ý, mục 9): 2 dòng RTL, quay vòng viết dạng tích `x_pos × stride_x ≥ iact_x_add_up − stride_x` (không có bộ chia; với `STRIDE_ENABLED=0` `stride_x` là hằng 1) |
| 41d | Layer stride 2 đọc input do pha ghi ngược tạo ra có **chiều cao lẻ**: hàng output cuối sai (14×14 → 7×7 → 4×4, 16×14 → 8×7 → 4×4: chỉ y = 3 sai; 10×10 → 5×5 → 3×3: chỉ y = 2) | Python `layer_parameters.py`: số hàng mỗi lượt `iact_size_y + kernel − strideY` = H + 1 khi stride 2, đủ cho cao chẵn (tâm cửa sổ cuối H − 2) nhưng thiếu hàng đệm dưới cho cao lẻ (tâm H − 1 cần hàng H); stride 1 che hàng đó, nên rác pha ghi ngược để sau ảnh (có cả ở stride 1) không lộ | **Phát hiện và sửa 2026-11-08** (được bạn đồng ý, mục 9): `iact_y_add_up = ⌈H / strideY⌉ × strideY` thay `iact_size_y` trong 3 công thức (giống B theo trục x); chuỗi 16×14 → 8×7 → 4×4 và Conv → Pool → Conv 28×28 (bộ đệm có dữ liệu cũ) PASS |
| 42 | Toolchain **bỏ qua padding của model**: `LayerParameters` luôn dùng `padding = "same"` (`layer_parameters.py:355`, đệm `kernel // 2` mỗi bên, dòng 799), còn `padding_pads` mà `onnx2model` đọc từ ONNX không được dùng. Conv `padding = 0` ("valid", ví dụ LeNet-5) hay đệm lệch (TF "same" với stride 2) được tính như "same" | Python | **Phát hiện 2026-11-07** bằng đọc code (mục 8e), chưa chạy. Model MNIST trong repo dùng `padding = 1` (= "same") nên không bị **2026-11-07:** tài liệu RTL ghi `padding_reg = (kernel_size - 1) / 2`: chỉ có padding "same" là **giới hạn thiết kế**; lỗi là toolchain không báo. **Phép kiểm tra `check_conv_geometry`** đọc padding của model (`model_padding`: chuỗi Keras, pads ONNX, số / cặp PyTorch) và từ chối khi khác `kernel // 2`. |
| 43 | `onnx2model` chỉ nhận đúng model kiểu MNIST: (a) `export_to_onnx` cố định input giả `1 × 1 × 28 × 28` (`onnx2model.py:93`); (b) chỉ lấy `COMPUTE_OPS` (Conv, Gemm/MatMul, MaxPool), **lặng lẽ bỏ** mọi op khác (`Add` của residual, `AveragePool`, `GlobalAveragePool`, `Concat`...; dòng 453); (c) không đọc thuộc tính `group`: Conv depthwise thành Conv thường 1 channel. Testbench nạp model thật cố định `SimpleMNISTConvNet` và ảnh MNIST | Python | **Phát hiện 2026-11-07** bằng đọc code (mục 8e), chưa chạy. Đã có phép kiểm tra cho zero point ≠ 0 và scale weight theo channel (báo lỗi rõ) **2026-11-07:** tài liệu `tutorial/model_formats.rst` liệt kê phần không hỗ trợ (concatenation, skip connection, BatchNorm chưa fuse, dilated conv) và hứa báo lỗi "Unsupported layer type": giới hạn là thiết kế, việc bỏ lặng lẽ là lỗi. **`onnx2model.check_supported_graph`** từ chối op lạ, Add residual, `group` / `dilations` / `auto_pad`, layer không nối thành chuỗi, hàm kích hoạt không gộp được vào Conv/Dense; input giả khi export lấy theo dữ liệu hiệu chỉnh. `pytorch2model` (đường `model_loader`) cũng bỏ qua stride / padding / groups / dilation và chỉ cảnh báo module lạ: nay từ chối. Depthwise (`DWMapper`): fork không có đường dữ liệu depthwise, nay báo lỗi rõ thay cho `IndexError` / `ValueError`. |
| 44 | `pytorch2model.extract_quantization_params` gọi `layer.weight()` với cả layer float (với bản torch hiện tại `Parameter` có thuộc tính `q_scale`): `TypeError: 'Parameter' object is not callable`, nên `create_model_from_pytorch` không chuyển được Conv2d / Linear float nào | `src/open_eye/pytorch2model.py:308` | **Phát hiện 2026-11-07** khi viết test cho #43; không liên quan đến đường model thật của fork (`onnx2model`), chưa sửa (`test_model_guards.py::test_pytorch2model_accepts_supported_modules` ghi lại) |

### 8c. Kế hoạch gần (theo thứ tự ưu tiên, cập nhật 2026-11-02)

**Định hướng (mốc phần cứng 2026-11-04 sau bản sửa #31, `e78e5b7`, `wghts_per_pe + 1`, phần cứng hàm kích hoạt, #28/#29/#36, #38 và hàng O: 59,4k LUT, 39,4k FF, 188 BRAM tile,
12 URAM, 4 DSP, đạt 250 MHz sau route (WNS +0,077 ns); mốc chu kỳ `baseline_2026-11-04` (= `baseline_2026-11-02` trừ `model_mnist_real_c1` −360), `baseline_2026-11-02`:
`baseline_2026-10-24` trừ 0–673 chu kỳ của dòng `wghts_per_pe + 1`):**

| # | Việc | Loại | Vì sao | Trạng thái |
|---|---|---|---|---|
| A | Place & route (clock 4 ns) để có fmax chính thức | Vivado, không sửa RTL | Fmax sau tổng hợp là ước lượng lạc quan; mọi tối ưu cần cả chu kỳ lẫn fmax | **Xong 2026-10-13: đạt 250 MHz sau route** (WNS +0,025 ns); đường găng là dây tới 144 BRAM của bộ đệm psum (mục 6d) |
| B | **Lỗi #13: phần cứng khác mô phỏng** ở `iact_stream_constructor` | Thí nghiệm, rồi sửa RTL | Nếu đúng như Vivado báo, bitstream hiện tại tính sai iact, nên mọi số đo trên board sẽ vô nghĩa | (1) Thí nghiệm **xong 2026-10-13: lỗi có thật**, 6/9 case sai trên phần cứng giả lập. (2) **Đã sửa 2026-10-13** (mục 9). (3) **Vivado xác nhận 2026-10-14**: CRITICAL WARNING biến mất, vẫn đạt 250 MHz. **Xong** |
| B2 | Lỗi #6/#7 (1 channel, `NUM_GLB_IACT=3`) và #18 (weight đọc gấp đôi) | Sửa RTL (#6/#7), Python (#18) | Kết quả sai | **Xong 2026-10-14/15** (mục 9), Vivado xác nhận |
| C | Gửi bias theo filter (1.1 bên dưới) | Sửa RTL | Bias chiếm **26 %** chu kỳ `mnist1` sau bản sửa #18; ước tính −23 % chu kỳ, DMA pha bias giảm khoảng 900 lần, chi phí khoảng +2 % FF và 0 BRAM | Chờ đồng ý |
| C2 | MNIST đầy đủ: lỗi #17 (Conv1), #9 (Conv3), #5 (FC) | Python (đệm channel) hoặc RTL | Chạy cả mạng thật, đo độ trễ end-to-end | **Kiến trúc MNIST chạy đủ 6 layer** (2026-10-22): #17 có workaround Python, #5 là lỗi testbench, #9 không chặn khi nối layer; `model_mnist_real_c1` = 963 µs (dữ liệu ngẫu nhiên). #22 đã sửa (2026-10-24): Conv1/2/3 với weight đã huấn luyện tính đúng. **Xong 2026-10-30**: sau #30 (kẹp int8, ReLU), #34, #32, #31, model int8 đã huấn luyện chạy trọn mạng trên RTL, khớp từng bit ở ảnh test 0–7, đoán đúng cả 8; đo được 852–884 µs (mục 6.13, 8d) |
| D | Thu nhỏ bộ đệm psum (`BUFFER_WIDTH_PSUM` 14 → 11/12) | Đổi tham số, không sửa RTL | 144/168 RAMB36 là bộ đệm psum, layer lớn nhất chỉ dùng khoảng 1.792/16.384 địa chỉ (ước tính); tiết kiệm khoảng 100–124 BRAM36 để thêm cluster hoặc bộ đệm | Cần kiểm chứng bằng 9 case. Sau route còn thấy lợi thêm: đường găng là dây tới các BRAM này, nên bộ đệm nhỏ hơn có thể tăng fmax |
| E | DMA 128 bit | Băng thông | Cổng HP của ZU+ rộng 128 bit; 64 bit ở 250 MHz chỉ đạt khoảng 2 GB/s; giảm một nửa số chu kỳ nạp và đọc kết quả | 128 bit chưa từng được kiểm chứng |
| F | Pipeline đường găng iact converter (`OpenEye_FPGA.v` 943–950) | Sửa RTL (fmax) | Tính trước các tích tham số một lần mỗi layer | Chỉ làm nếu fmax sau route chưa đủ |
| G | `USE_DSP=1` cho PE | Sửa RTL (tài nguyên) | Bộ nhân 48 PE đang dùng LUT, còn 1.724 DSP trống | Khi cần thêm cluster |
| H | Lỗi #14, #15 (cảnh báo "simulation mismatch") | Phân tích, có thể sửa RTL | Cùng loại rủi ro với #13 | #14 **xong** (2026-10-19); #15 chưa |
| I | Lỗi #26 (Dense nối tiếp Dense) và #25 (`NUM_GLB_PSUM=2`) | Điều tra (Python trước) | Chặn mạng của paper và mọi model có 2 Dense; Bảng 3 chưa có cấu hình nào tính đúng hết | #26 **đã sửa** (2026-10-24, 1 dòng RTL + Python, mục 9); #25 **đã sửa** (2026-10-26, mục 9) |
| J | Bảng 3 với activation thưa (giả lập ReLU) | Chỉ Python | Phần xử lý của fork chậm hơn paper 4–5,6 lần; xem bao nhiêu là do activation không thưa | Đề xuất |
| K | Hàm kích hoạt (#24) + kẹp int8 trong `quantization_unit` | Sửa RTL | Cần cho model thật (mục 8d) | **Xong** (2026-10-28, #30): kẹp với cận dưới theo layer, ReLU gộp vào kẹp (mục 9) |
| L | Kết thúc gửi weight sớm 1 chu kỳ (`wghts_per_pe + 1`, từ upstream `3258813`) | Sửa RTL 1 dòng | Mỗi lượt có việc gửi weight trên đường găng bớt 1 chu kỳ | **Đã thử 2026-10-31**: đúng ở mọi kiểm tra, −0,1 đến −0,3 % chu kỳ (−673 trên model MNIST), 0 tài nguyên; **đã đưa vào `dev` 2026-11-01** (`doc/experiments/2026-10-31_wght_send_end.md`); mốc chu kỳ `baseline_2026-11-02`, Vivado 2026-11-02 đạt 250 MHz (WNS +0,020 ns) |
| M | Hàm kích hoạt: Leaky ReLU, SiLU, hard-swish (ReLU đã có) + đo bằng profiler | Python (toolchain, tham chiếu) rồi RTL | Model thật dùng các hàm này; trước 2026-11-02 chỉ có ReLU (#24) | **Kế hoạch 2026-11-02** (`doc/experiments/2026-11-02_activation_plan.md`): gộp vào bộ lượng tử của pha ghi ngược (0 chu kỳ mỗi giá trị); Leaky = hai độ dốc trong bộ lượng tử (0 word DMA), SiLU/hard-swish = bảng 256 entry trong LUTRAM (32 word DMA mỗi layer dùng bảng, khoảng +400 LUT); profiler thêm pha `load_act` và bộ đếm của khối kích hoạt. **Bước A (Python) xong 2026-11-02** (`doc/experiments/2026-11-02_activation.md`): toolchain + tham chiếu tính đủ 4 hàm, 3 model đã huấn luyện, int8 giữ độ chính xác (≤ 0,04 điểm so với float), nhưng mất số 0 nên ước tính compute +7 đến +10,5 %; bit làm tròn cần thiết. **Bước B (RTL) xong 2026-11-02** (được bạn đồng ý; thiết kế `doc/experiments/2026-11-02_activation_rtl_design.md`, kết quả `doc/experiments/2026-11-02_activation_rtl.md`): 180 test 175 PASS + 5 xfail đã biết, 3 model đã huấn luyện khớp từng bit trên RTL, 0 chu kỳ lệch ở chế độ 0 (12 ca mốc, Bảng 3), Vivado đạt 250 MHz, khoảng +550 LUT. **Bước C (profiler) xong 2026-11-02** (chỉ Python, mục 6.15, `doc/experiments/2026-11-02_activation_profiler.md`): pha `load_act`, chu kỳ khối kích hoạt, số 0 ở input từng layer; model đã huấn luyện ảnh 0: khối kích hoạt 0 chu kỳ mỗi giá trị, bảng 32 chu kỳ mỗi layer, nhưng cả model +8,7 % (Leaky), +9,7 % (SiLU), +9,8 % (hard-swish) vì mất số 0 (gần như toàn bộ ở `compute`). Hướng giảm tiếp: bảng `band1` (đặt ô ±1 về 0) |

| N | Sửa 3 lỗi của các cấu hình CR 1 trong Bảng 3: #29 (kiểm tra số hàng bộ đệm weight trong Python + `BUFFER_WIDTH_WGHT = 13`), #28 (điều kiện ready xét cả GLB lẻ ở CR 1), #36 (nới thanh ghi đọc ra) | Python + tham số (#29), sửa RTL (#28, #36) | Bảng 3 lên 16/16; #29 còn chặn mọi Dense lớn (3136 → 32 ở cấu hình MNIST) | **Xong 2026-11-03** (được bạn đồng ý, mục 9): Bảng 3 16/16, hồi quy 184 test 179 PASS + 5 xfail, 12 ca mốc 0 lệch |
| O | Chép từ upstream `36395dd` / `9498271`: #17 (1 channel trong RTL, bỏ `channel_pad`) và #37 (nới trường iact) | Sửa RTL + regmap | #17: Conv1 MNIST bớt 1,1 % chu kỳ (đo: −360, −336 word DMA; ước tính ban đầu khoảng 5 % theo thời gian mô phỏng), bỏ được workaround Python; #37: Conv lớn ở CR 1 X 2 | **Xong 2026-11-04** (được bạn đồng ý; `doc/experiments/2026-11-04_rowO_bug17_bug37.md`, mục 9 "Sửa #37, #17"): chép từng phần lên code của `dev`, không gộp commit |

Thứ tự đề xuất: A, B, B2, C2 (kiến trúc MNIST chạy đủ), I, K, L, M (hàm kích hoạt A/B/C) **đã xong**; tiếp theo là C (bias theo filter: Bảng 3 cho thấy bias chiếm khoảng 54.000–58.000 ns ở mọi
cấu hình), rồi D (I: #25, #26 đã sửa).
Mỗi thay đổi RTL: test, `run_profile --compare`, Yosys (so sánh nhanh LUT), Vivado ở các mốc quan trọng.

**Kế hoạch theo giai đoạn (số liệu theo `baseline_2026-10-15`; 9 case này không đổi trong `baseline_2026-10-24`, `baseline_2026-11-02` chỉ ít hơn 0–224 chu kỳ):**

1. **Giai đoạn 1.1: gửi bias theo filter** (= hướng C; thiết kế ở dưới). **Cần bạn đồng ý** vì sửa RTL.
2. **Giai đoạn 1.2: readout INT8.** Lượng tử kết quả trên chip trước khi gửi ra (đường này đã có cho write-back giữa các layer).
   Readout của `mnist1` chiếm 26 %; có thể giảm khoảng 4 lần số word.
3. **Giai đoạn 1.3: tìm hiểu định dạng weight** (hiệu suất 15–30 %). Bước đầu chỉ phân tích, không sửa RTL; sau đó mới đề xuất cách đóng gói.
4. **Việc 0.2:** đo layer Dense và lượt nhiều layer: **xong** (2026-10-22, mục 6.13); lỗi #5 hoá ra là báo động giả của testbench.
5. **Giai đoạn 2:** chạy chồng pha nạp và pha tính toán (double-buffering), sau khi Giai đoạn 1 xong.

**Thiết kế đề xuất cho 1.1 (gửi bias theo filter), chưa thực hiện, chờ đồng ý:**
- Hiện tại: Python (`psum_stream_mapper.get_psum_stream`) gửi giá trị bias cho từng (lượt x, hàng output, filter), mỗi giá trị lặp
  `block_length` lần. `psum_pipeline.v` ghép `CONV_BIAS_CYCLES` word (= 8 với 2×2 cluster, 4 GLB psum) thành 1 địa chỉ của bộ đệm psum.
  Bộ đệm này là **giá trị khởi tạo của bộ cộng dồn**: `CALCULATE_PSUM` đưa nội dung bộ đệm vào mảng PE, lượt đầu là bias, các lượt sau là
  kết quả cộng dồn.
- **Phương án A (đề xuất): bảng bias trên chip + tự sinh lại đúng chuỗi ghi cũ.** DMA chỉ gửi F giá trị bias (2 giá trị mỗi word 64 bit).
  RTL lưu chúng vào một bảng nhỏ, rồi một bộ đếm (lượt x → hàng → filter → lặp `block_length`) **ghi lại đúng các địa chỉ và nội dung như
  trước**, mỗi chu kỳ 1 địa chỉ (đủ mọi cluster). Phần tính toán, cộng dồn và đọc ra giữ nguyên, nên rủi ro thấp và kiểm chứng được bit-exact
  (so sánh nội dung bộ đệm psum giữa cách cũ và cách mới).
- Phương án B (sau này): không ghi bias vào bộ đệm; ở lượt đầu của `CALCULATE_PSUM` thay `psum_buffer_data_r` bằng giá trị lấy từ bảng
  bias. Loại bỏ cả thời gian ghi, nhưng cần ánh xạ địa chỉ/lane → filter, phức tạp hơn.
- Phương án C (loại): cộng bias ở bước lượng tử/đọc ra. Không làm được trực tiếp vì `current_filter` không được cập nhật (lỗi #12).
- File cần sửa (phương án A): `hdl/psum_pipeline.v` (bảng bias, bộ đếm sinh lại, `GET_BIAS`), `hdl/OpenEye_FPGA.v` (tham số bật/tắt,
  điều kiện rời `GET_BIAS` chờ sinh lại xong), `src/open_eye/psum_stream_mapper.py` (stream F giá trị), `src/open_eye/layer_parameters.py`
  (`trans_cycles_psum`), `src/open_eye/vh_file_creator.py`/`open_eye_parameters.py` (tham số). Có thể cần thêm thanh ghi cấu hình
  (`test/cocotb_fpga/regmap.yaml`) cho số hàng, số lượt x, `block_length`. Giữ cách cũ khi tham số tắt, áp dụng trước cho Conv (Dense và
  Depthwise giữ nguyên).
- Ước tính (bộ nhớ lý tưởng, theo `baseline_2026-10-15`): `mnist1` pha bias 14.336 → khoảng 16 word DMA + 1.792 chu kỳ sinh lại, tức khoảng −12.500 chu kỳ
  (khoảng −23 % trên 55.048; trước bản sửa #18 là −19 % trên 65.800);
  `32x3_f16`: 768 → khoảng 8 + 96, khoảng −18 %. Với bộ nhớ `typical` lợi hơn (mỗi word DMA tốn khoảng 1,44 chu kỳ). Lưu lượng DMA của pha bias
  giảm khoảng 900 lần.
- Chi phí ước tính: bảng bias tối đa 32 × 20–32 bit (khoảng 640–1.024 flip-flop, hoặc vài chục LUT nếu dùng LUTRAM), khoảng 4 bộ đếm (khoảng 40 flip-flop),
  logic chọn và ghép word. Đo lại bằng Yosys sau khi làm.

Mỗi bước đều đánh giá bằng `tools/run_profile.py --compare doc/perf/baseline_2026-11-04`, kèm thêm `--mem typical` để thấy lợi ích khi có bộ nhớ thực tế hơn,
và Bảng 3 (`tools/paper_table3.py`) để thấy tác dụng trên nhiều cấu hình cluster.

### 8d. Chạy cả một model nhiều layer (phân tích 2026-10-22)

Chi tiết: `doc/experiments/2026-10-22_multilayer_model.md`, script `doc/experiments/2026-10-22_multilayer/`. Testbench chạy model **nối tiếp trên chip**:
layer trung gian ghi kết quả đã lượng tử ngược vào bộ đệm iact (trạng thái 11), testbench so bộ đệm đó với tham chiếu của layer sau; chỉ layer cuối gửi
kết quả ra.

**Hiện trạng (cập nhật 2026-10-31):**

| Model | Kết quả |
|---|---|
| `LAYER=MNIST` của `data_create.py` (Conv 2→16, Pool, Conv 16→16, Pool, Conv 7×7 16→16, Dense 784→10), `NUM_GLB_IACT` 1 và 3 | **PASS** cả 6 layer |
| Kiến trúc MNIST thật (`models/mnist_conv_net.py`: Conv 32, Pool, Conv 64, Pool, Conv 7×7 64, FC 3136→10), đầu vào **đệm thành 2 channel**, `QUANT_AMOUNT=64` | **PASS** cả 6 layer |
| Như trên với **1 channel** (đúng model gốc) | FAIL ở bộ đệm iact sau Conv1 (lỗi #17); **PASS từ 2026-10-22** nhờ đệm 2 channel bằng Python (`model_mnist_real_c1`, 241.250 chu kỳ = 965 µs; 240.671 sau #22) |
| **Model MNIST đã huấn luyện** (`SimpleMNISTConvNet` + `mnist_unquantized_model.pth`, lượng tử tĩnh qua `onnx2model`, ảnh test thật, 1 channel đệm thành 2) | **PASS** cả 6 layer, khớp từng bit, ảnh 0–7 đoán đúng cả 8 (2026-10-30, sau #30, #34, #32, #31; `test_real_model.py`) |
| `LAYER=PAPER_MNIST` (mạng Bảng 2 của paper: Conv 16, Pool, Conv 32, Pool, Conv 32, Dense 1568→32, Dense 32→10), 16 cấu hình | Trước bản sửa #26 FAIL ở mọi cấu hình. Sau bản sửa #26 (2026-10-24): 7/8 cấu hình X = 4 PASS. **Sau bản sửa #25 (2026-10-26): 13/16 cấu hình PASS cả 7 layer**; còn CR 1 X 4 Y 3 (lỗi tính #19b ở Dense 1568→32) và CR 1 X 2 (lỗi tính #28 ở Conv) (mục 6.14, 9) |

**Còn thiếu để mô phỏng đúng model MNIST thật (ngữ nghĩa của testbench):** (1) lỗi #17: **đã làm** đệm 1 → 2 channel bằng Python (2026-10-22, channel thêm
toàn 0, +472 chu kỳ = +1,5 % Conv1, mục 9; sửa RTL vẫn là lựa chọn sau này); (2) dựng phần cứng với `QUANT_AMOUNT=64`; (3) nới ngưỡng phát hiện treo (layer 64 filter tính 90.000 chu kỳ trong trạng thái 11);
(4) model khác: #19b, #21 (Dense N > 32 làm layer cuối), #28 (`CLUSTER_ROWS=1` với `NUM_GLB_PSUM=2`), #27 (pooling 4×4 → 2×2), layer nhiều lượt truyền (#26 và #25 đã sửa 2026-10-24/26).

**Còn thiếu để chạy model int8 đã huấn luyện với kết quả đúng** (điều tra bằng bộ giả lập 2026-10-28, `doc/experiments/2026-10-28_int8_clamp.md`;
TFLite int8 đạt 99,23 % trên 10.000 ảnh): (A) ~~kẹp int8~~ và (B) ~~ReLU~~ **đã làm 2026-10-28** (#30: kẹp với cận dưới theo layer, ReLU = cận dưới 0; giả lập: từ 9,3 %
lên 99,21–99,25 % với activation lượng tử đối xứng, zero point 0). Còn lại lúc đó (trạng thái 2026-10-31 ghi trong ngoặc vuông): (C) **luồng Python lượng tử int8 (PTQ)** cho model thật
[**đã làm 2026-10-30** bằng lượng tử tĩnh trong `onnx2model`, một scale weight mỗi layer, `mant`/`shift` mỗi layer, xem bảng bên dưới]: hiệu chỉnh, weight theo channel,
bias int32, `mant`/`shift` theo filter, `act_min`, lượng tử ảnh input, hoán vị weight Dense đầu tiên theo thứ tự làm phẳng khối 4 channel của phần cứng; (D) tham chiếu
int8 thật (bộ giả lập bit-exact, đã khớp TFLite) thay cho `floor(mant·x/2^shift)` [không cần nữa: tham chiếu của toolchain dùng đúng phép tính của phần cứng và khớp
RTL từng bit; so với ONNX Runtime chỉ khác do làm tròn]; (E) lỗi #12 `current_filter` [**còn mở**; không chặn vì đang dùng một hệ số mỗi layer] và (F) mantissa bị cắt
8 bit (`OpenEye_FPGA.v:1350`) [**đã sửa 2026-11-04**, lỗi #38; `onnx2model` nay dùng mantissa 24 bit]: không ảnh hưởng độ chính xác model MNIST (−0,04 điểm) nhưng cần để khớp từng bit;
(G) lỗi #29 (Dense 3136 → 64) [**còn mở**; không chặn model trong repo vì Dense của nó là 3136 → 10]. Với lượng tử đối xứng: psum 20 bit đủ (lớn nhất
365.571), đệm 0 đúng, không cần cộng zero point, giữ được bỏ-qua-số-0 (63–83 % activation là 0 sau ReLU). Lượng tử bất đối xứng kiểu TFLite (zp −128) thì cần thêm
psum 32 bit, đệm viền bằng zero point (RTL) và mất bỏ-qua-số-0.

**Đường model thật của toolchain (kiểm tra 2026-10-30, không sửa gì; đây là trạng thái trước bản sửa ở bảng dưới):** testbench có sẵn đường này khi `USE_RANDOM_VALUES=0`: `models/mnist_conv_net.py`
(`SimpleMNISTConvNet`, PyTorch) → `onnx2model.get_model` (xuất ONNX, `quantize_dynamic` weight int8, tách thành `HardwareLayer`) → `LayerParameters` → `DRAMContents`
→ mapper → RTL. Makefile chỉ chọn `LAYER`, kích thước, tham số phần cứng và cờ này; nó không ghi đè bias/weight. Kết quả: `onnx2model` cho đủ 6 layer (gồm 2 layer
pooling để cấu hình pooling trên RTL, cờ ReLU, weight int8, bias int32), `LayerParameters` nhận được (khác `tflite2model`: `TFLite_dense` không có `.kernel` mà
`LayerParameters` đọc ở `layer_parameters.py:643/1360/1557`). Nhưng dữ liệu thật không tới RTL: testbench tạo `SimpleMNISTConvNet()` chưa huấn luyện (file đã huấn luyện
`doc/demo_notebooks/mnist_unquantized_model.pth` khớp kiến trúc nhưng không được nạp); `DRAM.py` nhân weight int8 với 127 (tràn int8, dòng 215), ghi đè bias Conv = 1
(253), bias Dense = c+1 (260), weight Dense ngẫu nhiên (228), input ngẫu nhiên (273); `quantize` lấy mặc định [1, 7]/[1, 9]; `act_min` bỏ qua `has_relu`
(`activation_min` chỉ đọc `relu`/`activation`); `quantize_dynamic` không cho scale activation nên không suy ra được `mant`/`shift`. Chạy RTL theo đường này (MNIST_REAL,
QUANT_AMOUNT 64): FAIL ở bộ đệm sau pooling đầu, 784/784 word sai (DUT 0/−128, tham chiếu giá trị nhỏ); chưa điều tra (đường này không có test nào).

**Đường model thật chở được model đã huấn luyện (2026-10-30, được bạn đồng ý, chỉ Python; `doc/experiments/2026-10-30_onnx_model_flow.md`):**

| File | Sửa |
|---|---|
| `onnx2model.py` | `get_model(model, calibration_data)`: có dữ liệu hiệu chỉnh thì **lượng tử tĩnh** (ONNX Runtime `quantize_static`, int8 zero point 0 cho cả activation lẫn weight, một scale weight mỗi layer); không có thì vẫn lượng tử động như cũ. Đọc `QLinearConv`/`QGemm` (Linear thành `QGemm`): weight int8, bias int32, scale input/weight/output, `quantization_factor` = `[mant, shift]` từ `M = s_in·s_w/s_out` (mantissa 24 bit từ bản sửa #38, trước đó 8 bit), cờ `quantized`. Layer MaxPool tên `max_pooling2d` (sửa #34). Dò ReLU dừng ở node tính kế tiếp. Kích thước output của `QGemm` lấy từ weight |
| `layer_parameters.py` | `activation_min` đọc thêm `has_relu` (tên cờ ReLU của `onnx2model`; upstream không đọc cờ này ở đâu, và upstream không có kẹp ReLU) |
| `DRAM.py` | Layer `quantized`: weight và bias của model giữ nguyên (không ×127, không bias 1); weight Dense hoán vị theo thứ tự input Dense của phần cứng (`dense_input_order`, lấy từ `fill_dram_with_ref`) so với thứ tự làm phẳng NCHW của model. Đường ngẫu nhiên giữ nguyên |
| `data_create.py` | `mnist_images`: ảnh MNIST chuẩn hoá như lúc huấn luyện (`(pixel/255 − 0,1307)/0,3081`) |
| Testbench | `OPENEYE_MODEL_WEIGHTS` (nạp `.pth`, lượng tử tĩnh), `OPENEYE_INPUT_IMAGE` (ảnh test thật), log lớp DUT dự đoán |

Kiểm chứng toolchain không cần RTL (`test/test_onnx_model_flow.py`, 6/6): tham chiếu của testbench so với ONNX Runtime chạy cùng model int8, từng layer: chỉ khác
do làm tròn (Conv1/Pool1 lệch ≤ 1; Conv2…Conv3 lệch ≤ 3, ≥ 98 % lệch ≤ 1), lớp dự đoán trùng ORT và nhãn; trên 100 ảnh test đầu, tham chiếu đúng 100 % và trùng lớp với ORT int8 100 %. Trên RTL (`test_real_model.py`, ảnh 0 và 1), **lúc đó, trước các bản sửa #32 và #31**:
Conv1 + ReLU + Pool1 và Conv2 + ReLU + Pool2 **khớp từng bit**; Conv3 sai (112/392 và 138/392 word đúng); test đánh `xfail(strict)`. Dense của model này là
3136 → 10 nên không vướng #29. Điều tra cùng ngày (`doc/experiments/2026-10-30_bug32_bias_order.md`): ảnh 0 = #32 ở mọi vị trí + #31 ở hàng output cuối
của Conv3, ảnh 1 = chỉ #32 (mô hình khớp DUT 3136/3136 giá trị ở cả hai); "#35, cột cuối" là đọc nhầm layout, thực ra là #31. **Giả lập bản sửa Python của #32
trong mô phỏng: ảnh 1 chạy trọn model trên RTL, PASS, khớp từng bit ở mọi layer, DUT ra lớp 2 = nhãn** (ảnh MNIST thật đầu tiên qua cả mạng đã huấn luyện trên
phần cứng). Quét 1000 ảnh test (chỉ Python, mô hình lỗi đã kiểm chứng trên RTL với ảnh 0, 1, 7): Conv3 có lượt rỗng (#31) ở **861/1000 ảnh** (Conv2: 0);
độ chính xác 99,5 % nếu không lỗi, 99,5 % chỉ với #32, 72,9 % chỉ với #31, **61,9 % với cả hai** (Dense tính đúng; phía Dense của #31 chưa mô hình hoá).
**#32 đã sửa bằng Python** (cùng ngày, được bạn đồng ý, mục 9): `test_real_model[1]` PASS với code thật (không còn giả lập); ảnh 0 còn xfail do #31; độ chính xác
ước tính của phần cứng hiện nay 72,9 % (chỉ còn #31).
**#31 đã sửa trong `PE.v`** (cùng ngày, được bạn đồng ý, hướng A, mục 9): **model MNIST đã huấn luyện chạy trọn mạng trên RTL, khớp từng bit với tham chiếu, ở cả 8
ảnh test 0–7, DUT đoán đúng nhãn cả 8** (7, 2, 1, 0, 4, 1, 4, 9); `test_real_model.py` 2 PASS. Tham chiếu của toolchain (= phần cứng) đúng 99,5 % trên 1000 ảnh
test đầu (mô hình Python `scan31.py`).

**Vì sao lượng tử tĩnh, không phải động như upstream (phân tích 2026-10-31, không sửa gì; `doc/experiments/2026-10-30_onnx_model_flow.md` mục 7):**
`onnx2model` cũ giống hệt upstream: `quantize_dynamic(weight_type=QInt8)`. Đồ thị động mỗi layer: `DynamicQuantizeLinear` (activation **uint8**, scale và zero
point tính **lúc chạy** từ min/max của chính tensor đó) → `ConvInteger` (int32) → `Cast` → `Mul` (scale) → `Add` (bias float) → `Relu` (float) → `MaxPool` (float).
Scale activation không có trong file và đổi theo từng ảnh (layer 2: 0,01055 / 0,01125 / 0,0087 với ảnh 0, 1, 2), layer đầu có zero point 33. Phần cứng chỉ có **một
hệ số cố định** (`mant`, `shift`) mỗi layer, nạp trước khi chạy, activation int8 có dấu zero point 0 (bỏ qua số 0 và đệm 0 dựa vào đó), và lượng tử từng output ngay
khi ghi ngược, không duyệt cả tensor để tìm min/max: scale lúc chạy không đưa xuống được, scale đã hiệu chỉnh (tĩnh) thì được. Bản thân ONNX Runtime đúng: động với
weight uint8 99,5 %, float 99,5 %, tĩnh int8 99,4 %, tham chiếu phần cứng 99,5 % (1000 ảnh test đầu); nhưng **model int8 mà đường cũ ghi ra ONNX Runtime không chạy
được** (`ConvInteger` trên CPU chỉ nhận weight uint8), nên chưa bao giờ được kiểm. **ReLU:** `check_fused_relu` cũ tìm thấy (`has_relu` True ở 3 Conv) nhưng không ai
đọc cờ (upstream cũng vậy), tham chiếu không có ReLU, bộ lượng tử RTL quấn vòng tới #30; trong đồ thị động ReLU là phép float của ONNX Runtime. **Lỗi khác của phần
trích xuất cũ:** `input_scale` tìm trong initializer nên luôn 1,0 (bias int32 sai đơn vị, không có hệ số lượng tử); kernel chuyển vị `(3,2,1,0)` = [cột][hàng] trong
khi `DRAMContents` đọc [hàng][cột] (Conv1 so với ONNX Runtime chỉ 65,8 % lệch ≤ 1, lệch tới 199; cách mới `(2,3,1,0)` khớp 100 %); weight Dense `[in][out]` đọc như
`[out][in]` nên `filters` = 3136 thay vì 10; MaxPool thành average (#34); khối "stable hardware reference generator" là code chết.

**Đo pha khi chạy nhiều layer (phân tích ngày 2026-10-22, đã làm xong cùng ngày):** khi đó profiler cộng dồn mọi layer, và với layer trung gian thì tính toán diễn ra trong trạng thái 11 nên bị ghi là `writeback`
(`compute = 0`). Bản thử `probe_model.py` tách theo từng lần vào `GET_PARAMETERS` và tách trạng thái 10/11 theo FSM psum (1–3 = tính toán, 4/6 = ghi ngược).
Model MNIST thật (2 channel, bộ nhớ lý tưởng): **244.052 chu kỳ = 976 µs ở 250 MHz**; tính toán 62 %, nạp weight 16 %, nạp bias 10 % (40 % của Conv1), ghi ngược
5 %, chuyển đổi 4 %, pooling 3 %; Conv2 là layer nặng nhất (121.162 chu kỳ). **Đã đưa vào profiler của repo** (2026-10-22, chỉ Python): mỗi layer có bảng
pha riêng, case `model_*` trong `run_profile.py`, bảng theo layer trong `profile_report`. Cách dùng và số liệu: mục 6.13.

### 8e. Lỗi còn mở khi chạy một model thật (tổng hợp 2026-11-07)

**Model đang chạy đúng:** model MNIST đã huấn luyện của repo (`SimpleMNISTConvNet`: Conv 3×3 1 → 32, MaxPool, Conv 32 → 64, MaxPool,
Conv 7×7 64 → 64, Dense 3136 → 10; lượng tử tĩnh đối xứng, một scale mỗi layer) chạy trọn mạng trên RTL, **khớp từng bit** với tham chiếu
ở 8/8 ảnh test, đoán đúng cả 8; tham chiếu của toolchain (= phép tính của phần cứng) đúng 99,5 % trên 1.000 ảnh test đầu (mục 8d). Các bản
Leaky ReLU / SiLU / hard-swish của model này cũng chạy (mục 6.15). Model khác hình dạng này thì vướng các lỗi dưới đây.

**Kiểm tra thêm ngày 2026-11-07** (fork, `doc/experiments/2026-11-04_bug39/run39.py`, CR 2 × CC 2, dữ liệu ngẫu nhiên, seed 1):

| Ca | Kết quả |
|---|---|
| Conv 8×8×4 → 16, stride 1 (đối chứng) | PASS |
| Conv 8×8×4 → 16, **stride 2** | **FAIL**, 16/16 feature map, 207/256 giá trị (lỗi mới **#41**) |
| Như trên, phần cứng dựng với `STRIDE_ENABLED=1`: stride 2 với input rộng 8, 16, 24, 28, 32; stride 1 8×8 | **PASS** (stride 1 cùng 33.150 ns như khi tắt) |
| `STRIDE_ENABLED=1`, stride 2 với input rộng 4, 6, 7, 9, 12 (mọi chiều cao) | **FAIL** (#41b) |
| Conv **1×1** 8×4×4 → 16 và 8×4×2 → 8 | PASS (ca treo ghi ngày 2026-11-05, 8×4×4 → 96 ở CR 1 X 2 Y 3, vẫn chưa điều tra) |

**A. Từng sai mà không báo lỗi** (toolchain vẫn tạo stream, RTL chạy hết, kết quả sai). **Từ 2026-11-07 toolchain báo lỗi
`NotImplementedError` cho cả nhóm** (chỉ Python, không sửa RTL; `doc/experiments/2026-11-07_bug41_stride.md`, test `test/test_model_guards.py`).
Cột "Tài liệu" là kết quả đọc lại các file trong `doc/` để xem đó là lỗi hay là giới hạn có chủ đích của project:

| # | Khi nào gặp trong model thật | Ví dụ | Tài liệu nói gì → kết luận | Phép kiểm tra |
|---|---|---|---|---|
| 41, 41b–d | Conv stride 2 | ResNet, MobileNet | Stride là tính năng (thanh ghi 1–8, PE trượt C0 × U) nhưng chưa test; phần cứng mặc định dựng với `STRIDE_ENABLED=0` (không có stride), không tài liệu nào ghi → **lỗi cấu hình / toolchain** (#41); với `STRIDE_ENABLED=1`: 2 lỗi Python (#41b), ghi ngược dùng kích thước input (#41c, RTL), input trên chip cao lẻ mất hàng output cuối (#41d) → **lỗi thật**, **đã sửa 2026-11-08** | `check_conv_geometry`: từ chối stride > 1 khi `STRIDE_ENABLED=0` |
| 42 | Conv không phải "same" (padding 0, đệm lệch; TF "same" với stride 2 trên ảnh chẵn) | LeNet-5; Conv stride 2 xuất từ TF | RTL chỉ đệm `(kernel_size − 1) / 2` → **giới hạn thiết kế**, lỗi là toolchain không báo | `check_conv_geometry`: padding của model phải bằng `kernel // 2` |
| 43 | Op ngoài Conv / Gemm / MaxPool (`Add` residual, `AveragePool`, `GlobalAveragePool`, `Concat`, `Softmax`), conv nhóm / depthwise / dilated, input khác 1 × 1 × 28 × 28 | ResNet, MobileNet | `model_formats.rst` ghi các op này không hỗ trợ và hứa lỗi "Unsupported layer type" → **giới hạn thiết kế**, lỗi là bị bỏ lặng lẽ | `onnx2model.check_supported_graph`; `pytorch2model` từ chối Conv2d / MaxPool2d nó không chuyển được và module lạ; `DWMapper` báo không có depthwise |
| 7 | Ảnh **3 channel** (RGB) | CIFAR-10, mạng ảnh màu | Tài liệu có ví dụ đóng gói 3 channel và input RGB → **lỗi thật** | `check_conv_geometry`: số channel lẻ > 1 |
| 21 | Dense **làm layer cuối** có hơn 32 output | Bộ phân loại 100 / 1.000 lớp | Không có giới hạn trong tài liệu → **lỗi thật** | `check_dense_readout`: layer cuối cần > 1 lượt psum |
| 27 | Pooling có input rộng ≤ 4 (đo 2026-11-07: rộng 2, 4 sai; 6, 8 đúng) | Bản đồ đặc trưng nhỏ cuối mạng | "2×2 max-pooling on-chip", không giới hạn kích thước → **lỗi thật** | `check_pooling_geometry`: rộng ≤ 4, cửa sổ khác 2 × 2 / stride 2 |
| 23 | Activation thưa dạng bàn cờ với `NUM_GLB_IACT = 3` | Phụ thuộc cấu hình | Phụ thuộc dữ liệu, chưa rõ nguyên nhân | **Chưa chặn được** (không có điều kiện tĩnh) |
| 19b | Dense N = 32 từ 8 lượt K | Dense ẩn 512 → 32 | **Chưa tái hiện lại được** (PASS cả commit lúc phát hiện `10bcaf7` lẫn `dev`, seed 1–5) | Chưa có điều kiện để chặn |

`OPENEYE_ALLOW_UNSUPPORTED=1` biến các phép kiểm tra của `LayerParameters` (#41, #42, #7, #27, #21) thành cảnh báo để tái hiện lỗi trên RTL;
#21 tái hiện lại được (Dense 64 → 40: 30/40 output sai).
Quét tĩnh (`doc/experiments/2026-11-07_bug41_stride/scan_guards.py`) 78 Conv, 46 pooling, 39 Dense của Bảng 3, 12 ca mốc và 4 model hàm kích hoạt:
0 layer bị chặn.

**B. Bị toolchain từ chối, có thông báo** (không sai, nhưng không chạy được):

| Lỗi / giới hạn | Phép kiểm tra | Model bị chặn |
|---|---|---|
| #12: bộ lượng tử dùng hệ số của filter 0 cho mọi filter | `onnx2model.process_qlinear`: từ chối scale weight theo channel | Model lượng tử theo channel (mặc định của TFLite, PyTorch): phải lượng tử lại theo layer, mạng lớn mất độ chính xác |
| Zero point ≠ 0 (lượng tử bất đối xứng, activation zp −128 kiểu TFLite) | `onnx2model.process_qlinear` | Model int8 TFLite có sẵn; cần đệm viền bằng zp, psum 32 bit (mục 8d) |
| #29: bộ đệm weight 8.192 hàng | `check_wght_buffer` | Dense lớn, ví dụ 3136 → 64 (cần 14 bit hoặc tách layer) |
| Bộ đệm iact 8.191 word mỗi lượt (#37) | `check_iact_buffer` | Ảnh / bản đồ đặc trưng lớn nhiều channel |
| #39, #39b: số bộ weight ≠ số lượt × số lô channel | `check_wght_sets` | 3 channel × 64/96/128 filter, nhiều layer 1×1 / 7×7 có tile |
| #40 (và nhiều khả năng #18b): lượt weight cuối thiếu filter | `check_full_passes` | Số filter không lấp đầy lượt, ví dụ 24, 48 |

**C. Treo hoặc chưa kiểm chứng:** Conv 1×1 ở một số cấu hình (8×4×4 → 96, CR 1 X 2 Y 3); Conv 7×7 có tile (giới hạn bộ mã hoá weight của #22);
kernel 5×5 chưa có test nào trong fork; `CLUSTER_ROWS = 1` (#10) với các cấu hình khác Bảng 3.

**D. Chưa có trong fork:** conv depthwise (upstream đang làm, chưa đúng, mục 2), mạng có nhánh / residual (DAG của upstream `c342d04` chưa lấy).

**E. Khi đưa lên FPGA thật:** wrapper AXI không biên dịch (#16); 12 thanh ghi có set và reset cùng mức ưu tiên chưa phân tích (#15, cùng loại rủi ro
"mô phỏng khác phần cứng" với #13 đã sửa).

**Thứ tự đề xuất** (cập nhật 2026-11-09): (1) ~~phép kiểm tra Python cho nhóm A~~ **xong 2026-11-07**; (2) stride: ~~sửa #41b, #41c, #41d, nới phép kiểm tra~~ **xong 2026-11-08**; ~~dựng phần cứng với `STRIDE_ENABLED=1`~~ **xong 2026-11-09, mặc định** (+155 LUT, đạt 250 MHz, 0 chu kỳ thay đổi);
(3) #7 bằng Python (đệm 3 → 4 channel, đề xuất cũ); (4) #21, #27 (điều tra RTL); (5) #12 (lượng tử theo filter, RTL). Padding khác "same" (#42)
là giới hạn thiết kế: dùng model có padding `kernel // 2`; TF "same" stride 2 ở layer đầu có thể đổi bằng cách dịch input một pixel (`doc/experiments/2026-11-07_bug41_stride.md` mục 5).

## 9. Các lỗi đã biết và các bản sửa RTL

**Số channel vào và `NUM_GLB_IACT`** (đo ngày 2026-10-09: một layer Conv, input 8×1, 4 filter, ramp, 2×2 cluster, `QUANT_AMOUNT=32`):

| Channel vào | `NUM_GLB_IACT=1` | `NUM_GLB_IACT=3` |
|---|---|---|
| 1 | FAIL: ra toàn bias (giá trị 1) | FAIL: giá trị sai |
| 2 | **PASS** | FAIL: giá trị sai |
| 3 | FAIL: giá trị sai (dạng dốc lệch so với tham chiếu) | FAIL: giá trị sai |
| 4 | **PASS** | FAIL: giá trị sai |

- Chỉ có **2 hoặc 4 channel với `NUM_GLB_IACT=1`** là chạy đúng.
- **Đã điều tra (2026-10-14, `doc/experiments/2026-10-14_channel_bugs.md`):** 1 channel và `NUM_GLB_IACT=3` là hồi quy do commit upstream `23be043`
  (trước commit đó cả hai PASS); 3 channel là do Python xếp 3 byte mỗi pixel trong khi RTL truyền iact theo cặp (`PARALLEL_MACS=2`).
- `NUM_GLB_IACT=3` sai với mọi số channel đã thử.
- **Sau bản sửa ngày 2026-10-14:** 1/2/4/8 channel × `NUM_GLB_IACT` 1 và 3 đều đúng (`test_mnist_layers.py -k mapping`); chỉ 3 channel còn sai (Python).
  MNIST Conv1 (1 channel, rộng 28) có lỗi #17 (từ 2026-10-22 workaround Python; RTL sửa 2026-11-04, mục 9).

**Lỗi `GET_BIAS` khi dữ liệu DMA tới không liên tục** (tìm ra, kiểm chứng và **đã sửa** ngày 2026-10-10, với sự đồng ý của bạn):
- `hdl/OpenEye_FPGA.v:1978` (vị trí hiện tại): `GET_BIAS` chuyển sang `GET_QUANTIZE` khi `fsm_psum_cycle == trans_cycles_psum - 1`,
  **không kiểm tra `enable_dma_i_reg`**. Các trạng thái nạp khác thì có kiểm tra.
- Hậu quả: nếu đúng chu kỳ đó không có word hợp lệ, word bias cuối không được nhận, bị `GET_QUANTIZE` coi là word đầu của bảng
  lượng tử, toàn bộ dữ liệu sau lệch 1 word, FSM treo. `fsm_psum_cycle` còn kẹt ở N−1, ảnh hưởng tới layer sau.

**Kiểm chứng: lỗi do *thời điểm*, không do dữ liệu** (case `8x1_f4_q32`, stream 194 word: status 0–17, iact 18–21, weight 22–141,
bias 142–173, quant 174–193). Công cụ: `OPENEYE_TRACE_DMA=1` (ghi mọi word DUT nhận và mọi lần đổi trạng thái) và
`tools/check_dma_trace.py` (so với `dma_stream_input.txt` do testbench sinh ra).

| Kịch bản | Kết quả | Word DUT nhận | Lúc `GET_BIAS` → `GET_QUANTIZE` |
|---|---|---|---|
| Driver cũ (testbench gốc) | PASS | 194/194, đúng nội dung và thứ tự | `enable_reg=1` |
| Driver mới, bộ nhớ lý tưởng | PASS | 194/194, đúng | `enable_reg=1` |
| Chèn **1 chu kỳ trống trước word 173** (bias cuối) | **FAIL** | 193/194, **đúng nội dung và thứ tự**, chỉ thiếu word cuối | **`enable_reg=0`**, `fsm_psum_cycle=31` |
| 1 chu kỳ trống trước word 172 (bias áp chót) | PASS | 194/194 | `enable_reg=1` |
| 1 chu kỳ trống trước word 142 (bias đầu), 174 (quant đầu), 193 (quant cuối) | PASS | 194/194 | `enable_reg=1` |
| 1 chu kỳ trống trước word cuối của `GET_PARAMETERS` (14), `GET_ROUTER_CONFIG` (17), `GET_IACT` (21), `GET_WGHT` (141) | PASS | 194/194 | `enable_reg=1` |
| `typical` (khoảng trống giữa các burst) | PASS | 194/194 | `enable_reg=1` |
| `typical` + `bandwidth=0.5` (cứ 1 word nghỉ 1 chu kỳ) | FAIL | 193/194, đúng thứ tự | **`enable_reg=0`** |

Kết luận:
1. **Dữ liệu không thừa, không lệch thứ tự**: ở mọi kịch bản, DUT nhận đúng chuỗi testbench sinh ra (cùng nội dung, cùng thứ tự);
   số word bias gửi (32) khớp với số DUT mong đợi (`trans_cycles_psum` = 32).
2. Cùng một dữ liệu, chỉ thêm **đúng 1 chu kỳ trống ở đúng 1 vị trí** (trước word bias cuối) là đủ làm hỏng; dời khoảng trống
   đi 1 word về trước hoặc về sau là PASS. Trong 6 trạng thái nạp, chỉ `GET_BIAS` có điểm yếu này.
3. **Không phải tối ưu hiệu năng.** Khi dữ liệu tới liên tục, tại chu kỳ chuyển trạng thái `enable_dma_i_reg` luôn bằng 1
   (dòng 1–2 của bảng), nên thêm điều kiện `& enable_dma_i_reg` **không làm chậm đi chu kỳ nào**. Nó chỉ thay đổi hành vi khi có
   khoảng trống, mà khi đó hành vi hiện tại là sai. Cái giá duy nhất là 1 cổng AND trong logic chuyển trạng thái; các trạng thái khác đều đã có.
4. Thiết kế hiện tại dựa vào giả định "dữ liệu tới liên tục mỗi chu kỳ" (comment trong `psum_pipeline.v` ghi "fixed lockstep schedule,
   no flow control"). AXI4-Stream cho phép `tvalid` thấp ở bất kỳ chu kỳ nào, và AXI DMA không đảm bảo dữ liệu liên tục khi DDR hoặc
   interconnect chậm, nên trên FPGA thật lỗi có thể xảy ra **lúc có lúc không**.
**Bản sửa (2026-10-10)**: `hdl/OpenEye_FPGA.v`, trạng thái `GET_BIAS`, đúng 1 điều kiện (kèm comment):
```verilog
- if (fsm_psum_cycle == trans_cycles_psum - 1) begin
+ if ((fsm_psum_cycle == trans_cycles_psum - 1) & enable_dma_i_reg) begin
```
FSM chỉ rời `GET_BIAS` ở chu kỳ **thật sự nhận** word bias cuối, giống `GET_IACT`/`GET_WGHT`/`GET_QUANTIZE`.
Cùng với bản sửa lỗi #13 và bản sửa lỗi #6/#7 (bên dưới), đây là 3 thay đổi RTL so với upstream (tính tới 2026-10-14; sau đó thêm #14, #19 và 3 commit
upstream, xem mục 8b).

**Kiểm chứng sau khi sửa:**

| Kiểm tra | Trước khi sửa | Sau khi sửa |
|---|---|---|
| 15 kịch bản khoảng trống (`gap_before` ở 9 vị trí, `typical`, `typical`+`bandwidth=0.5`, `slow`, burst 1 word) | 3 FAIL (trước word 173, bw 0.5, burst 1) | **15/15 PASS**, DUT nhận đủ 194/194 word đúng thứ tự |
| `--mem slow`, 8 case (5 nhỏ + 3 MNIST) | 5/5 case nhỏ đã thử đều treo | **8/8 PASS** (độ trễ +112 % đến +350 % so với bộ nhớ lý tưởng) |
| Baseline 9 case, bộ nhớ lý tưởng | — | **0 chu kỳ chênh lệch ở cả 9 case**, nên không mất hiệu năng |
| 16 test Conv (`test_conv_const.py`) | 9 PASS, 7 FAIL (lỗi có sẵn, mục trên) | **Giống hệt**: 9 PASS, cùng 7 FAIL |
| 63 test GEMM/Dense (`test_gemm_layer.py`) | 23 test chạy đối chứng đều FAIL | 40 PASS, 23 FAIL; **cả 23 cũng FAIL trên RTL gốc** (lỗi có sẵn `FC activation write ... bank=1 addr=0`), không có hồi quy |
| Lint baseline (Verilator 5.020) | — | 0 warning mới (`parallel` 38, `fpga` 478) |

**Tài nguyên** (Yosys 0.69 `synth_xilinx`, module `OpenEye_FPGA`, tham số mặc định):

| | Trước | Sau | Chênh lệch |
|---|---:|---:|---:|
| Flip-flop (FDCE + FDPE) | 4.755 | 4.755 | 0 |
| LUT (LUT2–LUT6) | 4.000 | 3.968 | −32 (nhiễu tối ưu của công cụ, không phải tiết kiệm thật) |
| MUXF7 / CARRY4 / DSP48 | 1 / 225 / 2 | 0 / 225 / 2 | ~0 |

Về lý thuyết bản sửa thêm 1 đầu vào cho một hàm logic (một cổng AND), tức nhiều nhất 1 LUT. Trên thực tế đầu vào này được gộp vào
LUT có sẵn; số LUT thay đổi ±vài chục chỉ là do bộ ánh xạ LUT (ABC) sắp xếp lại khi logic đầu vào thay đổi. Không thêm flip-flop,
BRAM hay DSP.

**Vì sao sửa RTL thay vì bắt DMA gửi liên tục:**
- Phía bộ tăng tốc chỉ kiểm soát được `ready`; còn `valid` do AXI DMA và DDR quyết định. Giao thức AXI4-Stream cho phép `tvalid` thấp ở bất kỳ chu kỳ nào,
  và AXI DMA không đảm bảo dữ liệu liên tục (độ trễ DDR, refresh, tranh chấp bus với CPU, ranh giới burst khi số burst đang chờ không đủ để che độ trễ).
- Muốn **đảm bảo** liên tục thì phải đặt một FIFO "store and forward" trước bộ tăng tốc, gom đủ ít nhất tới word bias cuối rồi mới phát.
  Với `mnist1` thì phần đó là khoảng 15.700 word × 8 byte ≈ 123 KB (khoảng 27–31 BRAM36), và **cộng thêm độ trễ của cả đoạn stream đó**.
  So với 1 cổng AND (0 LUT đo được), cách này tốn hơn nhiều bậc và đi ngược mục tiêu giảm độ trễ.
- Trong 6 trạng thái nạp, 5 trạng thái đã kiểm tra `enable_dma_i_reg`, nên RTL vốn đã được thiết kế để chịu khoảng trống; `GET_BIAS` chỉ là chỗ bị thiếu.

**Vì sao chỉ một vài cấu hình bị khoảng trống đúng trước word bias cuối:**
- Mỗi layer là **một lần truyền DMA** gồm lần lượt: H word cấu hình (18 với DMA 64 bit, 34 với 32 bit) → iact → weight → bias → bảng lượng tử.
  Word bias cuối nằm ở vị trí `H + iact + weight + bias − 1`.
- Lỗi chỉ xảy ra khi **chu kỳ ngay trước word đó** không có dữ liệu. Với bộ nhớ chỉ tạo khoảng trống ở ranh giới burst (mỗi 16 hoặc 32 word),
  điều đó chỉ xảy ra khi vị trí trên là bội của độ dài burst. Ở 9 case hiện tại, vị trí đó luôn chia 16 dư 1 (vì H = 18 còn các phần sau là bội của 16),
  nên không trúng: 4 cấu hình kiểu ranh giới burst (`typical`, burst 16 với 1 burst chờ, độ trễ 10 hoặc 30, burst 64) đều không lỗi.
- Khoảng trống **ngẫu nhiên** (jitter, nửa băng thông, refresh DDR, tranh chấp bus) có thể rơi vào bất kỳ chu kỳ nào. `slow` trúng ở cả 9 case.
  Trên FPGA thật xác suất mỗi layer nhỏ, nhưng khác 0, nên lỗi xảy ra **lúc có lúc không**, rất khó debug.

**Khác:**
- `model_test` (chạy model từ file TFLite qua `tflite2model`) bị tắt trong testbench; các model nhiều layer chạy qua `data_create` (mục 6.13, 8d), weight
  đã huấn luyện của từng layer Conv nạp bằng `OPENEYE_TFLITE_CONV` (mục 3c).
- **CI "Lint"** của upstream luôn fail vì các warning có sẵn trong RTL (repo gốc cũng fail ở mọi commit). Từ 2026-10-10, CI của `dev`
  dùng lint theo baseline (mục 9c), chỉ fail khi có warning mới. Chi tiết từng warning: mục 9b.

### Sửa lỗi #13: bộ đếm vòng lặp đọc iact bị lái từ 2 khối `always` (2026-10-13, được bạn đồng ý)

**Thay đổi** (`hdl/iact_stream_constructor.v`, chỉ chuyển chỗ 4 dòng, không thêm logic):
- Trước: `rd_cycle_loop_cnt_0..3` được **đếm** trong khối `always` của bộ đọc/encode (dòng 233), nhưng được **reset** trong khối `always`
  của bộ ghi/lưu trữ (dòng 437). Một thanh ghi bị gán ở 2 khối là "multi-driven".
- Sau: 4 lệnh reset nằm trong nhánh reset của chính khối đang đếm (khối dòng 233). Khối dòng 437 không còn gán các bộ đếm này.
  `rd_cycle_loop_cnt_4` không đổi: nó chỉ được gán trong khối dòng 437 và không được dùng (lint `UNUSEDSIGNAL`), nên không bị multi-driven.

**Vì sao trước đây mô phỏng đúng mà phần cứng sai:**
- Simulator (Icarus) cho 2 khối cùng ghi một biến. Khối reset chỉ ghi khi `rst_ni = 0`, còn khối đếm ghi khi chạy, nên kết quả trùng với ý người viết.
- Công cụ tổng hợp phải tạo **một** flip-flop cho mỗi bit. Hai khối tạo ra 2 nguồn lái trên cùng một dây. Vivado (Synth 8-6858/8-6859) giữ nguồn hằng số
  (giá trị reset 0) và bỏ logic đếm, nên trên FPGA các bộ đếm luôn bằng 0. Thí nghiệm ở `doc/experiments/2026-10-13_bug13_stuck_counters.md` cho thấy
  khi đó 6/9 case baseline (mọi layer có `iact_read_limit_1..3` ≠ 0, gồm cả 3 layer MNIST) tính sai.
- Verilator lint không bắt được vì `MULTIDRIVEN` chỉ cảnh báo khi 2 khối dùng clock khác nhau.

**Kiểm chứng:**

| Kiểm tra | Kết quả |
|---|---|
| Yosys `check` riêng module `iact_stream_constructor` | Bản cũ: 32 cảnh báo "multiple conflicting drivers" (4 bộ đếm × 8 bit). Bản sửa: **0** |
| 9 case baseline (`run_profile --compare doc/perf/baseline_2026-10-10`) | **9/9 PASS, số chu kỳ và số word DMA chênh lệch 0** ở cả 9 case |
| 79 test hồi quy (16 Conv `test_conv_const.py` + 63 GEMM/Dense `test_gemm_layer.py`) | **Giống hệt từng test** so với lần chạy 2026-10-10: Conv 9 PASS / 7 FAIL, GEMM 40 PASS / 23 FAIL, 0 test đổi kết quả (các FAIL là lỗi có sẵn #5–#7) |
| Lint baseline (Verilator 5.020) | 0 warning mới (`parallel` 38, `fpga` 478) |
| Yosys `synth_xilinx` toàn thiết kế (so với lần chạy ngày 2026-10-12) | FF 45.274 → 45.402 (**+128 = 4 instance × 4 bộ đếm × 8 bit**, đúng các bộ đếm mà trước đây bị bỏ); LUT 61.277 → 61.456 (+179, +0,3 %); CARRY4 +33 (bộ cộng 8 bit); BRAM và DSP không đổi. Trên ZU7EV: +0,03 % FF, +0,08 % LUT. Yosys còn báo conflicting drivers cho `a`, `b` trong `OpenEye_FPGA.v`: đây là biến chạy vòng `for` dùng chung giữa các khối `always`, không có logic nào đọc nên không thành phần cứng. Lỗi cũ, vô hại, Vivado không báo |
| Vivado 2024.2, place & route 4 ns (2026-10-14, `doc/synth/2026-10-14_route4ns_fix13_zu7ev/`) | CRITICAL WARNING Synth 8-6858/8-6859: **200 → 0**. Vẫn đạt 250 MHz (WNS +0,117 ns). Mỗi `iact_stream_constructor` **+32 FF** (306 → 338), đúng 4 bộ đếm × 8 bit; tổng sau tổng hợp +134 FF, +127 LUT; BRAM, URAM, DSP không đổi |

**Tốt hơn cũ ở đâu:** trên mô phỏng không có gì thay đổi (đúng như mong muốn: cùng số chu kỳ, cùng kết quả). Khác biệt nằm ở **phần cứng thật**:
bitstream tạo từ RTL cũ tính sai mọi layer thực tế, còn RTL mới cho phần cứng làm đúng như mô phỏng. Bản sửa không tốn chu kỳ nào. Về tài nguyên,
phần cứng chỉ có thêm đúng các bộ đếm mà thiết kế vốn cần (4 × 8 bit = 32 flip-flop cùng bộ cộng và so sánh), những thứ trước đây Vivado đã bỏ đi.

### Sửa lỗi #6 và #7 (`NUM_GLB_IACT=3`) (2026-10-14, được bạn đồng ý)

**Thay đổi** (`hdl/iact_stream_constructor.v`, 12 dòng thêm, 7 dòng bỏ; không file RTL nào khác):

```verilog
// mới: chỉ Dense mới xoay vòng các bank iact
wire rotate_banks = fully_connected_i && (NUM_GLB_IACT > 1);

// WRITE_TO_MEMORY, dữ liệu (cũ: NUM_GLB_IACT == 1 ? mọi bank : chỉ bank router_cycle)
if (!rotate_banks || (router_cycle == r)) mem_data_payload_reg[r][w] <= ...;

// WRITE_TO_MEMORY, địa chỉ (cũ: (NUM_GLB_IACT == 1) | ...)
if (!rotate_banks | (router_cycle == 0) | (switching_cycle == 0)) begin ram_wr_addr <= wr_addr_0; ... end

// địa chỉ RAM (cũ: ram_wr_en_q ? ram_wr_addr : ...)
wire [ADDRWIDTH-1:0] bank_addr = ram_wr_en_q ? (single_channel ? ram_wr_addr_q : ram_wr_addr) : ...;
```

- **Lỗi #6 (1 channel):** chế độ 1 channel xếp 2 hàng ảnh vào 2 ô của **cùng** một word RAM và tự tính địa chỉ đó vào `ram_wr_addr_q`.
  Commit upstream `23be043` đổi RAM sang `ram_wr_addr`, làm địa chỉ này thành tín hiệu không ai dùng (lint đã báo `UNUSEDSIGNAL 'ram_wr_addr_q'`).
  Nay chế độ 1 channel dùng lại `ram_wr_addr_q`; các chế độ khác giữ `ram_wr_addr`.
- **Lỗi #7 (`NUM_GLB_IACT=3`):** Conv đọc **cùng** một chuỗi pixel từ mọi bank (bank r lệch `r*channel_div_trans` địa chỉ), nên bộ ghi phải ghi mỗi word vào
  **mọi** bank. `23be043` áp cách ghi xoay vòng của Dense cho cả Conv, làm một pixel bị chia sang 2 bank và 2 địa chỉ. Nay chỉ Dense
  (`fully_connected_i`) mới xoay vòng; với Dense điều kiện mới giống hệt điều kiện cũ, nên Dense không đổi.

**Kiểm chứng:**

| Kiểm tra | Trước | Sau |
|---|---|---|
| 34 test Conv (`test_conv_const.py`) | 19 PASS / 15 FAIL | **34/34 PASS** |
| 63 test GEMM/Dense (`test_gemm_layer.py`) | 40 / 23 | 40 / 23, **giống hệt từng test** (23 là lỗi Dense #5) |
| Test mới `test_mnist_layers.py -k mapping` (1/2/3/4/8 channel × `NUM_GLB_IACT` 1/3) | 1 channel và `NUM_GLB_IACT=3` FAIL | 8 passed, 2 xfailed (3 channel, lỗi Python) |
| 9 case baseline | – | 9/9 PASS, **0 chu kỳ, 0 word DMA thay đổi** |
| Lint | 478 (fpga) | 477 (`UNUSEDSIGNAL ram_wr_addr_q` biến mất), 0 mới; baseline đã hạ |
| Yosys (so với sau lỗi #13) | 61.456 LUT / 45.402 FF | **+65 LUT, +104 FF, +31 CARRY4** (logic địa chỉ 1 channel không còn bị xoá); BRAM/DSP không đổi |

**Layer MNIST thật** (`test_mnist_layers.py::test_mnist_conv`, đánh dấu `xfail(strict)` để khi sửa xong sẽ tự báo): Conv1 FAIL do lỗi #17, Conv2 và Conv3
FAIL do lỗi #18 (Conv3 thêm #9), FC 3136 → 10 chưa chạy được do lỗi Dense #5. Ba lỗi #17, #18, #9 đều có từ trước bản sửa này.
Chi tiết: `doc/experiments/2026-10-14_channel_bugs.md`.

### Sửa lỗi #18: mỗi lần gửi weight đọc gấp đôi số địa chỉ (2026-10-15, được bạn đồng ý; chỉ sửa Python)

**Nguyên nhân** (`doc/experiments/2026-10-15_bug18_weight_send.md`): `src/open_eye/conv_mapper.py` có 2 khoá `used_wght_per_PE` trong cùng một dict; khoá sau
(số word chưa đóng gói, 192) ghi đè khoá trước (đã chia cho `PARALLEL_MACS`, 96). Từ RTL `3e2e20f` (19/9) vòng gửi weight của `OpenEye_FPGA.v` đếm theo word đã
đóng gói, nên mỗi lần gửi đọc 192 thay vì 96 địa chỉ: lần gửi k đọc từ 192k thay vì 96k, tức weight của đợt channel khác; nửa số lần đọc rơi vào vùng chưa ghi
(`X`), và khi vượt 4.096 địa chỉ (12 bit) thì quay vòng về 0 (lỗi thấy được ở Conv2/Conv3). Test hiện có dùng weight hằng số (mọi channel/filter giống nhau) nên
không thấy; với weight ngẫu nhiên mọi layer > 4 channel đều sai, kể cả case baseline `mnist2`.

**Thay đổi:** xoá dòng `"used_wght_per_PE": layer_params.used_wght_per_PE,` (thêm comment giải thích ở dòng còn lại). RTL không đổi, không cần tổng hợp lại.
Với `PARALLEL_MACS = 1` hai giá trị bằng nhau; Dense/Pooling/Depthwise dùng mapper khác.

**Kiểm chứng từng word** (trước khi áp dụng, trên bản sao): tính lại layer bằng numpy từ chính các số nguyên DUT nhận, tách mỗi word 64 bit thành 2 psum 20 bit,
đặt vào (filter, x, y) theo `output_order`, so từng giá trị; kiểm tra không thiếu/không trùng vị trí, không có X, bit trên = 0. 9 trường hợp (7 với dữ liệu ngẫu nhiên,
gồm 64→64 và Conv2/Conv3 MNIST thật): **mọi giá trị bằng numpy** (ví dụ Conv2 thật 12.544/12.544), mọi dòng mang kết quả giống hệt file tham chiếu, tham chiếu của
testbench cũng bằng numpy. Hướng kernel chuyển vị cho kết quả khác hẳn (đối chứng). Dòng khác tham chiếu chỉ là dòng/ô đệm (DUT gửi psum của ô PE không dùng; Conv3: lỗi #9).
Công cụ chính thức: `tools/verify_conv_output.py` + `OPENEYE_DUMP_VERIFY=1`; các test `test_mnist_layers.py::test_random_data` và `test_mnist_conv` tự chạy nó.

**Kiểm chứng sau khi áp dụng:** xem bảng hồi quy dưới đây và nhật ký 2026-10-15. Baseline mới `doc/perf/baseline_2026-10-15/`: 9/9 PASS, `mnist1` 65.800 → 55.048 (−16,3 %),
`mnist2` 87.032 → 65.528 (−24,7 %), `mnist3` 26.728 → 20.584 (−23,0 %), `32x3_f16` −2,6 %, 5 case còn lại 0; số word DMA không đổi.

| Kiểm tra (sau khi áp dụng) | Kết quả |
|---|---|
| 34 test Conv (`test_conv_const.py`) | 34/34 PASS, giống trước |
| 63 test GEMM/Dense (`test_gemm_layer.py`) | 40 PASS / 23 FAIL, **giống hệt từng test** (23 là lỗi Dense #5; Dense không dùng `conv_mapper`) |
| 19 test `test_mnist_layers.py` | 10 mapping (8 passed, 2 xfailed 3 channel); **Conv2 MNIST thật passed**; Conv1 xfailed (#17), Conv3 xfailed (#9); **6 test dữ liệu ngẫu nhiên passed**, mỗi test kèm kiểm tra độc lập từng word |
| Kiểm tra độc lập Conv3 / Conv2 của lần hồi quy | 3.136/3.136 và 12.544/12.544 giá trị = numpy; Conv3: 448 dòng khác tham chiếu chỉ ở ô đệm (#9) |
| 9 case baseline | 9/9 PASS, lưu thành `doc/perf/baseline_2026-10-15/` |
| Vivado | Không cần (không đổi RTL) |

### Phân tích lỗi #14: `results_ready` vừa gán blocking vừa non-blocking (2026-10-16, không sửa RTL)

Chi tiết và script: `doc/experiments/2026-10-16_bug14_results_ready.md`, `doc/experiments/2026-10-16_bug14/`.

**Code.** Trong khối `always` lớn của `hdl/psum_pipeline.v`, thanh ghi `results_ready` được gán theo hai kiểu:
- `WAIT_TO_SEND_READY_SIGNAL` (dòng 429): `results_ready = 0;` (blocking).
- `CALCULATE_PSUM` (449–457): nếu đang 0 thì `results_ready = 1;` rồi AND lần lượt `psum_ready_o_reg` của các PE đầu chuỗi psum
  (blocking); dòng 460 dùng ngay giá trị này trong **cùng chu kỳ**. Khi thoát: `results_ready <= 1;` (485).
- `PSUM_GET_RESULTS`: `results_ready <= 1;` (507, non-blocking, viết trước), rồi `results_ready = results_ready & psum_enable_o...`
  (522, blocking, viết sau); dòng 536 dùng giá trị blocking.

**Ý nghĩa theo chuẩn Verilog (mô phỏng).** Gán blocking có hiệu lực ngay; gán non-blocking được áp ở cuối chu kỳ, sau mọi gán blocking,
nên **non-blocking thắng dù viết trước**. Vì vậy biến này đóng hai vai:
- trong `CALCULATE_PSUM`: một cờ "dính" (thanh ghi). Chu kỳ đầu tiên mọi PE đầu chuỗi cùng báo sẵn sàng thì cờ lên 1, được dùng ngay
  chu kỳ đó và giữ 1;
- trong `PSUM_GET_RESULTS`: một tín hiệu tổ hợp "mọi PE đầu chuỗi đang gửi kết quả". FSM chỉ đếm kết quả ở chu kỳ đó, còn giá trị thanh ghi
  bị ép về 1 mỗi chu kỳ.

**Mỗi công cụ hiểu thế nào:**

| Công cụ | Cách hiểu | Bằng chứng |
|---|---|---|
| Icarus (mọi test) | Đúng chuẩn, như trên | mốc so sánh |
| **Vivado 2024.2** (phần cứng hiện tại) | **Giống mô phỏng**. Cảnh báo 8-6090 chỉ là cảnh báo chung, không xoá logic nào | 3 thí nghiệm bên dưới |
| **Yosys 0.69** | **Theo thứ tự dòng code: lệnh blocking viết sau đè lệnh non-blocking viết trước** | ví dụ 2 dòng: Icarus cho `r = 1`, Yosys cho `r = r & a` |
| Verilator 5.020 | Từ chối: `%Error-BLKANDNBLK ... Unsupported` (4 lỗi) + 3 cảnh báo `BLKSEQ` | lint |

**Thí nghiệm (không sửa RTL):**

| # | Thí nghiệm | Kết quả |
|---|---|---|
| E1 | Mở checkpoint tổng hợp fix67 (chính phần cứng hiện tại) | Có thanh ghi `results_ready_reg` (FDCE) + 4 LUT, đầu vào là đúng các tín hiệu `psum_ready_o_reg`, `psum_enable_o`, `router_mode_psum`: **không bị xoá** |
| E2 | Module nhỏ chép đúng kiểu gán này, so netlist Vivado với RTL, 200.000 chu kỳ ngẫu nhiên | **0 sai khác**. Đối chứng (mô hình coi mọi lệnh là non-blocking): 24.585 sai khác, nên phép so phân biệt được |
| E3 | Netlist Yosys của module nhỏ | 13.820 / 200.000 chu kỳ sai khác |
| E4 | Tổng hợp `psum_pipeline` bằng Vivado với đúng tham số phần cứng, thay vào mô phỏng hệ thống (phần còn lại vẫn RTL) | **9/9 ca PASS** (7 ca mốc dạng dốc + 2 ca ngẫu nhiên); chu kỳ từng pha **giống hệt** mốc 2026-10-15 (568 … 55.048 / 65.528 / 20.584); kiểm tra độc lập: mọi giá trị = numpy |
| E5 | Làm như E4 với netlist Yosys | **Treo ngay ở layer nhỏ nhất** (8×1): FSM chính kẹt ở trạng thái 10, FSM psum kẹt ở `PSUM_GET_RESULTS` với `fsm_psum_cycle = 0` |
| E6 | Probe trên RTL | Mỗi lần vào `PSUM_GET_RESULTS`, kết quả cần 16–28 chu kỳ để ra khỏi chuỗi delay của PE, trong lúc đó điều kiện AND = 0. Theo chuẩn (và Vivado) thanh ghi được ép về 1 nên FSM chỉ chờ; theo Yosys thanh ghi nhận 0 ở chu kỳ đầu rồi **giữ 0 mãi**, nên không bao giờ đếm được kết quả |

**Kết luận:**
- **Phần cứng FPGA hiện tại (Vivado 2024.2) chạy đúng**, không có kết quả sai do lỗi này.
- Lỗi thật là **code không khả chuyển**: cùng file, Yosys tạo ra mạch treo ở mọi layer, Verilator không chạy được. Điều này chặn flow Yosys của repo
  (`yosys/`, `nextpnr/`, GateMate), mọi flow ASIC dựa trên Yosys, và mô phỏng bằng Verilator (nhanh hơn Icarus nhiều lần). Một phiên bản Vivado khác
  cũng có thể hiểu khác mà vẫn đúng chuẩn.
- Hai cách sửa "dễ thấy" lại **sai**: đổi hết sang `<=` thì cờ không bao giờ lên 1 (treo, chính là mô hình đối chứng của E2).

**Đề xuất sửa (đã làm ngày 2026-10-19, mục kế tiếp):** tách phần tổ hợp ra khỏi khối FSM, giữ nguyên biểu thức và thời điểm từng chu kỳ:
- `generate` tính cho mỗi PE đầu chuỗi `psum_ready_o_reg[i] | not_chain_start` và `psum_enable_o[i] | not_chain_start`, rồi
  `all_psum_ready = &...`, `all_psum_enable = &...` (đúng các biểu thức cũ, chỉ chuyển ra ngoài);
- `results_ready_calc = results_ready | ((psum_ready_i_reg != 0) & all_psum_ready)` (cờ dính, dùng ngay trong chu kỳ);
- trong FSM chỉ còn gán non-blocking: `WAIT_TO_SEND_READY_SIGNAL`: `results_ready <= 0`; `CALCULATE_PSUM`: `results_ready <= results_ready_calc`
  và điều kiện `results_ready_calc & (psum_ready_i_reg != 0)`; `PSUM_GET_RESULTS`: bỏ dòng 522, điều kiện `results_ready & all_psum_enable`.

Vẫn 1 flip-flop, cùng hàm logic, không thêm chu kỳ. Các phương án bị loại: đổi hết sang `<=` (treo); đổi hết sang `=` (chạy được nhưng thanh ghi gán
blocking, vẫn còn `BLKSEQ`); thêm biến tạm blocking trong khối FSM (diff nhỏ hơn nhưng vẫn trộn tổ hợp với tuần tự); thay cờ bằng
`fsm_psum_cycle != 0` (tiết kiệm 1 FF nhưng dựa vào các bất biến dễ bị phá).

**Kế hoạch kiểm chứng (đã thực hiện, kết quả ở mục kế tiếp):** chạy song song bản cũ và bản mới trong cùng mô phỏng, so mọi đầu ra mỗi chu kỳ (9 ca mốc + 1 triệu chu kỳ đầu vào
ngẫu nhiên); netlist Vivado và **netlist Yosys** của bản mới trong hệ thống (Yosys phải PASS, hiện đang treo); hồi quy 34 Conv + 63 GEMM/Dense +
19 MNIST/ngẫu nhiên + 9 ca mốc (0 chu kỳ thay đổi); lint: hết 4 `BLKANDNBLK` và 3 `BLKSEQ` của `psum_pipeline.v`; Vivado: hết 10 cảnh báo 8-6090,
tài nguyên và fmax không đổi.

### Sửa lỗi #14: tách phần tổ hợp của `results_ready` (2026-10-19, được bạn đồng ý)

Chỉ sửa `hdl/psum_pipeline.v` (+41 / −18 dòng). Các biểu thức AND giữ nguyên, chỉ chuyển ra ngoài khối FSM:

```verilog
// ngoài khối FSM: mỗi PE đầu chuỗi psum một term (generate), rồi AND rút gọn
assign chain_ready_terms[TERM]  = psum_ready_o_reg[GLB] | not_chain_start;
assign chain_enable_terms[TERM] = psum_enable_o[GLB]    | not_chain_start;
wire all_psum_ready     = &chain_ready_terms;    // CALCULATE_PSUM: mọi PE đầu chuỗi báo sẵn sàng
wire all_psum_enable    = &chain_enable_terms;   // PSUM_GET_RESULTS: mọi PE đầu chuỗi đang gửi kết quả
wire results_ready_calc = results_ready | ((psum_ready_i_reg != 0) & all_psum_ready);  // cờ dính, dùng ngay trong chu kỳ
```

| Trạng thái | Trước | Sau |
|---|---|---|
| `WAIT_TO_SEND_READY_SIGNAL` | `results_ready = 0;` | `results_ready <= 0;` |
| `CALCULATE_PSUM` | khối blocking `results_ready = 1; results_ready = results_ready & ...` (12 dòng); điều kiện `results_ready & (psum_ready_i_reg != 0)` | `results_ready <= results_ready_calc;` điều kiện `results_ready_calc & (psum_ready_i_reg != 0)` |
| `PSUM_GET_RESULTS` | `results_ready <= 1;` rồi `results_ready = results_ready & ...` (blocking); điều kiện `results_ready` | giữ `results_ready <= 1;`, bỏ dòng blocking; điều kiện `results_ready & all_psum_enable` |

Vì sao tương đương từng chu kỳ với code cũ (theo ngữ nghĩa mô phỏng, cũng là ngữ nghĩa Vivado đã dùng):
- `CALCULATE_PSUM`: code cũ chỉ tính lại khi cờ đang 0 và `psum_ready_i_reg != 0`, kết quả là AND các term; nếu cờ đã 1 thì giữ 1.
  Đó đúng là `results_ready | ((psum_ready_i_reg != 0) & all_psum_ready)`, dùng ngay trong chu kỳ (như giá trị blocking) và lưu lại (như thanh ghi).
- `PSUM_GET_RESULTS`: giá trị blocking cũ là `results_ready & AND(term)`; thanh ghi cuối chu kỳ là 1 (lệnh `<=` thắng). Code mới y hệt.
- `WAIT_TO_SEND_READY_SIGNAL`: thanh ghi về 0 như cũ. Reset, lệnh `<= 1` khi thoát `CALCULATE_PSUM` và `<= 0` khi `status_reg_enable_reg` giữ nguyên.

**Kiểm chứng:**

| Kiểm tra | Kết quả |
|---|---|
| **Lockstep trong hệ thống**: bản cũ (`35f747f`) và bản mới chạy song song trong cùng mô phỏng, cùng đầu vào; 19 đầu ra so bằng `!==` ở mỗi sườn xuống clock, sai một lần là `$fatal`. Chạy trên **cả 125 test** (34 Conv, 63 GEMM/Dense, 19 MNIST/ngẫu nhiên, 9 ca mốc) | **125/125 test: 0 sai khác**, tổng 767.343 chu kỳ được so (Conv 57.947; GEMM/Dense 58.380; MNIST/ngẫu nhiên 499.625; ca mốc 151.391). Thêm 23 test GEMM/Dense chạy lại với `OPENEYE_SKIP_FC_WRITE_CHECK=1` (chạy hết, không dừng sớm): 0 sai khác trên 24.804 chu kỳ |
| Đối chứng: bản "đột biến" quyết định trễ 1 chu kỳ trong `CALCULATE_PSUM` | Bị bắt ngay (`LOCKSTEP MISMATCH` ở `psum_buffer_addr`, test FAIL): phép so phân biệt được |
| Lockstep ngẫu nhiên ở mức module (đầu vào được điều chỉnh để FSM đi qua `CALCULATE_PSUM` và `PSUM_GET_RESULTS`) | 300.000 chu kỳ, **0 sai khác**; FSM đi qua đủ 7 trạng thái (`CALCULATE_PSUM` 5.344 chu kỳ, cờ được bật 765 lần; `PSUM_GET_RESULTS` 252.961 chu kỳ, trong đó 41.404 chu kỳ chờ). Lần chạy đầu (1 triệu chu kỳ) cũng 0 sai khác nhưng không vào được hai trạng thái này nên không tính |
| Kết quả các bộ test (so với trước khi sửa) | Giống hệt trước khi sửa: Conv 34/34 PASS; GEMM/Dense 40 PASS / 23 FAIL (cả 23 do bộ kiểm tra FC live của testbench: 17 lỗi giá trị, 6 lỗi địa chỉ, lỗi #5); MNIST/ngẫu nhiên 15 passed + 4 xfailed (3 channel ×2, #17, #9); 9 ca mốc PASS. **Tắt bộ kiểm tra FC live: 23/23 test GEMM/Dense PASS** |
| 9 ca mốc (`tools/run_profile.py --compare doc/perf/baseline_2026-10-15`) | 9/9 PASS, **0 chu kỳ và 0 word DMA chênh lệch** ở mọi pha của cả 9 ca |
| Netlist **Vivado** của module mới thay vào mô phỏng hệ thống: 8×1, 32×3 16 filter, mnist3, ngẫu nhiên 8×4×32→32 | 4/4 PASS, chu kỳ 568 / 3.556 / 20.584 / 12.200 giống mốc, mọi giá trị = numpy |
| Netlist **Yosys** của module mới (trước đây **treo**) | **4/4 PASS**, chu kỳ giống hệt, mọi giá trị = numpy |
| Lint Verilator 5.020 | fpga 477 → 470: hết 4 lỗi `BLKANDNBLK` và 3 cảnh báo `BLKSEQ` của `psum_pipeline.v`, 0 cảnh báo mới; đã hạ baseline |
| Verilator 5.020 biên dịch cả thiết kế thành C++ (`--cc --build`) | RTL cũ: dừng với 4 lỗi `BLKANDNBLK`; RTL mới: **biên dịch xong** (0 lỗi). Chưa chạy mô phỏng cocotb bằng Verilator (bước sau) |
| Yosys `synth_xilinx` riêng `psum_pipeline` | FF 1.996 → 1.996; LUT 4.115 → 4.117; DSP 9 → 9 |
| Vivado 2024.2 toàn thiết kế, synth + place & route ở 4 ns (`doc/synth/2026-10-19_route4ns_fix14_zu7ev/`) | 0 ERROR / 0 CRITICAL; Synth 8-6090: 10 → 0, không loại cảnh báo nào khác thay đổi; WNS +0,219 / **+0,097 ns** (fix67: +0,192 / +0,048), đạt 250 MHz; sau route LUT 64.162 → 64.050, FF 39.192 → 39.184; BRAM / URAM / DSP không đổi |

Kết luận: hành vi không đổi ở bất kỳ chu kỳ nào (chứng minh bằng lockstep), nên số chu kỳ và kết quả của mọi layer giữ nguyên; tài nguyên và tần số
chỉ khác ở mức dao động của công cụ. Cái được là code nay có cùng một nghĩa với mọi công cụ: Yosys tạo ra mạch chạy đúng, Verilator không còn lỗi.

### Lấy 3 commit upstream: `b6fa369`, `2c8c324`, `2bf497d` (2026-10-21, được bạn đồng ý)

Chi tiết: `doc/experiments/2026-10-21_upstream_cherry_pick.md`. `git cherry-pick -x` không xung đột: `0cacda1`, `22614d2`, `9c0c8dc` (tác giả gốc DenLeb,
mỗi commit ghi hash upstream), cộng một commit riêng của mình.

| Thay đổi | Trước | Sau |
|---|---|---|
| `OpenEye_FPGA.v` (comment) | `TRANS_WORDS - Number of DMA transfer words` (sai nghĩa) | `Number of words per transmissions from layer to layer` |
| `OpenEye_Parallel.v` | 4 khối generate của router **psum** mang tên `gen_router_iact_bottom_connect/top_connect/top_edge/bottom_edge` (trùng tên với khối của router iact, chỉ không xung đột vì nằm trong hai vòng `for` khác nhau) | `gen_router_psum_*`: tên hierarchy trong Vivado, khi debug và trong báo cáo đúng với nội dung |
| `PE.v`: `first_spad_words_wght` | `wire [4:0]`, nối vào cổng `first_spad_words_o` 7 bit của `data_pipeline_wght`: bộ đếm số word của SPad địa chỉ weight bị cắt còn 5 bit, giá trị ≥ 32 sẽ quay vòng trong 4 phép so `(first_spad_words_wght - 1) > wght_addr_vec` | `wire [$clog2(WGHT_ADDR_ADDR+1)-1:0]` = 7 bit, khớp cổng |
| `PE.v`: `filters_reg_M0` | `wire [5:0]` nối vào cổng `first_spad_max_i` 8 bit | `wire [$clog2(WGHT_ADDR_ADDR+1):0]` = 8 bit; **mình thêm**: gán bằng mở rộng 0 tường minh qua `generate if` (`FILTERS_M0_BITS > 6`: thêm bit 0; nếu không: lấy vừa đủ bit), nên không sinh cảnh báo mới và vẫn đúng khi `WGHT_ADDR_ADDR=16` (đúng 6 bit) hay 8 |

**Lỗi cắt bit có xảy ra thật không?** Đo bằng probe (`first_spad_words_o` lớn nhất trên mọi PE): mọi layer Conv đã thử (4–64 channel, 4–64 filter) chỉ tới **13** (kernel rộng 3 × tối đa 4 channel mỗi PE + 1); 8 test GEMM/Dense mẫu từ 3 tới **25**. **Dense K = 512 (10 output) lên tới 64** (đầy cả 64 word của SPad địa chỉ), có 3.564 mẫu ≥ 32, tức là dây 5 bit cũ **có** cắt bit thật. Nhưng PE cũ vẫn PASS ở K = 512, và lockstep PE trên chính layer đó cho **0 sai khác trong 161.088 PE-chu kỳ**: ở mọi trường hợp đã thử, các phép so bị cắt bit vẫn cho cùng quyết định. Nên bản sửa là **phòng ngừa** (đúng độ rộng, lint và Vivado sạch), không thay đổi kết quả nào đã thấy.

Kết quả phụ cho lỗi #19 (Dense K > 512 sai, phát hiện 2026-10-19): K = 520 sai 10/10 output với **cả** PE cũ lẫn PE mới, nên lỗi này không do độ rộng bit. Nguyên nhân thật (tìm ra cùng ngày): bộ đếm 8 bit `x_pos_in_w_cycle` trong `iact_stream_constructor` (lỗi #19, mục 8b).

**Kiểm chứng:**

| Kiểm tra | Kết quả |
|---|---|
| Lint Verilator 5.020 | fpga 470 → 468, parallel 38 → 36: hết 2 cảnh báo `WIDTHEXPAND` ở cổng của `PE.v`, **0 cảnh báo mới** (bản gốc upstream sẽ sinh thêm 1 cảnh báo ở phép gán 6 → 8 bit; phần mở rộng 0 tránh được). Đã hạ baseline |
| Elaborate riêng `PE` với `WGHT_ADDR_ADDR` = 8, 16, 64 (cả hai nhánh `generate`) | Icarus và Verilator: 0 lỗi |
| `2c8c324` (chỉ đổi tên): netlist Yosys của `OpenEye_Parallel` (48 PE, `proc; flatten; opt_clean`) trước / sau | **Giống hệt từng byte** (198.236 cell): các khối đổi tên không khai báo tín hiệu nào |
| **Lockstep PE trong hệ thống**: mỗi PE mang theo một bản PE cũ (`3717d12`) chạy song song, cùng đầu vào, so 8 đầu ra bằng `!==` ở mỗi sườn xuống clock; chạy **cả 125 test** | **5.708 PE (mảng từ 8 đến 128 PE), tất cả OK, 0 sai khác, 36.363.008 PE-chu kỳ** |
| Như trên, 23 test GEMM/Dense chạy lại với `OPENEYE_SKIP_FC_WRITE_CHECK=1` | 23/23 PASS; 592 PE, 607.944 PE-chu kỳ, 0 sai khác |
| Đối chứng: PE mới bị "đột biến" (`filters_reg_M0 + 1`) | Bị bắt ngay (`PE LOCKSTEP MISMATCH`, FAIL): phép so phân biệt được |
| Kết quả các bộ test | Giống hệt trước: Conv 34/34; GEMM/Dense 40/23 (23 do bộ kiểm tra FC, lỗi #5); MNIST/ngẫu nhiên 15 passed + 4 xfailed; ca mốc 9/9 |
| 9 ca mốc (`tools/run_profile.py --compare doc/perf/baseline_2026-10-15`) | 9/9 PASS, **0 chu kỳ và 0 word DMA** chênh lệch |
| Vivado toàn thiết kế, 4 ns (`doc/synth/2026-10-21_route4ns_up3_zu7ev/`) | 0 CRITICAL; Synth 8-689: 2 → 0, không loại cảnh báo nào khác thay đổi; **FF +101 (+2 mỗi PE)**, LUT −209 / −80; BRAM/URAM/DSP không đổi; WNS +0,219 / +0,070 ns, đạt 250 MHz |
| Tài nguyên PE theo Yosys | **Không dùng được**: Yosys elaborate sai `PE.v:829–830` (lỗi #20 mới), nên hai bản cho netlist giống nhau, không chứng minh được gì |

**Ưu và nhược điểm, trước và sau:**

| | Trước (`3717d12`) | Sau |
|---|---|---|
| Đúng chức năng ở các cấu hình đã thử | Đúng | Đúng; lockstep chứng minh hành vi không đổi ở bất kỳ chu kỳ nào (125 + 23 test, thêm Dense K = 512) |
| Bộ đếm ≥ 32 (đã gặp ở Dense K = 512, tới 64) | Bị cắt còn 5 bit; ở các trường hợp đã thử vẫn không đổi kết quả (lockstep 0 sai khác), nhưng phụ thuộc may rủi vào giá trị | Đúng độ rộng tới 64 word (hết dải của SPad địa chỉ) |
| Lint / Vivado | 2 `WIDTHEXPAND` + 2 Synth 8-689; tên khối psum sai | Sạch hơn (−2 / −2), tên đúng |
| Tài nguyên, tần số | 39.184 FF, 64.050 LUT, WNS +0,097 ns | +101 FF (+0,26 %), −80 LUT, WNS +0,070 ns (dao động placement), vẫn 250 MHz |
| Chu kỳ, DMA | — | Không đổi |
| Đồng bộ với upstream | Lệch 3 commit | Lệch ít hơn; `-x` giúp merge sau này nhận ra; phần mở rộng 0 là khác biệt riêng nhỏ (1 khối `generate`) |

### Sửa lỗi #19: Dense có K > 512 input (2026-10-21, được bạn đồng ý)

Chi tiết: `doc/experiments/2026-10-21_bug19_dense_k512.md` (mục 1–6 là điều tra, mục 8 là bản sửa và kiểm chứng).

**Hai chỗ sửa** (thêm comment giải thích tại chỗ), không đổi Python:

| File | Trước | Sau | Vì sao |
|---|---|---|---|
| `hdl/iact_stream_constructor.v:218` | `reg [ 8-1:0] x_pos_in_w_cycle;` | `reg [12-1:0] x_pos_in_w_cycle;` | Bộ đếm vị trí trong luồng (pixel với Conv, **cặp activation** với FC) quyết định cặp nào được ghi vào RAM iact. 8 bit quay vòng ở cặp 256 = activation 512, nên từ đó cặp không còn nằm trong cửa sổ ghi (`x_range_lower_bound` 12 bit) và **không bao giờ được ghi**; chỗ của nó nhận số 0 đệm. Nay rộng bằng `x_range_lower_bound`, `x_pos_inc`, `iact_x_add_up` (12 bit) |
| `hdl/OpenEye_FPGA.v:2163` (`CONVERT_IACT`) | `if ((current_x >= 0) & ...` | `if ((fully_connected_layer \| (current_x >= 0)) & ...` | `current_x` là số có dấu 12 bit, đếm activation; từ 2048 nó đọc ra âm nên phép so có dấu loại bỏ mọi activation ≥ 2048 (chặn FC 3136 của MNIST). FC không có padding (`padding_x = 0`), `current_x` bắt đầu ở 0 và chỉ tăng, nên phép so dấu chỉ có ý nghĩa với padding của Conv; Conv giữ nguyên điều kiện cũ |

Rào cản thứ hai được dự đoán từ việc đọc code và được kiểm chứng **trước** khi sửa: chỉ với chỗ sửa thứ nhất, K = 520, 784, 2046 đúng, K = 2050 sai và
output khớp chính xác (10/10) giả thuyết "activation ≥ 2048 bị coi là 0" (ngưỡng 2046 hay 2044 đều không khớp).

Không mở rộng `x_start` và `iact_converter_x` (vẫn 8 bit): với FC chúng chỉ mang độ lệch của từng hàng (đo được 0 và 18), mở rộng thì phải đổi cách đóng gói
word tham số của bộ chuyển đổi; chúng chỉ là giới hạn với Conv có ảnh rộng hơn 255 pixel.

**Kiểm chứng:**

| Kiểm tra | Kết quả |
|---|---|
| Loạt K, 10 output, dữ liệu ngẫu nhiên, từng output so với numpy | **14/14 PASS, 0 output sai**: K = 64, 256, 510, 512, **513, 520, 576, 784** (Dense của mạng MNIST), **1024, 2046, 2048, 2050, 3136** (FC của MNIST), **4032** |
| Lockstep `iact_stream_constructor` (bản cũ `ef709b9` chạy song song trong mọi constructor, so 4 đầu ra mỗi chu kỳ), 125 test | **499 constructor OK, 0 sai khác**, 3.051.186 constructor-chu kỳ; 23 test GEMM chạy lại với bộ kiểm tra FC tắt: 60 constructor OK, 23/23 PASS |
| Đối chứng: constructor đột biến (`>=` → `>` ở cửa sổ ghi) | Bị bắt ngay (`iact_data_o`, FAIL) |
| Giám sát FC (`fc_guard_monitor.v`, module root riêng): chu kỳ có `fully_connected_layer = 1` và `current_x < 0`, trường hợp duy nhất điều kiện cũ/mới khác nhau | 57.283 chu kỳ FC trong 125 test, 11 chu kỳ có `current_x < 0`: mỗi chu kỳ ở một test Conv hai layer, khi `fully_connected_layer` lên 1 đúng một chu kỳ lúc nạp cấu hình layer sau (chạy lại có theo dõi trạng thái: luôn là `GET_PARAMETERS`, **0 chu kỳ trong `CONVERT_IACT`**, trạng thái duy nhất đánh giá điều kiện). Vậy điều kiện cũ và mới cho cùng kết quả ở mọi chu kỳ của bộ hồi quy. Lượt chạy lại GEMM: 24.390 chu kỳ FC, 0 chu kỳ âm |
| Kết quả các bộ test | Giống hệt trước: Conv 34/34, GEMM/Dense 40/23 (23 do bộ kiểm tra FC, lỗi #5), MNIST/ngẫu nhiên 15 passed + 4 xfailed, ca mốc 9/9 |
| 9 ca mốc (`run_profile --compare`) | 9/9 PASS, **0 chu kỳ, 0 word DMA** chênh lệch |
| Lint Verilator | fpga 468 → 463: hết **5 cảnh báo `WIDTHEXPAND`** so `x_pos_in_w_cycle` 8 bit với giá trị 12 bit (Verilator đã chỉ đúng vào lỗi này từ trước), 0 cảnh báo mới; đã hạ baseline |
| Vivado toàn thiết kế, 4 ns (`doc/synth/2026-10-21_route4ns_fix19_zu7ev/`) | 0 CRITICAL, danh sách cảnh báo giống hệt; FF +24, LUT −60 (mỗi constructor +3 FF, +10 LUT); BRAM/URAM/DSP không đổi; WNS +0,199 / +0,073 ns, đạt 250 MHz; đường găng không đổi |

**Ưu và nhược điểm, trước và sau:**

| | Trước | Sau |
|---|---|---|
| Dense K ≤ 512 | Đúng | Đúng (lockstep chứng minh hành vi constructor không đổi ở mọi test hiện có) |
| Dense 512 < K ≤ 2048 (Dense 784 → 10) | **Sai**: activation ≥ 512 thành 0 | Đúng |
| Dense K > 2048 (FC 3136 → 10) | **Sai**: activation ≥ 512 thành 0 | Đúng, tới K = 4032 (giới hạn mới: trường cấu hình 12 bit `iact_size_c` = K đã đệm ≤ 4095) |
| Cách tránh bằng phần mềm (chia K ≤ 512, cộng psum trên CPU) | Cần thiết, tốn thêm một lần nạp weight/iact và một lần đọc kết quả cho mỗi khối | Không cần |
| Tài nguyên, tần số | 39.285 FF, 63.970 LUT, WNS +0,070 ns | +24 FF (+0,06 %), −60 LUT, WNS +0,073 ns, vẫn 250 MHz |
| Chu kỳ, DMA của các layer hiện có | — | Không đổi |
| Lint | 5 cảnh báo độ rộng ở `x_pos_in_w_cycle` | Sạch |
| Còn lại | — | Lỗi #19b (32 output, K ≥ 508) và #21 (> 32 output) không thuộc bản sửa này; `x_start`/`iact_converter_x` 8 bit vẫn giới hạn Conv rộng > 255 pixel |

### Lỗi #17: đệm input 1 channel thành 2 channel bằng Python (2026-10-22, không sửa RTL)

> **Từ 2026-11-04 lỗi #17 đã sửa trong RTL** (mục "Sửa #37, #17" bên dưới): workaround này tắt mặc định, `OPENEYE_PAD_CHANNELS=1` bật lại để so
> với số đo cũ. Phần dưới là ghi chép lúc làm workaround.

Chi tiết: `doc/experiments/2026-10-22_bug17_channel_pad.md`, script `doc/experiments/2026-10-22_bug17/`.

**Lỗi:** bộ ghi 1 channel của `iact_stream_constructor.v` tính địa chỉ RAM chỉ từ hàng và cột, bỏ qua các lượt x. Ảnh cần hơn một lượt x
(`iact_x_line_repetitions > 1`; với 2×2 cluster là ảnh rộng > 16, ví dụ MNIST Conv1 28×28×1) cho output sai. Từ 2 channel trở lên, RTL dùng bộ ghi
nhiều channel, bộ này xử lý đúng các lượt x.

**Cách làm (phía host, RTL giữ nguyên):** layer 0 là Conv 1 channel cần hơn một lượt x thì chạy như Conv 2 channel:

| | Channel 0 | Channel 1 (đệm) |
|---|---|---|
| Activation | ảnh thật | toàn 0 |
| Weight | của model | toàn 1 (giá trị nào khác 0 cũng được, xem lỗi #22 bên dưới) |

Mọi tích của channel 1 là `0 × 1 = 0`, nên mỗi output **bằng đúng** kết quả 1 channel (cộng số nguyên, không làm tròn).
- `channel_pad.needs_padding`: đúng điều kiện của lỗi #17 (`Convolution2D`, `channels == 1`, `iact_x_line_repetitions > 1`).
- `ChannelPaddedConv2D` bọc layer Keras: `input.shape`/`kernel.shape` có 2 channel, kernel thêm một channel 0 (model float không đổi); mọi thuộc tính
  khác lấy từ layer gốc. Testbench tính lại tham số layer từ model đã bọc, nên mọi giá trị suy ra (độ dài stream, giới hạn vòng lặp) là của 2 channel.
- `fill_padding_channels`: sau `DRAMContents` và mọi hook dữ liệu, đặt activation của channel đệm = 0, weight = 1; stream và tham chiếu tạo sau đó.
- Bật mặc định; `OPENEYE_PAD_CHANNELS=0` tắt (tái hiện lỗi #17). Chỉ đệm layer 0 (layer duy nhất nhận activation từ DMA qua bộ chuyển đổi).
- Profiler ghi `pad_channels` vào thông tin layer: bảng theo layer in `Conv 28x28x1+1pad->32`, hiệu suất bus chỉ tính channel thật.

**Kiểm chứng** (2×2 cluster, DMA 64 bit; "= numpy": `tools/verify_conv_output.py` tính lại layer từ số nguyên DUT nhận và so từng word):

| Layer | Lượt x | Không đệm | Có đệm |
|---|---:|---|---|
| Conv 20×8×1 → 8, ngẫu nhiên | 2 | FAIL: 8/8 feature map sai | **PASS**, 1.280/1.280 output = numpy |
| Conv 28×28×1 → 32 (MNIST Conv1), ngẫu nhiên | 2 | FAIL: treo 20.000 chu kỳ rồi 32/32 sai | **PASS**, 25.088/25.088 = numpy |
| Conv 28×28×1 → 32, ramp + kernel bất đối xứng (`test_mnist_conv`) | 2 | FAIL (giữ làm `xfail(strict)`: `test_mnist_conv1_without_padding`) | **PASS**, 25.088/25.088 = numpy |
| Conv 40×8×1 → 8, ngẫu nhiên | 3 | FAIL: 8/8 sai | **PASS**, 2.560/2.560 = numpy |
| `MNIST_REAL` 1 channel, 6 layer nối tiếp (`model_mnist_real_c1`) | 2 | FAIL ở bộ đệm iact sau Conv1 | **PASS** mọi lần kiểm tra bộ đệm giữa layer và output |

Không bị đệm (không đổi): `test_conv_const.py` 34/34 PASS và test mapping 8 PASS + 2 xfail (3 channel, như trước), không ca nào bị đệm (các ca 1 channel đều rộng 8);
9 case đo một layer 0 chu kỳ lệch so với `baseline_2026-10-22`. Dữ liệu dump xác nhận
channel 1 toàn 0, weight channel 1 toàn 1. Unit test `test/test_channel_pad.py` (10 test): hình dạng layer bọc, Keras trên `[x, 0]` bằng đúng Keras trên `x`
(số nguyên), điều kiện đệm với `LayerParameters` thật (rộng 8/16 không đệm, 28/40 đệm, 2 channel không đệm), `OPENEYE_PAD_CHANNELS=0`, dữ liệu channel đệm.
Các ô đệm khác 0 trong word output (3.584 ô ở 28×28) cũng có ở layer 2 channel thật cùng kích thước: là hiện tượng của lỗi #9, không do việc đệm.

**Chi phí** (MNIST Conv1 đứng riêng; số 1 channel lấy từ lần chạy không đệm, kết quả sai):

| | 1 channel (sai) | Có đệm | Chênh |
|---|---:|---:|---:|
| Word DMA nạp iact | 100 | 196 | +96 |
| Word DMA nạp weight | 120 | 480 | +360 |
| Chu kỳ tính toán | 9.622 | 9.638 | +16 |
| Tổng chu kỳ | 39.645 | 40.117 | **+472 (+1,2 %)** |

Trong cả model: Conv1 32.980 chu kỳ (ít hơn 2.611 so với channel thứ hai ngẫu nhiên thật, vì activation 0 được bỏ qua), cả model 241.250 chu kỳ = 965 µs.
Weight đệm ±1 thay vì 1 cho số chu kỳ như nhau. Ưu điểm: không đổi RTL, đúng từng bit, tự động. Nhược điểm: +1,2 % chu kỳ Conv1 và +456 word DMA; RTL vẫn còn
lỗi (bật `OPENEYE_PAD_CHANNELS=0` sẽ thấy); host thật (driver CPU) sau này cũng phải đệm như vậy.

### Lỗi #22: weight bằng 0 làm sai định dạng weight nén (phát hiện 2026-10-22, điều tra và sửa 2026-10-24, chỉ Python)

Chi tiết: `doc/experiments/2026-10-24_bug22_weight_encoding.md`, công cụ `doc/experiments/2026-10-24_bug22/`.

**Đính chính phần viết ngày 2026-10-22:** mapper Conv **có nén số 0** (lớp con `ConvWghtStreamMapper` ghi đè hàm dạng dày của lớp cha), "phía PE cũng sai"
thực ra là các cơ chế F1/F2/F9 trong `data_pipeline_wght.v` (không phải vòng MAC), và không cần cặp số 0: một số 0 ở filter cuối của một cột là đủ, nên ước
lượng "p²" là sai.

**Định dạng (theo cách RTL giải mã):** mỗi word 24 bit có 2 entry `{overhead 4 bit, giá trị 8 bit}`; weight của một PE chia thành cột (mỗi vị trí iact = (kernel x,
channel) một cột gồm `M0` filter). Mapper bỏ weight 0, entry khác 0 kế tiếp ghi số 0 đã bỏ vào overhead. `data_pipeline_wght` đếm "vị trí" (mỗi entry
`overhead + 1`, ô đệm `(0,0)` tính 1), đủ `M0` vị trí thì kết thúc cột và ghi con trỏ cột (số word dữ liệu) vào SPad địa chỉ; PE đọc cột k từ word `addr[k-1]`
đến `addr[k]`.

**6 cơ chế hỏng** (đều tái hiện trên RTL):

| | Cơ chế | Phía |
|---|---|---|
| F1 | Cột rỗng (mọi filter của một vị trí iact bằng 0): RTL chỉ sang cột tối đa 1 lần mỗi word, không tạo được cột rỗng → các cột sau lệch, thiếu con trỏ cuối | định dạng không khớp |
| F2 | Cột có số entry lẻ được thêm ô đệm `(0,0)`: RTL tính ô đệm là 1 vị trí, mapper thì không mà còn mang mọi số 0 cuối cột sang overhead của cột sau → đếm trùng 1 vị trí, cột sau lệch 1 filter | định dạng không khớp |
| F3 | Hơn 15 số 0 liên tiếp không vừa overhead 4 bit | định dạng không khớp |
| F7 | Bộ ghép stream gửi cho mọi PE số word bằng PE (0,0,0); khi nén, PE dài hơn bị cắt | Python |
| F8 | `SKIP_ZERO_WORDS` bỏ các word 0 ở đuôi → stream weight ngắn hơn. `layer_mapper` đặt `trans_cycles_wght` theo stream thực tế nên stream không lệch, nhưng mỗi PE vẫn nhận `used_wght_per_PE/2` word (độ dài dày) từ bộ đệm weight → khối PE không còn khớp dữ liệu (đính chính: ngày 24/10 sáng ghi nhầm là RTL lấy word bias làm weight) | Python |
| F9 | RTL reset địa chỉ ghi SPad dữ liệu ở mỗi word 0, và PE nhận thêm 1 word sau khối của nó; khối có đuôi word 0 thì word thừa (dữ liệu thật ở layer nhiều lượt truyền) ghi đè địa chỉ 0 và đặt `second_spad_words = 2` → PE treo ở `CALCULATE_PSUM` | định dạng không khớp |

**Bằng chứng:** probe dump mọi lần ghi SPad weight của 48 PE với giá trị weight duy nhất (đối chứng không có số 0: 0/48 PE sai; channel 1 toàn 0: con trỏ
`[4, 5, 8, 9, 12]` thay vì `[4, 4, 8, 8, 12, 12]`); **mô hình chu kỳ Python của `data_pipeline_wght` khớp RTL từng lần ghi ở 336 lần nạp weight** (7 lượt chạy),
tái hiện cả `second_spad_words = 2` của ca treo; bộ kiểm tra offline (mapper thật → bộ ghép stream → mô hình → cách PE đọc) dự đoán đúng kết quả RTL ở mọi ca
đã mô phỏng. Quét offline 6 kích thước layer (gồm 3 Conv MNIST) × 9 mẫu số 0: bộ mã hóa hiện tại sai ở mọi mẫu trừ "filter 0 bằng 0" (mỗi cột một số 0 ở đầu).

**Ảnh hưởng thật:** model MNIST int8 đã huấn luyện (`doc/demo_notebooks/mnist_quantized_model.tflite`, ~1 % weight bằng 0): Conv2 140/384, Conv3 116/384 lần
nạp weight giải mã sai; mô phỏng RTL Conv2/Conv3 với weight này treo. Các test hiện có không thấy vì `DRAMContents` thay weight 0 bằng ±1
(`test_conv3x3_sparse` PASS vì ở cấu hình đó RTL nhận đúng 24 word mỗi PE, bằng độ dài dữ liệu nén của mẫu bàn cờ).

**Bản sửa (chỉ Python, đưa vào `src/` ngày 2026-10-24 sau khi bạn đồng ý):** bộ mã hóa mới chỉ sinh định dạng RTL giải mã đúng: mỗi cột tự kết thúc ở filter
`M0-1` (entry 0 tường minh khi cần, cột rỗng thành `(0, M0-1)`), không mang số 0 sang cột sau, cắt chuỗi số 0 dài bằng `(0, 15)`, không bao giờ tạo word toàn 0,
lấp phần còn lại của khối PE bằng word `[(0,0), (0,1)]` (giá trị 0, chỉ tạo cột PE không đọc), gửi đủ độ dài (tắt `SKIP_ZERO_WORDS`).

| Kiểm chứng bộ mã hóa mới | Kết quả |
|---|---|
| Offline: 6 kích thước × 9 mẫu số 0 (3 seed), weight MNIST thật | 0 lần nạp sai (bộ hiện tại: sai ở mọi mẫu trừ 1) |
| Weight không có số 0 (8 kích thước, 30 – 15.360 word DMA) | Stream **giống hệt từng word** bộ hiện tại → mọi test và mốc không đổi |
| RTL: 20×8×2→8 (30 %, 90 %, channel 1 = 0), 8×4×8→16 (30 %, 50 %, không 0), 8×4×4→32 (30 %, cột rỗng 16 filter), Conv2 MNIST với 30 % số 0, test thưa có sẵn `test_conv3x3_sparse` | **PASS** cả 10 |
| RTL: MNIST Conv1 / Conv2 với weight int8 đã huấn luyện | **PASS** (Conv2: bộ hiện tại treo) |
| RTL: MNIST Conv3 với weight đã huấn luyện | **3.136/3.136 output = numpy** (kiểm tra stream vẫn fail do lỗi #9 như trước); bộ hiện tại treo |
| Chi phí | Word DMA weight **không đổi** (độ dài khối do cấu hình RTL cố định); chu kỳ tính giảm nhẹ khi có số 0 (8×4×8→16: 1.054 → 1.001 ở 30 %, 963 ở 50 %) |

Bản nháp đầu (chưa có word lấp đầy) PASS ở layer 1 lượt truyền nhưng treo ở layer nhiều lượt; snapshot trạng thái PE cho thấy `second_spad_words_wght = 2`,
mô hình truy ra F9. **Hướng phía RTL** (cần bạn đồng ý, chưa làm): cho phép cột rỗng, sửa nghĩa ô đệm, bỏ reset địa chỉ ở word 0; độ dài stream weight thay
đổi được thì weight 0 còn tiết kiệm được cả DMA.

**Đưa vào `src/` (2026-10-24):** `src/open_eye/conv_wght_encoding.py` (bộ mã hóa), `ConvWghtStreamMapper.write_wght_data_storage` lấy cột từ bố cục dày
(`write_dense_wght_data_storage` = vòng lặp cũ, giữ số 0 tại chỗ) rồi mã hóa, `SKIP_ZERO_WORDS = False` cho Conv; `DRAMContents` **không còn thay weight
Conv bằng 0 thành ±1** (Dense, Depthwise giữ như cũ); hook `OPENEYE_TFLITE_CONV=<file>:<tensor>` nạp weight Conv đã huấn luyện từ TFLite
(`DRAMContents.load_conv_weights_tflite`); `src/open_eye/wght_pipeline_model.py` (mô hình chu kỳ đã khớp RTL) cho unit test.

| Kiểm chứng sau khi đưa vào | Kết quả |
|---|---|
| Stream của mapper mới so với mapper đã commit, weight không có số 0 (8 kích thước) | Giống hệt từng word |
| Stream của mapper mới so với bộ mã hóa đã chạy RTL, 27 ca có số 0 (gồm weight MNIST thật) | Giống hệt từng word |
| `test/test_conv_wght_encoding.py` (39 test: quy tắc mã hóa, mô hình RTL đọc lại đúng mọi cột với 0–100 % số 0, mapper thật qua mọi PE và mọi lượt truyền, bố cục cũ hỏng trong mô hình) | Pass |
| Hồi quy RTL: `test_conv_const` 34, `test_mnist_layers` 26 (mapping, Conv MNIST, 9 test ngẫu nhiên nay có 1,4–5,3 % weight bằng 0, **3 test mới với weight MNIST đã huấn luyện**), 2 ca `test_conv3x3_sparse` | 56 pass, 5 xfail như trước (3 channel ×2, #17 không đệm, #9 Conv3 ×2); 1 fail có từ trước (#23) |
| MNIST với weight đã huấn luyện (`test_trained_mnist_conv`) | Conv1 25.088/25.088, Conv2 12.544/12.544, Conv3 3.136/3.136 output = numpy (Conv3 xfail do #9 ở kiểm tra stream) |
| `run_profile` 12 case | 9 case một layer 0 chu kỳ lệch; 3 case model −13 … −579 chu kỳ, DMA không đổi; mốc mới `doc/perf/baseline_2026-10-24/` |

Hạn chế đã biết: cột dài hơn 16 filter không giải mã được ở RTL (thanh ghi đếm vị trí 5 bit), mapper hiện không tạo cột như vậy; bộ mã hóa dừng với lỗi
nếu một cột không mã hóa được mà không sinh word 0 (chỉ xảy ra khi số filter mỗi cột lẻ).

### Điều tra lỗi #26: Dense nối tiếp Dense không ghi kết quả vào bộ đệm (2026-10-24, không sửa RTL)

**Triệu chứng.** Mọi model có hai Dense liền nhau trên chip (MLP, `Dense 1568→32 → Dense 32→10` của mạng paper) cho kết quả cuối sai, ở mọi cấu hình,
mọi K, N đã thử. Sau Dense đầu, bộ đệm iact **vẫn chứa input của chính Dense đó** (ví dụ `D_16_8_10`: word 0 = 8 activation đầu vào, không phải 8 output
đã lượng tử); `TRACE_RAM_WRITES` chỉ thấy đúng 1 lần ghi RAM trong cả layer (nạp input qua DMA). Ghi chú cũ "4 byte thấp/cao nằm ở 2 word" là đọc nhầm.

**Phần đúng.** Psum của Dense đầu **đúng** trong bộ đệm psum: filter `f = r·CX·P + c·P + a` nằm ở cột cluster `c`, hàng 0, GLB 0, địa chỉ `r·P + a`
(`P = used_psum_per_PE`, `CX` = số cột cluster, `r` = lượt psum), giá trị = psum + bias; bộ lượng tử cũng đúng. Thí nghiệm cô lập: ghi sẵn ảnh bộ đệm
đúng sau Dense đầu (`B26_INJECT`) thì 4 chuỗi (16→8→10, 64→8→10, 256→32→10, MLP 3 layer) đều ra kết quả cuối đúng: **chỉ pha ghi ngược hỏng**.

**Nguyên nhân (3 tầng).**

| | Ở đâu | Điều gì sai |
|---|---|---|
| W1 | Python: `fsm_psum_limit = used_psum_per_PE + 3` | `SEND_PSUM_TO_IACT` chỉ dài 8 chu kỳ, main FSM bắt đầu nhận ở chu kỳ ≥ 7 nên nhận 1 giá trị; khi FSM psum về nghỉ, bộ đếm lưu trữ = 0 nên thoát ngay, **không ghi RAM lần nào** |
| W2 | Python: vòng đọc psum của Dense | Vòng chọn cluster (`psum_pagu_cs_*`) không được đặt (= 0), vòng địa chỉ đếm 0, 1, 2, ...: mỗi chu kỳ đọc 4 GLB của cluster 0 (bố cục conv: 4 GLB = 4 pixel) trong khi kết quả Dense chỉ ở GLB 0 của mỗi cột; cột 1 (nửa số filter) không bao giờ được đọc |
| W3 | RTL: `RECEIVE_PSUMS_TO_IACT` | Bộ đóng gói chuyển vị 4 lane × 4 chu kỳ thành nhóm theo pixel (conv) và chỉ giữ nhóm có `x_pos < iact_size_x`, `x_pos` quay về 0 theo `iact_x_add_up`. Với Dense chỉ lane 0 có dữ liệu; muốn giữ "lane 0 của mọi nhóm" phải đổi `iact_x_add_up`, mà bộ chuyển đổi iact FC đang cần giá trị này (= K) |

**Lịch sử:** ghi ngược FC từng có ở upstream và bị bỏ để giảm LUT: `1320759` (14/7) comment-out bộ đóng gói FC, `8350a00` (20/7) thay mẫu đọc viết tay
bằng vòng đếm tổng quát và mất nhánh FC; `e8f39ad` (3/9) thêm ca MLP nhưng chưa bao giờ cấu hình vòng ghi ngược cho Dense (mục 2).

**Python thuần có sửa được không?** Phía đọc **có**: đặt vòng chọn cluster `[P−1, CX−1, 0]`/`[0, 1, 0]`, vòng địa chỉ `[P−1, CX−1, R−1, 255, 0]`/`[1, 0, P, 0, 0]`
thì bộ lượng tử ra đúng thứ tự f0, f1, ... (đã thấy trong trace). Phía đóng gói **không**: `iact_size_x = 1` an toàn với Dense (bộ chuyển đổi FC dùng
`fc_size_reg`), nhưng đặt `iact_x_add_up = 4` làm sai psum của chính layer (filter 0: 1025 thay vì 1610); giữ `iact_x_add_up = K` thì cứ `⌈K/4⌉` nhóm mới
giữ 1 nhóm và pha flush nhân bản nó (hàng bộ đệm thành f0..f3 lặp 8 lần). Cách vòng đường khác: Dense đầu gửi kết quả ra host, host lượng tử rồi gửi lại
làm input của Dense sau (không sửa RTL, tốn 1 word DMA 64 bit mỗi output + `⌈N/8⌉` word vào + độ trễ host; testbench phải hỗ trợ output giữa chừng).

**Đề xuất (sửa RTL 1 dòng; đã được bạn đồng ý và áp dụng, xem mục "Sửa lỗi #26" ngay sau).** Trong `RECEIVE_PSUMS_TO_IACT` của `OpenEye_FPGA.v`:

```verilog
-              if (iact_to_psum_x_pos_counter >= iact_x_add_up - 1) begin
+              if ((iact_to_psum_x_pos_counter >= iact_x_add_up - 1) | fully_connected_layer) begin
```

cộng phần Python cho Dense giữ kết quả trên chip (`send_values_out = 0`): `iact_size_x` = 1 (chỉ giữ lane 0), vòng đọc như trên,
`fsm_psum_limit = 8 + 8·IACT_RAM_CELLS·⌈R·CX·P / (8·IACT_RAM_CELLS)⌉` (kết thúc ngay sau nhóm cuối của một hàng bộ đệm đầy, để pha flush dừng ngay không
nhân bản nhóm), và kiểm tra bộ đệm của testbench chỉ so N byte đầu (các byte đệm sau N nhân với weight 0 ở layer sau). Conv không đổi
(`fully_connected_layer = 0`); diện tích: 1 cổng OR.

**Kiểm chứng bằng giả lập (không sửa RTL):** testbench ghi `x_pos = 0` vào thanh ghi ngay sau mỗi lần nạp nhóm của layer FC, đúng giá trị dòng RTL mới sẽ
lưu (`B26_EMU=1`), cùng các thanh ghi Python ở trên:

| Model | Cấu hình | Kiểm tra bộ đệm | Kết quả cuối |
|---|---|---|---|
| D 16→8→10, 64→8→10, 256→32→10, 1568→32→10, MLP 6→32→16→4 | mặc định (2×2 cluster, `NUM_GLB_PSUM=4`) | PASS | PASS |
| D 64→10→10 | mặc định | byte 12–15 khác (byte đệm, xem trên) | PASS |
| D 16→64→10 (2 lượt psum) | `QUANT_AMOUNT=64` | PASS | PASS |
| D 64→8→10 / 64→8→10 / 64→32→10 / MLP | `NUM_GLB_PSUM=2` / `CLUSTER_ROWS=1` / `CLUSTER_ROWS=4` / `CLUSTER_ROWS=4` | PASS | PASS |
| **Mạng paper** (7 layer) | CR=2, X=4, Y=3 | **PASS cả 6 lần kiểm tra** | **PASS** |
| Mạng paper | CR=1, X=4, Y=3 | sai sau layer 5 | FAIL do lỗi tính #19b: Dense 1568→32 đứng một mình ở CR=1 cũng sai 32/32 |

Chi phí: pha ghi ngược 146 chu kỳ cho N = 32 (0,9 % layer 1568→32), không tốn word DMA nào. Không có dòng RTL thì các thanh ghi Python trên không đủ.

**Phát hiện thêm:** lỗi #21 (Dense N > 32, chỉ P output đầu đúng) nằm ở bước đọc kết quả cuối, không ở phép tính: Dense 16→64 làm layer cuối sai 48/64,
nhưng cùng layer đó ghi ngược trên chip cho đủ 64 giá trị đúng.

Chi tiết: `doc/experiments/2026-10-24_bug26_dense_writeback.md`, công cụ `doc/experiments/2026-10-24_bug26/` (`run_dense.py`, `probe_dense.py`).

### Sửa lỗi #26: ghi ngược Dense → Dense (2026-10-24, được bạn đồng ý)

Làm đúng đề xuất ở mục trên.

| File | Thay đổi |
|---|---|
| `hdl/OpenEye_FPGA.v` (`RECEIVE_PSUMS_TO_IACT`) | **Dòng RTL duy nhất:** `if ((iact_to_psum_x_pos_counter >= iact_x_add_up - 1) \| fully_connected_layer)`: với layer FC bộ đếm `x_pos` quay về 0 ở mỗi nhóm, nên chỉ nhóm của lane 0 (GLB 0) được ghi, đúng thứ tự filter |
| `src/open_eye/layer_parameters.py` | `configure_fc_writeback` (gọi khi Dense có `send_values_out = 0`): `fsm_psum_limit = 8 + 8·IACT_RAM_CELLS·⌈R·CX·P / (8·IACT_RAM_CELLS)⌉`, vòng địa chỉ `[P−1, CX−1, R−1, 255, 0]` / `[1, 0, P, 0, 0]`, vòng chọn cluster `[P−1, CX−1, 0]` / `[0, 1, 0]` |
| `src/open_eye/dense_mapper.py` | Thanh ghi `iact_size_x` = 1 cho Dense giữ kết quả trên chip (Dense cuối giữ nguyên `⌈K/2⌉`); thanh ghi này chỉ bộ ghi ngược đọc |
| `src/open_eye/rtl_test_utils.py`, `test/cocotb_fpga/OpenEye_FPGA_tb.py` | Sau một layer Dense, kiểm tra bộ đệm chỉ so N output thật (`valid_values`); các byte đệm phía sau nhân với weight 0 ở layer sau |
| `src/open_eye/data_create.py` | Ca model `DENSE_CHAIN_<K>_<N1>_<N2>...` |
| `test/cocotb_fpga/test_dense_chain.py` (mới) | 11 chuỗi Dense / cấu hình qua RTL |
| `test/test_fc_writeback.py` (mới) | Mô hình chu kỳ của hai FSM ghi ngược với thanh ghi của `configure_fc_writeback`: 108 cấu hình (N 4–128, 1/2/4 cột cluster, `IACT_RAM_CELLS` 4/8, `WRITEBACK_WORDS` 2/4) + 2 hành vi đã thấy ở RTL |

Conv (`fully_connected_layer = 0`) và Dense cuối (thanh ghi như cũ) không đổi gì.

**Kiểm chứng:**

| Kiểm tra | Kết quả |
|---|---|
| `test_dense_chain.py` (RTL, mới) | **11/11 PASS** (bộ đệm đúng N output + kết quả cuối đúng) |
| Đối chứng âm: RTL cũ (`142ee6c`) + Python mới | FAIL đúng như dự đoán (hàng bộ đệm = `f0..f3` lặp lại): dòng RTL là cần thiết, test bắt được lỗi |
| `test/test_fc_writeback.py` (mô hình chu kỳ, mới) | **110/110 PASS**; mô hình tái hiện đúng 2 hành vi đã thấy ở RTL; `fsm_psum_limit` có biên khoảng ±3 chu kỳ |
| Unit test Python | 239 pass, 11 fail (đều là lỗi có từ trước ở `test_dense_output.py`) |
| Hồi quy RTL 128 test (`OPENEYE_SKIP_FC_WRITE_CHECK=1`) | **123 PASS + 5 xfail, 0 FAIL**, giống hệt trước khi sửa: `test_conv_const` 34/34, `test_mnist_layers` 21 + 5 xfail, `test_gemm_layer` 63/63, `test_pooling` 4/4, `test_nets` (LAYER=MNIST) 1/1 |
| `run_profile` 12 case so với `baseline_2026-10-24` | 12/12 PASS, **0 chu kỳ và 0 word DMA lệch** |
| Lint | `parallel` 36, `fpga` 463: **0 mới** |
| Bảng 3 chạy lại (16 cấu hình, `doc/perf/paper_table3_2026-10-24_fix26.md`) | X = 4: **7/8 cấu hình PASS cả 7 layer** (trước: cả 8 hỏng sau layer 5). Còn CR 1 X 4 Y 3 hỏng sau layer 5 = lỗi tính #19b ở `CLUSTER_ROWS=1`. X = 2: như cũ (#25 từ layer 1) |
| Chi phí trên mạng paper | Pha ghi ngược của layer 5: 109–131 → 130–146 chu kỳ; cả mạng **+15 đến +28 chu kỳ** trên 62.600–206.400 (≤ 0,03 %); layer 0–4 giống hệt |
| Vivado tổng hợp + place & route ở 4 ns (`doc/synth/2026-10-26_route4ns_fix26_zu7ev/`) | **0 ERROR, 0 CRITICAL WARNING**, cảnh báo giống mốc fix19; LUT −4 / FF −4 sau tổng hợp; BRAM/URAM/DSP không đổi; WNS +0,199 / **+0,028 ns**, đạt 250 MHz; đường găng (URAM weight → PE) không liên quan phần sửa |

### Điều tra lỗi #25: ghi ngược của Conv khi `NUM_GLB_PSUM = 2` (2026-10-26, không sửa RTL)

**Triệu chứng.** Với `NUM_GLB_PSUM = 2` (cột "PEs X-axis" = 2 của Bảng 3), mọi model nối một Conv với layer khác trên chip tính sai. **Đính chính:** ghi chú
cũ "kiểm tra sau Conv2 lại đúng" là sai, kiểm tra đó (Conv → Pooling) bị bỏ qua vì testbench không có bố cục cho input của Pooling ("skipping the check").

**Ca nhỏ nhất:** Conv đơn (đọc kết quả thẳng ra) với `NUM_GLB_PSUM = 2` **PASS**; Conv → Conv **FAIL** ngay ở mối nối; `NUM_GLB_PSUM = 4` thì PASS cả hai.
Word đầu của bộ đệm: tham chiếu `p0(c0..c3) p1(c0..c3)`, DUT `p0(c0,c1) p1(c0,c1) p0(c2,c3) p1(c2,c3)` (hai nhóm 2 byte ở giữa đổi chỗ); các word cuối là rác.

**Chỉ pha ghi ngược của Conv hỏng:** tiêm ảnh đúng sau mỗi lần Conv ghi ngược (L0, L2, L4 của mạng paper) thì các kiểm tra sau Pooling và sau Dense → Dense đều PASS
và **kết quả cuối đúng**: Conv, Pooling, Dense và ghi ngược Dense đều đúng với 2 lane. Để kiểm tra được input của Pooling, probe dựng bố cục Conv với nhóm 4 channel
(`B25_POOLCHECK=4`); với `NUM_GLB_PSUM = 4` kiểm tra này PASS ở mọi mối nối, nên đó đúng là bố cục Pooling đọc.

**Nguyên nhân (3 điểm).**

| | Ở đâu | Sai gì |
|---|---|---|
| G1 | RTL `RECEIVE_PSUMS_TO_IACT` | Chuyển vị `WRITEBACK_WORDS` lane (pixel) × `WRITEBACK_WORDS` chu kỳ (channel), `WRITEBACK_WORDS = min(TRANS_WORDS, NUM_GLB_PSUM)` = 2: mỗi nhóm chỉ có 2 channel của một pixel, còn bố cục của layer sau là nhóm 4 channel/pixel (`used_channels` = 4 với kernel 3×3) |
| G2 | cùng chỗ | Bộ đếm `x_pos` dùng để bỏ pixel đệm cuối hàng (`x_pos < iact_size_x`) và quay vòng hàng (`iact_x_add_up`) đếm theo **nhóm**; 2 nhóm/pixel nên cắt sai chỗ (hàng 28 pixel đọc thành 32: mất mọi thứ sau pixel 13) |
| G3 | Python `layer_parameters.py` | `fsm_psum_limit = ⌈x·filters·y / 4⌉ + 11` cho Conv ghi ngược: 4 là số pixel đọc mỗi chu kỳ (`NUM_GLB_PSUM`), với 2 thì pha ghi ngược dừng ở nửa chừng |

**Python thuần không đủ:** cho layer sau dùng nhóm 2 channel (`used_channels = 2`) thì ngay một Conv 4 hoặc 16 channel nạp qua DMA đã tính sai (ánh xạ nhiều nhóm 2 channel
chưa chạy được); thứ tự byte không đổi được bằng vòng đọc (hai nhóm liền nhau luôn đến từ hai lane = hai pixel khác nhau); bỏ cách một nhóm thì cần đổi `iact_x_add_up`,
thứ bộ chuyển đổi Conv đang dùng. Chỉ G3 là Python.

**Đề xuất (sửa RTL khoảng 15 dòng trong `RECEIVE_PSUMS_TO_IACT`; đã được bạn đồng ý và áp dụng, xem mục "Sửa lỗi #25" ngay sau):** `localparam WRITEBACK_CHANNELS = 4` làm độ dài nhóm (byte/nhóm, số chu kỳ mỗi lần
chuyển vị, số nhóm mỗi hàng bộ đệm, độ rộng các lát bus), số lane vẫn là `WRITEBACK_WORDS`; mỗi lần chuyển vị chỉ phát `WRITEBACK_WORDS` nhóm (lane), các chu kỳ còn lại
không dịch và `x_pos` giữ nguyên, nên `x_pos` đếm theo pixel. Với `WRITEBACK_WORDS = 4` mọi điều kiện luôn đúng: **mạch y hệt hiện tại** (mọi test và mốc phần cứng dùng
cấu hình này). Cộng 1 dòng Python: `fsm_psum_limit` chia cho `min(TRANS_WORDS, NUM_GLB_PSUM)` thay vì 4.

**Kiểm chứng trước khi sửa (không đổi RTL):** (1) giả lập G3 (`B25_LIMIT_W`) + sắp lại byte của DUT như bộ chuyển vị 2 lane × 4 channel sẽ ghi (`B25_UNSWAP`): Conv → Conv
16 channel 128/128 word đúng, Conv → Pool → Conv 32/32; (2) thêm giả lập G2 (`B25_XSCALE=2`: ép `iact_size_x`, `iact_x_add_up` gấp đôi trong lúc ghi ngược): Conv rộng 14
56/56, mạng paper L0 1568/1568, L2 784/784 (L4 rộng 7 chỉ 84/196: giới hạn của cách giả lập với độ rộng lẻ); (3) mô hình chu kỳ (`model25.py`): RTL hiện tại tái hiện
đúng kiểu đổi chỗ khi W = 2 và đúng khi W = 4; đề xuất đúng với W = 2 và 4, độ rộng 6, 7, 8, 14, 28, giống hệt mạch cũ từng chu kỳ khi W = 4, đường ghi ngược Dense vẫn đúng.

**Chi phí:** 2 lane đọc nửa số pixel mỗi chu kỳ nên pha ghi ngược của Conv dài gấp đôi: mạng paper CR 2 X 2 Y 3 từ 131.858 lên 137.636 chu kỳ (+4,4 %). Số đo Bảng 3
hiện tại cho X = 2 đang nhanh hơn thực tế khoảng 4 % vì pha ghi ngược bị cắt.

**Chưa bao phủ:** `NUM_GLB_PSUM = 8`; layer sau có `used_channels` khác 4 ngay sau một Conv ghi ngược (ví dụ Conv 7×7: cũng sai với 4 lane hiện nay); `TRANS_WORDS < NUM_GLB_PSUM`.
Lịch sử: `WRITEBACK_WORDS` có từ `4ed008a` (19/9, Hendrik Woehrle), thay bộ đóng gói cũ (chế độ 4/2/1 byte mỗi pixel), chỉ được kiểm chứng với `NUM_GLB_PSUM = 4`.

Chi tiết: `doc/experiments/2026-10-26_bug25_glb_psum2.md`, công cụ `doc/experiments/2026-10-26_bug25/` (`run25.py`, `probe25.py`, `model25.py`).

### Sửa lỗi #25: ghi ngược Conv khi `NUM_GLB_PSUM = 2` (2026-10-26, được bạn đồng ý)

Làm đúng đề xuất ở mục trên.

| File | Thay đổi |
|---|---|
| `hdl/OpenEye_FPGA.v` | `localparam WRITEBACK_CHANNELS = 4`. Trong `RECEIVE_PSUMS_TO_IACT`, độ dài nhóm (số chu kỳ mỗi lần chuyển vị, lúc nạp lại `iact_to_psum_trans_counter`, số nhóm mỗi hàng bộ đệm, độ rộng các lát của thanh ghi chuyển vị/dịch và bus ghi RAM, độ rộng bộ đếm lưu trữ) dùng hằng số này; số lane vẫn là `WRITEBACK_WORDS`. Chỉ ghi nhóm khi `iact_to_psum_trans_counter <= WRITEBACK_WORDS` (so 4 bit; OR với hằng `WRITEBACK_WORDS >= WRITEBACK_CHANNELS` để với 4 lane công cụ tổng hợp bỏ hẳn phép so sánh), các chu kỳ còn lại `x_pos` giữ nguyên (chỉ về 0 trước nhóm đầu tiên); pha flush dùng cùng kích thước nhóm |
| `src/open_eye/layer_parameters.py` | `fsm_psum_limit` của Conv ghi ngược chia cho `min(TRANS_WORDS, NUM_GLB_PSUM)` thay vì 4 |
| `src/open_eye/writeback_model.py` (mới) | Mô hình chu kỳ (vòng đọc + bộ đóng gói, số lane và độ dài nhóm tách riêng), dùng chung cho unit test |
| `test/test_conv_writeback.py` (mới) | 12 test: pixel đúng thứ tự với 2 và 4 lane, hàng rộng 6, 7, 8, 14, 28; cách gom cũ với 2 lane tái hiện đúng kiểu đổi byte |
| `test/test_fc_writeback.py` | Dùng mô hình chung (nhóm 4 channel): ghi ngược Dense vẫn đúng thứ tự với 2 và 4 lane |
| `test/cocotb_fpga/test_glb_psum2.py` (mới) | 7 test RTL với `NUM_GLB_PSUM = 2` |

Với `NUM_GLB_PSUM = 4` mọi điều kiện mới luôn đúng: mạch như trước khi sửa. Lỗi mới #27 (pooling 4×4 → 2×2, mục 8b) phát hiện khi viết test.

**Kiểm chứng:**

| Kiểm tra | Kết quả |
|---|---|
| `test_glb_psum2.py` (RTL, mới) | **7/7 PASS** (bộ đệm và kết quả cuối) |
| Đối chứng âm: RTL cũ (`e062707`) + Python mới | Conv đơn PASS; 3 ca có ghi ngược FAIL đúng kiểu đổi nhóm 2 byte: dòng RTL là cần thiết, test bắt được lỗi |
| Unit test | `test_conv_writeback.py` 12/12, `test_fc_writeback.py` 110/110; tổng 251 pass, 11 fail có từ trước |
| Hồi quy RTL 146 test (`test_conv_const`, `test_mnist_layers`, `test_gemm_layer`, `test_pooling`, `test_nets`, `test_dense_chain`, `test_glb_psum2`) | **141 PASS + 5 xfail đã biết, 0 FAIL** |
| `run_profile` 12 case so với mốc | 12/12 PASS, **0 chu kỳ và 0 word DMA lệch** |
| Lint cấu hình mặc định | `parallel` 36, `fpga` 463: **0 mới** (phép so sánh bộ đếm viết 4 bit để không thêm cảnh báo WIDTHEXPAND) |
| Lint với `NUM_GLB_PSUM=2` (RTL mới so với RTL cũ, cùng cấu hình) | Không có cảnh báo mới |
| Bảng 3 chạy lại (`doc/perf/paper_table3_2026-10-26_fix25.md`; chạy trên bản RTL đầu, trước khi OR thêm hằng vào phép kiểm lane, không đổi hành vi; hồi quy và 12 case mốc đã chạy lại trên RTL cuối) | **13/16 cấu hình PASS** (trước: 7/16). X = 2 với CR 2/4/8: FAIL → PASS, chu kỳ +4,4 % đến +7,8 % (pha ghi ngược Conv không còn bị cắt). X = 4: giống hệt từng chu kỳ. Còn sai: CR 1 X 4 Y 3 (#19b) và CR 1 X 2 Y 3/Y 4 (lỗi mới #28) |
| Vivado tổng hợp + place & route ở 4 ns (`doc/synth/2026-10-26_route4ns_fix25_zu7ev/`) | **0 ERROR, 0 CRITICAL WARNING**, cảnh báo như mốc fix26; sau tổng hợp LUT +113 (+0,17 %, trong biên dao động giữa các lần chạy), FF −10; BRAM/URAM/DSP không đổi; WNS +0,205 / **+0,084 ns**, đạt 250 MHz; đường găng không nằm ở bộ ghi ngược. Lần chạy đầu (phép kiểm lane chưa gấp hằng) LUT +92; RTL cuối OR thêm hằng `WRITEBACK_WORDS >= WRITEBACK_CHANNELS` |
| Kiểm tra tương đương hình thức bằng Yosys (thử) | **Không dùng được**: quy trình báo "tương đương" cả với một sai khác cố ý cài vào, nên không phải bằng chứng |

**Lỗi mới #28:** Conv ở `CLUSTER_ROWS=1` với `NUM_GLB_PSUM=2` tính sai (không phải ghi ngược): 3 layer đầu của mạng paper với conv2 là layer cuối (đọc thẳng ra)
sai ở một số pixel với CR 1 X 2, đúng với CR 1 X 4; một Conv 14×14 32 → 32 channel nạp qua DMA sai với CR 1 X 2, đúng với CR 1 X 4 và CR 2 X 2. Chưa điều tra.

### Kẹp int8 và ReLU gộp (#30, 2026-10-28, được bạn đồng ý)

**Điều tra (trước khi sửa, không đổi repo):** bộ lượng tử tính `8 bit thấp của floor(mant·(psum + offset)/2^shift)`: giá trị tràn bị **quấn vòng** (130 → −126).
Tham chiếu Python cũng không kẹp nên mọi test PASS (dữ liệu test chưa từng tràn). Bộ giả lập numpy (`doc/experiments/2026-10-28_int8/emu.py`) chạy model MNIST int8
đã huấn luyện (`doc/demo_notebooks/mnist_quantized_model.tflite`) theo đúng cách TFLite (đã đối chiếu TFLite interpreter: khớp từng bit ở 3 Conv + 2 MaxPool, Dense lệch
≤ 1 ở 5/19.200 giá trị) và theo cách phần cứng tính, trên 10.000 ảnh test:

| Phương án | Độ chính xác |
|---|---:|
| TFLite int8 | 99,23 % |
| Model thật trên phần cứng hiện tại, chỉ đổi Python | **9,3 %** |
| Đối xứng (zero point 0) + kẹp cận dưới 0 cho ReLU, chưa sửa #12, mantissa 8 bit, psum 20 bit | **99,21 %** |
| Như trên, sửa #12 | 99,25 % |
| Bất đối xứng (zp −128, như TFLite) + kẹp + đệm viền bằng zp + psum 32 bit | 99,24 % (psum 20 bit: 35 %; đệm 0: 96,5 %) |

**ReLU không cần khối riêng:** phép lượng tử lại là đơn điệu, nên `lượng_tử(ReLU(y)) = max(q, lượng_tử(0)) = max(q, zp_out)`: ReLU là **cận dưới của phép kẹp** tại
"số 0 thật". TFLite làm đúng như vậy ("fused ReLU" = `act_min = max(−128, zp_out)`; model đã huấn luyện có zp_out = −128 ở mọi layer ReLU nên ReLU trùng kẹp int8).
Với activation zero point 0: `act_min = 0` cho Conv/Dense có ReLU, −128 cho layer khác.

**Lỗi quấn vòng cụ thể là gì** (đo thêm 2026-10-28, không đổi RTL: `doc/experiments/2026-10-28_int8/wrap.py`, kết quả `wrap_result.txt`). Tầng 3 cũ
`quantized_value <= prod_s2 >>> shift_s2;` gán kết quả 46 bit vào thanh ghi 8 bit: Verilog bỏ 38 bit cao (lấy theo modulo 256), không có gì kiểm tra giá trị có nằm trong
[−128, 127] hay không (lint `WIDTHTRUNC ... SHIFTRS generates 46 bits` đã báo đúng dòng này). Phép cộng offset, nhân `mant`, dịch `shift` đều đúng; thiếu bước thứ tư là
đưa kết quả về khoảng int8, và đó là bộ kẹp được thêm vào.

| Giá trị đúng sau phép dịch | RTL cũ (quấn vòng) | RTL mới, act_min = −128 | RTL mới, ReLU (act_min = 0) |
|---:|---:|---:|---:|
| 100 | 100 | 100 | 100 |
| 127 | 127 | 127 | 127 |
| 128 | **−128** | 127 | 127 |
| 130 | **−126** | 127 | 127 |
| 200 | **−56** | 127 | 127 |
| 256 | **0** | 127 | 127 |
| 300 | **44** | 127 | 127 |
| −5 | −5 | −5 | 0 |
| −129 | **127** | −128 | 0 |
| −150 | **106** | −128 | 0 |
| −200 | **56** | −128 | 0 |
| −300 | **−44** | −128 | 0 |

Hai lỗi: (1) giá trị vượt 127 bị lật thành số âm, sai số 256 thay vì vài đơn vị, và đầu ra không còn đơn điệu theo đầu vào (răng cưa); (2) không có cận dưới nên không làm
được ReLU, giá trị dưới −128 bị lật thành số dương.

Độ chính xác khi chỉ giữ từng nửa của phép kẹp (model MNIST int8 đã huấn luyện, 10.000 ảnh test, TFLite 99,23 %; zp −128 = activation như TFLite, chưa sửa #12,
mantissa 8 bit, psum 32 bit; zp 0 = activation đối xứng, ReLU ở cận 0, theo từng filter, mantissa 8 bit, psum 20 bit):

| Đầu ra bộ lượng tử | zp −128 | zp 0 |
|---|---:|---:|
| Quấn vòng, lấy 8 bit thấp (RTL cũ) | **9,55 %** | **9,22 %** |
| Chỉ kẹp trên 127, phía dưới vẫn quấn | 8,08 % | 43,95 % |
| Chỉ kẹp dưới (ReLU), phía trên vẫn quấn | 97,38 % | 99,18 % |
| Kẹp int8 [−128, 127], không ReLU | 97,58 % | 55,24 % |
| Kẹp [act_min, 127] (RTL mới) | **97,58 %** | **99,25 %** |

Cột zp −128 dừng ở 97,58 % vì đệm viền bằng 0 thay vì zp và lỗi #12, không liên quan đến phép kẹp (mục điều tra ở trên: 99,24 % khi sửa cả hai).

Tỉ lệ đầu ra bộ lượng tử (trước khi kẹp) nằm ngoài khoảng, 1.000 ảnh; với zp −128, cận dưới −128 chính là ReLU:

| Đầu ra của | zp −128: > 127 | zp −128: < −128 (vùng ReLU) | zp 0: > 127 | zp 0: < 0 (vùng ReLU) | zp 0: < −128 |
|---|---:|---:|---:|---:|---:|
| conv1 | 0,23 % | 67,8 % (nhỏ nhất −439) | 0,00 % | 70,6 % | 0,17 % |
| conv2 | 0,01 % | 76,7 % (−452) | 0,00 % | 81,1 % | 0,02 % |
| conv3 | 0,00 % | 86,7 % (−824) | 0,00 % | 77,4 % | 0,08 % |
| fc1 | 0,00 % | 63,5 % (−367) | 0,04 % | 66,3 % | 0,39 % |

Ví dụ thật: conv1, filter 0, ảnh test số 0, lượng tử lại theo TFLite (s_out = 0,0027657, zp_out = −128, M = 0,00335; giá trị thực = (int8 + 128) × s_out):

| Vị trí | psum | × M + zp | Kẹp (TFLite, RTL mới) | Quấn vòng (RTL cũ) |
|---|---:|---:|---|---|
| 658 (đặc trưng mạnh nhất) | 53.077 | 50 | 50, thực 0,492 | 50, thực 0,492 |
| 286 | −6.443 | −150 | −128, thực **0** (ReLU) | 106, thực **0,647** |
| 436 | −52.917 | −305 | −128, thực **0** | −49, thực 0,218 |

Kết luận:

- **Phía âm gây gần hết thiệt hại.** Khi lượng tử hoá trước (offline), TFLite xoá op ReLU, chọn zp_out = −128 để khoảng int8 chỉ biểu diễn [0, max], và để phép kẹp
  lúc chạy đưa phần âm về 0. 64–87 % đầu ra mỗi layer nằm ở phần đó. Quấn vòng biến chúng thành số tuỳ ý: ở vị trí 286, chỗ "không có đặc trưng" thành 0,647, lớn hơn cả
  đặc trưng mạnh nhất thật (0,492). Qua 4 layer chỉ còn ~9 %, ngang đoán bừa 10 chữ số.
- **Phía dương ít ảnh hưởng với model này:** nhờ hiệu chỉnh, ≤ 0,23 % đầu ra vượt 127; bỏ kẹp trên chỉ mất 0,07–0,2 điểm. Nhưng mỗi lần tràn vẫn sai 256 và lật dấu, nên
  với model khác hoặc dữ liệu ngoài vùng hiệu chỉnh thì thiệt hại lớn hơn.
- **Lượng tử hoá trước không thay được bước này.** Offline chỉ chốt tham số (weight int8, bias int32, s_out, zp_out, M → `mant`/`shift`). Đầu ra từng layer phụ thuộc
  ảnh đầu vào nên phải lượng tử lại lúc chạy, ở mỗi layer và với mỗi ảnh; kernel int8 của TFLite cũng kẹp ở đúng bước này (`max(act_min)`, `min(act_max)` rồi ép int8).
- **Với zp 0, kẹp int8 thường mà không có ReLU chỉ được 55 %**: vì vậy bản sửa có thanh ghi `quant_clamp_low` để đặt cận dưới 0.

**Bản sửa:**

| File | Thay đổi |
|---|---|
| `hdl/quantization_unit.v` | Cổng `act_min`; tầng 3 tính `prod >>> shift` đủ độ rộng rồi **kẹp về [act_min, 127]** thay vì lấy 8 bit thấp. Độ trễ vẫn 3 chu kỳ (nhịp ghi ngược không đổi) |
| `hdl/psum_pipeline.v` | Cổng `quant_clamp_low` (8 bit); `act_min = quant_clamp_low ^ 8'h80` (trừ 128 = lật bit cao) đưa vào 8 bộ lượng tử |
| `hdl/OpenEye_FPGA.v` | Nối `quant_clamp_low` từ `dma_storage` sang `psum_pipeline` |
| `test/cocotb_fpga/regmap.yaml` | Thanh ghi `quant_clamp_low` = act_min + 128 (0: kẹp int8 thường, 128: ReLU), đặt cuối: vừa word trạng thái cuối, số word vẫn 14 (DMA 64) / 28 (DMA 32) nên **không đổi chu kỳ**; mapper nào không gửi thì mặc định vẫn là kẹp int8 |
| `src/open_eye/layer_parameters.py` | `activation_min(layer)`: 0 nếu Keras `activation='relu'` hoặc layer nhập có `relu=True`, ngược lại −128; `LayerParameters.act_min` cho Conv và Dense; Dense đọc `quantization_factor` như Conv |
| `src/open_eye/conv_mapper.py`, `dense_mapper.py` | Gửi `quant_clamp_low = act_min + 128` |
| `src/open_eye/simple_layer_operations.py` | Tham chiếu kẹp về [act_min, 127]; nhánh Dense nhân `mant` của filter 0 như phần cứng (không đổi khi `mant = 1`) |
| `src/open_eye/data_create.py` | Hậu tố `_RELU` cho mọi ca model (ReLU ở mọi Conv/Dense trừ layer cuối); móc test `OPENEYE_QUANT_SHIFT` (dịch nhỏ để giá trị vượt int8) |
| `test/cocotb_quantization/` (mới) | Testbench riêng `quantization_unit` so với mô hình Python: ngẫu nhiên + biên, `act_min` −128/0/−17/5, psum 20 và 32 bit |
| `test/cocotb_fpga/test_int8_clamp.py` (mới) | 9 test RTL: tràn, ReLU, cả hai; Conv → Conv (4/16 channel), Conv → Pool → Conv, chuỗi Dense, MLP, `NUM_GLB_PSUM=2`, mạng paper có ReLU |
| `test/test_int8_clamp.py` (mới) | `activation_min`, tham chiếu kẹp (Conv, Dense), vị trí thanh ghi |

**Kiểm chứng:**

| Kiểm tra | Kết quả |
|---|---|
| `test/cocotb_quantization/test_quantization_unit.py` (mới) | 2/2 PASS (psum 20 và 32 bit), mỗi test 12.188 output khớp mô hình, trong đó 3.486 bị kẹp lên 127 và 5.329 kẹp xuống `act_min` |
| `test/cocotb_fpga/test_int8_clamp.py` (mới, RTL) | **9/9 PASS**; ảnh tham chiếu thật sự chạm biên (ca tràn: 111/128 byte bằng 127 hoặc −128; ca ReLU: 64/128 byte bằng 0, không còn số âm) |
| Đối chứng âm: RTL cũ (`b954eda`) + Python và test mới | **9/9 FAIL** đúng dự đoán: ca ReLU còn số âm (`01 fa fa f6 …` so với `01 00 00 00 …`), ca tràn ra giá trị quấn vòng (`4a d2 e3 …` so với `80 7f …`) |
| `test/test_int8_clamp.py` (mới) | 11/11; tổng unit test 262 pass, 11 fail có từ trước |
| Hồi quy RTL 157 test (`test_conv_const`, `test_mnist_layers`, `test_gemm_layer`, `test_pooling`, `test_nets`, `test_dense_chain`, `test_glb_psum2`, `test_int8_clamp`, bộ lượng tử) | **152 PASS + 5 xfail đã biết, 0 FAIL** |
| `run_profile` 12 case so với mốc | 12/12 PASS, **0 chu kỳ và 0 word DMA lệch** |
| Lint | `fpga` 463 → **462** (0 mới, bớt đúng cảnh báo cắt bit của lỗi quấn vòng), `parallel` 36; baseline đã cập nhật; cấu hình `NUM_GLB_PSUM=2` cũng không có cảnh báo mới |
| Vivado tổng hợp + place & route ở 4 ns (`doc/synth/2026-10-28_route4ns_clamp_zu7ev/`) | **0 ERROR, 0 CRITICAL WARNING**, cảnh báo như cũ; LUT +857 sau tổng hợp / +832 sau route (+1,3 %), trong đó +676 ở 8 bộ lượng tử của `psum_pipeline` (phép kẹp cần cả giá trị sau dịch, trước đây chỉ cần 8 bit thấp); FF +22; DSP/BRAM/URAM không đổi; WNS +0,205 / **+0,076 ns**, đạt 250 MHz; không đường găng nào đi qua bộ lượng tử |

**Chưa thuộc bản sửa này:** luồng Python lượng tử int8 cho model thật, lỗi #12, mantissa bị cắt 8 bit, lỗi #29 (mục 8b, 8d).

Chi tiết: `doc/experiments/2026-10-28_int8_clamp.md`, công cụ `doc/experiments/2026-10-28_int8/`.

### Điều tra lỗi #31: một lượt rỗng làm mất mọi lượt sau (2026-10-30, không sửa RTL)

Chi tiết: `doc/experiments/2026-10-30_bug31_empty_pass.md`, công cụ `doc/experiments/2026-10-30_bug31/` (`probe31.py` bọc testbench gốc, `run31.py` chạy một
layer với input tự chọn và so mọi output với numpy). Dùng luồng gốc của project (weight ngẫu nhiên của model Keras, bias 1), chỉ thay input layer 0.

**Điều kiện kích hoạt:** một lượt tính mà **không PE nào có activation khác 0**. Conv 3×3: hàng output có cửa sổ 3 hàng input (y−1, y, y+1) toàn 0 trên phần
hàng một lượt phủ; Dense 3136 → 10: một khối K input của lượt toàn 0 (65–109 input). **Hậu quả:** lượt đó và **mọi lượt sau** không được tính, output giữ bias
(+ các lượt trước); layer vẫn kết thúc đúng giờ nên không có gì báo lỗi.

| Input (28×28×1, đệm 2 channel) | Kết quả |
|---|---|
| Ảnh MNIST số 0 | sai: bias ở cả 3.136 output |
| Cùng ảnh, thay mọi số 0 bằng 1 | đúng |
| 50 % số 0 rải rác / hàng y = 0 toàn 0 / hàng 10–11 toàn 0 / x = 0…4 toàn 0 ở mọi hàng | đúng |
| Hàng y = 0–1 toàn 0 (cả 2, 4 channel thật và layer 8×4×4) | sai: bias toàn bộ |
| Hàng 4–6 toàn 0 | sai: bias từ hàng 5 (cửa sổ rỗng đầu tiên) đến hết |
| Ba hàng cuối toàn 0 | đúng (phía sau không còn gì) |
| 90 % số 0 rải rác | sai từ hàng 16 (cửa sổ có chuỗi 20 vị trí x toàn 0) |
| Dense: input 0…511 toàn 0 / 1024…1535 toàn 0 / 0…63 toàn 0 | bias / sai (mất các lượt sau) / đúng |

**Lần theo dữ liệu** (layer 8×4×4, hàng 0–1 toàn 0 sai, hàng 1–2 toàn 0 đúng): luồng DMA Python đúng; bộ đệm iact sau khi nạp đúng; bộ chuyển đổi ghi 72 word
(20 khác 0) vào RAM của nó ở cả hai ca; nhưng ở ca sai nó **chỉ phát một lượt** (72 word, toàn 0) thay vì 4 lượt (288 word, 80 khác 0), vì `enable_converter`
không bao giờ được phát lại; PE có `second_spad_words_iact` = 0 suốt layer và ở IDLE; xung `compute_i` vẫn đủ 12 lần, layer kết thúc cùng thời điểm (10.540 ns).

**Nguyên nhân (điều khiển RTL):** PE chỉ bắt đầu một lượt khi có ít nhất một activation khác 0 và một weight (`PE.v:1135`); PE rỗng ở IDLE, iact ready vẫn 1.
`OpenEye_FPGA.v` đếm lượt (Process 2, `current_cycle`) và khởi động lượt converter + gửi weight kế tiếp (Process 5) **chỉ khi bus `iact_ready_o_oep_w` rời trạng
thái toàn 1**, tức khi có PE bắt đầu tính. Lượt rỗng: không PE nào bắt đầu → bus giữ toàn 1 → lượt sau không được khởi động, không được đếm.

**Lỗi #33 cùng nguyên nhân:** output sai của fc1 ở ảnh 0 bằng đúng bias + tích của input 0…2653; input 2654 mở đầu chuỗi 109 số 0; ảnh 1 có chuỗi dài nhất 75 nên
đúng. Lỗi #32 (đổi chỗ bias cặp filter ở Conv3) là lỗi khác.

**Giả lập (chỉ trong mô phỏng):** ép bus ready xuống 1 chu kỳ khi lượt rỗng chữa được ca 8×4×4 với một cách kích hoạt, nhưng ở 28×28 FSM psum lại chờ psum từ các
PE đã bỏ lượt (kẹt ở trạng thái 3). Vậy bản sửa phải làm cho lượt rỗng đi trọn giao thức như một lượt có tích bằng 0, không chỉ tạo xung ready.

**Upstream cũng bị (kiểm tra 2026-10-30, `upstream/main` = `93f0e82`):** điều kiện bắt đầu lượt của PE, Process 2 và điều kiện kích hoạt lượt kế tiếp theo bus
ready ở Process 5 giống hệt `dev` (có từ `a83260d` 2025-03-19 và `337bd44` 2025-07-22, có trên mọi nhánh gần đây). Chạy trên chính RTL và testbench của upstream
(worktree, `doc/experiments/2026-10-30_bug31/run31_upstream.py`; Conv 8×4×4, weight hằng 8 của upstream): ngẫu nhiên PASS, hàng 1–2 toàn 0 PASS, **hàng 0–1 toàn 0
FAIL** (cả 4 feature map, 96 giá trị sai đều bằng 1 = bias). Dữ liệu test của upstream cũng không có số 0 nên không lộ.

**Hướng sửa (sửa RTL, cần bạn đồng ý, chưa làm):** (A) `PE.v`: PE rỗng vẫn rời IDLE, bỏ qua CALCULATING (tích 0), đi qua WAIT_TO_SEND_PSUM/SEND_PSUM như PE có tính:
thay đổi cục bộ, mọi bắt tay giữ nguyên, tốn vài chu kỳ cho lượt rỗng; (B) `OpenEye_FPGA.v`: đếm lượt và khởi động lượt sau theo một sự kiện tường minh (xung
compute hoặc converter phát xong) thay cho bus ready, và FSM psum không chờ PE bỏ lượt: bỏ hẳn điều khiển phụ thuộc dữ liệu nhưng đụng vào lịch trung tâm,
rủi ro hồi quy cao hơn. Đề xuất A. Kiểm chứng: các ca `run31.py` ở trên khớp numpy, hồi quy, mốc chu kỳ (lượt có dữ liệu không được đổi), Vivado. Không có
workaround chỉ bằng Python (làm mọi lượt khác rỗng là đổi dữ liệu).

### Điều tra lỗi #32 và #35 (2026-10-30, không sửa RTL), bản sửa #32 bằng Python

Chi tiết: `doc/experiments/2026-10-30_bug32_bias_order.md`, công cụ `doc/experiments/2026-10-30_bug32/` (`probe32.py` bọc probe31 và testbench gốc: `B32_BIAS`
ghi giá trị bias từng lane khi nạp, `B32_REVERSE` giả lập bản sửa Python, `B35_DUMP` lưu mọi lần kiểm tra bộ đệm iact; `run32.py` một layer conv, `run35.py` model
thật, `analyze35.py`, `explain35.py`, `scan31.py`).

**#32, nguyên nhân:** Conv3 (7×7×64 → 64) là layer duy nhất của model có `different_kernels_per_calculation` = 2: hai filter tính cùng lúc trên hai hàng cluster,
filter 2p ở cluster row 0, 2p+1 ở row 1 (tính toán và đọc ra đều đếm lane từ cluster 0). Stream bias (`psum_stream_mapper`, serial) gửi mỗi filter thành 4 word
(8 word khi chỉ một nhóm kernel), filter theo thứ tự tăng; `psum_pipeline.v` (GET_BIAS) dịch từng word vào **từ dưới lên** và ghi một địa chỉ sau 8 word, nên word
đầu (filter 2p) rơi vào lane trên cùng = cluster row 1, đang tính filter 2p+1. Một nhóm kernel: 8 word cùng một bias nên thứ tự không quan trọng; 2 nhóm: cặp đổi
chỗ; 4 nhóm (hàng ≤ 4 pixel, ≥ 13 filter): nhóm 4 filter đảo ngược. Đo trong mô phỏng (bias 1 + 3f, Conv 7×2 4 ch 8 filter): lần ghi bias đầu
`cr0 = 4 (b1), cr1 = 1 (b0)`; DUT − numpy = +3/−3 xen kẽ; Conv 4×2 16 filter: +9/+3/−3/−9. Đảo thứ tự nhóm kernel trong stream bias (`B32_REVERSE`): **0 sai** ở
cả hai. Bị che vì mọi test cũ cho mọi filter bias 1 (test bias khác nhau `test_conv_channel_order` chỉ có 4 filter, một nhóm). Upstream cùng mapper và cùng
cách dịch (đọc code).

**#35 = #31:** với bản sửa #32 giả lập, 113 output sai của Conv3 (ảnh 0) đều ở **hàng output cuối y = 6**, không phải một cột. Các hàng 0–5 khớp đúng tham chiếu;
cửa sổ của hàng 6 (input hàng 5, 6 và hàng đệm 0) có nhóm channel 44–47 toàn 0 → lượt (hàng 6, refresh 0, nhóm 11) rỗng, nó và mọi lượt sau mất: mô hình
"bias + nhóm 0…10 cho filter 0–31, chỉ bias cho filter 32–63" khớp DUT **448/448**. Mô hình #31 (+ #32) của `scan31.py` khớp RTL 3136/3136 ở ảnh 0 (có/không
sửa #32), ảnh 1 (có/không) và ảnh 7 (lượt rỗng ở hàng đầu). Ghi chép cũ "cột x = 6" là do đọc chỉ số pixel thành 7x + y thay vì x + 7y.

**Kết quả:** với #32 sửa (giả lập), **ảnh test 1 chạy trọn model đã huấn luyện trên RTL, PASS, khớp từng bit, DUT ra lớp 2 = nhãn**. Ảnh 0 và 86 % ảnh test còn
vướng #31 ở Conv3 (lượt rỗng đầu tiên ở hàng 0: 429 ảnh, hàng 6: 377, hàng 5: 52); độ chính xác ước tính 61,9 % hôm nay, 72,9 % khi sửa #32, 99,5 % khi sửa cả #31.

**Bản sửa #32 (được bạn đồng ý, chỉ Python, cùng ngày):** `src/open_eye/psum_stream_mapper.py`: hàm mới `PsumStreamMapper.bias_stream_filter_order()` trả về thứ
tự filter trong stream, mỗi nhóm `different_kernels_per_calculation` filter liên tiếp bị đảo ([1, 0, 3, 2, …] với 2 nhóm kernel, [3, 2, 1, 0, …] với 4, thứ tự thường
với 1 nhóm); `get_psum_stream` (serial) lặp theo thứ tự này thay cho `range(filters)`. Cùng các word, cùng số word (không đổi `trans_cycles_psum`, không đổi chu kỳ),
không sửa RTL. Chỉ Conv2D mới có hơn một nhóm kernel; Depthwise luôn 1 nhóm, Dense/GEMM có stream bias riêng. Khi mọi bias bằng nhau (mọi model hồi quy: Conv
bias 1) stream giống hệt từng word. Số filter không chia hết cho số nhóm vốn không chạy được (`calculate_conv_serial` chia cho 0, thử 5 filter rộng 8).

| Kiểm chứng | Kết quả |
|---|---|
| `test/test_psum_bias_order.py` (mới, 22 test): stream so với mô hình nạp bias của RTL (dịch vào từ dưới, một địa chỉ mỗi `CONV_BIAS_CYCLES` word), 1/2/4 nhóm kernel, DMA 64/32, psum 20/32 bit | 22/22; với mapper cũ 15 FAIL |
| `test_conv_const.py::test_conv_bias_order` (mới, RTL, bias 1 + 3f, dữ liệu ngẫu nhiên): rộng 8, 8 filter (2 nhóm); rộng 4, 16 filter (4 nhóm) | 2 PASS (khoảng 10 s mỗi test); với mapper cũ 2 FAIL (DUT − tham chiếu +3/+9) |
| `test_real_model.py` | **ảnh 1 PASS**: trọn model đã huấn luyện khớp từng bit, DUT ra lớp 2 = nhãn; ảnh 0 xfail(strict) do #31 (45/392 word trước Dense, đúng như giả lập) |
| Unit test `test/test_*.py` | 290 pass (268 + 22), 11 fail có từ trước (`test_dense_output.py`) |
| Hồi quy RTL | `test_int8_clamp` 9/9, `test_glb_psum2` 7/7, `test_mnist_layers -k random` 9/9 (gồm 8×4, 64 filter: 2 nhóm kernel, bias 1), `test_conv_const` **36/36 PASS** (34 cũ + 2 mới) |

Thay thế không chọn: dịch word bias từ trên xuống trong `psum_pipeline.v` (sửa RTL, không lợi hơn). #31: hướng A trong `PE.v` như mục trên (đã làm cùng ngày, được bạn đồng ý, mục dưới).

### Sửa lỗi #31 trong `PE.v` (hướng A, 2026-10-30, được bạn đồng ý)

Chi tiết: `doc/experiments/2026-10-30_bug31_fix.md`. Gồm cả #33 (Dense) và #35 (Conv3 của model thật).

**Thiếu gì:** mỗi lượt, `OpenEye_Parallel` phát `compute_i` cho mọi PE; PE có dữ liệu rời IDLE và hạ iact ready; bus ready của mảng PE rời trạng thái toàn 1 thì
`OpenEye_FPGA` đếm lượt (Process 2) và khởi động converter + gửi weight của lượt sau (Process 5); FSM psum thu psum rồi quay lại chờ. PE không có activation khác 0
(`second_spad_words_iact == 0`) ở lại IDLE (dữ liệu của nó vẫn được xoá đúng qua `compute_pe`); khi cả lượt không PE nào có dữ liệu thì bus không rời toàn 1, lượt
sau không được nạp, còn FSM psum vẫn chạy hết các lượt (PE rảnh chuyển psum đi qua) nên output = bias + các lượt trước.

**Sửa (`hdl/PE.v`, cả FSM sparse đang dùng và FSM dense):** trạng thái mới `EMPTY_PASS` (9). Ở IDLE, `data_set & compute_pe` mà không có activation hoặc word weight
thì sang `EMPTY_PASS` thay vì đứng yên: hạ iact/wght ready (lượt được đếm, lượt sau được nạp như với PE có tính), `psum_select = 1` (sẵn sàng nhận psum ngay). Ready
giữ thấp **16 chu kỳ** (`EMPTY_PASS_HOLD`) hoặc tới khi FSM psum bắt đầu đọc lượt này (`psum_enable_i`), cái nào tới trước; khi đọc thì sang `SEND_PSUM` y như từ
IDLE (`use_psum = 0`, chuyển psum đi qua). Không đọc SPad, không có tích. PE không nhận dữ liệu trong layer (`data_set = 0`) hoặc không có `compute_i` vẫn ở IDLE; PE
có dữ liệu đi đường cũ. Chi phí: 1 trạng thái + bộ đếm 5 bit mỗi PE.

**Thời gian giữ ready (hai bản bị loại):**

| Bản | Conv | Dense 3136 → 10 có khối 0 | Chu kỳ 12 ca mốc |
|---|---|---|---|
| nâng ready sau 6 chu kỳ (lượt tính ngắn nhất) | đúng | **treo** | – |
| giữ tới khi đọc psum | đúng | đúng | **+5 … +11 % compute** ở Conv nhỏ, +3,9 % `model_mnist_real` |
| **giữ 16 chu kỳ hoặc tới khi đọc psum** (bản cuối) | đúng | đúng | **0 chu kỳ, 0 word DMA** cả 12 ca |

Vì sao 6 chu kỳ bị treo (lần vết bằng `probe32.py` `B31_TOP`/`B31_WATCH`): dữ liệu lượt sau được truyền khi FSM psum còn ở `WAIT_TO_SEND_READY_SIGNAL`
(`psum_transmitted = 1`, nó chỉ rời trạng thái này sau 16 chu kỳ không truyền); truyền xong, `OpenEye_Parallel` thấy "psum đã thu, không truyền" lần nữa và phát
**thêm một xung tính sớm một lượt**; PE giữ xung đó (`compute_pending`) và bắt đầu lượt sau khi mới có 4/12 word, lệch pha rồi kẹt. Lượt bình thường truyền sau khi
PE tính xong (> 16 chu kỳ), lúc FSM psum đã ở trạng thái 2/3 (`psum_transmitted = 0`). Vì sao "giữ tới khi đọc" tốn chu kỳ: nhiều lượt có dữ liệu cũng có PE rỗng
(PE ngoài cuối hàng, ví dụ x = 28…31 khi hàng 28 pixel được trải trên 32 cột PE); ready của cluster là AND các PE nên chúng làm chậm việc nạp lượt sau. Giữ 16 chu
kỳ: không truyền nào bắt đầu trước khi FSM psum rời trạng thái 1, còn trong lượt có dữ liệu các PE đang tính giữ bus lâu hơn 16 chu kỳ nên PE rỗng không làm chậm gì.

**Kiểm chứng:**

| Kiểm tra | Trước | Sau |
|---|---|---|
| `run31.py`: Conv 8×4×4 hàng 0–1 bằng 0; ảnh MNIST làm input; hàng 4–6 bằng 0; 90 % số 0; một khối khác 0 (28×28) | sai (bias) | 0 giá trị sai ở mọi ca |
| Dense 3136 → 10, input 0…511 / 1024…1535 bằng 0 (#33); đối chứng ngẫu nhiên | sai / đúng | đúng / đúng |
| `test/cocotb_fpga/test_empty_pass.py` (mới, 3 test, móc `OPENEYE_ZERO_BLOCK`) | 3 FAIL | 3 PASS |
| `test_real_model.py` (ảnh 0, 1) + `run35.py` ảnh 2…7 | ảnh 0 sai Conv3 | **8/8 khớp từng bit, lớp đúng cả 8** |
| Lint (`tools/lint_check.py`) | fpga 462, parallel 36 | 0 cảnh báo mới |
| `run_profile --compare doc/perf/baseline_2026-10-24` | | **12/12, 0 chu kỳ, 0 word DMA lệch** |
| Hồi quy RTL | | **162 test: 157 PASS + 5 xfail đã biết, 0 FAIL**: `test_conv_const` 36/36, `test_mnist_layers` 21 + 5 xfail (#7, #9, #17), `test_gemm_layer` 63/63 (`OPENEYE_SKIP_FC_WRITE_CHECK=1`), `test_dense_chain` 11/11, `test_glb_psum2` 7/7, `test_int8_clamp` 9/9, `test_pooling` 4/4, `test_nets` 1/1, `test_empty_pass` 3/3, `test_real_model` 2/2; unit test Python 290 pass, 11 fail có từ trước |
| Vivado tổng hợp + place & route 4 ns (`doc/synth/2026-10-30_route4ns_fix31_zu7ev/`) | WNS +0,076 ns; 64.801 LUT; 39.316 FF | **0 ERROR, 0 CRITICAL WARNING**, cảnh báo như cũ; **WNS +0,074 ns** (đạt 250 MHz); FF +480 (+10/PE); LUT −3.961 (Vivado mã hoá FSM của PE one-hot) |

### Lấy upstream `e78e5b7`: mẫu reset trong `OpenEye_FPGA.v` (2026-10-31, được bạn đồng ý)

`git cherry-pick -x e78e5b7` → `5595d15` (giữ tác giả gốc DenLeb). Commit xoá một dòng `temp_var = 0;` nằm **ngoài** cặp `if (!rst_n) ... else ...`
của khối `always @(posedge clk_i, negedge rst_n)` của Process 5 (gửi weight và iact). Dòng đó chạy cả ở cạnh xuống của reset nên khối không còn đúng
mẫu reset bất đồng bộ. `temp_var` chỉ là biến tạm, được gán và dùng ngay rồi đặt lại 0 trong vòng tạo mặt nạ enable weight (`OpenEye_FPGA.v:1202–1204`),
nên xoá dòng này không đổi chức năng.

| Kiểm tra | Kết quả |
|---|---|
| Hồi quy RTL 162 test (như #31) | **157 PASS + 5 xfail đã biết, 0 FAIL**, giống hệt trước |
| `test/cocotb_quantization/test_quantization_unit.py`; unit test Python | 2/2; 290 pass, 11 fail có từ trước |
| 12 ca mốc (`run_profile --compare doc/perf/baseline_2026-10-24`) | **12/12, 0 chu kỳ, 0 word DMA lệch** |
| Bảng 3 của paper, 16 cấu hình | 13/16 như cũ; **0 chu kỳ lệch** so với `paper_table3_2026-10-26_fix25` ở cả 16 |
| Lint | `fpga` 462 → **461** (bớt đúng 1 `BLKSEQ` của dòng đã xoá), `parallel` 36; baseline đã hạ |
| Vivado tổng hợp + place & route 4 ns (`doc/synth/2026-10-31_route4ns_e78_zu7ev/`) | **0 ERROR, 0 CRITICAL WARNING**, 410 cảnh báo như cũ; WNS +0,205 / **+0,074 ns** (đạt 250 MHz); mọi báo cáo tài nguyên và timing **giống từng dòng** lần chạy `fix31` (60.840 LUT, 39.796 FF sau route): Vivado vốn đã dựng cùng netlist, commit chỉ làm sạch mẫu reset |

### Thí nghiệm: kết thúc gửi weight ở `wghts_per_pe + 1` (dòng RTL của upstream `3258813`, thử 2026-10-31, đưa vào `dev` 2026-11-01, được bạn đồng ý)

Chi tiết: `doc/experiments/2026-10-31_wght_send_end.md`, bản vá `doc/experiments/2026-10-31_wght_send_end/wght_send_end_plus1.patch`. Chạy trong một
worktree của `dev` (`5595d15`) chỉ đổi dòng `if (fsm_sending_cycle > wghts_per_pe + 2)` thành `+ 1` (Process 5 của `OpenEye_FPGA.v`).

- **Vì sao được:** bộ đệm weight trả dữ liệu trễ 2 chu kỳ: địa chỉ tăng ở các chu kỳ đếm 1…N (N = `wghts_per_pe`), dữ liệu ra ở 3…N+2. Với `+ 2`, enable
  còn bật thêm ở chu kỳ N+3 (gửi một word thừa) và lượt tính bắt đầu muộn 1 chu kỳ; với `+ 1`, enable bật đúng N chu kỳ có dữ liệu.
- **Đúng:** hồi quy 162 test 157 PASS + 5 xfail như `dev`; 12 ca mốc 12/12; model đã huấn luyện ảnh 0, 1, 2, 7 khớp từng bit, lớp đúng; Bảng 3 13/16 như
  `dev`; lint 0 cảnh báo mới.
- **Lợi:** 1 chu kỳ mỗi lượt mà việc gửi weight nằm trên đường găng, **chỉ ở pha compute** (không phải `load_wght`: pha đó là DMA nạp weight vào bộ đệm
  trên chip, không đổi). Model MNIST −673 chu kỳ (−0,28 %, khoảng 2,7 µs ở 250 MHz: Conv2 −448, Conv3 −224), `mnist1`/`mnist2`/`mnist3` −0,2/−0,3/−0,3 %,
  Bảng 3 −0,1 % (CR 8) đến −0,3 % (CR 1), các ca nhỏ 0; số word DMA không đổi; không tốn tài nguyên (chỉ đổi hằng số của một phép so sánh).
- **Trạng thái:** **đã đưa vào `dev` 2026-11-01** (được bạn đồng ý, commit dựa trên kết quả của worktree ở trên, cùng một dòng thay đổi; thêm comment
  giải thích ở dòng đó và sửa 2 comment mô tả dải đếm `fsm_sending_cycle` trong `OpenEye_FPGA.v` và `dense_mapper.py`). Trên `dev` đã chạy: lint 0 cảnh
  báo mới, unit test Python 290 pass / 11 fail có từ trước, bộ lượng tử 2/2, 16 test đầu của hồi quy đều PASS/xfail (dừng theo yêu cầu). **2026-11-02:**
  12 ca mốc trên `dev` 12/12 PASS, số chu kỳ trùng đúng worktree, lưu thành mốc mới `doc/perf/baseline_2026-11-02/` (mục 7); Vivado 4 ns 0 CRITICAL,
  LUT −199, FF −6, WNS +0,020 ns (đường găng mới không qua phép so sánh vừa sửa), mốc phần cứng mới `doc/synth/2026-11-02_route4ns_wsend_zu7ev/` (mục 6d).

### Hàm kích hoạt trên RTL, bước B (2026-11-02, được bạn đồng ý)

Thiết kế `doc/experiments/2026-11-02_activation_rtl_design.md`, kết quả `doc/experiments/2026-11-02_activation_rtl.md`. Leaky ReLU, SiLU, hard-swish tính
trong bộ lượng tử của pha ghi ngược, khớp từng bit với tham chiếu của bước A.

- **`quantization_unit.v`:** tầng 1 lấy dấu của tổng và chọn cặp [mant, shift] của độ dốc âm khi `leaky_en`; tầng 2 nhân và cộng `2^(shift−1)` khi `round_en`
  (DSP: A·B + C); tầng 3 không đổi. Hai tuỳ chọn bằng 0 thì mọi thanh ghi giữ giá trị như cũ.
- **`activation_table.v` (mới):** bảng 256 ô chia `TABLE_WORD_WIDTH/8` bank LUTRAM (8 bank × 32 ô ở DMA 64 bit): mỗi word DMA ghi 8 ô trong 1 chu kỳ; đọc không
  đồng bộ ở chỉ số = giá trị + 128, nên độ trễ 3 chu kỳ của bộ lượng tử giữ nguyên. Một bảng cho mỗi lane ghi ngược (`WRITEBACK_WORDS`, 4).
- **`psum_pipeline.v`:** cổng `act_mode`, `act_round`, `act_neg_mant`, `act_neg_shift`, `act_table_we`, `act_table_addr`; lane ra = bảng ở chế độ 2.
- **`OpenEye_FPGA.v`:** 5 trường mới từ `dma_storage`; trạng thái `GET_ACTIVATION` = 15 nạp `2048/DMA_BITWIDTH` word sau `GET_QUANTIZE` (chỉ khi chế độ 2 và không
  `act_keep_table`, giữ `ready_dma_o` cao nên stream không có bong bóng); dây trace `UNPACKED_TRACES.act_capture` cho profiler.
- **`regmap.yaml`:** `act_neg_mant`, `act_neg_shift`, `act_round` sau `quant_clamp_low`; `act_mode` và `act_keep_table` đặt vào các khe trống phía trên. Lần profile
  đầu (5 trường ở cuối) cho thấy ca DMA 32 bit thêm 1 word trạng thái (28 → 29); sau khi dời 2 trường, 28 / 14 / 7 word ở 32 / 64 / 128 bit như cũ.
- **Python:** mapper gửi 5 trường và các word bảng (nối sau word lượng tử, cùng phần stream); `check_rtl_activation` kiểm tham số vừa phần cứng; `onnx2model` làm
  tròn gần nhất cho Leaky/SiLU/hard-swish; móc test `OPENEYE_ACTIVATION`; testbench dựng model theo hàm kích hoạt ghi trong checkpoint.

| Kiểm tra | Kết quả |
|---|---|
| Testbench bộ lượng tử (mở rộng) | 2/2 PASS, mỗi lần 30.470 đầu ra khớp mô hình (khoảng 6.100 trên dốc âm) |
| Testbench `activation_table` (mới) | 3/3 PASS ở word 32 / 64 / 128 bit |
| `test_activation_rtl.py` (mới, 12 ca: Leaky, bảng ngẫu nhiên / SiLU / hard-swish, làm tròn, giữ bảng, Dense, MLP, `NUM_GLB_PSUM=2`, DMA 32 bit, mạng paper) | **12/12 PASS** |
| Đối chứng âm (sai stream: chế độ 0, bảng lệch 1 ô, tắt làm tròn) | 6/6 FAIL như phải thế |
| Model đã huấn luyện Leaky ReLU / SiLU / hard-swish, ảnh 0, 1 (`test_real_model_activation`) | **6/6 PASS**, trọn mạng khớp từng bit, lớp 7 và 2 = nhãn |
| Hồi quy RTL 180 test (162 cũ + 12 + 6) | **175 PASS + 5 xfail đã biết, 0 FAIL** |
| 12 ca mốc | 0 chu kỳ, 0 word DMA lệch so với `baseline_2026-11-02` |
| Bảng 3 | 13/16, 0 chu kỳ lệch so với số của dòng `+1`; lưu mốc Bảng 3 mới `doc/perf/paper_table3_2026-11-02` |
| Unit test Python; lint | 321 pass, 11 fail có từ trước; `fpga` 461 → 460, 0 mới |
| Vivado 4 ns (`doc/synth/2026-11-02_route4ns_act_zu7ev/`) | 0 CRITICAL, WNS +0,045 ns (đạt 250 MHz), LUT +778 (do bước B khoảng +550), FF +59, 0 BRAM/URAM/DSP thêm |

Chi phí khi chạy: 0 chu kỳ mỗi giá trị ở mọi chế độ; chế độ bảng nạp 32 word (DMA 64 bit) mỗi layer, 0 nếu giữ bảng cũ; 0 word trạng thái thêm.
Đo bằng profiler trên model đã huấn luyện (bước C): mục 6.15.

**Cách tính của từng hàm** (psum = Σ x·w + bias, số nguyên; giá trị thật = psum × s_in × s_w; s_out, s_next = scale đầu ra của layer và scale input của
layer tính kế tiếp, do `onnx2model` lấy từ lượng tử tĩnh; `hardware_multiplier(M)` = (mant 24 bit, shift) với mant / 2^shift ≈ M, shift lớn nhất có thể; trước bản sửa #38 mant 8 bit; độ dốc âm của Leaky vẫn 8 bit):

| Hàm | Python tính (`onnx2model.finish_activations`) | Gửi vào accelerator (mỗi layer) | Phần cứng làm |
|---|---|---|---|
| ReLU | (mant, shift) = M(s_in·s_w / s_out); `has_relu` → act_min 0; làm tròn xuống | Word lượng tử (mant, shift, offset 0 cho mỗi filter); `quant_clamp_low` = 128 (act_min 0); `act_mode` 0 | q = kẹp(⌊mant·psum / 2^shift⌋, 0, 127) |
| Leaky ReLU | (mant, shift) = M(s_in·s_w / s_next) cho psum ≥ 0; (neg_mant, neg_shift) = M(α·s_in·s_w / s_next), α = 0,1; làm tròn | Word lượng tử; `act_mode` 1, `act_neg_mant`, `act_neg_shift`, `act_round` 1; `quant_clamp_low` 0 (act_min −128) | Tầng 1 chọn cặp theo dấu của psum; q = kẹp(⌊(mant·psum + 2^(shift−1)) / 2^shift⌋, −128, 127) |
| SiLU | (mant, shift) = M(s_in·s_w / s_out) (int8 trước hàm); bảng T[i] = làm_tròn(f((i − 128)·s_out) / s_next), f(x) = x·sigmoid(x), 256 ô | Word lượng tử; `act_mode` 2, `act_round` 1; **32 word bảng** (DMA 64 bit) sau word lượng tử, trừ khi `act_keep_table` | q như Leaky (một cặp), rồi ra = T[q + 128] (đọc LUTRAM không clock) |
| hard-swish | Như SiLU với f(x) = x·clip(x + 3, 0, 6) / 6 | Như SiLU | Như SiLU |

Ví dụ Conv1 của các model đã huấn luyện, psum = 5000 / −5000 (hệ số 24 bit từ #38; với hệ số 8 bit cũ trong ngoặc kết quả y hệt): ReLU (14.166.994, 32)
[(216, 16)] → 16 / 0; Leaky (8.817.157, 31) [(135, 15)] và (215, 19) → 21 / −2; SiLU (9.899.939, 32) [(151, 16)] → q = 12 / −12 → T = 12 / −8; hard-swish
(10.282.080, 32) [(157, 16)] → q = 12 / −12 → T = 11 / −8. Cả 4 hàm qua cùng 3 tầng của bộ lượng tử (3 chu kỳ, 4 lane mỗi chu kỳ); bảng chỉ thêm
một lần đọc LUTRAM trong cùng chu kỳ, nên 0 chu kỳ mỗi giá trị.

#### Bảng của SiLU / hard-swish, vì sao Leaky ReLU không cần bảng, 3 tầng của bộ lượng tử (giải thích 2026-11-03)

**96 chu kỳ của SiLU / hard-swish nằm ở pha `load_act`** (trạng thái `GET_ACTIVATION` = 15), không phải `load_iact`: 32 chu kỳ × 3 layer có hàm kích hoạt
(Conv1, Conv2, Conv3; Dense cuối không có).

**Bảng gửi vào accelerator.** Sau bộ lượng tử, giá trị của layer là int8, chỉ có 256 khả năng (−128 … 127). `onnx2model.activation_table` tính sẵn kết quả
của hàm cho từng khả năng, mỗi layer một bảng (scale mỗi layer khác nhau):

```
T[x + 128] = làm_tròn( f(x · s_out) / s_next ),  kẹp về [−128, 127],  x = −128 … 127
  f(x) = x · sigmoid(x)               (SiLU)
  f(x) = x · clip(x + 3, 0, 6) / 6    (hard-swish)
```

`activation_table_words` xếp 8 ô vào mỗi word DMA 64 bit (ô 8w + b ở byte b của word w): 256 ô = 32 word, gửi ngay sau các word lượng tử của layer. Ví dụ
bảng SiLU của Conv1 của model đã huấn luyện (s_out = 0,0374, s_next = 0,0228):

| Word | x | 8 ô | Word gửi đi |
|---:|---|---|---|
| 0 | −128 … −121 | −2 −2 −2 −2 −2 −2 −2 −2 | `0xFEFEFEFEFEFEFEFE` |
| 14 | −16 … −9 | −9 −9 −9 −8 −8 −7 −7 −6 | `0xFAF9F9F8F8F7F7F7` |
| 15 | −8 … −1 | −6 −5 −4 −4 −3 −2 −2 −1 | `0xFFFEFEFDFCFCFBFA` |
| 16 | 0 … 7 | 0 1 2 3 4 4 5 7 | `0x0705040403020100` |
| 31 | 120 … 127 | 127 (cả 8 ô) | `0x7F7F7F7F7F7F7F7F` |

Trên accelerator: sau `GET_QUANTIZE`, FSM chính vào `GET_ACTIVATION`, nhận 1 word mỗi chu kỳ (32 chu kỳ; 64 ở DMA 32 bit). Mỗi word được ghi cùng lúc vào cả
4 bảng (`activation_table.v`, một bảng cho mỗi lane ghi ngược), mỗi bảng 8 bank LUTRAM: byte b vào bank b ở địa chỉ w. Layer sau dùng đúng bảng cũ thì
`act_keep_table` bỏ qua bước này; ở model MNIST 3 layer có scale khác nhau nên nạp 3 bảng.

Bảng giải thích luôn vì sao các hàm này mất số 0: bảng SiLU chỉ có **một** ô bằng 0 (x = 0), mọi giá trị âm thành số âm khác 0; bảng hard-swish đưa
x ≤ −78 (số thực ≤ −3) về 0 nên còn giữ khoảng 14 % số 0 ở input Conv3; ReLU đưa mọi số âm về 0.

**Vì sao Leaky ReLU không cần bảng.** Bộ lượng tử vốn đã nhân: đầu ra ≈ psum × M (M = s_in·s_w / s_next = mant / 2^shift). Leaky ReLU là hai đoạn thẳng
(f(x) = x khi x ≥ 0, 0,1·x khi x < 0), nên psum ≥ 0 dùng psum × M, cặp (8.817.157, 31) ở Conv1 (trước #38: (135, 15)), và psum < 0 dùng psum × 0,1·M, cặp (215, 19): vẫn chỉ là
một phép nhân, khác hệ số. Phần cứng chỉ cần **cặp hệ số thứ hai** `act_neg_mant` (8 bit) và `act_neg_shift` (7 bit), nằm trong các bit trống của word cấu
hình: 0 word DMA, 0 chu kỳ. SiLU và hard-swish là **đường cong** (sigmoid cần hàm mũ và phép chia; hard-swish kẹp rồi nhân với chính x), không viết được
thành "psum × hằng số" cho mỗi dấu; tính thật cần nhiều DSP và nhiều tầng, còn input chỉ có 256 giá trị nên tra bảng cho kết quả chính xác và rẻ hơn.

**3 tầng của bộ lượng tử** (`hdl/quantization_unit.v`; 4 bộ chạy song song = 4 lane ghi ngược, `WRITEBACK_WORDS`). Mỗi chu kỳ FSM psum
(`SEND_PSUM_TO_IACT`) đọc 4 psum từ bộ đệm vào `pre_quantized_value`, rồi mỗi psum đi qua 3 tầng thanh ghi:

```
psum (20 bit)
  │
  ▼  TẦNG 1  (thanh ghi sum_s1, mant_s1, shift_s1, round_s1)
  │    sum = psum + offset (offset = 0)
  │    Leaky: bit dấu của sum chọn (neg_mant, neg_shift) hay (mant, shift)    ← bộ chọn 2:1
  ▼  TẦNG 2  (thanh ghi prod_s2)
  │    prod = mant × sum + hằng_số_làm_tròn, hằng số = 2^(shift−1) nếu act_round   ← 1 DSP: nhân + cộng
  ▼  TẦNG 3  (thanh ghi quantized_value)
  │    q = kẹp(prod >>> shift, act_min, 127)        (ReLU: act_min = 0)
  ▼
  [chế độ bảng] T[q + 128]: chỉ số = q với bit dấu đảo, đọc LUTRAM không cần clock, trong cùng chu kỳ (psum_pipeline.v: quant_result)
  ▼
FSM chính chép vào iact_to_psum_mux_reg ở cạnh clock kế tiếp → đóng gói → bộ đệm iact của layer sau
```

Cùng psum = −5000 ở Conv1 (hệ số 24 bit từ bản sửa #38; với hệ số 8 bit cũ (216, 16), (151, 16) kết quả y hệt):

| | Tầng 1 | Tầng 2 | Tầng 3 | Bảng | Ra |
|---|---|---|---|---|---:|
| ReLU | (14.166.994, 32), không làm tròn | 14.166.994·(−5000) = −70.834.970.000 | >>32 = −16,49 → −17 → kẹp ở 0 | — | **0** |
| Leaky | dấu âm → (215, 19), làm tròn | −1.075.000 + 2^18 = −812.856 | >>19 = −1,55 → −2 | — | **−2** |
| SiLU | (9.899.939, 32), làm tròn | −49.499.695.000 + 2^31 = −47.352.211.352 | >>32 = −11,03 → −12 | ô 116: bank 4, địa chỉ 14 = −8 | **−8** |

**Vì sao hàm kích hoạt không tốn thêm chu kỳ ở pha ghi ngược:**
1. **Pipeline:** mỗi tầng là một thanh ghi; mỗi chu kỳ 4 psum mới vào tầng 1, trong khi 4 psum trước ở tầng 2 và 4 psum trước nữa ở tầng 3. Mỗi giá trị luôn
   mất đúng 3 chu kỳ nhưng vẫn ra 4 giá trị mỗi chu kỳ, dù mỗi tầng làm nhiều hay ít việc. FSM chính đã chờ đúng 3 chu kỳ này từ trước khi có hàm kích hoạt.
2. **Hàm kích hoạt chen vào các tầng có sẵn, không thêm tầng:** bộ chọn độ dốc của Leaky nằm trước thanh ghi tầng 1 (bit dấu có ngay trong chu kỳ đó);
   phép cộng làm tròn dùng bộ cộng của DSP ở tầng 2; tra bảng là đọc LUTRAM không clock giữa thanh ghi tầng 3 và thanh ghi nhận của FSM chính. Vẫn 3 chu kỳ
   trễ, 4 giá trị mỗi chu kỳ, nên pha ghi ngược giữ nguyên 11.948 chu kỳ (mục 6.15).
3. **Điều kiện:** logic thêm phải chạy kịp trong một chu kỳ 4 ns. Vivado xác nhận kịp (WNS +0,045 ns, các đường của hàm kích hoạt không nằm trong nhóm đường
   chậm nhất). Nếu không kịp thì phải thêm tầng thứ 4 (phương án dự phòng trong thiết kế), và mỗi lượt ghi ngược sẽ chậm thêm 1 chu kỳ.

### Điều tra 3 cấu hình CR 1 còn FAIL của Bảng 3 (2026-11-03, không sửa RTL)

Chi tiết: `doc/experiments/2026-11-03_table3_cr1.md`; script: `doc/experiments/2026-11-03_table3_cr1/` (`run.py`: chạy một model với testbench nguyên bản
qua probe `probe_t3.py`, mọi CR / X / Y, tham số `BWW` = `BUFFER_WIDTH_WGHT`; `params.py`: tham số layer không cần mô phỏng; `analyze_px*.py`, `mapfit.py`).
Không sửa file nào của RTL; các "bản sửa" dưới đây chỉ là tham số build hoặc ép tín hiệu trong mô phỏng.

| Cấu hình | Lỗi |
|---|---|
| CR 1 X 4 Y 3 | **#29**: tràn bộ đệm weight ở Dense 1568→32 (trước đây ghi nhầm là #19b) |
| CR 1 X 2 Y 4 | **#28**: thu psum khi cột PE lẻ chưa tính xong (Conv) + **#36**: Dense cuối mất output của cụm cột 1 |
| CR 1 X 2 Y 3 | **#29 + #28 + #36** |

**#29: bộ đệm weight 4.096 hàng bị tràn.** `GET_WGHT` (`OpenEye_FPGA.v`) ghi mỗi `WGHT_ONE_WORD_ALL_RAM` word DMA thành một hàng của `wght_buffer`
(`BUFFER_WIDTH_WGHT` = 12 bit, 4.096 hàng); con trỏ `wght_buffer_wr_addr` quay vòng mà không ai kiểm tra. Mỗi hàng chứa `2 × CLUSTERS × NUM_GLB_WGHT` weight
(12 ở CR 1 Y 3). Dense nạp weight của mọi lượt K một lần: 1568 → 32 ở CR 1 Y 3 = 44 lượt × 96 hàng = **4.224 hàng**, 128 hàng cuối ghi đè lên weight của khoảng
48 input đầu, nên cả 32 output lệch một chút. Trong 16 cấu hình chỉ CR 1 Y 3 vượt 4.096 (Y 4: 3.168, CR 2: 2.112). Kiểm chứng: probe con trỏ ghi:
1512 → 32 = 4.032 hàng, 0 lần quay vòng, PASS; 1520 → 32 = 4.128 hàng và 1568 → 32 = 4.224 hàng, quay vòng 1 lần, FAIL; đặt 0 cho 72 input đầu (phần bị ghi đè)
thì PASS dù vẫn tràn, đặt 0 khối giữa thì FAIL; `BUFFER_WIDTH_WGHT=13`: cả mạng CR 1 X 4 Y 3 **PASS đủ 7 layer** (133.190 chu kỳ, mốc 133.193). Đây cũng
chính là #29 cũ: Dense 3136 → 32 ở cấu hình MNIST (CR 2 X 4 Y 3) = 4.224 hàng, FAIL; với 13 bit PASS; 2560 → 32 = 3.456 hàng, PASS. #19b (K = 508) là lỗi khác:
khi đó con trỏ đọc chỉ tới 768 hàng.
Hướng sửa: (1) Python kiểm tra số hàng ≤ `2^BUFFER_WIDTH_WGHT` và từ chối layer với thông báo rõ (nên có trong mọi trường hợp); (2) `BUFFER_WIDTH_WGHT = 13`
(tham số có sẵn, không sửa logic; ước tính +4 URAM ở cấu hình tổng hợp, cần Vivado xác nhận; Dense 3136 → 64 cần 14 bit); (3) lâu dài: nạp weight Dense theo nhóm lượt K.

**#28: ở `CLUSTER_ROWS = 1`, FSM psum bắt đầu thu khi cột PE lẻ chưa xong.** `psum_pipeline.v`: khối tạo `chain_ready_terms` → `all_psum_ready` lặp theo cặp GLB
và chỉ đọc `psum_ready_o_reg[... + rr_g*2]` (GLB chẵn); chú thích của chính nó nói ở CR 1 mọi cột PE là đầu chuỗi, nhưng cột lẻ (cột 1 của mỗi cụm khi X = 2) không
được xét. Các hàng PE của một cột chuyền psum lên theo lịch cố định cách nhau 3 chu kỳ; nếu cột lẻ xong muộn từ 3 chu kỳ trở lên, PE hàng 1 bắt đầu cùng lúc với hàng 2
và bỏ mất psum của hàng 2: một pixel sai ở mọi filter. Cột lẻ của cụm 1 tính pixel cuối của lượt x 4 pixel nên lỗi luôn ở x = 3 hoặc 7. Thời gian tính của PE phụ thuộc
số số 0 bị bỏ qua, nên lỗi phụ thuộc dữ liệu (đổi chỗ theo seed; Conv đơn lẻ dữ liệu ngẫu nhiên thường đúng). Các bước khoanh vùng: đổi seed (pixel (7,1) / (3,7) /
(3,1), (3,4), (3,9)); bơm dữ liệu conv2 vào Conv đơn lẻ tái hiện đúng (X 4 và CR 2 đúng); bỏ số 0 của iact thì hết lỗi, số 0 ngoài cửa sổ cũng ảnh hưởng (hiệu ứng
thời gian); so luồng dữ liệu 12 PE: PE cụm 1 cột 1 nhận đúng cùng word iact nhưng ra psum khác; trace trạng thái: lúc bắt đầu thu, PE hàng 2 của cột đó còn đang tính
(`pe_rdy_out=01`), sau đó hàng 1 bắt đầu cùng lúc với nó; bit ready lúc bắt đầu thu = `0111` ở đúng lượt sai (36–68 lần trên 448 lượt ở dữ liệu lỗi, 0 lần ở X 4 / CR 2).
Giả lập bản sửa (ép `all_psum_ready` = AND cả 4 bit, chỉ trong mô phỏng): mọi bộ dữ liệu lỗi PASS; mạng CR 1 X 2 Y 3 / Y 4 qua mọi kiểm tra bộ đệm L0–L5;
chu kỳ 0 (X 4 Y 4) đến ±16. Hướng sửa RTL (chờ đồng ý): ở `CLUSTER_ROWS == 1` lấy `psum_ready_o_reg[GLB] & psum_ready_o_reg[GLB+1]` cho mỗi cặp (khối generate
`gen_pair`), CR ≥ 2 giữ nguyên mạch (mọi ca mốc là CR 2). `chain_enable_terms` cùng cấu trúc nhưng không cần sửa (giả lập không đổi gì).

**#36: Dense đọc ra cuối mất output của cụm cột 1 (CR 1 X 2).** `psum_pipeline.v`: `psum_readout_src` và `psum_buffer_data_temp_reg` rộng
`TRANS_BITWIDTH_PSUM × CLUSTERS × NUM_GLB_PSUM` = 80 bit; khi đọc Dense, kết quả của cụm cột cc đặt ở bit cc × 64, cc = 1 cần bit 64–83 > 80 nên điều kiện bảo vệ bỏ qua và
các output đó ra 0 (Dense 32 → 10: cụm 0 giữ f 0–5, cụm 1 giữ f 6–9 → f 6–9 = 0; N = 6, 7 cũng vậy). CR 1 X 4 và CR 2: 160 bit, đúng. Trace bước thu kết quả cho thấy
giá trị f 6–9 được ghi đúng vào bộ đệm, chỉ mất khi đọc ra. Hướng sửa RTL (chờ đồng ý): hai thanh ghi rộng `max(TRANS_BITWIDTH_PSUM × CLUSTERS × NUM_GLB_PSUM,
CLUSTER_COLUMNS × DMA_BITWIDTH)`, `psum_readout_src` = `psum_buffer_data_r` thêm bit 0; đường đọc Conv không đổi; khoảng +48 FF chỉ ở CR 1 X 2.

**Phát hiện phụ #37:** Conv 14×14×32 → 32 ở CR 1 X 2 ra toàn bias vì `iact_buffer_words_per_write` và `iact_write_inc_2` = 4.096 không vừa trường 12 bit
(24/28 channel đúng). Không thuộc Bảng 3; ghi chú cũ của #28 trộn lỗi này vào.

**Upstream:** `upstream/main` vẫn là `93f0e82` (29/10), không branch nào có commit mới hơn. Code upstream có đủ cả 3 lỗi (bộ đệm weight 12 bit không kiểm tra; vòng
`results_ready` chỉ xét `g_psum*2`; `psum_readout_src` cùng độ rộng). Commit "mở rộng" gần nhất `655a2ae` ("Fixed adresses and ranges for bigger Nets and input
activations") chỉ nới các trường/bộ đếm (`trans_cycles_*` 24 bit, `iact_read/write_limit_*` 12–18 bit, vòng psum 12 bit, bước tăng iact `BUFFER_WIDTH_IACT` bit),
không động tới bộ đệm weight, điều kiện ready hay thanh ghi đọc ra: **không giải quyết #28, #29, #36**, và cả #37 với bộ đệm iact 12 bit. Lần chạy upstream ngày 31/10
cũng đã cho thấy #28 và #29 sai trên upstream.

Kế hoạch (mục 8c hàng N): được bạn đồng ý và **đã làm cùng ngày**, mục tiếp theo.

### Sửa #28, #29, #36 (2026-11-03, được bạn đồng ý)

Chi tiết: `doc/experiments/2026-11-03_table3_cr1.md` (mục "Fixes"). Ba lỗi, bốn chỗ sửa; mọi cấu hình CR ≥ 2 giữ nguyên mạch (#28) hoặc giữ nguyên độ rộng
(#36), nên 12 ca mốc và 13 cấu hình Bảng 3 vốn đúng không lệch chu kỳ nào.

**1. #29, độ sâu bộ đệm weight 12 → 13 bit.** `open_eye_parameters.py` (mặc định `BUFFER_WIDTH_WGHT = 13`), `OpenEye_FPGA.v` (giá trị mặc định của tham số, chỉ
để thống nhất: `parameters_FPGA.vh` sinh ra luôn ghi đè), `export_vivado.py` (ghi rõ 13 vào cấu hình). Bộ đệm `wght_buffer` từ 4.096 lên 8.192 hàng, con trỏ ghi / đọc
13 bit. Không có logic nào đổi: `RAM_SP` của bộ đệm vốn lấy `AddrWidth = BUFFER_WIDTH_WGHT`. Trường `used_wght_per_PE` trong `regmap.yaml` rộng `BUFFER_WIDTH_WGHT`
bit nên dài thêm 1 bit, nhưng số word trạng thái vẫn 28 / 14 / 7 ở DMA 32 / 64 / 128 bit (đã tính bằng `generator.regmap_transmissions` cho mọi tổ hợp CR 1/2,
X 2/4), nên 0 chu kỳ nạp thêm. **Kiểu bộ nhớ:** lần Vivado đầu với 13 bit, Vivado tự đặt bộ đệm vào 64 RAMB36 + 845 LUT bộ chọn (BRAM 192 → 256 tile = 82 %,
URAM 8 → 4); nên thêm tham số `RamStyle` cho `RAM_SP` / `RAM_SP_generic` (mặc định `"auto"` = Vivado tự chọn như cũ, chỉ là thuộc tính `ram_style` của mảng nhớ,
trình mô phỏng bỏ qua; Verilator được tắt cảnh báo tham số không dùng) và `wght_buffer` đặt `RamStyle("ultra")`: 8.192 hàng nằm trong URAM như 4.096 hàng trước.

**2. #29, toolchain từ chối layer không vừa bộ đệm.** `layer_parameters.py`: `wght_buffer_rows(params, words)` = `ceil(words / ceil(Clusters × 24 ×
NUM_GLB_WGHT / DMA_BITWIDTH))` (đúng phép ghép hàng của `GET_WGHT`: 3 word mỗi hàng ở CR 1 Y 3, 5 ở CR 2 Y 3) và `check_wght_buffer(params, words, tên)`
ném `NotImplementedError` khi số hàng > `2^BUFFER_WIDTH_WGHT`. `conv_mapper.py` gọi nó với `trans_cycles_wght` của stream, `dense_mapper.py` với độ dài stream
weight thật, ngay trước khi đóng gói word trạng thái. `test_utils_main.py`: stream được tạo trong process con, trước đây lỗi trong đó bị mất (process chính chỉ
thấy `KeyError: 0`); nay process con ghi lại thông báo và `write_stream` ném lại `RuntimeError` với nội dung gốc (cũng có ích cho `check_rtl_activation`). Ví dụ
với 12 bit: `RuntimeError: stream generation of Dense failed: NotImplementedError: Dense weights need 4224 rows of the weight buffer (12672 DMA words), it
has 4096 (BUFFER_WIDTH_WGHT=12); raise BUFFER_WIDTH_WGHT or split the layer`.

**3. #28, điều kiện "mọi chuỗi psum sẵn sàng" ở `CLUSTER_ROWS = 1`.** `psum_pipeline.v`, khối generate tạo `chain_ready_terms`:

```verilog
if ((CLUSTER_ROWS == 1) && (rr_g*2 + 1 < NUM_GLB_PSUM)) begin : gen_pair_ready
  assign chain_ready_terms[TERM] = psum_ready_o_reg[GLB] & psum_ready_o_reg[GLB+1];
end else begin : gen_even_ready
  assign chain_ready_terms[TERM] = psum_ready_o_reg[GLB] | not_chain_start;
end
```

Ở CR 1, mỗi cặp GLB giờ chỉ "sẵn sàng" khi **cả hai** cột PE xong, nên FSM psum (`CALCULATE_PSUM`) không còn bắt đầu thu khi cột lẻ đang tính; các hàng PE của cột
đó chuyền psum lên đúng nhịp 3 chu kỳ. CR ≥ 2 (và cặp chỉ có một GLB khi `NUM_GLB_PSUM` lẻ) đi nhánh `gen_even_ready` = đúng biểu thức cũ, nên mạch không đổi.
`chain_enable_terms` giữ nguyên (giả lập sửa nó không đổi gì). Chi phí: một cổng AND mỗi cặp. Chu kỳ: các layer Conv của CR 1 X 2 lệch 0 (cột chậm nhất vốn đã
quyết định thời gian của lượt).

**4. #36, độ rộng thanh ghi đọc ra.** `psum_pipeline.v`:

```verilog
localparam PSUM_BUS_WIDTH = TRANS_BITWIDTH_PSUM*CLUSTERS*NUM_GLB_PSUM;
localparam READOUT_WIDTH  = (CLUSTER_COLUMNS*DMA_BITWIDTH > PSUM_BUS_WIDTH) ? CLUSTER_COLUMNS*DMA_BITWIDTH : PSUM_BUS_WIDTH;
reg [READOUT_WIDTH-1:0] psum_buffer_data_temp_reg;
reg [READOUT_WIDTH-1:0] psum_readout_src;   // = psum_buffer_data_r mở rộng bằng bit 0; Dense: kết quả cụm cột cc ở bit cc*DMA_BITWIDTH
```

Ở CR 1 X 2: 80 → 128 bit, kết quả của cụm cột 1 (bit 64–83) giờ có chỗ và được đọc ra ở word DMA thứ hai. Mọi cấu hình khác: `READOUT_WIDTH` = độ rộng cũ.
Đường đọc Conv (`psum_dma_word` lấy `CONV_DMA_PAYLOAD_WIDTH` bit thấp, dịch theo đó) không đổi vì phần thêm toàn 0.

**Test mới:** `test/cocotb_fpga/test_cluster_rows1.py` (Dense 32 → 10 ở CR 1 X 2: #36; Dense 1568 → 32 → 10 ở CR 1 X 4 và X 2: #29, #36; mạng paper CR 1 X 2 Y 3:
#28, #29, #36), `test/test_wght_buffer.py` (số hàng, phép kiểm tra ở đúng giới hạn, mặc định 13).

| Kiểm chứng | Kết quả |
|---|---|
| `test_cluster_rows1.py` trên code chưa sửa (đối chứng âm) | 4/4 FAIL: Dense 32 → 10 sai 4/10, Dense 1568 → 32 sai kiểm tra bộ đệm (X 2 và X 4), mạng paper sai sau layer 3 |
| ... sau bản sửa | **4/4 PASS** (mạng paper CR 1 X 2 Y 3 đủ 7 layer, 238 s) |
| 3 bộ dữ liệu conv của #28 (seed 1, 2, 3; không giả lập) | PASS |
| Dense 1520 → 32 (4.128 hàng) | PASS, 0 lần quay vòng |
| `BUFFER_WIDTH_WGHT=12` với Dense 1568 → 32 | toolchain từ chối trước khi chạy, thông báo số hàng (ở trên) |
| Hồi quy RTL: 180 test cũ + 4 test mới = 184 | **179 PASS + 5 xfail đã biết, 0 FAIL** |
| 12 ca mốc (`run_profile --compare doc/perf/baseline_2026-11-02`) | **12/12, 0 chu kỳ, 0 word DMA lệch** |
| Bảng 3, 16 cấu hình (`doc/perf/paper_table3_2026-11-03`, mốc mới) | **16/16 PASS** (trước 13/16); 13 cấu hình cũ giống hệt từng chu kỳ; CR 1 X 2 Y 3 −16, CR 1 X 2 Y 4 +16, CR 1 X 4 Y 3 −3 |
| Unit test Python | 328 pass (+4), 11 fail có từ trước |
| Lint | `fpga` 460 → **459** (0 mới), `parallel` 36; đã hạ baseline |
| Vivado 4 ns (`doc/synth/2026-11-03_route4ns_cr1fix_zu7ev/`) | **0 CRITICAL**, cảnh báo y như trước; WNS +0,211 / **+0,075 ns** (đạt 250 MHz); URAM 8 → 12, FF +288 (bộ đệm), BRAM 192, LUT không tăng; ở cấu hình tổng hợp (CR 2 X 4) #28 và #36 sinh đúng mạch cũ |

### Sửa #38: mantissa của hệ số lượng tử lại bị cắt còn 8 bit (2026-11-04, được bạn đồng ý)

Chi tiết: `doc/experiments/2026-11-04_bug38_mantissa.md`. Mỗi entry bảng lượng tử gồm offset 8 + exponent 7 + mantissa 25 bit, bộ lượng tử nhân với mantissa
25 bit có dấu, nhưng `OpenEye_FPGA.v` cắt các trường từ `quant_reg` sai độ rộng:

```verilog
assign quant_exp[f]  = quant_reg[OFFSET_WIDTH + base +: OFFSET_WIDTH];                 // cũ: 8 bit vào dây 7 bit
assign quant_mant[f] = quant_reg[OFFSET_WIDTH + EXPONENT_WIDTH + base +: OFFSET_WIDTH]; // cũ: 8 bit vào dây 25 bit
// sửa: +:EXPONENT_WIDTH và +:MANTISSA_WIDTH
```

Exponent tình cờ đúng (8 bit gán vào dây 7 bit, bit thừa là bit 0 của mantissa bị bỏ), còn mantissa mất bit 8–24: hệ số `mant ≥ 256` thành `mant mod 256`.
Verilator đã báo đúng hai dòng này từ lâu (`WIDTHEXPAND`, `WIDTHTRUNC` trong baseline lint). Không test nào phát hiện vì toolchain cố ý giữ mantissa < 256
(`onnx2model.MANT_BITS = 8`) và model ngẫu nhiên dùng hệ số 1.

**Các chỗ sửa:**
- `hdl/OpenEye_FPGA.v`: lát cắt `+:EXPONENT_WIDTH`, `+:MANTISSA_WIDTH`.
- `src/open_eye/onnx2model.py`: `MANT_BITS` 8 → **24** (mantissa có dấu 25 bit nên tối đa 24 bit; cũng đúng bằng phần định trị của float32, nên hệ số của phần cứng
  trùng hệ số float32 mà ONNX Runtime dùng); `hardware_multiplier` đọc `MANT_BITS` lúc gọi; độ dốc âm Leaky giữ 8 bit (`NEG_MANT_BITS`, trường `act_neg_mant`
  8 bit). Đường dữ liệu đã đủ rộng: tổng 21 bit × mantissa 24 bit < 2^45 trong tích 46 bit; shift của các model đã huấn luyện thành 31–35 (trước 15–19), dưới
  giới hạn làm tròn 45. Sai số của hệ số giảm từ tới 0,2 % (ví dụ 220/2^16 cho 0,0033496: −0,22 %) xuống dưới 10⁻⁷.
- `src/open_eye/data_create.py`: móc test `OPENEYE_QUANT_MANT=<m>` đi cùng `OPENEYE_QUANT_SHIFT=<s>`.
- Test mới `test/cocotb_fpga/test_quant_mantissa.py`: Conv → Conv với mantissa 17 bit (127.909, shift 23) và 24 bit (11.920.113, shift 29), Dense → Dense
  với mantissa 24 bit. Sửa kỳ vọng trong `test_onnx_model_flow.py`, `test_activation.py`. Script đo độ chính xác `doc/experiments/2026-11-04_bug38/precision.py`.

| Kiểm chứng | Kết quả |
|---|---|
| `test_quant_mantissa.py` trên RTL cũ (đối chứng âm) | 3/3 FAIL: mọi output là 0x00 hoặc 0xff (hệ số mod 256 với shift 23/29 gần như 0), tham chiếu trải khắp dải int8 |
| ... sau bản sửa | **3/3 PASS** |
| Hồi quy RTL: 184 test + 3 test mới = 187 | **182 PASS + 5 xfail đã biết, 0 FAIL**; 8 test model đã huấn luyện (giờ mantissa 24 bit) khớp từng bit |
| 12 ca mốc (`doc/perf/baseline_2026-11-02`) | 12/12 giống hệt: 0 chu kỳ, 0 word DMA lệch (các ca mốc dùng hệ số 1, không chạm mantissa ≥ 256) |
| Model đã huấn luyện ảnh 0 (cả 4 hàm), chu kỳ (`doc/perf/activation_2026-11-04_mant24.md`) | ReLU 218.925 → 218.924 (−1, ở layer Dense), Leaky ReLU 238.049 (0), SiLU 240.229 → 240.230 (+1, ở Dense), hard-swish 240.293 → 240.287 (−6, ở Dense); 4/4 PASS khớp từng bit; tỉ lệ số 0 ở input các layer gần như không đổi (SiLU conv3 7,2 → 7,1 %, Dense 6,6 → 6,7 %): input của Dense (output conv3) khác vài giá trị làm tròn, vài ô đổi giữa 0 và khác 0, mà PE bỏ qua số 0, nên Dense lệch 1 chu kỳ |
| So với ONNX Runtime (4 model × 20 ảnh) | gần hơn một chút: tỉ lệ khớp đúng tăng tới +0,9 điểm mỗi layer; lệch lớn nhất 3 → 2 (ReLU conv3), 2 → 1 (SiLU conv1), 3 → 1 (hard-swish conv1); phân loại 20/20 ở cả hai. Phần lệch còn lại do làm tròn (ReLU làm tròn xuống, ONNX Runtime làm tròn hai lần cho SiLU/hard-swish) |
| Unit test Python | 328 pass, 11 fail có từ trước |
| Lint | `fpga` 459 → **457** (hết đúng 2 cảnh báo của hai lát cắt), 0 mới |
| Vivado 4 ns (`doc/synth/2026-11-04_route4ns_fix38_zu7ev/`, **mốc phần cứng mới**) | **0 CRITICAL**, cảnh báo y như trước; WNS +0,211 / **+0,044 ns** (đạt 250 MHz); BRAM / URAM / DSP 192 / 12 / **4 như cũ**; mỗi bộ lượng tử +69 LUT, +17 FF (bộ nhân 25 × 21 bit: 1 DSP + phần còn lại bằng LUT; thanh ghi mantissa 8 → 25 bit); tổng LUT +293, FF +85 sau route. Đường xấu nhất sau route là địa chỉ psum → BRAM psum (đi dây), không qua bộ lượng tử |

### Sửa #37, #17 (hàng O, chép từ upstream `9498271` / `36395dd`) và #39 (2026-11-04, được bạn đồng ý)

Chi tiết: `doc/experiments/2026-11-04_rowO_bug17_bug37.md` (điều tra upstream: `doc/experiments/2026-11-04_upstream_36395dd.md`). Không gộp commit
upstream; chép từng ý lên code của `dev`.

**#37 – trường cấu hình của bộ đệm iact chỉ 12 bit.** Mỗi `iact_stream_constructor` có bộ đệm iact 8.192 word (địa chỉ 13 bit), nhưng các trường trỏ vào
nó (`iact_buffer_words_per_write`, `iact_read_inc_0..4`, `iact_write_limit_0`, `iact_write_inc_0..2`), cổng của constructor và các thanh ghi địa chỉ
`wr_addr_*`, `rd_addr_*` chỉ 12 bit. Conv 14×14×32 → 32 ở CR 1 X 2 cần ghi 4.096 word mỗi lượt: trường nhận 0, bộ ghi dừng ngay khi bộ đếm word bằng giá
trị đó, không ghi gì, mọi output = bias. Verilator đã báo các chỗ lệch 12/13 bit từ lâu. Sửa:
- RTL: `localparam IACT_BUFFER_ADDR_WIDTH = 13` trong `OpenEye_FPGA.v` (thay số 13 viết cứng), 10 dây và các cổng / thanh ghi địa chỉ tương ứng của
  constructor rộng 13 bit.
- `regmap.yaml`: 10 trường 12 → 13 bit. Để số word trạng thái không đổi, 4 trường kích hoạt cuối stream (`act_neg_mant`, `quant_clamp_low`,
  `act_neg_shift`, `act_round`, 24 bit) chuyển vào chỗ trống của word 1, 2, 5: vẫn 28 / 14 / 7 word ở DMA 32 / 64 / 128 bit với cả 96 cấu hình
  CR 1–4 × CC 1–4 × DMA × BRANCHES 1–2 (không chuyển thì 34 cấu hình thêm 1 word).
- Python: `check_iact_buffer` từ chối layer cần quá 8.191 word mỗi lượt (như `check_wght_buffer` của #29). Không kiểm tra chung mọi trường: quét
  giá trị thật cho thấy vài trường tràn sẵn ở cấu hình đang đúng (`needed_x_cls_reg`, `start_param_array`, `iact_write_inc_1`, `psum_pagu_cs_limit_2`)
  vì không dùng hoặc dùng đúng giá trị đã cắt.

**#17 – 1 channel, ảnh rộng hơn một lượt x.** Constructor gói 2 hàng ảnh vào 1 word (hàng 2k ở sub-word 0, hàng 2k+1 ở sub-word 1) theo địa chỉ chỉ tính
từ hàng và cột, nên các lượt x đè lên nhau; `data_pipeline_iact` trong PE có logic "dòng lệch" để đọc xen kẽ sub-word. Sửa như upstream: bỏ cách gói
cặp hàng, mỗi pixel 1 word (giá trị ở sub-word 0, các sub-word khác 0), ghi / đọc bằng đúng các vòng địa chỉ của nhiều channel; PE lấy sub-word 0
(`cycle_counter` quay về 0 sau mỗi sub-word khi `first_spad_max_i == 1`); xoá phần "dòng lệch" và bộ ghi cặp hàng; `stride_y_i`,
`iact_x_line_repetitions_i` thành cổng không dùng (miễn lint). Giữ của `dev` (upstream bỏ): bước nhảy `NUM_GLB_IACT − 1` sau mỗi lần đọc 1 channel
(cần cho `NUM_GLB_IACT` 3) và công thức `iact_read_inc_2` cũ. `channel_pad` tắt mặc định (`OPENEYE_PAD_CHANNELS=1` bật lại).

**#39 – phát hiện trong lúc kiểm chứng (Python, có từ trước, upstream cũng có).** Lần hồi quy đầy đủ đầu tiên sau khi tắt đệm channel có 10 FAIL, đều là
layer 1 channel 28×28 với 32 filter (8 test model đã huấn luyện, `test_random_data[28x28_c1_f32]`, `test_trained_mnist_conv[conv1]`); test ramp
`test_mnist_conv[conv1]` vẫn PASS vì weight hằng số giống nhau ở mọi filter nên che lỗi (như #18). Khoanh vùng: hỏng khi **1 channel và từ 2 lượt weight**
(28×28×1 → 32, 40×8×1 → 32, 8×4×1 → 64), đúng với 8/16 filter hay 2 channel; RTL cũ cũng hỏng (8×4×1 → 64: 64/64 sai), upstream `36395dd` hỏng y hệt `dev`
mới. Hồi quy kernel hiệu dụng của từng output sai: filter 16–31 được tính **đúng bằng kernel của filter 0–15**, bias đúng. Probe RTL
(`doc/experiments/2026-11-04_bug39/probe39.py`): phần đếm lượt và địa chỉ đọc bộ đệm weight đúng (lượt 0 đọc hàng 0–23, lượt 1 hàng 24–47), nhưng stream
weight chỉ có 1 lượt: `trans_cycles_wght` = 120 word ở cả 32 và 64 filter (2 channel: 240 → 480). Nguyên nhân: `LayerParameters`, nhánh "hơn 16 filter
mỗi lần tính" đặt `wght_transmissions_pe = ceil(channels / channel_div_trans)` = số lô channel, không phải số nhóm filter (đúng tình cờ với 2 channel và
≥ 4 channel). Sửa: số lô channel × số nhóm filter (= `needed_wght_cycles` × `iact_transmissions_pe`, đúng số bộ weight RTL đọc). Trên 315 cấu hình
(CR 1, 2, 4) chỉ layer 1 channel nhiều lượt weight đổi tham số.

**#39, điều tra thêm và phép kiểm tra (2026-11-05, `doc/experiments/2026-11-05_bug39_detail.md`).** Quét 2.880 cấu hình mỗi kernel (16 nền tảng của Bảng 3,
1–64 channel, 4–128 filter, `doc/experiments/2026-11-04_bug39/grid39.py`): với kernel 3×3 lỗi xảy ra đúng khi **1 channel và hơn 16 filter mỗi lần tính**
(ngưỡng 24 filter ở hầu hết nền tảng với ảnh 28×28, 48–96 với ảnh hẹp và nhiều cụm; MNIST Conv1 bị ở mọi nền tảng trừ CR 8 X 4, layer 0 của mạng paper
không bao giờ). RTL không sai phép tính (nhóm filter có weight 0 ra đúng bias) nhưng tin độ dài stream của host: ở lượt thiếu nó đọc 26/26 hàng chưa ghi,
trong mô phỏng là X nên SPAD weight giữ weight lượt trước, trên FPGA sẽ là 0 hoặc weight còn sót. Chưa từng làm sai kết quả đã commit (trước 22/10 Conv1
hỏng vì #17, sau đó được đệm 2 channel, vô tình đúng). **Phép kiểm tra `check_wght_sets`** (Python, `ConvMapper`): từ chối layer có số bộ weight ≠ số lượt
weight × số lô channel. Còn **#39b** ở nhánh tile (số psum mỗi PE làm tròn xuống, số weight làm tròn lên: 3 channel × 64/96/128 filter, nhiều layer 1×1 và
7×7): nay bị từ chối; mọi cấu hình đó vốn hỏng vì lý do khác (#7, 1×1 treo, 7×7 vướng bộ mã hoá weight), nên sửa sau cùng các lỗi đó. **Upstream:**
`36395dd` có đúng lỗi này (178 cấu hình như `dev` cũ; vá công thức thì 8×4×1 → 64 và 28×28×1 → 32 PASS), `b10db82` (04/11, 32 psum mỗi PE) thu hẹp còn
118 cấu hình (1 channel hơn 32 filter mỗi lần tính: FAIL toàn bộ map; vá công thức thì treo, xem đoạn dưới). Hồi quy với phép kiểm tra: 189 test = 185 PASS + 4 xfail, 0 FAIL (giống trước, không chặn layer nào đang chạy được); unit test 369 pass; không đổi RTL, mốc chu kỳ
và mốc phần cứng giữ nguyên.

**Lỗi treo của `b10db82` và lỗi #40 (2026-11-05, chỉ điều tra, `doc/experiments/2026-11-05_b10db82_hang.md`, script
`doc/experiments/2026-11-05_b10db82_hang/`).** Treo không do 1 channel hay 32 psum: `b10db82` + công thức #39 PASS với 8×4×1 → 128 và 28×28×1 → 64
(2 lượt đầy), chỉ treo khi **lượt weight cuối thiếu filter** (8×4×1 → 96 = 64 + 32, 28×28×1 → 48 = 32 + 16). Lần theo một PE: ở lượt 2 nó nhận SPAD
weight 2 word địa chỉ, 9 word dữ liệu (ca chẵn: 3 và 48), nên vòng MAC (trạng thái CALCULATING) không bao giờ kết thúc. Nguyên nhân: mapper upstream
ghi weight của các filter đệm (96–127) thành số 0 tường minh (48 mục 0, 24 word toàn 0, chuỗi 16 số 0), mà `data_pipeline_wght.v` coi word toàn 0 là
phần đệm stream và trường overhead chỉ 4 bit; đây là cơ chế **#22** mà fork đã sửa bằng `conv_wght_encoding.py`, upstream thì chưa. `36395dd` + công
thức #39 với ca lẻ (28×28×1 → 24, 8×4×1 → 48): cũng treo, cùng dấu hiệu, nên không liên quan 32 psum. Trên `dev` các ca lẻ không treo nhưng vẫn FAIL toàn bộ map: lỗi mới **#40** (Python, có cả ở upstream). RTL tính đúng,
nhưng `psum_output_words` và `trans_cycles_psum` đếm số filter thật trong khi RTL tính và gửi cả ô filter đệm, nên RTL dừng gửi sớm (28×28×1 → 24:
10.752/14.336 word, 4.704/18.816 output không ra); tham chiếu testbench (`filter_cycles` làm tròn xuống) cũng sai. Giải mã theo thứ tự đã đệm: 14.112/14.112
(28×28×1 và 28×28×2 → 24), 1.152/1.152 (8×4×1 → 48) giá trị bằng numpy; đối chứng 28×28×1 → 48 (3 lượt đầy) PASS. Hồi quy, Bảng 3, MNIST đều chia chẵn
nên không kết quả nào đã commit bị ảnh hưởng. Hướng sửa #40 (Python): (1) phép kiểm tra từ chối layer lẻ; (2) chọn số psum mỗi PE để các lượt
đầy (24 → 12 + 12…), đỡ cả phép tính thừa trên ô đệm (25 % ở 16 + 8); (3) đệm trong toolchain (đếm ô đệm ở số word output/bias, sửa tham chiếu).

**Phép kiểm tra `check_full_passes` cho #40 (2026-11-05, hướng 1, được bạn đồng ý; `doc/experiments/2026-11-05_b10db82_hang.md` mục 7).** Hàm mới trong
`layer_parameters.py`, gọi trong `ConvMapper` ngay sau `check_wght_sets`: từ chối Conv có lượt × psum mỗi PE × kernel mỗi lần tính ≠ số filter, không đổi
stream. Điều kiện gồm cả layer 1 lượt có số filter lẻ khi 2 kernel mỗi lần tính (8×4×1 → 5: 6 ô); các layer đó vốn cũng không chạy được (bộ sinh tham
chiếu của testbench lỗi trước khi mô phỏng, cả 8×4×2 → 6 không có ô đệm: giới hạn số psum lẻ mỗi PE của tham chiếu, không phải #40, chưa điều tra).
Unit test mới (34): từ chối 24 = 16 + 8; 30 layer chạy được qua; 28×28×1/×2 → 24 và 8×8×1 → 48 (32 + 16) bị chặn, 28×28×1 → 48 (3 × 16) qua. Quét tĩnh
mọi layer Conv đã lưu profile (`doc/experiments/2026-11-05_b10db82_hang/scan_guards.py`: Bảng 3 trên 16 cấu hình, 12 ca mốc, 4 model hàm kích hoạt):
78 layer, 0 bị chặn. Hồi quy RTL đầy đủ: 189 test = 185 PASS + 4 xfail đã biết, 0 FAIL (như trước, không layer nào bị chặn).

| Kiểm chứng | Kết quả |
|---|---|
| #37: `test_cluster_rows1[conv14_c32_x2]` | RTL mới PASS; RTL cũ (`87f9bac`) FAIL, 32/32 feature map sai |
| #17: 1 channel rộng 20 / 40 (`test_random_data`, không đệm) | RTL mới PASS; RTL cũ FAIL, 8/8 feature map sai |
| #17: MNIST Conv1 28×28×1 → 32 không đệm | PASS, kiểm tra độc lập numpy 25.088/25.088 khớp (trước là xfail #17) |
| #17: 1 channel × `NUM_GLB_IACT` 1, 3 (`test_iact_channel_mapping`) | PASS (đường mới thay cách sửa #6 cũ) |
| #39: 8×4×1 → 64, 28×28×1 → 32, 40×8×1 → 32, 14×14×1 → 64 (4 lượt), 8×4×1 → 32 ở CR 1 | 5/5 PASS (trước: FAIL); unit test `test_weight_sets_cover_every_pass` 8/8 (công thức cũ: 4 ca 1 channel FAIL) |
| Hồi quy RTL: 187 test cũ + `conv14_c32_x2` (lần 1, trước #39), rồi 10 test hỏng + `test_random_data[8x4_c1_f64]` (sau #39) | **189 test: 185 PASS + 4 xfail đã biết, 0 FAIL** (xfail: 3 channel ×2 #7, Conv3 ×2 #9; xfail #17 cũ nay thành `test_mnist_conv1_with_padding`, PASS) |
| 12 ca mốc (`doc/perf/baseline_2026-11-04`, **mốc mới**) | 11 ca giống hệt từng chu kỳ và word DMA (cả ca DMA 32); `model_mnist_real_c1` −360 chu kỳ (−0,2 %), −336 word, chỉ ở Conv1 (−1,1 %: `load_iact` −96, `load_wght` −240, `writeback` −24, `compute` 0) |
| Bảng 3 (`doc/perf/paper_table3_2026-11-04`, **mốc mới**) | 16/16 PASS, không còn "PASS pad"; 12 cấu hình −192 đến −408 chu kỳ cả mạng (−0,09 đến −0,39 %), 4 cấu hình giống hệt |
| Model hàm kích hoạt đã huấn luyện, ảnh 0 (`doc/perf/activation_2026-11-04_rowO.md`) | 4/4 PASS khớp từng bit; ReLU 218.924 → **218.564**, Leaky 237.689, SiLU 239.870, hard-swish 239.927: cả 4 −360, chỉ ở Conv1; số 0 ở input Conv1 50 % → 0 % (không còn channel đệm); chênh lệch giữa các hàm không đổi (+8,75 / +9,75 / +9,77 %) |
| Unit test Python | 337 pass (thêm 1 test #37, 8 test #39), 11 fail có từ trước |
| Lint | `fpga` 457 → **444** (hết 11 cảnh báo lệch 12/13 bit, 2 cảnh báo của phần đã xoá; 3 cảnh báo đổi số bit trong thông báo, đã cập nhật baseline); `parallel` 36 |
| Vivado 4 ns (`doc/synth/2026-11-04_route4ns_rowO_zu7ev/`, **mốc phần cứng mới**) | **0 CRITICAL**, 311 cảnh báo (4 mới: cổng `iact_x_line_repetitions_i` không tải); WNS +0,169 / **+0,077 ns** (đạt 250 MHz); **LUT −1.547, FF −525, BRAM 192 → 188** sau route (mỗi PE −7 FF; mỗi constructor −37 FF và bộ đệm iact 6 → 5 RAMB36 vì mặt nạ ghi byte nay là hằng số); URAM 12, DSP 4 |

### Sửa #41b, #41c, #41d: Conv có stride khi phần cứng dựng với `STRIDE_ENABLED=1` (2026-11-08, được bạn đồng ý)

Chi tiết: `doc/experiments/2026-11-07_bug41_stride.md` mục 8–9. Stride là phần tuỳ chọn của RTL (tham số `STRIDE_ENABLED`, mặc định 0); với tham số
bằng 1, Conv stride 2 vẫn sai vì phía host lập trình và giải mã layer bằng kích thước **input** ở những chỗ cần kích thước **output** (với stride 1
hai thứ trùng nhau nên chưa từng lộ), và pha ghi ngược của RTL cũng vậy. Công cụ tìm lỗi: `slot_map.py` (mỗi ô output của DUT ứng với cửa sổ nào),
`window_map.py`, `padcheck.py`, `DUMP_IACT_IMAGE=1` (nội dung bộ đệm iact cả sau ảnh).

**Các chỗ sửa** (mọi giá trị không đổi khi stride 1):
- (A, #41b) `src/open_eye/test_utils_main.py` `calculate_conv_serial`: chuyển kernel sau `psum_size_x + psum_add_up` ô output (cũ `+ add_up`, đơn vị pixel input).
- (B, #41b) `src/open_eye/layer_parameters.py`: `iact_x_add_up = (số output + psum_add_up) × strideX` (ảnh rộng lẻ thiếu một cột).
- (Y, #41d) `layer_parameters.py`: `iact_y_add_up = ⌈H / strideY⌉ × strideY` trong `y_size` (chu kỳ ghi của bộ chuyển đổi), `needed_iact_buffer_words`,
  `iact_buffer_words_per_write`: một lượt có thêm hàng đệm dưới mà cửa sổ cuối của ảnh cao lẻ cần.
- (W) `layer_parameters.py`: `fsm_psum_limit` của pha ghi ngược đếm theo output (stride 2 trước chạy gấp 4 lần cần thiết; chuỗi 8×8: 30.880 → 28.960 ns).
- (C, #41c, **RTL**) `hdl/OpenEye_FPGA.v` `RECEIVE_PSUMS_TO_IACT`, 2 dòng: một hàng output có `psum_size_x` pixel (Dense giữ `iact_size_x`), chu kỳ hàng
  `iact_x_add_up / stride_x` viết dạng tích `x_pos × stride_x ≥ iact_x_add_up − stride_x` (không bộ chia; `STRIDE_ENABLED=0` thì `stride_x` là hằng 1).
- (F) `test_utils_main.py` `fill_dram_with_ref` (cũng là `DRAM.dense_input_order`): thứ tự làm phẳng Conv → Dense theo kích thước output (sau Conv stride 2
  trước đây vượt chỉ số).
- Phép kiểm tra `check_conv_geometry`: chỉ từ chối stride khi `STRIDE_ENABLED=0` (#41); vẫn từ chối "same" của TF đệm lệch (#42).
- Mode model mới `Conv_Dense` (`data_create.py`), test `test/test_stride_params.py` (15), `test/cocotb_fpga/test_stride.py` (12), sửa 2 test của
  `test_model_guards.py`.

| Kiểm chứng | Kết quả |
|---|---|
| `test_stride.py` (RTL, `STRIDE_ENABLED=1`) | **12/12 PASS**; trên `69320ba` 10/12 FAIL (2 PASS là rộng 8 và 24, vốn đúng) |
| Các ca khác đã chạy | layer đơn rộng 5, 6, 9, 10, 14 và chuỗi 14×14, 10×10, 12×8: giá trị đúng, chỉ ô đệm / word dư khác 0 (#9, như stride 1 rộng 7) |
| Hồi quy RTL 201 test (189 + 12) | **197 PASS + 4 xfail đã biết, 0 FAIL** |
| 12 ca mốc (`doc/perf/baseline_2026-11-04`) | **12/12 giống hệt**: 0 chu kỳ, 0 word DMA lệch |
| Bảng 3 (16 cấu hình, `tools/paper_table3.py --run`) | **16/16 PASS, 16/16 profile giống hệt** `paper_table3_2026-11-04` (mọi layer: tổng chu kỳ và chu kỳ từng pha) |
| Unit test Python | 474 pass (+15), 11 fail có từ trước |
| Lint | `fpga` 444 → **443** (hết 1 cảnh báo độ rộng ở dòng quay vòng), 0 mới; baseline cập nhật |
| Vivado 4 ns | 0 CRITICAL, 311 cảnh báo y như cũ; LUT 61.519 / 59.373 (synth / route, +21 / −16), FF +1 / +38, BRAM 188 / URAM 12 / DSP 4 như cũ; WNS +0,196 / **+0,009 ns** (đạt 250 MHz; đường găng giữa hai PE ở hai cluster, 95,5 % do route, không qua logic vừa sửa); **mốc phần cứng mới** `doc/synth/2026-11-08_route4ns_fix41_zu7ev/` |

### `STRIDE_ENABLED = 1` làm mặc định (đề xuất 5, 2026-11-09, được bạn đồng ý)

Ý nghĩa của tham số: mục 5.10. Phần cứng trước đây được dựng với `STRIDE_ENABLED = 0` (mặc định của upstream): stride bị gắn cứng bằng 1, nên toolchain
phải từ chối mọi Conv stride > 1 (#41). Sau các bản sửa #41b–#41d (mục trên) đường stride đã đúng, nên dựng phần cứng có stride.

**Các chỗ sửa:** `src/open_eye/open_eye_parameters.py` mặc định `STRIDE_ENABLED` 0 → **1** (chú thích cũ "AXI bus width" sai, đã thay);
`hdl/OpenEye_FPGA.v` giá trị mặc định của `parameter STRIDE_ENABLED` 0 → 1 (chỉ dùng khi không có `parameters_FPGA.vh`; mọi bản dựng của test và
`export_vivado.py` lấy giá trị từ Python). Cách đo: chạy mọi thứ với biến môi trường `STRIDE_ENABLED=1` **trước** khi đổi mặc định (cùng kết quả,
vì mặc định chỉ dùng khi biến không đặt), rồi đổi mặc định và kiểm tra lại không đặt biến.

| Kiểm chứng (`STRIDE_ENABLED = 1`) | Kết quả |
|---|---|
| Vivado 4 ns (`doc/synth/2026-11-09_route4ns_stride1_zu7ev/`, **mốc phần cứng mới**) | 0 CRITICAL, 311 cảnh báo y như `STRIDE_ENABLED = 0`; LUT 61.674 / 59.548 (synth / route, **+155 / +175**, +0,25 %), FF +7 / +13, CARRY8 +4, BRAM 188 / URAM 12 / DSP 4 như cũ; WNS +0,171 / **+0,042 ns** (đạt 250 MHz); phần tăng ở `dma_storage` (+220 LUT), các bộ dựng stream không tăng |
| Hồi quy RTL 201 test | **197 PASS + 4 xfail đã biết, 0 FAIL** (mọi bản dựng có `STRIDE_ENABLED = 1`, đã kiểm trong `parameters_FPGA.vh`) |
| 12 ca mốc (`doc/perf/baseline_2026-11-04`) | **12/12 giống hệt**: 0 chu kỳ, 0 word DMA lệch |
| Bảng 3 (16 cấu hình) | **16/16 PASS, 16/16 profile giống hệt** (tổng và từng pha của mọi layer) |
| Lint | `fpga` 443, `parallel` 36: 0 mới |
| Sau khi đổi mặc định, không đặt biến | `export_vivado.py` mặc định ra header giống hệt bản đã chạy Vivado; lint như trên; unit test 474 pass (11 fail có từ trước); Conv 7×7 stride 2 qua RTL PASS không cần `OPENEYE_ALLOW_UNSUPPORTED` |

Muốn mạch nhỏ nhất (không dùng stride) thì dựng với `STRIDE_ENABLED=0`: toolchain sẽ từ chối layer stride > 1 (#41).

## 9b. Kết quả lint RTL chi tiết (Verilator 5.020, 2026-10-10)

**Số liệu mục này là của ngày 2026-10-10.** Hiện tại (baseline lint `tools/lint_baseline/`, sau các bản sửa #14, #19, #30, upstream `e78e5b7` và bước B của hàm kích hoạt, bản sửa #29, #38, hàng O #37/#17, #41c): `fpga` **443**, `parallel` **36** (#38: hết `WIDTHEXPAND` / `WIDTHTRUNC` của hai lát cắt trường lượng tử; #29: `wghts_per_pe` nay 13 bit như toán hạng nó được so sánh, bớt 1 `WIDTHEXPAND`; bước B: `data_dma_i_reg` nay dùng hết nên bớt 1 `UNUSEDSIGNAL`; `e78e5b7` bớt 1 `BLKSEQ` trong `OpenEye_FPGA.v`; #30 xoá cảnh báo
`WIDTHTRUNC` gán 46 bit vào 8 bit trong `quantization_unit.v`: chính là chỗ quấn vòng mà lint đã chỉ ra từ trước);
mục (1) bên dưới (`PE.v:2210`) đã sửa (2026-10-21), mục (2)–(3) đã được phân tích trong lỗi #22 (mục 8b, #11).
Output gốc đầy đủ: `doc/lint/verilator-5.020_2026-10-10.txt`; chạy lại đúng lệnh CI của upstream trên RTL hiện tại (2026-10-14, vẫn 38 warning, giống hệt):
`doc/lint/verilator-5.020_upstream-ci_2026-10-14.txt`. Mọi warning dưới đây đều có sẵn trong upstream; hai bản sửa RTL (`GET_BIAS` và lỗi #13, mục 9) không thêm warning nào.

### Hai mục tiêu lint

| Mục tiêu | File gốc | Tham số | Kết quả |
|---|---|---|---|
| `parallel` (lệnh CI gốc của upstream) | `OpenEye_Parallel.v` | mặc định **`SERIAL=0`** (chế độ song song, FPGA **không** dùng) | 38 warning, 0 lỗi |
| `fpga` (thêm mới) | `OpenEye_FPGA.v` + `psum_pipeline.v` + toàn bộ cây con | **`SERIAL=1`**, đúng chế độ FPGA đang dùng | 474 warning + **4 lỗi `BLKANDNBLK`** |

Lệnh CI gốc kiểm tra **chế độ không được dùng**, và bỏ sót `OpenEye_FPGA.v` cùng `psum_pipeline.v`, hai file sẽ bị sửa ở Giai đoạn 1.
Vì vậy `fpga` là mục tiêu phản ánh đúng phần cứng thật.

Mức đánh giá: **Vô hại** = không đổi hành vi phần cứng. **Tiềm ẩn** = chỉ sai ở chế độ hoặc cấu hình đang không dùng.
**Đáng ngờ** = có thể đang gây sai, cần kiểm tra bằng test trước khi kết luận.

### A. Mục tiêu `parallel`: 38 warning

#### A1. Đáng ngờ (nên kiểm tra khi làm Giai đoạn 1, phần weight)

**(1) `PE.v:2210`: số word của SPAD địa chỉ weight bị cắt từ 7 bit xuống 5 bit**
```verilog
wire [4:0] first_spad_words_wght;                 // PE.v:662, chỉ 5 bit (tối đa 31)
.first_spad_words_o (first_spad_words_wght),      // PE.v:2210, output của data_pipeline_wght rộng $clog2(WGHT_ADDR_ADDR+1) = 7 bit
```
- Commit upstream `546338e` tăng `WGHT_ADDR_ADDR` lên 64 entry, nên output thành 7 bit, nhưng dây trong `PE.v` vẫn 5 bit.
- Giá trị lớn hơn 31 sẽ mất 2 bit cao. Dây này được dùng ở `PE.v:1366, 1398, 1408, 1414` (`if ((first_spad_words_wght - 1) > wght_addr_vec)`)
  để giới hạn địa chỉ weight trong **chế độ sparse**. Hậu quả có thể là đọc sai hoặc thiếu weight khi một PE có hơn 31 word địa chỉ weight.
- Ảnh hưởng tới cấu hình đang đo: **có thể**. Phần cứng được sinh với `SPARSITY_EN=1` (đường sparse đang chạy), nhưng dữ liệu test là dense
  (`USE_SPARSE_*=0`), nên trường hợp hơn 31 word địa chỉ weight có thể chưa được thử. (Sửa 2026-10-14: trước đây ghi nhầm là `SPARSITY_EN=0`.)

**(2) `data_pipeline_wght.v:394, 396`: tổng overhead bị gói vào 4 bit cố định**
```verilog
wire [3:0] overhead_temp [PARALLEL_MACS-1:0];   // 4 bit cố định
assign overhead_temp[0]   = input_words_w[0][SECOND_PAYLOAD_WIDTH+:SECOND_OVERHEAD_WIDTH];
assign overhead_temp[w+1] = input_words_w[w+1][...] + overhead_temp[w];   // cộng dồn qua các MAC
```
- "Overhead" là số weight bằng 0 bị bỏ qua trước một weight khác 0 (mã hoá sparse). Độ rộng thật là tham số `SECOND_OVERHEAD_WIDTH`
  (với cấu hình mặc định của lint là 16 bit), nhưng `overhead_temp`, `overhead_w` và `overhead_next_word` lại khai báo cứng `[3:0]`.
- Khi `PARALLEL_MACS > 1`, tổng của 2 overhead 4 bit có thể tới 30 nhưng bị cắt còn 4 bit (tối đa 15), nên **tràn**.
- Tài liệu upstream (`doc/test_status_handover.md`) có nhắc lỗi "PARALLEL_MACS=2 weight shortfall" (thiếu weight khi chạy 2 MAC song song) chưa rõ nguyên nhân;
  hai dòng này là một ứng viên. **Chưa kiểm chứng.**

**(3) `data_pipeline_wght.v:424`: `overhead_output` (4 bit) nhận biểu thức 17/32 bit**
- Kết quả sau khi trừ `filters_w` thường nhỏ, nhưng nếu phép trừ ra số âm thì bị cắt thành một số dương sai. Chỉ dùng khi `SPARSITY_EN=1`
  (cấu hình đang dùng).
  Nên kiểm tra cùng với (2).

#### A2. Tiềm ẩn (chỉ sai ở `SERIAL=0`, FPGA không bị ảnh hưởng)

**(4) `PE.v:820` SELRANGE ×2: lấy 40 bit từ số 20 bit**
```verilog
assign psum_data_o = SERIAL == 1 ? {zeros, adder_tree_o} : output_adder[TRANS_BITWIDTH_PSUM-1:0];
```
- Nhánh `SERIAL==0` lấy `[39:0]` từ `output_adder` chỉ có 20 bit. Với `SERIAL=1`, nhánh này không bao giờ được chọn.

**(5) `OpenEye_Parallel.v:260-261` UNDRIVEN ×2: `mem_addr_iact`, `mem_addr_psum` không được gán**
- Có chủ đích: comment ở `OpenEye_Parallel.v:790` ghi rằng chế độ `SERIAL=0` cần một bộ sinh địa chỉ chưa tồn tại,
  nên các địa chỉ "cố ý để trống để lint tiếp tục báo". Với `SERIAL=1`, chúng được gán bằng 0 và không được dùng.

#### A3. Vô hại

**(6) WIDTHEXPAND ×26** (`data_pipeline_wght.v` 20, `PE.v` 6)
- Phép toán trộn độ rộng, ví dụ `overhead_reg + PARALLEL_MACS + overhead_w` (17 bit + 32 bit + 4 bit). Verilog tự mở rộng
  toán hạng hẹp bằng số 0, nên kết quả đúng. Gồm các dòng `data_pipeline_wght.v:381, 386, 396, 424, 425, 515, 589–601` và
  `PE.v:829, 1287, 1367, 1409, 2211`. Riêng `PE.v:2211`: `filters_reg_M0` 6 bit nối vào input 8 bit, được thêm 0, nên đúng.
  (`PE.v:2210` cũng được báo là WIDTHEXPAND nhưng là output, xem mục (1).)
- `data_pipeline_wght.v:376` (WIDTHTRUNC): `filters_w` 7 bit nhận `first_spad_max_i` 8 bit. Vô hại vì đầu vào chỉ tới 63 (6 bit).

**(7) UNOPTFLAT ×2** (`PE.v:566` `wght_data_spad_oh_acc`, `data_pipeline_wght.v:392` `overhead_temp`)
- Mảng được nối tiếp kiểu `a[i+1] = f(a[i])`. Verilator coi cả mảng là một tín hiệu nên tưởng có vòng lặp tổ hợp.
  Không có vòng lặp thật; chỉ làm Verilator mô phỏng chậm hơn. Icarus và FPGA không bị ảnh hưởng.

**(8) PINMISSING ×2** (`GLB_cluster.v:187, 213`, chân `wr_mask_i` của `RAM_SP`)
- `RAM_SP.v:86` ghi rõ: khi không dùng mask thì chân này được phép để trống.

### B. Mục tiêu `fpga`: 474 warning + 4 lỗi

| Loại | Số | Ý nghĩa và đánh giá |
|---|---:|---|
| UNUSEDSIGNAL | 184 | Tín hiệu khai báo nhưng không dùng (`OpenEye_FPGA.v` 109, `psum_pipeline.v` 28, `iact_stream_constructor.v` 24, `OpenEye_Parallel.v` 13,…). Vô hại, nhưng là dấu hiệu có code thừa |
| WIDTHEXPAND | 178 | Như A3-(6). Vô hại |
| WIDTHTRUNC | 51 | Cắt bit (`psum_pipeline.v` 22, `OpenEye_FPGA.v` 22, `data_pipeline_wght.v` 4 như mục A, `iact_stream_constructor.v` 2, `quantization_unit.v` 1). **Cần xem từng chỗ** khi sửa các file này |
| UNUSEDPARAM | 30 | Tham số không dùng. Vô hại |
| BLKSEQ | 13 | Phép gán blocking `=` trong khối tuần tự (`OpenEye_FPGA.v` 10, `psum_pipeline.v` 3). **Đáng ngờ** về mặt phong cách: dễ làm kết quả mô phỏng khác phần cứng sau tổng hợp |
| **BLKANDNBLK (lỗi)** | 4 | **Đáng ngờ.** `psum_pipeline.v`: biến `results_ready` vừa được gán blocking `=` (dòng 429–454, 522: tích luỹ AND qua các cluster) vừa non-blocking `<=` (dòng 274, 485, 507, 900) trong cùng một khối. Icarus vẫn chạy, nhưng Verilator từ chối, và đây là mẫu code dễ sai khi tổng hợp. Nằm ở **đường readout**, đúng chỗ Giai đoạn 1 sẽ sửa |
| Khác | 18 | VARHIDDEN 4 (tên biến trùng tên ở phạm vi ngoài), PINMISSING 3, EOFNEWLINE 3 (file thiếu xuống dòng ở cuối), UNOPTFLAT 2 (như A3-(7)), UNDRIVEN 2 (`GLB_cluster.v`), UNUSEDGENVAR 1, REALCVT 1 (số thực đổi sang nguyên), PINCONNECTEMPTY 1, GENUNNAMED 1 (khối generate không đặt tên). Vô hại |

Tổng: 474 warning + 4 lỗi = 478. `SELRANGE` (mục A2) **không xuất hiện** ở mục tiêu này, vì nó chỉ thuộc chế độ `SERIAL=0`.
Danh sách đầy đủ, đã gộp theo loại, file và nội dung: `tools/lint_baseline/fpga.txt` và `tools/lint_baseline/parallel.txt`.

## 9c. CI lint theo baseline (hướng A cải tiến)

- **Mục đích:** CI không fail vì các warning có sẵn từ upstream, nhưng **fail ngay khi bạn tạo ra warning mới**.
- **Cách làm:** `tools/lint_check.py` lint 2 mục tiêu (mục 9b). Mỗi warning được nhận diện bằng `loại | file | nội dung`,
  **không dùng số dòng**, để code chỉ dịch chỗ (ví dụ sau khi merge upstream) không bị tính là mới. Sau đó script so số lượng với
  `tools/lint_baseline/*.txt`. Mục tiêu `fpga` tự sinh các header (`parameters_*.vh`, `regmap_params.vh`, `dma_storage.v`) vào thư mục tạm.
- **CI** (`.github/workflows/lint.yml`): Ubuntu 24.04, `apt install verilator` (5.020, cùng phiên bản baseline) và `python3-yaml`.

```bash
python3 tools/lint_check.py --verilator ~/tools/verilator-5.020/bin/verilator            # kiểm tra
python3 tools/lint_check.py --verilator ~/tools/verilator-5.020/bin/verilator --update   # chấp nhận trạng thái hiện tại làm baseline
```

- Khi CI báo `NEW`: script in đúng `file:dòng` của warning mới. Sửa code, hoặc nếu warning đó chấp nhận được thì chạy `--update`
  và commit baseline mới, ghi lý do trong commit message.
- Khi sửa bớt warning: script báo `fixed`; chạy `--update` để hạ baseline, tránh warning đó quay lại mà không ai biết.
- Khi merge upstream có RTL mới: warning mới của upstream sẽ hiện là `NEW`; xem xét rồi `--update`.
- Lưu ý: bộ sinh code ghi thêm `src/open_eye/regmap_pack.py`. File này nằm trong `.gitignore` nên không ảnh hưởng tới git.

---

## 10. Nhật ký

### 2026-10-09

**Tổ chức repo**
- Stash các thay đổi chưa commit ban đầu (`stash@{0}` trên máy local, không push).
- Dựng lại các thay đổi trên upstream mới nhất (`c4bd562`, lúc đó local đang chậm 58 commit), tách thành 3 branch, rồi gộp vào `dev`.

**Sửa lỗi**
1. `fix/verilog-doc-parser` (`83750e9`): bộ sinh tài liệu Verilog.
   Bỏ comment trước khi parse, parse được parameter có giá trị là biểu thức (`OpenEye_FPGA.v`: 0 → 95 parameter),
   escape ký tự `|`, xử lý bullet list. Warning Sphinx phần Verilog: 125 → 0. Thêm 2 unit test.
2. `fix/conv-serial-output-order` (`27aa75c`): giải mã chuỗi DMA output của Conv ở chế độ SERIAL theo đúng thứ tự
   mà hàm sinh tham chiếu đã dùng, thay vì đoán bằng bộ đếm riêng. Sửa lỗi "values differ, reference file ok"
   ở cấu hình 1×1 cluster và DMA 32 bit: 124/128 giá trị sai → 0. 22 test Conv cho kết quả giống hệt trước khi sửa.
3. `docs/mnist-notebook-rtl-smoke-test` (`0aba7b4`): notebook `doc/demo_notebooks/mnist.ipynb` chạy được bước mô phỏng RTL
   (smoke test một layer Conv ngẫu nhiên, **chưa phải model MNIST**). Đã xoá output và dịch comment sang tiếng Anh.

**Giai đoạn 0: đo lường** (`1a9e6b2`)
- `profile_dma_phases` (profiler), `open_eye.profile_report` (báo cáo), `test_profile.py` (6 cấu hình),
  `test/test_profile_report.py` (unit test), `doc/perf/baseline.md` và CSV (baseline).
- Helper `_run_conv_const` thêm 2 tham số tuỳ chọn `quant_amount` và `dma_bitwidth` (giá trị mặc định không đổi).

**Đưa lên GitHub riêng**
- Remote repo gốc đổi tên thành `upstream` và đã khoá chiều push. `origin` = `github.com/DevFi-23/OpenEye` (private, đăng nhập bằng SSH key `~/.ssh/id_ed25519`).
- Đã push `dev` (branch mặc định) và `main` (bản sao upstream `c4bd562`).
- Không push 3 branch sửa lỗi riêng lẻ vì chúng đã được gộp vào `dev`; chúng vẫn còn trên máy local.

**Kiểm tra lỗi**
- CI Lint fail trên `dev` (`ea4f774`): lỗi kế thừa từ upstream, không do thay đổi của mình (mục 9).
- Quét số channel vào 1–4 × `NUM_GLB_IACT` 1/3: chỉ 2 và 4 channel với `NUM_GLB_IACT=1` là đúng (mục 9).

### 2026-10-10

- Build Verilator 5.020 từ source (`~/tools`), chạy đúng lệnh lint của CI: 38 warning, chi tiết ở mục 9b. **Chưa sửa RTL.**
- Ghi lại cách project dùng DMA (AXI DMA Simple mode + AXI4-Stream) ở mục 5.2.
- **CI lint theo baseline** (hướng A cải tiến): `tools/lint_check.py`, `tools/lint_baseline/{parallel,fpga}.txt`,
  `.github/workflows/lint.yml`. Thêm mục tiêu lint `fpga` (`OpenEye_FPGA.v`, `SERIAL=1`). Mục 9b ghi chi tiết từng warning
  (vô hại / tiềm ẩn / đáng ngờ), mục 9c ghi cách dùng. **RTL không đổi.**
- Mục 6b: so sánh những gì đo được trên mô phỏng với khi chạy trên FPGA thật.
- Mục 5.7: giải thích `SERIAL=1` và `SERIAL=0`. Mục 8: trạng thái chi tiết của Giai đoạn 0; việc thu hẹp khoảng cách mô phỏng/FPGA tạm hoãn.
- **Việc 0.1 xong:** `profile_report --compare`, `tools/run_profile.py`, snapshot `doc/perf/baseline_2026-10-09/`,
  10 unit test. Chạy lại toàn bộ 6 case so với baseline: chênh lệch 0, tức mô phỏng tất định (mục 6.3–6.6).
- **Việc 0.3 xong** (cấu hình gần thực tế): khảo sát giới hạn RTL (PASS: 8/16/32 channel, 32 filter, 14×14, 28×28, 8×8;
  FAIL: 64 filter (lỗi Python), 7×7 (ô đệm)). Thêm 3 case kiểu MNIST vào `test_profile.py`, **giữ 6 case cũ**.
  Baseline mới 9 case: `doc/perf/baseline_2026-10-10/` (6 case cũ không đổi). Layer đầu: bias + readout khoảng 44 %; layer sâu:
  compute 71–77 %.
- **Mô hình bộ nhớ ngoài** (`memory_model.py`, driver AXI-Stream mới, bộ đếm chờ bộ nhớ, `run_profile --mem`), 15 unit test.
  `ideal` cho kết quả giống hệt baseline; `typical` chậm thêm 8–22 %; `slow` làm lộ **lỗi RTL `GET_BIAS`** (mục 9, chưa sửa).
- Profiler: ghi `pending` (số liệu chưa chốt) và ghi file định kỳ mỗi 1024 chu kỳ để chẩn đoán test bị treo.
- README: mục 6 viết lại thành hướng dẫn chạy chi tiết; thêm mục 6c (mô hình bộ nhớ).
- **Kiểm chứng lỗi `GET_BIAS`** (theo yêu cầu: có phải do dữ liệu DMA thừa hoặc lệch thứ tự?): thêm `OPENEYE_TRACE_DMA`
  (`trace_dma_input`), `tools/check_dma_trace.py`, tham số `gap_before` của mô hình bộ nhớ. 13 kịch bản: dữ liệu luôn đúng số lượng và
  thứ tự; chỉ 1 chu kỳ trống đúng trước word bias cuối là FAIL. Không phải tối ưu hiệu năng (không tốn chu kỳ nào khi dữ liệu liên tục).
  Chi tiết mục 9. **RTL vẫn chưa sửa**, chờ đồng ý.
- **Sửa RTL `GET_BIAS`** (`hdl/OpenEye_FPGA.v`, 1 điều kiện `& enable_dma_i_reg`, được bạn đồng ý). Kiểm chứng: 15/15 kịch bản khoảng trống PASS,
  `--mem slow` 8/8 PASS, baseline 9 case 0 chu kỳ chênh lệch, Conv 16 test và GEMM/Dense 63 test không có hồi quy (các FAIL đều có sẵn trên RTL gốc),
  lint 0 warning mới. Tài nguyên: 0 flip-flop, LUT không tăng (Yosys `synth_xilinx`). Chi tiết mục 9.
- **Báo cáo tiến độ** (Word) cho giáo viên hướng dẫn: `doc/reports/BaoCao_TienDo_OpenEye_2026-10-10.docx`, tạo bằng
  `~/tools/docenv/bin/python tools/report/make_progress_report.py` (đọc số liệu từ `doc/perf/`; môi trường `~/tools/docenv` có python-docx,
  matplotlib, nodejs, cài qua micromamba để không động vào venv của project).
- README: mục 5.8 (độ rộng DMA), 8b (tổng hợp lỗi), 8c (kế hoạch gần).

### 2026-10-12

- README mục 8c: thiết kế "gửi bias theo filter" (phương án A/B/C), **chưa triển khai**, chờ đồng ý. Mục 8b: lỗi #12 (`current_filter` không tăng, mới đọc code).
- **Chuẩn bị tổng hợp Vivado** (mục 6d): repo chưa đủ file để add thẳng (4 header được sinh tự động, `hdl/dma_storage.v` cũ,
  wrapper AXI có 4 lỗi biên dịch). Thêm `tools/export_vivado.py`: sinh đồng bộ header và `dma_storage.v` theo cấu hình baseline,
  viết `synth_ooc.tcl` (non-project, out-of-context). Đầu ra `vivado/` được đưa vào `.gitignore`. Header xuất ra giống hệt bản của phép đo `mnist1`.
  Yosys tổng hợp đầy đủ thư mục xuất ra: khoảng 61k LUT, 45k FF, 272 BRAM36, 121 DSP, nên cấu hình baseline không vừa xc7z020; part mặc định đổi thành ZU7EV.
  **RTL không đổi.**
- **Kết quả Vivado đầu tiên** (bạn chạy trên Windows, Vivado 2024.2, ZU7EV): 64,5k LUT (28 %), 38,7k FF (8 %), 192 BRAM tile (62 %), 8 URAM, 4 DSP;
  WNS +6,1 ns ở 10 ns, nên fmax sau tổng hợp khoảng 257 MHz. 46 % BRAM của chip là 8 bộ đệm psum. Đường găng là logic điều khiển iact converter.
  Báo cáo lưu ở `doc/synth/2026-10-12_baseline_zu7ev/` (kèm `SUMMARY.md`).
- `synth_ooc.tcl`: ràng buộc clock đặt trước `synth_design`; thêm tuỳ chọn `impl` (place & route out-of-context, fmax sau route).
- **Lần chạy Vivado thứ hai (clock 4 ns)**: place & route **không chạy**, vì thư mục trên ổ C là bản cũ chưa có tuỳ chọn `impl`. Fmax sau tổng hợp vẫn khoảng 257 MHz.
  Lưu ở `doc/synth/2026-10-12_synth4ns_zu7ev/` (báo cáo, danh sách cảnh báo, `SUMMARY.md`).
- **Lỗi mới #13** (CRITICAL WARNING Synth 8-6858/8-6859): `rd_cycle_loop_cnt_0..3` trong `iact_stream_constructor.v` bị lái từ 2 khối `always`;
  trên FPGA chúng luôn bằng 0, mô phỏng không thấy. Thêm #14–#16 vào mục 8b. Mục 8c: bảng định hướng A–H sau Vivado. **RTL không đổi.**

### 2026-10-13

- **Place & route Vivado (clock 4 ns) xong:** đạt 250 MHz (WNS +0,025 ns, hold +0,010 ns), 63,9k LUT, 38,7k FF, 192 BRAM tile, 8 URAM, 4 DSP.
  Không có lỗi mới (chỉ có cảnh báo của chế độ OOC). Đường găng sau route: dây từ `psum_pipeline` tới 144 BRAM của bộ đệm psum, và URAM `wght_buffer` → PE.
  Lưu ở `doc/synth/2026-10-13_route4ns_zu7ev/`. Thời gian thật ở 250 MHz: `mnist1` 0,263 ms.
- Mục 5.7: `SERIAL=0` **chưa được kiểm chứng** (thiếu bộ sinh địa chỉ GLB, `cocotb_parallel` cũ); `OpenEye_Parallel` là "ASIC compute core" theo upstream,
  nhưng repo không có luồng ASIC.
- Kiểm tra upstream (`upstream/main` = `c085224`, 2026-10-12): 3 commit mới chỉ đổi comment (`TRANS_WORDS`), tên khối generate
  (`gen_router_iact_*` → `gen_router_psum_*` trong `OpenEye_Parallel.v`) và Makefile test. Không thay đổi chức năng, lỗi #13 chưa được sửa ở upstream.
  Chưa gộp vào `dev`.
- **Thí nghiệm lỗi #13** (được bạn đồng ý; 2 git worktree tạm trong scratchpad, đã xoá; RTL của project không đổi): giả lập netlist của Vivado
  (`rd_cycle_loop_cnt_0..3` luôn bằng 0) rồi chạy 9 case baseline. Kết quả: **6/9 FAIL** (3 case `32x3` và 3 case MNIST, mọi feature map sai), 3 case nhỏ PASS.
  Đối chứng (bản sao không sửa) PASS với số chu kỳ đúng như baseline. Quy luật: sai khi một trong `iact_read_limit_1..3` khác 0. Công cụ mới
  `tools/decode_iact_read_loops.py` giải mã các thanh ghi này từ stream DMA. Chi tiết: `doc/experiments/2026-10-13_bug13_stuck_counters.md`.
- **Sửa lỗi #13** (`hdl/iact_stream_constructor.v`, được bạn đồng ý): 4 lệnh reset của `rd_cycle_loop_cnt_0..3` chuyển về khối `always` đang đếm.
  Yosys `check`: 32 → 0 cảnh báo conflicting drivers. 9 case baseline PASS, 0 chu kỳ chênh lệch. 79 test Conv/GEMM giống hệt trước. Lint 0 warning mới.
  Thư mục Vivado `C:/openeye_vivado/fix13_impl` đã xuất sẵn để tổng hợp lại. Chi tiết ở mục 9.

### 2026-10-14

- **Vivado sau khi sửa lỗi #13** (place & route, 4 ns): 0 ERROR, **CRITICAL WARNING 200 → 0**, đạt 250 MHz (WNS +0,117 ns), mỗi `iact_stream_constructor` +32 FF.
  Đây là **mốc phần cứng hiện tại**: `doc/synth/2026-10-14_route4ns_fix13_zu7ev/`.
- `.gitignore`: thêm ngoại lệ `!doc/synth/**/*.txt` và `*.json`. Trước đó các báo cáo Vivado (`*.txt`, `config.json`) bị `.gitignore` của upstream bỏ qua,
  nên **chỉ các file `SUMMARY.md` được đưa lên GitHub**; nay đã đưa đủ.
- Mục 5.9: `IACT_RAM_CELLS` (số bank của bộ đệm iact) và thí nghiệm `IACT_RAM_CELLS=32` (6/6 PASS, chậm hơn 0,4–4,9 %, +7,8 % LUT, +12,6 % FF).
- **Rà soát README:** thêm sơ đồ thư mục (mục 4); gộp 3 mục kết quả Vivado cũ thành mục "Kết quả hiện tại" + bảng lịch sử (mục 6d); sửa các chỗ sai hoặc
  lỗi thời: baseline hiện tại (5.4, 7), mô hình bộ nhớ đã có (5.2, 6b), số unit test (16), vị trí dòng code (`GET_BIAS` 1978, `quant_reg` 2026–2028),
  nguồn `DMA_BITWIDTH` (5.8), "thay đổi RTL duy nhất" (nay là 2), `SPARSITY_EN` của cấu hình đang dùng là 1 chứ không phải 0 (9b, lỗi #11), bỏ các đoạn trùng
  (5.7, 8c, `CLUSTER_ROWS=1` ở mục 9, `BLKANDNBLK` ở #11 và #14).
- Mục 5.1: giải thích vì sao 9 case không có pha `writeback`/`pooling`, liệt kê 15 trạng thái FSM chính và 7 trạng thái FSM psum.
- Lint: chạy lại đúng lệnh CI của upstream (Verilator 5.020) trên RTL hiện tại: 38 warning, giống hệt danh sách 9b (2 bản sửa RTL không thêm warning).
  Không đọc được log GitHub Actions của repo private khi chưa có token; upstream thì job "lint" fail ở mọi commit.
- **Điều tra lỗi #6 và #7** (không sửa RTL; probe cocotb và bisect bằng 2 worktree tạm, đã xoá): 1 channel và `NUM_GLB_IACT=3` là **hồi quy do upstream `23be043`**
  ("Fixed many bugs for Dense Layer"); 3 channel là lỗi cũ do cách đóng gói của Python. Nguyên nhân và đề xuất sửa: `doc/experiments/2026-10-14_channel_bugs.md`.
- **Sửa RTL lỗi #6 (1 channel) và #7 (`NUM_GLB_IACT=3`)** (được bạn đồng ý, `iact_stream_constructor.v`): 34/34 test Conv PASS (trước 19/34), GEMM/Dense
  không đổi (40/63), 9 case baseline 0 chu kỳ thay đổi, lint 0 mới (1 cảnh báo biến mất), Yosys +65 LUT, +104 FF. Thêm `test/cocotb_fpga/test_mnist_layers.py`
  (quét channel × `NUM_GLB_IACT`, và 3 layer Conv MNIST thật). Layer MNIST thật còn bị chặn bởi lỗi cũ #17 (1 channel ảnh rộng), #18 (lượt filter thứ hai
  với nhiều channel), #9 và #5. Lỗi #8 hoá ra là giới hạn cấu hình (`QUANT_AMOUNT` ≥ số filter). Thư mục Vivado: `C:/openeye_vivado/fix67_impl`.

### 2026-10-15

- **Điều tra lỗi #18** (không sửa RTL, không sửa code của repo; probe cocotb, dữ liệu ngẫu nhiên, worktree tạm đã xoá): nguyên nhân là khoá `used_wght_per_PE`
  bị lặp trong `conv_mapper.py` (từ 7/2026) cộng với RTL `3e2e20f` (9/2026) đổi cách đếm sang word đóng gói. Mọi lần gửi weight đọc gấp đôi số địa chỉ,
  lấy nhầm weight của đợt channel khác. Weight hằng của các test che lỗi; với weight ngẫu nhiên mọi layer > 4 channel đều sai, kể cả case baseline `mnist2`.
  Đề xuất sửa 1 dòng Python; thử trên bản sao: MNIST Conv2 thật PASS, Conv3 thật đúng mọi giá trị (còn lỗi #9 ở kiểm tra file), 9 case baseline PASS với
  **−16,3 % / −24,7 % / −23,0 % chu kỳ** ở mnist1/2/3. **Chưa áp dụng, chờ đồng ý.** Lỗi mới #18b (40/48 filter).
- **Áp dụng bản sửa lỗi #18** (được bạn đồng ý sau khi kiểm chứng từng word): xoá khoá `used_wght_per_PE` bị lặp trong `conv_mapper.py`. Trước khi áp dụng,
  kiểm tra độc lập 9 trường hợp (7 với dữ liệu ngẫu nhiên): mọi giá trị bằng numpy, mọi dòng mang kết quả giống hệt file tham chiếu. Sau khi áp dụng: hồi quy 116 test
  (Conv 34/34, GEMM/Dense không đổi từng test, 19 test mới đạt), baseline mới `doc/perf/baseline_2026-10-15/` (−16 % / −25 % / −23 % chu kỳ ở mnist1/2/3).
  Thêm `tools/verify_conv_output.py` + `OPENEYE_DUMP_VERIFY=1` (kiểm tra độc lập từng word), tham số `random_data` cho `_run_conv_const`, test dữ liệu ngẫu nhiên.
- **Vivado sau bản sửa #6/#7** (bạn chạy `fix67_impl`): 0 CRITICAL WARNING, đạt 250 MHz (WNS +0,048 ns), +103 FF, +201 LUT. Mốc phần cứng hiện tại:
  `doc/synth/2026-10-15_route4ns_fix67_zu7ev/`.
- **Báo cáo tiến độ lần 2** (Word): `doc/reports/BaoCao_TienDo_OpenEye_2026-10-15.docx` (+ `phan_bo_do_tre_2026-10-15.png`,
  `so_sanh_chu_ky_2026-10-15.png`), tạo bằng `~/tools/docenv/bin/python tools/report/make_progress_report_2026-10-15.py` (dùng chung hàm định dạng
  với script của báo cáo 10/10; số liệu đọc từ `doc/perf/baseline_2026-10-15/` và `baseline_2026-10-10/`, số Vivado lấy từ
  `doc/synth/2026-10-15_route4ns_fix67_zu7ev/`). Nội dung: tóm tắt, công cụ mới, kết quả Vivado, mốc đo mới và so sánh trước/sau lỗi #18, kiểm tra độc
  lập từng word, kiểm thử hồi quy, lỗi đã sửa / chưa sửa, kế hoạch sắp tới, hạn chế.
- **Rà soát README** cho đúng trạng thái sau các bản sửa: mục 6.7 (lý do chọn 9 case, mốc mới), 6.9, 6.10, mục mới 6.12 (kiểm tra độc lập từng word),
  sơ đồ thư mục, mục 8 (thêm bước "0b. Sửa lỗi tính đúng"), 8b, 8c (bias 26 % / readout 26 % của `mnist1`, ước tính bias −23 % trên 55.048 chu kỳ,
  việc C2 chạy đủ MNIST), mục 9 (trạng thái channel sau bản sửa).

### 2026-10-16

- **Phân tích lỗi #14** (`results_ready` vừa gán blocking vừa non-blocking; không sửa RTL): mở checkpoint tổng hợp fix67, tổng hợp riêng
  `psum_pipeline` bằng Vivado (chạy batch từ WSL, thư mục `C:/openeye_vivado/bug14_check`) và Yosys, rồi thay netlist vào mô phỏng hệ thống.
  Vivado hiểu đúng như mô phỏng (9/9 ca PASS, chu kỳ giống hệt mốc, từng giá trị = numpy), nên **phần cứng hiện tại không bị ảnh hưởng**. Yosys hiểu khác:
  **mạch treo ở mọi layer**; Verilator từ chối. Đề xuất cách sửa giữ nguyên từng chu kỳ (tách phần tổ hợp ra khỏi thanh ghi), chờ đồng ý. Chi tiết: mục 9,
  `doc/experiments/2026-10-16_bug14_results_ready.md`.

### 2026-10-19 → 2026-10-20

- **Kiểm tra upstream** (`git fetch upstream`): 6 commit mới (12–15/10). Không commit nào động tới các file mình đã sửa lỗi. Đáng chú ý: `2bf497d` sửa độ rộng bit
  trong `PE.v` (chính là lỗi #11 phần `PE.v:2210`; probe 48 PE cho thấy bộ đếm lớn nhất là 13 < 32 nên chưa đổi kết quả hiện tại) và `18772d6` tắt bộ kiểm tra FC
  live (nguyên nhân 23 test GEMM fail). Đề xuất: cherry-pick `b6fa369`, `2c8c324`, `2bf497d`, không lấy `18772d6`; chờ đồng ý. Chi tiết: mục 2.
- **Sửa lỗi #14** (được bạn đồng ý, `hdl/psum_pipeline.v`): tách phần AND tổ hợp của `results_ready` ra khỏi khối FSM, thanh ghi chỉ còn gán `<=`.
  Kiểm chứng: lockstep bản cũ/mới trên 125 test + 23 test GEMM chạy lại (0 sai khác / 792.147 chu kỳ), lockstep ngẫu nhiên 300.000 chu kỳ, kết quả các bộ test
  không đổi, 9 ca mốc 0 chu kỳ chênh lệch, netlist Vivado và **netlist Yosys** (trước treo) PASS, Verilator nay biên dịch được cả thiết kế, lint fpga 477 → 470
  (baseline đã hạ), Vivado (`doc/synth/2026-10-19_route4ns_fix14_zu7ev/`, mốc phần cứng mới): hết 10 cảnh báo 8-6090, đạt 250 MHz (WNS +0,097 ns). Chi tiết: mục 9.
- **Lỗi #5 là báo động giả của testbench**: tắt bộ kiểm tra FC live thì 23/23 test GEMM/Dense PASS (mục 8b).

### 2026-10-21

- **Lấy 3 commit upstream** (được bạn đồng ý): `git cherry-pick -x b6fa369 2c8c324 2bf497d` → `0cacda1`, `22614d2`, `9c0c8dc`, cộng phần mở rộng 0 tường minh
  cho `filters_reg_M0`. Kiểm chứng: lockstep PE trên 125 + 23 test (5.708 + 592 PE, 0 sai khác), netlist `OpenEye_Parallel` giống hệt từng byte sau khi đổi tên,
  9 ca mốc 0 chu kỳ chênh lệch, lint fpga 470 → 468 và parallel 38 → 36 (baseline đã hạ), Vivado (`doc/synth/2026-10-21_route4ns_up3_zu7ev/`, mốc phần cứng mới):
  hết 2 cảnh báo 8-689, +2 FF mỗi PE, đạt 250 MHz. Chi tiết: mục 9, `doc/experiments/2026-10-21_upstream_cherry_pick.md`.
- Upstream có thêm `81173dc` (20/10, đồng bộ `hdl/config/regmap.yaml`), chưa lấy (mục 2).
- **Lỗi mới #20** (chưa sửa): `PE.v:829–830` tham chiếu tiến vào khối `gen_sparse_fsm`; Yosys tạo dây 1 bit không ai lái (mục 8b).
- Lỗi #19 (Dense K > 512): K = 520 sai với cả PE cũ lẫn PE mới, nên không do độ rộng bit (nguyên nhân: xem mục điều tra #19 bên dưới).
- **Điều tra lỗi #19** (không sửa RTL): K = 512 đúng, K = 513 đã sai. Dữ liệu dump cho thấy chính xác (10/10 output, K = 520 và 784) mọi activation từ
  chỉ số 512 bị coi là 0. Probe trong `iact_stream_constructor` chỉ ra nguyên nhân: `x_pos_in_w_cycle` (8 bit) quay vòng ở cặp 256 nên các cặp đó không được ghi
  vào RAM iact. Đã loại: độ rộng bit của upstream `2bf497d`, trường 8 bit `iact_x_add_up` (K = 264/300 vẫn đúng), con trỏ bộ đệm weight, SPad địa chỉ weight.
  Phát hiện thêm #19b (N = 32 với K ≥ 508) và #21 (N > 32 sai với mọi K). Chi tiết: `doc/experiments/2026-10-21_bug19_dense_k512.md`.
- **Sửa lỗi #19** (được bạn đồng ý): `iact_stream_constructor.v` bộ đếm `x_pos_in_w_cycle` 8 → 12 bit; `OpenEye_FPGA.v` điều kiện lưu của FC không dùng dấu của
  `current_x` (rào cản K > 2048, dự đoán từ code và kiểm chứng trước khi sửa). Loạt K 64 … 4032 (gồm Dense 784 và FC 3136 của MNIST) 14/14 đúng từng output;
  lockstep constructor trên 125 + 23 test 0 sai khác; 9 ca mốc 0 chu kỳ; lint fpga 468 → 463; Vivado (`doc/synth/2026-10-21_route4ns_fix19_zu7ev/`, mốc phần cứng mới)
  đạt 250 MHz, +24 FF. Chi tiết: mục 9.

### 2026-10-22

- **Phân tích chạy cả model nhiều layer** (không sửa RTL): model `LAYER=MNIST` và kiến trúc MNIST thật (đầu vào đệm 2 channel, `QUANT_AMOUNT=64`) chạy đúng cả
  6 layer nối tiếp trên chip; với 1 channel thì fail do lỗi #17. Liệt kê những gì còn thiếu cho model int8 thật (kẹp int8, ReLU, zero point, làm tròn, mantissa,
  #12, độ rộng psum, luồng Python) và cách đo pha theo từng layer (bản thử profiler, kết quả 976 µs cho MNIST). Mục 8d,
  `doc/experiments/2026-10-22_multilayer_model.md`.
- **Profiler theo từng layer** (chỉ Python, không đổi RTL): `profile_dma_phases` tách bảng pha cho mỗi layer (mở layer mới khi FSM chính vào
  `GET_PARAMETERS`) và gán pha trong trạng thái 11 theo FSM psum (1–3 = `compute`, còn lại = `writeback`), nên layer nối tiếp không còn `compute = 0`.
  Testbench ghi tên/kích thước layer vào `profile.json` (`layers[].info`); `OPENEYE_SEED` cố định model và dữ liệu (`tf.keras.utils.set_random_seed`, vì Keras 3
  bỏ qua `tf.random.set_seed`). Thêm `LAYER=MNIST_REAL` (`data_create.py`), 2 case `model_mnist16_c2` / `model_mnist_real_c2` (`test_profile.py`),
  bảng theo layer, so sánh theo layer, `--clock-mhz` và báo cáo case mới khi so sánh (`profile_report.py`, `run_profile.py`). Kiểm chứng: 9 case cũ 0 chu kỳ
  lệch, 2 lần chạy model giống hệt nhau, khớp bản thử `probe_model.py` 6/6 layer; 35 unit test của profiler pass (11 lỗi có sẵn của `test_dense_output.py` không
  liên quan). Mốc mới `doc/perf/baseline_2026-10-22/` (11 case). MNIST thật (2 channel): 244.050 chu kỳ = 976 µs, Conv2 50 %. Mục 6.13.
- **Lỗi #17: đệm input 1 channel thành 2 channel bằng Python** (không sửa RTL): `src/open_eye/channel_pad.py` (mới). Testbench tự đệm layer 0 khi là Conv
  1 channel cần hơn một lượt x (đúng điều kiện của lỗi): channel thêm có activation 0, weight 1; `OPENEYE_PAD_CHANNELS=0` để tắt. Conv 1 channel rộng 20/28/40
  (ngẫu nhiên, mọi output = numpy) và MNIST thật 1 channel cả 6 layer PASS; cùng các ca đó không đệm thì FAIL. Chi phí Conv1 +472 chu kỳ (+1,2 %), +456 word
  DMA. `test_mnist_layers.py`: Conv1 MNIST bỏ `xfail`, thêm `test_mnist_conv1_without_padding` (`xfail(strict)`, giữ dấu vết lỗi RTL) và 3 test ngẫu nhiên
  1 channel; `test/test_channel_pad.py` (10 unit test); hồi quy `test_conv_const` 34/34, mapping 8 + 2 xfail, 9 case mốc 0 chu kỳ lệch; case đo `model_mnist_real_c1` (241.250 chu kỳ = 965 µs) thêm vào `baseline_2026-10-22`; profiler
  ghi `pad_channels`. Mục 9, `doc/experiments/2026-10-22_bug17_channel_pad.md`.
- **Lỗi mới #22** (chưa sửa): word weight Conv toàn 0 (2 filter liền kề cùng có weight 0 ở một vị trí kernel) làm sai cả layer: mapper Python bỏ word 0 nên
  stream thiếu word (Conv1 có đệm weight 0: 240 thay vì 480 word), giữ lại word 0 thì PE vẫn tính sai hoặc treo. Trước giờ bị che vì `DRAMContents` thay
  weight 0 bằng ±1. Chặn việc chạy model int8 thật. Vì vậy channel đệm của #17 dùng weight 1. Mục 8b, 9. (Đính chính 2026-10-24: nguyên nhân là định dạng nén không khớp, không phải PE; mục 9.)

### 2026-10-24

- **Điều tra lỗi #22** (không sửa RTL, không sửa code repo): weight 0 làm sai định dạng weight nén của Conv. Mapper Python và `data_pipeline_wght.v` hiểu khác
  nhau về cột rỗng, ô đệm, overhead 4 bit và word 0; thêm 2 lỗi của bộ ghép stream (cắt theo PE đầu, `SKIP_ZERO_WORDS` làm lệch stream): 6 cơ chế F1–F3, F7–F9.
  Mô hình chu kỳ Python của `data_pipeline_wght` khớp RTL từng lần ghi ở 336 lần nạp weight; bộ kiểm tra offline dự đoán đúng mọi ca mô phỏng. Model MNIST
  int8 đã huấn luyện: Conv2 140/384, Conv3 116/384 lần nạp weight sai (mô phỏng RTL treo). Bản sửa chỉ Python (bộ mã hóa mới, làm thử ngoài `src/`): 0 lỗi
  offline trên 6 kích thước × 9 mẫu và weight thật; RTL 12 ca PASS gồm MNIST Conv1/Conv2 thật, Conv3 thật 3.136/3.136 output đúng (fail stream do #9 như
  trước); stream giống hệt khi không có số 0; DMA không đổi. Đính chính phân tích ngày 22/10. Mục 8b, 9,
  `doc/experiments/2026-10-24_bug22_weight_encoding.md`, công cụ `doc/experiments/2026-10-24_bug22/`.
- **Sửa lỗi #22** (được bạn đồng ý, chỉ Python): bộ mã hóa weight Conv mới `src/open_eye/conv_wght_encoding.py` trong `ConvWghtStreamMapper`
  (cột tự kết thúc, 0 tường minh, không mang số 0 sang cột sau, chia chuỗi số 0 dài, lấp khối PE bằng word khác 0, gửi đủ độ dài); `DRAMContents` giữ weight
  Conv bằng 0 thật; hook `OPENEYE_TFLITE_CONV` + 3 test `test_trained_mnist_conv` với weight MNIST đã huấn luyện; `test/test_conv_wght_encoding.py`
  (39 test, dùng mô hình chu kỳ `src/open_eye/wght_pipeline_model.py`). Stream giống hệt khi không có số 0; hồi quy 56 pass + 5 xfail như trước + 1 fail có
  từ trước (#23, weight của nó giải mã đúng); 9 case mốc 0 chu kỳ lệch, mốc mới `baseline_2026-10-24`. Đính chính F8 (`trans_cycles_wght` theo stream thực tế).
- **Ghi nhận #23** (`test_conv3x3_sparse` 32×4×8 → 16 sai từ trước, phía activation thưa) và **#24** (không có hàm kích hoạt: `af_cluster.v` không được dùng
  và có 2 lỗi, tham chiếu Python không có ReLU). Mục 8b.
- **Bảng 3 của paper OpenEye đo bằng profiler** (chỉ Python): `LAYER=PAPER_MNIST`, 16 case `test_profile_paper`, `tools/paper_table3.py` (bảng theo từng
  layer với 10 pha, bảng tổng so với paper), tùy chọn testbench `OPENEYE_KEEP_GOING`, `test/test_paper_table3.py`. Kết quả `doc/perf/paper_table3_2026-10-24.md`:
  cùng xu hướng với paper, con số gấp 1,8–3,5 lần. Phát hiện lỗi mới #25 (`NUM_GLB_PSUM = 2`) và #26 (Dense nối tiếp Dense). Mục 6.14.
- **Rà soát README_FI.md** (theo yêu cầu): thêm mục **3c** (cách chạy mọi test và mô phỏng, kết quả mong đợi, cách tái hiện từng lỗi, bảng biến môi trường);
  cập nhật các chỗ lỗi thời: mốc hiện tại `baseline_2026-10-24` (mục 5.4, 6.1, 6.3, 6.4, 6.6, 8c), số case (6.1, 6.7, 6.10, 6.13), Conv1/#17 (6.7, 9),
  lộ trình giai đoạn 0 và 0b (việc 0.2 đã xong, #5 là báo động giả), #10 (`CLUSTER_ROWS=1` chạy hết mạng Bảng 3, không treo), #11 phần `data_pipeline_wght`,
  8c (việc mới I, J, K), 8d (mạng của paper, #25, #26), 9b (lint hiện tại `fpga` 463, `parallel` 36), cây thư mục (file mới và file đã sửa).
  Repo gốc có 5 commit mới (16–21/10, chưa lấy): `c48899f` sửa #14 theo hướng ngược với `dev` (không nên lấy), `e78e5b7` xoá `temp_var = 0` (cần phân
  tích), còn lại là test và `regmap.yaml` (mục 2).
- `tools/run_profile.py` mặc định **không** chạy 16 case Bảng 3 (chỉ khi `-k` có chữ `paper`): trước đó lệnh đo mốc sẽ chạy thêm khoảng 1 giờ case FAIL.

- **Điều tra lỗi #26** (không sửa RTL, không sửa code repo): Dense nối tiếp Dense. Dense đầu tính psum đúng nhưng pha ghi ngược không ghi gì vào bộ đệm
  iact (`fsm_psum_limit` quá ngắn, vòng đọc psum chưa cấu hình cho Dense, bộ đóng gói chỉ biết bố cục conv); Dense sau đọc lại input của Dense đầu.
  Ghi sẵn ảnh bộ đệm đúng thì kết quả cuối đúng (pha ghi ngược là chỗ hỏng duy nhất). Nhánh ghi ngược FC bị upstream bỏ để giảm LUT (`1320759`, `8350a00`).
  Python thuần không đủ (cần đổi `iact_x_add_up`, thứ bộ chuyển đổi FC dùng). Đề xuất: 1 dòng RTL + thanh ghi Python; giả lập trong cocotb (không sửa RTL):
  11 chuỗi Dense ở 4 cấu hình đúng, mạng paper CR=2 X=4 Y=3 PASS cả 7 layer (CR=1 còn lỗi tính #19b). **Chờ đồng ý sửa RTL.** Thêm thông tin cho #21
  (lỗi ở bước đọc kết quả, psum đúng) và #19b (Dense 1568→32 sai ở `CLUSTER_ROWS=1`). Mục 8b, 9, `doc/experiments/2026-10-24_bug26_dense_writeback.md`,
  công cụ `doc/experiments/2026-10-24_bug26/`.
- **Phân tích hướng đi của upstream** (mục 2): 7–8/2026 giảm LUT cho GateMate A1, 7–9/2026 chạy đúng lại (Hendrik Woehrle), 10/2026 sửa nhỏ; không có tối ưu
  băng thông/độ trễ. Lỗi #14: upstream (`c48899f`) chuyển hết sang gán blocking, `dev` tách phần tổ hợp và chỉ gán `<=` (không lấy `c48899f`).
  `e78e5b7` (xoá `temp_var = 0` nằm ngoài nhánh reset): không đổi chức năng, làm sạch mẫu reset bất đồng bộ, lấy được nếu bạn đồng ý.

### 2026-10-26

- **Sửa lỗi #26** (được bạn đồng ý; làm 24–26/10): Dense nối tiếp Dense trên chip. **1 dòng RTL** trong `RECEIVE_PSUMS_TO_IACT` của `OpenEye_FPGA.v`
  (`| fully_connected_layer` ở điều kiện cho `x_pos` quay về 0: với layer FC chỉ ghi nhóm của lane 0, đúng thứ tự filter) + Python: `configure_fc_writeback`
  trong `layer_parameters.py` (`fsm_psum_limit`, vòng địa chỉ và vòng chọn cluster của `SEND_PSUM_TO_IACT`), `iact_size_x` = 1 trong `dense_mapper.py`;
  testbench chỉ so N output thật sau một layer Dense (`valid_values`); ca model `DENSE_CHAIN_<K>_<N1>_...`. Test mới: `test/cocotb_fpga/test_dense_chain.py`
  (11 chuỗi qua RTL) và `test/test_fc_writeback.py` (mô hình chu kỳ, 110 test). Kiểm chứng: 11/11 PASS (chạy lại sau khi máy tắt: vẫn 11/11); đối chứng
  âm (RTL cũ + Python mới) FAIL đúng dự đoán; hồi quy 128 test 123 PASS + 5 xfail, 0 FAIL như trước; 12 case mốc 0 chu kỳ / 0 word DMA lệch; lint 0 mới;
  Bảng 3 chạy lại (`doc/perf/paper_table3_2026-10-24_fix26.md`): 7/8 cấu hình X = 4 tính đúng cả mạng (còn #19b ở CR 1 X 4 Y 3, #25 ở X = 2), chi phí
  +15 đến +28 chu kỳ mỗi mạng; Vivado 4 ns (`doc/synth/2026-10-26_route4ns_fix26_zu7ev/`, **mốc phần cứng mới**): 0 CRITICAL, LUT −4 / FF −4 sau tổng hợp,
  WNS +0,028 ns, đạt 250 MHz. Mục 8b, 9, `doc/experiments/2026-10-24_bug26_dense_writeback.md` mục 10.
- **Điều tra lỗi #25** (không sửa RTL, không sửa code repo): `NUM_GLB_PSUM = 2`. Chỉ pha ghi ngược của Conv sai (Conv đơn PASS, Conv → Conv FAIL; tiêm ảnh đúng sau mỗi
  lần Conv ghi ngược thì mạng paper X = 2 ra kết quả đúng). RTL gom nhóm 2 channel thay vì 4 channel/pixel và đếm pixel đệm theo nhóm; Python `fsm_psum_limit` chia 4 thay
  vì `NUM_GLB_PSUM`. Đính chính: kiểm tra "sau Conv2" không đúng mà bị bỏ qua. Đề xuất khoảng 15 dòng RTL (y hệt mạch cũ khi `NUM_GLB_PSUM = 4`) + 1 dòng Python,
  kiểm chứng bằng giả lập trong mô phỏng và mô hình chu kỳ; chi phí +4,4 % chu kỳ cho mạng paper X = 2. **Chờ đồng ý sửa RTL.** Mục 8b, 9,
  `doc/experiments/2026-10-26_bug25_glb_psum2.md`, công cụ `doc/experiments/2026-10-26_bug25/`.
- **Sửa lỗi #25** (được bạn đồng ý): ghi ngược Conv với `NUM_GLB_PSUM = 2`. RTL `RECEIVE_PSUMS_TO_IACT`: nhóm ghi ngược luôn 4 channel/pixel (`WRITEBACK_CHANNELS`),
  chỉ phát đủ số lane thật, `x_pos` đếm theo pixel; với 4 lane mọi điều kiện mới là hằng đúng (mạch như cũ). Python: `fsm_psum_limit` chia theo số lane.
  Mô hình chu kỳ dùng chung `src/open_eye/writeback_model.py`; test mới `test/cocotb_fpga/test_glb_psum2.py` (7) và `test/test_conv_writeback.py` (12).
  Kiểm chứng: 7/7; đối chứng âm (RTL cũ) FAIL đúng kiểu đổi byte; hồi quy 146 test 141 PASS + 5 xfail, 0 FAIL; 12 case mốc 0 chu kỳ / 0 word DMA lệch; lint 0 mới
  (cả cấu hình 2 lane); Bảng 3 (`doc/perf/paper_table3_2026-10-26_fix25.md`, mốc Bảng 3 mới) **13/16 cấu hình PASS** (X = 2 với CR 2/4/8 nay đúng, chậm hơn số đo cũ
  4,4–7,8 % vì pha ghi ngược không còn bị cắt; X = 4 giống hệt); Vivado 4 ns (`doc/synth/2026-10-26_route4ns_fix25_zu7ev/`, **mốc phần cứng mới**): 0 CRITICAL,
  LUT +113 (+0,17 %, dao động), WNS +0,084 ns. Thử kiểm tra tương đương hình thức bằng Yosys: quy trình không phát hiện được sai khác cài sẵn nên không dùng.
  Lỗi mới: **#27** (pooling 4×4 → 2×2 sai, cả 4 lane), **#28** (Conv ở `CLUSTER_ROWS=1` với 2 lane tính sai: 2 hàng CR 1 X 2 của Bảng 3). Mục 8b, 9,
  `doc/experiments/2026-10-26_bug25_glb_psum2.md` mục 9.

### 2026-10-28

- **Điều tra int8** (không đổi repo khi điều tra): kiểm kê đường int8 (bộ lượng tử lấy 8 bit thấp, `offset` 8 bit cộng trước phép nhân, mantissa bị cắt 8 bit ở
  `OpenEye_FPGA.v:1350`, #12, đệm viền 0, Python không có bước lượng tử int8 thật, tham chiếu không kẹp, thứ tự làm phẳng Conv → Dense khác TFLite). Bộ giả lập numpy
  bit-exact (khớp TFLite interpreter) của model MNIST int8 đã huấn luyện trên 10.000 ảnh: model thật trên phần cứng hiện tại **9,3 %**, thêm kẹp + activation zero point 0
  **99,21–99,25 %** (TFLite 99,23 %); bất đối xứng (zp −128) cần thêm psum 32 bit và đệm bằng zp. Giải thích "fused ReLU" của TFLite: ReLU = cận dưới của phép kẹp.
  Phát hiện lỗi mới **#29** (Dense K = 3136 với ≥ 32 output sai). `doc/experiments/2026-10-28_int8_clamp.md`, công cụ `doc/experiments/2026-10-28_int8/`.
- **Sửa #30: kẹp int8 và ReLU gộp** (được bạn đồng ý, RTL): `quantization_unit.v` kẹp về `[act_min, 127]` thay vì lấy 8 bit thấp; `act_min` theo layer qua thanh ghi
  mới `quant_clamp_low` (= act_min + 128, mặc định 0 = kẹp int8 thường; vừa word trạng thái cuối nên không đổi chu kỳ); Python: `activation_min` (Keras
  `activation='relu'` → 0), mapper gửi thanh ghi, tham chiếu kẹp như phần cứng, hậu tố model `_RELU`, móc `OPENEYE_QUANT_SHIFT`. Test mới: `test_int8_clamp.py` (9 RTL),
  `test/cocotb_quantization/` (bộ lượng tử, 2), `test/test_int8_clamp.py` (11). Kiểm chứng: 9/9 + 2/2; đối chứng âm trên RTL cũ 9/9 FAIL; hồi quy 157 test 0 FAIL; 12 case
  mốc 0 chu kỳ lệch; lint fpga 463 → 462 (bớt đúng cảnh báo cắt bit của lỗi này). Vivado 4 ns (`doc/synth/2026-10-28_route4ns_clamp_zu7ev/`, **mốc phần cứng mới**): 0 CRITICAL, LUT +1,3 %, WNS +0,076 ns, đạt 250 MHz. Mục 8b (#24, #29, #30), 8c (K), 8d, 9.
- **Số liệu lỗi quấn vòng** (chỉ đo, không đổi RTL): công cụ mới `doc/experiments/2026-10-28_int8/wrap.py` (+ `wrap_result.txt`). Bảng giá trị ví dụ quấn vòng / kẹp;
  độ chính xác khi chỉ giữ từng nửa phép kẹp (quấn vòng 9,55 % / 9,22 %; chỉ kẹp trên 8,08 % / 43,95 %; chỉ kẹp dưới 97,38 % / 99,18 %; kẹp đủ 97,58 % / 99,25 %, với
  zp −128 / zp 0); tỉ lệ đầu ra ngoài khoảng (vùng ReLU 64–87 % mỗi layer, vượt 127 ≤ 0,23 %); ví dụ conv1 (−150 → 106: chỗ lẽ ra 0 thành giá trị thực 0,647, lớn
  hơn đặc trưng mạnh nhất 0,492). Kết luận: thiệt hại gần hết ở phía âm (ReLU gộp bị mất), lượng tử hoá trước không thay được bước kẹp lúc chạy. Mục 9 (#30),
  `doc/experiments/2026-10-28_int8_clamp.md` mục 3b.

### 2026-10-30

- **Kiểm tra upstream** (`upstream/main` = `93f0e82`): 15 commit mới (DAG, nới độ rộng thanh ghi, Verilator, sửa xếp weight conv), không commit nào về
  lượng tử hoá; chưa lấy (mục 2).
- **PTQ bước 1–2 rồi gỡ bỏ.** Đã làm theo đề xuất (commit `440f36d`: `src/open_eye/ptq.py` lượng tử model TFLite đã huấn luyện cho phần cứng, hook testbench
  `OPENEYE_PTQ`, test `test_ptq.py` và `test_ptq_mnist.py`), sau đó **revert theo yêu cầu của bạn**: model MNIST đã huấn luyện chỉ để hiểu luồng làm việc của
  project, và hướng mong muốn là giữ thiết kế Python cũ, không dựng một đường riêng song song. `dev` trở lại đúng nội dung trước `440f36d` (trừ ghi chép dưới đây).
  Kiểm tra lúc làm rõ: tool của OpenEye (`open_eye.model_loader.load_model`, như notebook gọi) đọc được model int8 (5 layer: conv ×3, dense ×2, **bỏ mất 2 layer
  MaxPool**, weight int8, bias int32, zero point, hệ số Q31), nhưng Python cũ chưa nhận được đối tượng này (`LayerParameters`: `'TFLite_dense' object has no attribute
  'kernel'`), và testcase `model_test` bị upstream tắt; luồng gốc chưa có đường từ model đã lượng tử tới RTL (chỉ đọc model để xem).
- **Giữ ghi chép 3 lỗi phần cứng mới** tìm được khi chạy model thật trên RTL (ảnh test 0 và 1; tham chiếu đã được kiểm độc lập bằng `tools/verify_conv_output.py`):
  **#31** Conv1/Conv2 với input thật thưa mất các tích (phần cứng ra đúng bias: Conv1 ở 25.088/25.088 output), **#32** Conv3 7×7×64 → 64 đổi chỗ bias của cặp filter
  (2k, 2k+1), **#33** Dense 3136 → 10 sai với ảnh 0 (ảnh 1 đúng). Bị che vì dữ liệu test thay số 0 bằng ±1 và cho mọi filter bias 1. Chưa điều tra. Mục 8b,
  cách tái hiện ở mục 3c, chi tiết `doc/experiments/2026-10-30_real_data_bugs.md`.
- **Điều tra lỗi #31** (theo yêu cầu, không sửa RTL; mục 9, `doc/experiments/2026-10-30_bug31_empty_pass.md`, công cụ `doc/experiments/2026-10-30_bug31/`):
  tái hiện bằng luồng gốc của project với weight ngẫu nhiên, chỉ thay input layer 0. Điều kiện: **một lượt tính không có activation khác 0 ở PE nào** (Conv 3×3:
  cửa sổ 3 hàng input toàn 0; Dense: một khối K input của lượt toàn 0) → lượt đó và mọi lượt sau không được tính, output giữ bias, layer vẫn chạy hết. Nguyên nhân
  ở điều khiển RTL: PE chỉ bắt đầu khi có activation khác 0 (`PE.v:1135`), còn `OpenEye_FPGA.v` đếm lượt và khởi động lượt converter/weight kế tiếp khi bus iact
  ready của mảng PE rời trạng thái toàn 1, việc chỉ xảy ra khi có PE bắt đầu tính. **#33 cùng nguyên nhân** (output ảnh 0 = bias + tích của input 0…2653, input
  2654 mở đầu chuỗi 109 số 0). Giả lập một xung ready là chưa đủ (FSM psum chờ psum của PE bỏ lượt). Hướng sửa A (PE rỗng vẫn đi trọn giao thức một lượt, đề
  xuất) hoặc B (đếm lượt theo sự kiện tường minh), cần bạn đồng ý.
- **Kiểm tra upstream có lỗi #31 không:** có. Code (`upstream/main` = `93f0e82`): điều kiện bắt đầu lượt của PE và cơ chế đếm/kích hoạt lượt theo bus iact ready
  giống hệt `dev` (từ `a83260d` 2025-03-19 và `337bd44` 2025-07-22). Chạy trên RTL và testbench của upstream trong worktree (`run31_upstream.py`, probe chèn input
  không sửa file của upstream): ngẫu nhiên và hàng 1–2 toàn 0 PASS, hàng 0–1 toàn 0 FAIL, mọi giá trị sai bằng bias. Mục 9.
- **Đường model thật của toolchain** (`USE_RANDOM_VALUES=0`: PyTorch `SimpleMNISTConvNet` → `onnx2model` → `LayerParameters` → `DRAMContents` → RTL), kiểm tra theo câu
  hỏi của bạn, không sửa gì: Makefile không ghi đè bias/weight; cấu trúc model thật đi qua toolchain được (6 layer, pooling cấu hình cho RTL) nhưng dữ liệu bị thay ở
  Python (weight ×127, bias 1 / c+1, Dense và input ngẫu nhiên, `quantize` mặc định, ReLU bị bỏ qua) và model không được nạp trọng số đã huấn luyện; RTL theo đường
  này FAIL sau pooling đầu (chưa điều tra). Lỗi `LayerParameters` với `tflite2model` là thiếu thuộc tính `kernel` (đường TFLite không nối với toolchain). Mục 8d.
- **Đường model thật của toolchain chở được model đã huấn luyện** (được bạn đồng ý, chỉ Python, mục 8d, `doc/experiments/2026-10-30_onnx_model_flow.md`):
  `has_relu` không được đọc vì `activation_min` (#30) chỉ biết tên `relu`/`activation`; upstream không đọc cờ này ở đâu và cũng không có kẹp ReLU. Điều tra lỗi RTL sau
  pooling của đường này: **lỗi mới #34** (Python, đã sửa): `onnx2model` đặt tên layer MaxPool là `pooling2d` nên `LayerParameters` cấu hình thành average pooling;
  xác nhận trên RTL. Sửa trong file của toolchain: `onnx2model` lượng tử tĩnh (zero point 0, một scale mỗi layer, `QLinearConv`/`QGemm`, `mant`/`shift` 8 bit), tên
  MaxPool; `activation_min` đọc `has_relu`; `DRAMContents` giữ nguyên weight/bias int8 của model và hoán vị weight Dense; testbench nạp `.pth` đã huấn luyện và ảnh
  test thật (`OPENEYE_MODEL_WEIGHTS`, `OPENEYE_INPUT_IMAGE`). Kiểm chứng: `test/test_onnx_model_flow.py` 6/6 (tham chiếu = ONNX Runtime trừ làm tròn, lớp đúng);
  unit test 268 pass, 11 fail có từ trước. RTL với model thật: Conv1/Pool1/Conv2/Pool2 khớp từng bit, Conv3 sai do #32 (13/16 word) và **lỗi mới #35** (cột cuối hàng
  7 pixel khi ghi ngược, 3/16 word; điều tra sau đó: thực ra là #31 ở hàng output cuối, mục dưới); `test/cocotb_fpga/test_real_model.py` 2 xfail.
- **Điều tra lỗi #32 và #35** (theo yêu cầu, không sửa RTL, không sửa `src/`; mục 9, `doc/experiments/2026-10-30_bug32_bias_order.md`, công cụ
  `doc/experiments/2026-10-30_bug32/`): **#32** là thứ tự word bias: khi một địa chỉ bộ đệm psum chứa nhiều filter (Conv3: 2 nhóm kernel trên 2 hàng cluster),
  `psum_pipeline.v` dịch word bias vào từ dưới nên word đầu rơi vào cluster cuối, ngược với thứ tự `psum_stream_mapper` gửi và với cách tính/đọc ra; cặp filter đổi
  bias (4 nhóm: đảo cả nhóm 4). Giả lập bản sửa Python (đảo thứ tự nhóm trong stream bias) cho 0 sai. **#35 chính là #31**: output sai ở hàng output cuối của Conv3
  (cửa sổ có nhóm channel 44–47 toàn 0 → lượt rỗng); "cột cuối" là đọc nhầm layout; đóng #35, gộp vào #31. Mô hình lỗi khớp RTL 3136/3136 ở ảnh 0, 1, 7. **Với #32
  sửa giả lập, ảnh test 1 chạy trọn model đã huấn luyện trên RTL: PASS, khớp từng bit, lớp 2 = nhãn.** Quét 1000 ảnh: #31 chặn 86 % ảnh ở Conv3; độ chính xác ước tính
  61,9 % hôm nay, 72,9 % khi sửa #32, 99,5 % khi sửa cả #31. Sửa lại lý do `xfail` của `test_real_model.py` (ảnh 0: #32 + #31, ảnh 1: #32) và ghi chú đính chính trong
  `2026-10-30_onnx_model_flow.md`. Hướng sửa #32 bằng Python và hướng A cho #31 chờ bạn đồng ý.
- **Sửa lỗi #32 bằng Python** (được bạn đồng ý, mục 9, `doc/experiments/2026-10-30_bug32_bias_order.md` mục 6): `psum_stream_mapper.py` có hàm mới
  `bias_stream_filter_order()`; stream bias Conv (serial) gửi các filter của mỗi địa chỉ bộ đệm psum theo thứ tự nhóm kernel ngược, khớp với cách `psum_pipeline.v`
  dịch word bias vào. Cùng số word, không đổi chu kỳ, không sửa RTL; stream giống hệt khi chỉ có một nhóm kernel hoặc mọi bias bằng nhau. Test mới:
  `test/test_psum_bias_order.py` (22, mô hình nạp bias của RTL; với mapper cũ 15 FAIL), `test_conv_const.py::test_conv_bias_order` (RTL, 2 và 4 nhóm kernel, bias
  khác nhau; với mapper cũ 2 FAIL). **`test_real_model[1]` PASS: ảnh MNIST thật chạy trọn model đã huấn luyện trên RTL, khớp từng bit, lớp 2 = nhãn**; ảnh 0 xfail
  do #31. Unit test 290 pass, 11 fail có từ trước; hồi quy RTL: `test_int8_clamp` 9/9, `test_glb_psum2` 7/7, `test_mnist_layers -k random` 9/9, `test_conv_const`
  36/36 PASS (34 cũ + 2 mới).
- **Sửa lỗi #31 trong `PE.v`** (được bạn đồng ý, hướng A, mục 9, `doc/experiments/2026-10-30_bug31_fix.md`; gồm cả #33, #35): trạng thái mới `EMPTY_PASS`: PE không có
  activation khác 0 (hoặc word weight) vẫn rời IDLE cùng nhịp PE có dữ liệu, giữ iact/wght ready thấp 16 chu kỳ hoặc tới khi FSM psum đọc lượt đó, rồi chuyển psum đi
  qua như PE rảnh. Bản đầu (nâng ready sau 6 chu kỳ) làm Dense có khối 0 bị treo do một xung tính thừa của `OpenEye_Parallel`; bản giữ tới khi đọc psum tốn +4 % chu
  kỳ; bản cuối 0 chu kỳ lệch ở 12 ca mốc. Kiểm chứng: các ca `run31.py` đúng hết (Conv và Dense); test mới `test/cocotb_fpga/test_empty_pass.py` (3, móc testbench
  `OPENEYE_ZERO_BLOCK`; với RTL cũ 3 FAIL); **model MNIST đã huấn luyện chạy trọn mạng trên RTL đúng từng bit ở ảnh test 0–7, lớp đúng cả 8**; lint 0 cảnh báo mới;
  hồi quy RTL 162 test: 157 PASS + 5 xfail đã biết, 0 FAIL; 12 ca mốc 0 chu kỳ lệch; Vivado 0 critical, đạt 250 MHz (WNS +0,074 ns), FF +10/PE, mốc phần cứng mới `doc/synth/2026-10-30_route4ns_fix31_zu7ev/`.

### 2026-10-31

- **Đo model đã huấn luyện trên chip bằng profiler** (2026-10-31, chỉ đo, mục 6.13, `doc/perf/trained_mnist_2026-10-31.md`): ảnh test 0, 1, 2, 7: 213.040–220.941
  chu kỳ (852–884 µs ở 250 MHz), so với 240.671 của `model_mnist_real_c1` (dữ liệu ngẫu nhiên); chỉ pha tính toán khác (bỏ qua số 0): Conv2 −9 % với 44 % số 0, Conv3
  −27 % với 87 % số 0, Dense −21 % với 74 % số 0 (sửa 31/10: bản đầu ghi nhầm −28 % và số Conv3/Dense của ca `_c2`).
- **Phân tích lượng tử động của `onnx2model` cũ / upstream** (2026-10-31, không sửa gì, mục 8d, `doc/experiments/2026-10-30_onnx_model_flow.md` mục 7): scale
  activation tính lúc chạy (uint8, zero point khác 0) nên không đưa xuống phần cứng được; model int8 động mà đường cũ tạo ra ONNX Runtime không chạy được; `has_relu`
  tìm thấy nhưng không dùng; thêm các lỗi trích xuất: `input_scale` = 1,0, kernel chuyển vị sai chiều, Dense đảo `in`/`out`, code tham chiếu chết.
- **Báo cáo tiến độ lần 3** (Word, 2026-10-31): `doc/reports/BaoCao_TienDo_OpenEye_2026-10-31.docx`, tạo bằng
  `~/tools/docenv/bin/python tools/report/make_progress_report_2026-10-31.py` từ số đo (`doc/perf/baseline_2026-10-24`, `doc/perf/trained_mnist_2026-10-31`,
  `doc/perf/paper_table3_2026-10-26_fix25`) và Vivado. 5 hình: đường model thật qua toolchain, chu kỳ theo layer của 7 ca model, pha theo layer của model đã huấn
  luyện, bỏ qua số 0 (ngẫu nhiên so với thật), mạng Bảng 3 trên 16 cấu hình. Khi lấy số cho hình đã sửa 2 chỗ ghi sai: Bảng 3 là **13/16** cấu hình đúng (không phải
  14/16: 7 + 6, `status.json` có 3 FAIL), và hàng `model_mnist_real_c1` trong mục 6.13 lấy nhầm số Conv3/Dense của ca `_c2` (Conv3 −27 %, không phải −28 %).
  Bổ sung cùng ngày (theo câu hỏi của bạn): bảng cấu hình các ca model (mục 4), Hình 4 ghi tỉ lệ số 0 của cả hai ca (ca ngẫu nhiên có 6–11 % số 0 sau layer đầu,
  không phải "không có số 0" như bản đầu), phụ lục A (bỏ qua số 0: chỉ activation khác 0 vào SPad, số chu kỳ nhân ≈ N_khác0 × F / 2 mỗi PE mỗi lượt, cộng
  phần cố định) và phụ lục B (bộ lượng tử: q = kẹp(⌊mant·(psum + offset)/2^shift⌋, act_min, 127), cách tính mant/shift, ReLU bằng act_min = 0, vì sao offset
  luôn 0).
- **Rà soát upstream** (2026-10-31, lúc đó không lấy gì, không sửa RTL; sau đó lấy `e78e5b7`, xem dưới; mục 2, `doc/experiments/2026-10-31_upstream_review.md`, công cụ
  `doc/experiments/2026-10-31_upstream_review/`): 19 commit của upstream chưa có trong `dev`; chạy các ca lỗi còn mở trên upstream nguyên bản và trên `dev`:
  #7 (3 channel), #9, #19b, #21, #23, #27, #28, #29 sai như nhau trên cả hai, upstream còn sai Dense 3136 → 10/16 mà `dev` đúng; không có trường thanh ghi
  nào tràn ở các model của ta. Các lỗi upstream sửa đều đã sửa trong `dev`. Phát hiện thêm: #29 sai cả khi Dense 3136 → 32 đứng một mình (bảng mục 8).
- **Lấy upstream `e78e5b7`** (2026-10-31, được bạn đồng ý, RTL, mục 2 và 9): `git cherry-pick -x e78e5b7` = `5595d15`, xoá `temp_var = 0;` nằm ngoài
  `if (!rst_n) ... else` của khối reset bất đồng bộ của Process 5 trong `OpenEye_FPGA.v`. Kiểm chứng: hồi quy RTL 162 test 157 PASS + 5 xfail đã biết, 0 FAIL;
  bộ lượng tử 2/2; unit test Python 290 pass, 11 fail có từ trước; 12 ca mốc 0 chu kỳ, 0 word DMA lệch; Bảng 3 13/16 và 0 chu kỳ lệch ở cả 16 cấu hình (chạy lại,
  trùng `paper_table3_2026-10-26_fix25`, nên mốc Bảng 3 giữ nguyên); lint `fpga` 462 → 461, baseline đã hạ; Vivado 4 ns 0 CRITICAL, WNS +0,074 ns, mọi báo cáo giống
  từng dòng lần `fix31` (netlist không đổi), mốc phần cứng mới `doc/synth/2026-10-31_route4ns_e78_zu7ev/`.
- **So sánh `551cf85` với `dev`** (2026-10-31, không sửa gì, mục 2, `doc/experiments/2026-10-31_upstream_551cf85_iact.md`): file của commit giống từng byte bản
  `f84f064` (trước `23be043`, có đường FC riêng); 8 ca chạy trên upstream nguyên bản (cha `2dde2db`, `551cf85`, cây trước `23be043`) và `dev`: `dev` 8/8 đúng,
  `551cf85` 6/8 (sai Conv 14×4×8 → 8 `NUM_GLB_IACT=3`, lỗi cũ của module; sai FC K > 2048 vì #19 phần 2 nằm ở `OpenEye_FPGA.v`: K = 2032 đúng, 2064 sai), chu kỳ
  bằng hoặc chậm hơn `dev`; bản cũ còn **mang lại lỗi #13** (Yosys: "multiple conflicting drivers" ở `rd_cycle_loop_cnt_0..3`). Kết luận: hướng của `dev` tốt hơn,
  không lấy. `up_run.py` có thêm tuỳ chọn `GLBI=<n>`.
- **Thí nghiệm `wghts_per_pe + 1`** (dòng RTL của upstream `3258813`, 2026-10-31, được bạn đồng ý thử, **chưa đưa vào `dev`**; mục 9,
  `doc/experiments/2026-10-31_wght_send_end.md`): trong worktree, hồi quy 162 test như `dev`, 12 ca mốc 12/12, model đã huấn luyện ảnh 0/1/2/7 khớp từng bit, Bảng 3
  13/16 như `dev`, lint 0 mới; chu kỳ −0,1 đến −0,3 % (model MNIST −673, chỉ ở pha compute, không phải `load_wght`), DMA và tài nguyên không đổi. Chờ bạn quyết định.
- **Rà README_FI.md cho khỏi lỗi thời** (2026-10-31): mục 2 gộp các lần kiểm tra upstream (19/10, 21/10, 24/10, 30/10, 31/10) thành một bảng trạng thái của cả 22
  commit + danh sách commit đáng xem; mục 3b/3c: đường model thật của toolchain, cách chạy lại #31/#32 trên `dev`, mốc Bảng 3 `fix25`; mục 4: các file fork đã sửa
  (`PE.v` #31, `quantization_unit.v` kẹp int8, `onnx2model.py`, `psum_stream_mapper.py`, `layer_parameters.py`, `dense_mapper.py`, `test_conv_const` 36 test,
  `doc/perf`); mục 7: mốc Bảng 3 và số đo model đã huấn luyện; mục 8: danh sách lỗi còn mở (#24 nay chỉ còn hàm khác ReLU), mốc phần cứng, ghi chú upstream ở
  #19b/#23/#27/#28, hàng C2 (model đã huấn luyện chạy trọn mạng), hàng L mới, trạng thái (C)–(G) của model int8; mục 9b: số lint hiện tại.

### 2026-11-01

- **Đưa dòng `wghts_per_pe + 1` vào `dev`** (được bạn đồng ý, RTL, mục 9; dòng của upstream `3258813`, áp bằng tay, không lấy cả commit): Process 5 của
  `OpenEye_FPGA.v` kết thúc gửi weight ở `fsm_sending_cycle > wghts_per_pe + 1` thay vì `+ 2`, kèm comment giải thích; sửa 2 comment mô tả dải đếm
  (`OpenEye_FPGA.v`, `dense_mapper.py`). Commit dựa trên kết quả thí nghiệm hôm trước trong worktree với đúng dòng này (hồi quy 162 test như `dev`, 12 ca
  mốc, model đã huấn luyện 4 ảnh, Bảng 3 13/16, −0,1 đến −0,3 % chu kỳ; `doc/experiments/2026-10-31_wght_send_end.md`). Trên `dev`: lint 0 mới, unit test
  Python 290 pass / 11 fail có từ trước, bộ lượng tử 2/2, 16/162 test hồi quy đầu PASS/xfail rồi dừng theo yêu cầu. Chưa chạy Vivado, chưa lưu mốc chu kỳ mới
  (mục 7).

### 2026-11-02

- **Mốc mới sau dòng `wghts_per_pe + 1`** (theo yêu cầu, không sửa RTL): `tools/run_profile.py --compare doc/perf/baseline_2026-10-24 --save
  doc/perf/baseline_2026-11-02 --report doc/perf/baseline_2026-11-02.md`: 12/12 PASS, 0 … −673 chu kỳ mỗi case (`model_mnist_real_c1` 239.998, `_c2` 242.844,
  `mnist1/2/3` 54.936 / 65.304 / 20.520, `model_mnist16_c2` 49.930), trùng đúng số của worktree thí nghiệm, số word DMA không đổi; **`baseline_2026-11-02` là mốc
  chu kỳ hiện tại** (mục 7; các lệnh mẫu ở mục 3c và 6 đã đổi sang mốc này). Vivado 4 ns (`doc/synth/2026-11-02_route4ns_wsend_zu7ev/`, **mốc phần cứng mới**):
  0 ERROR, 0 CRITICAL, cảnh báo như cũ (thêm 1 dòng `DRC 23-814` của chế độ out-of-context); LUT 60.840 → 60.641 sau route, FF 39.796 → 39.790; timing sau tổng
  hợp không đổi (+0,205 ns); sau route WNS +0,074 → **+0,020 ns** (vẫn đạt 250 MHz, biên nhỏ nhất từ trước tới nay): đường găng mới là chuỗi so sánh của
  `fsm_cycle` tới `router_configurator`, không chứa phép so sánh vừa sửa, nên là dao động của placement/routing (mục 6d).
- **Kế hoạch hàm kích hoạt** (theo yêu cầu, chưa sửa gì; `doc/experiments/2026-11-02_activation_plan.md`, mục 8c hàng M): ReLU đã có (cận dưới của bộ kẹp);
  Leaky ReLU bằng hai độ dốc trong bộ lượng tử (mantissa/shift riêng cho psum âm, dùng chung bộ nhân, 0 chu kỳ, trường mới nằm trong 24 bit trống của word
  trạng thái cuối nên 0 word DMA); SiLU và hard-swish bằng bảng tra 256 entry int8 → int8 sau bộ kẹp (8 bản LUTRAM cho 8 lane, nạp 32 word ở trạng thái mới
  `GET_ACTIVATION` = mã 15 còn trống, chỉ khi layer dùng bảng). Giữ độ trễ 3 chu kỳ của bộ lượng tử (đọc LUTRAM không đồng bộ) để không động vào các chuỗi trễ
  3 chu kỳ của bộ ghi ngược (chỗ lỗi #25/#26); thêm bit làm tròn để giữ số 0 cho bỏ-qua-số-0. Toolchain: PyTorch xuất `LeakyRelu`, `Sigmoid` + `Mul` (SiLU),
  `HardSwish` (ONNX Runtime không lượng tử op này). Profiler: pha `load_act` (nạp bảng), bộ đếm của khối kích hoạt theo layer (giá trị, chu kỳ bận, số 0 ở
  đầu ra), và chi phí đo bằng `--compare` với chế độ không kích hoạt.
- **Hàm kích hoạt, bước A** (theo yêu cầu, chỉ Python, không sửa RTL; `doc/experiments/2026-11-02_activation.md`, công cụ
  `doc/experiments/2026-11-02_activation/`): `SimpleMNISTConvNet(activation=...)` (relu mặc định = model gốc, leaky_relu 0,1, silu, hardswish);
  `models/train_mnist.py` huấn luyện như notebook (float 99,33 / 99,29 / 99,36 %, ReLU gốc 99,35 %); `onnx2model` nhận ra `QLinearLeakyRelu`,
  `QLinearSigmoid` + `QLinearMul` (SiLU), `HardSigmoid` + `QLinearMul` (hard-swish, ONNX Runtime không lượng tử `HardSwish`) và tính tham số phần cứng theo
  scale đầu vào của layer tính kế tiếp (gộp cả bước lượng tử lại quanh `Flatten` float); điền shape mà suy luận ONNX bỏ trống sau op com.microsoft;
  `LayerParameters` có `act_mode` (none/relu/leaky/table), `act_negative`, `act_table`, `act_round`; tham chiếu `batchnorm_output` tính hai độ dốc, bảng 256 ô
  và làm tròn (đường ReLU cũ giữ nguyên); mapper từ chối layer dùng chế độ mới (`check_rtl_activation`) cho tới bước B. Test mới `test/test_activation.py`
  29/29 (so với ONNX Runtime: làm tròn xuống lệch tới 7 ở conv3, làm tròn gần nhất ≤ 4); unit test 319 pass, 11 fail có từ trước; RTL với toolchain mới:
  `test_real_model` 2/2, `test_int8_clamp` 9/9. 10.000 ảnh test: int8 như phần cứng sẽ tính 99,34 % (Leaky), 99,27 % (SiLU), 99,35 % (hard-swish), so với
  ReLU 99,35 %; nhưng số 0 ở đầu vào các layer chỉ còn 1–23 % (ReLU 39–83 %), nên ước tính compute +7 đến +10,5 % của model; làm tròn gần nhất (Leaky:
  từ +10,5 % xuống +7,4 %) và đặt các ô ±1 của bảng về 0 (SiLU/hard-swish: +9 % xuống +7 %, không mất độ chính xác) giúp lấy lại một phần.
- **Thiết kế RTL bước B để duyệt** (theo yêu cầu, chưa sửa RTL; `doc/experiments/2026-11-02_activation_rtl_design.md`): 19 bit cấu hình mới (`act_mode`,
  `act_round`, `act_neg_mant`, `act_neg_shift`, `act_keep_table`) trong 24 bit trống của word trạng thái cuối (0 word DMA thêm); `quantization_unit.v` chọn độ
  dốc âm và cờ làm tròn ở tầng 1 (dấu của tổng có sẵn ở đó), DSP48E2 cộng hằng số làm tròn trong phép nhân (A·B + C), tầng 3 không đổi; module mới
  `activation_table.v`: bảng 256 ô chia 8 bank LUTRAM (32 ô mỗi bank ở DMA 64 bit) để mỗi word DMA ghi 8 ô trong 1 chu kỳ, đọc không đồng bộ ngay sau thanh ghi
  đầu ra của bộ lượng tử, chỉ cho `WRITEBACK_WORDS` lane (4); trạng thái `GET_ACTIVATION` (mã 15) nạp 32 word sau `GET_QUANTIZE`, không bong bóng trong stream;
  giữ độ trễ 3 chu kỳ (phía nhận chép thẳng `quantized_value_reg` vào `iact_to_psum_mux_reg`), phương án dự phòng 4 tầng nếu Vivado không đạt; ước tính
  khoảng 300 LUT (+0,5 %), 70 FF, 0 BRAM/DSP; profiler dùng một dây trace `act_capture`.
- **Hàm kích hoạt, bước B: RTL** (được bạn đồng ý; mục 9, `doc/experiments/2026-11-02_activation_rtl.md`): `quantization_unit.v` (độ dốc âm Leaky, làm tròn), module mới
  `activation_table.v` (bảng 256 ô, bank LUTRAM), `psum_pipeline.v`, `OpenEye_FPGA.v` (trạng thái `GET_ACTIVATION` = 15, dây trace `act_capture`), 5 trường trong
  `regmap.yaml` (không thêm word trạng thái ở DMA 32/64/128 bit); mapper gửi trường và bảng; móc test `OPENEYE_ACTIVATION`; testbench mới `test_activation_rtl.py`,
  `cocotb_activation_table/`, mở rộng testbench bộ lượng tử, `test_real_model_activation`. Hồi quy 180 test 175 PASS + 5 xfail, 0 FAIL; 3 model đã huấn luyện
  khớp từng bit trên RTL; 12 ca mốc và Bảng 3 0 chu kỳ lệch (Bảng 3 lưu thành mốc mới `paper_table3_2026-11-02`); lint `fpga` 460; Vivado 0 CRITICAL, WNS
  +0,045 ns, LUT +778 (+1,3 %), mốc phần cứng mới `doc/synth/2026-11-02_route4ns_act_zu7ev/`.
- **Hàm kích hoạt, bước C: profiler** (theo yêu cầu, chỉ Python, không sửa RTL; mục 6.15, `doc/experiments/2026-11-02_activation_profiler.md`, số đo
  `doc/perf/activation_2026-11-02.md`): pha `load_act` (trạng thái 15), `activation_cycles` theo layer từ dây trace `act_capture`, hàm kích hoạt và số 0 / số
  âm ở input của từng layer (từ tham chiếu của testbench, `profile_set_layer_input`), bảng hàm kích hoạt trong `profile_report`, cột `load_act` trong
  `paper_table3.py` khi có (bảng cũ không đổi). Model đã huấn luyện, ảnh 0: ReLU 218.925, Leaky ReLU 238.049 (+8,7 %), SiLU 240.229 (+9,7 %), hard-swish
  240.293 chu kỳ (+9,8 %); ghi ngược giống nhau từng chu kỳ (0 chu kỳ mỗi giá trị), bảng 3 × 32 chu kỳ, còn lại là `compute` vì số 0 ở input Conv2 / Conv3 /
  Dense giảm từ 43,5 / 87,3 / 74,3 % (ReLU) xuống 6–24 / 7–15 / 7–18 %. 7/7 lần chạy PASS; 12 ca mốc 0 lệch; unit test 324 pass, 11 fail có từ trước.
- **Độ trễ của từng hàm trên cùng một model** (theo yêu cầu, chỉ đo, không sửa RTL; mục 6.15, `doc/experiments/2026-11-02_activation_profiler.md` mục 4b,
  script `doc/experiments/2026-11-02_activation/run_same_weights.py`): trọng số ReLU đã huấn luyện chạy với Leaky ReLU / SiLU / hard-swish thay cho ReLU,
  ảnh 0: 238.786 (+9,1 %) / 240.728 (+10,0 %) / 240.560 chu kỳ (+9,9 %) so với 218.925; 3/3 PASS khớp từng bit, DUT ra lớp 7; gần như trùng với các model có
  trọng số riêng (+8,7 / +9,7 / +9,8 %), nên chi phí là của hàm, không phải của trọng số. Profile `doc/perf/activation_2026-11-02/same_weights_*.json`.
- **Rà soát README** (theo yêu cầu): mục 3b (biến thể hàm kích hoạt, stream có bảng, profiler đọc `act_capture`), 3c (ngày cập nhật; thêm `test_pooling.py`,
  `test_nets.py` vào bảng test; bộ hồi quy 180 test; biến môi trường `OPENEYE_ACTIVATION`, `OPENEYE_QUANT_SHIFT`; hàng #24 của bảng tái hiện lỗi), 4 (cây thư
  mục: `layer_parameters`, mapper, `data_create`, `simple_layer_operations`, `rtl_test_utils`, `regmap.yaml` ★, `test_pooling`/`test_nets`), 5.4 (mốc phần
  cứng `2026-11-02_route4ns_act_zu7ev` thay cho `fix31`), 6.5 (bảng layer, bảng hàm kích hoạt), 6d (bảng Vivado hiện tại là lần `act`, kèm cột `wsend`),
  7 (ảnh 0 đo lại trên `dev`, kết quả hàm kích hoạt), 8 và 8c (mốc phần cứng 61,4k LUT, WNS +0,045 ns; việc đo hàm kích hoạt; thứ tự đề xuất), 9b (lint
  `fpga` 461 → 460 sau bước B). Upstream kiểm tra lại: vẫn `93f0e82`, mục 2 còn đúng.

### 2026-11-03

- **Giải thích hàm kích hoạt trên phần cứng** (theo yêu cầu, chỉ tài liệu): mục 9, phần "Bảng của SiLU / hard-swish, vì sao Leaky ReLU không cần bảng,
  3 tầng của bộ lượng tử": nội dung bảng 256 ô và cách đóng gói thành 32 word DMA (ví dụ bảng SiLU của Conv1), nạp ở `GET_ACTIVATION` (96 chu kỳ = 3 × 32
  ở pha `load_act`, không phải `load_iact`); Leaky ReLU chỉ cần cặp hệ số thứ hai vì là hai đoạn thẳng; 3 tầng của `quantization_unit.v` và chỗ mỗi hàm chen
  vào (bộ chọn độ dốc ở tầng 1, cộng làm tròn ở tầng 2, tra bảng sau tầng 3 trong cùng chu kỳ), ví dụ psum = −5000 qua từng tầng; vì sao pha ghi ngược
  không dài thêm.
- **Điều tra 3 cấu hình CR 1 còn FAIL của Bảng 3** (theo yêu cầu, không sửa RTL; mục 9, `doc/experiments/2026-11-03_table3_cr1.md`, script
  `doc/experiments/2026-11-03_table3_cr1/`): 3 lỗi RTL riêng biệt. **#29** (tràn bộ đệm weight 4.096 hàng; Dense 1568 → 32 ở CR 1 Y 3 và 3136 → 32 ở cấu hình
  MNIST cần 4.224 hàng; trước đây CR 1 X 4 Y 3 bị ghi nhầm là #19b): `BUFFER_WIDTH_WGHT=13` cho cả mạng CR 1 X 4 Y 3 PASS. **#28** (ở CR 1, điều kiện
  `all_psum_ready` chỉ xét GLB chẵn, nên thu psum khi cột PE lẻ còn đang tính; lỗi phụ thuộc dữ liệu, pixel cuối của lượt x): giả lập AND cả 4 bit chữa mọi ca lỗi,
  0 đến ±16 chu kỳ. **#36** (Dense đọc ra cuối ở CR 1 X 2 mất output của cụm cột 1 vì thanh ghi đọc ra chỉ 80 bit). Phát hiện phụ **#37** (trường 12 bit
  không chứa được 4.096: Conv 14×14×32 ở CR 1 X 2). Sửa lại bảng lỗi 8b (#19b, #28, #29, thêm #36, #37), mục 2 (`655a2ae`), 6.14, 8, 8c (hàng N), bảng tái hiện
  lỗi. Upstream: vẫn `93f0e82`, có đủ 3 lỗi; `655a2ae` (nới trường/bộ đếm) không giải quyết lỗi nào trong số này. Chờ đồng ý để sửa.
- **Sửa #28, #29, #36** (được bạn đồng ý; mục 9 "Sửa #28, #29, #36", `doc/experiments/2026-11-03_table3_cr1.md` mục Fixes): #29 `BUFFER_WIDTH_WGHT` mặc định
  12 → 13 (bộ đệm weight 8.192 hàng, đặt vào URAM bằng tham số mới `RamStyle` của `RAM_SP`) và toolchain từ chối layer không vừa (`check_wght_buffer`; lỗi của
  mapper trong process con nay được báo ra ở `write_stream`); #28 `psum_pipeline.v`: ở `CLUSTER_ROWS = 1` điều kiện ready xét cả hai GLB của mỗi cặp; #36
  `psum_pipeline.v`: thanh ghi đọc ra rộng `max(bus psum, CLUSTER_COLUMNS × DMA_BITWIDTH)`. Test mới `test_cluster_rows1.py` (4: đối chứng âm 4/4 FAIL trước
  bản sửa, 4/4 PASS sau) và `test_wght_buffer.py` (4). Hồi quy 184 test 179 PASS + 5 xfail; 12 ca mốc 0 chu kỳ lệch; **Bảng 3 16/16 PASS** lần đầu (mốc mới
  `doc/perf/paper_table3_2026-11-03`, 13 cấu hình cũ giống hệt từng chu kỳ); unit test 328 pass; lint `fpga` 459 (0 mới); Vivado 4 ns 0 CRITICAL, WNS +0,075 ns,
  URAM 8 → 12, BRAM / LUT không tăng, **mốc phần cứng mới** `doc/synth/2026-11-03_route4ns_cr1fix_zu7ev/`.

### 2026-11-04

- **Upstream có 2 commit mới** `9498271` "Added new parameters" và `36395dd` "Implemented more functional layers for bigger inputs and single channel"
  (DenLeb, 2026-11-03; `upstream/main` = `36395dd`). Điều tra bằng worktree riêng, chạy cùng các ca của mình (`doc/experiments/2026-11-04_upstream_36395dd.md`):
  `9498271` thêm tham số `CYCLE_WIDTH`, `LIMIT_SIZE_*` và nới nhiều trường trạng thái (`needed_cycles` 18 → 32 bit, trường iact 16 bit ở 2 cụm...); `36395dd`
  nới bộ đếm trong RTL và **viết lại đường 1 channel** (`iact_stream_constructor.v` bỏ các nhánh riêng cho 1 channel, `data_pipeline_iact.v` quay vòng bộ đếm
  sub-word khi `first_spad_max_i == 1`) cùng phần Python dựa trên DAG `c342d04`. Kết quả: upstream **sửa được #17** (Conv 28×28×1 không cần đệm channel,
  khoảng 5 % ít chu kỳ hơn workaround của mình) và **#37** (Conv 14×14×32 ở CR 1 X 2), nhưng vẫn còn #29, #36 và FAIL Dense 3136 → 10 (đều đúng trên `dev`),
  phần Python phụ thuộc DAG chưa lấy. Không lấy gì; đề xuất chép tay từng phần (hàng **O** của 8c), chờ đồng ý. Cập nhật mục 2, 8b (#17, #37), 8c.
- **Sửa #38** (được bạn đồng ý; mục 9 "Sửa #38", `doc/experiments/2026-11-04_bug38_mantissa.md`): `OpenEye_FPGA.v` cắt exponent và mantissa của bảng lượng tử
  bằng `+:OFFSET_WIDTH` (8 bit), nên mantissa ≥ 256 bị lấy mod 256; sửa thành `+:EXPONENT_WIDTH`, `+:MANTISSA_WIDTH`. Toolchain `MANT_BITS` 8 → 24 (hệ số
  bằng đúng scale float32 của ONNX Runtime), độ dốc âm Leaky giữ 8 bit (`NEG_MANT_BITS`); móc test `OPENEYE_QUANT_MANT`; test mới `test_quant_mantissa.py`
  (đối chứng âm 3/3 FAIL, sau sửa 3/3 PASS). Hồi quy 187 = 182 PASS + 5 xfail; 12 ca mốc 0 chu kỳ lệch; model đã huấn luyện ảnh 0 ReLU −1, Leaky 0, SiLU +1, hard-swish −6 chu kỳ (chỉ ở Dense; `doc/perf/activation_2026-11-04_mant24.md`);
  so với ONNX Runtime gần hơn một chút (lệch lớn nhất 3 → 2 / 2 → 1 / 3 → 1 ở vài layer); unit test 328 pass; lint `fpga` 459 → 457. Vivado 4 ns: 0 CRITICAL, WNS +0,044 ns (đạt 250 MHz), DSP vẫn 4, mỗi bộ lượng tử +69 LUT +17 FF; **mốc phần cứng mới**
  `doc/synth/2026-11-04_route4ns_fix38_zu7ev/`. Cập nhật mục 4, 6.15 (dòng sau #38), 6d, 7, 8, 8b, 8d (F), 9 (ví dụ hệ số của các hàm kích hoạt nay là
  hệ số 24 bit, kết quả ví dụ không đổi), 9b; mục 7 còn ghi mốc Bảng 3 cũ `paper_table3_2026-11-02` (13/16) từ trước: sửa thành `2026-11-03` (16/16).
- **Hàng O: sửa #37 và #17, phát hiện và sửa #39** (được bạn đồng ý; mục 9 "Sửa #37, #17 (hàng O ...) và #39",
  `doc/experiments/2026-11-04_rowO_bug17_bug37.md`, script `doc/experiments/2026-11-04_bug39/`). #37: 10 trường bộ đệm iact, dây và thanh ghi địa chỉ
  constructor 12 → 13 bit (`IACT_BUFFER_ADDR_WIDTH`), 4 trường kích hoạt chuyển vào chỗ trống để giữ 28 / 14 / 7 word trạng thái, `check_iact_buffer`.
  #17 (như upstream `36395dd`): bỏ gói 2 hàng/word cho 1 channel trong `iact_stream_constructor.v`, PE lấy sub-word 0 (`data_pipeline_iact.v`, bỏ logic
  "dòng lệch"), `channel_pad` tắt mặc định. #39 (Python, có từ trước, upstream cũng có): layer 1 channel từ 2 lượt weight tính nhóm filter sau bằng weight
  nhóm đầu vì stream chỉ chứa 1 bộ weight; `wght_transmissions_pe` = số lô channel × số nhóm filter. Hồi quy 189 = 185 PASS + 4 xfail; mốc chu kỳ mới
  `baseline_2026-11-04` (11 ca giống hệt, `model_mnist_real_c1` −360), Bảng 3 mới `paper_table3_2026-11-04` (16/16, 12 cấu hình −192 … −408), 4 model hàm
  kích hoạt −360 (ReLU 218.564); số đo thật của #17 là −1,1 % ở Conv1 (không phải 5 % như ước tính). Unit test 337 pass; lint `fpga` 457 → 444. Vivado 4 ns: 0 CRITICAL, WNS +0,077 ns, LUT −1.547, FF −525, BRAM 192 → 188; **mốc phần cứng mới**
  `doc/synth/2026-11-04_route4ns_rowO_zu7ev/`. Cập nhật mục 2, 3b, 3c, 4, 5, 6.13, 6.14, 6.15, 6d, 7, 8, 8b (#17, #37, thêm #39), 8c (hàng O xong), 9, 9b.

### 2026-11-05

- **#39: điều tra chi tiết và phép kiểm tra `check_wght_sets`** (hướng 1, được bạn đồng ý; chỉ Python, không sửa RTL; mục 9 "#39, điều tra thêm",
  `doc/experiments/2026-11-05_bug39_detail.md`, script `grid39.py`, `upgrid39.py`, `probe39.py` thêm `B39_WDATA` / `B39_ZERO_FILTERS`, `run39.py` thêm `K` /
  `CR` / `GLBP` / `GLBW` / `QA`). Quy tắc chính xác (kernel 3×3): 1 channel và hơn 16 filter mỗi lần tính; RTL đọc hàng chưa ghi của bộ đệm weight (X trong
  mô phỏng, giữ weight lượt trước), không sai phép tính. `check_wght_sets` (`layer_parameters.py`, gọi trong `ConvMapper`) từ chối layer có số bộ weight ≠
  số lượt weight × số lô channel, không đổi stream; tìm ra **#39b** (nhánh tile, psum làm tròn xuống / weight làm tròn lên: k3 3 channel × 64/96/128 filter,
  66 cấu hình; k1 140; k7 635), mọi cấu hình đó vốn hỏng vì lỗi khác, nay bị từ chối, chưa sửa. **Upstream:** `upstream/main` = `b10db82` (04/11, "Re-Enabled
  python interface for DW Conv"); `36395dd` có đúng #39 (178 cấu hình, vá công thức thì PASS), `b10db82` còn 118 (1 channel hơn 32 filter mỗi lần tính: FAIL
  toàn bộ map; vá thì treo, lỗi riêng của upstream, không điều tra), #39b có ở mọi bản. Không lấy gì từ `b10db82`. Test mới 3 hàm (50 test) trong
  `test/test_channel_pad.py`; unit test 369 pass; hồi quy 189 = 185 PASS + 4 xfail; mốc chu kỳ, Bảng 3 và mốc phần cứng không đổi. Cập nhật mục 2 (`b10db82`),
  3c, 8b (#39), 9.
- **Điều tra lỗi treo của `b10db82`, phát hiện #40** (chỉ điều tra, không sửa RTL, không đổi Python của `dev`; mục 9 "Lỗi treo của `b10db82`",
  `doc/experiments/2026-11-05_b10db82_hang.md`, script `doc/experiments/2026-11-05_b10db82_hang/`). Treo khi lượt weight cuối thiếu filter: mapper upstream
  ghi weight filter đệm thành số 0 → word toàn 0 → PE nhận 2 thay vì 3 con trỏ cột → kẹt ở CALCULATING (cơ chế #22, fork đã sửa). #40 (cả `dev`): số word
  output/bias và tham chiếu tính theo số filter thật, RTL gửi đủ ô đệm nên dừng sớm (1/4 output mất với 16 + 8); RTL tính đúng. Cập nhật mục 2 (`b10db82`),
  8b (thêm #40), 9.
- **Phép kiểm tra `check_full_passes` cho #40** (hướng 1, được bạn đồng ý; mục 9, `doc/experiments/2026-11-05_b10db82_hang.md` mục 7): Python, từ chối
  Conv có số ô filter ≠ số filter; 34 unit test mới (403 pass); quét tĩnh 78 layer Conv của Bảng 3, ca mốc và model hàm kích hoạt: 0 bị chặn; hồi quy
  189 test = 185 PASS + 4 xfail, 0 FAIL. Cập nhật mục 3c, 8b (#40), 9.
- **Báo cáo Word lần 4 về hàm kích hoạt** (`doc/reports/BaoCao_HamKichHoat_OpenEye_2026-11-05.docx` + 4 hình, sinh bằng
  `~/tools/docenv/bin/python tools/report/make_activation_report_2026-11-05.py` từ `doc/perf/activation_2026-11-04_rowO/` và các tài liệu bước A/B/C):
  cách tính từng hàm, bước A (toolchain, độ chính xác 10.000 ảnh), bước B (RTL, kiểm chứng, tài nguyên), bước C/D (đo chu kỳ, số 0), các việc khác
  từ báo cáo 31/10, định hướng.

### 2026-11-06

- **Rà soát 5 commit mới của upstream** (`e8b3c3e`, `2abe8d4`, `0d5a0e3`, `7465852`, `b1e02a0`, 05/11; `upstream/main` = `b1e02a0`): **không lấy**,
  không sửa file nào của `dev` (`doc/experiments/2026-11-06_upstream_dw_review.md`, script `mkv.sh`). Depthwise viết lại trong FSM dense của PE vẫn
  **sai ở cả 3 ca** (4×1×4, 12×2×8, 8×8×4) ngay trong luồng Makefile của upstream, trước (`b10db82`) và sau; Conv dense giống hệt từng ns; bộ sinh địa chỉ
  đọc iact mới có lỗi `rd_cycle_loop_cnt_4` không đếm và `rd_addr_inc_4_next` bị gán 2 lần; nới `CHANNEL_CYCLE_WIDTH` làm dở. Có thể lấy riêng (cần đồng ý):
  2 khai báo `reg` → `wire`, công tắc `WAVES`. Cài Verilator 5.044 (`~/tools/verilator-5.044`) cho luồng Makefile cocotb của upstream. Cập nhật mục 2, 3.

### 2026-11-07

- **Tổng hợp lỗi còn mở khi chạy model thật** (mục 8e mới; không sửa RTL, không sửa Python): model MNIST của repo vẫn đúng; chia các lỗi còn lại thành
  sai lặng lẽ / bị từ chối / treo / chưa có / FPGA. Chạy thêm 4 ca trên RTL của fork: Conv stride 2 **FAIL** (lỗi mới **#41**), stride 1 và hai Conv 1×1 nhỏ
  PASS. Đọc code thấy thêm **#42** (toolchain luôn dùng padding "same") và **#43** (`onnx2model`: input giả cố định 1 × 1 × 28 × 28, bỏ lặng lẽ op không
  hỗ trợ, không đọc `group`). Cập nhật mục 8b (#41–#43), 8e.
- **Phép kiểm tra Python cho nhóm A, điều tra #41, xác nhận lỗi theo tài liệu** (không sửa RTL; `doc/experiments/2026-11-07_bug41_stride.md`,
  script `doc/experiments/2026-11-07_bug41_stride/`). #41: phần cứng mặc định dựng với `STRIDE_ENABLED=0` (tham số có từ upstream `2e3b351`) nên
  bỏ stride trục X; dựng với `STRIDE_ENABLED=1` thì stride 2 đúng ở độ rộng 8, 16, 24, 28, 32 nhưng vẫn sai ở 4, 6, 7, 9, 12 (#41b mới: cửa sổ đúng,
  thứ tự / số output sai); upstream `b1e02a0` cùng mặc định, cùng lỗi, testbench upstream còn giải mã stride lệch một hàng; Yosys: bật stride
  +75 LUT mỗi constructor. Phép kiểm tra mới: `check_conv_geometry` (mọi stride > 1, padding khác `kernel // 2` gồm TF "same" lệch, dilation,
  groups, số channel lẻ > 1), `check_pooling_geometry` (#27: đo được input rộng ≤ 4 sai; cửa sổ khác 2 × 2 / stride 2), `check_dense_readout`
  (#21, tái hiện lại: 30/40 output sai), `onnx2model.check_supported_graph` (op lạ, residual, `group` / `dilations`, chuỗi layer, hàm kích hoạt;
  input giả khi export theo dữ liệu hiệu chỉnh), `pytorch2model` (stride / padding / groups / dilation, module lạ), `DWMapper` báo không có
  depthwise; `OPENEYE_ALLOW_UNSUPPORTED=1` để tái hiện (test 3 channel dùng nó). #19b không tái hiện lại được (seed 1–5 trên `dev`, cả commit
  gốc `10bcaf7`). Lỗi mới #44 (`pytorch2model` không chuyển được layer float, có từ trước). Tài liệu trong `doc/`: #7, #21, #27, #41b là lỗi thật;
  #42, #43 và pooling 2 × 2 là giới hạn thiết kế mà toolchain phải báo. Unit test 459 pass (+56 `test_model_guards.py`); quét tĩnh 163 layer của
  Bảng 3, ca mốc, model hàm kích hoạt: 0 bị chặn; hồi quy RTL 189 test = 185 PASS + 4 xfail đã biết, 0 FAIL (như trước; `test_nets` chạy lại riêng vì script hồi quy thiếu `venv/bin` trong PATH, đã sửa). Cập nhật mục 2, 3c, 8b (#7, #19b, #21, #23, #27, #41–#44), 8e.

### 2026-11-08

- **Điều tra #41b** (không sửa file nào của `dev`, thử trong worktree tạm; `doc/experiments/2026-11-07_bug41_stride.md` mục 8, công cụ mới
  `slot_map.py`, `padcheck.py`, bản vá thử `fix41b_scratch.patch`). Hai nguyên nhân Python: (A) `calculate_conv_serial` chuyển kernel theo
  `add_up` (pixel input) thay vì `psum_add_up` (vị trí output) → thứ tự giải mã lệch khi hàng output có đệm và một lần tính nhiều kernel
  (rộng 4, 6, 12); (B) `iact_x_add_up` của ảnh lẻ thiếu một cột (rộng 7, 9). A + B: mọi layer stride 2 đơn lẻ đã thử đúng giá trị, stride 1
  không đổi. Thêm **#41c** (RTL: pha ghi ngược đếm theo kích thước input; bản vá 2 dòng thử trong worktree làm chuỗi stride 2 đúng, chuỗi
  stride 1 cùng chu kỳ) và **#41d** (layer stride 2 đọc input trên chip có chiều cao lẻ mất hàng output cuối, chưa truy). Đề xuất 5 bước (mục 8.6
  của tài liệu), chờ đồng ý. Cập nhật mục 8b (#41, thêm #41b–#41d), 8e.
- **Sửa #41b, #41c, #41d** (được bạn đồng ý, bước 1–4; mục 9 "Sửa #41b, #41c, #41d", `doc/experiments/2026-11-07_bug41_stride.md` mục 9). Python:
  thứ tự output (A), `iact_x_add_up` ảnh lẻ (B), `iact_y_add_up` ảnh cao lẻ (#41d: một lượt thiếu hàng đệm dưới; tìm ra bằng `DUMP_IACT_IMAGE`),
  `fsm_psum_limit` ghi ngược theo output (W), thứ tự làm phẳng Conv → Dense theo output (F, lỗi thêm tìm ra khi kiểm chứng); RTL 2 dòng
  `RECEIVE_PSUMS_TO_IACT` (#41c); phép kiểm tra chỉ còn chặn stride khi `STRIDE_ENABLED=0`; mode `Conv_Dense`; test `test_stride_params.py` (15),
  `test_stride.py` (12, RTL `STRIDE_ENABLED=1`; trên `69320ba` 10 FAIL). Hồi quy 201 = 197 PASS + 4 xfail, 0 FAIL; 12 ca mốc và Bảng 3 16/16 giống
  hệt (0 chu kỳ); unit test 474 pass; lint `fpga` 444 → 443; Vivado 4 ns: 0 CRITICAL, LUT/FF/BRAM như cũ, WNS +0,009 ns (đạt 250 MHz; đường găng do route), mốc phần cứng mới `doc/synth/2026-11-08_route4ns_fix41_zu7ev/`. Thêm mục 5.10 (stride và `STRIDE_ENABLED`). Cập nhật mục 3c, 4, 5, 6d, 8b, 8e, 9, 9b.

### 2026-11-09

- **Đề xuất 5: `STRIDE_ENABLED = 1` làm mặc định** (được bạn đồng ý; mục 9 "`STRIDE_ENABLED = 1` làm mặc định", mục 5.10). Vivado 4 ns với cùng RTL
  (`doc/synth/2026-11-09_route4ns_stride1_zu7ev/`, mốc phần cứng mới): 0 CRITICAL, cảnh báo như cũ, +155 LUT (+0,25 %), +7 FF, BRAM / URAM / DSP như cũ,
  WNS +0,042 ns (đạt 250 MHz); ước lượng Yosys +300 LUT là quá cao (phép nhân `pec × stride` có `pec` hằng). Với `STRIDE_ENABLED=1`: hồi quy 201 test =
  197 PASS + 4 xfail, 12 ca mốc và Bảng 3 giống hệt (0 chu kỳ), lint 0 cảnh báo mới. Đổi mặc định trong `open_eye_parameters.py` và
  `OpenEye_FPGA.v`; kiểm lại không đặt biến: export Vivado giống hệt, unit test 474 pass, Conv 7×7 stride 2 PASS. Cập nhật mục 3c (biến môi trường),
  5.10, 6d (cấu hình, mốc, lịch sử), 8b (#41), 8e, 9.
