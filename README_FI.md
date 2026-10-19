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

### Upstream mới so với `dev` (kiểm tra ngày 2026-10-19)

`dev` dựa trên upstream `c4bd562`. `git log dev..upstream/main` cho 6 commit (12–15/10/2026). Commit merge `c085224` chỉ đưa `c4bd562`
vào nhánh main của upstream, nên `dev` đã có nội dung đó. **Upstream không động tới các file mà mình đã sửa lỗi** (`psum_pipeline.v`,
`iact_stream_constructor.v`, phần `GET_BIAS` của `OpenEye_FPGA.v`, `conv_mapper.py`), nên các bản sửa #3, #6/#7, #13, #14, #18 vẫn chỉ có ở `dev`.

| Commit | Thay đổi | So với `dev` | Nên lấy? |
|---|---|---|---|
| `b6fa369` | Sửa comment `TRANS_WORDS` trong `OpenEye_FPGA.v` ("số word mỗi lần truyền từ layer sang layer") | Chỉ comment | **Nên**, không rủi ro |
| `2c8c324` | `OpenEye_Parallel.v`: 4 khối generate của router **psum** đặt nhầm tên `gen_router_iact_*` → `gen_router_psum_*` | Chỉ đổi tên hierarchy; không xung đột thật (hai vòng `for` không tên khác nhau); không file nào của mình tham chiếu các tên này | **Nên**: tên trong báo cáo Vivado và khi debug đúng hơn |
| `fc9ace3` | `test/cocotb_fpga/Makefile`: đổi cấu hình mặc định khi chạy bằng `make` (`Convolution_Single`, 16 filter, `NUM_GLB_PSUM=4`, `QUANT_AMOUNT=64`, `TRANS_WORDS=4`, `STRIDE_ENABLED=1`, ...) | Mình chạy test qua pytest (`test_*.py`), không dùng Makefile | Tuỳ, không ảnh hưởng |
| `2bf497d` | `PE.v`: `first_spad_words_wght` 5 → `$clog2(WGHT_ADDR_ADDR+1)` bit (= 7), `filters_reg_M0` 6 → 8 bit, cho khớp cổng của `data_pipeline_wght` | **Chính là lỗi #11 phần `PE.v:2210`** (cắt 7 → 5 bit). Probe 48 PE trên 7 layer (4–64 channel, 4–64 filter): giá trị lớn nhất của `first_spad_words_o` là **13**, chưa bao giờ ≥ 32, nên **không đổi kết quả** ở các cấu hình hiện tại; đây là lỗi tiềm ẩn. Lint: −2 cảnh báo cổng, +1 cảnh báo mới (`assign filters_reg_M0 = stream_data[5:0]` 6 → 8 bit) | **Nên**, kèm sửa nhỏ: mở rộng 0 tường minh để không sinh cảnh báo mới. Đụng 48 PE nên cần chạy lại Vivado |
| `18772d6` | `rtl_test_utils.py`: tắt các `assert` của `check_fc_activation_writes` (comment và bọc trong chuỗi `"""..."""`), ghi chú "For Claude to rewrite: kiểm tra sau khi ghi xong thay vì kiểm tra trực tiếp" | Đúng là nguyên nhân 23 test GEMM/Dense FAIL: tắt bằng công tắc `OPENEYE_SKIP_FC_WRITE_CHECK` (đã có trong `dev`) thì 23/23 PASS (lỗi #5 là báo động giả, mục 8b) | **Không lấy nguyên văn**: cách bọc chuỗi tắt luôn cả phần so giá trị. Nên viết lại kiểm tra: đọc nội dung RAM iact **sau khi** pha ghi kết thúc rồi mới so |

Cách lấy đề xuất: `git cherry-pick b6fa369 2c8c324 2bf497d` (có thể thêm `fc9ace3`), **không** merge cả `upstream/main` để tránh `18772d6`.
Làm thành một bước riêng, sau bản sửa #14, kèm hồi quy và Vivado (vì `PE.v` thay đổi). Bước này cần bạn đồng ý vì sửa RTL.

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
- Yosys 0.69 (micromamba, `~/tools/yosys/bin/yosys`) để ước lượng tài nguyên nhanh; Vivado 2024.2 chạy trên Windows (mục 6d).

## 3b. Một lần mô phỏng chạy những gì (Python và RTL)

Một test (ví dụ một case của `test_profile.py`) chạy qua 3 giai đoạn. **Python làm phần lớn công việc**: đóng vai host (CPU + DDR + AXI DMA),
mô hình tham chiếu và dụng cụ đo. **Chỉ RTL là "phần cứng"**: mọi phép tính của bộ tăng tốc và mọi số chu kỳ đều do RTL tạo ra.
Không có bước "dạy" (huấn luyện) nào: OpenEye chỉ làm suy luận (inference); weight là ngẫu nhiên, hằng số hoặc dạng dốc do testbench tạo.

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
     │    TensorFlow tạo layer (data_create) → DRAM.py giữ input, weight, bias (có thể thay bằng hằng/ramp)
     │    layer_parameters.py tính tham số layer → các word cấu hình
     │    test_utils_main.collect_results / make_ref: MÔ HÌNH THAM CHIẾU tính kết quả đúng bằng Python
     │    test_utils_main.write_stream + *_mapper.py: đóng gói stream DMA (cấu hình → iact → weight → bias → quant)
     ├─ các coroutine chạy song song với RTL:
     │    Clock, reset
     │    send_stream (hoặc send_words_through_memory khi bật mô hình bộ nhớ): mỗi chu kỳ đặt data_dma_i / enable_dma_i, xem ready_dma_o
     │    profile_dma_phases: mỗi cạnh clock đọc trạng thái FSM, đếm chu kỳ/word → profile.json  (chỉ quan sát, không làm đổi chu kỳ)
     │    probe_fsm_states: phát hiện treo;  trace_dma_input (tuỳ chọn)
     │    compare_stream_Conv/Dense/...: nhận data_dma_o (ready_dma_i do testbench hoặc WriteChannel quyết định), so với tham chiếu
     └─ assert → PASS/FAIL

C. Sau mô phỏng (Python thuần)
     run_profile.py gom profile.json → profile_report (bảng, --compare); check_dma_trace.py, decode_iact_read_loops.py khi cần
```

## 4. Cấu trúc project

Sơ đồ chỉ gồm những thư mục và file quan trọng (★ = do dự án riêng này thêm vào hoặc sửa; ☆ = sinh tự động, không có trong git).

```
OpenEye_orig/
├── README.md                     Tài liệu gốc của upstream (giữ nguyên)
├── README_FI.md               ★  File này: nhật ký, hướng dẫn, kết quả
├── hdl/                          RTL (Verilog) của bộ tăng tốc
│   ├── OpenEye_FPGA.v         ★  Top-level FPGA: cổng DMA, FSM chính (nạp → convert → tính → đọc ra), buffer iact/weight/psum
│   │                             (★ sửa GET_BIAS, lỗi #3)
│   ├── psum_pipeline.v           FSM psum: nạp bias, thu kết quả, lượng tử hoá, gửi kết quả ra DMA
│   ├── iact_stream_constructor.v ★ Đọc iact từ buffer và gửi tới các cluster (★ sửa bộ đếm lỗi #13; ghi 1 channel và NUM_GLB_IACT=3, lỗi #6/#7)
│   ├── OpenEye_Parallel.v        Mảng tính toán: các cluster + router ("ASIC compute core", SERIAL=0/1)
│   ├── OpenEye_Cluster.v, PE_cluster.v, PE.v   Cluster → nhóm PE → PE (MAC INT8, sparse)
│   ├── router_*.v, GLB_cluster.v Router iact/weight/psum giữa các cluster, GLB của cluster
│   ├── dma_storage.v             Bộ giải mã word cấu hình (BẢN CŨ: test và export luôn thay bằng bản sinh từ regmap.yaml)
│   ├── RAM_*.v, SPad_*.v         Mô hình RAM/scratchpad (Vivado suy luận thành BRAM/URAM/LUTRAM)
│   ├── include/regmap_params.vh ☆ Header sinh tự động (bản còn sót của lần chạy trước)
│   └── lint_waivers.vlt          Các warning Verilator được bỏ qua có chủ đích
├── fpga/
│   ├── hdl/open_eye_axi_v1_0.v   Wrapper AXI (AXI-Lite + AXI4-Stream) cho Vivado IP; hiện không biên dịch được (lỗi #16)
│   └── sw/                       Phần mềm chạy trên ARM: runtime AXI DMA (hal_xaxidma.c, openeye_runtime.c)
├── src/open_eye/                 Thư viện Python (cài kiểu editable vào venv)
│   ├── open_eye_parameters.py    Cấu hình phần cứng (đọc từ biến môi trường: CLUSTER_ROWS, IACT_RAM_CELLS, ...)
│   ├── layer_parameters.py       Tính tham số của từng layer (số chu kỳ, giới hạn vòng lặp, ...)
│   ├── *_mapper.py               Sinh stream DMA: conv, dense, iact, weight, psum (bias), pooling (★ conv_mapper: sửa lỗi #18)
│   ├── generator.py              regmap.yaml → regmap_params.vh, dma_storage.v, đóng gói word cấu hình
│   ├── vh_file_creator.py        Sinh parameters_FPGA.vh / parameters_PE.vh / parameters_PE_cluster.vh
│   ├── test_utils_main.py        Tính kết quả tham chiếu (golden model)
│   ├── rtl_test_utils.py      ★  Hàm cocotb: gửi stream, so sánh kết quả, profiler, trace DMA, driver bộ nhớ
│   ├── memory_model.py        ★  Mô hình DDR + AXI DMA (mục 6c)
│   └── profile_report.py      ★  Báo cáo và so sánh profile (mục 6.5)
├── test/
│   ├── cocotb_fpga/              Testbench top-level FPGA (OpenEye_FPGA_tb.py) và các bộ test
│   │   ├── test_profile.py    ★  9 case đo độ trễ (mục 6.7)
│   │   ├── test_conv_const.py ★  Test Conv (34 test dùng làm hồi quy; ★ thêm random_data)
│   │   ├── test_gemm_layer.py    Test GEMM/Dense (63 test dùng làm hồi quy)
│   │   ├── test_mnist_layers.py ★ Quét channel × NUM_GLB_IACT (lỗi #6/#7), 3 layer Conv MNIST thật, dữ liệu ngẫu nhiên + kiểm tra độc lập (lỗi #18)
│   │   └── regmap.yaml           Định nghĩa các thanh ghi cấu hình gửi qua DMA (nguồn của dma_storage.v)
│   ├── cocotb_parallel/          Test của OpenEye_Parallel (SERIAL=0), đã cũ (mục 5.7)
│   ├── test_memory_model.py   ★  16 unit test của mô hình bộ nhớ
│   ├── test_profile_report.py ★  Unit test của công cụ báo cáo
│   └── .temp/                 ☆  Thư mục chạy của từng test (log, header sinh ra, profile.json)
├── tools/                     ★  Công cụ của dự án riêng
│   ├── run_profile.py            Chạy các case đo song song, so sánh với baseline (mục 6)
│   ├── lint_check.py, lint_baseline/   Lint theo baseline (mục 9c)
│   ├── export_vivado.py          Xuất thư mục nguồn + Tcl cho Vivado (mục 6d)
│   ├── check_dma_trace.py        Kiểm tra DUT nhận đúng stream DMA (mục 9)
│   ├── decode_iact_read_loops.py Giải mã thanh ghi vòng lặp đọc iact từ stream DMA
│   ├── verify_conv_output.py     Kiểm tra độc lập từng word output của layer Conv (numpy)
│   └── report/make_progress_report*.py  Tạo báo cáo Word cho giáo viên hướng dẫn (2026-10-10, 2026-10-15)
├── doc/
│   ├── perf/                  ★  Số liệu đo chu kỳ: baseline_2026-10-15/ (mốc hiện tại, sau lỗi #18), baseline_2026-10-10/ (mốc cũ), mem_typical_2026-10-10/, ...
│   ├── synth/                 ★  Báo cáo Vivado theo từng lần chạy (mỗi thư mục có SUMMARY.md)
│   ├── experiments/           ★  Báo cáo thí nghiệm và điều tra lỗi (#13, #6/#7, #18, #14 + script lockstep)
│   ├── lint/                  ★  Output lint gốc
│   ├── reports/               ★  Báo cáo tiến độ (Word): BaoCao_TienDo_OpenEye_2026-10-10.docx, BaoCao_TienDo_OpenEye_2026-10-15.docx
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

**Các trạng thái của FSM chính** (`OpenEye_FPGA.v`, 15 giá trị 0–14): 0 `IDLE` (không dùng: sau reset FSM vào thẳng 1), 1 `GET_PARAMETERS`
(TRANSMISSIONS word cấu hình + mask PE), 2 `GET_ROUTER_CONFIG`, 3 `GET_IACT`, 4 `GET_WGHT`, 5 `GET_BIAS` (bỏ qua nếu `skipPsum`), 6 `GET_QUANTIZE`,
7 `START_CONVERTER`, 8 `CONVERT_IACT`, 9 `WAIT_CYCLE` (64 chu kỳ, phát lệnh gửi weight), 10 `WAIT_FOR_RESULTS` (mảng PE tính, FSM psum đọc kết quả ra;
rời trạng thái khi word cuối `last_data_o` được nhận), 11 `RECEIVE_PSUMS_TO_IACT`, 12 `MAXPOOLING_READ`, 13 `MAXPOOLING_SEND`, 14 `MAXPOOLING_WAIT`.
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
| `readout` | `số output × ceil(psum_bit / 8)` byte | Mỗi output một psum |

**Hiệu suất bus** = payload tối thiểu ÷ (số beat × `DMA_BITWIDTH`/8).
100% nghĩa là mọi bit trên bus đều là dữ liệu cần thiết; 15% nghĩa là 85% băng thông bị lãng phí
(do đệm, lặp lại dữ liệu, hoặc mã hoá kém).
Hiện chỉ tính được cho layer `Convolution_Single`.

### 5.4 Baseline

**Baseline** là **phép đo mốc trước khi tối ưu**. Mỗi lần sửa RTL để tối ưu, ta chạy lại đúng các cấu hình đó
và so sánh với baseline để biết thay đổi tốt hơn hay tệ hơn bao nhiêu. Không có baseline thì không chứng minh được
tối ưu có tác dụng. Có hai loại baseline:
- **Chu kỳ và DMA** (mô phỏng): `doc/perf/baseline_2026-10-15/` (9 case, sau bản sửa lỗi #18). `baseline_2026-10-10` (đo khi lỗi #18 còn: weight đọc gấp đôi,
  case > 4 channel tính sai với weight thật), `doc/perf/baseline.md` và `baseline_2026-10-09*` là mốc cũ.
- **Phần cứng** (Vivado): `doc/synth/2026-10-19_route4ns_fix14_zu7ev/` (tài nguyên, fmax 250 MHz). Các thư mục `doc/synth` cũ hơn là lịch sử.

### 5.5 QUANT_AMOUNT

- Tham số phần cứng (`parameter QUANT_AMOUNT` trong `OpenEye_FPGA.v`) = **số entry tối đa của bảng lượng tử hoá**,
  tức số filter tối đa mà một layer có thể có hệ số lượng tử riêng.
- Lượng tử hoá theo filter: `q = (mantissa × (psum + offset)) >>> exponent`, dùng để đưa psum 20/32 bit về INT8.
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

## 6. Hướng dẫn chạy công cụ đo hiệu suất

### 6.1 Các công cụ

| Công cụ | File | Vai trò |
|---|---|---|
| Profiler | `src/open_eye/rtl_test_utils.py` → `profile_dma_phases` | Chạy bên trong simulation. Mỗi chu kỳ ghi lại pha, số word DMA vào/ra và chu kỳ chờ bộ nhớ; kết quả vào `profile.json`. Bật bằng `OPENEYE_PROFILE=1` |
| Các case đo | `test/cocotb_fpga/test_profile.py` | 9 cấu hình layer Conv (mục 6.7) |
| Bộ chạy | `tools/run_profile.py` | **Lệnh chính.** Chạy các case song song, so sánh, lưu snapshot |
| Báo cáo | `src/open_eye/profile_report.py` | In bảng từ các `profile.json`; `--compare` để so sánh trước/sau |
| Mô hình bộ nhớ | `src/open_eye/memory_model.py` | Giả lập DDR + AXI DMA (mục 6c). Bật bằng `--mem` |
| Baseline | `doc/perf/baseline_2026-10-15/` | Số liệu mốc của 9 case (bộ nhớ lý tưởng), đo sau bản sửa lỗi #18 |
| Kiểm tra độc lập | `tools/verify_conv_output.py` | Tính lại layer Conv bằng numpy, kiểm tra từng word output của DUT (cần `OPENEYE_DUMP_VERIFY=1`) |

### 6.2 Chuẩn bị (một lần)

- Đứng ở thư mục gốc của repo: `cd ~/OpenEye_orig`.
- Dùng Python của venv: `venv/bin/python` (đã có cocotb, cocotb-test, tensorflow, open_eye).
- Cần `iverilog` (Icarus Verilog 11) trong `PATH`; máy này đã có sẵn.
- Không cần `source venv/bin/activate` nếu luôn gọi `venv/bin/python ...`.

### 6.3 Chạy nhanh

```bash
# Chạy 6 case nhỏ (khoảng 1–4 phút) và so với baseline:
venv/bin/python tools/run_profile.py -k "not mnist" --compare doc/perf/baseline_2026-10-15

# Chạy cả 9 case (khoảng 10 phút, 3 case kiểu MNIST mất 4–9 phút mỗi case):
venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-10-15

# Chỉ in bảng, không so sánh:
venv/bin/python tools/run_profile.py -k "8x1_f4_q32"
```

Output gồm: dòng PASS/FAIL của từng case (kèm thời gian chạy), rồi bảng của từng case, rồi bảng tổng hợp (mục 6.5).
Mã thoát khác 0 nếu có case FAIL.

### 6.4 Các tuỳ chọn của `tools/run_profile.py`

| Tuỳ chọn | Ý nghĩa | Ví dụ |
|---|---|---|
| `-k BIỂU_THỨC` | Chọn case theo tên (cú pháp `-k` của pytest) | `-k q32`, `-k "not mnist"`, `-k "mnist2 or 32x3"` |
| `--jobs N` | Số case chạy song song (mặc định 3). Máy 12 nhân, 7 GB RAM: tối đa khoảng 4–6 | `--jobs 4` |
| `--compare DIR` | So với snapshot trong `DIR` (lặp lại được) | `--compare doc/perf/baseline_2026-10-15` |
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

### 6.6 Quy trình đánh giá một tối ưu

1. Tạo branch hoặc commit riêng cho thay đổi (RTL hoặc Python).
2. Kiểm tra đúng sai trước: các test chức năng liên quan (ví dụ `test_conv_const.py`) phải PASS.
3. Đo: `venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-10-15`.
   Mô phỏng là tất định, nên **mọi chênh lệch đều do thay đổi của bạn gây ra**.
4. (Tuỳ chọn) đo thêm với bộ nhớ thực tế hơn: thêm `--mem typical`, và so với `doc/perf/mem_typical_2026-10-10` (đo trước bản sửa lỗi #18; với 5 case `q32` chỉ `32x3_f16` khác, −96 chu kỳ).
5. Nếu giữ thay đổi: lưu snapshot và báo cáo, rồi commit:
   ```bash
   venv/bin/python tools/run_profile.py --jobs 4 --save doc/perf/<tên>_<ngày> \
       --report doc/perf/<tên>_<ngày>.md --compare doc/perf/baseline_2026-10-15
   git add -f doc/perf/<tên>_<ngày>/*.json doc/perf/<tên>_<ngày>.md
   ```
   (`-f` vì `.gitignore` của upstream bỏ qua `*.json`/`*.csv`/`*.txt`.)
6. Ghi kết quả vào mục Nhật ký của file này.
7. Nếu sửa RTL: chạy lint (mục 9c); warning mới thì sửa, hoặc chấp nhận bằng `--update` kèm lý do.

### 6.7 Các case đo

Mọi case: một layer `Convolution_Single`, kernel 3×3, ramp activation, 2×2 cluster, `NUM_GLB_IACT=1`, psum 20 bit.

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
| Conv1: 28×28, 1 → 32 | 28×28, **4** → 32 | 1 channel với ảnh rộng 28 còn lỗi #17 (lỗi #6 đã sửa ngày 2026-10-14, nhưng chỉ đúng cho ảnh rộng một lượt x) |
| Conv2: 14×14, 32 → **64** | 14×14, 32 → **32** | Ban đầu: `IndexError` với 64 filter. Thực ra là giới hạn cấu hình (#8): 64 filter cần `QUANT_AMOUNT=64`. Giữ 32 để không đổi mốc |
| Conv3: **7×7**, 64 → 64 | **8×8**, 32 → 32 | 7×7 có cột đệm; phần cứng ghi giá trị khác 0 vào ô đệm nên kiểm tra chuỗi DMA FAIL (giá trị thật vẫn đúng, lỗi #9). 64 → 32 như trên |

Khảo sát ngày 2026-10-10 (đều `QUANT_AMOUNT=32`, `NUM_GLB_IACT=1`): **PASS**: 8/16/32 channel, 32 filter, 14×14, 28×28, 8×8.
**FAIL**: 64 filter (lỗi Python), 7×7 (ô đệm).

**Cập nhật 2026-10-15:** 9 case vẫn giữ kích thước "thu nhỏ" để mốc so sánh liên tục. Các layer MNIST **đúng kích thước thật** được kiểm tra riêng trong
`test/cocotb_fpga/test_mnist_layers.py::test_mnist_conv`: Conv2 (14×14, 32 → 64, `QUANT_AMOUNT=64`) **PASS** từ sau bản sửa lỗi #18; Conv3 đúng mọi giá trị
nhưng còn lỗi #9; Conv1 còn lỗi #17. Lưu ý: trước bản sửa lỗi #18, các case > 4 channel chỉ "PASS" vì weight hằng số che lỗi (mục 9).

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

Coroutine cocotb lấy mẫu **mỗi cạnh lên của clock**. Với mỗi chu kỳ, nó xác định pha (FSM chính, hoặc `readout` khi FSM psum
ở `PSUM_SEND_RESULTS`) và đếm: `cycles`, `in_offered` (host đưa word), `in_accepted` (`enable_dma_i_reg & ready_dma_o`),
`out_words` (`enable_dma_o & ready_dma_i`), `in_stall` (pha nạp, DUT sẵn sàng nhưng không có word), `out_stall` (có kết quả nhưng
`ready_dma_i` thấp). Cửa sổ đo bắt đầu từ word vào đầu tiên được nhận và kết thúc ở word ra cuối cùng. File `profile.json` được ghi lại
mỗi khi đổi pha và sau mỗi word ra, nên vẫn còn khi test FAIL hoặc treo.

Giới hạn: payload và hiệu suất bus chỉ tính cho `Convolution_Single` (việc 0.2 sẽ mở rộng cho Dense và lượt nhiều layer).
**Chưa đo được MNIST nguyên model**: `model_test` bị tắt, Conv1 thật còn lỗi #17, Conv3 lỗi #9, layer FC lỗi #5, và chuỗi nhiều layer chưa ổn định.

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

- **Pha của chu kỳ:** `readout` nếu FSM psum ở `PSUM_SEND_RESULTS` (5) hoặc đang có `out_word`; ngược lại theo trạng thái FSM chính (bảng mục 5.1).
- **Cửa sổ đo:** từ chu kỳ có `in_accepted` đầu tiên tới chu kỳ có `out_words` cuối cùng (cả hai đầu đều tính). Các chu kỳ sau word ra cuối nằm ở `pending`, không tính.
  Vì vậy **độ trễ layer** = `total_cycles` = Σ `cycles` của mọi pha = số chu kỳ từ khi DUT nhận word cấu hình đầu tiên tới khi gửi xong kết quả cuối.
  Không gồm: thời gian trước word đầu (reset, CPU cấu hình DMA), độ trễ của burst đầu tiên khi bật mô hình bộ nhớ, và overhead phần mềm.
- **Báo cáo** (`profile_report`), với `W = DMA_BITWIDTH/8` byte mỗi word:
  - `share` = `cycles(pha) / total_cycles`
  - `compute` = `cycles(compute) / total_cycles`
  - `DMA busy` = `Σ (in_accepted + out_words) / total_cycles` (tỉ lệ chu kỳ có word trên bus; tối đa có thể vượt 100 % nếu vào và ra cùng chu kỳ)
  - `waiting for memory` = `Σ (in_stall + out_stall) / total_cycles`
  - `bus eff.` = `payload(pha) / ((in_accepted + out_words) · W)`; payload theo mục 5.3 (chỉ cho `Convolution_Single`)
  - `change` = `new − base`, phần trăm = `(new − base) / base`
  - `total ... ns` = `total_cycles × CLOCK_NS`. **Chú ý:** `CLOCK_NS` là chu kỳ clock **giả định của mô phỏng** (10 hoặc 20 ns), không phải clock thật.
- **Đổi ra thời gian thật:** `t = total_cycles / f_clk`, với `f_clk` lấy từ Vivado sau route (hiện 250 MHz, tức 4 ns/chu kỳ).
  Ví dụ `mnist1`: 65.800 × 4 ns = 263,2 µs.
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

Dữ liệu ngẫu nhiên: `_run_conv_const(..., random_data=True)` bỏ các hook hằng số/dốc. Các test `test_mnist_layers.py::test_random_data` và `test_mnist_conv` tự
chạy công cụ sau mô phỏng.

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
| `BUFFER_WIDTH_PSUM`, `BUFFER_WIDTH_WGHT` | 14, 12 (mặc định) | Bộ đệm psum 16.384 địa chỉ (144 RAMB36), bộ đệm weight 4.096 |

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

### Kết quả Vivado hiện tại: mốc phần cứng (2026-10-19, sau khi sửa lỗi #13, #6/#7 và #14)

Chi tiết: `doc/synth/2026-10-19_route4ns_fix14_zu7ev/SUMMARY.md`. Vivado 2024.2, `xczu7ev-ffvc1156-2-e`, out-of-context, clock 4 ns (250 MHz),
cấu hình ở bảng trên, RTL = `dev` có bản sửa #14. Bản sửa lỗi #18 chỉ là Python, không đổi phần cứng. Lần này Vivado được chạy batch từ WSL
(`cmd.exe /c ... vivado.bat -mode batch -source synth_ooc.tcl -tclargs xczu7ev-ffvc1156-2-e 4 impl`).

| | Sau tổng hợp | **Sau route** | Tỉ lệ ZU7EV (sau route) |
|---|---:|---:|---:|
| WNS ở 4 ns / hold | +0,219 ns | **+0,097 ns** / +0,007 ns | đạt 250 MHz |
| fmax = 1000 / (4 − WNS) | ~264 MHz | **~256 MHz** | |
| LUT (logic + LUTRAM/SRL) | 65.839 | 64.050 | 27,8 % |
| Flip-flop | 38.859 | 39.184 | 8,5 % |
| Block RAM tile (RAMB36 168 + RAMB18 48) | 192 | 192 | **61,5 %** |
| URAM / DSP | 8 / 4 | 8 / 4 | 8,3 % / 0,2 % |

- **0 ERROR, 0 CRITICAL WARNING**. So với fix67 chỉ khác: **hết 10 cảnh báo Synth 8-6090** (lỗi #14), không có mã cảnh báo mới. Các cảnh báo còn lại:
  Synth 8-7137 (lỗi #15), 8-689 (`PE.v:2210/2211`, lỗi #11), 8-6057 (URAM không có thanh ghi pipeline), thanh ghi/cổng không dùng bị loại bỏ, và cảnh
  báo bình thường của chế độ out-of-context.
- **Tài nguyên theo khối:** mảng PE (`OpenEye_Parallel`, 48 PE) chiếm khoảng 84 % LUT và 85 % FF, mỗi PE khoảng 1.100 LUT và 655 FF; bộ nhân của PE làm bằng
  LUT (`USE_DSP=0`); 4 DSP ở 4 bộ lượng tử. 8 bộ đệm psum (16.384 × 40 bit) chiếm **144/168 RAMB36** (46 % BRAM của chip); 4 `iact_stream_constructor` chiếm
  24 RAMB36 (mỗi khối 364 FF sau bản sửa #6/#7); 48 RAMB18 là SPad của 48 PE; 8 URAM là 4 bộ đệm iact và bộ đệm weight.
- **Đường găng sau route:** dây từ `psum_pipeline` (`psum_buffer_addr_array`) tới 144 BRAM của bộ đệm psum (16/20), trong chuỗi BRAM của bộ đệm psum (1), `OpenEye_Parallel` (2), `fsm_cycle` (1). Logic của `results_ready` không nằm trên đường găng.
- **Thời gian thật ở 250 MHz** (bộ nhớ lý tưởng, baseline sau bản sửa #18): `mnist1` 55.048 chu kỳ = 220 µs, `mnist2` 262 µs, `mnist3` 82 µs.

### Lịch sử các lần chạy Vivado

| Ngày | Thư mục `doc/synth/` | Chạy gì | Kết quả chính |
|---|---|---|---|
| 2026-10-12 | `2026-10-12_baseline_zu7ev` | Tổng hợp, clock 10 ns | 64,5k LUT, 38,7k FF, 192 BRAM tile; fmax sau tổng hợp ~257 MHz. Phát hiện CRITICAL WARNING của lỗi #13 |
| 2026-10-12 | `2026-10-12_synth4ns_zu7ev` | Tổng hợp lại ở 4 ns (place & route **không** chạy vì thư mục trên ổ C là bản cũ, chưa có tuỳ chọn `impl`) | Cùng netlist; danh sách cảnh báo đầy đủ, lỗi #13–#15 |
| 2026-10-13 | `2026-10-13_route4ns_zu7ev` | Tổng hợp + place & route, 4 ns, **trước** khi sửa lỗi #13 | Đạt 250 MHz (WNS +0,025 ns); 63,9k LUT. Không dùng làm mốc vì phần cứng này tính sai (lỗi #13) |
| 2026-10-14 | `2026-10-14_route4ns_fix13_zu7ev` | Tổng hợp + place & route, 4 ns, **sau** khi sửa lỗi #13 | CRITICAL WARNING 200 → 0; mỗi `iact_stream_constructor` +32 FF (đúng 4 bộ đếm × 8 bit); WNS +0,117 ns |
| 2026-10-15 | `2026-10-15_route4ns_fix67_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi sửa lỗi #6/#7 | +103 FF, +201 LUT (logic địa chỉ 1 channel); WNS +0,048 ns |
| 2026-10-19 | `2026-10-19_route4ns_fix14_zu7ev` | Tổng hợp + place & route, 4 ns, sau khi sửa lỗi #14 (chạy batch từ WSL) | **Mốc hiện tại** (bảng trên). Synth 8-6090: 10 → 0; LUT −112, FF −8 (dao động công cụ); WNS +0,097 ns |

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

## 7. Kết quả baseline chính (chi tiết: `doc/perf/baseline_2026-10-15.md`; trước bản sửa #18: `baseline_2026-10-10.md`)

**Baseline hiện tại: `doc/perf/baseline_2026-10-15/`** (9 case, bộ nhớ lý tưởng, sau bản sửa lỗi #18; thời gian ở 250 MHz = chu kỳ × 4 ns).

**Layer kiểu MNIST (0.3):**

| Case | Thay cho | Tổng chu kỳ | Compute | Pha không tính toán lớn nhất |
|---|---|---:|---:|---|
| `mnist1_28x28_c4_f32` | Conv1 | 55.048 (220 µs) | 42% | **bias 26%** (14.336 word cho 96 byte payload), readout 26% |
| `mnist2_14x14_c32_f32` | Conv2 | 65.528 (262 µs) | **69%** | weight 12% (hiệu suất 15%), convert 7% |
| `mnist3_8x8_c32_f32` | Conv3 | 20.584 (82 µs) | 62% | weight 19% (hiệu suất 30%), convert 8% |

Trước bản sửa lỗi #18 (`baseline_2026-10-10`): 65.800 / 87.032 / 26.728 chu kỳ. Phần giảm (−16 % / −25 % / −23 %) nằm hết ở `compute`: mỗi lần gửi weight
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
| 0. Đo lường | Profiler, báo cáo, so sánh, baseline 9 case, mô hình bộ nhớ, mốc phần cứng Vivado, kiểm tra độc lập từng word | **Gần xong**: còn 0.2 (Dense, nhiều layer) |
| 0b. Sửa lỗi tính đúng (phát sinh) | Lỗi làm phần cứng/mô phỏng tính sai: #3, #13, #6, #7, #18 | **Đã sửa** (2026-10-10 → 2026-10-15); còn #17, #9, #5, #18b, 3 channel |
| 1. Giảm lưu lượng DMA | Bias theo filter, đóng gói weight, bảng quant theo F hoặc lưu BRAM, readout INT8 | Chưa làm. Đề xuất bắt đầu với bias |
| 2. Che độ trễ | Double-buffering (`BRANCHES=2`): nạp lượt sau trong lúc lượt hiện tại tính toán | Chưa làm (cần sửa lỗi chọn nửa buffer iact trước) |
| 3. Mô hình và DSE | Mô hình Python dự đoán chu kỳ và byte, roofline, quét cấu hình | Chưa làm |

**Giai đoạn 0: trạng thái chi tiết** (cập nhật 2026-10-15)

| Việc | Trạng thái |
|---|---|
| Profiler chu kỳ và beat DMA theo pha (`profile_dma_phases`) | Xong |
| Công cụ báo cáo + hiệu suất bus (`profile_report`) | Xong (chỉ cho `Convolution_Single`) |
| Baseline 6 cấu hình Conv đơn (`doc/perf/baseline.md`) | Xong |
| CI lint theo baseline | Xong |
| **0.1 So sánh trước/sau**: `profile_report --compare`, `tools/run_profile.py` (mục 6.3–6.6) | **Xong** (2026-10-10) |
| **0.2 Mở rộng phạm vi đo**: payload/hiệu suất cho layer Dense (FC) và cho lượt 2 layer (pha `writeback`), tách số liệu theo từng layer (đã có `layer_starts` nhưng báo cáo chưa dùng) | **Chưa.** Bias, bảng quant và readout INT8 đều ảnh hưởng tới Dense và write-back giữa các layer |
| **0.3 Cấu hình gần thực tế hơn**: 3 case kiểu MNIST (mục 6.7), baseline mới `baseline_2026-10-10` | **Xong** (2026-10-10) |
| Mô hình bộ nhớ ngoài (độ trễ burst, giới hạn băng thông) | **Xong** (2026-10-10, mục 6c); tham số chưa hiệu chỉnh theo board |
| Mốc phần cứng: tổng hợp + place & route Vivado (`tools/export_vivado.py`) | **Xong** (2026-10-12 → 2026-10-19, mục 6d): 250 MHz, 64,1k LUT, 39,2k FF, 192 BRAM tile |
| Kiểm tra độc lập từng word + test dữ liệu ngẫu nhiên | **Xong** (2026-10-15, mục 6.12) |
| Baseline sau các bản sửa | **Xong**: `doc/perf/baseline_2026-10-15/` |

### 8b. Tổng hợp lỗi phát hiện được (cập nhật 2026-10-15)

| # | Lỗi | Nơi | Trạng thái |
|---|---|---|---|
| 1 | Giải mã sai thứ tự output Conv ở chế độ SERIAL (124/128 giá trị sai ở 1×1 cluster, DMA 32 bit) | testbench Python | **Đã sửa** (`27aa75c`) |
| 2 | Bộ sinh tài liệu Verilog: 125 warning Sphinx, mất parameter | `doc/verilog_doc_parser` | **Đã sửa** (`83750e9`) |
| 3 | `GET_BIAS` rời trạng thái khi chưa nhận word bias cuối (treo khi DMA có khoảng trống) | `hdl/OpenEye_FPGA.v` | **Đã sửa** (`77f0477`), 0 chu kỳ, 0 tài nguyên |
| 4 | CI lint luôn fail (38 warning có sẵn) | `.github` | **Đã xử lý** bằng lint baseline (`4a26867`); RTL không đổi |
| 5 | Dense/FC: `FC activation write ... bank=1 addr=0` sai (23/63 test GEMM/Dense) | Testbench (`check_fc_activation_writes` trong `rtl_test_utils.py`) | **Không phải lỗi RTL** (kiểm chứng 2026-10-19, RTL có bản sửa #14): tắt bộ kiểm tra live (`OPENEYE_SKIP_FC_WRITE_CHECK=1`) thì **23/23 test PASS** (so với tham chiếu của testbench). Bộ kiểm tra so từng lần ghi RAM iact ngay khi xảy ra; theo upstream `18772d6`, với `NUM_GLB_IACT > 1` RAM được ghi tạm giá trị 0 rồi ghi đè ở các chu kỳ sau. **Cần viết lại bộ kiểm tra**: so nội dung RAM sau khi pha ghi kết thúc (mục 2, phần upstream) |
| 6 | Input 1 channel: chỉ ra bias | `hdl/iact_stream_constructor.v` | **Đã sửa** (2026-10-14, được bạn đồng ý): hồi quy do upstream `23be043`; RAM nay dùng lại địa chỉ 1-channel `ram_wr_addr_q`. Ảnh rộng một lượt x đã đúng; ảnh rộng hơn còn lỗi #17 |
| 7 | Input 3 channel và mọi `NUM_GLB_IACT=3`: giá trị sai | `iact_stream_constructor.v` (bank) + Python (3 channel) | **`NUM_GLB_IACT=3`: đã sửa** (2026-10-14, chỉ xoay bank khi Dense). **3 channel: chưa sửa** (lỗi cũ: Python đóng gói 3 byte/pixel, RTL đi theo cặp; đề xuất Python đệm số channel lẻ lên chẵn) |
| 8 | 64 filter: `IndexError` trong `layer_parameters.read_data_from_layer` | Cấu hình | **Không phải lỗi code** (2026-10-14): bảng lượng tử có `QUANT_AMOUNT` entry, nên số filter phải ≤ `QUANT_AMOUNT`. Layer 64 filter cần `QUANT_AMOUNT=64` |
| 9 | Ảnh rộng 7 (có cột đệm): phần cứng ghi giá trị khác 0 vào ô đệm (giá trị thật vẫn đúng) | RTL/testbench | **Chưa sửa** |
| 10 | `CLUSTER_ROWS=1`: một số cấu hình treo FSM (theo tài liệu upstream) | RTL | **Chưa sửa**, chưa tự kiểm chứng |
| 11 | Lint đáng ngờ: `PE.v:2210` (cắt 7→5 bit), `data_pipeline_wght.v:394/396/424` (overhead 4 bit). Cấu hình đang dùng có `SPARSITY_EN=1` nên các đường này **đang được dùng** | RTL | **Chưa sửa**, cần test (mục 9b) |
| 12 | `current_filter` (chỉ số filter của bộ lượng tử) chỉ được reset về 0, **không bao giờ tăng**, nên mọi filter dùng hệ số lượng tử của filter 0 (lượng tử theo filter chưa hoạt động) | `hdl/psum_pipeline.v` | **Chưa sửa**, phát hiện bằng đọc code (2026-10-10), chưa kiểm chứng bằng test. Test hiện tại dùng hệ số giống nhau cho mọi filter nên không phát hiện được |
| 13 | `rd_cycle_loop_cnt_0..3` bị lái từ 2 khối `always` (reset ở khối này, đếm ở khối kia). Vivado giữ giá trị reset nên trên FPGA các bộ đếm **luôn bằng 0**; mô phỏng không thấy | `hdl/iact_stream_constructor.v:233/437` | **Đã xác nhận bằng thí nghiệm** (2026-10-13, `doc/experiments/2026-10-13_bug13_stuck_counters.md`): giả lập phần cứng thì 6/9 case baseline FAIL (mọi case có `iact_read_limit_1..3` ≠ 0, gồm cả 3 layer MNIST), đối chứng PASS. **Đã sửa** (`5f1e66e`, 2026-10-13, được bạn đồng ý): 0 chu kỳ, 79 test hồi quy không đổi; Vivado 2026-10-14: CRITICAL WARNING 200 → 0, vẫn đạt 250 MHz (mục 9) |
| 14 | `results_ready` vừa gán blocking vừa non-blocking (lint `BLKANDNBLK`, 4 lỗi); Vivado Synth 8-6090: "entire logic could be removed" | `hdl/psum_pipeline.v` | **Đã sửa** (2026-10-19, được bạn đồng ý; phân tích 2026-10-16). Phần cứng Vivado trước đó vẫn đúng; lỗi thật là code không khả chuyển (netlist Yosys treo, Verilator từ chối). Tách phần AND tổ hợp ra khỏi thanh ghi, chỉ còn gán `<=`. Lockstep cũ/mới trên 125 test: 0 sai khác; netlist Yosys nay PASS; lint −4 lỗi −3 cảnh báo; Vivado hết 10 cảnh báo 8-6090, vẫn 250 MHz (mục 9) |
| 15 | 12 thanh ghi có set và reset cùng mức ưu tiên (Synth 8-7137, "may cause simulation mismatches") | `psum_pipeline.v:322/776`, `OpenEye_Parallel.v:443/448`, `PE.v:1113` | **Chưa phân tích** |
| 16 | Wrapper AXI `fpga/hdl/open_eye_axi_v1_0.v` không biên dịch được (thiếu module `cfg_reg`, `QUANT_AMOUNT` chưa khai báo, `BUFFER_WIDTH` gán 2 lần, `RAM_CELLS` không tồn tại) | `fpga/hdl` | **Chưa sửa**; chỉ cần khi đóng gói IP hoặc làm block design |
| 17 | 1 channel với ảnh rộng hơn một lượt x (ví dụ MNIST Conv1 28×28): các hàng output đi theo cặp giống nhau | `iact_stream_constructor.v` (bộ ghi 1 channel) | **Chưa sửa** (lỗi cũ, có từ trước `23be043`): địa chỉ 1 channel (hàng + cột) không tính các lượt x. Rộng 8/16 đúng, rộng 28 sai |
| 18 | Filter 32–63 sai (MNIST Conv2/Conv3); thực chất **mọi layer > 4 channel tính sai với weight thật** | `src/open_eye/conv_mapper.py` (Python) | **Đã sửa** (2026-10-15, được bạn đồng ý; xoá khoá `used_wght_per_PE` bị lặp). Kiểm chứng từng word bằng tính toán numpy độc lập (mục 9). Conv2 MNIST thật PASS, Conv3 đúng mọi giá trị; baseline −16 % đến −25 % chu kỳ |
| 18b | Số filter > 32 và không chia hết cho 32 (40, 48): sai từ cả filter 0 | Python/psum address generator | **Chưa điều tra xong**: Python báo 768 word ra nhưng tạo tham chiếu 1.024 dòng. MNIST không dùng |

### 8c. Kế hoạch gần (theo thứ tự ưu tiên, cập nhật 2026-10-15)

**Định hướng (mốc phần cứng 2026-10-19: 64,1k LUT, 39,2k FF, 192 BRAM tile, đạt 250 MHz sau route; mốc chu kỳ `baseline_2026-10-15`, không đổi sau bản sửa #14):**

| # | Việc | Loại | Vì sao | Trạng thái |
|---|---|---|---|---|
| A | Place & route (clock 4 ns) để có fmax chính thức | Vivado, không sửa RTL | Fmax sau tổng hợp là ước lượng lạc quan; mọi tối ưu cần cả chu kỳ lẫn fmax | **Xong 2026-10-13: đạt 250 MHz sau route** (WNS +0,025 ns); đường găng là dây tới 144 BRAM của bộ đệm psum (mục 6d) |
| B | **Lỗi #13: phần cứng khác mô phỏng** ở `iact_stream_constructor` | Thí nghiệm, rồi sửa RTL | Nếu đúng như Vivado báo, bitstream hiện tại tính sai iact, nên mọi số đo trên board sẽ vô nghĩa | (1) Thí nghiệm **xong 2026-10-13: lỗi có thật**, 6/9 case sai trên phần cứng giả lập. (2) **Đã sửa 2026-10-13** (mục 9). (3) **Vivado xác nhận 2026-10-14**: CRITICAL WARNING biến mất, vẫn đạt 250 MHz. **Xong** |
| B2 | Lỗi #6/#7 (1 channel, `NUM_GLB_IACT=3`) và #18 (weight đọc gấp đôi) | Sửa RTL (#6/#7), Python (#18) | Kết quả sai | **Xong 2026-10-14/15** (mục 9), Vivado xác nhận |
| C | Gửi bias theo filter (1.1 bên dưới) | Sửa RTL | Bias chiếm **26 %** chu kỳ `mnist1` sau bản sửa #18; ước tính −23 % chu kỳ, DMA pha bias giảm khoảng 900 lần, chi phí khoảng +2 % FF và 0 BRAM | Chờ đồng ý |
| C2 | MNIST đầy đủ: lỗi #17 (Conv1), #9 (Conv3), #5 (FC) | Python (đệm channel) hoặc RTL | Chạy cả mạng thật, đo độ trễ end-to-end | Chưa làm |
| D | Thu nhỏ bộ đệm psum (`BUFFER_WIDTH_PSUM` 14 → 11/12) | Đổi tham số, không sửa RTL | 144/168 RAMB36 là bộ đệm psum, layer lớn nhất chỉ dùng khoảng 1.792/16.384 địa chỉ (ước tính); tiết kiệm khoảng 100–124 BRAM36 để thêm cluster hoặc bộ đệm | Cần kiểm chứng bằng 9 case. Sau route còn thấy lợi thêm: đường găng là dây tới các BRAM này, nên bộ đệm nhỏ hơn có thể tăng fmax |
| E | DMA 128 bit | Băng thông | Cổng HP của ZU+ rộng 128 bit; 64 bit ở 250 MHz chỉ đạt khoảng 2 GB/s; giảm một nửa số chu kỳ nạp và đọc kết quả | 128 bit chưa từng được kiểm chứng |
| F | Pipeline đường găng iact converter (`OpenEye_FPGA.v` 943–950) | Sửa RTL (fmax) | Tính trước các tích tham số một lần mỗi layer | Chỉ làm nếu fmax sau route chưa đủ |
| G | `USE_DSP=1` cho PE | Sửa RTL (tài nguyên) | Bộ nhân 48 PE đang dùng LUT, còn 1.724 DSP trống | Khi cần thêm cluster |
| H | Lỗi #14, #15 (cảnh báo "simulation mismatch") | Phân tích, có thể sửa RTL | Cùng loại rủi ro với #13 | Phân tích sau B |

Thứ tự đề xuất: A, B, B2 **đã xong**; tiếp theo là C (bias theo filter) và C2 (MNIST đầy đủ), rồi D.
Mỗi thay đổi RTL: test, `run_profile --compare`, Yosys (so sánh nhanh LUT), Vivado ở các mốc quan trọng.

**Kế hoạch theo giai đoạn (số liệu cập nhật theo `baseline_2026-10-15`):**

1. **Giai đoạn 1.1: gửi bias theo filter** (= hướng C; thiết kế ở dưới). **Cần bạn đồng ý** vì sửa RTL.
2. **Giai đoạn 1.2: readout INT8.** Lượng tử kết quả trên chip trước khi gửi ra (đường này đã có cho write-back giữa các layer).
   Readout của `mnist1` chiếm 26 %; có thể giảm khoảng 4 lần số word.
3. **Giai đoạn 1.3: tìm hiểu định dạng weight** (hiệu suất 15–30 %). Bước đầu chỉ phân tích, không sửa RTL; sau đó mới đề xuất cách đóng gói.
4. **Việc 0.2:** đo layer Dense và lượt nhiều layer. Bị chặn một phần bởi lỗi #5; cần quyết định có điều tra hoặc sửa lỗi #5 không.
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

Mỗi bước đều đánh giá bằng `tools/run_profile.py --compare doc/perf/baseline_2026-10-15`, kèm thêm `--mem typical` để thấy lợi ích khi có bộ nhớ thực tế hơn.

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
  MNIST Conv1 (1 channel, rộng 28) còn lỗi #17.

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
Cùng với bản sửa lỗi #13 và bản sửa lỗi #6/#7 (bên dưới), đây là 3 thay đổi RTL so với upstream.

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
- `model_test` (chạy cả model) bị tắt trong testbench.
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

## 9b. Kết quả lint RTL chi tiết (Verilator 5.020, 2026-10-10)

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
