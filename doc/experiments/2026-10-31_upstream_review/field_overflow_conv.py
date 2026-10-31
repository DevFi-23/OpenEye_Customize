# Status-field overflow for conv models: the MNIST models in use, and bigger layers (what upstream 655a2ae widens)
import os, sys
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "test"))
import test_onnx_model_flow as flow
for k, v in flow.PLATFORM.items():
    os.environ[k] = v
os.environ["QUANT_AMOUNT"] = "256"
import tensorflow as tf
from open_eye import DRAM, data_create, generator, open_eye_parameters as oep, test_utils_main as tum
from open_eye import dense_mapper, conv_mapper, pooling_mapper
found = []
orig = generator.pack_registers
def checked(values, regmap_yaml_path=None):
    transmissions, _ = generator.layout_registers(regmap_yaml_path or generator._default_regmap_dir())
    for regs in transmissions:
        for reg in regs:
            v = values.get(reg["name"], 0)
            if isinstance(v, int) and (v < 0 or v >= (1 << reg["width"])):
                found.append((reg["name"], v, reg["width"]))
    return orig(values, regmap_yaml_path)
for m in (dense_mapper, conv_mapper, pooling_mapper):
    m.pack_registers = checked
cases = [("MNIST_REAL", 4, 8, 28, 1), ("Convolution_Single", 64, 56, 56, 64), ("Convolution_Single", 128, 112, 112, 32),
         ("Convolution_Single", 256, 28, 28, 256)]
for layer, nf, w, h, ch in cases:
    found.clear()
    tf.keras.utils.set_random_seed(1)
    try:
        km = data_create.create_layer(layer, nf, 3, 3, w, h, 1, ch, 10)
        model = [l for l in km.layers if not isinstance(l, tf.keras.layers.Flatten)]
        params = oep.get_oep(1)
        model, lps = flow.build_layers(model, params)
        dram = DRAM.DRAMContents(model, lps)
        dram.write_initial_data_to_dram(model, lps, 0, 0)
        for n in range(len(model)):
            tum.write_stream(params, lps[n], [dram.fmap[n], dram.weights[n], dram.bias[n]], 0, 0)
        print(f"{layer} {w}x{h}x{ch}->{nf}: overflowing fields: {sorted(set(found)) or 'none'}")
    except Exception as e:
        print(f"{layer} {w}x{h}x{ch}->{nf}: toolchain error {type(e).__name__}: {str(e)[:120]}; overflow so far {sorted(set(found))}")
