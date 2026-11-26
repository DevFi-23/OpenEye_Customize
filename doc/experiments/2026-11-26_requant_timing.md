# Bộ lượng tử và bảng hàm kích hoạt: mỗi tầng một chu kỳ, và có kịp trong 4 ns không (2026-11-26)

Hai câu hỏi khác nhau, hai cách kiểm khác nhau:

* **Mỗi tầng tốn đúng 1 chu kỳ (về logic)**: do thiết kế RTL, mỗi tầng kết thúc bằng một thanh ghi `always @(posedge clk_i)`;
  kiểm bằng mô phỏng RTL (Icarus), `2026-11-26_requant_timing/tb_requant.v`, log `tb_requant.log`.
* **Logic giữa hai thanh ghi kịp trong 1 chu kỳ 4 ns (về vật lý)**: mô phỏng RTL không có độ trễ cổng, nên phải dùng phân tích
  timing tĩnh (STA) của Vivado trên bản đã place and route (`doc/synth/2026-11-22_route4ns_fix51_zu7ev`, checkpoint
  `C:/openeye_vivado/fix51_2026-11-22/reports/OpenEye_FPGA_route.dcp`), script `timing_requant.tcl`, `timing_stages.tcl`,
  báo cáo `timing_requant.rpt`, `timing_stages.rpt`. STA tính mọi đường thanh ghi → thanh ghi, ở góc chậm nhất của chip
  (`Setup (Max at Slow Process Corner)`, speed grade −2), không phụ thuộc dữ liệu thử.

## 1. Mô phỏng: 3 chu kỳ trễ, 1 kết quả mỗi chu kỳ, bảng đọc không cần clock

`quantization_unit` với hệ số Conv1 MNIST Leaky ReLU (mant 8.817.157 / 2^31, neg 215 / 2^19, làm tròn), mỗi chu kỳ một psum:

| psum | kết quả sau cạnh thứ 3 (tính cả cạnh lấy mẫu) | mong đợi | sau cạnh thứ 2 |
|---:|---:|---:|---|
| 2000 | 8 | 8 | kết quả trước |
| −2000 | −1 | −1 | kết quả trước |
| 10000 / −10000 | 41 / −4 | 41 / −4 | kết quả trước |
| 0 / −1 | 0 / 0 | 0 / 0 | kết quả trước |
| 30000 / −30000 | 123 / −12 | 123 / −12 | kết quả trước |

Cạnh lấy mẫu nạp S1, cạnh sau nạp S2, cạnh thứ ba nạp S3 (thanh ghi output): đúng 3 chu kỳ trễ, và mỗi chu kỳ ra một kết
quả mới (pipeline). `activation_table`: nạp 32 word ở cạnh clock (we), rồi đổi `value_i` ba lần trong 0,2 ns giữa hai cạnh
clock (174 và 178 ns): `value_o` đổi theo ngay (T[5] = 122, T[−3] = 130, T[−128] = 255), không cần cạnh clock nào. RESULT PASS.

## 2. STA: đường xấu nhất vào từng tầng (4 ns = 250 MHz, sau route)

| Thanh ghi đích | Đường xấu nhất | Trễ đường dữ liệu | Slack |
|---|---|---:|---:|
| S1 (`sum_s1`, `mant_s1`, `shift_s1`) | reset đồng bộ → CLR (đường dữ liệu còn rộng hơn) | 3,151 ns | +0,739 ns |
| S2 (`prod_s2`): nhân mant × sum + hằng làm tròn | `mant_s1` → DSP48E2 + 5 CARRY8 → `prod_s2` | 3,865 ns | **+0,116 ns** (chặt nhất) |
| S3 = R4 (`quantized_value`): dịch, kẹp | `prod_s2` → 2 CARRY8 + 5 LUT → R4 | 3,128 ns | +0,853 ns |
| R5 (`iact_to_psum_mux_reg`), đường dữ liệu qua bảng | R4 → LUTRAM → 2 LUT6 → R5 | 2,489 ns | **+1,491 ns** |
| R5, đường điều khiển | `fsm_cycle` → CE của R5 | 2,666 ns | +1,228 ns |
| bảng, đường ghi (nạp bảng) | `data_dma_i_reg` → cổng ghi LUTRAM | 2,295 ns | +1,603 ns |

Đường R4 → R5 xấu nhất, chi tiết (`timing_requant.rpt`): clock → Q của R4 0,078 ns; dây (R4 nối tới 113 chân: mọi bank
của bảng và mux) 1,228 ns; **đọc LUTRAM (RAMD32, RADR → O) 0,100 ns**; dây 0,642; LUT6 0,125; dây 0,156; LUT6 0,088; dây 0,072
→ đến R5 ở 2,519 ns, cần trước 4,011 ns (4 ns + lệch clock − độ bất định 0,035 − setup): còn 1,491 ns. Logic chỉ 0,391 ns,
còn lại là dây.

## 3. Hai bộ chọn (mux) giữa R4 và R5

1. **Chọn bank (8:1) trong bảng**: bảng chia 8 bank (32 ô × 8 bit mỗi bank) để một word DMA 64 bit (8 ô) ghi vào 8 bank
   trong cùng một chu kỳ khi nạp bảng; khi đọc, 5 bit cao của chỉ số là địa chỉ trong bank (cả 8 bank đọc cùng lúc), 3 bit
   thấp chọn bank (`value_o = bank_out[index[2:0]]`).
2. **Chọn theo chế độ**: `quant_result = (act_mode == 2) ? table_out : quant_unit_out` (`psum_pipeline.v` dòng 1157): SiLU /
   hard-swish lấy output của bảng; không hàm, ReLU, Leaky ReLU (đã làm trong bộ lượng tử) đi thẳng, nên không phải nạp bảng
   (không tốn 32 chu kỳ). Vivado gộp hai bộ chọn thành 2 tầng LUT6 (đường trên).

`iact_to_psum_mux_reg` (R5) là thanh ghi ghi ngược (gom 4 channel của một pixel), không phải bộ chọn, dù tên có "mux".

## Kết luận

Mỗi tầng tốn đúng 1 chu kỳ theo RTL (mô phỏng), và mọi đường vào từng tầng đều kịp trong 4 ns ở góc chậm nhất (STA: slack
dương, WNS cả thiết kế +0,114 ns). Đường có bảng (R4 → R5) dư nhiều nhất (1,49 ns, 37 % chu kỳ); đường chặt nhất là phép nhân
ở tầng 2 (+0,116 ns), vì mant 25 bit × sum 21 bit lớn hơn một DSP48E2 (27 × 18) nên cần thêm bộ cộng CARRY8 ngoài DSP. Thêm bảng
vào trước phép nhân thì không kịp; đặt sau R4 như hiện nay thì kịp với dư rộng.
