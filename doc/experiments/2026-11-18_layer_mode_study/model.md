## Cost model check (step 1d): per layer, predicted from the sweep against measured

Prediction: sparse compute = dense compute x the sweep ratio at the layer's input zero share (same shape class and cluster configuration; MNIST runs at CR 2 X 4); load_wght from the transfer sizes. Differences as a share of the dense layer.

| run | layer | class | input zeros | sparse - dense measured | predicted | choice today measured / predicted | P1 - dense measured | predicted | choice with P1 measured / predicted |
|---|---|---|---:|---:|---:|---|---:|---:|---|
| MNIST relu | Conv 28x28x1 -> 32 | conv1 | 0.0 % | +2,0 % | +2,0 % | dense / dense | +1,5 % | +1,5 % | dense / dense |
| MNIST relu | Conv 14x14x32 -> 64 | conv2 | 43.5 % | -2,2 % | -2,4 % | sparse / sparse | -7,9 % | -8,1 % | sparse / sparse |
| MNIST relu | Conv 7x7x64 -> 64 | conv3 | 87.3 % | -12,1 % | -15,1 % | sparse / sparse | -22,7 % | -25,7 % | sparse / sparse |
| MNIST relu | Dense 3136 -> 10 | fc | 74.3 % | +22,1 % | +19,5 % | dense / dense | -7,4 % | -10,1 % | sparse / sparse |
| MNIST leaky_relu | Conv 28x28x1 -> 32 | conv1 | 0.0 % | +2,0 % | +2,0 % | dense / dense | +1,5 % | +1,5 % | dense / dense |
| MNIST leaky_relu | Conv 14x14x32 -> 64 | conv2 | 24.3 % | +4,2 % | +3,5 % | dense / dense | -1,5 % | -2,2 % | sparse / sparse |
| MNIST leaky_relu | Conv 7x7x64 -> 64 | conv3 | 14.7 % | +7,5 % | +7,3 % | dense / dense | -3,1 % | -3,3 % | sparse / sparse |
| MNIST leaky_relu | Dense 3136 -> 10 | fc | 18.1 % | +29,8 % | +29,0 % | dense / dense | +0,3 % | -0,5 % | dense / sparse |
| MNIST silu | Conv 28x28x1 -> 32 | conv1 | 0.0 % | +2,0 % | +2,0 % | dense / dense | +1,5 % | +1,5 % | dense / dense |
| MNIST silu | Conv 14x14x32 -> 64 | conv2 | 11.0 % | +5,4 % | +4,8 % | dense / dense | -0,3 % | -1,0 % | sparse / sparse |
| MNIST silu | Conv 7x7x64 -> 64 | conv3 | 7.1 % | +8,8 % | +8,1 % | dense / dense | -1,8 % | -2,5 % | sparse / sparse |
| MNIST silu | Dense 3136 -> 10 | fc | 6.7 % | +30,6 % | +29,9 % | dense / dense | +1,1 % | +0,4 % | dense / dense |
| MNIST hardswish | Conv 28x28x1 -> 32 | conv1 | 0.0 % | +2,0 % | +2,0 % | dense / dense | +1,5 % | +1,5 % | dense / dense |
| MNIST hardswish | Conv 14x14x32 -> 64 | conv2 | 5.9 % | +5,7 % | +5,2 % | dense / dense | -0,1 % | -0,5 % | sparse / sparse |
| MNIST hardswish | Conv 7x7x64 -> 64 | conv3 | 14.1 % | +8,5 % | +7,3 % | dense / dense | -2,1 % | -3,2 % | sparse / sparse |
| MNIST hardswish | Dense 3136 -> 10 | fc | 13.1 % | +30,3 % | +29,4 % | dense / dense | +0,8 % | -0,1 % | dense / sparse |
| T2 cr1_x2_y3 ReLU | Conv 28x28x1 -> 16 | conv1 | 0.0 % | +1,9 % | +1,7 % | dense / dense | +1,9 % | +1,6 % | dense / dense |
| T2 cr1_x2_y3 ReLU | Conv 14x14x16 -> 32 | conv2 | 10.7 % | -0,4 % | -1,2 % | sparse / sparse | -1,2 % | -2,0 % | sparse / sparse |
| T2 cr1_x2_y3 ReLU | Conv 7x7x32 -> 32 | conv3 | 53.3 % | -15,8 % | -12,3 % | sparse / sparse | -18,9 % | -15,4 % | sparse / sparse |
| T2 cr1_x2_y3 ReLU | Dense 1568 -> 32 | fc | 85.4 % | +6,2 % | +6,8 % | dense / dense | -16,9 % | -16,3 % | sparse / sparse |
| T2 cr2_x4_y3 ReLU | Conv 28x28x1 -> 16 | conv1 | 0.0 % | +2,0 % | +2,0 % | dense / dense | +1,5 % | +1,5 % | dense / dense |
| T2 cr2_x4_y3 ReLU | Conv 14x14x16 -> 32 | conv2 | 10.7 % | +5,0 % | +4,4 % | dense / dense | -0,3 % | -0,9 % | sparse / sparse |
| T2 cr2_x4_y3 ReLU | Conv 7x7x32 -> 32 | conv3 | 53.3 % | -4,0 % | -1,5 % | sparse / sparse | -13,9 % | -11,4 % | sparse / sparse |
| T2 cr2_x4_y3 ReLU | Dense 1568 -> 32 | fc | 85.4 % | +23,4 % | +24,0 % | dense / dense | -12,5 % | -11,8 % | sparse / sparse |
| T2 cr8_x4_y3 ReLU | Conv 28x28x1 -> 16 | conv1 | 0.0 % | +2,2 % | +2,2 % | dense / dense | +1,1 % | +1,1 % | dense / dense |
| T2 cr8_x4_y3 ReLU | Conv 14x14x16 -> 32 | conv2 | 10.7 % | +9,0 % | +8,6 % | dense / dense | +0,6 % | +0,3 % | dense / dense |
| T2 cr8_x4_y3 ReLU | Conv 7x7x32 -> 32 | conv3 | 53.3 % | +8,5 % | +9,1 % | dense / dense | -2,7 % | -2,1 % | sparse / sparse |
| T2 cr8_x4_y3 ReLU | Dense 1568 -> 32 | fc | 85.4 % | +32,9 % | +33,1 % | dense / dense | -3,8 % | -3,5 % | sparse / sparse |

Right choices: today 28 of 28 (cycles lost by the wrong ones 0), with P1 26 of 28 (lost 110).
