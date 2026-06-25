"""
TCN Architecture — ICU Septic Shock Monitor
Direkonstruksi dari state_dict best_tcn.pt.

Arsitektur terverifikasi dari state_dict:
  - in_channels = 21 (jumlah fitur final)
  - hidden_size = 32
  - kernel_size = 3
  - n_blocks    = 3
  - dilations   = [1, 2, 4]
  - dropout     = 0.4
  - fc          : Linear(32, 1)
  - Total param : 18.305
  - Tanpa weight_norm (model dilatih tanpa weight_norm)

Referensi: Bai S, Kolter JZ, Koltun V (2018). An empirical evaluation of
  generic convolutional and recurrent networks for sequence modeling.
  arXiv:1803.01271.
"""

import torch
import torch.nn as nn


class CausalConv1d(nn.Module):
    """Dilated causal convolution — tidak bocor ke masa depan."""
    def __init__(self, in_channels: int, out_channels: int,
                 kernel_size: int, dilation: int, dropout: float = 0.4):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv    = nn.Conv1d(in_channels, out_channels, kernel_size,
                                  dilation=dilation, padding=self.padding)
        self.dropout = nn.Dropout(dropout)
        self.relu    = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv(x)
        out = out[:, :, : -self.padding] if self.padding > 0 else out
        return self.dropout(self.relu(out))


class TCNResidualBlock(nn.Module):
    """Residual block: conv1 → conv2 + skip connection."""
    def __init__(self, in_channels: int, out_channels: int,
                 kernel_size: int, dilation: int, dropout: float = 0.4):
        super().__init__()
        self.conv1 = CausalConv1d(in_channels,  out_channels,
                                   kernel_size, dilation, dropout)
        self.conv2 = CausalConv1d(out_channels, out_channels,
                                   kernel_size, dilation, dropout)
        self.downsample = (
            nn.Conv1d(in_channels, out_channels, 1)
            if in_channels != out_channels else None
        )
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv2(self.conv1(x))
        res = self.downsample(x) if self.downsample is not None else x
        return self.relu(out + res)


class TCNModel(nn.Module):
    """
    TCN untuk prediksi septic shock.
    Input : (batch, time, n_features)
    Output: scalar logit per sequence
    """
    def __init__(self, n_features: int = 21, hidden_size: int = 32,
                 kernel_size: int = 3, n_blocks: int = 3,
                 dropout: float = 0.4):
        super().__init__()
        dilations = [2 ** i for i in range(n_blocks)]
        blocks = []
        for i, d in enumerate(dilations):
            in_ch = n_features if i == 0 else hidden_size
            blocks.append(TCNResidualBlock(in_ch, hidden_size,
                                           kernel_size, d, dropout))
        self.blocks  = nn.ModuleList(blocks)
        self.fc      = nn.Linear(hidden_size, 1)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # (batch, time, features) → (batch, features, time)
        out = x.transpose(1, 2)
        for block in self.blocks:
            out = block(out)
        out = out.mean(dim=2)          # global avg pool → (batch, hidden)
        return self.fc(self.dropout(out)).squeeze(-1)
