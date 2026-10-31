# Which status-register fields overflow their width in the current regmap for Dense layers (bug #29 vs upstream 655a2ae)
import os, sys
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "test"))
import test_onnx_model_flow as flow
cr = sys.argv[1] if len(sys.argv) > 1 else "2"
for k, v in flow.PLATFORM.items():
    os.environ[k] = v
os.environ["CLUSTER_ROWS"] = cr
os.environ["QUANT_AMOUNT"] = "64"
import tensorflow as tf
from open_eye import DRAM, data_create, generator, open_eye_parameters as oep, test_utils_main as tum
from open_eye import dense_mapper, conv_mapper
found = []
orig = generator.pack_registers
def checked(values, regmap_yaml_path=None):
    transmissions, _ = generator.layout_registers(regmap_yaml_path or generator._default_regmap_dir())
    for regs in transmissions:
        for reg in regs:
            v = values.get(reg["name"], 0)
            if isinstance(v, (int,)) and (v < 0 or v >= (1 << reg["width"])):
                found.append((reg["name"], v, reg["width"]))
    return orig(values, regmap_yaml_path)
dense_mapper.pack_registers = checked
conv_mapper.pack_registers = checked
for K, N in [(3136, 10), (3136, 16), (3136, 32), (3136, 64), (2560, 32), (2048, 32), (1568, 32), (1024, 64), (512, 32), (508, 32), (64, 40)]:
    found.clear()
    tf.keras.utils.set_random_seed(1)
    km = data_create.create_layer(f"DENSE_CHAIN_{K}_{N}", 4, 3, 3, 8, 1, 1, 1, 10)
    model = [l for l in km.layers if not isinstance(l, tf.keras.layers.Flatten)]
    params = oep.get_oep(1)
    model, lps = flow.build_layers(model, params)
    dram = DRAM.DRAMContents(model, lps)
    dram.write_initial_data_to_dram(model, lps, 0, 0)
    tum.write_stream(params, lps[0], [dram.fmap[0], dram.weights[0], dram.bias[0]], 0, 0)
    print(f"CR{cr} Dense {K}->{N}: overflowing fields: {sorted(set(found)) or 'none'}")
