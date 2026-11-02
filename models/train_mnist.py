"""train_mnist.py --activation <relu|leaky_relu|silu|hardswish> [--negative-slope A] [--epochs N] [--out FILE]

Trains models/mnist_conv_net.SimpleMNISTConvNet with the given activation the way doc/demo_notebooks/mnist_pytorch.ipynb
trained the original checkpoint (Adam, learning rate 0.001, batch 64, 5 epochs, StepLR(step 3, gamma 0.7),
cross-entropy, dropout 0.5 before FC1), on the MNIST images of open_eye.data_create.mnist_images (normalised as in
training). Saves a checkpoint in the notebook's format (epoch, model_state_dict, optimizer_state_dict, test_accuracy)
plus the activation and its negative slope, by default doc/demo_notebooks/mnist_<activation>_model.pth (ignored by
git, like the original). Seeded, CPU. Run from the repository root with the project venv:
  venv/bin/python models/train_mnist.py --activation silu
"""
import argparse
import os
import sys

import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
from mnist_conv_net import ACTIVATIONS, SimpleMNISTConvNet  # noqa: E402


def load_activation_model(path):
    """SimpleMNISTConvNet with the activation stored in a checkpoint of this script (ReLU for the original one)."""
    checkpoint = torch.load(path, map_location="cpu")
    model = SimpleMNISTConvNet(checkpoint.get("activation", "relu"), checkpoint.get("negative_slope", 0.1))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, checkpoint


def accuracy(model, x, y, batch=1000):
    model.eval()
    correct = 0
    with torch.no_grad():
        for i in range(0, len(x), batch):
            correct += int((model(x[i:i + batch]).argmax(1) == y[i:i + batch]).sum())
    return 100.0 * correct / len(x)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--activation", choices=ACTIVATIONS, required=True)
    parser.add_argument("--negative-slope", type=float, default=0.1, help="Leaky ReLU slope (default 0.1)")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", help="checkpoint (default doc/demo_notebooks/mnist_<activation>_model.pth)")
    args = parser.parse_args()
    out = args.out or os.path.join(REPO, "doc", "demo_notebooks", f"mnist_{args.activation}_model.pth")

    from open_eye import data_create
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    x_train, y_train = data_create.mnist_images("train", range(60000))
    x_test, y_test = data_create.mnist_images("test", range(10000))
    x_train, x_test = torch.from_numpy(x_train), torch.from_numpy(x_test)
    y_train, y_test = torch.from_numpy(y_train.astype(np.int64)), torch.from_numpy(y_test.astype(np.int64))

    model = SimpleMNISTConvNet(args.activation, args.negative_slope)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.7)
    accuracies = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = torch.randperm(len(x_train))
        for i in range(0, len(x_train), 64):
            idx = order[i:i + 64]
            optimizer.zero_grad()
            loss = criterion(model(x_train[idx]), y_train[idx])
            loss.backward()
            optimizer.step()
        scheduler.step()
        accuracies.append(accuracy(model, x_test, y_test))
        print(f"{args.activation}: epoch {epoch}, loss {loss.item():.4f}, test accuracy {accuracies[-1]:.2f} %", flush=True)
    torch.save({"epoch": args.epochs, "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(), "test_accuracy": max(accuracies),
                "activation": args.activation, "negative_slope": args.negative_slope}, out)
    print(f"saved {out} (best test accuracy {max(accuracies):.2f} %)")


if __name__ == "__main__":
    main()
