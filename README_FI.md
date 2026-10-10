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
  tự cấp dữ liệu song song cho từng cluster. Hiện **không có luồng nào chạy được ở chế độ này**.
- **Liên quan tới hướng nghiên cứu:** `SERIAL=0` giữ dữ liệu trong GLB của từng cluster, tức tái sử dụng dữ liệu trên chip nhiều hơn
  và giảm lưu lượng DMA. Về lâu dài đây có thể là một hướng kiến trúc, nhưng phải hoàn thiện phần RTL còn thiếu. Đây là việc lớn, không thuộc trước mắt.

### 5.8 Độ rộng DMA: 32 bit hay 64 bit

- **Phần cứng FPGA (`fpga/hdl/open_eye_axi_v1_0.v`): 64 bit.** `C_dma_i_TDATA_WIDTH = C_dma_o_TDATA_WIDTH = 64`; wrapper không truyền
  `DMA_BITWIDTH` vào `OpenEye_FPGA`, nên lõi dùng giá trị mặc định `parameter DMA_BITWIDTH = 64` (`OpenEye_FPGA.v:123`).
- **Mô phỏng/đo hiệu suất:** giá trị lấy từ biến môi trường `DMA_BITWIDTH` (nếu không có thì mặc định 64 trong `OpenEyeParameters`) và được ghi
  vào `parameters_FPGA.vh`. Các case đo dùng **64 bit** để khớp với phần cứng, trừ case `32x3_f4_q32_dma32` (32 bit, để so sánh: chậm hơn 34 %).
  Lưu ý: `test/cocotb_fpga/Makefile` của upstream đặt `DMA_BITWIDTH = 32`, và notebook MNIST cũng dùng 32.
- **Cố định hay thay đổi được?** `DMA_BITWIDTH` là **tham số lúc tổng hợp (elaboration)**: sau khi tổng hợp và nạp bitstream thì **cố định**; muốn đổi thì
  tổng hợp lại. Khi đổi phải đổi **đồng thời**: độ rộng stream của IP AXI DMA, `C_dma_*_TDATA_WIDTH` của wrapper (và thêm `.DMA_BITWIDTH(...)` vào
  wrapper, hiện chưa có), cùng bộ sinh stream Python và runtime (dữ liệu được đóng gói theo `DMA_BITWIDTH`).
- **Giá trị nào chạy được:** 32 và 64 đã chạy đúng trong mô phỏng. Logic đọc kết quả xếp psum vào các ô 32 bit (`DMA_BITWIDTH // 32` psum mỗi beat),
  nên độ rộng phải là bội của 32. 128 bit **chưa được kiểm chứng** (có các hằng số như `WORDS_PER_CYCLE = 2` và comment giả định beat 64 bit).

## 6. Hướng dẫn chạy công cụ đo hiệu suất

### 6.1 Các công cụ

| Công cụ | File | Vai trò |
|---|---|---|
| Profiler | `src/open_eye/rtl_test_utils.py` → `profile_dma_phases` | Chạy bên trong simulation. Mỗi chu kỳ ghi lại pha, số word DMA vào/ra và chu kỳ chờ bộ nhớ; kết quả vào `profile.json`. Bật bằng `OPENEYE_PROFILE=1` |
| Các case đo | `test/cocotb_fpga/test_profile.py` | 9 cấu hình layer Conv (mục 6.7) |
| Bộ chạy | `tools/run_profile.py` | **Lệnh chính.** Chạy các case song song, so sánh, lưu snapshot |
| Báo cáo | `src/open_eye/profile_report.py` | In bảng từ các `profile.json`; `--compare` để so sánh trước/sau |
| Mô hình bộ nhớ | `src/open_eye/memory_model.py` | Giả lập DDR + AXI DMA (mục 6c). Bật bằng `--mem` |
| Baseline | `doc/perf/baseline_2026-10-10/` | Số liệu mốc của 9 case (bộ nhớ lý tưởng) |

### 6.2 Chuẩn bị (một lần)

- Đứng ở thư mục gốc của repo: `cd ~/OpenEye_orig`.
- Dùng Python của venv: `venv/bin/python` (đã có cocotb, cocotb-test, tensorflow, open_eye).
- Cần `iverilog` (Icarus Verilog 11) trong `PATH`; máy này đã có sẵn.
- Không cần `source venv/bin/activate` nếu luôn gọi `venv/bin/python ...`.

### 6.3 Chạy nhanh

```bash
# Chạy 6 case nhỏ (khoảng 1–4 phút) và so với baseline:
venv/bin/python tools/run_profile.py -k "not mnist" --compare doc/perf/baseline_2026-10-10

# Chạy cả 9 case (khoảng 10 phút, 3 case kiểu MNIST mất 4–9 phút mỗi case):
venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-10-10

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
| `--compare DIR` | So với snapshot trong `DIR` (lặp lại được) | `--compare doc/perf/baseline_2026-10-10` |
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
3. Đo: `venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-10-10`.
   Mô phỏng là tất định, nên **mọi chênh lệch đều do thay đổi của bạn gây ra**.
4. (Tuỳ chọn) đo thêm với bộ nhớ thực tế hơn: thêm `--mem typical`, và so với `doc/perf/mem_typical_2026-10-10` (5 case `q32`).
5. Nếu giữ thay đổi: lưu snapshot và báo cáo, rồi commit:
   ```bash
   venv/bin/python tools/run_profile.py --jobs 4 --save doc/perf/<tên>_<ngày> \
       --report doc/perf/<tên>_<ngày>.md --compare doc/perf/baseline_2026-10-10
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
| Conv1: 28×28, 1 → 32 | 28×28, **4** → 32 | RTL sai với 1 channel vào (mục 9) |
| Conv2: 14×14, 32 → **64** | 14×14, 32 → **32** | Bộ sinh dữ liệu Python lỗi với 64 filter (`layer_parameters.read_data_from_layer`, IndexError) |
| Conv3: **7×7**, 64 → 64 | **8×8**, 32 → 32 | 7×7 có cột đệm; phần cứng ghi giá trị khác 0 vào ô đệm nên kiểm tra chuỗi DMA FAIL (giá trị thật vẫn đúng). 64 → 32 như trên |

Khảo sát ngày 2026-10-10 (đều `QUANT_AMOUNT=32`, `NUM_GLB_IACT=1`): **PASS**: 8/16/32 channel, 32 filter, 14×14, 28×28, 8×8.
**FAIL**: 64 filter (lỗi Python), 7×7 (ô đệm).

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

### 6.10 Profiler hoạt động thế nào

Coroutine cocotb lấy mẫu **mỗi cạnh lên của clock**. Với mỗi chu kỳ, nó xác định pha (FSM chính, hoặc `readout` khi FSM psum
ở `PSUM_SEND_RESULTS`) và đếm: `cycles`, `in_offered` (host đưa word), `in_accepted` (`enable_dma_i_reg & ready_dma_o`),
`out_words` (`enable_dma_o & ready_dma_i`), `in_stall` (pha nạp, DUT sẵn sàng nhưng không có word), `out_stall` (có kết quả nhưng
`ready_dma_i` thấp). Cửa sổ đo bắt đầu từ word vào đầu tiên được nhận và kết thúc ở word ra cuối cùng. File `profile.json` được ghi lại
mỗi khi đổi pha và sau mỗi word ra, nên vẫn còn khi test FAIL hoặc treo.

Giới hạn: payload và hiệu suất bus chỉ tính cho `Convolution_Single` (việc 0.2 sẽ mở rộng cho Dense và lượt nhiều layer).
**Chưa đo được MNIST nguyên model**: `model_test` bị tắt, RTL sai với 1 channel, và chuỗi nhiều layer chưa ổn định.

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
| Độ trễ DDR, burst, ngắt quãng `tvalid` | **Không** | Có ảnh hưởng thật |
| Overhead phần mềm (flush/invalidate cache, cấu hình DMA, polling, giữa các layer) | **Không** | Có; với layer nhỏ có thể lớn hơn cả thời gian tính |
| Tần số clock tối đa (fmax), tài nguyên, công suất | **Không** | Chỉ biết sau khi tổng hợp và place & route (Vivado) |

**Kết luận:**
- Các tối ưu về **băng thông** (giảm số beat, tăng hiệu suất bus) đo trên mô phỏng là **chính xác** và giữ nguyên khi lên FPGA.
- Các tối ưu **độ trễ bên trong** RTL (giảm chu kỳ convert/compute, chạy chồng pha) cũng chính xác **về số chu kỳ**.
- Con số tổng độ trễ của mô phỏng là **trường hợp tốt nhất về phía bộ nhớ**; trên FPGA sẽ chậm hơn. Mức chậm hơn bao nhiêu
  phụ thuộc vào board, cấu hình AXI DMA (độ dài burst, độ rộng bus) và phần mềm, nên chưa thể ước lượng nếu không đo trên board.
- Giảm số beat thường còn **có lợi hơn** trên FPGA thật, vì mỗi beat bỏ bớt cũng tránh được thời gian chờ DDR tương ứng.

### Cách thu hẹp khoảng cách
1. **Mô hình bộ nhớ trong cocotb**: **đã làm** (mục 6c).
2. **Bộ đếm hiệu năng trong RTL**: đếm chu kỳ của mỗi pha và số beat, đọc qua AXI-Lite trên board. Đây là thay đổi RTL, cần bạn đồng ý.
3. **Tổng hợp bằng Vivado** để lấy fmax và tài nguyên (thư mục `dse_scripts/` đã có script nhưng đang trỏ tới project trên máy của tác giả gốc).
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
| `test/test_memory_model.py` | 15 unit test so với công thức tính tay |

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

## 7. Kết quả baseline chính (chi tiết: `doc/perf/baseline.md`)

**Baseline hiện tại: `doc/perf/baseline_2026-10-10/`** (9 case, bộ nhớ lý tưởng).

**Layer kiểu MNIST (0.3):**

| Case | Thay cho | Tổng chu kỳ | Compute | Pha không tính toán lớn nhất |
|---|---|---:|---:|---|
| `mnist1_28x28_c4_f32` | Conv1 | 65.800 | 51% | **bias 22%** (14.336 word cho 96 byte payload), readout 22% |
| `mnist2_14x14_c32_f32` | Conv2 | 87.032 | **77%** | weight 9% (hiệu suất 15%), convert 5% |
| `mnist3_8x8_c32_f32` | Conv3 | 26.728 | 71% | weight 14% (hiệu suất 30%), convert 6% |

**Layer nhỏ (2026-10-09):**
1. Phần tính toán chỉ chiếm **14–40%** độ trễ; mọi pha chạy **tuần tự**.
2. Bus DMA chỉ bận **35–58%** số chu kỳ.
3. **Bias gửi theo từng pixel output** (hiệu suất 1–5%).
4. **Weight**: hiệu suất 15%.
5. **Bảng lượng tử** luôn gửi đủ `QUANT_AMOUNT` entry.
6. **Readout** gửi psum 20 bit trong ô 32 bit.

**Rút ra cho Giai đoạn 1:**
- Layer đầu (ảnh lớn, ít channel): **bias theo filter** và **readout INT8** là quan trọng nhất (tới khoảng 40% độ trễ).
- Layer sâu (nhiều channel): compute chiếm phần lớn; tối ưu DMA còn khoảng 10–15% (chủ yếu weight). Muốn giảm thêm thì phải
  chạy chồng pha (Giai đoạn 2) hoặc tăng hiệu suất tính toán.
- Với bộ nhớ thực tế hơn (`typical`), mỗi word DMA tốn khoảng 1,44 chu kỳ, nên lợi ích của việc giảm word còn lớn hơn (mục 6c).

## 8. Lộ trình

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 0. Đo lường | Profiler, báo cáo, so sánh, baseline 9 case, mô hình bộ nhớ | **Gần xong**: còn 0.2 (Dense, nhiều layer) |
| 1. Giảm lưu lượng DMA | Bias theo filter, đóng gói weight, bảng quant theo F hoặc lưu BRAM, readout INT8 | Chưa làm. Đề xuất bắt đầu với bias |
| 2. Che độ trễ | Double-buffering (`BRANCHES=2`): nạp lượt sau trong lúc lượt hiện tại tính toán | Chưa làm (cần sửa lỗi chọn nửa buffer iact trước) |
| 3. Mô hình và DSE | Mô hình Python dự đoán chu kỳ và byte, roofline, quét cấu hình | Chưa làm |

**Giai đoạn 0: trạng thái chi tiết** (cập nhật 2026-10-10)

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

### 8b. Tổng hợp lỗi phát hiện được (cập nhật 2026-10-10)

| # | Lỗi | Nơi | Trạng thái |
|---|---|---|---|
| 1 | Giải mã sai thứ tự output Conv ở chế độ SERIAL (124/128 giá trị sai ở 1×1 cluster, DMA 32 bit) | testbench Python | **Đã sửa** (`27aa75c`) |
| 2 | Bộ sinh tài liệu Verilog: 125 warning Sphinx, mất parameter | `doc/verilog_doc_parser` | **Đã sửa** (`83750e9`) |
| 3 | `GET_BIAS` rời trạng thái khi chưa nhận word bias cuối (treo khi DMA có khoảng trống) | `hdl/OpenEye_FPGA.v` | **Đã sửa** (`77f0477`), 0 chu kỳ, 0 tài nguyên |
| 4 | CI lint luôn fail (38 warning có sẵn) | `.github` | **Đã xử lý** bằng lint baseline (`4a26867`); RTL không đổi |
| 5 | Dense/FC: `FC activation write ... bank=1 addr=0` sai (23/63 test GEMM/Dense) | RTL hoặc testbench Dense | **Chưa sửa** (có sẵn ở upstream) |
| 6 | Input 1 channel: chỉ ra bias | RTL (đường iact) | **Chưa sửa** |
| 7 | Input 3 channel và mọi `NUM_GLB_IACT=3`: giá trị sai | RTL (đường iact) | **Chưa sửa** |
| 8 | 64 filter: `IndexError` trong `layer_parameters.read_data_from_layer` | Python | **Chưa sửa** |
| 9 | Ảnh rộng 7 (có cột đệm): phần cứng ghi giá trị khác 0 vào ô đệm (giá trị thật vẫn đúng) | RTL/testbench | **Chưa sửa** |
| 10 | `CLUSTER_ROWS=1`: một số cấu hình treo FSM (theo tài liệu upstream) | RTL | **Chưa sửa**, chưa tự kiểm chứng |
| 11 | Lint đáng ngờ: `PE.v:2210` (cắt 7→5 bit), `data_pipeline_wght.v:394/396/424` (overhead 4 bit), `BLKANDNBLK` trong `psum_pipeline.v` | RTL | **Chưa sửa**, cần test (mục 9b) |

### 8c. Kế hoạch gần (theo thứ tự ưu tiên)

1. **Giai đoạn 1.1: gửi bias theo filter.** Hiện bias được gửi theo từng pixel output (hiệu suất bus khoảng 0 %; 22 % độ trễ của layer kiểu Conv1).
   Sửa RTL (`GET_BIAS`, `psum_pipeline.v`) và bộ sinh stream Python. Ước tính `mnist1`: 14.336 → vài chục word, giảm khoảng 20 % độ trễ.
   **Cần bạn đồng ý** vì sửa RTL.
2. **Giai đoạn 1.2: readout INT8.** Lượng tử kết quả trên chip trước khi gửi ra (đường này đã có cho write-back giữa các layer).
   Readout của `mnist1` chiếm 22 %; có thể giảm khoảng 4 lần số word.
3. **Giai đoạn 1.3: tìm hiểu định dạng weight** (hiệu suất 15–30 %). Bước đầu chỉ phân tích, không sửa RTL; sau đó mới đề xuất cách đóng gói.
4. **Việc 0.2:** đo layer Dense và lượt nhiều layer. Bị chặn một phần bởi lỗi #5; cần quyết định có điều tra hoặc sửa lỗi #5 không.
5. **Giai đoạn 2:** chạy chồng pha nạp và pha tính toán (double-buffering), sau khi Giai đoạn 1 xong.

Mỗi bước đều đánh giá bằng `tools/run_profile.py --compare doc/perf/baseline_2026-10-10`, kèm thêm `--mem typical` để thấy lợi ích khi có bộ nhớ thực tế hơn.

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

**Lỗi `GET_BIAS` khi dữ liệu DMA tới không liên tục** (tìm ra, kiểm chứng và **đã sửa** ngày 2026-10-10, với sự đồng ý của bạn):
- `hdl/OpenEye_FPGA.v:1974`: `GET_BIAS` chuyển sang `GET_QUANTIZE` khi `fsm_psum_cycle == trans_cycles_psum - 1`,
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
Đây là thay đổi RTL duy nhất so với upstream.

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
- `CLUSTER_ROWS=1`: có cấu hình bị treo FSM (theo `doc/test_status_handover.md`).
- `model_test` (chạy cả model) bị tắt trong testbench.
- **CI "Lint"** của upstream luôn fail vì các warning có sẵn trong RTL (repo gốc cũng fail ở mọi commit). Từ 2026-10-10, CI của `dev`
  dùng lint theo baseline (mục 9c), chỉ fail khi có warning mới. Chi tiết từng warning: mục 9b.

## 9b. Kết quả lint RTL chi tiết (Verilator 5.020, 2026-10-10)

Output gốc đầy đủ: `doc/lint/verilator-5.020_2026-10-10.txt`. Mọi warning dưới đây đều có sẵn trong upstream; bản sửa `GET_BIAS` (mục 9) không thêm warning nào.

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
- Ảnh hưởng tới cấu hình đang đo: không, vì các test hiện dùng `SPARSITY_EN=0`. Sẽ quan trọng nếu bật sparsity.

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
- Kết quả sau khi trừ `filters_w` thường nhỏ, nhưng nếu phép trừ ra số âm thì bị cắt thành một số dương sai. Chỉ dùng khi `SPARSITY_EN=1`.
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
