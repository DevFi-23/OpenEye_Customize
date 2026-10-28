import numpy as np, tensorflow as tf, emu
images = np.load(emu.MNIST)
xt, yt = images["x_test"], images["y_test"]
layers = emu.load()
it = tf.lite.Interpreter(model_path=emu.MODEL, experimental_preserve_all_tensors=True,
                         experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
it.allocate_tensors()
td = {t["index"]: t for t in it.get_tensor_details()}
outs = [op["outputs"][0] for op in it._get_ops_details() if op["op_name"] in ("CONV_2D", "FULLY_CONNECTED", "MAX_POOL_2D")]
inp = it.get_input_details()[0]["index"]
n, mism, ref_hits = 300, np.zeros(len(outs), int), 0; maxd = [0]*len(outs)
for k in range(n):
    it.set_tensor(inp, (xt[k:k+1, :, :, None] / 255.0).astype(np.float32)); it.invoke()
    col = []
    emu.tflite_exact(xt[k:k+1, :, :, None].astype(np.int64), layers, collect=col)
    for j, o in enumerate(outs):
        ref = it.get_tensor(o).astype(np.int64).reshape(col[j].shape)
        mism[j] += int((ref != col[j]).sum()); d = np.abs(ref - col[j]); maxd[j] = max(maxd[j], int(d.max()))
    ref_hits += int(np.argmax(it.get_tensor(outs[-1])) == yt[k])
print("bit mismatches per layer (emulator vs TFLite reference kernels, %d images):" % n, mism.tolist())
print("TFLite reference-kernel accuracy on these images: %.2f %%" % (100 * ref_hits / n))
print("max |difference| per layer:", maxd)
