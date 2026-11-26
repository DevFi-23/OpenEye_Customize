# Kiểm tra lại bản sửa test_dense_output / #21 và đối chiếu upstream (2026-11-23)

Bản sửa của phiên 21/11 (commit `6a7a323`, `doc/experiments/2026-11-21_test_dense_output.md`): thêm hai trường
`output_cycles` / `needed_psum_transmissions` vào fixture của `test/test_dense_output.py` (11 test hỏng từ upstream `23be043`)
và sửa bộ giải mã output Dense của testbench (`rtl_test_utils.compare_stream_Dense`, #21) giải mã theo lượt r, địa chỉ a, cột c:
`f = r·CX·P + c·P + a`. Kiểm lại bằng `2026-11-23_dense_output_check.py` (kết quả `2026-11-23_dense_output_check.json`) và chạy
lại 15 test RTL `test/cocotb_fpga/test_dense_readout.py`.

| Kiểm tra | dev (`abd2bb8`) | upstream (`12340ab`, mới nhất) |
|---|---|---|
| `test/test_dense_output.py` của chính cây đó | **31 qua, 0 hỏng** | 0 qua, **11 hỏng**: 8 × `TypeError: compare_stream_Dense() missing 1 required positional argument: 'rel_layers'`, 3 × `FileNotFoundError` (`make_ref` không ghi `dma_stream_ref.txt`) |
| Khứ hồi `make_ref` → bộ giải mã, N = 1–200 × CX = 1 / 2 / 4 | **600/600 đúng** | công thức `f = offset + (beat % CX)·P + beat // CX` (rtl_test_utils.py dòng 3187): **304/600 sai** = mọi Dense có hơn 16·CX output khi CX ≥ 2 (từ lượt thứ hai) |
| `test_dense_readout.py` (15 test RTL: Dense 64 → 40 / 34 / 100, 16 → 64, 1568 → 40, CR 1 / 4, `NUM_GLB_IACT` 3, `NUM_GLB_PSUM` 2, dense, chuỗi 2 Dense, GEMM) | **15/15 PASS** (chạy lại 23/11) | không có |

Kết luận: bản sửa đúng và đủ. Cả hai lỗi đều là testbench (RTL gửi đúng mọi lượt, luồng output trùng từng byte với tham chiếu,
đã kiểm 21/11); upstream vẫn còn cả hai (test lỗi thời, bộ giải mã cũ) nên không có gì để lấy từ upstream ở phần này.
