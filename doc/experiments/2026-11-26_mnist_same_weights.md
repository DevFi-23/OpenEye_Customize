# MNIST không hàm kích hoạt và 4 hàm trên cùng weight (2026-11-26)

Các model MNIST đã huấn luyện đều có hàm kích hoạt (mỗi hàm một model), nên chưa có số chu kỳ của mạng không hàm. Ở đây lấy
weight của model ReLU (`doc/demo_notebooks/mnist_unquantized_model.pth`) và chạy với từng hàm, kể cả không hàm (hàm đồng
nhất: `models/mnist_conv_net.py` thêm `"none": nn.Identity()`), ảnh test 0, CR 2 X 4 Y 3, sparse và dense, RTL `abd2bb8`.
Model không hàm không phải model huấn luyện cho không hàm (độ chính xác khác), nhưng chu kỳ chỉ phụ thuộc kích thước layer
và số 0. Script `2026-11-26_mnist_same_weights/run_same.py <activation> <sparse|dense>`; profile
`doc/perf/act_same_weights_2026-11-26/`. 10/10 PASS (mỗi buffer và kết quả khớp tham chiếu).

| hàm | sparse | so với không hàm | dense | so với không hàm | số 0 ở input Conv2 / Conv3 / Dense |
|---|---:|---:|---:|---:|---|
| không hàm | 217.947 | | 202.895 | | 8,1 / 7,4 / 5,1 % |
| ReLU | 196.238 | −21.709 (−9,96 %) | 202.895 | 0 | 43,5 / 87,3 / 74,3 % |
| Leaky ReLU (slope 0,1) | 216.095 | −1.852 (−0,85 %) | 202.895 | 0 | 7,5 / 19,4 / 13,8 % |
| SiLU | 218.010 | +63 (+0,03 %) | 202.959 | +64 | 5,1 / 7,8 / 7,3 % |
| hard-swish | 217.838 | −109 (−0,05 %) | 202.959 | +64 | 5,3 / 13,8 / 14,0 % |

- Hiệu số theo pha (sparse): ReLU / Leaky ReLU chỉ ở `compute`; SiLU / hard-swish `load_act` +96, `writeback` −32 (Conv1 che
  32 chu kỳ nạp bảng bằng thời gian chờ trải bảng bias), `compute` −1 / −173. Dense: chỉ `load_act` +96 và `writeback` −32.
- ReLU cùng weight = 196.238, đúng bằng lần chạy model ReLU ngày 19/11 (lặp lại từng chu kỳ).
- Không hàm, MNIST trên sparse chậm hơn dense 7,4 %: lợi thế của sparse trên MNIST đến từ số 0 của ReLU.
