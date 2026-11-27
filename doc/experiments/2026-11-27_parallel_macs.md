# Một phép nhân mỗi PE (PARALLEL_MACS = 1): đo, mô hình, upstream và đề xuất (2026-11-27)

Chỉ đo và phân tích; không sửa RTL hay Python của dự án. Thư mục `2026-11-27_parallel_macs/`: `test_pm.py` (một layer
chạy riêng với `PARALLEL_MACS` 1 / 2), `model_pm.py` + `model_pm.txt` (mô hình chu kỳ đọc weight của PE sparse).

## 1. Đo trên RTL hiện tại (dev `cf4bffd`), CR 2 X 4 Y 3, weight / input không có số 0

| Layer (chạy riêng) | | Nạp weight | Tính toán | Tổng |
|---|---|---:|---:|---:|
| Conv 14×14×16→32 | dense, 1 phép nhân | 3.072 | 43.963 | 53.442 |
| | dense, 2 phép nhân | 2.304 | 22.459 | 31.170 |
| | sparse, 2 phép nhân | 3.840 | 22.505 | 32.752 |
| | sparse, 1 phép nhân | Python dừng: `data_pipeline_wght decodes two entries per word` | | |
| Conv 7×7×32→32 | dense 1 / 2 phép nhân | 3.072 / 2.304 | 22.011 / 11.259 | 27.742 / 16.222 |
| Dense 1568→32 | dense 1 / 2 phép nhân | 8.448 / 6.336 | 8.693 / 4.469 | 18.308 / 11.972 |

Dense với 1 phép nhân chạy đúng; tính toán ×1,95, nạp weight +33 % (hàng 12 ô × 8 bit = 96 bit vẫn cần 2 word 64 bit).

## 2. Có trường hợp nào 1 phép nhân mỗi PE lợi hơn ở sparse không: không

Mô hình (`model_pm.py`, dùng đúng bộ mã hoá cột của dự án `conv_wght_encoding.column_entries`): với mỗi activation khác 0,
PE đọc cột weight của nó, mỗi chu kỳ một word. 2 phép nhân: ⌈số mục / 2⌉ word; 1 phép nhân: một mục mỗi word (mục = weight
khác 0, cộng mục 0 cho đoạn hơn 15 số 0 và cho số 0 ở cuối cột; lạc quan cho 1 phép nhân vì không cần ô đệm).

| M0 (filter / cột) | weight = 0 | 0 % | 40 % | 80 % | 90 % | 95 % | 100 % |
|---|---|---:|---:|---:|---:|---:|---:|
| 16 | chu kỳ 1 PN / 2 PN | 2,00 | 1,90 | 1,77 | 1,66 | 1,50 | 1,00 |
| 8 | | 2,00 | 1,82 | 1,66 | 1,47 | 1,30 | 1,00 |
| 4 | | 2,00 | 1,69 | 1,44 | 1,27 | 1,15 | 1,00 |
| 16, cùng số bộ nhân (2 PE × 1 PN chia cột, PE chậm hơn quyết định) | | 1,00 | 1,12 | 1,32 | 1,39 | 1,37 | 1,00 |

1 phép nhân không bao giờ ít chu kỳ hơn: tỉ số giảm từ 2 về 1 khi weight càng thưa, chỉ bằng nhau khi cả cột bằng 0 (mỗi
cột vẫn cần ít nhất một mục). Kể cả khi cho gấp đôi số PE (cùng số bộ nhân) vẫn chậm hơn 6–39 % vì mỗi nửa cột tốn thêm một mục
cho số 0 ở cuối và PE chậm hơn quyết định. Số 0 của activation không đổi tỉ số (cả hai bỏ qua giống nhau). Thêm vào đó, nạp
weight sparse với 1 phép nhân dài hơn 20 % (12 ô × 12 bit = 144 bit → 3 word cho 12 weight, so với 5 word cho 24). Tham khảo:
4 phép nhân mỗi PE (nếu tham số hoá) đọc cột trong 0,50–0,87 lần số chu kỳ của 2 phép nhân (thưa càng nhiều càng lợi ít).

## 3. Upstream (`12340ab`, mới nhất)

* `hdl/data_pipeline_wght.v` giống dev ở chỗ này (dev chỉ khác 3 dòng của #47 cho dense): cùng dòng viết cứng
  `premade_spad_2_output = {data_storage_2[23:12], overhead_output, data_storage_2[7:0]}`, cùng ghi chú "the current
  implementation always assumes DATA_WIDTH / SECOND_SPAD_DATA = 2".
* Python của upstream (`set_sparse_stream`) có vòng lặp theo `PARALLEL_MACS` và không chặn, nhưng không có các sửa của #22
  (cách mã hoá số 0 mà RTL giải mã được); đường sparse Conv của upstream đã sai ở cả 2 phép nhân (0 / 23 ca sparse đúng, rà
  21/11), nên 1 phép nhân sparse cũng không dùng được ở upstream.
* Test `test_gemm_layer.py` của upstream (và `test_dense_readout.py::pm1_k64_n40` của dev, PASS) chạy 1 phép nhân với
  GEMM / Dense: weight gửi dạng raw (`raw_wght_i = 1`), không đi qua phần giải mã CSC nên không bị ảnh hưởng.

## 4. Đề xuất sửa triệt để (chưa làm; RTL cần đồng ý)

Mục tiêu: `PARALLEL_MACS` là tham số thật cho đường sparse (1, 2, 4), thay vì một giả định ngầm bằng 2.

RTL, `hdl/data_pipeline_wght.v`:
1. Sinh `premade_spad_2_output` theo số làn: thay mục 0 bằng `overhead_output`, các làn trên giữ nguyên, dùng
   `SECOND_PAYLOAD_WIDTH` / `SECOND_OVERHEAD_WIDTH` thay cho hằng 23:12, 11:8, 7:0 (cả `overhead_next_word`).
2. Nới `overhead_w` lên `$clog2(PARALLEL_MACS × 15 + 1)` bit (tổng các tag trong một word; nay 4 bit, chỉ an toàn vì cột tối
   đa 16 filter).
3. Tổng quát hoá phần sửa vượt biên cột (nhánh `- filters_w - 1`: "vượt đúng một" do ô đệm của cột lẻ) thành vượt tối đa
   `PARALLEL_MACS − 1`; với 1 phép nhân không còn ô đệm.
4. Triệt để nhất: bỏ quy ước "word toàn 0 = không có dữ liệu" (nguồn của #22, #47; buộc bộ mã hoá tránh mục (0, 0)), thay
   bằng đếm word: độ dài khối weight của mỗi PE đã biết khi cấu hình layer (⌈used_wght_per_PE / PARALLEL_MACS⌉), FSM nhận đúng
   số word đó. Thay đổi này cũng là phần RTL mà P1 (weight 8 bit, bước 3a) cần, nên làm chung một lần.

RTL, `hdl/PE.v`: các mảng theo làn đã tham số hoá; rà lại FSM sparse (đọc overhead theo làn, nhánh EMPTY_PASS của #31) để
không còn hằng 2.

Python: `conv_wght_encoding.column_entries` / `encode_columns` / `encode_dense` theo `PARALLEL_MACS` (ô đệm tới
`PARALLEL_MACS − 1`, FILLER theo số làn; nếu làm bước 4 thì bỏ được luật tránh word toàn 0), `wght_pipeline_model.py`, bỏ
kiểm tra `parallel_macs != 2` sau khi RTL qua kiểm chứng.

Kiểm chứng: unit test bộ mã hoá ↔ mô hình giải mã với 1 / 2 / 4 phép nhân; RTL: 4 dạng layer của mạng Bảng 2 × weight 0 –
80 % × input 0 / 50 % ở 1 và 2 phép nhân (như `test_pm.py`); hồi quy 254 test ở 2 phép nhân phải giữ nguyên từng chu kỳ;
lint Verilator 0 cảnh báo mới; Vivado cho LUT / timing.

Thứ tự ưu tiên: 1 phép nhân không bao giờ nhanh hơn (mục 2), nên không đáng làm chỉ để có 1 phép nhân; giữ kiểm tra Python
hiện có (nó dừng rõ ràng). Đáng làm bước 4 (đếm word) cùng với P1 / tách Weight–Activation, rồi các bước 1–3 nếu muốn thử 4
phép nhân mỗi PE.
