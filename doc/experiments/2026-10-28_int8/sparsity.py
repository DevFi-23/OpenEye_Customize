import numpy as np, emu
d = np.load(emu.MNIST)
X = d["x_test"][:1000, :, :, None].astype(np.int64)
layers = emu.load()
col = []
emu.tflite_exact(X, layers, collect=col)
names = ["conv1 out", "pool1 out (conv2 in)", "conv2 out", "pool2 out (conv3 in)", "conv3 out (fc1 in)", "fc1 out (fc2 in)"]
print("input image: zero pixels (raw 0 when zp = 0) %.1f %%" % (100 * (X == 0).mean()))
for n, t, L in zip(names, col, layers):
    zp = L["zp_out"]
    print(f"{n:22s}: activations at real 0 (int8 == zp {zp}) {100*(t == zp).mean():5.1f} %")
