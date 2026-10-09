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
  (công cụ build lấy qua micromamba ở `~/tools/vbuild`, không cần sudo). Chạy lint giống CI:

```bash
~/tools/verilator-5.020/bin/verilator --lint-only -Wall -Ihdl/ +define+USE_INTERNAL_PARAMS_PE \
  +define+USE_INTERNAL_PARAMS_PE_cluster hdl/lint_waivers.vlt hdl/OpenEye_Parallel.v
```

## 4. Cấu trúc project (những phần liên quan tới hướng nghiên cứu)

| Đường dẫn | Nội dung |
|---|---|
| `hdl/OpenEye_FPGA.v` | Top-level FPGA: nhận dữ liệu qua DMA, FSM chính điều khiển mỗi layer |
| `hdl/psum_pipeline.v` | FSM psum: nạp bias, thu kết quả, lượng tử hoá, gửi kết quả ra DMA |
| `hdl/OpenEye_Parallel.v`, `OpenEye_Cluster.v`, `PE.v` | Mảng tính toán (cluster, PE) |
| `src/open_eye/` | Thư viện Python: sinh stream DMA, tính kết quả tham chiếu, tiện ích testbench |
| `src/open_eye/rtl_test_utils.py` | Các hàm cocotb: gửi stream, so sánh kết quả, **profiler** |
| `src/open_eye/profile_report.py` | Công cụ báo cáo profile (bảng, CSV) |
| `test/cocotb_fpga/` | Testbench top-level FPGA (`OpenEye_FPGA_tb.py`) và các bộ test pytest |
| `doc/perf/` | Số liệu đo hiệu năng (baseline) |

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
không có trạng thái riêng cho việc này.

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
  Testbench hiện tại **không mô phỏng burst hay độ trễ bộ nhớ**: host luôn sẵn sàng và gửi liên tục.
  Vì vậy số liệu hiện tại là trường hợp tốt nhất về phía bộ nhớ.

**Một burst gồm nhiều beat liên tiếp.** Ví dụ: chuyển 100 beat trong 1 burst tốn khoảng 100 + 1 × độ trễ; chia thành 100 burst
thì tốn khoảng 100 + 100 × độ trễ.

**DMA trong project:**
- Trên FPGA thật (`fpga/`): dùng **Xilinx AXI DMA IP ở chế độ Simple** (không có Scatter-Gather), tắt ngắt và chờ bằng polling
  (`fpga/sw/runtime/hal_xaxidma.c`). Có 2 kênh: MM2S (DDR → bộ tăng tốc) và S2MM (bộ tăng tốc → DDR).
  Phía bộ tăng tốc là **AXI4-Stream** (`tvalid/tready/tdata/tlast`, không có địa chỉ); cấu hình qua AXI4-Lite
  (`fpga/hdl/open_eye_axi_v1_0.v`). Runtime gửi **toàn bộ stream của một layer bằng một lệnh `XAxiDma_SimpleTransfer`**
  (`openeye_runtime.c`). Chính IP AXI DMA mới chia lệnh đó thành các burst AXI4 tới DDR; độ dài burst do cấu hình IP
  trong Vivado quyết định, và cấu hình này không nằm trong repo. Input `tlast` bị bỏ qua; output `tlast` = `last_data_o`.
- Trong simulation (cocotb): **không có AXI DMA**. Testbench đẩy thẳng mỗi chu kỳ một word vào cổng stream, luôn sẵn sàng,
  nên chưa mô phỏng burst và độ trễ DDR.

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
tối ưu có tác dụng. Baseline hiện tại: `doc/perf/baseline.md` và `doc/perf/baseline_2026-10-09.csv`.

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
   (`OpenEye_FPGA.v`, khoảng dòng 2020–2025). 640 beat tạo ra 640 lần thay đổi của một vector khổng lồ.
3. Mỗi lần `quant_reg` thay đổi, Icarus phải tính lại **mọi lệnh `assign` đọc từ nó**: 3 × 1024 lệnh tách
   offset, exponent, mantissa trong `OpenEye_FPGA.v`, cộng thêm các bản "flat" và bản trong `psum_pipeline.v`.
   Tổng cộng hàng nghìn phép cắt bit trên vector 40 kbit, lặp lại sau mỗi beat.
4. Thêm thời gian biên dịch (`iverilog`) cho thiết kế lớn hơn, và 620 chu kỳ DMA thừa.

Trên FPGA thật, cách lưu này cũng tốn **khoảng 41.000 flip-flop**. Nếu lưu bảng trong BRAM và chỉ nạp `F` entry
thì vừa tiết kiệm tài nguyên, vừa giảm DMA, vừa giúp simulation nhanh hơn. Đây là một ứng viên tối ưu.

## 6. Profiler (`profile_dma_phases`): cách dùng và phạm vi

**Hoạt động:** coroutine cocotb lấy mẫu **mỗi cạnh lên của clock**. Với mỗi chu kỳ, nó xác định pha (mục 5.1) và đếm:
`cycles`, `in_offered` (host đưa word vào), `in_accepted` (DUT nhận word, `enable_dma_i_reg & ready_dma_o`),
`out_words` (word ra, `enable_dma_o & ready_dma_i`). Cửa sổ đo bắt đầu từ word vào đầu tiên và kết thúc ở word ra cuối cùng.
Kết quả được ghi vào `profile.json` trong thư mục simulation.

**Bật:** đặt biến môi trường `OPENEYE_PROFILE=1` trước khi chạy test `OpenEye_FPGA_tb` (mặc định tắt).

**Báo cáo:**

```bash
venv/bin/python -m open_eye.profile_report test/.temp/*test_profile*/profile.json --csv out.csv
```

**Các cấu hình đã đo** (`test/cocotb_fpga/test_profile.py`). Tất cả là **một layer Conv đơn** (`Convolution_Single`),
kernel 3×3, 4 channel vào, 2×2 cluster, psum 20 bit:

| Case | Input | Filter | QUANT_AMOUNT | DMA | Tổng chu kỳ | Compute |
|---|---|---|---|---|---:|---:|
| `8x1_f4_q1024_dma64` | 8×1 | 4 | 1024 | 64 | 1188 | 13.6% |
| `8x1_f4_q32_dma64` | 8×1 | 4 | 32 | 64 | 568 | 28.3% |
| `16x3_f4_q32_dma64` | 16×3 | 4 | 32 | 64 | 984 | 36.3% |
| `32x3_f4_q32_dma64` | 32×3 | 4 | 32 | 64 | 1672 | 40.0% |
| `32x3_f16_q32_dma64` | 32×3 | 16 | 32 | 64 | 3652 | 31.1% |
| `32x3_f4_q32_dma32` | 32×3 | 4 | 32 | 32 | 2236 | 29.9% |

**Chưa đo MNIST.** Model MNIST (`models/mnist_conv_net.py`) gồm Conv1 (1→32 channel, ảnh 28×28),
MaxPool, Conv2 (32→64, 14×14), MaxPool, Conv3 (64→64, 7×7), rồi FC (3136→10).
Conv1 có 25.088 output, gấp khoảng 16 lần cấu hình lớn nhất ở trên. Lý do chưa đo được:
1. Testcase chạy model (`model_test` trong `OpenEye_FPGA_tb.py`) đang bị tắt trong code upstream.
2. RTL upstream còn lỗi ở đúng những điểm MNIST cần: input **1 channel** cho ra toàn bias
   (`test_conv_input_mapping[1-*]`, `test_conv_tall_ramp` fail), và chuỗi Conv rồi Pool rồi Conv chưa ổn định
   (xem `doc/test_status_handover.md`).
3. Bản thân profiler chạy được cho lượt nhiều layer (nó ghi `layer_starts`), nhưng phần tính payload và hiệu suất
   hiện chỉ hỗ trợ `Convolution_Single`.

## 7. Kết quả baseline chính (chi tiết: `doc/perf/baseline.md`)

1. Phần tính toán chỉ chiếm **14–40%** độ trễ của một layer, phần còn lại là nạp dữ liệu, chuyển đổi và đọc ra.
   Mọi pha chạy **tuần tự**, không chồng lên nhau.
2. Bus DMA chỉ bận **35–58%** số chu kỳ.
3. **Bias gửi theo từng pixel output** thay vì theo filter: hiệu suất 1–5%, chiếm tới 21% độ trễ ở layer 16 filter.
4. **Weight**: hiệu suất 15% (30 beat cho 36 byte mỗi filter 3×3×4).
5. **Bảng lượng tử** luôn gửi đủ `QUANT_AMOUNT` entry.
6. **Readout** gửi psum 20 bit trong ô 32 bit, chưa lượng tử về INT8 trước khi gửi ra.
7. Ước tính giới hạn trên: sửa 3 điểm bias, weight và readout có thể giảm tới khoảng 48% độ trễ của layer 32×3, 16 filter.

## 8. Lộ trình

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 0. Đo lường | Profiler chu kỳ/DMA, công cụ báo cáo, baseline | **Xong** (còn thiếu mô hình bộ nhớ ngoài: độ trễ và burst) |
| 1. Giảm lưu lượng DMA | Bias theo filter, đóng gói weight, bảng quant theo F hoặc lưu BRAM, readout INT8 | Chưa làm. Đề xuất bắt đầu với bias |
| 2. Che độ trễ | Double-buffering (`BRANCHES=2`): nạp lượt sau trong lúc lượt hiện tại tính toán | Chưa làm (cần sửa lỗi chọn nửa buffer iact trước) |
| 3. Mô hình và DSE | Mô hình Python dự đoán chu kỳ và byte, roofline, quét cấu hình | Chưa làm |

## 9. Các lỗi upstream đã biết (ảnh hưởng tới việc đo)

**Số channel vào và `NUM_GLB_IACT`** (đo ngày 2026-10-09: một layer Conv, input 8×1, 4 filter, ramp, 2×2 cluster, `QUANT_AMOUNT=32`):

| Channel vào | `NUM_GLB_IACT=1` | `NUM_GLB_IACT=3` |
|---|---|---|
| 1 | FAIL: ra toàn bias (giá trị 1) | FAIL: giá trị sai |
| 2 | **PASS** | FAIL: giá trị sai |
| 3 | FAIL: giá trị sai (dạng dốc lệch so với tham chiếu) | FAIL: giá trị sai |
| 4 | **PASS** | FAIL: giá trị sai |

- Chỉ có **2 hoặc 4 channel với `NUM_GLB_IACT=1`** là chạy đúng.
- Giả thuyết, **chưa kiểm chứng**: RTL đóng gói `CHANNELS_PER_WORD = 4` channel vào một word, nên số channel không chia hết cho 4
  (như 3) bị lệch dữ liệu, còn 1 channel đi theo một đường xử lý khác và hỏng theo kiểu khác (chỉ ra bias).
- `NUM_GLB_IACT=3` sai với mọi số channel đã thử.
- MNIST Conv1 có 1 channel vào, nên chưa chạy được trên RTL hiện tại.

**Khác:**
- `CLUSTER_ROWS=1`: có cấu hình bị treo FSM (theo `doc/test_status_handover.md`).
- `model_test` (chạy cả model) bị tắt trong testbench.
- **CI "Lint" (GitHub Actions) fail** trên `dev` vì bước `verilator --lint-only -Wall` trên `hdl/` fail.
  Lỗi kế thừa từ upstream: CI của repo gốc fail ở mọi commit gần đây, kể cả `c4bd562`; `hdl/` và `.github/` của `dev` giống hệt upstream.
  Chi tiết từng warning: mục 9b.

## 9b. Kết quả lint RTL (Verilator 5.020, 2026-10-10)

Output đầy đủ: `doc/lint/verilator-5.020_2026-10-10.txt`. `hdl/` của `dev` giống hệt upstream, nên đây cũng là lỗi của upstream.
CI fail vì `-Wall` biến warning thành lỗi ("Exiting due to 38 warning(s)"). **Không có lỗi cú pháp.**
Lưu ý: lint của CI chỉ kiểm tra cây module dưới `OpenEye_Parallel.v`, **không kiểm tra `OpenEye_FPGA.v` và `psum_pipeline.v`**.

| Loại | Số | Vị trí | Đánh giá |
|---|---:|---|---|
| WIDTHEXPAND | 26 | `data_pipeline_wght.v` (20), `PE.v` (4 + 2 cổng) | Toán hạng hẹp được mở rộng bằng 0. Theo chuẩn Verilog là đúng, **vô hại** |
| WIDTHTRUNC | 4 | `data_pipeline_wght.v:376, 394, 396, 424` | Bị cắt bit. 376 (`filters_w` 7 bit) vô hại vì đầu vào tối đa 63. **394/396**: tổng overhead của các sub-word bị gói vào 4 bit, có thể tràn ở chế độ sparse với `PARALLEL_MACS>1`. **Cần kiểm tra** |
| (cổng) | trong 26 ở trên | `PE.v:2210` | Output 7 bit `first_spad_words_o` nối vào dây 5 bit: **mất 2 bit cao** nếu số word lớn hơn 31. **Cần kiểm tra** (liên quan tới việc nạp weight) |
| SELRANGE | 2 | `PE.v:820` | Nhánh `SERIAL==0` lấy 40 bit từ số 20 bit. Luồng FPGA dùng `SERIAL=1` nên không bị ảnh hưởng; là **lỗi tiềm ẩn** ở chế độ song song |
| UNOPTFLAT | 2 | `PE.v:566`, `data_pipeline_wght.v:392` | Mảng nối tiếp kiểu `a[i+1] = f(a[i])` bị Verilator xem như vòng lặp tổ hợp. **Vòng lặp giả**, chỉ làm Verilator mô phỏng chậm hơn |
| UNDRIVEN | 2 | `OpenEye_Parallel.v:260-261` (`mem_addr_iact/psum`) | Có bit không được gán trong nhánh generate đang dùng. Ít khả năng ảnh hưởng, nên xem lại |
| PINMISSING | 2 | `GLB_cluster.v:187, 213` (`wr_mask_i`) | `RAM_SP.v` ghi chú rằng chân này được phép để trống. **Vô hại** |

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
