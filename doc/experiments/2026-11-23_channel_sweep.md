# Quét số channel / số filter trên RTL hiện tại (2026-11-23)

RTL `abd2bb8` (sau các sửa #7, #9, #50, #51 ngày 22/11). Weight và input ngẫu nhiên (`OPENEYE_SEED=1`), kernel 3 × 3, CR 2
(2 × 2 cluster), `NUM_GLB_PSUM` 4, `NUM_GLB_WGHT` 3, DMA 64 bit, cả sparse và dense; mỗi lần so từng giá trị output và bộ đệm
activation giữa các layer với tham chiếu của testbench. 168 lần chạy (`test_channels.py`, `run_channels.py`,
kết quả `out/status.json`, `out/progress.txt`). Chỉ đo, không sửa code dự án.

Phân loại (`run_channels.py classify`): đúng; đệm rồi đúng (layer đầu được `channel_pad` đệm channel 0); **SAI** = RTL chạy và
output hoặc bộ đệm activation khác tham chiếu, hoặc output chứa X; bị chặn = một kiểm tra của Python (`NotImplementedError`)
từ chối có chủ đích; Python dừng = lỗi Python (bộ mã hoá weight, tạo tham chiếu) trước hoặc trong khi chạy.

| Vị trí | Chế độ | Kết quả |
|---|---|---|
| Layer đầu, Conv 16×4×C → 8 (C = 1–34) | sparse | đúng: 1, 2, 4, 8, 12, 16, 20, 24, 28, 32; đệm rồi đúng: 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33; SAI: 6, 10, 14, 18, 22, 26, 30, 34 |
| Layer đầu, Conv 16×4×C → 8 (C = 1–34) | dense | đúng: 1, 2, 4, 8, 12, 16, 20, 24, 28, 32; đệm rồi đúng: 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33; SAI: 6, 10, 14, 18, 22, 26, 30, 34 |
| Layer giữa, Conv 16×4×4 → F → F (F = 1–20) | sparse | Python dừng: 1, 3, 5, 7, 9, 11, 13, 15, 17, 18; SAI: 2, 6, 10, 14; đúng: 4, 8, 12, 16, 20; bị chặn: 19 |
| Layer giữa, Conv 16×4×4 → F → F (F = 1–20) | dense | bị chặn: 1, 3, 5, 7, 9, 11, 13, 15, 17–19; SAI: 2, 6, 10, 14; đúng: 4, 8, 12, 16, 20 |
| Trước Dense, Conv 8×4×4 → F, flatten, Dense → 10 (F = 1–18) | sparse | Python dừng: 1–3, 5–7, 9–11, 13–15, 17, 18; đúng: 4, 8, 12, 16 |
| Trước Dense, Conv 8×4×4 → F, flatten, Dense → 10 (F = 1–18) | dense | bị chặn: 1, 3, 6, 10, 14, 18; Python dừng: 2, 5, 7, 9, 11, 13, 15, 17; đúng: 4, 8, 12, 16 |
| Layer cuối, Conv 16×4×4 → F (F = 1–12) | sparse | Python dừng: 1, 3, 5, 7, 9, 11; đúng: 2, 4, 6, 8, 10, 12 |
| Layer cuối, Conv 16×4×4 → F (F = 1–12) | dense | bị chặn: 1, 3, 5, 7, 9, 11; đúng: 2, 4, 6, 8, 10, 12 |

## Kết luận

1. **Layer đầu, C chia 4 dư 2 và C > 2 (6, 10, …, 34) = #45, còn mở, không có kiểm tra chặn.** Sparse: output sai lặng lẽ
   (`Difference found at f = 0, x = 0, y = 0`); dense: output chứa X. Mẫu lặp lại đúng chu kỳ 4 đến C = 34. C lẻ được đệm
   (3 → 4, 5 → 8, …, 33 → 36) và đúng; C = 1, 2 và C chia hết cho 4 đúng.
2. **Layer giữa: chỉ F chia hết cho 4 đúng.** F chia 4 dư 2, kể cả F = 2: bộ đệm activation sau ghi ngược khác tham chiếu
   (F = 6: word 0–31 đúng, sai từ word 32 = nhóm 4 channel thứ hai; F = 2: sai từ word 0), cả hai chế độ.
3. **Trước Dense: chỉ F chia hết cho 4 chạy được** (4, 8, 12, 16); còn lại Python dừng (bộ mã hoá weight; `KeyError: 0` trong
   `make_ref`; `IndexError` trong `fill_dram_with_ref` với F = 2) hoặc bị chặn (#48 trên dense).
4. **Số filter mỗi PE lẻ:** layer cuối với F lẻ: sparse dừng ở bộ mã hoá weight (`encoded columns need … words, the PE block
   has …` / `column cannot be encoded without an all-zero word`), dense bị #48 chặn; F chẵn đều đúng (2, 6, 10 cũng đúng ở
   layer cuối). Vậy lỗi của F chia 4 dư 2 ở layer giữa là lỗi số channel, còn F lẻ là lỗi số filter.

## Nguyên nhân (#45 và layer giữa)

* Python gửi activation của layer đầu theo nhóm `used_channels` channel (`iact_stream_mapper.py` 186–197): trong nhóm, các
  channel của một pixel liền nhau; nhóm cuối chỉ ghi channel có thật. Kernel 3 × 3: `used_channels = min(C, 4)`
  (`layer_parameters.py` 1100–1122: 16 // 3 = 5, làm tròn xuống lũy thừa của 2).
* RTL đọc mỗi pixel `channel_div_trans = ceil(used_channels / 2)` lần 2 channel = 4 ô ở mọi nhóm. Nhóm cuối có 2 giá trị mỗi
  pixel (C chia 4 dư 2) → từ pixel thứ hai mọi giá trị trượt. C = 2: `used_channels = 2`, đọc 2 ô, khớp.
* Layer giữa: bộ ghi ngược ghi theo nhóm 4 channel mỗi pixel (#25), nhóm cuối thiếu → bộ đệm khác bố cục layer sau đọc.

## Đề xuất (Python, cần đồng ý)

* Đệm layer đầu có C chia 4 dư 2 lên bội của 4 (như C lẻ, `channel_pad.pad_first_layer`).
* Chặn layer giữa / Dense có số channel không chia hết cho 4 với thông báo rõ (hoặc đệm filter 0 ở layer trước).
* Kiểm tra sớm số filter mỗi PE lẻ với thông báo rõ.
