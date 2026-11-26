# Làn ghi ngược mang output nào: kiểm bằng mô phỏng (2026-11-26)

Câu hỏi: ghi ngược có X làn song song (`WRITEBACK_WORDS = min(TRANS_WORDS, NUM_GLB_PSUM)`); mỗi làn mang giá trị nào, giá
trị đó đã cộng đủ (bias + mọi channel + mọi hàng kernel) chưa. Cách đo (`2026-11-26_writeback_lanes/`, chỉ Python, RTL không
đổi): `probe_lanes.py` bọc testbench, ở mỗi cạnh clock có `act_capture` = 1 ghi giá trị của mọi làn
(`psum_pipeline_inst.quantized_value_flat`) cùng trạng thái FSM psum; sau khi chạy lưu tham chiếu output của layer (int8 sau
lượng tử, `dram.fmap[1]`). Lịch ghi ngược không phụ thuộc dữ liệu, nên chạy cùng layer với 4 seed và lấy giao các vị trí có
cùng giá trị (`analyse_lanes.py`) xác định duy nhất (filter, x, y) của từng ô. Convolution_Stack, layer 0 ghi ngược, CR 2, sparse,
không hàm kích hoạt. Mọi lần chạy PASS.

| Ca | Ô (lần nhận × làn) | Xác định duy nhất | Output được ghi |
|---|---:|---:|---|
| X 4, Conv 8 × 4 × 4 → 8 | 70 × 4 = 280 | 280/280 | 256/256; 232 một lần, 24 hai lần (6 lần nhận cuối lặp lại, cùng giá trị) |
| X 2, cùng layer | 134 × 2 = 268 | 268/268 | 256/256; 244 một lần, 12 hai lần |
| X 4, Conv 16 × 4 × 4 → 16 | 262 × 4 = 1.048 | 1.048/1.048 | 1.024/1.024; 1.000 một lần, 24 hai lần |

Thứ tự (X 4, Conv 8 × 4 × 4 → 8; f = filter, x, y = vị trí output):

| lần nhận | làn 0 | làn 1 | làn 2 | làn 3 |
|---:|---|---|---|---|
| 0 | (0, 0, 0) | (0, 1, 0) | (0, 2, 0) | (0, 3, 0) |
| 1 | (1, 0, 0) | (1, 1, 0) | (1, 2, 0) | (1, 3, 0) |
| 2 | (2, 0, 0) | (2, 1, 0) | (2, 2, 0) | (2, 3, 0) |
| 3 | (3, 0, 0) | (3, 1, 0) | (3, 2, 0) | (3, 3, 0) |
| 4 | (0, 4, 0) | (0, 5, 0) | (0, 6, 0) | (0, 7, 0) |
| … | … | … | … | … |
| 8 | (0, 0, 1) | (0, 1, 1) | (0, 2, 1) | (0, 3, 1) |
| 32 | (4, 0, 0) | (4, 1, 0) | (4, 2, 0) | (4, 3, 0) |

## Kết luận

1. **Mỗi giá trị trên một làn là một output hoàn chỉnh**: khớp đúng giá trị int8 cuối cùng của tham chiếu (bias + mọi
   channel + mọi hàng kernel, đã lượng tử), mỗi output có mặt. Không có bước cộng nào sau ghi ngược.
2. **Các làn là X vị trí x liền nhau của cùng một filter, cùng hàng y** (X 4: x 0–3, rồi 4–7; X 2: x 0–1, 2–3, …). Số làn
   theo X (`NUM_GLB_PSUM`); làn 4–7 (X 4) và 2–7 (X 2) luôn 0.
3. **Các lần nhận liên tiếp đi qua 4 filter** (0, 1, 2, 3) cho cùng các pixel: thanh ghi của mỗi làn gom 4 filter = 4
   channel của layer sau thành một nhóm cho một pixel (bố cục nhóm 4 channel của bộ đệm activation). Thứ tự quét: nhóm 4
   filter → khối X vị trí x → hàng y → nhóm 4 filter kế tiếp.
4. **6 lần nhận cuối mỗi layer lặp lại các output đầu** (cùng giá trị, bộ đệm vẫn đúng): vô hại, nhưng `activation_cycles` của
   profiler đếm dư 6 chu kỳ mỗi layer.
5. Chỉ số cluster của FSM psum (`fsm_x_cl_psum`, `fsm_y_cl_psum`) giữ 0 trong suốt pha ghi ngược ở cả ba ca, nên phép đo này
   không cho thấy ghi ngược "đọc từng cluster một" như chú thích trong RTL; số làn vẫn chỉ theo X (đo 18/11: đổi CR không đổi
   tốc độ ghi ngược). Cột PE nào tính vị trí x nào cần thêm một phép đo ở bộ đệm psum.
