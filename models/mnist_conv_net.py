import torch
import torch.nn as nn
import torch.nn.functional as F

# Activation functions of the conv blocks: the default "relu" is the original model (F.relu, the trained checkpoint
# doc/demo_notebooks/mnist_unquantized_model.pth); the others are variants for the activation work of the fork
# (models/train_mnist.py, doc/experiments/2026-11-02_activation_plan.md). None of them has parameters, so the state
# dict is the same for every activation.
ACTIVATIONS = ("relu", "leaky_relu", "silu", "hardswish")


class SimpleMNISTConvNet(nn.Module):
    def __init__(self, activation="relu", negative_slope=0.1):
        super(SimpleMNISTConvNet, self).__init__()
        if activation not in ACTIVATIONS:
            raise ValueError(f"activation {activation!r} is not one of {ACTIVATIONS}")
        self.activation = activation
        self.negative_slope = negative_slope
        self.act = {"relu": nn.ReLU(), "leaky_relu": nn.LeakyReLU(negative_slope), "silu": nn.SiLU(),
                    "hardswish": nn.Hardswish()}[activation]

        # 1. Conv-Block (Output: 32 Kanäle)
        self.Conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.Pool1 = nn.MaxPool2d(2, 2)
        
        # 2. Conv-Block (Output: 64 Kanäle) -> Hier lag der Unterschied!
        self.Conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.Pool2 = nn.MaxPool2d(2, 2)
        
        # 3. Conv-Block (Output: 64 Kanäle)
        self.Conv3 = nn.Conv2d(64, 64, kernel_size=3, padding=1)
        
        # Linear-Layer: 64 Kanäle * 7 * 7 = 3136 Features (genau wie im Original)
        self.FC1 = nn.Linear(3136, 10)
        
        self.dropout = nn.Dropout(0.5)
    
    def _act(self, x):
        # The original model calls F.relu; keep exactly that graph for "relu"
        return F.relu(x) if self.activation == "relu" else self.act(x)

    def forward(self, x):
        # Conv1 -> ReLU -> MaxPool1: (1, 28, 28) -> (32, 28, 28) -> (32, 14, 14)
        x = self.Pool1(self._act(self.Conv1(x)))

        # Conv2 -> ReLU -> MaxPool2: (32, 14, 14) -> (64, 14, 14) -> (64, 7, 7)
        x = self.Pool2(self._act(self.Conv2(x)))

        # Conv3 -> ReLU: (64, 7, 7) -> (64, 7, 7)
        x = self._act(self.Conv3(x))
        
        # Flatten: (64, 7, 7) -> 3136 Features
        x = torch.flatten(x, 1)
        
        x = self.dropout(x)
        x = self.FC1(x)
        return x
    
# Load model
def load_simple_mnist_model(model_path, model, optimizer=None, device='cpu'):
    """Loads a saved model"""
    checkpoint = torch.load(model_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    
    if optimizer:
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    
    epoch = checkpoint['epoch']
    accuracy = checkpoint['test_accuracy']
    
    print(f"Model loaded - Epoch: {epoch}, Accuracy: {accuracy:.2f}%")
    return model, optimizer, epoch, accuracy